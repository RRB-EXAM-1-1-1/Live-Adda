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
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
import youtube_service

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

# Create uploads directory
UPLOAD_DIR = ROOT_DIR / 'uploads' / 'videos'
THUMBNAIL_DIR = ROOT_DIR / 'uploads' / 'thumbnails'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

# Plan configurations
PLANS = {
    "daily": {"price": 4.99, "duration_days": 1, "name": "Daily"},
    "weekly": {"price": 24.99, "duration_days": 7, "name": "Weekly"},
    "monthly": {"price": 79.99, "duration_days": 30, "name": "Monthly"}
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
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
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

async def check_active_plan(user: dict):
    """Check if user has an active plan"""
    if not user.get("plan") or not user.get("plan_expires_at"):
        raise HTTPException(
            status_code=403,
            detail="⚠️ Please purchase a slot/plan first to proceed."
        )
    
    # Check if plan is expired
    expires_at = user["plan_expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        # Plan expired, clear it
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"plan": None, "plan_expires_at": None}}
        )
        raise HTTPException(
            status_code=403,
            detail="⚠️ Your plan has expired. Please purchase a new plan to proceed."
        )

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
        max_age=900,
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
        max_age=900,
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

@api_router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current user info"""
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "plan": user.get("plan"),
        "plan_expires_at": user.get("plan_expires_at").isoformat() if user.get("plan_expires_at") else None,
        "storage_used": user.get("storage_used", 0)
    }

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

    # Stream file to disk in 1MB chunks, enforcing the storage limit incrementally
    CHUNK_SIZE = 1024 * 1024  # 1 MB
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

@api_router.get("/videos")
async def get_videos(user: dict = Depends(get_current_user)):
    """Get all videos for current user"""
    videos = await db.videos.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(1000)
    return videos

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
    plan = PLANS[plan_id]
    expires_at = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])

    await db.users.update_one(
        {"user_id": transaction["user_id"]},
        {"$set": {"plan": plan_id, "plan_expires_at": expires_at}}
    )
    logger.info(f"Plan '{plan_id}' activated for user {transaction['user_id']} via session {session_id}")
    return True

@api_router.get("/payments/checkout-status/{session_id}")
async def get_checkout_status(
    session_id: str,
    user: dict = Depends(get_current_user)
):
    """Get payment status and update user plan (polling fallback)"""
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
        "price": plan["price"],
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

def _youtube_redirect_uri(request: Request) -> str:
    """Build the OAuth redirect URI from the incoming request's base URL."""
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/youtube/oauth/callback"

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
    base = str(request.base_url).rstrip("/")

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

# ==================== DASHBOARD STATS ====================

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    """Get dashboard statistics"""
    # Count videos
    video_count = await db.videos.count_documents({"user_id": user["user_id"]})
    
    # Get live stream status
    live_stream = await db.live_streams.find_one({"user_id": user["user_id"]})
    
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
        "active_live_slots": 1 if live_stream and live_stream.get("is_live") else 0,
        "total_videos": video_count,
        "storage_used": user.get("storage_used", 0),
        "plan": user.get("plan"),
        "plan_expires_at": user.get("plan_expires_at").isoformat() if user.get("plan_expires_at") else None,
        "recent_activity": activity
    }

# ==================== STARTUP EVENTS ====================

@app.on_event("startup")
async def startup_event():
    """Seed admin user and create indexes"""
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.videos.create_index("user_id")
    await db.payment_transactions.create_index("session_id")
    
    # Seed admin user
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
            "plan": "monthly",
            "plan_expires_at": datetime.now(timezone.utc) + timedelta(days=365),
            "storage_used": 0,
            "created_at": datetime.now(timezone.utc)
        }
        await db.users.insert_one(admin_doc)
        logger.info(f"Admin user created: {admin_email}")
    
    # Write test credentials
    test_creds_path = Path("/app/memory/test_credentials.md")
    test_creds_path.parent.mkdir(parents=True, exist_ok=True)
    
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
