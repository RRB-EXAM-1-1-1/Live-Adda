"""
YouTube Live Streaming integration for Live Adda.
Handles OAuth2 (channel connect), live broadcast/stream creation & binding,
and ffmpeg-based RTMP push of pre-uploaded videos.

Requires env: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET
"""
import json
import os
import signal
import subprocess
import logging
import threading
import time
from datetime import datetime, timezone

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# OAuth scopes required for live streaming
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.readonly",
]

# YouTube RTMP ingestion base
RTMP_BASE = "rtmp://a.rtmp.youtube.com/live2"


def is_configured() -> bool:
    """Whether YouTube OAuth credentials are set in the environment."""
    return bool(os.environ.get("YOUTUBE_CLIENT_ID")) and bool(os.environ.get("YOUTUBE_CLIENT_SECRET"))


def _client_config(redirect_uri: str) -> dict:
    return {
        "web": {
            "client_id": os.environ["YOUTUBE_CLIENT_ID"],
            "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }


def build_authorization_url(redirect_uri: str, state: str) -> str:
    """Return the Google consent-screen URL for the user to authorize their channel."""
    flow = Flow.from_client_config(
        _client_config(redirect_uri),
        scopes=YOUTUBE_SCOPES,
        redirect_uri=redirect_uri,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return auth_url


def exchange_code_for_tokens(redirect_uri: str, code: str) -> dict:
    """Exchange the OAuth authorization code for tokens."""
    flow = Flow.from_client_config(
        _client_config(redirect_uri),
        scopes=YOUTUBE_SCOPES,
        redirect_uri=redirect_uri,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "scopes": creds.scopes,
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }


def _credentials_from_doc(doc: dict) -> Credentials:
    creds = Credentials(
        token=doc.get("token"),
        refresh_token=doc.get("refresh_token"),
        token_uri=doc.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=doc.get("scopes", YOUTUBE_SCOPES),
    )
    # Refresh if needed
    if not creds.valid and creds.refresh_token:
        creds.refresh(GoogleRequest())
    return creds


def get_channel_info(account_doc: dict) -> dict:
    """Fetch the connected channel's title/id for display."""
    creds = _credentials_from_doc(account_doc)
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    resp = youtube.channels().list(part="snippet,statistics", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        return {}
    item = items[0]
    return {
        "channel_id": item["id"],
        "channel_title": item["snippet"]["title"],
        "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
        "subscriber_count": item.get("statistics", {}).get("subscriberCount"),
    }


def create_broadcast_and_stream(account_doc: dict, title: str, description: str = "") -> dict:
    """Create a liveBroadcast + liveStream, bind them, and return the RTMP ingestion info."""
    creds = _credentials_from_doc(account_doc)
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Create the broadcast
    broadcast = youtube.liveBroadcasts().insert(
        part="snippet,status,contentDetails",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "scheduledStartTime": now_iso,
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            },
            "contentDetails": {
                "enableAutoStart": True,
                "enableAutoStop": True,
            },
        },
    ).execute()
    broadcast_id = broadcast["id"]

    # 2. Create the stream
    stream = youtube.liveStreams().insert(
        part="snippet,cdn,contentDetails,status",
        body={
            "snippet": {"title": f"{title} - stream"},
            "cdn": {
                "ingestionType": "rtmp",
                "resolution": "variable",
                "frameRate": "variable",
            },
            "contentDetails": {"isReusable": True},
        },
    ).execute()
    stream_id = stream["id"]
    ingestion = stream["cdn"]["ingestionInfo"]
    stream_key = ingestion["streamName"]
    ingestion_address = ingestion["ingestionAddress"]

    # 3. Bind broadcast to stream
    youtube.liveBroadcasts().bind(
        id=broadcast_id,
        part="id,contentDetails",
        streamId=stream_id,
    ).execute()

    return {
        "broadcast_id": broadcast_id,
        "stream_id": stream_id,
        "stream_key": stream_key,
        "ingestion_address": ingestion_address,
        "watch_url": f"https://www.youtube.com/watch?v={broadcast_id}",
    }


# Track Popen handles by PID so we can .wait() them on stop and avoid zombies.
# If the backend restarts we lose this map; the reaper below (psutil) handles
# such orphans by signalling directly and marking DB rows stopped.
_running_procs: "dict[int, subprocess.Popen]" = {}
_procs_lock = threading.Lock()


def _probe_codecs(video_path: str) -> "tuple[str | None, str | None]":
    """Return (video_codec, audio_codec) for a local file, or (None, None) on error."""
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-print_format", "json",
                "-show_streams", "-select_streams", "v:0,a:0", video_path,
            ],
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
        streams = json.loads(out).get("streams", [])
        v = next((s.get("codec_name") for s in streams if s.get("codec_type") == "video"), None)
        a = next((s.get("codec_name") for s in streams if s.get("codec_type") == "audio"), None)
        return v, a
    except Exception as e:
        logger.warning(f"ffprobe failed for {video_path}: {e}")
        return None, None


def start_ffmpeg_push(video_path: str, stream_key: str, loop: bool = True) -> int:
    """Start an ffmpeg process pushing the given local video to YouTube RTMP.

    CPU optimizations for shared 2 vCPU droplet:
      1. If the source is already h264+aac (YouTube-compatible), use `-c copy`
         so no re-encoding happens (near-zero CPU).
      2. Otherwise re-encode with `-preset ultrafast` and a 1200k target
         bitrate (matches 720p reasonably, avoids CPU throttling blur).
      3. Spawn in its own process group so we can SIGTERM/SIGKILL the whole
         group on stop and never leak orphaned encoders.
    """
    rtmp_url = f"{RTMP_BASE}/{stream_key}"
    v_codec, a_codec = _probe_codecs(video_path)
    can_copy = (v_codec == "h264" and a_codec == "aac")

    cmd: list[str] = ["ffmpeg", "-re"]
    if loop:
        cmd += ["-stream_loop", "-1"]
    cmd += ["-i", video_path]

    if can_copy:
        # Zero-encode passthrough. YouTube accepts this as-is.
        cmd += ["-c", "copy", "-bsf:a", "aac_adtstoasc"]
        mode = "copy"
    else:
        # Ultrafast preset trades a bit of compression efficiency for a
        # large CPU drop — right call on a 2 vCPU box under contention.
        cmd += [
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-b:v", "1200k", "-maxrate", "1500k", "-bufsize", "3000k",
            "-pix_fmt", "yuv420p", "-g", "60",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        ]
        mode = "reencode-ultrafast"

    cmd += ["-f", "flv", rtmp_url]

    log_path = f"/tmp/ffmpeg_{stream_key[:8]}.log"
    logf = open(log_path, "wb")
    # start_new_session=True → new process group, so os.killpg reaches every
    # child ffmpeg spawns (filters, muxers, etc.) and nothing is left behind.
    proc = subprocess.Popen(
        cmd, stdout=logf, stderr=logf, stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    with _procs_lock:
        _running_procs[proc.pid] = proc
    logger.info(
        f"Started ffmpeg push PID={proc.pid} mode={mode} "
        f"src_codecs=v:{v_codec}/a:{a_codec} -> {RTMP_BASE}/***"
    )
    return proc.pid


def stop_ffmpeg_push(pid: int) -> bool:
    """Terminate an ffmpeg push cleanly, escalating to SIGKILL and always
    reaping the child so we never leave zombie processes behind.
    """
    if not pid:
        return False

    with _procs_lock:
        proc = _running_procs.pop(pid, None)

    # Path 1: we still hold the Popen — clean, in-process kill + reap.
    if proc is not None:
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception as e:
            logger.warning(f"SIGTERM to pgid failed pid={pid}: {e}")
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning(f"ffmpeg pid={pid} ignored SIGTERM, sending SIGKILL")
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass
            try:
                proc.wait(timeout=3)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"proc.wait failed pid={pid}: {e}")
        return True

    # Path 2: backend restarted and lost the handle — signal by PID.
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except ProcessLookupError:
        return False
    except Exception:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return False
        except Exception as e:
            logger.error(f"stop_ffmpeg_push signal failed pid={pid}: {e}")
            return False
    # Escalate if still alive
    for _ in range(10):
        try:
            os.kill(pid, 0)  # existence check
        except ProcessLookupError:
            return True
        time.sleep(0.5)
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
    return True


def reap_finished_pushes() -> list[int]:
    """Reap any tracked ffmpeg processes that exited on their own (e.g. YouTube
    dropped the connection, source file was removed). Returns list of PIDs
    that finished. Callers should mark the DB row `is_live=False` for these.
    """
    finished: list[int] = []
    with _procs_lock:
        for pid, proc in list(_running_procs.items()):
            rc = proc.poll()
            if rc is not None:
                _running_procs.pop(pid, None)
                finished.append(pid)
                logger.info(f"ffmpeg pid={pid} exited on its own rc={rc}")
    return finished


def transition_broadcast(account_doc: dict, broadcast_id: str, status: str) -> dict:
    """Transition a broadcast to 'testing', 'live', or 'complete'."""
    creds = _credentials_from_doc(account_doc)
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    return youtube.liveBroadcasts().transition(
        broadcastStatus=status,
        id=broadcast_id,
        part="id,status",
    ).execute()
