from fastapi import FastAPI, APIRouter, Request, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import aiofiles
import asyncio
# emergentintegrations is optional (Emergent-internal only). Legacy Stripe endpoints
# degrade gracefully if unavailable. Razorpay is the primary payment path.
try:
    from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
    STRIPE_AVAILABLE = True
except ImportError:
    StripeCheckout = None
    CheckoutSessionRequest = None
    STRIPE_AVAILABLE = False
import razorpay
import hmac
import hashlib
import youtube_service

# Build SHA is resolved once at first request and cached
_BUILD_SHA_CACHE = None

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Constants
JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"
MAX_STORAGE_BYTES = int(os.environ.get('MAX_STORAGE_GB', '2')) * 1024 * 1024 * 1024  # 2GB
STRIPE_API_KEY = os.environ['STRIPE_API_KEY']
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)) if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET else None

# Create uploads directory
UPLOAD_DIR = ROOT_DIR / 'uploads' / 'videos'
THUMBNAIL_DIR = ROOT_DIR / 'uploads' / 'thumbnails'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

# Plan configurations
PLANS = {
    "daily": {"price": 4.99, "inr": 35, "duration_days": 1, "name": "Daily"},
    "weekly": {"price": 24.99, "inr": 199, "duration_days": 7, "name": "Weekly"},
    "monthly": {"price": 79.99, "inr": 599, "duration_days": 30, "name": "Monthly"},
    # Admin/lifetime plan — never expires, 3 concurrent stream slots.
    # Not sold; assigned manually to admin/staff accounts.
    "lifetime": {"price": 0, "inr": 0, "duration_days": 36500, "name": "Lifetime (Admin)"}
}

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    plan: Optional[str] = None
    plan_expires_at: Optional[datetime] = None
    storage_used: int = 0
    created_at: datetime

class VideoUpload(BaseModel):
    video_id: str
    user_id: str
    title: str
    duration: str
    size: int
    file_path: str
    thumbnail_url: Optional[str] = None
    uploaded_at: datetime

class VideoRename(BaseModel):
    title: str

class LiveSlotSettings(BaseModel):
    auto_rotate: bool
    loop_videos: bool

class StreamKeyStart(BaseModel):
    video_id: str
    stream_key: str
    loop: bool = True

class SupportTicket(BaseModel):
    subject: str
    message: str

# ==================== UTILITY FUNCTIONS ====================

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        "type": "access"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "refresh"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(request: Request) -> dict:
    """Extract and validate JWT from cookies or Authorization header"""
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==================== SLOT STACKING (Active Plans) ====================
#
# Each user has an `active_plans` array holding one entry PER non-expired plan.
# Every entry = +1 stream slot. Buying the same plan again extends that entry's
# expires_at (stacks duration, no new slot). Buying a different plan appends a
# NEW entry (adds a slot). Admin `lifetime` overrides everything to 3 slots.
#
# Entry shape: {"plan_id": str, "purchased_at": datetime, "expires_at": datetime}


def _as_utc(dt) -> Optional[datetime]:
    """Normalize a stored datetime (may be str or naive) to a tz-aware UTC datetime."""
    if not dt:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _active_entries(user: dict) -> List[dict]:
    """Return the entries in user['active_plans'] whose expires_at > now.
    Backward compat: if active_plans is missing, synthesize from legacy plan fields.
    Lifetime (admin) is NOT a stackable entry — it grants a fixed 3 slots via
    compute_stream_slots — so we return an empty list for lifetime users."""
    if user.get("plan") == "lifetime":
        return []
    now = datetime.now(timezone.utc)
    entries = list(user.get("active_plans") or [])
    # Legacy migration on the fly: if the user has legacy plan/plan_expires_at but
    # no active_plans array yet, synthesize a single entry.
    if not entries and user.get("plan") and user.get("plan_expires_at"):
        legacy_exp = _as_utc(user.get("plan_expires_at"))
        if legacy_exp:
            entries = [{
                "plan_id": user["plan"],
                "purchased_at": _as_utc(user.get("plan_started_at")) or now,
                "expires_at": legacy_exp,
            }]
    live = []
    for e in entries:
        exp = _as_utc(e.get("expires_at"))
        if exp and exp > now:
            live.append({
                "plan_id": e.get("plan_id"),
                "purchased_at": _as_utc(e.get("purchased_at")) or now,
                "expires_at": exp,
            })
    return live


def compute_stream_slots(user: dict) -> int:
    """How many concurrent streams this user is allowed to run."""
    if user.get("plan") == "lifetime":
        return int(user.get("stream_slots") or 3)
    live = _active_entries(user)
    return len(live)


async def sync_user_plans_and_enforce_slots(user: dict) -> dict:
    """Prune expired entries, refresh legacy display fields, and if the user's
    concurrent-stream count now EXCEEDS their slots, stop the excess ffmpeg
    processes (most-recent-first) so slot count and running streams stay
    consistent. Returns the refreshed user doc."""
    if user.get("plan") == "lifetime":
        return user

    live = _active_entries(user)

    # Update stored active_plans + legacy display fields
    if live:
        # Display "latest expiring" plan as the primary one
        primary = max(live, key=lambda e: e["expires_at"])
        legacy_plan = primary["plan_id"]
        legacy_expiry = primary["expires_at"]
    else:
        legacy_plan = None
        legacy_expiry = None

    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "active_plans": live,
            "plan": legacy_plan,
            "plan_expires_at": legacy_expiry,
            "stream_slots": (3 if user.get("plan") == "lifetime" else len(live)),
        }}
    )

    # Enforce slot budget: if streams > slots, stop the newest excess streams
    max_slots = len(live)
    active_streams = await db.live_streams.find(
        {"user_id": user["user_id"], "is_live": True}
    ).sort("started_at", -1).to_list(50)
    if len(active_streams) > max_slots:
        to_stop = active_streams[: len(active_streams) - max_slots]
        for s in to_stop:
            if s.get("ffmpeg_pid"):
                try:
                    youtube_service.stop_ffmpeg_push(s["ffmpeg_pid"])
                except Exception as e:
                    logger.warning(f"Failed to stop excess ffmpeg pid={s['ffmpeg_pid']}: {e}")
            await db.live_streams.update_one(
                {"_id": s["_id"]},
                {"$set": {
                    "is_live": False,
                    "ffmpeg_pid": None,
                    "stopped_at": datetime.now(timezone.utc),
                    "stopped_reason": "plan_expired_slot_shrink",
                }}
            )
            logger.info(f"Stopped excess stream {s.get('stream_id')} for user {user['user_id']} — slot count shrank to {max_slots}")
            # Auto-delete the video attached to this just-stopped stream
            # (guards against another live slot still using the same video_id).
            await cleanup_stream_video_if_orphaned(user["user_id"], s.get("video_id"))

    refreshed = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
    return refreshed or user


async def _delete_video_files_and_row(user_id: str, video_id: str) -> int:
    """Delete a single video's file + thumbnail + Mongo row AND refund the
    user's storage_used counter by the video's byte size. Returns the number
    of bytes freed (0 if the video didn't exist)."""
    if not video_id:
        return 0
    video = await db.videos.find_one({"user_id": user_id, "video_id": video_id})
    if not video:
        return 0
    freed = int(video.get("size", 0) or 0)
    # Delete the main file
    file_path = video.get("file_path")
    if file_path:
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Failed to delete video file {file_path}: {e}")
    # Delete the JPEG thumbnail if it exists
    try:
        (UPLOAD_DIR / "thumbnails" / f"{video_id}.jpg").unlink(missing_ok=True)
    except Exception:
        pass
    # Refund storage_used (guard against going negative)
    await db.users.update_one(
        {"user_id": user_id},
        {"$inc": {"storage_used": -freed}}
    )
    await db.users.update_one(
        {"user_id": user_id, "storage_used": {"$lt": 0}},
        {"$set": {"storage_used": 0}}
    )
    await db.videos.delete_one({"video_id": video_id, "user_id": user_id})
    logger.info(f"Deleted video {video_id} for user {user_id} — freed {freed} bytes")
    return freed


async def cleanup_stream_video_if_orphaned(user_id: str, video_id: Optional[str]) -> None:
    """Delete the video associated with a just-stopped stream, but ONLY if no
    OTHER live stream on the same account still references it (so we don't
    yank a video out from under another active slot)."""
    if not video_id:
        return
    still_used = await db.live_streams.count_documents({
        "user_id": user_id, "is_live": True, "video_id": video_id
    })
    if still_used > 0:
        logger.info(f"Video {video_id} still used by {still_used} other live stream(s) — skipping delete")
        return
    await _delete_video_files_and_row(user_id, video_id)


async def wipe_all_videos_for_user(user_id: str) -> int:
    """Delete every video (file + row) belonging to a user and reset the
    storage counter. Called when every plan on the account has expired so the
    server's disk isn't held hostage by users who've stopped paying.
    Returns count of videos deleted."""
    count = 0
    async for v in db.videos.find({"user_id": user_id}):
        vid_id = v.get("video_id")
        if not vid_id:
            continue
        # Best-effort file cleanup
        fp = v.get("file_path")
        if fp:
            try: Path(fp).unlink(missing_ok=True)
            except Exception: pass
        try:
            (UPLOAD_DIR / "thumbnails" / f"{vid_id}.jpg").unlink(missing_ok=True)
        except Exception:
            pass
        count += 1
    if count > 0:
        await db.videos.delete_many({"user_id": user_id})
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"storage_used": 0}}
        )
        logger.info(f"Wiped {count} videos for user {user_id} (all plans expired)")
    return count


async def activate_or_extend_plan(user_id: str, plan_id: str) -> dict:
    """Idempotently apply a plan purchase to a user's active_plans.
    - If the user already has a non-expired entry for the same plan_id:
      EXTEND that entry's expires_at by plan.duration_days (stack).
    - Otherwise: APPEND a new entry (adds a stream slot).
    Also updates legacy plan / plan_expires_at fields to the latest-expiring plan.
    Returns the fresh user doc."""
    plan = PLANS[plan_id]
    now = datetime.now(timezone.utc)

    user = await db.users.find_one({"user_id": user_id})
    live = _active_entries(user or {})

    # Find existing entry for the same plan_id (stack duration)
    existing = next((e for e in live if e["plan_id"] == plan_id), None)
    if existing:
        existing["expires_at"] = existing["expires_at"] + timedelta(days=plan["duration_days"])
    else:
        live.append({
            "plan_id": plan_id,
            "purchased_at": now,
            "expires_at": now + timedelta(days=plan["duration_days"]),
        })

    # Sort by expires_at descending; the latest-expiring is the "display primary"
    live.sort(key=lambda e: e["expires_at"], reverse=True)
    primary = live[0]

    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "active_plans": live,
            "plan": primary["plan_id"],
            "plan_expires_at": primary["expires_at"],
            "stream_slots": len(live),
        }}
    )
    logger.info(
        f"Plan '{plan_id}' activated for user {user_id} — total active plans = {len(live)} (slots)."
    )
    return await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})


async def check_active_plan(user: dict):
    """Check if user has at least one non-expired plan (or lifetime)."""
    if user.get("plan") == "lifetime":
        return
    live = _active_entries(user)
    if not live:
        # Also clear stale legacy fields
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"active_plans": [], "plan": None, "plan_expires_at": None, "stream_slots": 0}}
        )
        # Auto-cleanup: stop any lingering ffmpeg process, delete their videos.
        # Runs at most once per user (subsequent calls find no videos to wipe).
        try:
            async for s in db.live_streams.find({"user_id": user["user_id"], "is_live": True}):
                if s.get("ffmpeg_pid"):
                    try:
                        youtube_service.stop_ffmpeg_push(s["ffmpeg_pid"])
                    except Exception:
                        pass
                await db.live_streams.update_one(
                    {"_id": s["_id"]},
                    {"$set": {
                        "is_live": False,
                        "ffmpeg_pid": None,
                        "stopped_at": datetime.now(timezone.utc),
                        "stopped_reason": "all_plans_expired",
                    }}
                )
            await wipe_all_videos_for_user(user["user_id"])
        except Exception as e:
            logger.warning(f"Cleanup after plan expiry failed for user {user['user_id']}: {e}")
        raise HTTPException(
            status_code=403,
            detail="⚠️ Please purchase a slot/plan first to proceed."
        )
    # Auto-sync: prune expired entries + stop excess streams if a plan expired since last call
    stored = user.get("active_plans") or []
    if len(stored) != len(live) or any(_as_utc(e.get("expires_at")) is None for e in stored):
        await sync_user_plans_and_enforce_slots(user)

async def check_storage_limit(user: dict, additional_size: int):
    """Check if adding file would exceed 2GB storage limit"""
    current_storage = user.get("storage_used", 0)
    if (current_storage + additional_size) > MAX_STORAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Storage limit exceeded. You have {MAX_STORAGE_BYTES / (1024**3):.2f} GB limit. Current usage: {current_storage / (1024**3):.2f} GB"
        )

# ==================== AUTHENTICATION ENDPOINTS ====================

@api_router.post("/auth/register")
async def register(user_data: UserRegister):
    """Register new user with email/password"""
    email = user_data.email.lower()
    
    # Check if user exists
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    password_hash = hash_password(user_data.password)
    
    user_doc = {
        "user_id": user_id,
        "email": email,
        "name": user_data.name,
        "password_hash": password_hash,
        "plan": None,
        "plan_expires_at": None,
        "storage_used": 0,
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.users.insert_one(user_doc)
    
    # Create tokens
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    
    # Prepare response
    response = JSONResponse({
        "user_id": user_id,
        "email": email,
        "name": user_data.name,
        "plan": None,
        "storage_used": 0
    })
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=43200,
        path="/"
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=604800,
        path="/"
    )
    
    return response

@api_router.post("/auth/login")
async def login(credentials: UserLogin):
    """Login with email/password"""
    email = credentials.email.lower()
    
    # Find user
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Create tokens
    access_token = create_access_token(user["user_id"], email)
    refresh_token = create_refresh_token(user["user_id"])
    
    # Prepare response
    response_data = {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "plan": user.get("plan"),
        "plan_expires_at": user.get("plan_expires_at").isoformat() if user.get("plan_expires_at") else None,
        "storage_used": user.get("storage_used", 0)
    }
    
    response = JSONResponse(response_data)
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=43200,
        path="/"
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=604800,
        path="/"
    )
    
    return response

@api_router.post("/auth/logout")
async def logout():
    """Logout user"""
    response = JSONResponse({"message": "Logged out successfully"})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return response

@api_router.post("/auth/refresh")
async def refresh_token(request: Request):
    """Issue a new access token using the refresh_token cookie."""
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_access = create_access_token(user["user_id"], user["email"])
    response = JSONResponse({"message": "Token refreshed"})
    response.set_cookie(
        key="access_token", value=new_access, httponly=True,
        secure=False, samesite="lax", max_age=43200, path="/"
    )
    return response

@api_router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current user info"""
    live_plans = _active_entries(user)
    # Serialize datetimes for JSON
    active_plans_serial = [
        {
            "plan_id": e["plan_id"],
            "purchased_at": e["purchased_at"].isoformat() if hasattr(e["purchased_at"], "isoformat") else str(e["purchased_at"]),
            "expires_at": e["expires_at"].isoformat() if hasattr(e["expires_at"], "isoformat") else str(e["expires_at"]),
        }
        for e in live_plans
    ]
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "plan": user.get("plan"),
        "plan_expires_at": user.get("plan_expires_at").isoformat() if user.get("plan_expires_at") else None,
        "active_plans": active_plans_serial,
        "storage_used": user.get("storage_used", 0),
        "role": user.get("role"),
        "stream_slots": compute_stream_slots(user),
    }


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


@api_router.put("/auth/profile")
async def update_profile(data: ProfileUpdate, user: dict = Depends(get_current_user)):
    """Update the current user's name, email, and/or password.
    Password change requires current_password. Email change requires uniqueness."""
    updates = {}

    if data.name and data.name.strip() and data.name != user["name"]:
        updates["name"] = data.name.strip()

    if data.email:
        new_email = data.email.lower()
        if new_email != user["email"]:
            clash = await db.users.find_one({"email": new_email, "user_id": {"$ne": user["user_id"]}})
            if clash:
                raise HTTPException(status_code=400, detail="This email is already in use.")
            updates["email"] = new_email

    if data.new_password:
        if not data.current_password:
            raise HTTPException(status_code=400, detail="Current password is required to change password.")
        # Re-load the user WITH password_hash (get_current_user strips it)
        full_user = await db.users.find_one({"user_id": user["user_id"]})
        if not full_user or not verify_password(data.current_password, full_user["password_hash"]):
            raise HTTPException(status_code=401, detail="Current password is incorrect.")
        if len(data.new_password) < 6:
            raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")
        updates["password_hash"] = hash_password(data.new_password)

    if not updates:
        return {"message": "Nothing to update.", "updated": False}

    await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
    return {"message": "Profile updated successfully.", "updated": True, "fields": list(updates.keys())}

# ==================== VIDEO MANAGEMENT ENDPOINTS ====================

@api_router.post("/videos/upload")
async def upload_video(
    file: UploadFile = File(...),
    title: str = Form(...),
    user: dict = Depends(get_current_user)
):
    """Upload video with streaming/chunked write to safely handle files up to 2GB"""
    # Check active plan
    await check_active_plan(user)

    # Remaining storage budget for this user (2GB - already used)
    current_storage = user.get("storage_used", 0)
    remaining_budget = MAX_STORAGE_BYTES - current_storage
    if remaining_budget <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Storage limit reached. You have a {MAX_STORAGE_BYTES / (1024**3):.0f} GB limit."
        )

    # Prepare destination
    video_id = f"video_{uuid.uuid4().hex[:12]}"
    file_extension = Path(file.filename).suffix
    file_path = UPLOAD_DIR / f"{video_id}{file_extension}"

    # Stream file to disk in 8MB chunks, enforcing the storage limit incrementally
    CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB - fewer awaits = faster throughput
    file_size = 0
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                file_size += len(chunk)
                # Enforce 2GB limit mid-stream; abort if exceeded
                if file_size > remaining_budget:
                    await f.close()
                    if file_path.exists():
                        file_path.unlink()
                    raise HTTPException(
                        status_code=400,
                        detail=f"Storage limit exceeded. You have {MAX_STORAGE_BYTES / (1024**3):.0f} GB limit. "
                               f"Current usage: {current_storage / (1024**3):.2f} GB"
                    )
                await f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        # Clean up partial file on any failure
        if file_path.exists():
            file_path.unlink()
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed. Please try again.")

    # Create video document
    video_doc = {
        "video_id": video_id,
        "user_id": user["user_id"],
        "title": title,
        "duration": "00:00",  # Will be calculated by video processing
        "size": file_size,
        "file_path": str(file_path),
        "thumbnail_url": None,
        "uploaded_at": datetime.now(timezone.utc),
        "processing_status": "completed"
    }
    
    await db.videos.insert_one(video_doc)
    
    # Update user storage
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$inc": {"storage_used": file_size}}
    )
    
    # Calculate remaining plan validity
    plan_expires_at = user.get("plan_expires_at")
    if plan_expires_at:
        if isinstance(plan_expires_at, str):
            plan_expires_at = datetime.fromisoformat(plan_expires_at)
        if plan_expires_at.tzinfo is None:
            plan_expires_at = plan_expires_at.replace(tzinfo=timezone.utc)
        
        remaining_seconds = (plan_expires_at - datetime.now(timezone.utc)).total_seconds()
        remaining_days = int(remaining_seconds // 86400)
        remaining_hours = int(remaining_seconds // 3600)
        if remaining_days >= 1:
            remaining_message = f"{remaining_days} days remaining"
        else:
            remaining_message = f"{remaining_hours} hours remaining"
    else:
        remaining_message = "No active plan"
    
    return {
        "video_id": video_id,
        "title": title,
        "size": file_size,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "message": f"✅ Ready for the stream! Plan validity: {remaining_message}"
    }

def _plan_validity_message(user: dict) -> str:
    plan_expires_at = user.get("plan_expires_at")
    if not plan_expires_at:
        return "No active plan"
    if isinstance(plan_expires_at, str):
        plan_expires_at = datetime.fromisoformat(plan_expires_at)
    if plan_expires_at.tzinfo is None:
        plan_expires_at = plan_expires_at.replace(tzinfo=timezone.utc)
    remaining_seconds = (plan_expires_at - datetime.now(timezone.utc)).total_seconds()
    remaining_days = int(remaining_seconds // 86400)
    remaining_hours = int(remaining_seconds // 3600)
    return f"{remaining_days} days remaining" if remaining_days >= 1 else f"{remaining_hours} hours remaining"

@api_router.get("/videos/upload/status/{upload_id}")
async def get_upload_status(upload_id: str, user: dict = Depends(get_current_user)):
    """Returns how many bytes the server has already received for this upload_id,
    or the finalized video if the upload has already completed. Used by the
    frontend to resume interrupted uploads without re-sending completed chunks."""
    # Was it already finalized?
    existing = await db.videos.find_one(
        {"user_id": user["user_id"], "upload_id": upload_id},
        {"_id": 0}
    )
    if existing:
        return {
            "completed": True,
            "received_bytes": existing["size"],
            "video_id": existing["video_id"],
            "title": existing["title"],
        }

    safe_id = f"{user['user_id']}_{upload_id}".replace("/", "_")
    part_path = UPLOAD_DIR / "tmp" / f"{safe_id}.part"
    received = part_path.stat().st_size if part_path.exists() else 0
    return {"completed": False, "received_bytes": received}


@api_router.post("/videos/upload/chunk")
async def upload_video_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    filename: str = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    offset: int = Form(0),
    user: dict = Depends(get_current_user)
):
    """Chunked, resumable, idempotent upload.
    - `offset` is the byte position where this chunk begins in the final file.
    - The server truncates the part file to `offset` before appending, so
      retrying the same chunk (transient network fail) never causes duplication.
    - Finalize is idempotent on `(user_id, upload_id)`: a retried final chunk
      returns the existing video instead of inserting a second row.
    """
    await check_active_plan(user)

    # If this upload is already finalized, short-circuit idempotently
    existing = await db.videos.find_one(
        {"user_id": user["user_id"], "upload_id": upload_id},
        {"_id": 0}
    )
    if existing:
        return {
            "status": "completed",
            "video_id": existing["video_id"],
            "title": existing["title"],
            "size": existing["size"],
            "uploaded_at": (existing["uploaded_at"].isoformat()
                            if hasattr(existing["uploaded_at"], "isoformat")
                            else str(existing["uploaded_at"])),
            "message": f"✅ Ready for the stream! Plan validity: {_plan_validity_message(user)}",
            "idempotent": True,
        }

    # Namespace the temp file by user to prevent collisions/abuse
    safe_id = f"{user['user_id']}_{upload_id}".replace("/", "_")
    tmp_dir = UPLOAD_DIR / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    part_path = tmp_dir / f"{safe_id}.part"

    # Fresh start on chunk 0 with offset 0
    if chunk_index == 0 and offset == 0 and part_path.exists():
        part_path.unlink()

    # Read the chunk bytes
    content = await file.read()

    # Enforce the 2GB budget incrementally (based on final projected size)
    projected_size = offset + len(content)
    remaining_budget = MAX_STORAGE_BYTES - user.get("storage_used", 0)
    if projected_size > remaining_budget:
        part_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Storage limit exceeded. You have {MAX_STORAGE_BYTES / (1024**3):.0f} GB limit."
        )

    # Truncate/create at the exact offset so retries are byte-safe.
    # `r+b` requires the file to exist and won't truncate; we handle both cases.
    current_size = part_path.stat().st_size if part_path.exists() else 0
    if offset > current_size:
        # Client is skipping bytes the server never received — refuse.
        raise HTTPException(
            status_code=409,
            detail=f"Upload offset gap: server has {current_size} bytes, client sent offset {offset}. Restart upload."
        )
    # Truncate to offset (drops any bytes past this point from a prior retry)
    async with aiofiles.open(part_path, 'ab') as f:
        await f.truncate(offset)
        await f.write(content)

    # Not the last chunk yet
    if chunk_index + 1 < total_chunks:
        return {
            "status": "chunk_received",
            "chunk_index": chunk_index,
            "received_bytes": part_path.stat().st_size,
        }

    # Final chunk -> finalize (guarded again against concurrent duplicate finalize)
    existing = await db.videos.find_one(
        {"user_id": user["user_id"], "upload_id": upload_id},
        {"_id": 0}
    )
    if existing:
        return {
            "status": "completed",
            "video_id": existing["video_id"],
            "title": existing["title"],
            "size": existing["size"],
            "uploaded_at": (existing["uploaded_at"].isoformat()
                            if hasattr(existing["uploaded_at"], "isoformat")
                            else str(existing["uploaded_at"])),
            "message": f"✅ Ready for the stream! Plan validity: {_plan_validity_message(user)}",
            "idempotent": True,
        }

    video_id = f"video_{uuid.uuid4().hex[:12]}"
    file_extension = Path(filename).suffix or ".mp4"
    final_path = UPLOAD_DIR / f"{video_id}{file_extension}"
    part_path.rename(final_path)
    file_size = final_path.stat().st_size

    video_doc = {
        "video_id": video_id,
        "user_id": user["user_id"],
        "upload_id": upload_id,  # idempotency key
        "title": title,
        "duration": "00:00",
        "size": file_size,
        "file_path": str(final_path),
        "thumbnail_url": None,
        "uploaded_at": datetime.now(timezone.utc),
        "processing_status": "completed"
    }
    try:
        await db.videos.insert_one(video_doc)
    except Exception as e:
        # Unique index on (user_id, upload_id) — another finalize won the race.
        logger.warning(f"Finalize race for upload_id={upload_id}: {e}")
        # Clean up the duplicate file we just renamed and return the existing one.
        try:
            final_path.unlink(missing_ok=True)
        except Exception:
            pass
        existing = await db.videos.find_one(
            {"user_id": user["user_id"], "upload_id": upload_id},
            {"_id": 0}
        )
        if existing:
            return {
                "status": "completed",
                "video_id": existing["video_id"],
                "title": existing["title"],
                "size": existing["size"],
                "uploaded_at": (existing["uploaded_at"].isoformat()
                                if hasattr(existing["uploaded_at"], "isoformat")
                                else str(existing["uploaded_at"])),
                "message": f"✅ Ready for the stream! Plan validity: {_plan_validity_message(user)}",
                "idempotent": True,
            }
        raise

    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$inc": {"storage_used": file_size}}
    )

    # Generate thumbnail asynchronously (non-blocking) — extracts a JPEG frame
    # from the video via ffmpeg so the Video Manager can show a preview.
    try:
        thumb_dir = UPLOAD_DIR / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumb_dir / f"{video_id}.jpg"
        # Grab a frame at ~1 second, scaled to max width 640. Fast (<1s) for MP4/MOV.
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-ss", "00:00:01", "-i", str(final_path),
            "-vframes", "1", "-vf", "scale=640:-2", "-q:v", "5", str(thumb_path),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        # Wait up to 8s; if ffmpeg is slow, keep going without a thumbnail.
        try:
            await asyncio.wait_for(proc.wait(), timeout=8.0)
            if thumb_path.exists() and thumb_path.stat().st_size > 0:
                await db.videos.update_one(
                    {"video_id": video_id},
                    {"$set": {"thumbnail_url": f"/api/videos/{video_id}/thumbnail"}}
                )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Thumbnail generation failed for {video_id}: {e}")

    # Extract duration + resolution via ffprobe (non-blocking; JSON output)
    duration_seconds = 0
    duration_str = "00:00"
    width = 0
    height = 0
    try:
        probe = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "format=duration:stream=width,height",
            "-of", "csv=p=0", str(final_path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            stdout, _ = await asyncio.wait_for(probe.communicate(), timeout=6.0)
        except asyncio.TimeoutError:
            try: probe.kill()
            except Exception: pass
            stdout = b""
        # ffprobe csv output shape: "1920,1080\n<seconds>\n"
        lines = [ln.strip() for ln in stdout.decode(errors="ignore").splitlines() if ln.strip()]
        for ln in lines:
            if "," in ln and width == 0:
                w, _, h = ln.partition(",")
                try:
                    width = int(w); height = int(h.split(",")[0])
                except Exception:
                    pass
            else:
                try:
                    duration_seconds = int(float(ln))
                except Exception:
                    pass
        if duration_seconds > 0:
            mins, secs = divmod(duration_seconds, 60)
            hrs, mins = divmod(mins, 60)
            duration_str = (f"{hrs}:{mins:02d}:{secs:02d}" if hrs else f"{mins}:{secs:02d}")
        if duration_seconds or width or height:
            await db.videos.update_one(
                {"video_id": video_id},
                {"$set": {
                    "duration": duration_str,
                    "duration_seconds": duration_seconds,
                    "width": width,
                    "height": height,
                }}
            )
    except Exception as e:
        logger.warning(f"ffprobe metadata extraction failed for {video_id}: {e}")

    return {
        "status": "completed",
        "video_id": video_id,
        "title": title,
        "size": file_size,
        "duration": duration_str,
        "duration_seconds": duration_seconds,
        "width": width,
        "height": height,
        "thumbnail_url": f"/api/videos/{video_id}/thumbnail",
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "message": f"✅ Ready for the stream! Plan validity: {_plan_validity_message(user)}"
    }

@api_router.get("/videos")
async def get_videos(user: dict = Depends(get_current_user)):
    """Get all videos for current user"""
    videos = await db.videos.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(1000)
    return videos


@api_router.get("/videos/{video_id}/thumbnail")
async def get_video_thumbnail(video_id: str, user: dict = Depends(get_current_user)):
    """Serve a JPEG thumbnail for a video the user owns. Lazily generates the
    thumbnail if it's missing (e.g. for videos uploaded before this feature)."""
    from fastapi.responses import FileResponse
    video = await db.videos.find_one({"video_id": video_id, "user_id": user["user_id"]})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    thumb_dir = UPLOAD_DIR / "thumbnails"
    thumb_path = thumb_dir / f"{video_id}.jpg"
    if not thumb_path.exists():
        # Try to generate on-the-fly
        thumb_dir.mkdir(parents=True, exist_ok=True)
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-ss", "00:00:01", "-i", str(video["file_path"]),
                "-vframes", "1", "-vf", "scale=640:-2", "-q:v", "5", str(thumb_path),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                await asyncio.wait_for(proc.wait(), timeout=8.0)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass
        except Exception:
            pass
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not available yet")
    return FileResponse(str(thumb_path), media_type="image/jpeg")

@api_router.put("/videos/{video_id}/rename")
async def rename_video(
    video_id: str,
    data: VideoRename,
    user: dict = Depends(get_current_user)
):
    """Rename a video"""
    video = await db.videos.find_one({"video_id": video_id, "user_id": user["user_id"]})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    await db.videos.update_one(
        {"video_id": video_id},
        {"$set": {"title": data.title}}
    )
    
    return {"message": "Video renamed successfully", "title": data.title}

@api_router.delete("/videos/{video_id}")
async def delete_video(video_id: str, user: dict = Depends(get_current_user)):
    """Delete a video"""
    video = await db.videos.find_one({"video_id": video_id, "user_id": user["user_id"]})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Delete file
    file_path = Path(video["file_path"])
    if file_path.exists():
        file_path.unlink()
    
    # Update storage
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$inc": {"storage_used": -video["size"]}}
    )
    
    # Delete from database
    await db.videos.delete_one({"video_id": video_id})
    
    return {"message": "Video deleted successfully"}

# ==================== LIVE SLOT ENDPOINTS ====================

@api_router.get("/live-slot")
async def get_live_slot(user: dict = Depends(get_current_user)):
    """Get live slot status"""
    await check_active_plan(user)
    
    live_stream = await db.live_streams.find_one({"user_id": user["user_id"]}, {"_id": 0})
    
    if not live_stream:
        return {
            "is_live": False,
            "current_video": None,
            "viewers": 0,
            "uptime": "0h 0m",
            "next_video": None
        }
    
    return live_stream

@api_router.post("/live-slot/start")
async def start_streaming(user: dict = Depends(get_current_user)):
    """Start live streaming"""
    await check_active_plan(user)
    
    # Get first video
    videos = await db.videos.find({"user_id": user["user_id"]}).to_list(10)
    if not videos:
        raise HTTPException(status_code=400, detail="No videos available to stream")
    
    # Create or update live stream
    stream_doc = {
        "stream_id": f"stream_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "is_live": True,
        "current_video": videos[0]["title"],
        "viewers": 0,
        "started_at": datetime.now(timezone.utc),
        "uptime": "0h 0m",
        "next_video": videos[1]["title"] if len(videos) > 1 else videos[0]["title"],
        "settings": {
            "auto_rotate": True,
            "loop_videos": True
        }
    }
    
    await db.live_streams.update_one(
        {"user_id": user["user_id"]},
        {"$set": stream_doc},
        upsert=True
    )
    
    return {"status": "live", "message": "Streaming started successfully"}

@api_router.post("/live-slot/stop")
async def stop_streaming(user: dict = Depends(get_current_user)):
    """Stop live streaming"""
    await db.live_streams.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"is_live": False}}
    )
    
    return {"status": "stopped", "message": "Streaming stopped successfully"}

@api_router.put("/live-slot/settings")
async def update_stream_settings(
    settings: LiveSlotSettings,
    user: dict = Depends(get_current_user)
):
    """Update stream settings"""
    await db.live_streams.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"settings": settings.dict()}}
    )
    
    return {"message": "Settings updated successfully"}

# ==================== PAYMENT ENDPOINTS ====================

@api_router.post("/payments/checkout-session")
async def create_checkout_session(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Create Stripe checkout session"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe checkout is disabled on this deployment. Please use Razorpay.")
    body = await request.json()
    plan_id = body.get("plan_id")
    origin_url = body.get("origin_url")
    
    if plan_id not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    plan = PLANS[plan_id]
    
    # Initialize Stripe
    webhook_url = f"{origin_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    
    # Create checkout session
    success_url = f"{origin_url}/dashboard/billings?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/dashboard/billings"
    
    checkout_request = CheckoutSessionRequest(
        amount=plan["price"],
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "user_id": user["user_id"],
            "plan_id": plan_id,
            "plan_name": plan["name"]
        }
    )
    
    session = await stripe_checkout.create_checkout_session(checkout_request)
    
    # Create payment transaction record
    transaction_doc = {
        "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "session_id": session.session_id,
        "plan_id": plan_id,
        "amount": plan["price"],
        "currency": "usd",
        "payment_status": "pending",
        "status": "initiated",
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.payment_transactions.insert_one(transaction_doc)
    
    return {
        "session_id": session.session_id,
        "checkout_url": session.url
    }

async def activate_plan_from_transaction(session_id: str, payment_status: str) -> bool:
    """Idempotently activate a user's plan for a paid session.
    Returns True if the plan was activated by this call, False otherwise.
    Uses an atomic conditional update so parallel webhook + polling requests
    never activate/credit the same session twice.
    """
    if payment_status != "paid":
        return False

    # Atomic guard: only transition initiated/pending -> completed once
    result = await db.payment_transactions.update_one(
        {"session_id": session_id, "status": {"$ne": "completed"}},
        {"$set": {
            "payment_status": "paid",
            "status": "completed",
            "completed_at": datetime.now(timezone.utc)
        }}
    )

    if result.modified_count == 0:
        # Already processed by another request
        return False

    # Load transaction to get user + plan
    transaction = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not transaction:
        return False

    plan_id = transaction["plan_id"]
    # Slot-stacking activation
    await activate_or_extend_plan(transaction["user_id"], plan_id)
    logger.info(f"Plan '{plan_id}' activated for user {transaction['user_id']} via session {session_id}")
    return True

@api_router.get("/payments/checkout-status/{session_id}")
async def get_checkout_status(
    session_id: str,
    user: dict = Depends(get_current_user)
):
    """Get payment status and update user plan (polling fallback)"""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe checkout is disabled on this deployment.")
    # Get transaction
    transaction = await db.payment_transactions.find_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # If already processed, return status
    if transaction["payment_status"] == "paid" and transaction["status"] == "completed":
        return transaction
    
    # Check with Stripe
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url="")
    status_response = await stripe_checkout.get_checkout_status(session_id)
    
    # Idempotently activate plan if paid
    activated = await activate_plan_from_transaction(session_id, status_response.payment_status)
    if activated or status_response.payment_status == "paid":
        transaction["payment_status"] = "paid"
        transaction["status"] = "completed"
    
    return transaction

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks with signature verification.
    Acts as a reliable backup to frontend polling for plan activation."""
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe webhook is disabled on this deployment.")
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")

    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url="")
    try:
        webhook_response = await stripe_checkout.handle_webhook(body, signature)
    except Exception as e:
        logger.error(f"Stripe webhook verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    # Activate plan idempotently on paid event
    if webhook_response.session_id:
        await activate_plan_from_transaction(
            webhook_response.session_id,
            webhook_response.payment_status
        )

    return {"received": True}

# ==================== RAZORPAY PAYMENT ENDPOINTS ====================

@api_router.post("/razorpay/create-order")
async def razorpay_create_order(request: Request, user: dict = Depends(get_current_user)):
    """Create a Razorpay order for the selected plan (amount in paise, INR)."""
    if not razorpay_client:
        raise HTTPException(status_code=503, detail="Razorpay is not configured.")

    body = await request.json()
    plan_id = body.get("plan_id")
    if plan_id not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")

    plan = PLANS[plan_id]
    amount_paise = int(plan["inr"]) * 100  # rupees -> paise

    try:
        order = razorpay_client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "payment_capture": 1,
            "receipt": f"rcpt_{uuid.uuid4().hex[:16]}",  # must be <= 40 chars
            "notes": {"user_id": user["user_id"], "plan_id": plan_id}
        })
    except Exception as e:
        logger.error(f"Razorpay order creation failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to create Razorpay order")

    # Record the pending transaction
    await db.payment_transactions.insert_one({
        "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "gateway": "razorpay",
        "order_id": order["id"],
        "plan_id": plan_id,
        "amount": plan["inr"],
        "currency": "INR",
        "payment_status": "pending",
        "status": "created",
        "created_at": datetime.now(timezone.utc)
    })

    return {
        "order_id": order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "key_id": RAZORPAY_KEY_ID,
        "plan_name": plan["name"],
        "prefill": {"name": user.get("name", ""), "email": user.get("email", "")}
    }

@api_router.post("/razorpay/verify-payment")
async def razorpay_verify_payment(request: Request, user: dict = Depends(get_current_user)):
    """Verify the Razorpay payment signature and activate the plan on success."""
    if not razorpay_client:
        raise HTTPException(status_code=503, detail="Razorpay is not configured.")

    body = await request.json()
    order_id = body.get("razorpay_order_id")
    payment_id = body.get("razorpay_payment_id")
    signature = body.get("razorpay_signature")

    if not (order_id and payment_id and signature):
        raise HTTPException(status_code=400, detail="Missing payment verification fields")

    # Verify signature: HMAC_SHA256(order_id|payment_id, key_secret)
    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        await db.payment_transactions.update_one(
            {"order_id": order_id, "user_id": user["user_id"]},
            {"$set": {"payment_status": "failed", "status": "signature_mismatch"}}
        )
        raise HTTPException(status_code=400, detail="Payment verification failed")

    # Look up the transaction to get the plan
    transaction = await db.payment_transactions.find_one(
        {"order_id": order_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Order not found")

    # Idempotent activation
    result = await db.payment_transactions.update_one(
        {"order_id": order_id, "status": {"$ne": "completed"}},
        {"$set": {
            "payment_status": "paid",
            "status": "completed",
            "payment_id": payment_id,
            "completed_at": datetime.now(timezone.utc)
        }}
    )

    if result.modified_count > 0:
        plan_id = transaction["plan_id"]
        # Slot-stacking activation — appends a new entry per different plan,
        # extends duration if the same plan is bought again.
        await activate_or_extend_plan(user["user_id"], plan_id)
        logger.info(f"Razorpay plan '{plan_id}' activated (slot-stacking) for user {user['user_id']}")

    return {"status": "success", "message": "Payment verified and plan activated"}

@api_router.post("/razorpay/webhook")
async def razorpay_webhook(request: Request):
    """Handle Razorpay webhooks (backup to client-side verification)."""
    payload = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not RAZORPAY_WEBHOOK_SECRET:
        # Webhook secret not configured; acknowledge without processing
        return {"status": "ignored"}

    try:
        razorpay_client.utility.verify_webhook_signature(
            payload.decode(), signature, RAZORPAY_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.error(f"Razorpay webhook verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    import json as _json
    event = _json.loads(payload.decode())
    if event.get("event") in ("payment.captured", "order.paid"):
        entity = event.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = entity.get("order_id")
        payment_id = entity.get("id")
        if order_id:
            txn = await db.payment_transactions.find_one({"order_id": order_id}, {"_id": 0})
            if txn:
                res = await db.payment_transactions.update_one(
                    {"order_id": order_id, "status": {"$ne": "completed"}},
                    {"$set": {"payment_status": "paid", "status": "completed",
                              "payment_id": payment_id, "completed_at": datetime.now(timezone.utc)}}
                )
                if res.modified_count > 0:
                    # Slot-stacking activation (same code path as verify_payment)
                    await activate_or_extend_plan(txn["user_id"], txn["plan_id"])
    return {"status": "processed"}

# ==================== BILLING ENDPOINTS ====================

@api_router.get("/billings/current-plan")
async def get_current_plan(user: dict = Depends(get_current_user)):
    """Get current plan details"""
    if not user.get("plan"):
        return {
            "plan_name": None,
            "price": 0,
            "next_billing_date": None,
            "status": "inactive"
        }
    
    plan = PLANS[user["plan"]]
    
    return {
        "plan_name": plan["name"],
        "price": plan["inr"],
        "next_billing_date": user.get("plan_expires_at").isoformat() if user.get("plan_expires_at") else None,
        "status": "active"
    }

@api_router.get("/billings/transactions")
async def get_transactions(user: dict = Depends(get_current_user)):
    """Get transaction history"""
    transactions = await db.payment_transactions.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return transactions

# ==================== SUPPORT ENDPOINTS ====================

@api_router.post("/support/ticket")
async def create_support_ticket(
    ticket: SupportTicket,
    user: dict = Depends(get_current_user)
):
    """Create support ticket"""
    ticket_doc = {
        "ticket_id": f"ticket_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "subject": ticket.subject,
        "message": ticket.message,
        "status": "open",
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.support_tickets.insert_one(ticket_doc)
    
    return {
        "ticket_id": ticket_doc["ticket_id"],
        "created_at": ticket_doc["created_at"].isoformat()
    }

# ==================== YOUTUBE LIVE STREAMING ENDPOINTS ====================

def _public_base_url(request: Request) -> str:
    """Base URL for building OAuth redirect + post-callback redirects.
    Prefers PUBLIC_APP_URL (set this in production, e.g. https://liveadda.org)
    to avoid http/https or proxy-header ambiguity; falls back to request.base_url."""
    configured = os.environ.get("PUBLIC_APP_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")

def _youtube_redirect_uri(request: Request) -> str:
    """Build the OAuth redirect URI from the public base URL."""
    return f"{_public_base_url(request)}/api/youtube/oauth/callback"

@api_router.get("/youtube/status")
async def youtube_status(user: dict = Depends(get_current_user)):
    """Return whether the user's YouTube channel is connected."""
    if not youtube_service.is_configured():
        return {"configured": False, "connected": False}

    account = await db.youtube_accounts.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not account:
        return {"configured": True, "connected": False}

    channel = {
        "channel_title": account.get("channel_title"),
        "channel_id": account.get("channel_id"),
        "thumbnail": account.get("thumbnail"),
    }
    return {"configured": True, "connected": True, "channel": channel}

@api_router.get("/youtube/oauth/authorize")
async def youtube_authorize(request: Request, user: dict = Depends(get_current_user)):
    """Return the Google OAuth consent URL to connect the user's YouTube channel."""
    if not youtube_service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="YouTube integration not configured. Add YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET."
        )
    redirect_uri = _youtube_redirect_uri(request)
    # Use user_id as state to correlate the callback
    auth_url = youtube_service.build_authorization_url(redirect_uri, state=user["user_id"])
    return {"authorization_url": auth_url}

@api_router.get("/youtube/oauth/callback")
async def youtube_oauth_callback(request: Request):
    """Handle the OAuth redirect from Google, store tokens, redirect back to the app."""
    from fastapi.responses import RedirectResponse

    params = dict(request.query_params)
    code = params.get("code")
    state = params.get("state")  # user_id
    base = _public_base_url(request)

    if not code or not state:
        return RedirectResponse(url=f"{base}/dashboard/live-slot?youtube=error")

    try:
        redirect_uri = _youtube_redirect_uri(request)
        tokens = youtube_service.exchange_code_for_tokens(redirect_uri, code)

        account_doc = {
            "user_id": state,
            **tokens,
            "connected_at": datetime.now(timezone.utc),
        }
        # Fetch channel info for display
        try:
            channel = youtube_service.get_channel_info(account_doc)
            account_doc.update(channel)
        except Exception as e:
            logger.error(f"Failed to fetch channel info: {e}")

        await db.youtube_accounts.update_one(
            {"user_id": state},
            {"$set": account_doc},
            upsert=True,
        )
        return RedirectResponse(url=f"{base}/dashboard/live-slot?youtube=connected")
    except Exception as e:
        logger.error(f"YouTube OAuth callback failed: {e}")
        return RedirectResponse(url=f"{base}/dashboard/live-slot?youtube=error")

@api_router.delete("/youtube/disconnect")
async def youtube_disconnect(user: dict = Depends(get_current_user)):
    """Disconnect the user's YouTube channel."""
    await db.youtube_accounts.delete_one({"user_id": user["user_id"]})
    return {"message": "YouTube channel disconnected"}

@api_router.post("/youtube/broadcast/create")
async def youtube_create_broadcast(request: Request, user: dict = Depends(get_current_user)):
    """Create a YouTube live broadcast+stream, bind them, start ffmpeg push for a video."""
    await check_active_plan(user)

    account = await db.youtube_accounts.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not account:
        raise HTTPException(status_code=400, detail="Connect your YouTube channel first.")

    body = await request.json()
    video_id = body.get("video_id")
    if not video_id:
        raise HTTPException(status_code=400, detail="video_id is required")

    video = await db.videos.find_one({"video_id": video_id, "user_id": user["user_id"]}, {"_id": 0})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        result = youtube_service.create_broadcast_and_stream(
            account,
            title=body.get("title", video["title"]),
            description=body.get("description", ""),
        )
        # Start ffmpeg push (roll back the broadcast if the encoder fails to start)
        try:
            pid = youtube_service.start_ffmpeg_push(video["file_path"], result["stream_key"], loop=True)
        except Exception as ff_err:
            logger.error(f"ffmpeg failed to start, completing broadcast {result['broadcast_id']}: {ff_err}")
            try:
                youtube_service.transition_broadcast(account, result["broadcast_id"], "complete")
            except Exception:
                pass
            raise HTTPException(status_code=500, detail="Failed to start the video encoder. Broadcast cancelled.")

        # Persist the live stream state
        await db.live_streams.update_one(
            {"user_id": user["user_id"]},
            {"$set": {
                "user_id": user["user_id"],
                "is_live": True,
                "current_video": video["title"],
                "broadcast_id": result["broadcast_id"],
                "stream_id": result["stream_id"],
                "watch_url": result["watch_url"],
                "ffmpeg_pid": pid,
                "started_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
        return {
            "message": "Broadcast created and streaming started",
            "watch_url": result["watch_url"],
            "broadcast_id": result["broadcast_id"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"YouTube broadcast creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"YouTube streaming failed: {str(e)}")

@api_router.post("/youtube/broadcast/stop")
async def youtube_stop_broadcast(user: dict = Depends(get_current_user)):
    """Stop the ffmpeg push and complete the broadcast."""
    stream = await db.live_streams.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not stream:
        raise HTTPException(status_code=404, detail="No active stream")

    # Stop ffmpeg
    if stream.get("ffmpeg_pid"):
        youtube_service.stop_ffmpeg_push(stream["ffmpeg_pid"])

    # Complete broadcast on YouTube
    account = await db.youtube_accounts.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if account and stream.get("broadcast_id"):
        try:
            youtube_service.transition_broadcast(account, stream["broadcast_id"], "complete")
        except Exception as e:
            logger.error(f"Failed to complete broadcast: {e}")

    await db.live_streams.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"is_live": False, "ffmpeg_pid": None}}
    )
    return {"message": "Broadcast stopped"}

# ==================== STREAM WITH KEY (Multi-slot support) ====================

@api_router.get("/streams")
async def list_active_streams(user: dict = Depends(get_current_user)):
    """Return all currently-live streams for the user + their slot budget."""
    streams = await db.live_streams.find(
        {"user_id": user["user_id"], "is_live": True},
        {"_id": 0, "ffmpeg_pid": 0}
    ).sort("started_at", -1).to_list(50)
    # Serialize datetime + ensure stream_id is always present (defensive for legacy docs)
    for s in streams:
        if s.get("started_at"):
            s["started_at"] = s["started_at"].isoformat() if hasattr(s["started_at"], "isoformat") else str(s["started_at"])
        if not s.get("stream_id"):
            s["stream_id"] = f"stream_legacy_{uuid.uuid4().hex[:12]}"
    max_slots = compute_stream_slots(user)
    return {
        "active": streams,
        "count": len(streams),
        "max_slots": max_slots,
        "slots_available": max(0, max_slots - len(streams)),
    }


@api_router.post("/stream/start-with-key")
async def start_stream_with_key(data: StreamKeyStart, user: dict = Depends(get_current_user)):
    """Go live by entering a YouTube stream key directly (no OAuth needed).
    Enforces the user's concurrent-stream slot budget (default 1, admin lifetime = 3)."""
    await check_active_plan(user)

    stream_key = data.stream_key.strip()
    if not stream_key:
        raise HTTPException(status_code=400, detail="Stream key is required")

    video = await db.videos.find_one(
        {"video_id": data.video_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Enforce concurrent-stream slot budget (slot-stacking aware)
    max_slots = compute_stream_slots(user)
    active_count = await db.live_streams.count_documents(
        {"user_id": user["user_id"], "is_live": True}
    )
    if active_count >= max_slots:
        raise HTTPException(
            status_code=403,
            detail=f"You already have {active_count} live stream(s), which is your maximum of {max_slots}. Stop an existing stream before starting another."
        )

    # Prevent the exact same stream_key from being used twice concurrently on this account
    dup = await db.live_streams.find_one(
        {"user_id": user["user_id"], "is_live": True, "stream_key": stream_key}
    )
    if dup:
        raise HTTPException(
            status_code=409,
            detail="This stream key is already live in another slot. Stop that stream first or use a different key."
        )

    try:
        pid = youtube_service.start_ffmpeg_push(video["file_path"], stream_key, loop=data.loop)
    except Exception as e:
        logger.error(f"Failed to start ffmpeg with key: {e}")
        raise HTTPException(status_code=500, detail="Failed to start the video encoder.")

    stream_id = f"stream_{uuid.uuid4().hex[:12]}"
    stream_doc = {
        "stream_id": stream_id,
        "user_id": user["user_id"],
        "is_live": True,
        "current_video": video["title"],
        "video_id": video["video_id"],
        "stream_method": "manual_key",
        "stream_key": stream_key,  # stored so we can dedupe & audit
        "ffmpeg_pid": pid,
        "started_at": datetime.now(timezone.utc),
    }
    await db.live_streams.insert_one(stream_doc)

    return {
        "message": "You are now live on YouTube!",
        "stream_id": stream_id,
        "current_video": video["title"],
        "slot": {"used": active_count + 1, "max": max_slots},
        "watch_hint": "Open YouTube Studio to view your live stream."
    }


@api_router.post("/stream/stop")
async def stop_stream_with_key(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Stop a manual-key stream. If body contains {stream_id: "..."}, stop that
    specific stream. Otherwise stop the MOST RECENT live stream (back-compat for
    single-slot users). Idempotent."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    target_stream_id = (body or {}).get("stream_id")

    query = {"user_id": user["user_id"], "is_live": True}
    if target_stream_id:
        query["stream_id"] = target_stream_id
    stream = await db.live_streams.find_one(query, sort=[("started_at", -1)])
    if not stream:
        return {"message": "Already stopped"}

    if stream.get("ffmpeg_pid"):
        try:
            youtube_service.stop_ffmpeg_push(stream["ffmpeg_pid"])
        except Exception as e:
            logger.warning(f"stop_ffmpeg_push failed: {e}")

    await db.live_streams.update_one(
        {"_id": stream["_id"]},
        {"$set": {"is_live": False, "ffmpeg_pid": None, "stopped_at": datetime.now(timezone.utc), "stopped_reason": "user_stopped"}}
    )
    # Auto-delete the video that was being streamed (skips if another live
    # slot for the same user still references the same video_id).
    stopped_video_id = stream.get("video_id")
    if stopped_video_id:
        await cleanup_stream_video_if_orphaned(user["user_id"], stopped_video_id)
    return {"message": "Stream stopped", "stream_id": stream.get("stream_id"), "video_deleted": bool(stopped_video_id)}

# ==================== DASHBOARD STATS ====================

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    """Get dashboard statistics"""
    # Count videos
    video_count = await db.videos.count_documents({"user_id": user["user_id"]})

    # Count active live streams across all slots
    active_slots = await db.live_streams.count_documents(
        {"user_id": user["user_id"], "is_live": True}
    )

    # Get recent activity
    recent_videos = await db.videos.find(
        {"user_id": user["user_id"]}
    ).sort("uploaded_at", -1).limit(5).to_list(5)
    
    activity = []
    for video in recent_videos:
        activity.append({
            "action": "Video uploaded",
            "description": video["title"],
            "timestamp": video["uploaded_at"].isoformat()
        })
    
    return {
        "active_live_slots": active_slots,
        "max_stream_slots": compute_stream_slots(user),
        "total_videos": video_count,
        "storage_used": user.get("storage_used", 0),
        "plan": user.get("plan"),
        "plan_expires_at": user.get("plan_expires_at").isoformat() if user.get("plan_expires_at") else None,
        "recent_activity": activity
    }


@api_router.get("/health")
async def health_check():
    """Public health/version endpoint — no auth. Returns build SHA + timestamp
    so operators can verify a `git pull` + `deploy/update.sh` actually landed."""
    global _BUILD_SHA_CACHE
    if _BUILD_SHA_CACHE is None:
        sha = os.environ.get("BUILD_SHA") or ""
        if not sha:
            try:
                import subprocess
                sha = subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=str(ROOT_DIR.parent), stderr=subprocess.DEVNULL, timeout=2
                ).decode().strip()
            except Exception:
                sha = "unknown"
        _BUILD_SHA_CACHE = sha or "unknown"
    # DB ping
    db_ok = True
    try:
        await db.command("ping")
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "build_sha": _BUILD_SHA_CACHE,
        "build_time": os.environ.get("BUILD_TIME", ""),
        "server_time": datetime.now(timezone.utc).isoformat(),
        "db": "ok" if db_ok else "down",
        "features": {
            "chunked_upload": True,
            "resumable_upload": True,
            "video_thumbnails": True,
            "ffprobe_metadata": True,
            "multi_slot_streaming": True,
            "razorpay": True,
        }
    }

# ==================== STARTUP EVENTS ====================

@app.on_event("startup")
async def startup_event():
    """Seed admin user and create indexes"""
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.videos.create_index("user_id")
    # Speeds up multi-slot count/list queries.
    await db.live_streams.create_index("user_id")

    # One-time migration: backfill stream_id on any legacy live_streams docs
    # (docs created before iter-9 didn't have this field, which crashed the
    # LiveSlot UI with "Cannot read properties of undefined (reading 'slice')").
    cursor = db.live_streams.find({"stream_id": {"$exists": False}})
    async for legacy in cursor:
        new_sid = f"stream_legacy_{uuid.uuid4().hex[:12]}"
        await db.live_streams.update_one(
            {"_id": legacy["_id"]},
            {"$set": {"stream_id": new_sid}}
        )
        logger.info(f"Backfilled stream_id={new_sid} on legacy stream for user {legacy.get('user_id')}")

    # One-time migration: users who had a single legacy `plan`+`plan_expires_at`
    # but no `active_plans` array. Populate the array from the legacy fields so
    # slot-stacking works transparently for pre-iter-10 users.
    users_cursor = db.users.find({
        "active_plans": {"$exists": False},
        "plan": {"$exists": True, "$nin": [None, "", "lifetime"]},
        "plan_expires_at": {"$exists": True, "$ne": None},
    })
    async for u in users_cursor:
        legacy_exp = _as_utc(u.get("plan_expires_at"))
        if not legacy_exp:
            continue
        now = datetime.now(timezone.utc)
        # Only migrate non-expired plans
        if legacy_exp > now:
            entry = {
                "plan_id": u["plan"],
                "purchased_at": _as_utc(u.get("plan_started_at")) or now,
                "expires_at": legacy_exp,
            }
            await db.users.update_one(
                {"_id": u["_id"]},
                {"$set": {"active_plans": [entry], "stream_slots": 1}}
            )
            logger.info(f"Migrated user {u.get('user_id')} to active_plans (plan={u['plan']})")
        else:
            await db.users.update_one(
                {"_id": u["_id"]},
                {"$set": {"active_plans": [], "plan": None, "plan_expires_at": None, "stream_slots": 0}}
            )
    # Idempotency key for chunked uploads. Partial filter ensures only new
    # rows (with a string upload_id) are indexed — legacy rows without
    # upload_id are excluded. Prevents duplicate video docs on retried
    # final-chunk uploads.
    await db.videos.create_index(
        [("user_id", 1), ("upload_id", 1)],
        unique=True,
        partialFilterExpression={"upload_id": {"$type": "string"}},
        name="uniq_user_upload_id"
    )
    await db.payment_transactions.create_index("session_id")
    
    # Seed / re-seed admin user (idempotent — updates existing admin to lifetime + 3 slots)
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@liveadda.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")

    existing_admin = await db.users.find_one({"email": admin_email})
    if not existing_admin:
        admin_id = f"user_{uuid.uuid4().hex[:12]}"
        admin_doc = {
            "user_id": admin_id,
            "email": admin_email,
            "name": "Admin",
            "password_hash": hash_password(admin_password),
            "role": "admin",
            "plan": "lifetime",
            # Set to a far-future date; check_active_plan short-circuits on "lifetime" anyway
            "plan_expires_at": datetime.now(timezone.utc) + timedelta(days=36500),
            "stream_slots": 3,
            "storage_used": 0,
            "created_at": datetime.now(timezone.utc)
        }
        await db.users.insert_one(admin_doc)
        logger.info(f"Admin user created: {admin_email}")
    else:
        # Upgrade any existing admin to lifetime + 3 slots (idempotent).
        # DO NOT reset password_hash — the user may have changed it via Profile.
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {
                "role": "admin",
                "plan": "lifetime",
                "plan_expires_at": datetime.now(timezone.utc) + timedelta(days=36500),
                "stream_slots": 3,
            }}
        )
        logger.info(f"Admin user upgraded to lifetime + 3 slots: {admin_email}")
    
    # Write test credentials — only if file doesn't already exist, to preserve
    # any richer manual notes/setup the operator has documented.
    test_creds_path = Path("/app/memory/test_credentials.md")
    test_creds_path.parent.mkdir(parents=True, exist_ok=True)
    if not test_creds_path.exists():
        with open(test_creds_path, "w") as f:
            f.write("# Live Adda Test Credentials\n\n")
            f.write("## Admin Account\n")
            f.write(f"- Email: {admin_email}\n")
            f.write(f"- Password: {admin_password}\n")
            f.write(f"- Role: admin\n\n")
            f.write("## API Endpoints\n")
            f.write("- POST /api/auth/register\n")
            f.write("- POST /api/auth/login\n")
            f.write("- GET /api/auth/me\n")
            f.write("- POST /api/videos/upload\n")
            f.write("- GET /api/videos\n")
            f.write("- POST /api/payments/checkout-session\n")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
