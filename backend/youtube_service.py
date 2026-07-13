"""
YouTube Live Streaming integration for Live Adda.
Handles OAuth2 (channel connect), live broadcast/stream creation & binding,
and ffmpeg-based RTMP push of pre-uploaded videos.

Requires env: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET
"""
import os
import subprocess
import logging
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


def start_ffmpeg_push(video_path: str, stream_key: str, loop: bool = True) -> int:
    """Start an ffmpeg process pushing the given local video to YouTube RTMP.
    Returns the process PID. Uses -c copy when possible for low CPU.
    """
    rtmp_url = f"{RTMP_BASE}/{stream_key}"
    cmd = ["ffmpeg", "-re"]
    if loop:
        cmd += ["-stream_loop", "-1"]
    cmd += [
        "-i", video_path,
        "-c:v", "libx264", "-preset", "veryfast", "-b:v", "2500k",
        "-maxrate", "2500k", "-bufsize", "5000k", "-pix_fmt", "yuv420p", "-g", "60",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-f", "flv", rtmp_url,
    ]
    log_path = f"/tmp/ffmpeg_{stream_key[:8]}.log"
    with open(log_path, "wb") as logf:
        proc = subprocess.Popen(cmd, stdout=logf, stderr=logf)
    logger.info(f"Started ffmpeg push PID={proc.pid} -> {RTMP_BASE}/***")
    return proc.pid


def stop_ffmpeg_push(pid: int) -> bool:
    """Stop a running ffmpeg push process by PID."""
    try:
        os.kill(pid, 15)  # SIGTERM
        return True
    except ProcessLookupError:
        return False
    except Exception as e:
        logger.error(f"Failed to stop ffmpeg PID={pid}: {e}")
        return False


def transition_broadcast(account_doc: dict, broadcast_id: str, status: str) -> dict:
    """Transition a broadcast to 'testing', 'live', or 'complete'."""
    creds = _credentials_from_doc(account_doc)
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    return youtube.liveBroadcasts().transition(
        broadcastStatus=status,
        id=broadcast_id,
        part="id,status",
    ).execute()
