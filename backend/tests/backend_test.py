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
            first, second = asyncio.run(run())
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
        result = asyncio.run(activate_plan_from_transaction("cs_unknown_session", "unpaid"))
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
        r = admin_session.post(f"{API}/razorpay/create-order",
                               json={"plan_id": plan_id}, timeout=30)
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
        r = s.post(f"{API}/razorpay/create-order", json={"plan_id": "daily"}, timeout=30)
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
        r = s.post(f"{API}/razorpay/create-order", json={"plan_id": "weekly"}, timeout=30)
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
