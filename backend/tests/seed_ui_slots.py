# Seed UI test users for My Slots page: one with ready/live/expired slots, one with zero slots
import os, uuid, shutil, requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from pymongo import MongoClient

env = dict(l.split("=", 1) for l in Path("/app/backend/.env").read_text().splitlines() if "=" in l)
db = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
BASE = [l.split("=", 1)[1] for l in Path("/app/frontend/.env").read_text().splitlines() if l.startswith("REACT_APP_BACKEND_URL")][0].rstrip("/")
NOW = datetime.now(timezone.utc)

def reg(email):
    db.users.delete_one({"email": email})
    r = requests.post(f"{BASE}/api/auth/register", json={"email": email, "password": "TestPass123!", "name": "TEST UI"})
    assert r.status_code in (200, 201), r.text
    return db.users.find_one({"email": email})["user_id"]

uid = reg("test_ui_slots@example.com")
db.live_streams.delete_many({"user_id": uid}); db.videos.delete_many({"user_id": uid})
db.users.update_one({"user_id": uid}, {"$set": {"plan": "weekly", "plan_expires_at": NOW + timedelta(days=5), "stream_slots": 2, "active_plans": [
    {"slot_id": "slot_uiready", "name": "Ready One", "plan_id": "daily", "purchased_at": NOW, "expires_at": NOW + timedelta(hours=20)},
    {"slot_id": "slot_uilive", "name": "Live One", "plan_id": "weekly", "purchased_at": NOW, "expires_at": NOW + timedelta(days=5)},
    {"slot_id": "slot_uiexp", "name": "Expired One", "plan_id": "daily", "purchased_at": NOW - timedelta(days=3), "expires_at": NOW - timedelta(days=2)},
]}})
for i in (1, 2):
    dst = Path(f"/app/backend/uploads/TEST_ui{i}.mp4"); shutil.copy("/tmp/t.mp4", dst)
    db.videos.insert_one({"video_id": f"video_ui{i}", "user_id": uid, "title": f"UI Clip {i}", "file_path": str(dst), "size": dst.stat().st_size,
                          "processing_status": "ready", "created_at": NOW, "uploaded_at": NOW, "filename": dst.name})
db.live_streams.insert_one({"stream_id": "stream_uilive", "user_id": uid, "is_live": True, "slot_id": "slot_uilive", "slot_name": "Live One",
                            "current_video": "UI Clip 2", "video_id": "video_ui2", "stream_key": "fake-ui", "started_at": NOW})
reg("test_ui_empty@example.com")
print("seeded", uid)
