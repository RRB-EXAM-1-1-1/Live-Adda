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
