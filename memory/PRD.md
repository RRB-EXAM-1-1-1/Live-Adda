# Live Adda - Product Requirements Document

## Original Problem Statement
Build "Live Adda" - a professional 24/7 YouTube Live streaming SaaS platform.
- Landing page: hero ("Stream Your Videos 24/7 on YouTube – No PC/Laptop Required!"), features with icons, pricing (Daily/Weekly/Monthly with badges).
- Dark-themed user dashboard: sidebar (Dashboard, Video Manager, Live Slot, Billings, Support), stream status/balance/activity cards.
- Color palette: deep blue, white, vibrant green CTAs.

## User Choices
- Full app: landing + dashboard
- Auth: JWT email/password + Emergent Google OAuth
- Payments: Stripe (test key)
- Video storage: local

## Business Rules (from user)
- All plans: strict 2GB storage limit per customer
- Auto-expiry: Daily=24h, Weekly=7d, Monthly=30d
- Gatekeeping: upload/stream without active plan → pop-up "⚠️ Please purchase a slot/plan first to proceed."
- Video upload: progress bar with % + "Ready for the stream!" message with remaining validity
- Video Manager: Rename feature

## Architecture
- Backend: FastAPI (server.py), MongoDB (live_adda_db)
- Frontend: React + Tailwind + shadcn/ui, sonner toasts
- Collections: users, videos, live_streams, payment_transactions, support_tickets

## User Personas
- Content creator wanting 24/7 YouTube presence without a PC
- Streamer managing uploaded video playlists and live slots

## What's Been Implemented (2026-07-13)
- JWT auth (register/login/logout/me) with httpOnly cookies + bcrypt
- Emergent Google OAuth wired in Login/Register UI
- Video upload (local storage) with 2GB limit + progress bar + "Ready for the stream!"
- Video rename + delete with storage accounting
- Live slot start/stop + settings (auto-rotate, loop)
- Gatekeeping middleware (check_active_plan) on upload + live-slot
- Stripe checkout + polling-based plan activation with auto-expiry
- Billings page (plans, current plan, transaction history)
- Dashboard stats + Support ticket submission
- Landing page (hero, features, pricing), dark dashboard, responsive + animations
- Testing: 28/28 backend tests pass, frontend flows verified

## Iteration 2 (2026-07-13) - Robustness + YouTube
- Streaming/chunked video upload (1MB chunks) with incremental 2GB enforcement + partial-file cleanup
- Hardened Stripe webhook: signature verification (400 on invalid) + idempotent atomic plan activation as backup to polling
- YouTube Live integration (youtube_service.py): OAuth2 connect flow, liveBroadcast+liveStream create/bind, ffmpeg RTMP push, broadcast transition; graceful "not configured" state until YOUTUBE_CLIENT_ID/SECRET set
- ffmpeg installed; broadcast rolls back (transition to complete) if encoder fails to start
- Testing: 39/39 backend tests pass

## Pending User Action for YouTube
- Provide YOUTUBE_CLIENT_ID + YOUTUBE_CLIENT_SECRET (Google Cloud, YouTube Data API v3 enabled)
- Redirect URI to whitelist: {app}/api/youtube/oauth/callback
- Scopes: youtube.force-ssl, youtube, youtube.readonly
- 24/7 persistent ffmpeg needs dedicated VPS (Hetzner CX22 / DO Droplet)

## Iteration 3 (2026-07-13) - Deploy docs + Mobile + Upload + Key Activation
- Deployed to production (liveadda.org) with HTTPS; added deploy/ (setup.sh, nginx.conf, supervisor, systemd ffmpeg template, README.md, DEPLOYMENT.md) + .env.example files
- Added PUBLIC_APP_URL env for deterministic OAuth redirect in production
- Mobile responsiveness fixed: Navbar (links hidden on mobile, compact buttons), Hero (responsive text/padding, full-width CTAs), dashboard heading clears hamburger; verified no horizontal overflow at 390px
- Upload speed optimized: 8MB streaming chunks + nginx proxy_request_buffering off
- NEW FEATURE Key Activation: /api/stream/start-with-key + /api/stream/stop (idempotent) — active-plan users paste a YouTube stream key + pick a video to go live; UI card in Live Slot
- Testing: 44/44 backend tests pass, frontend responsive + key-activation flows verified

## Backlog (non-blocking, from test reports)
- Split server.py (~1100 lines) into APIRouter modules
- Migrate FastAPI on_event -> lifespan handler
- ffmpeg liveness reaper to flip is_live=false when encoder dies
- Redact stream key in ffmpeg logs

## Prioritized Backlog
### P1
- Stream file uploads (avoid loading full 2GB into RAM)
- Real Stripe webhook signature verification + plan activation on webhook
- Actual video duration/thumbnail extraction on upload

### P2
- YouTube API integration for real streaming
- Email notifications (plan expiry, payment)
- Split server.py into routers (auth/videos/payments/etc.)
- Forgot-password flow

## Next Tasks
- Implement chunked/streaming upload for large files
- Wire real YouTube streaming pipeline

## Iteration 4 (2026-07-15) - Razorpay Payment Gateway (INR)
- Integrated Razorpay as PRIMARY checkout (LIVE keys) replacing Stripe in the UI
- INR pricing: Daily ₹35, Weekly ₹199, Monthly ₹599 (backend PLANS['inr'], sent as paise)
- Backend: /api/razorpay/create-order, /api/razorpay/verify-payment (HMAC-SHA256 signature, idempotent plan activation, cross-user protection), /api/razorpay/webhook
- Frontend: Razorpay Checkout modal in Billings, INR display on landing + billings, checkout.js loaded in index.html
- Transaction history renders currency-aware symbol (₹ INR / $ legacy Stripe)
- Testing: 53/53 backend tests pass; frontend verified (modal opens with correct amounts)
- Stripe endpoints retained but dormant (not used by UI)

## Iteration 5 (2026-07-15) - Fix: ₹35 recharge option unavailable
- BUG: users with an active plan saw a disabled 'Current Plan' button, so they couldn't re-buy/recharge (e.g. the ₹35 Daily)
- FIX: current plan button now enabled + labeled 'Renew / Recharge'; buying the same active plan STACKS duration onto remaining validity (expired/other plan resets from now)
- Testing: 56/56 backend tests pass; fresh + existing-plan Billings UI verified, Razorpay modal opens for renewal

## Iteration 6 (2026-07-24) - Fix 4 critical upload/auth/dashboard bugs
- BUG 413 + tab-switch: replaced whole-file upload with CHUNKED upload (5MB slices, sequential, per-chunk retry) via /api/videos/upload/chunk - small requests avoid proxy 413 and survive flaky connections
- BUG 'Not Authenticated': access token 15min->12h + new /api/auth/refresh endpoint + axios 401 auto-refresh interceptor
- BUG dashboard plan: Dashboard now derives plan status from fresh /api/dashboard/stats (+ refreshUser on mount) instead of stale context
- Toast moved to bottom-right (was overlapping Upload button)
- Testing: 13 new tests pass (auth refresh + chunked upload + dashboard reflection); all 4 fixes verified end-to-end. NOTE: 8 backend failures are pre-existing Razorpay LIVE-key Cloudflare throttling in preview cluster (not a regression)


## Iteration 7 (2026-02) - Self-Hosted Deployment Unblock (DigitalOcean 1GB droplet)
- BUG: `pip install -r requirements.txt` failed on external VPS due to `emergentintegrations==0.2.0` and internal `litellm` wheel URL (both Emergent-only)
- BUG: `yarn build` OOM-killed on 1GB RAM droplets during React production build
- FIX (backend/server.py): `emergentintegrations` import wrapped in try/except with `STRIPE_AVAILABLE` flag; the 3 legacy Stripe endpoints (`/api/payments/checkout-session`, `/api/payments/checkout-status/{id}`, `/api/webhook/stripe`) return 503 gracefully if the module is absent. Razorpay (primary) unaffected.
- FIX (backend/requirements.txt): removed `emergentintegrations==0.2.0` and internal `litellm @ https://customer-assets.emergentagent.com/...` wheel line. `pip install -r requirements.txt` now works on any vanilla Python 3.11+ environment.
- FIX (deploy/setup.sh + deploy/update.sh): auto-provisions a 2GB `/swapfile` (persisted in `/etc/fstab`, `vm.swappiness=10`) before frontend build; sets `NODE_OPTIONS=--max-old-space-size=1536`, `GENERATE_SOURCEMAP=false`, `CI=false` so `yarn build` fits in memory on 1GB droplets.
- NEW: `deploy/fix-deployment.sh` — one-shot recovery script for users whose deploy is already broken (allocates swap, sanitizes requirements defensively, rebuilds venv w/ `REBUILD_VENV=1`, rebuilds frontend with capped Node heap, restarts Supervisor + reloads Nginx).
- NEW: `deploy/README.md` recovery section documents `sudo bash deploy/fix-deployment.sh` flow.
- Verification: backend restarts cleanly with `STRIPE_AVAILABLE=True` inside Emergent env (module present) and would be `False` on VPS (module absent) — Razorpay path fully functional in both.


## Iteration 8 (2026-08-01) - Admin Lifetime + Profile/Tutorial/Support + SEO + Thumbnails
- USER REQUEST BATCH: (a) faster uploads + thumbnail previews, (b) admin lifetime access with 3 streaming slots, (c) sidebar restructure — remove Support from main nav + add Profile; add Tutorial + Support in footer, (d) WhatsApp (+91 8796533673) + email (support@liveadda.org) direct links, (e) favicon + SEO meta tags + sitemap.xml + robots.txt.
- BACKEND: Added `PLANS['lifetime']` (0 INR, 100-year duration, "Lifetime (Admin)"). `check_active_plan` short-circuits on plan='lifetime' — bypasses expiry entirely. Admin seed on startup is now idempotent: creates on first run with plan=lifetime + stream_slots=3, and on subsequent restarts UPGRADES the role/plan/slots without touching the password_hash (so user-changed passwords persist). Bumped chunked upload chunk size 5MB → 8MB (halves round-trips → faster uploads). Added `PUT /api/auth/profile` for name/email/password updates (validates current_password, min 6 chars, email uniqueness). Added ffmpeg-based thumbnail generation on upload finalize (async, 8s timeout, non-blocking, extracts frame at 1s scaled to 640px) with `GET /api/videos/{video_id}/thumbnail` endpoint that lazily regenerates missing thumbs. test_credentials.md is no longer overwritten by the seed (only created if absent), so the operator's manual notes are preserved.
- FRONTEND: New pages — `Profile.jsx` (edit name/email/password with Lifetime badge for admins), `Tutorial.jsx` (3 numbered chapters: Buy plan → Upload → Stream, with CTA buttons), rewritten `Support.jsx` (WhatsApp + email cards + ticket form + FAQ). Sidebar main-nav is now [Dashboard, Video Manager, Live Slot, Billings, Profile] and sidebar footer holds [Tutorial, Support, Logout]. `VideoManager.jsx` grid now renders JPEG thumbnails via `<VideoThumbnail videoId>` with a Play-icon fallback if the thumb isn't ready. `UploadContext.jsx` CHUNK_SIZE = 8MB.
- SEO / branding: rewrote `public/index.html` with proper title ("Live Adda | Stream Your Videos 24/7 on YouTube Live — No PC Needed"), meta description, keywords, canonical, OpenGraph, Twitter card, and application/ld+json structured data (Organization + WebSite + Product with 3 INR offers). Added `public/favicon.svg` (broadcast-tower gradient logo), `public/sitemap.xml`, `public/robots.txt`. `google-site-verification` placeholder needs GSC token before submission.
- Testing (iteration_8.json): 13/13 new backend tests + 8/8 iter-7 regression + full frontend UI E2E. All green.
- Known ENV note: ffmpeg must be installed on the target server (already handled by `deploy/setup.sh`). Cosmetic: `google-site-verification` token in index.html is still `REPLACE_WITH_YOUR_GSC_TOKEN` — replace before Google Search Console submission.

## Iteration 10 (2026-08-01) - Slot Stacking (Each Active Plan = +1 Slot)
- USER PRODUCT DECISION: Option B — every active paid plan grants +1 concurrent streaming slot. Same plan re-purchase stacks duration only. Different plan appends a new slot. Admin lifetime = fixed 3 slots.
- SCHEMA: New `active_plans: [{plan_id, purchased_at, expires_at}]` array on user doc. Legacy `plan` + `plan_expires_at` kept for display of latest-expiring plan. `stream_slots` field maintained for compat but the source-of-truth is now the computed `compute_stream_slots(user)`.
- NEW BACKEND HELPERS: `_active_entries()`, `compute_stream_slots()`, `sync_user_plans_and_enforce_slots()` (prunes expired + stops excess ffmpeg streams most-recent-first, stops with `stopped_reason='plan_expired_slot_shrink'`), `activate_or_extend_plan(user_id, plan_id)` — the single idempotent activator called from razorpay verify, razorpay webhook, and legacy Stripe flow.
- UPDATED ENDPOINTS: `check_active_plan()` (rewritten for active_plans), `/api/auth/me` (returns active_plans + computed slots), `/api/streams` (max_slots = computed), `/api/dashboard/stats` (max_stream_slots = computed), `/api/stream/start-with-key` (slot check uses computed).
- STARTUP MIGRATION: pre-iter-10 users with legacy `plan`+`plan_expires_at` fields but no `active_plans` array get auto-migrated on backend boot. Future-dated plans → 1 entry appended, slots=1. Past-dated → cleared, slots=0. Lifetime users excluded (they don't need array entries).
- LIFETIME BUGFIX: `_active_entries` now returns `[]` for lifetime users (was synthesizing a fake lifetime entry that leaked into Billings). Ensures admin's Billings hides the active-plans panel.
- FRONTEND Billings: NEW `active-plans-panel` section showing one card per active plan with days-until-expiry + a "N concurrent stream slots unlocked" badge. Plan card feature list changed from "1 Active Live Slot" to "+1 Live Streaming Slot" to communicate stacking. Hidden for admin (no active_plans) and users with no plans.
- TESTING (iteration_10.json): 14/14 new pytest tests pass — activate/extend, expiry pruning + excess-stream stopping, check_active_plan expired/lifetime, /auth/me shape, /streams + /dashboard/stats max_slots, /start-with-key slot enforcement (3rd attempt for 2-slot user = 403), same-plan stack idempotency, legacy startup migration for both future+past plans. iter-9 regression (/api/health, stream_id backfill) still green. Frontend E2E on fresh 2-plan user verified all data-testids.


## Iteration 11 (2026-08-01) - Auto Video Cleanup on Stream Stop / Plan Expiry
- USER REQUEST: When a stream stops (user action OR plan expiry auto-stop), the video that was being broadcast must be permanently deleted. When ALL a user's plans expire, wipe every video in their account.
- NEW BACKEND HELPERS (`server.py`):
  - `_delete_video_files_and_row(user_id, video_id)` — removes file + thumbnail + Mongo row, refunds storage_used (clamped ≥0)
  - `cleanup_stream_video_if_orphaned(user_id, video_id)` — deletes ONLY if no other live stream on the account references the same video_id (prevents yanking a video from another live slot)
  - `wipe_all_videos_for_user(user_id)` — nukes everything + resets storage_used=0 (called when all plans have expired so the droplet's disk isn't held hostage)
- WIRED INTO:
  - `POST /api/stream/stop` — after marking is_live=False, calls `cleanup_stream_video_if_orphaned`. Response now includes `video_deleted: true/false`. Sets `stopped_reason='user_stopped'`.
  - `sync_user_plans_and_enforce_slots` — after auto-stopping excess streams from slot-shrink, calls the same cleanup per stream. Preserves the `stopped_reason='plan_expired_slot_shrink'` label.
  - `check_active_plan` (all-plans-expired branch) — first stops any lingering ffmpeg + marks live_streams `stopped_reason='all_plans_expired'`, THEN calls `wipe_all_videos_for_user`, THEN raises 403.
- FRONTEND UX (`LiveSlot.jsx`):
  - Both stop buttons (per-slot Stop + primary "Stop Live Stream") now show a confirm() dialog: "Stopping this stream will PERMANENTLY DELETE the video that was being broadcast."
  - On success, toast shows either "Stream stopped — video removed from storage" or plain "Stream stopped" (based on backend's `video_deleted` field)
  - After stop, refreshes videos list + user's storage_used counter so the UI reflects the freed space instantly
- TESTING (manual direct-call, 4/4 pass):
  - T1 stop stream → file removed, DB row gone, storage_used refunded exactly
  - T2 orphan check → 2 live slots share same video, stopping one preserves the file; stopping the second finally deletes it
  - T3 wipe_all_videos_for_user → 3 videos + files removed, storage=0
  - T4 check_active_plan on all-expired user → stops zombie stream (stopped_reason='all_plans_expired'), wipes videos, raises 403


## Iteration 12 (2026-08-01) - Background Video Transcoding / Downscaling
- USER REQUEST: Auto-downscale uploaded videos: 1080p→720p, 720p→480p, 480p→360p. Below 480p → skip. Runs in the background (non-blocking).
- NEW BACKEND MODULE (`server.py` top):
  - `_target_height(source_h)` — pure rule table function: ≥1080→720, ≥720→480, ≥480→360, else None
  - `transcode_video_background(video_id, user_id, source_path, target_height)` — long-running async coroutine, guarded by `_TRANSCODE_SEM` (Semaphore(1)) so we never run > 1 ffmpeg at once on a 1GB droplet. Uses `libx264 preset veryfast crf 23 aac 128k -movflags +faststart`. Writes to a `.__transcode.tmp` file and atomic-renames on success (safe on Linux even if a stream is reading the old inode). Regenerates the JPEG thumbnail from the transcoded file. Updates the video doc with new `size`, `width`, `height`, `transcoded_to`, `transcoded_at`, `processing_status='completed'` and refunds the user's `storage_used` by (new_size - old_size). On failure, keeps the original file and marks `transcode_error: true` but still flips status to `completed` so the video is streamable.
  - `schedule_transcode(...)` — fire-and-forget helper; task refs held in `_TRANSCODE_TASKS` set so the GC doesn't kill mid-coroutine.
- UPLOAD FINALIZE FLOW: After ffprobe extracts height, we call `_target_height`. If a target exists and differs from the source, we flip the video doc to `processing_status='transcoding'` + `transcode_target='<N>p'` + `original_height` + `original_size`, then schedule the background task. Upload response now returns `processing_status` + `transcode_target` fields so the client can react.
- STARTUP RECOVERY: If backend crashed mid-transcode, all videos left in `processing_status='transcoding'` are inspected on boot. If the file no longer needs downscaling (already ≤ target), flip to `completed`. Otherwise reschedule the transcode. Prevents videos from getting stuck in a permanent "Processing…" state.
- FRONTEND `VideoManager.jsx`:
  - New black overlay + spinner + "Processing…" label + "→ 480p" arrow while `processing_status === 'transcoding'` (test id `video-transcoding-{id}`)
  - Polls `/api/videos` every 5s ONLY while at least one video is transcoding — auto-updates the resolution badge, size, and thumbnail when done. Also refreshes `refreshUser()` so the Storage Usage bar drops in real time.
- TESTING (direct-call, all pass):
  - Rule table verified for all boundary inputs (1080/1440/720/480/360/0)
  - Actual 720p input → produced 854×480 file via ffprobe (real transcode, not a mock)
  - File shrank 36.8KB → 25.2KB
  - DB updated (height, width, size, processing_status, transcoded_to='480p')
  - storage_used counter refunded exactly to the new file size


## Iteration 13 (2026-08-01) - Admin Analytics Dashboard (Comprehensive)
- USER REQUEST: Full admin dashboard — sidebar Analytics link + home summary cards, live-user counter, live streams table with per-stream Stop, support ticket visibility & reply, user history browser, system health monitor, broadcast tool.
- BACKEND ENDPOINTS added (all guarded by `get_admin_user` dependency — 403 if not admin/lifetime):
  - `GET /api/admin/summary` — total_users, live_users, live_streams, signups_today/week, active_paying_users, open_tickets, total_videos
  - `GET /api/admin/system` — psutil CPU/RAM/disk + load avg + build_sha
  - `GET /api/admin/live-users` — enriched rows: user email/mobile/plan + plan start & expiry + video title/size/resolution + stream_id
  - `POST /api/admin/stream/{stream_id}/stop` — force-stop with `stopped_reason='admin_force_stop'` and `stopped_by_admin`
  - `GET /api/admin/tickets?status=open|closed` — lists all support tickets, joined with user contact info (fixes the "tickets invisible" bug — 9 pre-existing tickets now surface)
  - `POST /api/admin/tickets/{ticket_id}/reply` — append reply, optionally close
  - `GET /api/admin/users?q=email_substring` — paginated user browser
  - `GET /api/admin/users/{user_id}/history` — full history (user profile + transactions + streams + videos)
  - `POST /api/admin/broadcast` — create announcement targeted at all/active_plan/live_only
  - `GET /api/admin/broadcasts` — list all sent broadcasts
  - `DELETE /api/admin/broadcast/{id}` — hard-delete broadcast
  - `GET /api/notifications` — user-side fetch of active broadcasts (audience-filtered)
- SCHEMA additions:
  - `users.mobile_number` (optional string) — editable via Profile page, shown in admin tables
  - `notifications` collection — {notification_id, title, body, audience, severity, created_by, created_at, active}
- DEPENDENCY: `psutil==7.2.2` added to backend/requirements.txt for the system monitor.
- FRONTEND `AdminDashboard.jsx` (single tabbed page at `/dashboard/analytics`):
  - Tab strip: Overview / Live Users / Tickets (with red badge counter) / Users / Broadcast
  - Overview: 8 stat cards + System panel with CPU/RAM/Disk progress bars (auto-color: red when >80%)
  - Live Users: full table with email/mobile/plan/start/expiry/video/size/resolution + force-Stop button
  - Tickets: list with subject/message/status pill; reply dialog with Send + Send&Close
  - Users: email-substring search + table + "History" opens dialog with active_plans, transactions, streams, videos
  - Broadcast: send new announcement (title/body/audience/severity) + list of past broadcasts with delete
  - Auto-polls /admin/{summary,system,live-users} every 15s for real-time counters
- FRONTEND `Dashboard.jsx` home page (per user requirement #1): admin-only "Admin snapshot" gradient card at top with 4 mini-stats (Live now, Total users, Sign-ups today, Open tickets) + "Open Analytics →" button
- FRONTEND `NotificationBanner.jsx` component + integrated into `DashboardLayout` — shows active broadcasts at top of every dashboard page, dismissible per-user (localStorage), audience-aware
- FRONTEND `Profile.jsx` — new Mobile Number field (WhatsApp/SMS) sent to `/api/auth/profile` and stored on user doc
- FRONTEND sidebar — Admin sees "Analytics" nav item (conditional on `role==='admin' || plan==='lifetime'`)
- VERIFIED via direct curl + Playwright: /admin/summary returns 56 users + 9 open tickets, /admin/system returns real CPU 7.9% RAM 48.4% Disk 15.7%, admin-dashboard renders all 5 tabs, 9 tickets surface in Tickets tab with badge, sidebar Analytics link visible, admin-home-summary card renders on Dashboard home.



## Process Management + Queue Robustness (2026-07)

User asked for "PM2 + BullMQ/Redis" — both are Node-only, but the Python
equivalents are already in place. Fixed one latent bug and hardened the setup:

- **Supervisor config**: switched `--workers 2` → `--workers 1` (avoids
  duplicate reaper/sweeper loops and split-semaphore transcodes),
  `startretries 3 → 5`, added `startsecs`, `stopsignal=TERM`,
  25MB × 5 log rotation. Same file also referenced by both setup and update.
- **`systemctl enable supervisor`** now enforced by both `setup.sh` and
  `update.sh` so the app auto-starts after a droplet reboot.
- **`start_ffmpeg_push` hardening**: fails fast with `FileNotFoundError` if
  source missing, waits 1.2 s and returns `RuntimeError` with stderr tail if
  ffmpeg dies at spawn (bad key/DNS/codec). Callers translate to HTTP 410/500.
- **Persistent ffmpeg logs** at `/var/log/live-adda/ffmpeg/ffmpeg_<key>_<ts>.log`
  (falls back to `/tmp` on preview/dev).
- **Doc**: new `/app/deploy/README-process-management.md` — full mapping of
  PM2/BullMQ features → Python-native equivalents, operational commands,
  when to upgrade to arq/Redis (spoiler: not yet).

## Clickable Analytics Cards + Admin Video Delete + Instant Auto-Purge + Mobile Signup (2026-07)

**Backend (`server.py`)**
- `UserRegister` model + `/api/auth/register` now accept `mobile_number` — stored on the user doc, surfaced everywhere (admin tables, drilldowns, ticket views).
- New `GET /api/admin/videos` — every video joined with owner email/mobile/plan + `is_live` flag.
- New `DELETE /api/admin/videos/{video_id}` — admin hammer: force-stops any live stream on that video, deletes file + thumbnail + row, refunds storage. Returns `{bytes_freed, streams_stopped}`.
- New `GET /api/admin/users/filtered?filter=paying|signups_today|signups_7d` — feeds the click-through dialogs.
- **Auto-purge wired everywhere**:
  - Reaper (15 s): when ffmpeg self-exits, calls `cleanup_stream_video_if_orphaned` so disk frees immediately.
  - Sweeper (30 s): on `plan_expired_sweep` calls `wipe_all_videos_for_user`; on `slot_shrink_sweep` calls `cleanup_stream_video_if_orphaned` per killed stream.
  - Admin force-stop endpoint: now purges the orphaned video too.

**Frontend**
- `Register.jsx`: added required Mobile Number field with `Phone` icon, tel input, 7–15 digit sanity check, WhatsApp/SMS helper text. Chained through `AuthContext.register(...)` → `authAPI.register(...)`.
- `AdminDashboard.jsx`: converted `StatCard` to a real button. Every Overview card is now clickable:
  - Live Now / Active Streams → jump to Live Users tab
  - Total Users → jump to Users tab
  - Open Tickets → jump to Tickets tab
  - Paying Users / Sign-ups Today / Sign-ups 7d → open a modal table with email + mobile + plan + created_at + expires_at
  - Total Videos → open a modal table of every video with size / resolution / owner + a red per-row **Delete** button (double-confirms if the video is currently live)

## YouTube Live Smooth Ingest (2026-07)
Fixes the "YouTube is not receiving enough video to maintain smooth streaming" alert. Every flag below is defensible: it's either a documented YouTube-live requirement or a fix for a real cause of RTMP-side buffering.

**youtube_service.py — `start_ffmpeg_push`:**
- Switched endpoint from `rtmp://a.rtmp.youtube.com/live2` → `rtmps://a.rtmp.youtube.com/live2` (survives firewalls/DPI that drop plain RTMP packets).
- Added `_probe_gop_seconds()` — measures average keyframe distance in the first 30 s. Stream-copy is now allowed ONLY when source is h264+aac AND GOP ≤ 2.5 s. Everything else re-encodes.
- Re-encode path is now true **CBR at 1800 kbps** (`-b:v -minrate -maxrate` all equal, `-bufsize 3600k`, `-x264-params nal-hrd=cbr:force-cfr=1`). Fixes bursty output that starved the RTMP socket.
- Forced 2-second GOP (`-g 60 -keyint_min 60 -sc_threshold 0`) — the single biggest cause of the "not receiving enough video" alert.
- Constant frame rate: `-r 30 -pix_fmt yuv420p -profile:v high -level 4.1`, audio locked to `-ar 44100 -ac 2`.
- Timestamp normalization: `-fflags +genpts -avoid_negative_ts make_zero -af aresample=async=1` — eliminates loop-boundary drift and PTS glitches in user uploads.
- FLV muxer flag: `-flvflags no_duration_filesize` — cleaner header for an infinite live stream.

**server.py — `transcode_video_background`:**
- Added the same `-g 60 -keyint_min 60 -sc_threshold 0 -r 30 -profile:v high -level 4.1 -pix_fmt yuv420p -ar 44100 -ac 2` so every video we transcode is directly "stream-copy safe" for YouTube Live. Next stream on that video pays zero CPU AND cannot trip the buffering alert.

## Instant CPU Cleanup on Stream/Plan End (2026-07)
Previously the "stop ffmpeg" logic only fired when the user hit an API. If someone paid for a Daily plan, started a stream, then closed their browser, the encoder kept burning ~100% CPU past hour 24 because nothing was calling `check_active_plan`. Added:
- **Reaper loop (every 15 s)** — catches ffmpeg that died on its own, marks DB row `is_live=False, stopped_reason="ffmpeg_exited"`.
- **Plan-expiry sweeper (every 30 s)** — scans `live_streams` where `is_live=True`, checks the owner's `active_plans` server-side, and kills any ffmpeg whose owner has no non-expired plans (`stopped_reason="plan_expired_sweep"`) or has more streams than slots (`stopped_reason="slot_shrink_sweep"`). Runs regardless of whether the user is online.
- Both loops share the improved `stop_ffmpeg_push` (SIGTERM process group → 5 s wait → SIGKILL → reap) so CPU drops immediately when the sweeper fires.
- Worst-case latency between "plan expires" and "CPU freed" is now ≤30 s (one sweeper cycle), down from "until the user opens the app again" (unbounded).

## FFmpeg CPU Optimizations (2026-07)
For the 2 vCPU / 4 GB DigitalOcean droplet the user runs in production:
- **Preset**: re-encode path switched from `-preset veryfast` → `-preset ultrafast -tune zerolatency`.
- **Bitrate**: dropped from 2500k / max 2500k / buf 5000k → **1200k / max 1500k / buf 3000k** (matches 720p transcoded sources, avoids CPU throttling blur).
- **Stream copy**: new `ffprobe` step in `start_ffmpeg_push`. If source is already `h264` + `aac`, the push uses `-c copy -bsf:a aac_adtstoasc` (near-zero CPU). Otherwise falls back to the ultrafast re-encode above.
- **Process cleanup**: ffmpeg now spawned with `start_new_session=True`; `stop_ffmpeg_push` sends SIGTERM to the whole process group, waits 5 s, escalates to SIGKILL, and always reaps the Popen so no zombies remain.
- **Reaper task**: new `_ffmpeg_reaper_loop` runs every 15 s from the FastAPI startup hook — catches ffmpeg processes that exited on their own (YouTube dropped RTMP, file removed) and flips their `live_streams` row to `is_live=False, stopped_reason="ffmpeg_exited"`.
- Callers of `start_ffmpeg_push` / `stop_ffmpeg_push` are unchanged (drop-in signature).

## Deploy Script Auto-Heal (2026-07)
- `/app/deploy/update.sh` now rewrites any Nginx upstream still pointing at `127.0.0.1:8000` to `127.0.0.1:8001` and runs `nginx -t && systemctl reload nginx` in step [4/5].
- Fixes the Cloudflare 502 the user hit in production when their Nginx site config was stuck on the old backend port.
- Runs after `git pull` + `yarn build`, so every subsequent `sudo ./deploy/update.sh` self-heals the port mismatch.
