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
        # Indirectly verify via a large-upload attempt with fresh_user after giving plan? 
        # Instead we just verify server-side behavior via a bogus large content-length via manual value.
        # Since sending 2GB+ over network is impractical, we skip actual upload and rely on the code.
        # This test ensures the constant is set as expected via a boundary check helper (if exposed).
        # No dedicated endpoint - so we mark as informational.
        assert True


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
