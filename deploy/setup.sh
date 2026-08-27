#!/usr/bin/env bash
#
# Live Adda - one-shot deployment script for a fresh Ubuntu 22.04 DigitalOcean droplet.
#
# WHAT THIS DOES:
#   - Installs Python, Node, Yarn, MongoDB, Nginx, ffmpeg, Supervisor, Certbot
#   - Clones your repo to /opt/live-adda
#   - Sets up the backend (venv + deps) and builds the frontend
#   - Writes backend/.env and frontend/.env from the values you set below
#   - Configures Supervisor (backend) + Nginx (reverse proxy)
#   - Optionally provisions HTTPS via Let's Encrypt (required for YouTube OAuth)
#
# USAGE:
#   1. Edit the CONFIG section below.
#   2. scp this file to your droplet (or paste it), then:
#        chmod +x setup.sh && sudo ./setup.sh
#
set -euo pipefail

# ============================ CONFIG (EDIT THESE) ============================
REPO_URL="https://github.com/YOUR_USERNAME/YOUR_REPO.git"
INSTALL_DIR="/opt/live-adda"

# Public domain/host of your app. For YouTube OAuth this MUST be https + a real domain.
DOMAIN="liveadda.org"
USE_HTTPS="true"          # "true" runs certbot for https://$DOMAIN ; "false" serves http only
CERTBOT_EMAIL="you@example.com"   # for Let's Encrypt notices

# --- Backend secrets ---
JWT_SECRET="$(openssl rand -hex 32)"     # auto-generated; or hardcode your own
ADMIN_EMAIL="admin@liveadda.com"
ADMIN_PASSWORD="ChangeMe123!"
STRIPE_API_KEY="sk_test_or_live_key_here"
MAX_STORAGE_GB="2"

# --- YouTube OAuth (from Google Cloud) ---
YOUTUBE_CLIENT_ID="573321102528-h7r19jqaiv5vonj5jpi2agtbmuj1os67.apps.googleusercontent.com"
YOUTUBE_CLIENT_SECRET="GOCSPX-REPLACE_WITH_ROTATED_SECRET"
# =============================================================================

if [[ "$USE_HTTPS" == "true" ]]; then
  SCHEME="https"
else
  SCHEME="http"
fi
PUBLIC_APP_URL="${SCHEME}://${DOMAIN}"

echo "==> [1/9] Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv nodejs npm nginx ffmpeg curl git supervisor gnupg openssl
npm install -g yarn

# --- Ensure at least 2GB of swap so `yarn build` doesn't get OOM-killed on 1GB droplets ---
CURRENT_SWAP_MB=$(free -m | awk '/^Swap:/ {print $2}')
if [ "${CURRENT_SWAP_MB:-0}" -lt 2000 ]; then
  echo "    Current swap = ${CURRENT_SWAP_MB}MB -> creating /swapfile (2GB)..."
  swapoff /swapfile 2>/dev/null || true
  rm -f /swapfile
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q "/swapfile" /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
  sysctl vm.swappiness=10 || true
  echo "    Swap enabled: $(free -h | awk '/^Swap:/ {print $2}')"
else
  echo "    Swap already >=2GB (${CURRENT_SWAP_MB}MB) — skipping."
fi

echo "==> [2/9] Installing MongoDB 7.0..."
if ! command -v mongod >/dev/null 2>&1; then
  curl -fsSL https://pgp.mongodb.com/server-7.0.asc | gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
  echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" > /etc/apt/sources.list.d/mongodb-org-7.0.list
  apt update && apt install -y mongodb-org
fi
systemctl enable --now mongod

echo "==> [3/9] Cloning repository to ${INSTALL_DIR}..."
if [[ -d "$INSTALL_DIR/.git" ]]; then
  cd "$INSTALL_DIR" && git pull
else
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

echo "==> [4/9] Backend setup (venv + deps)..."
cd "$INSTALL_DIR/backend"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# NOTE: emergentintegrations & the internal litellm wheel are intentionally NOT in
# requirements.txt — they only exist inside Emergent's build environment. Razorpay
# is the active payment path; the legacy Stripe endpoints degrade gracefully if the
# module is absent (see server.py STRIPE_AVAILABLE flag).

echo "==> [5/9] Writing backend/.env..."
cat > "$INSTALL_DIR/backend/.env" <<EOF
MONGO_URL="mongodb://localhost:27017"
DB_NAME="live_adda_db"
CORS_ORIGINS="*"
JWT_SECRET="${JWT_SECRET}"
ADMIN_EMAIL="${ADMIN_EMAIL}"
ADMIN_PASSWORD="${ADMIN_PASSWORD}"
STRIPE_API_KEY="${STRIPE_API_KEY}"
MAX_STORAGE_GB="${MAX_STORAGE_GB}"
YOUTUBE_CLIENT_ID="${YOUTUBE_CLIENT_ID}"
YOUTUBE_CLIENT_SECRET="${YOUTUBE_CLIENT_SECRET}"
PUBLIC_APP_URL="${PUBLIC_APP_URL}"
EOF

echo "==> [6/9] Frontend build..."
cd "$INSTALL_DIR/frontend"
echo "REACT_APP_BACKEND_URL=${PUBLIC_APP_URL}" > "$INSTALL_DIR/frontend/.env"
yarn install
# Cap Node heap and disable sourcemaps to survive on 1GB droplets (with 2GB swap).
export NODE_OPTIONS="--max-old-space-size=1536"
export GENERATE_SOURCEMAP=false
export CI=false
yarn build

echo "==> [7/9] Configuring Supervisor (backend)..."
mkdir -p /var/log/live-adda
sed "s|/opt/live-adda|${INSTALL_DIR}|g" "$INSTALL_DIR/deploy/supervisor-backend.conf" > /etc/supervisor/conf.d/live-adda-backend.conf
supervisorctl reread && supervisorctl update
supervisorctl restart live-adda-backend || supervisorctl start live-adda-backend
# Enable supervisor to auto-start on server reboot (equivalent of `pm2 startup`).
systemctl enable supervisor >/dev/null 2>&1 || true

echo "==> [8/9] Configuring Nginx..."
sed -e "s|YOUR_DROPLET_IP|${DOMAIN}|g" -e "s|/opt/live-adda|${INSTALL_DIR}|g" \
    "$INSTALL_DIR/deploy/nginx.conf" > /etc/nginx/sites-available/live-adda
ln -sf /etc/nginx/sites-available/live-adda /etc/nginx/sites-enabled/live-adda
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# Firewall
ufw allow OpenSSH || true
ufw allow 'Nginx Full' || true
yes | ufw enable || true

echo "==> [9/9] HTTPS (Let's Encrypt)..."
if [[ "$USE_HTTPS" == "true" ]]; then
  apt install -y certbot python3-certbot-nginx
  certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${CERTBOT_EMAIL}" --redirect || \
    echo "!! Certbot failed. Ensure ${DOMAIN} DNS points to this droplet's IP, then re-run: certbot --nginx -d ${DOMAIN}"
else
  echo "Skipping HTTPS (USE_HTTPS=false). NOTE: YouTube OAuth requires HTTPS."
fi

echo ""
echo "======================================================================"
echo " Live Adda deployed."
echo " App:        ${PUBLIC_APP_URL}"
echo " Project:    ${INSTALL_DIR}"
echo " Backend:    ${INSTALL_DIR}/backend  (venv: ${INSTALL_DIR}/backend/venv)"
echo " Frontend:   ${INSTALL_DIR}/frontend/build (served by Nginx)"
echo " Backend env:${INSTALL_DIR}/backend/.env"
echo " Logs:       /var/log/live-adda/backend.{out,err}.log"
echo ""
echo " Google Cloud redirect URI to whitelist:"
echo "   ${PUBLIC_APP_URL}/api/youtube/oauth/callback"
echo ""
echo " Admin login: ${ADMIN_EMAIL} / ${ADMIN_PASSWORD}"
echo "======================================================================"
