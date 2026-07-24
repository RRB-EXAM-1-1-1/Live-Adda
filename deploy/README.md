# Live Adda — Deployment Guide

Quick reference for deploying Live Adda (FastAPI + React + MongoDB) to a
DigitalOcean droplet with 24/7 YouTube streaming.

---

## Prerequisites (do these FIRST)

1. **DNS A record** — Point your domain to the droplet's public IP:
   ```
   Type: A   Host: @ (and www)   Value: YOUR_DROPLET_IP
   ```
   Wait for it to propagate (`dig liveadda.org +short` should return your IP)
   before running certbot, or HTTPS provisioning will fail.

2. **Google Cloud OAuth** — In APIs & Services → Credentials → your OAuth client:
   - **Authorized redirect URI (must be HTTPS):**
     `https://liveadda.org/api/youtube/oauth/callback`
   - Enable **YouTube Data API v3**
   - On the OAuth consent screen, add your Google account as a **Test user**
   - ⚠️ `http://` and raw IP addresses are **rejected** by Google — HTTPS + domain only.

3. **Droplet** — Ubuntu 22.04, ≥ 2GB RAM recommended. 1GB works only with the
   2GB swap file that `setup.sh` / `update.sh` / `fix-deployment.sh` provision
   automatically (needed to survive the React production build).

---

## 🚑 Broken deployment? One-shot recovery

If `pip install` failed with `emergentintegrations` / internal `litellm` errors,
**or** `yarn build` was OOM-killed on a 1GB droplet, run:

```bash
cd /opt/live-adda
git pull
sudo bash deploy/fix-deployment.sh
```

This script will:
1. Allocate a 2GB swap file (persistent via `/etc/fstab`) so `yarn build` stops OOM-crashing.
2. Strip any Emergent-internal lines from `backend/requirements.txt` (defensive).
3. Reinstall backend deps in the venv (`REBUILD_VENV=1` to wipe & recreate).
4. Rebuild the frontend with `NODE_OPTIONS=--max-old-space-size=1536` and `GENERATE_SOURCEMAP=false`.
5. Restart the backend via Supervisor and reload Nginx.

---

## One-command deploy

```bash
# On the droplet (as root):
curl -O https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/deploy/setup.sh
nano setup.sh        # edit the CONFIG block (REPO_URL, DOMAIN, secrets, YOUTUBE_*)
chmod +x setup.sh
sudo ./setup.sh
```

The script installs everything, clones the repo, writes `.env` files, builds the
frontend, configures Supervisor + Nginx, and provisions HTTPS via Let's Encrypt.

---

## Manual deploy
See the full step-by-step in [`../DEPLOYMENT.md`](../DEPLOYMENT.md).

---

## Key paths on the server

| What | Path |
|---|---|
| Project root | `/opt/live-adda` |
| Backend + venv | `/opt/live-adda/backend` (`.../venv`) |
| Backend env | `/opt/live-adda/backend/.env` |
| Frontend build (served by Nginx) | `/opt/live-adda/frontend/build` |
| Uploaded videos | `/opt/live-adda/backend/uploads/videos` |
| Backend logs | `/var/log/live-adda/backend.{out,err}.log` |
| Nginx site | `/etc/nginx/sites-available/live-adda` |
| Supervisor config | `/etc/supervisor/conf.d/live-adda-backend.conf` |

---

## Required environment variables (`backend/.env`)

| Var | Notes |
|---|---|
| `MONGO_URL` | `mongodb://localhost:27017` |
| `DB_NAME` | `live_adda_db` |
| `JWT_SECRET` | 64-char hex — `openssl rand -hex 32` |
| `STRIPE_API_KEY` | Stripe secret key |
| `MAX_STORAGE_GB` | `2` |
| `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` | Google Cloud OAuth |
| `PUBLIC_APP_URL` | e.g. `https://liveadda.org` — **must** match the whitelisted redirect scheme+host |

`frontend/.env`: `REACT_APP_BACKEND_URL=https://liveadda.org`

---

## Common operations

```bash
# Restart backend after code/env changes
supervisorctl restart live-adda-backend

# Tail logs
tail -f /var/log/live-adda/backend.err.log

# Update to latest code
cd /opt/live-adda && git pull \
  && cd backend && source venv/bin/activate && pip install -r requirements.txt && supervisorctl restart live-adda-backend \
  && cd ../frontend && yarn install && yarn build && systemctl reload nginx

# Renew HTTPS cert (certbot auto-renews; force test)
certbot renew --dry-run

# 24/7 always-on stream (survives reboots) — see deploy/liveadda-stream@.service
systemctl enable --now liveadda-stream@1
```

---

## Troubleshooting

- **`redirect_uri_mismatch`** → `PUBLIC_APP_URL` and the Google Cloud redirect URI
  must be byte-for-byte identical (`https://liveadda.org/api/youtube/oauth/callback`).
- **Certbot fails** → DNS A record not propagated yet, or port 80 blocked (`ufw allow 'Nginx Full'`).
- **Slow uploads** → confirm `proxy_request_buffering off;` is in the Nginx `/api/` block.
- **Backend 502** → `supervisorctl status`; check `/var/log/live-adda/backend.err.log`.
