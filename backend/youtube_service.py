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

# YouTube RTMP ingestion base. RTMPS is preferred: it survives firewalls/DPI
# that occasionally drop bare RTMP packets and causes the "not receiving enough
# video" alert. YouTube accepts the same stream key on both.
RTMP_BASE = "rtmps://a.rtmp.youtube.com/live2"


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


def _probe_gop_seconds(video_path: str) -> float:
    """Measure the average distance (in seconds) between video keyframes in
    the first ~30s of the file. YouTube requires ≤2s (with 4s as absolute max)
    to keep live latency low and avoid rebuffering. Returns 99.0 if we can't
    tell — caller will treat that as "unsafe for -c copy" and force re-encode.
    """
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-read_intervals", "%+30",
                "-select_streams", "v:0",
                "-show_entries", "packet=pts_time,flags",
                "-of", "csv=p=0", video_path,
            ],
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).decode(errors="ignore")
    except Exception as e:
        logger.warning(f"gop probe failed for {video_path}: {e}")
        return 99.0
    key_times: list[float] = []
    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) < 2:
            continue
        pts, flags = parts[0], parts[1]
        if "K" in flags:
            try:
                key_times.append(float(pts))
            except ValueError:
                continue
    if len(key_times) < 2:
        return 99.0
    diffs = [b - a for a, b in zip(key_times, key_times[1:])]
    return sum(diffs) / len(diffs) if diffs else 99.0


def start_ffmpeg_push(video_path: str, stream_key: str, loop: bool = True, bitrate_k: int = 1800) -> int:
    """Start an ffmpeg process pushing the given local video to YouTube RTMPS.

    Two modes, chosen automatically:

    * **Stream-copy** (`-c copy`, near-zero CPU) — only used when the source is
      already h264+aac AND its keyframes land ≤2.5s apart. YouTube live
      requires a keyframe every ~2s; any longer and viewers see the
      "not receiving enough video" buffering alert.

    * **Re-encode** (`-preset ultrafast`) — used for everything else. Emits
      a constant bitrate (CBR) stream with a hard-forced 2-second GOP,
      constant frame rate, and normalized timestamps. These are the specific
      flags YouTube's live-encoder guidelines call out as required for a
      stable ingest.

    Both paths spawn in their own process group so `stop_ffmpeg_push` can
    take the whole tree down cleanly (no zombies, instant CPU release).

    Raises FileNotFoundError if the source is missing. Raises RuntimeError if
    ffmpeg dies within the first second (usually means bad codec/key/network).
    """
    # Fail fast + loud when the file is missing — otherwise ffmpeg would emit
    # a cryptic "No such file" into a log the operator will never look at.
    if not video_path or not os.path.exists(video_path):
        raise FileNotFoundError(f"Video source not found on disk: {video_path}")
    if not stream_key:
        raise ValueError("stream_key is empty")

    rtmp_url = f"{RTMP_BASE}/{stream_key}"
    v_codec, a_codec = _probe_codecs(video_path)
    codec_ok = (v_codec == "h264" and a_codec == "aac")
    can_copy = False
    gop_s = None
    if codec_ok:
        gop_s = _probe_gop_seconds(video_path)
        can_copy = gop_s <= 2.5

    # Common input + timing flags. `-re` paces reads at native frame rate so
    # we don't flood YouTube; `-fflags +genpts` and `-avoid_negative_ts` fix
    # broken PTS from user uploads that otherwise cause ingest desyncs.
    cmd: list[str] = [
        "ffmpeg",
        "-fflags", "+genpts",
        "-avoid_negative_ts", "make_zero",
        "-re",
    ]
    if loop:
        cmd += ["-stream_loop", "-1"]
    cmd += ["-i", video_path]

    if can_copy:
        # Zero-encode passthrough. `aac_adtstoasc` fixes AAC framing for FLV.
        cmd += [
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
        ]
        mode = f"copy (gop≈{gop_s:.1f}s)"
    else:
        # CBR + fixed 2-second GOP + CFR — the trifecta that stops YouTube's
        # "buffering" alerts. `-tune zerolatency` keeps encoder buffers small
        # so packets leave promptly instead of bunching up.
        cmd += [
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-profile:v", "high", "-level", "4.1",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            # Fixed GOP: keyframe every 60 frames (2 s @ 30 fps). `sc_threshold=0`
            # blocks scene-cut keyframes from breaking the cadence.
            "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
            # True CBR — RTMP smoothness needs steady bytes/sec, not VBR bursts.
            "-b:v", f"{bitrate_k}k", "-minrate", f"{bitrate_k}k", "-maxrate", f"{bitrate_k}k",
            "-bufsize", f"{bitrate_k * 2}k",
            "-x264-params", "nal-hrd=cbr:force-cfr=1",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            # Resamples audio so loop-boundary jitter doesn't drift out of sync.
            "-af", "aresample=async=1",
        ]
        mode = f"reencode-ultrafast (src gop={gop_s})"

    # `-flvflags no_duration_filesize` — cleaner FLV framing for live; some
    # RTMP endpoints reject the default duration/size headers on infinite streams.
    cmd += ["-f", "flv", "-flvflags", "no_duration_filesize", rtmp_url]

    # Persistent log location. Tries /var/log/live-adda first (production),
    # falls back to /tmp so dev/preview still works.
    log_dir = "/var/log/live-adda/ffmpeg"
    try:
        os.makedirs(log_dir, exist_ok=True)
    except (PermissionError, OSError):
        log_dir = "/tmp"
    log_path = f"{log_dir}/ffmpeg_{stream_key[:8]}_{int(time.time())}.log"
    logf = open(log_path, "wb")
    # start_new_session=True → new process group, so os.killpg reaches every
    # child ffmpeg spawns (filters, muxers, etc.) and nothing is left behind.
    proc = subprocess.Popen(
        cmd, stdout=logf, stderr=logf, stdin=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Health check: give ffmpeg 1.2 s to survive. If it exits inside that
    # window it means the command was invalid (bad codec, bad key, DNS fail).
    # We surface the last 300 bytes of stderr so the caller can log a useful
    # error instead of a silent 500.
    time.sleep(1.2)
    rc = proc.poll()
    if rc is not None:
        # Read the tail of the log for context
        tail = ""
        try:
            with open(log_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 400))
                tail = f.read().decode(errors="ignore").strip()
        except Exception:
            pass
        raise RuntimeError(
            f"ffmpeg exited immediately (rc={rc}). Tail: {tail[-300:]}"
        )

    with _procs_lock:
        _running_procs[proc.pid] = proc
    logger.info(
        f"Started ffmpeg push PID={proc.pid} mode={mode} "
        f"src_codecs=v:{v_codec}/a:{a_codec} log={log_path} -> {RTMP_BASE}/***"
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
