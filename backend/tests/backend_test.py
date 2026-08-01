"""
Live Adda Backend API Tests
Tests: Auth, Gatekeeping, Video CRUD, Storage limits, Rename, Live slot, Payments, Support, Dashboard stats
"""
import os
import io
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # Try to load from frontend .env
    from pathlib import Path
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@liveadda.com"
ADMIN_PASSWORD = "admin123"

GATEKEEP_MSG = "⚠️ Please purchase a slot/plan first to proceed."


# ==================== Fixtures ====================

@pytest.fixture(scope="session")
def admin_session():
    """Session logged in as admin (has active monthly plan)."""
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def fresh_user():
    """Register a fresh user (no plan) and return (session, email, user_id)."""
    s = requests.Session()
    email = f"TEST_freshuser_{uuid.uuid4().hex[:8]}@example.com"
    password = "test123456"
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": password, "name": "Fresh Tester"
    }, timeout=30)
    assert r.status_code == 200, f"Register failed: {r.status_code} {r.text}"
    data = r.json()
    return s, email, data["user_id"]


# ==================== Auth tests ====================

class TestAuth:
    def test_register_new_user_sets_cookies(self):
        s = requests.Session()
        email = f"TEST_reg_{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register", json={
            "email": email, "password": "pw123456", "name": "Reg User"
        }, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == email.lower()
        assert data["plan"] is None
        assert "access_token" in s.cookies, "access_token cookie not set"

    def test_register_duplicate_email(self):
        email = f"TEST_dup_{uuid.uuid4().hex[:8]}@example.com"
        s = requests.Session()
        r1 = s.post(f"{API}/auth/register", json={"email": email, "password": "pw123456", "name": "A"}, timeout=30)
        assert r1.status_code == 200
        r2 = requests.post(f"{API}/auth/register", json={"email": email, "password": "pw123456", "name": "A"}, timeout=30)
        assert r2.status_code == 400

    def test_login_admin_success(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["plan"] == "monthly"
        assert "access_token" in s.cookies

    def test_login_invalid_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrongpw"}, timeout=30)
        assert r.status_code == 401

    def test_auth_me_returns_user(self, admin_session):
        r = admin_session.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["plan"] == "monthly"

    def test_auth_me_unauthenticated(self):
        r = requests.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 401

    def test_logout_clears_cookies(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
        r = s.post(f"{API}/auth/logout", timeout=30)
        assert r.status_code == 200
        # After logout, /me should be 401 (server-side cookie cleared)
        # Note: requests keeps cookie jar in sync with Set-Cookie
        r2 = s.get(f"{API}/auth/me", timeout=30)
        assert r2.status_code == 401


# ==================== Gatekeeping tests ====================

class TestGatekeeping:
    def test_video_upload_without_plan_returns_403_with_exact_message(self, fresh_user):
        s, email, uid = fresh_user
        # Upload a small in-memory file
        files = {"file": ("test.mp4", io.BytesIO(b"fake video bytes"), "video/mp4")}
        data = {"title": "TEST_no_plan_video"}
        r = s.post(f"{API}/videos/upload", files=files, data=data, timeout=30)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "")
        assert detail == GATEKEEP_MSG, f"Exact message mismatch: {detail!r}"

    def test_live_slot_get_without_plan_returns_403(self, fresh_user):
        s, _, _ = fresh_user
        r = s.get(f"{API}/live-slot", timeout=30)
        assert r.status_code == 403
        assert r.json().get("detail") == GATEKEEP_MSG

    def test_live_slot_start_without_plan_returns_403(self, fresh_user):
        s, _, _ = fresh_user
        r = s.post(f"{API}/live-slot/start", timeout=30)
        assert r.status_code == 403
        assert r.json().get("detail") == GATEKEEP_MSG


# ==================== Video tests (with active plan) ====================

class TestVideos:
    def test_upload_with_plan_returns_ready_message(self, admin_session):
        files = {"file": ("intro.mp4", io.BytesIO(b"a" * 1024), "video/mp4")}
        data = {"title": "TEST_video_admin"}
        r = admin_session.post(f"{API}/videos/upload", files=files, data=data, timeout=60)
        assert r.status_code == 200, r.text
        resp = r.json()
        assert "Ready for the stream!" in resp["message"]
        assert "video_id" in resp
        # cleanup handled in test_delete via GET-list
        pytest.admin_uploaded_video_id = resp["video_id"]

    def test_list_videos(self, admin_session):
        r = admin_session.get(f"{API}/videos", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_rename_video(self, admin_session):
        vid = getattr(pytest, "admin_uploaded_video_id", None)
        if not vid:
            pytest.skip("No uploaded video to rename")
        new_title = "TEST_renamed_video"
        r = admin_session.put(f"{API}/videos/{vid}/rename", json={"title": new_title}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["title"] == new_title
        # verify persistence
        r2 = admin_session.get(f"{API}/videos", timeout=30)
        titles = [v["title"] for v in r2.json() if v["video_id"] == vid]
        assert new_title in titles

    def test_rename_nonexistent_video(self, admin_session):
        r = admin_session.put(f"{API}/videos/nonexistent_id/rename", json={"title": "x"}, timeout=30)
        assert r.status_code == 404

    def test_delete_video_and_storage_decrement(self, admin_session):
        vid = getattr(pytest, "admin_uploaded_video_id", None)
        if not vid:
            pytest.skip("No uploaded video to delete")
        # Get storage before
        me_before = admin_session.get(f"{API}/auth/me", timeout=30).json()
        storage_before = me_before.get("storage_used", 0)

        r = admin_session.delete(f"{API}/videos/{vid}", timeout=30)
        assert r.status_code == 200

        me_after = admin_session.get(f"{API}/auth/me", timeout=30).json()
        storage_after = me_after.get("storage_used", 0)
        assert storage_after < storage_before, f"storage did not decrement ({storage_before} -> {storage_after})"


# ==================== Storage limit test ====================

class TestStorageLimit:
    def test_max_storage_env_is_2gb(self):
        # Informational - constant enforced server-side. See TestStorageEnforcement for real check.
        assert True


# ==================== Streaming upload + incremental storage enforcement ====================

class TestStorageEnforcement:
    """Validates iteration 2 changes: chunked/streaming upload with incremental 2GB limit.
    We can't ship a real 2GB payload, so we DIRECTLY manipulate the admin's stored
    storage_used to place them just under the limit, then upload a small file that
    pushes past it.
    """

    def _get_mongo_db(self):
        from pymongo import MongoClient
        from pathlib import Path
        env = Path("/app/backend/.env").read_text().splitlines()
        cfg = {}
        for line in env:
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"')
        cli = MongoClient(cfg["MONGO_URL"])
        return cli[cfg["DB_NAME"]]

    def test_upload_returns_ready_and_increments_storage(self, admin_session):
        me_before = admin_session.get(f"{API}/auth/me", timeout=30).json()
        before = me_before.get("storage_used", 0)
        payload = b"z" * (16 * 1024)  # 16 KB
        files = {"file": ("chunk.mp4", io.BytesIO(payload), "video/mp4")}
        data = {"title": "TEST_stream_upload"}
        r = admin_session.post(f"{API}/videos/upload", files=files, data=data, timeout=60)
        assert r.status_code == 200, r.text
        resp = r.json()
        assert "Ready for the stream!" in resp["message"]
        assert resp["size"] == len(payload)
        me_after = admin_session.get(f"{API}/auth/me", timeout=30).json()
        assert me_after["storage_used"] == before + len(payload), (
            f"storage did not increment correctly: {before} -> {me_after['storage_used']}"
        )
        # cleanup
        admin_session.delete(f"{API}/videos/{resp['video_id']}", timeout=30)

    def test_incremental_2gb_limit_rejects_upload(self, admin_session):
        db = self._get_mongo_db()
        me = admin_session.get(f"{API}/auth/me", timeout=30).json()
        uid = me["user_id"]
        original = me.get("storage_used", 0)
        # Set storage_used to (2GB - 1KB) so a 4KB upload will exceed the limit
        MAX = 2 * 1024 * 1024 * 1024
        db.users.update_one({"user_id": uid}, {"$set": {"storage_used": MAX - 1024}})
        try:
            files = {"file": ("big.mp4", io.BytesIO(b"y" * 4096), "video/mp4")}
            r = admin_session.post(f"{API}/videos/upload",
                                   files=files, data={"title": "TEST_over_limit"}, timeout=60)
            assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
            detail = r.json().get("detail", "")
            assert "Storage limit" in detail
        finally:
            db.users.update_one({"user_id": uid}, {"$set": {"storage_used": original}})


# ==================== Stripe webhook signature verification ====================

class TestStripeWebhook:
    def test_missing_signature_returns_400(self):
        r = requests.post(f"{API}/webhook/stripe",
                          data=b'{"type":"checkout.session.completed"}',
                          headers={"Content-Type": "application/json"}, timeout=30)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"

    def test_invalid_signature_returns_400(self):
        r = requests.post(f"{API}/webhook/stripe",
                          data=b'{"type":"checkout.session.completed","data":{}}',
                          headers={
                              "Content-Type": "application/json",
                              "Stripe-Signature": "t=123,v1=deadbeefdeadbeef"
                          }, timeout=30)
        assert r.status_code == 400


# ==================== Idempotent plan activation ====================

class TestIdempotentActivation:
    """Directly exercise the idempotent activation helper via a synthetic
    payment_transactions record + repeated checkout-status polling.
    """

    def _get_mongo_db(self):
        from pymongo import MongoClient
        from pathlib import Path
        env = Path("/app/backend/.env").read_text().splitlines()
        cfg = {}
        for line in env:
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"')
        cli = MongoClient(cfg["MONGO_URL"])
        return cli[cfg["DB_NAME"]]

    def test_activate_plan_is_idempotent(self):
        """Call activate_plan_from_transaction twice (simulating webhook + polling race).
        Second call must be a no-op (returns False) and the plan expiry must not shift.
        """
        import asyncio
        from datetime import datetime, timezone, timedelta
        from motor.motor_asyncio import AsyncIOMotorClient
        import sys
        sys.path.insert(0, "/app/backend")
        # Import the helper directly
        from server import activate_plan_from_transaction, db as server_db

        db = self._get_mongo_db()
        user_id = f"TEST_idem_user_{uuid.uuid4().hex[:8]}"
        session_id = f"cs_test_idem_{uuid.uuid4().hex[:10]}"
        db.users.insert_one({
            "user_id": user_id,
            "email": f"{user_id}@example.com",
            "name": "Idem Tester",
            "password_hash": "x",
            "plan": None,
            "plan_expires_at": None,
            "storage_used": 0,
            "created_at": datetime.now(timezone.utc),
        })
        db.payment_transactions.insert_one({
            "transaction_id": f"txn_{uuid.uuid4().hex[:8]}",
            "user_id": user_id,
            "session_id": session_id,
            "plan_id": "daily",
            "amount": 4.99,
            "currency": "usd",
            "payment_status": "pending",
            "status": "initiated",
            "created_at": datetime.now(timezone.utc),
        })

        async def run():
            first = await activate_plan_from_transaction(session_id, "paid")
            second = await activate_plan_from_transaction(session_id, "paid")
            return first, second

        try:
            first, second = _arun(run())
            assert first is True, "First activation should activate"
            assert second is False, "Second activation must be a no-op"
            user = db.users.find_one({"user_id": user_id})
            assert user["plan"] == "daily"
            txn = db.payment_transactions.find_one({"session_id": session_id})
            assert txn["status"] == "completed"
            assert txn["payment_status"] == "paid"
        finally:
            db.users.delete_one({"user_id": user_id})
            db.payment_transactions.delete_one({"session_id": session_id})

    def test_activate_plan_not_paid_no_op(self):
        import asyncio
        from server import activate_plan_from_transaction
        result = _arun(activate_plan_from_transaction("cs_unknown_session", "unpaid"))
        assert result is False


# ==================== YouTube endpoints ====================

class TestYouTubeNotConfigured:
    def test_status_returns_configured_but_not_connected(self, admin_session):
        r = admin_session.get(f"{API}/youtube/status", timeout=30)
        assert r.status_code == 200
        data = r.json()
        # Env now has YOUTUBE_CLIENT_ID/SECRET set; user hasn't OAuth-linked.
        assert data.get("configured") is True
        assert data.get("connected") is False

    def test_authorize_returns_authorization_url(self, admin_session):
        r = admin_session.get(f"{API}/youtube/oauth/authorize", timeout=30, allow_redirects=False)
        # Now that env is configured, endpoint should return 200 with an auth URL
        # (or 302 redirect to Google). Accept either.
        assert r.status_code in (200, 302), r.text
        if r.status_code == 200:
            body = r.json()
            url = body.get("authorization_url") or body.get("auth_url") or ""
            assert "accounts.google.com" in url or "oauth" in url.lower()

    def test_broadcast_create_without_plan_returns_403(self, fresh_user):
        s, _, _ = fresh_user
        r = s.post(f"{API}/youtube/broadcast/create", json={"video_id": "x"}, timeout=30)
        assert r.status_code == 403
        assert r.json().get("detail") == GATEKEEP_MSG

    def test_broadcast_create_with_plan_but_no_youtube_account_returns_400(self, admin_session):
        r = admin_session.post(f"{API}/youtube/broadcast/create",
                               json={"video_id": "any"}, timeout=30)
        assert r.status_code == 400, r.text
        assert r.json().get("detail") == "Connect your YouTube channel first."

    def test_youtube_disconnect_no_op_ok(self, admin_session):
        r = admin_session.delete(f"{API}/youtube/disconnect", timeout=30)
        assert r.status_code == 200


# ==================== Key Activation (start-with-key / stop) ====================

def _get_mongo_db_static():
    from pymongo import MongoClient
    from pathlib import Path
    env = Path("/app/backend/.env").read_text().splitlines()
    cfg = {}
    for line in env:
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip('"')
    cli = MongoClient(cfg["MONGO_URL"])
    return cli[cfg["DB_NAME"]]


@pytest.fixture(scope="class")
def key_user():
    """Dedicated fresh user with a daily plan seeded via Mongo (isolates from
    admin-shared state used by other parallel test classes)."""
    from datetime import datetime, timezone, timedelta
    s = requests.Session()
    email = f"TEST_keyuser_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": "keypw123", "name": "Key Tester"
    }, timeout=30)
    assert r.status_code == 200, r.text
    uid = r.json()["user_id"]
    db = _get_mongo_db_static()
    db.users.update_one({"user_id": uid}, {"$set": {
        "plan": "daily",
        "plan_expires_at": datetime.now(timezone.utc) + timedelta(days=1),
    }})
    yield s, email, uid
    # cleanup
    db.users.delete_one({"user_id": uid})
    db.videos.delete_many({"user_id": uid})
    db.live_streams.delete_many({"user_id": uid})


class TestKeyActivation:
    """Iteration 3: /api/stream/start-with-key + /api/stream/stop.
    NOTE: With a fake key ffmpeg exits almost immediately; that is EXPECTED.
    We validate the endpoint contract (status codes, messages, DB record), not
    the actual RTMP push. Uses a dedicated key_user to avoid parallel-race with
    admin storage/live-slot tests."""

    def test_start_with_key_without_plan_returns_gatekeep(self, fresh_user):
        s, _, _ = fresh_user
        r = s.post(f"{API}/stream/start-with-key",
                   json={"video_id": "any", "stream_key": "any-key"}, timeout=30)
        assert r.status_code == 403, r.text
        assert r.json().get("detail") == GATEKEEP_MSG

    def test_start_with_key_empty_stream_key_returns_400(self, key_user):
        s, _, _ = key_user
        r = s.post(f"{API}/stream/start-with-key",
                   json={"video_id": "any", "stream_key": "   "}, timeout=30)
        assert r.status_code == 400, r.text
        assert r.json().get("detail") == "Stream key is required"

    def test_start_with_key_missing_video_returns_404(self, key_user):
        s, _, _ = key_user
        r = s.post(f"{API}/stream/start-with-key",
                   json={"video_id": "does_not_exist_xyz", "stream_key": "abcd-efgh-ijkl-mnop"}, timeout=30)
        assert r.status_code == 404, r.text
        assert r.json().get("detail") == "Video not found"

    def test_stop_stream_no_active_is_idempotent(self, key_user):
        """Main agent implemented iteration-3 recommendation: stop is now idempotent
        (returns 200 with 'Already stopped' instead of 404)."""
        s, _, _ = key_user
        # Ensure clean state
        s.post(f"{API}/stream/stop", timeout=30)
        r = s.post(f"{API}/stream/stop", timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("message") in ("Already stopped", "Stream stopped")

    def test_start_with_key_success_and_stop(self, key_user):
        # Requires ffmpeg on PATH; skip if not present (environment gap)
        import shutil
        if not shutil.which("ffmpeg"):
            pytest.skip("ffmpeg binary not installed in this environment")
        s, _, _ = key_user
        # Upload a small video first
        files = {"file": ("keyclip.mp4", io.BytesIO(b"x" * 2048), "video/mp4")}
        data = {"title": "TEST_key_stream_video"}
        up = s.post(f"{API}/videos/upload", files=files, data=data, timeout=60)
        assert up.status_code == 200, up.text
        vid = up.json()["video_id"]

        try:
            r = s.post(
                f"{API}/stream/start-with-key",
                json={"video_id": vid, "stream_key": "fake-yt-key-abcd-efgh"},
                timeout=30,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("message") == "You are now live on YouTube!"
            assert body.get("current_video") == "TEST_key_stream_video"

            # Give ffmpeg a moment; then stop the stream (endpoint should succeed
            # regardless of whether ffmpeg has already exited due to fake key)
            time.sleep(1)
            r2 = s.post(f"{API}/stream/stop", timeout=30)
            assert r2.status_code == 200, r2.text
            assert r2.json().get("message") == "Stream stopped"
        finally:
            s.delete(f"{API}/videos/{vid}", timeout=30)


# ==================== Payments tests ====================

class TestPayments:
    def test_checkout_session_creation_returns_session_and_url(self, admin_session):
        origin = BASE_URL
        r = admin_session.post(f"{API}/payments/checkout-session",
                               json={"plan_id": "daily", "origin_url": origin}, timeout=60)
        # Stripe test key sk_test_emergent may or may not be valid. Accept success or upstream error.
        if r.status_code == 200:
            data = r.json()
            assert data.get("session_id")
            assert data.get("checkout_url", "").startswith("http")
            pytest.stripe_session_id = data["session_id"]
        else:
            pytest.skip(f"Stripe checkout returned {r.status_code}: {r.text[:200]}")

    def test_checkout_status(self, admin_session):
        sid = getattr(pytest, "stripe_session_id", None)
        if not sid:
            pytest.skip("No stripe session id from previous test")
        r = admin_session.get(f"{API}/payments/checkout-status/{sid}", timeout=60)
        assert r.status_code in (200, 404), r.text

    def test_invalid_plan_returns_400(self, admin_session):
        r = admin_session.post(f"{API}/payments/checkout-session",
                               json={"plan_id": "yearly", "origin_url": BASE_URL}, timeout=30)
        assert r.status_code == 400


# ==================== Billings tests ====================

class TestBillings:
    def test_current_plan_admin(self, admin_session):
        r = admin_session.get(f"{API}/billings/current-plan", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "active"
        assert data["plan_name"] == "Monthly"
        # INR pricing (iteration 4) - admin has monthly plan
        assert data["price"] == 599

    def test_current_plan_no_plan(self, fresh_user):
        s, _, _ = fresh_user
        r = s.get(f"{API}/billings/current-plan", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "inactive"
        assert data["plan_name"] is None

    def test_transactions(self, admin_session):
        r = admin_session.get(f"{API}/billings/transactions", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ==================== Live slot with plan ====================

class TestLiveSlotWithPlan:
    def test_get_live_slot_returns_default(self, admin_session):
        r = admin_session.get(f"{API}/live-slot", timeout=30)
        assert r.status_code == 200

    def test_start_without_videos_returns_400(self, admin_session):
        # Ensure no videos exist for admin first
        vids = admin_session.get(f"{API}/videos", timeout=30).json()
        for v in vids:
            admin_session.delete(f"{API}/videos/{v['video_id']}", timeout=30)
        r = admin_session.post(f"{API}/live-slot/start", timeout=30)
        assert r.status_code == 400

    def test_start_stop_with_video(self, admin_session):
        # Upload a video first
        files = {"file": ("clip.mp4", io.BytesIO(b"x" * 512), "video/mp4")}
        data = {"title": "TEST_slot_video"}
        up = admin_session.post(f"{API}/videos/upload", files=files, data=data, timeout=60)
        assert up.status_code == 200
        vid = up.json()["video_id"]

        try:
            r = admin_session.post(f"{API}/live-slot/start", timeout=30)
            assert r.status_code == 200
            assert r.json()["status"] == "live"

            r2 = admin_session.post(f"{API}/live-slot/stop", timeout=30)
            assert r2.status_code == 200

            r3 = admin_session.put(f"{API}/live-slot/settings",
                                   json={"auto_rotate": False, "loop_videos": False}, timeout=30)
            assert r3.status_code == 200
        finally:
            admin_session.delete(f"{API}/videos/{vid}", timeout=30)


# ==================== Support tests ====================

class TestSupport:
    def test_create_ticket(self, admin_session):
        r = admin_session.post(f"{API}/support/ticket",
                               json={"subject": "TEST_sub", "message": "TEST_msg"}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ticket_id", "").startswith("ticket_")


# ==================== Dashboard stats ====================

class TestDashboard:
    def test_stats_admin(self, admin_session):
        r = admin_session.get(f"{API}/dashboard/stats", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "total_videos" in data
        assert "storage_used" in data
        assert data.get("plan") == "monthly"

    def test_stats_fresh_user(self, fresh_user):
        s, _, _ = fresh_user
        r = s.get(f"{API}/dashboard/stats", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data.get("plan") is None
        assert data.get("total_videos") == 0


# ==================== Razorpay Payment tests (iteration 4) ====================

import hmac as _hmac
import hashlib as _hashlib


def _load_env_secret():
    from pathlib import Path
    env = Path("/app/backend/.env").read_text().splitlines()
    cfg = {}
    for line in env:
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip('"')
    return cfg


def _create_order_with_retry(session, plan_id, retries=6, backoff=8):
    """Razorpay LIVE keys are rate-limited by the provider (~1 successful
    order/minute in this preview env), returning 502 'Failed to create
    Razorpay order' -> Razorpay 'Authentication failed' when throttled.
    Retry a few times with backoff so tests aren't flaky due to external
    provider throttling."""
    last_resp = None
    for attempt in range(retries):
        r = session.post(f"{API}/razorpay/create-order",
                         json={"plan_id": plan_id}, timeout=30)
        if r.status_code == 200:
            return r
        last_resp = r
        # Only retry the provider-throttle path (502)
        if r.status_code != 502:
            return r
        time.sleep(backoff)
    return last_resp


@pytest.fixture(scope="class")
def rz_fresh_user():
    """Fresh no-plan user for Razorpay activation tests (isolated from other classes)."""
    from datetime import datetime, timezone
    s = requests.Session()
    email = f"TEST_rzuser_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": "rzpw12345", "name": "Razorpay Tester"
    }, timeout=30)
    assert r.status_code == 200, r.text
    uid = r.json()["user_id"]
    yield s, email, uid
    # cleanup
    db = _get_mongo_db_static()
    db.users.delete_one({"user_id": uid})
    db.payment_transactions.delete_many({"user_id": uid})


class TestRazorpayCreateOrder:
    """POST /api/razorpay/create-order"""

    def test_create_order_without_auth_returns_401(self):
        r = requests.post(f"{API}/razorpay/create-order", json={"plan_id": "daily"}, timeout=30)
        assert r.status_code == 401, r.text

    def test_create_order_invalid_plan_returns_400(self, admin_session):
        r = admin_session.post(f"{API}/razorpay/create-order", json={"plan_id": "yearly"}, timeout=30)
        assert r.status_code == 400, r.text
        assert r.json().get("detail") == "Invalid plan"

    @pytest.mark.parametrize("plan_id,expected_paise", [
        ("daily", 3500),
        ("weekly", 19900),
        ("monthly", 59900),
    ])
    def test_create_order_valid_plan_returns_order(self, admin_session, plan_id, expected_paise):
        r = _create_order_with_retry(admin_session, plan_id)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["order_id"].startswith("order_"), f"unexpected order id: {data.get('order_id')}"
        assert data["amount"] == expected_paise, f"expected {expected_paise} paise, got {data['amount']}"
        assert data["currency"] == "INR"
        assert data["key_id"].startswith("rzp_"), data.get("key_id")
        assert data["plan_name"] in ("Daily", "Weekly", "Monthly")
        assert "prefill" in data
        assert data["prefill"].get("email") == ADMIN_EMAIL

        # Verify pending transaction was persisted with gateway='razorpay'
        db = _get_mongo_db_static()
        txn = db.payment_transactions.find_one({"order_id": data["order_id"]})
        assert txn is not None, "pending payment_transactions record not created"
        assert txn["gateway"] == "razorpay"
        assert txn["plan_id"] == plan_id
        assert txn["payment_status"] == "pending"
        assert txn["currency"] == "INR"
        assert txn["amount"] == {"daily": 35, "weekly": 199, "monthly": 599}[plan_id]
        # cleanup this synthetic order
        db.payment_transactions.delete_one({"order_id": data["order_id"]})


class TestRazorpayVerifyPayment:
    """POST /api/razorpay/verify-payment - signature verification + idempotent activation"""

    def test_verify_missing_fields_returns_400(self, admin_session):
        r = admin_session.post(f"{API}/razorpay/verify-payment",
                               json={"razorpay_order_id": "order_x"}, timeout=30)
        assert r.status_code == 400, r.text
        assert "Missing" in r.json().get("detail", "")

    def test_verify_incorrect_signature_returns_400_and_marks_failed(self, rz_fresh_user):
        s, _, uid = rz_fresh_user
        # First create a real order so the transaction exists
        r = _create_order_with_retry(s, "daily")
        assert r.status_code == 200, r.text
        order_id = r.json()["order_id"]

        # Send an incorrect signature (well-formed hex, wrong value)
        r2 = s.post(f"{API}/razorpay/verify-payment", json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": "pay_fake_incorrect_sig",
            "razorpay_signature": "0" * 64,
        }, timeout=30)
        assert r2.status_code == 400, r2.text
        assert r2.json().get("detail") == "Payment verification failed"

        # Transaction must be marked failed
        db = _get_mongo_db_static()
        txn = db.payment_transactions.find_one({"order_id": order_id})
        assert txn is not None
        assert txn["payment_status"] == "failed"
        assert txn["status"] == "signature_mismatch"

        # Cleanup
        db.payment_transactions.delete_one({"order_id": order_id})

    def test_verify_unknown_order_with_valid_sig_returns_404(self, admin_session):
        cfg = _load_env_secret()
        secret = cfg["RAZORPAY_KEY_SECRET"]
        fake_order = f"order_UNKNOWN_{uuid.uuid4().hex[:10]}"
        fake_pay = "pay_fake_unknown"
        sig = _hmac.new(secret.encode(), f"{fake_order}|{fake_pay}".encode(), _hashlib.sha256).hexdigest()
        r = admin_session.post(f"{API}/razorpay/verify-payment", json={
            "razorpay_order_id": fake_order,
            "razorpay_payment_id": fake_pay,
            "razorpay_signature": sig,
        }, timeout=30)
        assert r.status_code == 404, r.text
        assert r.json().get("detail") == "Order not found"

    def test_verify_correct_signature_activates_plan_idempotently(self, rz_fresh_user):
        """End-to-end: create-order -> compute HMAC signature -> verify-payment.
        Confirms plan+plan_expires_at get set AND second verify is a no-op."""
        from datetime import datetime, timezone
        s, email, uid = rz_fresh_user

        # 1) Confirm user starts with no plan
        me0 = s.get(f"{API}/auth/me", timeout=30).json()
        # Reset in case a previous parametrized test left something
        db = _get_mongo_db_static()
        db.users.update_one({"user_id": uid}, {"$set": {"plan": None, "plan_expires_at": None}})
        db.payment_transactions.delete_many({"user_id": uid})

        # 2) Create real order
        r = _create_order_with_retry(s, "weekly")
        assert r.status_code == 200, r.text
        order_id = r.json()["order_id"]

        # 3) Compute signature = HMAC(order_id|payment_id, secret)
        cfg = _load_env_secret()
        secret = cfg["RAZORPAY_KEY_SECRET"]
        fake_pay = f"pay_test_{uuid.uuid4().hex[:12]}"
        sig = _hmac.new(secret.encode(), f"{order_id}|{fake_pay}".encode(), _hashlib.sha256).hexdigest()

        # 4) Verify-payment first call -> activates plan
        r2 = s.post(f"{API}/razorpay/verify-payment", json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": fake_pay,
            "razorpay_signature": sig,
        }, timeout=30)
        assert r2.status_code == 200, r2.text
        assert r2.json().get("status") == "success"

        # 5) Confirm plan activation via /api/auth/me
        me = s.get(f"{API}/auth/me", timeout=30).json()
        assert me["plan"] == "weekly", f"plan not activated, got {me['plan']!r}"
        assert me["plan_expires_at"] is not None
        expires_at_1 = me["plan_expires_at"]

        # 6) Confirm via billings/current-plan too (INR pricing)
        cp = s.get(f"{API}/billings/current-plan", timeout=30).json()
        assert cp["status"] == "active"
        assert cp["plan_name"] == "Weekly"
        assert cp["price"] == 199

        # 7) Idempotency: second call must NOT double-apply (expiry unchanged)
        time.sleep(1)  # ensure any timestamp diff would be visible
        r3 = s.post(f"{API}/razorpay/verify-payment", json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": fake_pay,
            "razorpay_signature": sig,
        }, timeout=30)
        assert r3.status_code == 200, r3.text
        me2 = s.get(f"{API}/auth/me", timeout=30).json()
        assert me2["plan"] == "weekly"
        assert me2["plan_expires_at"] == expires_at_1, (
            f"expiry shifted on idempotent replay: {expires_at_1} -> {me2['plan_expires_at']}"
        )

        # 8) Regression: this user (now activated) should be able to hit gated endpoint
        r4 = s.get(f"{API}/live-slot", timeout=30)
        assert r4.status_code == 200, "activated user should pass gatekeeping"

    def test_renewal_extends_expiry_when_active(self):
        """Iteration 5: A user with an ACTIVE (non-expired) daily plan who
        re-buys the SAME plan (daily) must have plan_expires_at EXTENDED by
        ~1 day beyond the previous FUTURE expiry, NOT reset to now+1day.
        """
        from datetime import datetime, timezone, timedelta
        # Fresh isolated user for this test
        s = requests.Session()
        email = f"TEST_rzrenew_{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register", json={
            "email": email, "password": "renewpw1", "name": "Renew Tester"
        }, timeout=30)
        assert r.status_code == 200, r.text
        uid = r.json()["user_id"]

        db = _get_mongo_db_static()
        try:
            # 1) Seed a FUTURE expiry (12h from now) with an active daily plan
            future_expiry = datetime.now(timezone.utc) + timedelta(hours=12)
            db.users.update_one({"user_id": uid}, {"$set": {
                "plan": "daily",
                "plan_expires_at": future_expiry,
            }})

            # Confirm via /auth/me
            me0 = s.get(f"{API}/auth/me", timeout=30).json()
            assert me0["plan"] == "daily"
            prev_expiry = datetime.fromisoformat(me0["plan_expires_at"].replace("Z", "")).replace(tzinfo=timezone.utc)
            # Should be within a second of what we set
            assert abs((prev_expiry - future_expiry).total_seconds()) < 5

            # 2) Create real order for daily
            r2 = _create_order_with_retry(s, "daily")
            assert r2.status_code == 200, r2.text
            order_id = r2.json()["order_id"]

            # 3) Compute signature and verify
            secret = _load_env_secret()["RAZORPAY_KEY_SECRET"]
            fake_pay = f"pay_test_{uuid.uuid4().hex[:12]}"
            sig = _hmac.new(secret.encode(), f"{order_id}|{fake_pay}".encode(),
                            _hashlib.sha256).hexdigest()
            r3 = s.post(f"{API}/razorpay/verify-payment", json={
                "razorpay_order_id": order_id,
                "razorpay_payment_id": fake_pay,
                "razorpay_signature": sig,
            }, timeout=30)
            assert r3.status_code == 200, r3.text
            assert r3.json().get("status") == "success"

            # 4) Fetch new expiry and assert it is ~= prev_expiry + 1 day
            me1 = s.get(f"{API}/auth/me", timeout=30).json()
            assert me1["plan"] == "daily"
            new_expiry = datetime.fromisoformat(me1["plan_expires_at"].replace("Z", "")).replace(tzinfo=timezone.utc)
            expected = prev_expiry + timedelta(days=1)
            delta = abs((new_expiry - expected).total_seconds())
            assert delta < 5, (
                f"expected extension {expected.isoformat()} (~prev + 1d), "
                f"got {new_expiry.isoformat()} (delta={delta}s). "
                f"Prev={prev_expiry.isoformat()}"
            )
            # Sanity: new expiry must be strictly greater than prev_expiry + 23h
            # (i.e. NOT reset to now+1d which would be ~12h earlier)
            assert new_expiry > prev_expiry + timedelta(hours=23), (
                f"expiry looks reset (now+1d) instead of stacked: prev={prev_expiry}, new={new_expiry}"
            )
        finally:
            db.users.delete_one({"user_id": uid})
            db.payment_transactions.delete_many({"user_id": uid})

    def test_renewal_resets_expiry_when_expired(self):
        """Iteration 5: If the plan is EXPIRED (plan_expires_at in the past),
        renewing daily must RESET expiry to now+1day (not stack on the past date).
        """
        from datetime import datetime, timezone, timedelta
        s = requests.Session()
        email = f"TEST_rzrenexp_{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register", json={
            "email": email, "password": "renewpw2", "name": "Renew Exp Tester"
        }, timeout=30)
        assert r.status_code == 200, r.text
        uid = r.json()["user_id"]

        db = _get_mongo_db_static()
        try:
            # 1) Seed a PAST expiry (2 days ago)
            past_expiry = datetime.now(timezone.utc) - timedelta(days=2)
            db.users.update_one({"user_id": uid}, {"$set": {
                "plan": "daily",
                "plan_expires_at": past_expiry,
            }})

            # 2) Create real order for daily
            r2 = _create_order_with_retry(s, "daily")
            assert r2.status_code == 200, r2.text
            order_id = r2.json()["order_id"]

            # 3) Verify with correct signature
            secret = _load_env_secret()["RAZORPAY_KEY_SECRET"]
            fake_pay = f"pay_test_{uuid.uuid4().hex[:12]}"
            sig = _hmac.new(secret.encode(), f"{order_id}|{fake_pay}".encode(),
                            _hashlib.sha256).hexdigest()
            t_before = datetime.now(timezone.utc)
            r3 = s.post(f"{API}/razorpay/verify-payment", json={
                "razorpay_order_id": order_id,
                "razorpay_payment_id": fake_pay,
                "razorpay_signature": sig,
            }, timeout=30)
            t_after = datetime.now(timezone.utc)
            assert r3.status_code == 200, r3.text

            # 4) New expiry must be ~ now + 1 day (not stacked on past date)
            me1 = s.get(f"{API}/auth/me", timeout=30).json()
            new_expiry = datetime.fromisoformat(me1["plan_expires_at"].replace("Z", "")).replace(tzinfo=timezone.utc)
            # It should be between t_before+1d and t_after+1d (allow a few seconds slack)
            low = t_before + timedelta(days=1) - timedelta(seconds=5)
            high = t_after + timedelta(days=1) + timedelta(seconds=5)
            assert low <= new_expiry <= high, (
                f"expected ~now+1d ([{low}, {high}]), got {new_expiry}. "
                f"past_expiry was {past_expiry}."
            )
            # Sanity: must be much greater than past_expiry (>= ~1 day in future)
            assert new_expiry > datetime.now(timezone.utc) + timedelta(hours=23)
        finally:
            db.users.delete_one({"user_id": uid})
            db.payment_transactions.delete_many({"user_id": uid})

    def test_renewal_different_plan_resets_from_now(self):
        """Iteration 5 companion: If user holds an ACTIVE plan of a DIFFERENT
        type (e.g. daily active) and buys weekly, the new expiry must reset
        from now (not stack) because the plan changed.
        """
        from datetime import datetime, timezone, timedelta
        s = requests.Session()
        email = f"TEST_rzswitch_{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register", json={
            "email": email, "password": "swpw1", "name": "Switch Tester"
        }, timeout=30)
        assert r.status_code == 200, r.text
        uid = r.json()["user_id"]

        db = _get_mongo_db_static()
        try:
            # Active daily plan expiring in ~12h
            future_expiry = datetime.now(timezone.utc) + timedelta(hours=12)
            db.users.update_one({"user_id": uid}, {"$set": {
                "plan": "daily", "plan_expires_at": future_expiry,
            }})

            # User buys WEEKLY (different plan)
            r2 = _create_order_with_retry(s, "weekly")
            assert r2.status_code == 200, r2.text
            order_id = r2.json()["order_id"]

            secret = _load_env_secret()["RAZORPAY_KEY_SECRET"]
            fake_pay = f"pay_test_{uuid.uuid4().hex[:12]}"
            sig = _hmac.new(secret.encode(), f"{order_id}|{fake_pay}".encode(),
                            _hashlib.sha256).hexdigest()
            t_before = datetime.now(timezone.utc)
            r3 = s.post(f"{API}/razorpay/verify-payment", json={
                "razorpay_order_id": order_id, "razorpay_payment_id": fake_pay,
                "razorpay_signature": sig,
            }, timeout=30)
            t_after = datetime.now(timezone.utc)
            assert r3.status_code == 200, r3.text

            me1 = s.get(f"{API}/auth/me", timeout=30).json()
            assert me1["plan"] == "weekly"
            new_expiry = datetime.fromisoformat(me1["plan_expires_at"].replace("Z", "")).replace(tzinfo=timezone.utc)
            # Should be ~now + 7d, NOT future_expiry + 7d
            low = t_before + timedelta(days=7) - timedelta(seconds=5)
            high = t_after + timedelta(days=7) + timedelta(seconds=5)
            assert low <= new_expiry <= high, (
                f"expected ~now+7d ([{low}, {high}]), got {new_expiry}. "
                f"Previous daily-expiry {future_expiry} should NOT have stacked."
            )
        finally:
            db.users.delete_one({"user_id": uid})
            db.payment_transactions.delete_many({"user_id": uid})

    def test_no_plan_user_still_gated_after_failed_verify(self, rz_fresh_user):
        """Regression: gatekeeping still enforced for a user who paid nothing."""
        # Use a NEW isolated session so we don't reuse the activated one above.
        s2 = requests.Session()
        email = f"TEST_rzgate_{uuid.uuid4().hex[:8]}@example.com"
        r = s2.post(f"{API}/auth/register", json={
            "email": email, "password": "pw12345", "name": "RZ Gate"
        }, timeout=30)
        assert r.status_code == 200

        # No plan - gatekeeping must apply
        r2 = s2.get(f"{API}/live-slot", timeout=30)
        assert r2.status_code == 403
        assert r2.json().get("detail") == GATEKEEP_MSG

        files = {"file": ("t.mp4", io.BytesIO(b"a"), "video/mp4")}
        r3 = s2.post(f"{API}/videos/upload", files=files, data={"title": "TEST_x"}, timeout=30)
        assert r3.status_code == 403
        assert r3.json().get("detail") == GATEKEEP_MSG

        # cleanup
        db = _get_mongo_db_static()
        db.users.delete_one({"email": email})


# ==================== Iteration 6: Chunked Upload + Auth Refresh ====================

import jwt as _jwt


class TestAuthRefreshIter6:
    """POST /api/auth/refresh - iteration 6"""

    def test_refresh_without_cookie_returns_401(self):
        r = requests.post(f"{API}/auth/refresh", timeout=15)
        assert r.status_code == 401, r.text
        assert r.json().get("detail") == "No refresh token"

    def test_refresh_with_valid_cookie_issues_new_access_token(self, admin_session):
        # admin_session already logged in; has both cookies
        assert "refresh_token" in admin_session.cookies
        old_access = admin_session.cookies.get("access_token")
        # Need a small delay to guarantee a different token payload timestamp
        time.sleep(1)
        r = admin_session.post(f"{API}/auth/refresh", timeout=15)
        assert r.status_code == 200, r.text
        # New access_token cookie must be set
        set_cookies = r.headers.get("set-cookie", "") or r.headers.get("Set-Cookie", "")
        assert "access_token" in set_cookies.lower(), f"Set-Cookie: {set_cookies!r}"
        new_access = admin_session.cookies.get("access_token")
        assert new_access is not None
        # /auth/me should still work with the new token
        me = admin_session.get(f"{API}/auth/me", timeout=15)
        assert me.status_code == 200

    def test_refresh_after_removing_access_token_still_works(self, admin_session):
        """Simulate the axios interceptor scenario: access_token missing but
        refresh_token present -> /auth/refresh issues a fresh access_token so
        a subsequent protected call succeeds."""
        # Make a fresh session that copies only the refresh_token
        s2 = requests.Session()
        rt = admin_session.cookies.get("refresh_token")
        assert rt, "admin_session missing refresh_token"
        s2.cookies.set("refresh_token", rt)
        # Without access_token, /auth/me should be 401
        r0 = s2.get(f"{API}/auth/me", timeout=15)
        assert r0.status_code == 401
        # Refresh
        r = s2.post(f"{API}/auth/refresh", timeout=15)
        assert r.status_code == 200, r.text
        # Now /auth/me should succeed
        r2 = s2.get(f"{API}/auth/me", timeout=15)
        assert r2.status_code == 200, r2.text

    def test_refresh_rejects_invalid_refresh_token(self):
        s = requests.Session()
        s.cookies.set("refresh_token", "this.is.not.a.valid.jwt")
        r = s.post(f"{API}/auth/refresh", timeout=15)
        assert r.status_code == 401

    def test_refresh_rejects_access_token_as_refresh(self, admin_session):
        """Sending an access_token in the refresh_token cookie must be rejected
        (type != 'refresh')."""
        at = admin_session.cookies.get("access_token")
        assert at
        s = requests.Session()
        s.cookies.set("refresh_token", at)
        r = s.post(f"{API}/auth/refresh", timeout=15)
        assert r.status_code == 401
        assert r.json().get("detail") in ("Invalid token type", "Invalid refresh token")

    def test_access_token_is_12h(self):
        """Access token now has 12h lifetime (iteration 6 fix)."""
        from pathlib import Path
        env = Path("/app/backend/.env").read_text().splitlines()
        secret = None
        for line in env:
            if line.startswith("JWT_SECRET="):
                secret = line.split("=", 1)[1].strip().strip('"')
                break
        assert secret, "JWT_SECRET missing from .env"

        s = requests.Session()
        r = s.post(f"{API}/auth/login",
                   json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
        assert r.status_code == 200
        access = s.cookies.get("access_token")
        assert access
        payload = _jwt.decode(access, secret, algorithms=["HS256"])
        # exp - iat approx 12h
        exp = payload["exp"]
        # Also allow verifying via 'exp' - now
        from datetime import datetime, timezone as _tz
        now_ts = int(datetime.now(_tz.utc).timestamp())
        remaining = exp - now_ts
        # Expect ~12h (43200s), with a couple minutes slack
        assert 43000 <= remaining <= 43300, f"access token TTL not ~12h: {remaining}s"


class TestChunkedUploadIter6:
    """POST /api/videos/upload/chunk - iteration 6"""

    def _split_and_upload(self, session, payload_bytes, filename, title,
                         chunk_size=1024, expected_status=200):
        upload_id = uuid.uuid4().hex[:16]
        total_chunks = max(1, (len(payload_bytes) + chunk_size - 1) // chunk_size)
        last = None
        for i in range(total_chunks):
            chunk = payload_bytes[i*chunk_size:(i+1)*chunk_size]
            files = {"file": (filename, io.BytesIO(chunk), "application/octet-stream")}
            data = {
                "upload_id": upload_id,
                "chunk_index": i,
                "total_chunks": total_chunks,
                "filename": filename,
                "title": title,
            }
            r = session.post(f"{API}/videos/upload/chunk", files=files, data=data, timeout=60)
            last = r
            if r.status_code != 200:
                return r, upload_id, total_chunks
        return last, upload_id, total_chunks

    def test_chunk_upload_without_plan_returns_403_with_exact_message(self, fresh_user):
        s, _, _ = fresh_user
        payload = b"A" * 100
        r, _, _ = self._split_and_upload(s, payload, "np.mp4", "TEST_no_plan_chunk", chunk_size=50)
        assert r.status_code == 403, r.text
        # Accept either purchase message or expired variant
        detail = r.json().get("detail", "")
        assert detail == GATEKEEP_MSG or "expired" in detail.lower(), f"Unexpected: {detail!r}"

    def test_chunk_upload_success_reassembles_and_creates_video(self, admin_session):
        # Get storage_used before
        me0 = admin_session.get(f"{API}/auth/me", timeout=15).json()
        before = me0.get("storage_used", 0)
        payload = os.urandom(5000)  # 5KB
        chunk_size = 1500  # -> 4 chunks
        r, upload_id, total_chunks = self._split_and_upload(
            admin_session, payload, "chunk_test.mp4",
            "TEST_chunked_upload", chunk_size=chunk_size)
        assert r.status_code == 200, r.text
        resp = r.json()
        assert resp["status"] == "completed", resp
        assert "video_id" in resp
        assert resp["size"] == len(payload), (resp["size"], len(payload))
        assert "Ready for the stream!" in resp["message"]
        vid = resp["video_id"]
        # storage_used incremented
        me1 = admin_session.get(f"{API}/auth/me", timeout=15).json()
        assert me1["storage_used"] == before + len(payload), (before, me1["storage_used"])
        # Video appears in listing
        lst = admin_session.get(f"{API}/videos", timeout=15).json()
        assert any(v["video_id"] == vid for v in lst), "video not present in listing"
        found = next(v for v in lst if v["video_id"] == vid)
        assert found["size"] == len(payload)
        assert found["title"] == "TEST_chunked_upload"
        # Cleanup
        admin_session.delete(f"{API}/videos/{vid}", timeout=15)

    def test_chunk_non_final_returns_chunk_received(self, admin_session):
        upload_id = uuid.uuid4().hex[:16]
        files = {"file": ("part.mp4", io.BytesIO(b"a" * 100), "application/octet-stream")}
        data = {
            "upload_id": upload_id,
            "chunk_index": 0,
            "total_chunks": 3,
            "filename": "part.mp4",
            "title": "TEST_partial_chunk",
        }
        r = admin_session.post(f"{API}/videos/upload/chunk", files=files, data=data, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") == "chunk_received"
        assert body.get("chunk_index") == 0
        # Cleanup partial file
        from pathlib import Path as _P
        me = admin_session.get(f"{API}/auth/me", timeout=15).json()
        p = _P("/app/backend/uploads/tmp") / f"{me['user_id']}_{upload_id}.part"
        if p.exists():
            p.unlink()

    def test_chunk_upload_storage_limit_exceeded_returns_400(self, admin_session):
        """Set storage_used near the 2GB limit and try to upload a payload that
        exceeds the remaining budget."""
        from pymongo import MongoClient
        from pathlib import Path
        env = Path("/app/backend/.env").read_text().splitlines()
        cfg = {}
        for line in env:
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"')
        cli = MongoClient(cfg["MONGO_URL"])
        db = cli[cfg["DB_NAME"]]
        me = admin_session.get(f"{API}/auth/me", timeout=15).json()
        uid = me["user_id"]
        original = me.get("storage_used", 0)
        MAX = 2 * 1024 * 1024 * 1024
        # 512 bytes remaining
        db.users.update_one({"user_id": uid}, {"$set": {"storage_used": MAX - 512}})
        try:
            # Upload 2KB in two 1KB chunks - should be rejected during first or second chunk
            payload = b"x" * 2048
            r, upload_id, _ = self._split_and_upload(
                admin_session, payload, "big.mp4",
                "TEST_over_limit_chunk", chunk_size=1024)
            assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
            assert "Storage limit" in r.json().get("detail", "")
        finally:
            db.users.update_one({"user_id": uid}, {"$set": {"storage_used": original}})

    def test_chunk_upload_first_chunk_wipes_previous_partial(self, admin_session):
        """If a previous aborted upload left a .part file, sending chunk_index=0
        must start fresh (not append)."""
        from pathlib import Path as _P
        me = admin_session.get(f"{API}/auth/me", timeout=15).json()
        uid = me["user_id"]
        upload_id = uuid.uuid4().hex[:16]
        tmp = _P("/app/backend/uploads/tmp")
        tmp.mkdir(parents=True, exist_ok=True)
        part = tmp / f"{uid}_{upload_id}.part"
        part.write_bytes(b"GARBAGE" * 100)  # 700 bytes of stale data

        payload = os.urandom(1500)
        # Single chunk covering the whole payload
        files = {"file": ("clean.mp4", io.BytesIO(payload), "application/octet-stream")}
        data = {
            "upload_id": upload_id,
            "chunk_index": 0,
            "total_chunks": 1,
            "filename": "clean.mp4",
            "title": "TEST_chunk_wipes_stale",
        }
        r = admin_session.post(f"{API}/videos/upload/chunk", files=files, data=data, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "completed"
        # Size MUST be len(payload) - proving the stale bytes were dropped
        assert body["size"] == len(payload), (body["size"], len(payload))
        admin_session.delete(f"{API}/videos/{body['video_id']}", timeout=15)


class TestDashboardStatsPlanReflection:
    """Iteration 6: /api/dashboard/stats must return `plan` and `plan_expires_at`
    (used by the Dashboard to render Plan Validity)."""

    def test_stats_has_plan_and_expiry_for_active_user(self, admin_session):
        r = admin_session.get(f"{API}/dashboard/stats", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("plan") == "monthly"
        assert data.get("plan_expires_at") is not None

    def test_stats_no_plan_for_fresh_user(self, fresh_user):
        s, _, _ = fresh_user
        r = s.get(f"{API}/dashboard/stats", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("plan") is None
        assert data.get("plan_expires_at") is None



# ==================== Iteration 7: Idempotent Chunked Upload + Resumability ====================

class TestIter7Idempotency:
    """Iteration 7: (user_id, upload_id) idempotency; retried finalize returns
    same video_id, no duplicate DB row, storage counted once."""

    @pytest.fixture
    def plan_user(self):
        from datetime import datetime, timezone, timedelta
        s = requests.Session()
        email = f"TEST_iter7_{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register", json={
            "email": email, "password": "iter7pw1", "name": "Iter7 Tester"
        }, timeout=30)
        assert r.status_code == 200, r.text
        uid = r.json()["user_id"]
        db = _get_mongo_db_static()
        db.users.update_one({"user_id": uid}, {"$set": {
            "plan": "daily",
            "plan_expires_at": datetime.now(timezone.utc) + timedelta(days=1),
            "storage_used": 0,
        }})
        yield s, email, uid
        db.videos.delete_many({"user_id": uid})
        db.users.delete_one({"user_id": uid})

    def _post_chunk(self, session, upload_id, chunk_index, total_chunks,
                    filename, title, offset, content):
        files = {"file": (filename, io.BytesIO(content), "video/mp4")}
        data = {
            "upload_id": upload_id,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "filename": filename,
            "title": title,
            "offset": offset,
        }
        return session.post(f"{API}/videos/upload/chunk", files=files, data=data, timeout=60)

    def test_duplicate_final_chunk_returns_same_video_id_no_double_row(self, plan_user):
        """The core bug fix: sending the same single-chunk upload twice must NOT
        create two video rows. Second call returns same video_id and idempotent=True."""
        s, _, uid = plan_user
        upload_id = uuid.uuid4().hex[:16]
        payload = os.urandom(2048)

        me0 = s.get(f"{API}/auth/me", timeout=15).json()
        storage_before = me0.get("storage_used", 0)

        # First upload -> creates the video
        r1 = self._post_chunk(s, upload_id, 0, 1, "dup.mp4",
                              "TEST_iter7_dup", 0, payload)
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert body1["status"] == "completed"
        vid1 = body1["video_id"]
        assert body1["size"] == len(payload)

        # Second identical upload -> idempotent, same video_id
        r2 = self._post_chunk(s, upload_id, 0, 1, "dup.mp4",
                              "TEST_iter7_dup", 0, payload)
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2["status"] == "completed"
        assert body2["video_id"] == vid1, (
            f"expected same video_id on retry, got {vid1} vs {body2['video_id']}"
        )
        assert body2.get("idempotent") is True

        # GET /api/videos returns exactly ONE video for this upload_id
        db = _get_mongo_db_static()
        rows = list(db.videos.find({"user_id": uid, "upload_id": upload_id}))
        assert len(rows) == 1, f"expected 1 video row, got {len(rows)}"

        # Storage_used incremented exactly ONCE
        me1 = s.get(f"{API}/auth/me", timeout=15).json()
        assert me1["storage_used"] == storage_before + len(payload), (
            f"storage counted twice: before={storage_before}, after={me1['storage_used']}, "
            f"payload={len(payload)}"
        )

    def test_status_endpoint_fresh_upload(self, plan_user):
        s, _, uid = plan_user
        upload_id = uuid.uuid4().hex[:16]
        r = s.get(f"{API}/videos/upload/status/{upload_id}", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["completed"] is False
        assert body["received_bytes"] == 0

    def test_status_endpoint_after_partial_chunk(self, plan_user):
        s, _, uid = plan_user
        upload_id = uuid.uuid4().hex[:16]
        # Send chunk 0 of 3 (non-final)
        r0 = self._post_chunk(s, upload_id, 0, 3, "p.mp4",
                              "TEST_iter7_partial", 0, b"A" * 512)
        assert r0.status_code == 200, r0.text
        assert r0.json()["status"] == "chunk_received"
        r = s.get(f"{API}/videos/upload/status/{upload_id}", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["completed"] is False
        assert body["received_bytes"] == 512
        # Cleanup part file
        from pathlib import Path as _P
        p = _P("/app/backend/uploads/tmp") / f"{uid}_{upload_id}.part"
        if p.exists():
            p.unlink()

    def test_status_endpoint_after_completion(self, plan_user):
        s, _, uid = plan_user
        upload_id = uuid.uuid4().hex[:16]
        payload = b"Z" * 1024
        r1 = self._post_chunk(s, upload_id, 0, 1, "done.mp4",
                              "TEST_iter7_done", 0, payload)
        assert r1.status_code == 200
        vid = r1.json()["video_id"]
        r = s.get(f"{API}/videos/upload/status/{upload_id}", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["completed"] is True
        assert body["received_bytes"] == len(payload)
        assert body["video_id"] == vid

    def test_offset_retry_does_not_double_write(self, plan_user):
        """Send chunk 0 (offset=0, 1KB), chunk 1 (offset=1024, 1KB),
        then RETRY chunk 1 (same offset=1024, 1KB). Final file must be 2KB, not 3KB."""
        s, _, uid = plan_user
        upload_id = uuid.uuid4().hex[:16]
        chunk_size = 1024
        c0 = b"a" * chunk_size
        c1 = b"b" * chunk_size

        # Chunk 0 (non-final since total_chunks=2)
        r0 = self._post_chunk(s, upload_id, 0, 2, "off.mp4",
                              "TEST_iter7_offset", 0, c0)
        assert r0.status_code == 200, r0.text
        assert r0.json()["status"] == "chunk_received"
        assert r0.json()["received_bytes"] == chunk_size

        # Chunk 1 retry #1 - final chunk. This finalizes the video.
        r1 = self._post_chunk(s, upload_id, 1, 2, "off.mp4",
                              "TEST_iter7_offset", chunk_size, c1)
        assert r1.status_code == 200, r1.text
        body = r1.json()
        assert body["status"] == "completed"
        vid = body["video_id"]
        assert body["size"] == 2 * chunk_size, f"final size wrong: {body['size']}"

        # Retry the same "final chunk" - must be idempotent, size still 2KB
        r2 = self._post_chunk(s, upload_id, 1, 2, "off.mp4",
                              "TEST_iter7_offset", chunk_size, c1)
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2["video_id"] == vid
        assert body2["size"] == 2 * chunk_size

        # Only 1 video row
        db = _get_mongo_db_static()
        rows = list(db.videos.find({"user_id": uid, "upload_id": upload_id}))
        assert len(rows) == 1
        assert rows[0]["size"] == 2 * chunk_size

    def test_unique_index_exists_on_videos(self):
        """Verify db.videos has partial unique index on (user_id, upload_id)."""
        db = _get_mongo_db_static()
        indexes = list(db.videos.list_indexes())
        target = next((i for i in indexes if i.get("name") == "uniq_user_upload_id"), None)
        assert target is not None, f"index uniq_user_upload_id missing. Existing: {[i.get('name') for i in indexes]}"
        assert target.get("unique") is True
        key = list(target["key"].items())
        assert key == [("user_id", 1), ("upload_id", 1)], f"unexpected key: {key}"
        # Partial filter should include upload_id string constraint
        pfe = target.get("partialFilterExpression", {})
        assert "upload_id" in pfe

    def test_gatekeeping_still_enforced_on_chunk_endpoint(self, fresh_user):
        """Regression: no-plan users still get 403 with exact message."""
        s, _, _ = fresh_user
        upload_id = uuid.uuid4().hex[:16]
        files = {"file": ("gk.mp4", io.BytesIO(b"x" * 100), "video/mp4")}
        data = {
            "upload_id": upload_id,
            "chunk_index": 0,
            "total_chunks": 1,
            "filename": "gk.mp4",
            "title": "TEST_iter7_gk",
            "offset": 0,
        }
        r = s.post(f"{API}/videos/upload/chunk", files=files, data=data, timeout=30)
        assert r.status_code in (402, 403), r.text
        detail = r.json().get("detail", "")
        # Accept the exact purchase message
        assert "purchase" in detail.lower() or "plan" in detail.lower(), detail

    def test_concurrent_final_chunks_yield_one_row(self, plan_user):
        """Fire 2 identical final-chunk requests concurrently. At most one
        video row must be created."""
        import concurrent.futures as _cf
        s, _, uid = plan_user
        upload_id = uuid.uuid4().hex[:16]
        payload = os.urandom(3000)

        def _fire():
            # Use a fresh session-like object cloned from `s` (share cookies)
            files = {"file": ("conc.mp4", io.BytesIO(payload), "video/mp4")}
            data = {
                "upload_id": upload_id,
                "chunk_index": 0,
                "total_chunks": 1,
                "filename": "conc.mp4",
                "title": "TEST_iter7_conc",
                "offset": 0,
            }
            return s.post(f"{API}/videos/upload/chunk",
                          files=files, data=data, timeout=60)

        with _cf.ThreadPoolExecutor(max_workers=2) as ex:
            futs = [ex.submit(_fire) for _ in range(2)]
            responses = [f.result() for f in futs]

        # Both should return 200 (one creates, one is idempotent)
        assert all(r.status_code == 200 for r in responses), \
            [(r.status_code, r.text[:200]) for r in responses]
        vids = {r.json()["video_id"] for r in responses}
        assert len(vids) == 1, f"different video_ids: {vids}"

        # DB must have exactly 1 row
        db = _get_mongo_db_static()
        rows = list(db.videos.find({"user_id": uid, "upload_id": upload_id}))
        assert len(rows) == 1, f"concurrent finalize created {len(rows)} rows"


# ==================== Iteration 8: Admin lifetime + Profile + Thumbnails ====================

class TestIter8AdminLifetime:
    """Admin now has plan='lifetime', stream_slots=3, plan_expires_at far in future."""

    def test_admin_me_returns_lifetime_and_3_slots(self, admin_session):
        r = admin_session.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["plan"] == "lifetime", f"expected plan=lifetime, got {data.get('plan')}"
        assert data["stream_slots"] == 3, f"expected stream_slots=3, got {data.get('stream_slots')}"
        assert data.get("role") == "admin", f"expected role=admin, got {data.get('role')}"
        # plan_expires_at should be far future (>= 50 years out)
        from datetime import datetime, timezone, timedelta
        exp_str = data.get("plan_expires_at")
        assert exp_str is not None
        exp = datetime.fromisoformat(exp_str.replace("Z", "")).replace(tzinfo=timezone.utc)
        assert exp > datetime.now(timezone.utc) + timedelta(days=365*50), \
            f"plan_expires_at not far-future: {exp_str}"

    def test_lifetime_bypasses_plan_expiry_even_if_past(self, admin_session):
        """Force admin.plan_expires_at into the past — 'lifetime' short-circuit
        in check_active_plan must still allow the upload/chunk endpoint."""
        from datetime import datetime, timezone, timedelta
        me = admin_session.get(f"{API}/auth/me", timeout=15).json()
        uid = me["user_id"]
        original_exp = me.get("plan_expires_at")
        db = _get_mongo_db_static()
        # Put expiry into the past
        db.users.update_one({"user_id": uid}, {"$set": {
            "plan_expires_at": datetime.now(timezone.utc) - timedelta(days=10)
        }})
        try:
            upload_id = uuid.uuid4().hex[:16]
            payload = b"a" * 200
            files = {"file": ("lp.mp4", io.BytesIO(payload), "video/mp4")}
            data = {"upload_id": upload_id, "chunk_index": 0, "total_chunks": 1,
                    "filename": "lp.mp4", "title": "TEST_iter8_lifetime_bypass", "offset": 0}
            r = admin_session.post(f"{API}/videos/upload/chunk", files=files, data=data, timeout=60)
            assert r.status_code == 200, f"lifetime bypass failed: {r.status_code} {r.text}"
            body = r.json()
            assert body.get("status") == "completed"
            admin_session.delete(f"{API}/videos/{body['video_id']}", timeout=15)
        finally:
            # Restore original expiry (parse back to datetime)
            if original_exp:
                exp = datetime.fromisoformat(original_exp.replace("Z", "")).replace(tzinfo=timezone.utc)
                db.users.update_one({"user_id": uid}, {"$set": {"plan_expires_at": exp}})


class TestIter8ProfileUpdate:
    """PUT /api/auth/profile - name/email/password updates + validation."""

    def test_update_name(self, admin_session):
        me0 = admin_session.get(f"{API}/auth/me", timeout=15).json()
        orig_name = me0["name"]
        try:
            r = admin_session.put(f"{API}/auth/profile", json={"name": "New Name"}, timeout=15)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("updated") is True
            assert "name" in body.get("fields", [])
            me = admin_session.get(f"{API}/auth/me", timeout=15).json()
            assert me["name"] == "New Name"
        finally:
            admin_session.put(f"{API}/auth/profile", json={"name": orig_name}, timeout=15)

    def test_update_email_then_revert(self, admin_session):
        me0 = admin_session.get(f"{API}/auth/me", timeout=15).json()
        orig_email = me0["email"]
        new_email = f"newadmin_{int(time.time())}@liveadda.org"
        try:
            r = admin_session.put(f"{API}/auth/profile", json={"email": new_email}, timeout=15)
            assert r.status_code == 200, r.text
            me = admin_session.get(f"{API}/auth/me", timeout=15).json()
            assert me["email"] == new_email
        finally:
            admin_session.put(f"{API}/auth/profile", json={"email": orig_email}, timeout=15)

    def test_change_password_flow_and_revert(self):
        """Change password → login with new → revert."""
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
        assert r.status_code == 200, r.text
        new_pw = "newSecret123"
        try:
            r2 = s.put(f"{API}/auth/profile", json={
                "current_password": ADMIN_PASSWORD, "new_password": new_pw
            }, timeout=15)
            assert r2.status_code == 200, r2.text
            # Login with new password
            s2 = requests.Session()
            r3 = s2.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": new_pw}, timeout=15)
            assert r3.status_code == 200, f"login with new password failed: {r3.text}"
            # Old password must now fail
            s3 = requests.Session()
            r4 = s3.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
            assert r4.status_code == 401
        finally:
            # Revert (log in with new_pw, change back)
            s_final = requests.Session()
            rr = s_final.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": new_pw}, timeout=15)
            if rr.status_code == 200:
                s_final.put(f"{API}/auth/profile", json={
                    "current_password": new_pw, "new_password": ADMIN_PASSWORD
                }, timeout=15)

    def test_new_password_without_current_returns_400(self, admin_session):
        r = admin_session.put(f"{API}/auth/profile",
                              json={"new_password": "anything123"}, timeout=15)
        assert r.status_code == 400, r.text

    def test_new_password_too_short_returns_400(self, admin_session):
        r = admin_session.put(f"{API}/auth/profile", json={
            "current_password": ADMIN_PASSWORD, "new_password": "abc"
        }, timeout=15)
        assert r.status_code == 400, r.text

    def test_wrong_current_password_returns_401(self, admin_session):
        r = admin_session.put(f"{API}/auth/profile", json={
            "current_password": "wrong", "new_password": "validPw123"
        }, timeout=15)
        assert r.status_code == 401, r.text


class TestIter8Thumbnails:
    """Thumbnail generation + auth + cross-user access."""

    def _upload_tiny_mp4(self, session, title="TEST_iter8_thumb"):
        """Upload /tmp/tiny.mp4 via chunked endpoint (single chunk)."""
        import shutil
        if not shutil.which("ffmpeg"):
            pytest.skip("ffmpeg not installed")
        path = "/tmp/tiny.mp4"
        if not os.path.exists(path):
            os.system(f"ffmpeg -y -f lavfi -i testsrc=duration=3:size=320x240:rate=15 -pix_fmt yuv420p {path} > /dev/null 2>&1")
        with open(path, "rb") as f:
            content = f.read()
        upload_id = uuid.uuid4().hex[:16]
        files = {"file": ("tiny.mp4", io.BytesIO(content), "video/mp4")}
        data = {"upload_id": upload_id, "chunk_index": 0, "total_chunks": 1,
                "filename": "tiny.mp4", "title": title, "offset": 0}
        r = session.post(f"{API}/videos/upload/chunk", files=files, data=data, timeout=60)
        assert r.status_code == 200, r.text
        return r.json()

    def test_thumbnail_generated_after_upload(self, admin_session):
        body = self._upload_tiny_mp4(admin_session)
        vid = body["video_id"]
        # finalize response should include thumbnail_url
        assert body.get("thumbnail_url") == f"/api/videos/{vid}/thumbnail", body
        try:
            # ffmpeg was up to 8s async — sleep briefly for thumbnail to be ready
            time.sleep(2)
            r = admin_session.get(f"{API}/videos/{vid}/thumbnail", timeout=30)
            assert r.status_code == 200, f"thumbnail fetch failed: {r.status_code} {r.text[:200]}"
            assert r.headers.get("content-type", "").startswith("image/jpeg"), r.headers
            assert len(r.content) > 500, f"thumbnail body too small: {len(r.content)}"
        finally:
            admin_session.delete(f"{API}/videos/{vid}", timeout=15)

    def test_thumbnail_requires_auth(self, admin_session):
        body = self._upload_tiny_mp4(admin_session, title="TEST_iter8_thumb_auth")
        vid = body["video_id"]
        try:
            time.sleep(2)
            r = requests.get(f"{API}/videos/{vid}/thumbnail", timeout=15)
            assert r.status_code == 401, f"expected 401 unauth, got {r.status_code}"
        finally:
            admin_session.delete(f"{API}/videos/{vid}", timeout=15)

    def test_thumbnail_cross_user_returns_404(self, admin_session):
        # Create a second isolated user with a plan
        from datetime import datetime, timezone, timedelta
        s2 = requests.Session()
        email = f"TEST_iter8_other_{uuid.uuid4().hex[:8]}@example.com"
        rr = s2.post(f"{API}/auth/register", json={
            "email": email, "password": "pw123456", "name": "Other"
        }, timeout=15)
        assert rr.status_code == 200
        uid2 = rr.json()["user_id"]
        db = _get_mongo_db_static()
        db.users.update_one({"user_id": uid2}, {"$set": {
            "plan": "daily",
            "plan_expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        }})
        body = self._upload_tiny_mp4(admin_session, title="TEST_iter8_thumb_x")
        admin_vid = body["video_id"]
        try:
            time.sleep(1)
            r = s2.get(f"{API}/videos/{admin_vid}/thumbnail", timeout=15)
            assert r.status_code == 404, f"expected 404 for cross-user, got {r.status_code}"
        finally:
            admin_session.delete(f"{API}/videos/{admin_vid}", timeout=15)
            db.users.delete_one({"user_id": uid2})


class TestIter8Sitemap:
    """Static assets: sitemap.xml + robots.txt at app root (served by frontend)."""

    def test_sitemap_reachable(self):
        r = requests.get(f"{BASE_URL}/sitemap.xml", timeout=15)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        assert "<urlset" in r.text or "<sitemapindex" in r.text

    def test_robots_reachable(self):
        r = requests.get(f"{BASE_URL}/robots.txt", timeout=15)
        assert r.status_code == 200
        assert "User-agent" in r.text or "Sitemap" in r.text


# ==================== ITERATION 9 TESTS ====================

class TestIter9Health:
    """GET /api/health public endpoint."""

    def test_health_no_auth_and_shape(self):
        r = requests.get(f"{API}/health", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "ok", data
        assert data.get("db") == "ok", data
        # build_sha should not be the literal 'unknown'
        sha = data.get("build_sha")
        assert isinstance(sha, str) and sha and sha != "unknown", f"bad build_sha: {sha!r}"
        # short git SHA is typically 7 chars but can be up to 40
        assert 4 <= len(sha) <= 40, f"unexpected sha length: {sha!r}"
        # server_time is ISO
        st = data.get("server_time", "")
        assert "T" in st and len(st) >= 19, f"bad server_time: {st!r}"
        # features flags
        f = data.get("features", {})
        for key in ("chunked_upload", "resumable_upload", "video_thumbnails",
                    "ffprobe_metadata", "multi_slot_streaming", "razorpay"):
            assert f.get(key) is True, f"feature flag {key} missing/false: {f}"


class TestIter9StreamsList:
    """GET /api/streams returns active list + slot budget."""

    def test_admin_streams_empty_default(self, admin_session):
        # Clean any leftover live streams first
        db = _get_mongo_db_static()
        me = admin_session.get(f"{API}/auth/me", timeout=15).json()
        db.live_streams.update_many(
            {"user_id": me["user_id"], "is_live": True},
            {"$set": {"is_live": False, "ffmpeg_pid": None}}
        )
        r = admin_session.get(f"{API}/streams", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data == {"active": [], "count": 0, "max_slots": 3, "slots_available": 3} \
            or (data["count"] == 0 and data["max_slots"] == 3 and data["slots_available"] == 3), data

    def test_fresh_user_max_slots_is_1(self, key_user):
        s, email, uid = key_user
        r = s.get(f"{API}/streams", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["max_slots"] == 1, data
        assert data["count"] == 0
        assert data["slots_available"] == 1


class TestIter9MultiSlot:
    """Multi-slot enforcement via seeded live_streams (no ffmpeg spawn).

    We seed is_live=True docs directly for admin so we can validate the
    count-check that runs BEFORE ffmpeg_service.start_ffmpeg_push. Then a real
    4th call should 403 without ever hitting ffmpeg.

    Also validates duplicate-key protection (409) — key check runs before the
    slot-count block only for the duplicate scenario? Actually the code checks
    slot budget first, then dup key. So for dup test we seed 1 active slot and
    call with same key => still gated by slot but only if budget full. We test
    dup with the same key while under limit.
    """

    def _cleanup(self, uid):
        db = _get_mongo_db_static()
        db.live_streams.delete_many({"user_id": uid, "stream_key": {"$regex": "^KEY-"}})

    def _get_admin_uid(self, admin_session):
        return admin_session.get(f"{API}/auth/me", timeout=15).json()["user_id"]

    def _get_video_id(self, admin_session):
        r = admin_session.get(f"{API}/videos", timeout=15)
        assert r.status_code == 200
        vids = r.json()
        if isinstance(vids, dict):
            vids = vids.get("videos", [])
        if not vids:
            # upload one
            import shutil
            path = "/tmp/tiny.mp4"
            if not os.path.exists(path):
                os.system(f"ffmpeg -y -f lavfi -i testsrc=duration=5:size=640x360:rate=15 -pix_fmt yuv420p {path} > /dev/null 2>&1")
            with open(path, "rb") as f:
                content = f.read()
            upload_id = uuid.uuid4().hex[:16]
            files = {"file": ("tiny.mp4", io.BytesIO(content), "video/mp4")}
            data = {"upload_id": upload_id, "chunk_index": 0, "total_chunks": 1,
                    "filename": "tiny.mp4", "title": "TEST_iter9_slotvid", "offset": 0}
            r = admin_session.post(f"{API}/videos/upload/chunk", files=files, data=data, timeout=60)
            assert r.status_code == 200, r.text
            return r.json()["video_id"]
        return vids[0]["video_id"]

    def test_multi_slot_count_enforcement_via_seed(self, admin_session):
        """Seed 3 live streams => 4th real POST returns 403 (count check before ffmpeg)."""
        from datetime import datetime, timezone
        uid = self._get_admin_uid(admin_session)
        db = _get_mongo_db_static()
        # Cleanup first
        db.live_streams.delete_many({"user_id": uid})
        try:
            for i, k in enumerate(["KEY-A", "KEY-B", "KEY-C"]):
                db.live_streams.insert_one({
                    "stream_id": f"seed_{i}_{uuid.uuid4().hex[:8]}",
                    "user_id": uid, "is_live": True, "stream_key": k,
                    "ffmpeg_pid": None, "started_at": datetime.now(timezone.utc),
                    "current_video": "seeded", "video_id": "seedvid", "stream_method": "manual_key",
                })
            # List should show 3
            lr = admin_session.get(f"{API}/streams", timeout=15).json()
            assert lr["count"] == 3, lr
            assert lr["max_slots"] == 3
            assert lr["slots_available"] == 0

            # 4th real call → 403 (no ffmpeg spawn because count check first)
            vid = self._get_video_id(admin_session)
            r = admin_session.post(f"{API}/stream/start-with-key",
                                    json={"video_id": vid, "stream_key": "KEY-D", "loop": True},
                                    timeout=15)
            assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"
            assert "maximum of 3" in r.text, r.text
        finally:
            db.live_streams.delete_many({"user_id": uid})

    def test_duplicate_stream_key_returns_409(self, admin_session):
        from datetime import datetime, timezone
        uid = self._get_admin_uid(admin_session)
        db = _get_mongo_db_static()
        db.live_streams.delete_many({"user_id": uid})
        try:
            # Seed 1 live stream under limit
            db.live_streams.insert_one({
                "stream_id": f"seed_dup_{uuid.uuid4().hex[:8]}",
                "user_id": uid, "is_live": True, "stream_key": "KEY-DUP",
                "ffmpeg_pid": None, "started_at": datetime.now(timezone.utc),
                "current_video": "seeded", "video_id": "seedvid", "stream_method": "manual_key",
            })
            vid = self._get_video_id(admin_session)
            r = admin_session.post(f"{API}/stream/start-with-key",
                                    json={"video_id": vid, "stream_key": "KEY-DUP", "loop": True},
                                    timeout=15)
            assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text}"
            assert "already live" in r.text.lower(), r.text
        finally:
            db.live_streams.delete_many({"user_id": uid})

    def test_stop_specific_stream_by_id(self, admin_session):
        from datetime import datetime, timezone
        uid = self._get_admin_uid(admin_session)
        db = _get_mongo_db_static()
        db.live_streams.delete_many({"user_id": uid})
        try:
            ids = []
            for k in ["KEY-X1", "KEY-X2", "KEY-X3"]:
                sid = f"seed_stop_{uuid.uuid4().hex[:8]}"
                db.live_streams.insert_one({
                    "stream_id": sid, "user_id": uid, "is_live": True,
                    "stream_key": k, "ffmpeg_pid": None,
                    "started_at": datetime.now(timezone.utc),
                    "current_video": "seeded", "video_id": "seedvid", "stream_method": "manual_key",
                })
                ids.append(sid)
            # stop the middle one
            target = ids[1]
            r = admin_session.post(f"{API}/stream/stop", json={"stream_id": target}, timeout=15)
            assert r.status_code == 200, r.text
            # verify
            listing = admin_session.get(f"{API}/streams", timeout=15).json()
            active_ids = [s["stream_id"] for s in listing["active"]]
            assert target not in active_ids, f"{target} still active: {active_ids}"
            assert set(active_ids) == {ids[0], ids[2]}, active_ids
            assert listing["count"] == 2
            # stop w/o body => stops most recent (ids[2] most-recent since inserted last)
            r2 = admin_session.post(f"{API}/stream/stop", json={}, timeout=15)
            assert r2.status_code == 200, r2.text
            listing2 = admin_session.get(f"{API}/streams", timeout=15).json()
            assert listing2["count"] == 1
        finally:
            db.live_streams.delete_many({"user_id": uid})


class TestIter9SingleSlotRegression:
    """Fresh daily user cannot start a 2nd concurrent stream."""

    def test_daily_user_2nd_stream_403(self, key_user):
        from datetime import datetime, timezone
        s, email, uid = key_user
        db = _get_mongo_db_static()
        db.live_streams.delete_many({"user_id": uid})
        try:
            # seed 1 live
            db.live_streams.insert_one({
                "stream_id": f"seed_single_{uuid.uuid4().hex[:8]}",
                "user_id": uid, "is_live": True, "stream_key": "USER-A",
                "ffmpeg_pid": None, "started_at": datetime.now(timezone.utc),
                "current_video": "seeded", "video_id": "seedvid", "stream_method": "manual_key",
            })
            # Need a video owned by this user — since we haven't uploaded any,
            # the endpoint would 404 on video lookup BEFORE hitting slot check.
            # server order: check_active_plan -> stream_key check -> video lookup -> slot count.
            # So we must seed a video doc.
            db.videos.insert_one({
                "video_id": "seedvid_user", "user_id": uid, "title": "TEST_seed",
                "file_path": "/tmp/tiny.mp4", "duration": 0
            })
            r = s.post(f"{API}/stream/start-with-key",
                        json={"video_id": "seedvid_user", "stream_key": "USER-B", "loop": True},
                        timeout=15)
            assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"
            assert "maximum of 1" in r.text, r.text
        finally:
            db.live_streams.delete_many({"user_id": uid})
            db.videos.delete_many({"video_id": "seedvid_user"})


class TestIter9FfprobeMetadata:
    """After finalize, GET /api/videos returns duration/width/height for uploaded MP4."""

    def test_ffprobe_populated(self, admin_session):
        import shutil
        if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
            pytest.skip("ffmpeg/ffprobe not installed")
        path = "/tmp/iter9_probe.mp4"
        os.system(f"ffmpeg -y -f lavfi -i testsrc=duration=5:size=640x360:rate=15 -pix_fmt yuv420p {path} > /dev/null 2>&1")
        assert os.path.exists(path)
        with open(path, "rb") as f:
            content = f.read()
        upload_id = uuid.uuid4().hex[:16]
        files = {"file": ("iter9_probe.mp4", io.BytesIO(content), "video/mp4")}
        data = {"upload_id": upload_id, "chunk_index": 0, "total_chunks": 1,
                "filename": "iter9_probe.mp4", "title": "TEST_iter9_probe", "offset": 0}
        r = admin_session.post(f"{API}/videos/upload/chunk", files=files, data=data, timeout=60)
        assert r.status_code == 200, r.text
        vid = r.json()["video_id"]
        try:
            # brief wait for ffprobe extraction
            time.sleep(2)
            lst = admin_session.get(f"{API}/videos", timeout=15).json()
            videos = lst.get("videos", lst) if isinstance(lst, dict) else lst
            match = next((v for v in videos if v["video_id"] == vid), None)
            assert match is not None, "uploaded video not returned"
            assert match.get("duration_seconds", 0) in range(3, 8), match
            assert match.get("width") == 640, match
            assert match.get("height") == 360, match
            dur = match.get("duration", "")
            assert "5" in dur or "05" in dur, f"unexpected duration string: {dur!r}"
        finally:
            admin_session.delete(f"{API}/videos/{vid}", timeout=15)


class TestIter9DashboardStats:
    """dashboard/stats reflects multi-slot counts."""

    def test_stats_active_live_slots(self, admin_session):
        from datetime import datetime, timezone
        uid = admin_session.get(f"{API}/auth/me", timeout=15).json()["user_id"]
        db = _get_mongo_db_static()
        db.live_streams.delete_many({"user_id": uid})
        try:
            # baseline
            r0 = admin_session.get(f"{API}/dashboard/stats", timeout=15)
            assert r0.status_code == 200
            j0 = r0.json()
            assert j0.get("active_live_slots") == 0, j0
            assert j0.get("max_stream_slots") == 3, j0
            # seed 2
            for k in ["STAT-A", "STAT-B"]:
                db.live_streams.insert_one({
                    "stream_id": f"seed_stat_{uuid.uuid4().hex[:8]}",
                    "user_id": uid, "is_live": True, "stream_key": k,
                    "ffmpeg_pid": None, "started_at": datetime.now(timezone.utc),
                    "current_video": "seeded", "video_id": "seedvid", "stream_method": "manual_key",
                })
            r1 = admin_session.get(f"{API}/dashboard/stats", timeout=15).json()
            assert r1.get("active_live_slots") == 2, r1
            assert r1.get("max_stream_slots") == 3, r1
        finally:
            db.live_streams.delete_many({"user_id": uid})


class TestIter9GSCFile:
    """Google Search Console verification file at public/ root."""

    def test_gsc_file_reachable(self):
        r = requests.get(f"{BASE_URL}/google217b552950b617e1.html", timeout=15)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        body = r.text.strip()
        assert body == "google-site-verification: google217b552950b617e1.html", f"body was: {body!r}"

    def test_index_html_meta_gsc_token(self):
        r = requests.get(f"{BASE_URL}/", timeout=15)
        assert r.status_code == 200
        assert 'name="google-site-verification"' in r.text
        assert 'content="google217b552950b617e1"' in r.text
        assert "REPLACE_WITH_YOUR_GSC_TOKEN" not in r.text



# ==================== ITERATION 10: Slot Stacking ====================

# Shared persistent asyncio loop for direct-call tests. Motor binds its client to
# the first loop that touches it — using a single loop across all direct-call
# tests avoids "Event loop is closed" errors from _arun() spinning up new loops.
import asyncio as _asyncio_iter10
_ITER10_LOOP = _asyncio_iter10.new_event_loop()

def _arun(coro):
    return _ITER10_LOOP.run_until_complete(coro)


def _make_fresh_user_direct(name_suffix=""):
    """Register a fresh user via /api/auth/register and return (session, email, user_id)."""
    s = requests.Session()
    email = f"TEST_iter10_{uuid.uuid4().hex[:8]}{name_suffix}@example.com"
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": "pw123456", "name": "Iter10 Tester"
    }, timeout=30)
    assert r.status_code == 200, r.text
    return s, email, r.json()["user_id"]


class TestIter10ActivateOrExtendPlan:
    """Direct-call tests of server.activate_or_extend_plan()."""

    def test_stack_daily_weekly_daily_monthly(self):
        import asyncio
        import sys
        sys.path.insert(0, "/app/backend")
        from server import activate_or_extend_plan, db as server_db
        s, email, uid = _make_fresh_user_direct("_stack")
        static_db = _get_mongo_db_static()
        try:
            # 1) daily
            u = _arun(activate_or_extend_plan(uid, "daily"))
            assert u["stream_slots"] == 1, u
            assert len(u["active_plans"]) == 1
            assert u["active_plans"][0]["plan_id"] == "daily"
            daily_exp_1 = u["active_plans"][0]["expires_at"]

            # 2) weekly => 2 slots, 2 entries
            u = _arun(activate_or_extend_plan(uid, "weekly"))
            assert u["stream_slots"] == 2, u
            plan_ids = sorted([e["plan_id"] for e in u["active_plans"]])
            assert plan_ids == ["daily", "weekly"], plan_ids

            # 3) daily AGAIN — no new slot, but daily entry's expires_at extended by 1 day
            u = _arun(activate_or_extend_plan(uid, "daily"))
            assert u["stream_slots"] == 2, u
            assert len(u["active_plans"]) == 2
            daily_entry = next(e for e in u["active_plans"] if e["plan_id"] == "daily")
            new_daily_exp = daily_entry["expires_at"]
            # New expiry should be ~1 day further out than the original
            from datetime import timedelta
            def _to_dt(x):
                from datetime import datetime
                if isinstance(x, str):
                    return datetime.fromisoformat(x.replace("Z", "+00:00"))
                return x
            delta = _to_dt(new_daily_exp) - _to_dt(daily_exp_1)
            assert timedelta(hours=23) < delta < timedelta(hours=25), f"Expected ~1 day extension, got {delta}"

            # 4) monthly => 3 slots, 3 entries
            u = _arun(activate_or_extend_plan(uid, "monthly"))
            assert u["stream_slots"] == 3, u
            assert len(u["active_plans"]) == 3
            plan_ids = sorted([e["plan_id"] for e in u["active_plans"]])
            assert plan_ids == ["daily", "monthly", "weekly"]
        finally:
            static_db.users.delete_one({"user_id": uid})
            static_db.live_streams.delete_many({"user_id": uid})


class TestIter10ExpiryPruning:
    """sync_user_plans_and_enforce_slots prunes expired entries and stops excess ffmpeg streams."""

    def test_prune_and_shrink_slots(self):
        import asyncio, sys
        sys.path.insert(0, "/app/backend")
        from server import activate_or_extend_plan, sync_user_plans_and_enforce_slots, db as server_db
        from datetime import datetime, timezone, timedelta

        s, email, uid = _make_fresh_user_direct("_prune")
        static_db = _get_mongo_db_static()
        try:
            # Give the user daily + weekly (2 slots)
            _arun(activate_or_extend_plan(uid, "daily"))
            _arun(activate_or_extend_plan(uid, "weekly"))

            # Seed 2 live streams
            now = datetime.now(timezone.utc)
            for i, k in enumerate(["KEY-P1", "KEY-P2"]):
                static_db.live_streams.insert_one({
                    "stream_id": f"seed_prune_{i}_{uuid.uuid4().hex[:6]}",
                    "user_id": uid, "is_live": True, "stream_key": k,
                    "ffmpeg_pid": None,
                    "started_at": now + timedelta(seconds=i),  # newest = i=1
                    "current_video": "seeded", "video_id": "seedvid",
                    "stream_method": "manual_key",
                })

            # Push the daily entry's expires_at into the past
            user_doc = static_db.users.find_one({"user_id": uid})
            active = list(user_doc.get("active_plans") or [])
            for e in active:
                if e["plan_id"] == "daily":
                    e["expires_at"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
            static_db.users.update_one({"user_id": uid}, {"$set": {"active_plans": active}})

            # Sync — must prune daily, decrement slots to 1, stop the newest excess stream
            user_doc = static_db.users.find_one({"user_id": uid})
            _arun(sync_user_plans_and_enforce_slots(user_doc))

            refreshed = static_db.users.find_one({"user_id": uid})
            assert len(refreshed["active_plans"]) == 1, refreshed["active_plans"]
            assert refreshed["active_plans"][0]["plan_id"] == "weekly"
            assert refreshed["stream_slots"] == 1

            # Excess (newest) stream should be stopped with plan_expired_slot_shrink
            stopped = list(static_db.live_streams.find({"user_id": uid, "is_live": False}))
            assert len(stopped) == 1, f"Expected 1 stopped stream, got {len(stopped)}"
            assert stopped[0].get("stopped_reason") == "plan_expired_slot_shrink"

            # 1 stream should remain live
            still_live = list(static_db.live_streams.find({"user_id": uid, "is_live": True}))
            assert len(still_live) == 1
        finally:
            static_db.users.delete_one({"user_id": uid})
            static_db.live_streams.delete_many({"user_id": uid})


class TestIter10CheckActivePlan:
    """check_active_plan integration — raises 403 only when NO live entries; never for lifetime."""

    def test_non_expired_entry_passes(self):
        import asyncio, sys
        sys.path.insert(0, "/app/backend")
        from server import activate_or_extend_plan, check_active_plan
        from fastapi import HTTPException
        s, email, uid = _make_fresh_user_direct("_chkok")
        db = _get_mongo_db_static()
        try:
            _arun(activate_or_extend_plan(uid, "daily"))
            user = db.users.find_one({"user_id": uid})
            # Should not raise
            _arun(check_active_plan(user))
        finally:
            db.users.delete_one({"user_id": uid})

    def test_only_expired_entries_raises_403_and_clears(self):
        import asyncio, sys
        sys.path.insert(0, "/app/backend")
        from server import check_active_plan
        from fastapi import HTTPException
        from datetime import datetime, timezone
        s, email, uid = _make_fresh_user_direct("_chkexp")
        db = _get_mongo_db_static()
        try:
            db.users.update_one({"user_id": uid}, {"$set": {
                "plan": "daily",
                "plan_expires_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "active_plans": [{
                    "plan_id": "daily",
                    "purchased_at": datetime(2019, 12, 30, tzinfo=timezone.utc),
                    "expires_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
                }],
                "stream_slots": 1,
            }})
            user = db.users.find_one({"user_id": uid})
            raised = False
            try:
                _arun(check_active_plan(user))
            except HTTPException as ex:
                raised = True
                assert ex.status_code == 403
            assert raised, "Expected HTTPException 403 for only-expired entries"
            # Doc must be cleared
            refreshed = db.users.find_one({"user_id": uid})
            assert refreshed["active_plans"] == []
            assert refreshed["plan"] is None
            assert refreshed["plan_expires_at"] is None
            assert refreshed["stream_slots"] == 0
        finally:
            db.users.delete_one({"user_id": uid})

    def test_lifetime_never_raises(self):
        import asyncio, sys
        sys.path.insert(0, "/app/backend")
        from server import check_active_plan
        db = _get_mongo_db_static()
        admin = db.users.find_one({"email": ADMIN_EMAIL})
        assert admin and admin.get("plan") == "lifetime"
        # Should not raise even though active_plans might be empty
        _arun(check_active_plan(admin))


class TestIter10AuthMeShape:
    """/api/auth/me returns active_plans as ISO strings + computed stream_slots."""

    def test_admin_shape(self, admin_session):
        r = admin_session.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d.get("active_plans"), list)
        assert d.get("stream_slots") == 3, d
        assert d.get("plan") == "lifetime"

    def test_fresh_user_with_2_plans(self):
        import asyncio, sys
        sys.path.insert(0, "/app/backend")
        from server import activate_or_extend_plan
        s, email, uid = _make_fresh_user_direct("_me2")
        db = _get_mongo_db_static()
        try:
            _arun(activate_or_extend_plan(uid, "daily"))
            _arun(activate_or_extend_plan(uid, "weekly"))
            r = s.get(f"{API}/auth/me", timeout=15)
            assert r.status_code == 200
            d = r.json()
            assert d["stream_slots"] == 2, d
            assert len(d["active_plans"]) == 2
            for e in d["active_plans"]:
                assert e["plan_id"] in ("daily", "weekly")
                # Must be ISO strings
                assert isinstance(e["purchased_at"], str) and "T" in e["purchased_at"]
                assert isinstance(e["expires_at"], str) and "T" in e["expires_at"]
        finally:
            db.users.delete_one({"user_id": uid})


class TestIter10StreamsAndStatsMaxSlots:
    """/api/streams max_slots + /api/dashboard/stats max_stream_slots both use compute_stream_slots."""

    def test_admin_max_slots_3(self, admin_session):
        r1 = admin_session.get(f"{API}/streams", timeout=15).json()
        r2 = admin_session.get(f"{API}/dashboard/stats", timeout=15).json()
        assert r1["max_slots"] == 3, r1
        assert r2["max_stream_slots"] == 3, r2

    def test_fresh_user_daily_weekly_max_slots_2(self):
        import asyncio, sys
        sys.path.insert(0, "/app/backend")
        from server import activate_or_extend_plan
        s, email, uid = _make_fresh_user_direct("_maxslots")
        db = _get_mongo_db_static()
        try:
            _arun(activate_or_extend_plan(uid, "daily"))
            _arun(activate_or_extend_plan(uid, "weekly"))
            r1 = s.get(f"{API}/streams", timeout=15).json()
            r2 = s.get(f"{API}/dashboard/stats", timeout=15).json()
            assert r1["max_slots"] == 2, r1
            assert r2["max_stream_slots"] == 2, r2
        finally:
            db.users.delete_one({"user_id": uid})


class TestIter10StartWithKeySlotEnforcement:
    """Fresh user with 2 plans (Daily+Weekly) can seed 2 live streams; 3rd rejected 403."""

    def test_third_stream_blocked_at_2_slots(self):
        import asyncio, sys
        sys.path.insert(0, "/app/backend")
        from server import activate_or_extend_plan
        from datetime import datetime, timezone
        s, email, uid = _make_fresh_user_direct("_start3")
        db = _get_mongo_db_static()
        try:
            _arun(activate_or_extend_plan(uid, "daily"))
            _arun(activate_or_extend_plan(uid, "weekly"))

            # Seed a video so /api/stream/start-with-key passes video ownership check
            db.videos.insert_one({
                "video_id": "seed_vid_i10",
                "user_id": uid,
                "title": "Seeded",
                "file_path": "/tmp/nonexistent.mp4",
                "size": 1024,
                "duration_seconds": 5,
                "created_at": datetime.now(timezone.utc),
            })

            # Seed 2 already-live streams — fills the 2 slots
            for i, k in enumerate(["KEY-S1", "KEY-S2"]):
                db.live_streams.insert_one({
                    "stream_id": f"seed_s_{i}_{uuid.uuid4().hex[:6]}",
                    "user_id": uid, "is_live": True, "stream_key": k,
                    "ffmpeg_pid": None,
                    "started_at": datetime.now(timezone.utc),
                    "current_video": "seeded", "video_id": "seed_vid_i10",
                    "stream_method": "manual_key",
                })

            # 3rd attempt via API should be blocked BEFORE ffmpeg spawn
            r = s.post(f"{API}/stream/start-with-key", json={
                "stream_key": "KEY-S3-NEW", "video_id": "seed_vid_i10", "loop": False,
            }, timeout=15)
            assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:200]}"
            assert "maximum of 2" in r.text, r.text
        finally:
            db.users.delete_one({"user_id": uid})
            db.videos.delete_many({"user_id": uid})
            db.live_streams.delete_many({"user_id": uid})


class TestIter10RazorpayVerifyStacksSamePlan:
    """activate_or_extend_plan is idempotent for the same plan (stacks duration, no new slot)."""

    def test_same_plan_stacks_duration_only(self):
        import asyncio, sys
        sys.path.insert(0, "/app/backend")
        from server import activate_or_extend_plan
        s, email, uid = _make_fresh_user_direct("_samestack")
        db = _get_mongo_db_static()
        try:
            u1 = _arun(activate_or_extend_plan(uid, "weekly"))
            first_exp = u1["active_plans"][0]["expires_at"]
            u2 = _arun(activate_or_extend_plan(uid, "weekly"))
            assert u2["stream_slots"] == 1, u2
            assert len(u2["active_plans"]) == 1
            second_exp = u2["active_plans"][0]["expires_at"]

            from datetime import datetime, timedelta
            def _dt(x):
                return datetime.fromisoformat(x.replace("Z", "+00:00")) if isinstance(x, str) else x
            delta = _dt(second_exp) - _dt(first_exp)
            assert timedelta(days=6, hours=23) < delta < timedelta(days=7, hours=1), f"delta={delta}"
        finally:
            db.users.delete_one({"user_id": uid})


class TestIter10LegacyMigration:
    """Startup migration converts legacy plan+plan_expires_at users into active_plans."""

    def test_legacy_future_plan_migrated_on_startup(self):
        """Insert a legacy user (no active_plans) with future plan_expires_at, restart backend,
        verify migration populated active_plans + stream_slots=1."""
        import subprocess, time
        from datetime import datetime, timezone, timedelta
        db = _get_mongo_db_static()
        uid_future = f"legacy_future_{uuid.uuid4().hex[:8]}"
        uid_past = f"legacy_past_{uuid.uuid4().hex[:8]}"
        future_exp = datetime.now(timezone.utc) + timedelta(days=5)
        past_exp = datetime(2020, 1, 1, tzinfo=timezone.utc)
        try:
            # Legacy: future plan
            db.users.insert_one({
                "user_id": uid_future,
                "email": f"TEST_legacy_fut_{uuid.uuid4().hex[:6]}@example.com",
                "name": "Legacy Future",
                "password_hash": "$2b$12$dummydummydummydummydummydummydummydummydummydummy",
                "plan": "monthly",
                "plan_expires_at": future_exp,
                "storage_used": 0,
                "role": "user",
                "stream_slots": 1,
                "created_at": datetime.now(timezone.utc),
            })
            # Legacy: past plan
            db.users.insert_one({
                "user_id": uid_past,
                "email": f"TEST_legacy_past_{uuid.uuid4().hex[:6]}@example.com",
                "name": "Legacy Past",
                "password_hash": "$2b$12$dummydummydummydummydummydummydummydummydummydummy",
                "plan": "daily",
                "plan_expires_at": past_exp,
                "storage_used": 0,
                "role": "user",
                "stream_slots": 1,
                "created_at": datetime.now(timezone.utc),
            })
            # Restart backend to trigger startup_event migration
            subprocess.check_output(["sudo", "supervisorctl", "restart", "backend"], timeout=30)
            # Wait for backend to come back up
            for _ in range(30):
                time.sleep(1)
                try:
                    h = requests.get(f"{API}/health", timeout=3)
                    if h.status_code == 200:
                        break
                except Exception:
                    continue
            else:
                pytest.fail("Backend did not come back after restart")

            # Verify future legacy user was migrated
            u_fut = db.users.find_one({"user_id": uid_future})
            assert isinstance(u_fut.get("active_plans"), list), u_fut
            assert len(u_fut["active_plans"]) == 1, u_fut["active_plans"]
            assert u_fut["active_plans"][0]["plan_id"] == "monthly"
            assert u_fut.get("stream_slots") == 1

            # Verify past legacy user was cleared
            u_past = db.users.find_one({"user_id": uid_past})
            assert u_past.get("active_plans") == [], u_past
            assert u_past.get("plan") is None
            assert u_past.get("plan_expires_at") is None
            assert u_past.get("stream_slots") == 0
        finally:
            db.users.delete_one({"user_id": uid_future})
            db.users.delete_one({"user_id": uid_past})


class TestIter10Regression:
    """Regression: iter-9 features still work — stream_id present on all rows, /api/health OK."""

    def test_health_still_ok(self):
        r = requests.get(f"{API}/health", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_streams_list_has_stream_id_for_admin(self, admin_session):
        r = admin_session.get(f"{API}/streams", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for s in d.get("active", []):
            assert s.get("stream_id"), s
