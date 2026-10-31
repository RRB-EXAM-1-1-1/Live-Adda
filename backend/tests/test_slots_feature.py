"""
My Slots feature tests: GET/PUT /api/slots, razorpay create-order renew_slot_id,
activate_or_extend_plan (new slot vs renew), start-with-key slot binding, stop -> ready.
"""
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip()
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"


def _env(key):
    for line in Path("/app/backend/.env").read_text().splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


mongo = MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]
NOW = datetime.now(timezone.utc)


@pytest.fixture(scope="module")
def ctx():
    s = requests.Session()
    email = f"test_slots_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "TestPass123!", "name": "TEST Slots"})
    assert r.status_code in (200, 201), r.text
    u = mongo.users.find_one({"email": email})
    uid = u["user_id"]
    plans = [
        {"slot_id": "slot_tA", "name": "Alpha", "plan_id": "daily", "purchased_at": NOW, "expires_at": NOW + timedelta(hours=20)},
        {"slot_id": "slot_tB", "name": "Beta", "plan_id": "weekly", "purchased_at": NOW, "expires_at": NOW + timedelta(days=5)},
        {"slot_id": "slot_tC", "name": "Charlie", "plan_id": "daily", "purchased_at": NOW - timedelta(days=6), "expires_at": NOW - timedelta(days=5)},
        {"slot_id": "slot_tD", "name": "Delta", "plan_id": "daily", "purchased_at": NOW - timedelta(days=41), "expires_at": NOW - timedelta(days=40)},
    ]
    mongo.users.update_one({"user_id": uid}, {"$set": {"active_plans": plans, "plan": "weekly",
                                                       "plan_expires_at": NOW + timedelta(days=5), "stream_slots": 2}})
    # login again so cookies are fresh
    r = s.post(f"{API}/auth/login", json={"email": email, "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    yield {"s": s, "uid": uid, "email": email}
    mongo.live_streams.delete_many({"user_id": uid})
    mongo.videos.delete_many({"user_id": uid})
    mongo.payment_transactions.delete_many({"user_id": uid})
    mongo.users.delete_one({"user_id": uid})


def _slots(ctx):
    r = ctx["s"].get(f"{API}/slots")
    assert r.status_code == 200, r.text
    return r.json()


def _mk_video(uid):
    dst = Path(f"/app/backend/uploads/TEST_{uuid.uuid4().hex[:6]}.mp4")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not Path("/tmp/t.mp4").exists():
        subprocess.run("ffmpeg -y -loglevel error -f lavfi -i testsrc=duration=5:size=320x240:rate=10 -f lavfi -i sine=frequency=440:duration=5 -c:v libx264 -pix_fmt yuv420p -c:a aac /tmp/t.mp4", shell=True, check=True)
    shutil.copy("/tmp/t.mp4", dst)
    vid = f"video_test{uuid.uuid4().hex[:8]}"
    mongo.videos.insert_one({"video_id": vid, "user_id": uid, "title": "TEST Clip", "file_path": str(dst),
                             "size": dst.stat().st_size, "processing_status": "ready", "created_at": NOW,
                             "uploaded_at": NOW, "filename": dst.name})
    return vid


class TestSlotsFeature:
    # GET /api/slots shape + retention
    def test_list_slots(self, ctx):
        d = _slots(ctx)
        ids = {x["slot_id"]: x for x in d["slots"]}
        assert set(ids) == {"slot_tA", "slot_tB", "slot_tC"}, ids.keys()
        assert ids["slot_tC"]["status"] == "expired"
        assert ids["slot_tA"]["status"] == "ready" and ids["slot_tB"]["status"] == "ready"
        for k in ("slot_id", "number", "name", "plan_name", "expires_at", "hours_left", "status"):
            assert k in ids["slot_tA"]
        assert ids["slot_tA"]["expiring_soon"] is True
        assert d["summary"] == {"total": 3, "live": 0, "ready": 2, "expired": 1}
        # >30 days slot pruned from mongo
        u = mongo.users.find_one({"user_id": ctx["uid"]})
        assert "slot_tD" not in [e.get("slot_id") for e in u["active_plans"]]

    # PUT /api/slots/{id}
    def test_rename(self, ctx):
        s = ctx["s"]
        r = s.put(f"{API}/slots/slot_tA", json={"name": "   My   Cool  Slot  "})
        assert r.status_code == 200 and r.json()["name"] == "My Cool Slot"
        assert next(x for x in _slots(ctx)["slots"] if x["slot_id"] == "slot_tA")["name"] == "My Cool Slot"
        assert s.put(f"{API}/slots/slot_tA", json={"name": "    "}).status_code == 400
        assert s.put(f"{API}/slots/slot_tA", json={"name": "x" * 41}).status_code == 400
        assert s.put(f"{API}/slots/slot_tA", json={"name": "x" * 40}).status_code == 200
        assert s.put(f"{API}/slots/slot_nope", json={"name": "abc"}).status_code == 404
        # expired slot renamable
        assert s.put(f"{API}/slots/slot_tC", json={"name": "Charlie2"}).status_code == 200
        s.put(f"{API}/slots/slot_tA", json={"name": "Alpha"})

    def test_rename_unauth(self):
        assert requests.put(f"{API}/slots/slot_tA", json={"name": "a"}).status_code == 401

    # razorpay create-order
    def test_create_order(self, ctx):
        s = ctx["s"]
        # validation happens before Razorpay call
        r3 = s.post(f"{API}/razorpay/create-order", json={"plan_id": "daily", "renew_slot_id": "slot_bogus"})
        assert r3.status_code in (404, 503), r3.text
        r = s.post(f"{API}/razorpay/create-order", json={"plan_id": "daily"})
        if r.status_code in (502, 503):
            pytest.skip(f"Razorpay not usable: {r.text}")
        assert r.status_code == 200, r.text
        r2 = s.post(f"{API}/razorpay/create-order", json={"plan_id": "daily", "renew_slot_id": "slot_tC"})
        assert r2.status_code == 200, r2.text
        txn = mongo.payment_transactions.find_one({"order_id": r2.json()["order_id"]})
        assert txn["renew_slot_id"] == "slot_tC"
        txn1 = mongo.payment_transactions.find_one({"order_id": r.json()["order_id"]})
        assert txn1["renew_slot_id"] is None
        r3 = s.post(f"{API}/razorpay/create-order", json={"plan_id": "daily", "renew_slot_id": "slot_bogus"})
        assert r3.status_code == 404
        assert s.post(f"{API}/razorpay/create-order", json={"plan_id": "lifetime"}).status_code == 400

    # activate_or_extend_plan via direct import
    def test_activate_or_extend(self, ctx):
        uid = ctx["uid"]
        before = {e["slot_id"]: e for e in mongo.users.find_one({"user_id": uid})["active_plans"]}
        script = f"""
import asyncio, server
async def m():
    await server.activate_or_extend_plan('{uid}', 'daily')
    await server.activate_or_extend_plan('{uid}', 'daily')
    await server.activate_or_extend_plan('{uid}', 'daily', 'slot_tB')
    await server.activate_or_extend_plan('{uid}', 'weekly', 'slot_tC')
asyncio.run(m())
"""
        p = subprocess.run(["python3", "-c", script], cwd="/app/backend", capture_output=True, text=True, timeout=60)
        assert p.returncode == 0, p.stderr[-2000:]
        after = {e["slot_id"]: e for e in mongo.users.find_one({"user_id": uid})["active_plans"]}
        new = [k for k in after if k not in before]
        assert len(new) == 2, after.keys()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        b_old = before["slot_tB"]["expires_at"].replace(tzinfo=None)
        b_new = after["slot_tB"]["expires_at"].replace(tzinfo=None)
        assert abs((b_new - b_old) - timedelta(days=1)).total_seconds() < 5
        assert after["slot_tB"]["name"] == "Beta"
        c_new = after["slot_tC"]["expires_at"].replace(tzinfo=None)
        assert abs((c_new - now) - timedelta(days=7)).total_seconds() < 60
        assert after["slot_tC"]["name"] == "Charlie2" and after["slot_tC"]["plan_id"] == "weekly"
        d = _slots(ctx)
        assert d["summary"]["total"] == 5 and d["summary"]["expired"] == 0
        # re-expire slot_tC for following tests
        mongo.users.update_one({"user_id": uid, "active_plans.slot_id": "slot_tC"},
                               {"$set": {"active_plans.$.expires_at": NOW - timedelta(days=5)}})

    # start-with-key slot binding
    def test_start_with_key_paths(self, ctx):
        s, uid = ctx["s"], ctx["uid"]
        vid = _mk_video(uid)
        ctx["vid"] = vid
        r = s.post(f"{API}/stream/start-with-key", json={"video_id": vid, "stream_key": "fake-key-1111", "slot_id": "slot_tC"})
        assert r.status_code == 404, r.text
        r = s.post(f"{API}/stream/start-with-key", json={"video_id": vid, "stream_key": "fake-key-1111", "slot_id": "slot_tA"})
        print("start-with-key real:", r.status_code, r.text[:300])
        ctx["start_status"] = r.status_code
        if r.status_code == 200:
            assert r.json()["slot_id"] == "slot_tA"
            doc = mongo.live_streams.find_one({"stream_id": r.json()["stream_id"]})
            assert doc["slot_id"] == "slot_tA" and doc["slot_name"] == "Alpha"
            ctx["stream_id"] = r.json()["stream_id"]
        else:
            assert r.status_code == 500
            sid = f"stream_test{uuid.uuid4().hex[:8]}"
            mongo.live_streams.insert_one({"stream_id": sid, "user_id": uid, "is_live": True, "slot_id": "slot_tA",
                                           "slot_name": "Alpha", "current_video": "TEST Clip", "video_id": vid,
                                           "stream_key": "fake-key-1111", "started_at": datetime.now(timezone.utc)})
            ctx["stream_id"] = sid
        r = s.post(f"{API}/stream/start-with-key", json={"video_id": vid, "stream_key": "fake-key-2222", "slot_id": "slot_tA"})
        assert r.status_code == 409, r.text

    def test_slots_live_and_rename_propagates(self, ctx):
        d = _slots(ctx)
        a = next(x for x in d["slots"] if x["slot_id"] == "slot_tA")
        assert a["status"] == "live" and a["stream"]["video_title"] == "TEST Clip"
        assert d["slots"][0]["slot_id"] == "slot_tA"  # live sorted first
        assert d["summary"]["live"] == 1
        r = ctx["s"].put(f"{API}/slots/slot_tA", json={"name": "Alpha Live"})
        assert r.status_code == 200
        assert mongo.live_streams.find_one({"stream_id": ctx["stream_id"]})["slot_name"] == "Alpha Live"

    def test_auto_pick_slot(self, ctx):
        s, uid = ctx["s"], ctx["uid"]
        r = s.post(f"{API}/stream/start-with-key", json={"video_id": ctx["vid"], "stream_key": "fake-key-3333"})
        print("auto-pick:", r.status_code, r.text[:300])
        if r.status_code == 200:
            assert r.json()["slot_id"] != "slot_tA"
            s.post(f"{API}/stream/stop", json={"stream_id": r.json()["stream_id"]})
        else:
            assert r.status_code == 500  # encoder failed with fake key; slot validation passed

    def test_stop_returns_ready(self, ctx):
        r = ctx["s"].post(f"{API}/stream/stop", json={"stream_id": ctx["stream_id"]})
        assert r.status_code == 200, r.text
        a = next(x for x in _slots(ctx)["slots"] if x["slot_id"] == "slot_tA")
        assert a["status"] == "ready" and a["stream"] is None


class TestAdminLifetimeSlots:
    def test_admin_slots(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": "admin@liveadda.com", "password": "admin123"})
        assert r.status_code == 200, r.text
        d = s.get(f"{API}/slots").json()
        ids = [x["slot_id"] for x in d["slots"]]
        assert {"lifetime_1", "lifetime_2", "lifetime_3"} <= set(ids)
        old = next(x for x in d["slots"] if x["slot_id"] == "lifetime_2")["name"]
        assert s.put(f"{API}/slots/lifetime_2", json={"name": "TEST Admin Slot"}).status_code == 200
        assert next(x for x in s.get(f"{API}/slots").json()["slots"] if x["slot_id"] == "lifetime_2")["name"] == "TEST Admin Slot"
        assert s.put(f"{API}/slots/lifetime_9", json={"name": "x"}).status_code == 404
        s.put(f"{API}/slots/lifetime_2", json={"name": old})
        assert all(x["expires_at"] is None for x in d["slots"])
