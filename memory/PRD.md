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
