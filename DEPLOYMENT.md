# Live Adda — DigitalOcean Deployment Guide (IP-only, no domain)

This guide deploys the FastAPI + React + MongoDB app on a single Ubuntu 22.04
DigitalOcean droplet, with a persistent 24/7 ffmpeg encoder managed by systemd.

> **Assumption:** You are using the droplet's public IP (e.g. `203.0.113.10`) and
> have NOT bought a domain. Replace `YOUR_DROPLET_IP` everywhere below.

---

## ⚠️ IMPORTANT: YouTube OAuth needs a hostname + HTTPS (not a raw IP)

Google OAuth **rejects raw IP addresses** as authorized redirect URIs and requires
**HTTPS** (except `http://localhost`). Since you don't have a domain, use a **free**
option — no purchase needed:

**Option A — Free subdomain via DuckDNS (recommended):**
1. Go to https://www.duckdns.org, sign in, create a subdomain, e.g. `liveadda.duckdns.org`
2. Point it to `YOUR_DROPLET_IP`
3. Get free HTTPS with Let's Encrypt (see Step 7)
4. Use `https://liveadda.duckdns.org` as your app URL and OAuth redirect base

**Option B — Test locally first:** Google allows `http://localhost:8001/api/youtube/oauth/callback`
for a "Testing" OAuth client — useful to validate the flow before going public.

Everything else (auth, uploads, payments, dashboard) works fine on the raw IP over HTTP.
Only the **YouTube OAuth connect step** requires the DuckDNS+HTTPS setup above.

---

## 1. Create & access the droplet
- Ubuntu 22.04 LTS, at least 2GB RAM (Basic Droplet $12/mo or Hetzner CX22)
```bash
ssh root@YOUR_DROPLET_IP
```

## 2. Install system dependencies
```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv nodejs npm nginx ffmpeg curl git

# Install yarn (frontend uses yarn, NOT npm for installs)
npm install -g yarn

# Install MongoDB 7.0
curl -fsSL https://pgp.mongodb.com/server-7.0.asc | gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list
apt update && apt install -y mongodb-org
systemctl enable --now mongod
```

## 3. Get the code
```bash
# After "Save to GitHub" from Emergent:
cd /opt
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git live-adda
cd live-adda
```

## 4. Backend setup
```bash
cd /opt/live-adda/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create the .env from the example and fill in values
cp .env.example .env
nano .env   # set MONGO_URL, DB_NAME, JWT_SECRET, STRIPE_API_KEY, YOUTUBE_* etc.
```

## 5. Frontend build
```bash
cd /opt/live-adda/frontend
cp .env.example .env
nano .env   # set REACT_APP_BACKEND_URL (see note below)
yarn install
yarn build   # produces /opt/live-adda/frontend/build
```

**REACT_APP_BACKEND_URL:**
- IP-only over HTTP: `http://YOUR_DROPLET_IP`
- With DuckDNS+HTTPS: `https://liveadda.duckdns.org`

## 6. Process management with Supervisor
```bash
apt install -y supervisor
cp /opt/live-adda/deploy/supervisor-backend.conf /etc/supervisor/conf.d/live-adda-backend.conf
supervisorctl reread && supervisorctl update
supervisorctl status
```
(Frontend is served as static files by Nginx from the `build/` folder — no process needed.)

## 7. Nginx reverse proxy
```bash
cp /opt/live-adda/deploy/nginx.conf /etc/nginx/sites-available/live-adda
ln -s /etc/nginx/sites-available/live-adda /etc/nginx/sites-enabled/live-adda
rm -f /etc/nginx/sites-enabled/default
# Edit the file: set server_name to YOUR_DROPLET_IP or liveadda.duckdns.org
nano /etc/nginx/sites-available/live-adda
nginx -t && systemctl restart nginx
```

**Free HTTPS (only if using DuckDNS):**
```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d liveadda.duckdns.org
```

## 8. Firewall
```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
```

## 9. YouTube 24/7 ffmpeg (systemd template)
The app starts ffmpeg automatically when a broadcast is created via the API.
For an always-on stream that survives reboots, use the provided systemd template:
```bash
# Example: stream video file to a YouTube stream key
cp /opt/live-adda/deploy/liveadda-stream@.service /etc/systemd/system/
systemctl daemon-reload
# Start a persistent stream (encode the video path + stream key into an env file first)
# systemctl enable --now liveadda-stream@1
```
See `deploy/liveadda-stream@.service` for details.

## 10. Google Cloud OAuth config
- APIs & Services → Credentials → OAuth 2.0 Client (Web application)
- **Authorized redirect URI:** `https://liveadda.duckdns.org/api/youtube/oauth/callback`
  (or `http://localhost:8001/api/youtube/oauth/callback` for local testing)
- OAuth consent screen → add your Google account as a **Test user**
- Enable **YouTube Data API v3**
- Put the Client ID/Secret in `backend/.env` → `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`
- Restart backend: `supervisorctl restart live-adda-backend`

## 11. Verify
```bash
curl http://YOUR_DROPLET_IP/api/          # health
# Open http://YOUR_DROPLET_IP (or https://liveadda.duckdns.org) in a browser
```

---

## Updating after code changes
```bash
cd /opt/live-adda && git pull
cd backend && source venv/bin/activate && pip install -r requirements.txt && supervisorctl restart live-adda-backend
cd ../frontend && yarn install && yarn build && systemctl reload nginx
```
