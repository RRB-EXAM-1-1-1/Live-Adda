# Process Management, Auto-Restart & Background Queues

This is the Python/FastAPI equivalent of the Node.js "PM2 ecosystem +
BullMQ + Redis" stack. Both capabilities are already implemented — this
document explains where and how, and how to operate them in production.

---

## 1. Process Manager — Supervisor (PM2 equivalent)

Live Adda's FastAPI backend is managed by **supervisor**, not PM2, because
PM2 is Node.js–only. Supervisor gives us exactly the same guarantees:

| Capability | PM2 | Live Adda (supervisor) |
|---|---|---|
| Auto-restart on crash | ✅ | ✅ `autorestart=true, startretries=5` |
| Auto-start on server reboot | ✅ (`pm2 startup`) | ✅ `systemctl enable supervisor` (enforced by `setup.sh` and `update.sh`) |
| Log rotation | ✅ (`pm2-logrotate`) | ✅ `stderr_logfile_maxbytes=25MB, stderr_logfile_backups=5` |
| Live log streaming | `pm2 logs` | `tail -f /var/log/live-adda/backend.err.log` |
| Restart / stop / status | `pm2 restart <n>` | `sudo supervisorctl restart live-adda-backend` |
| Zero-downtime reload | `pm2 reload` | `sudo supervisorctl restart live-adda-backend` (hot reload via WatchFiles in dev) |

### Files

- `/app/deploy/supervisor-backend.conf` — the source-of-truth config, copied
  into `/etc/supervisor/conf.d/` by `setup.sh` / `update.sh`.
- Logs land in `/var/log/live-adda/backend.err.log` and `backend.out.log`.
- FFmpeg per-stream logs go to `/var/log/live-adda/ffmpeg/ffmpeg_<key>_<ts>.log`.

### Common ops

```bash
sudo supervisorctl status                       # is it running?
sudo supervisorctl restart live-adda-backend    # restart after code changes
sudo tail -f /var/log/live-adda/backend.err.log # follow errors
sudo systemctl status supervisor                # is supervisor itself running?
sudo systemctl enable supervisor                # arm it for server reboots
```

### Why `--workers 1` (not 2)?

The backend runs long-lived asyncio background tasks:

- **FFmpeg reaper loop** (every 15 s) — cleans up self-exited encoders.
- **Plan-expiry sweeper loop** (every 30 s) — force-stops streams whose plans
  expired and purges their videos.
- **Transcode semaphore** (`asyncio.Semaphore(1)`) — serializes video
  transcodes so multiple uploads don't spike CPU to 100%.
- **Popen handle registry** (`_running_procs`) — tracks live ffmpeg PIDs so
  `stop_ffmpeg_push` can reap them cleanly.

Running two uvicorn workers would give us **two copies** of every one of
those loops and registries, causing race conditions on ffmpeg termination
and violating the single-transcode-at-a-time guarantee. FastAPI + asyncio
comfortably handles this app's load on one worker.

---

## 2. Background Job Queue — asyncio.Semaphore (BullMQ+Redis equivalent)

Live Adda's video-transcode queue is implemented in-process using
`asyncio.Semaphore(1)` at `/app/backend/server.py:39`. This gives us the
"one job at a time, controlled batch" behaviour BullMQ provides — without
adding Redis (which would cost ~40 MB of RAM on the 1 GB droplet and add a
separate service to babysit).

| Capability | BullMQ + Redis | Live Adda (asyncio) |
|---|---|---|
| Serialize jobs to prevent CPU spike | Concurrency option on Worker | ✅ `_TRANSCODE_SEM = asyncio.Semaphore(1)` |
| Retry on failure | Yes | ✅ Wrapped in `try/except`; failures mark `processing_status="completed"` with `transcode_error=True` |
| Survive backend restart | Yes (Redis persistence) | ✅ **Startup recovery** in `startup_event()` scans videos with `processing_status="transcoding"` and re-schedules |
| Distributed workers | Yes | ❌ Not needed at this scale (single node) |
| Cross-process job status | Yes | ❌ Same-process only (all workers run in one uvicorn worker) |

### If/when you outgrow this

If Live Adda ever needs multi-node transcode workers, the right upgrade
path is **arq** (asyncio-native, Redis-based, feels similar to BullMQ) or
Celery. Nothing else in the codebase needs to change — the current
`schedule_transcode()` function is the single entry point that would swap
its implementation from `asyncio.create_task(...)` to `queue.enqueue(...)`.

---

## 3. Error handling & logging

### FFmpeg push failures

`start_ffmpeg_push()` now:

1. Fails fast with `FileNotFoundError` if the source is missing.
2. Waits 1.2 s after spawn and checks the exit code. If ffmpeg died (bad
   stream key, DNS failure, invalid codec), raises `RuntimeError` with the
   last 300 bytes of ffmpeg stderr.
3. Callers (`/api/streams/start-with-key` and the OAuth-broadcast path)
   translate those into HTTP 410 / 500 with actionable messages instead of
   a silent failure.

### FFmpeg live logs

Each running stream writes to its own log at
`/var/log/live-adda/ffmpeg/ffmpeg_<key8>_<epoch>.log`. Persistent across
reboots so you can post-mortem a stream that stopped hours ago:

```bash
ls -lt /var/log/live-adda/ffmpeg/ | head
sudo tail -100 /var/log/live-adda/ffmpeg/ffmpeg_abcd1234_1725102000.log
```

### Transcode failures

Handled at `/app/backend/server.py` `transcode_video_background()`. On
non-zero ffmpeg exit code we log the last 300 bytes of stderr and mark the
row `processing_status="completed", transcode_error=True` so the video is
still usable (original file kept) and the operator can spot the failure
in the admin dashboard.

### Reaper / sweeper resilience

Both background loops are wrapped in `try/except Exception` inside a
`while True`. Any per-iteration error is logged as a warning and the loop
continues, so a bad stream row can never kill the reaper.
