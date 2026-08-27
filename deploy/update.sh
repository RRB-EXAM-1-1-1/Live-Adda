#!/usr/bin/env bash
#
# Live Adda - update an EXISTING deployment to the latest code.
# Run on the droplet after you've pushed the latest code to GitHub.
#
#   cd /opt/live-adda && sudo ./deploy/update.sh
#
set -euo pipefail

INSTALL_DIR="/opt/live-adda"
cd "$INSTALL_DIR"

# --- Ensure >=2GB swap so `yarn build` doesn't get OOM-killed on 1GB droplets ---
CURRENT_SWAP_MB=$(free -m | awk '/^Swap:/ {print $2}')
if [ "${CURRENT_SWAP_MB:-0}" -lt 2000 ]; then
  echo "==> [0/5] Adding 2GB swap (current swap = ${CURRENT_SWAP_MB}MB)..."
  swapoff /swapfile 2>/dev/null || true
  rm -f /swapfile
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q "/swapfile" /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
  sysctl vm.swappiness=10 || true
fi

echo "==> [1/5] Pulling latest code..."
git pull

# Capture the deployed commit SHA so /api/health can report it without needing git at runtime
DEPLOYED_SHA=$(git -C "$INSTALL_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")
DEPLOYED_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
if grep -q "^BUILD_SHA=" "$INSTALL_DIR/backend/.env" 2>/dev/null; then
  sed -i "s|^BUILD_SHA=.*|BUILD_SHA=\"${DEPLOYED_SHA}\"|" "$INSTALL_DIR/backend/.env"
else
  echo "BUILD_SHA=\"${DEPLOYED_SHA}\"" >> "$INSTALL_DIR/backend/.env"
fi
if grep -q "^BUILD_TIME=" "$INSTALL_DIR/backend/.env" 2>/dev/null; then
  sed -i "s|^BUILD_TIME=.*|BUILD_TIME=\"${DEPLOYED_TIME}\"|" "$INSTALL_DIR/backend/.env"
else
  echo "BUILD_TIME=\"${DEPLOYED_TIME}\"" >> "$INSTALL_DIR/backend/.env"
fi
echo "    Deployed SHA=${DEPLOYED_SHA}  time=${DEPLOYED_TIME}"

echo "==> [2/5] Backend deps + restart..."
cd "$INSTALL_DIR/backend"
source venv/bin/activate
pip install -r requirements.txt
# NOTE: emergentintegrations/litellm are Emergent-internal and intentionally NOT
# in requirements.txt. Stripe endpoints degrade gracefully if the module is absent.

# Ensure supervisor autostarts on OS reboot (idempotent — no-op if already enabled).
# Also refresh the supervisor unit in case we tweaked worker count, log rotation, etc.
mkdir -p /var/log/live-adda
systemctl enable supervisor >/dev/null 2>&1 || true
sed "s|/opt/live-adda|${INSTALL_DIR}|g" "$INSTALL_DIR/deploy/supervisor-backend.conf" > /etc/supervisor/conf.d/live-adda-backend.conf
supervisorctl reread >/dev/null 2>&1 || true
supervisorctl update >/dev/null 2>&1 || true

echo "    Checking required env vars in backend/.env ..."
MISSING=0
for VAR in RAZORPAY_KEY_ID RAZORPAY_KEY_SECRET PUBLIC_APP_URL; do
  if ! grep -q "^${VAR}=" "$INSTALL_DIR/backend/.env" 2>/dev/null || \
     [ -z "$(grep "^${VAR}=" "$INSTALL_DIR/backend/.env" | cut -d'"' -f2)" ]; then
    echo "    !! WARNING: ${VAR} is missing/empty in backend/.env"
    MISSING=1
  fi
done
if [ "$MISSING" = "1" ]; then
  echo "    -> Edit backend/.env and set the missing vars, then re-run. (These are gitignored, so not pulled from GitHub.)"
fi

supervisorctl restart live-adda-backend

echo "==> [3/5] Frontend build..."
cd "$INSTALL_DIR/frontend"
yarn install
# Cap Node heap and disable sourcemaps to survive on 1GB droplets (with 2GB swap).
export NODE_OPTIONS="--max-old-space-size=1536"
export GENERATE_SOURCEMAP=false
export CI=false
yarn build

echo "==> [4/5] Healing Nginx upstream port (8000 -> 8001) and reloading..."
# Auto-heal: older deploys pointed Nginx at 127.0.0.1:8000, but the backend
# runs on 8001. Rewrite any stale references so future updates self-correct
# instead of returning 502 Bad Gateway.
sed -i 's|127.0.0.1:8000|127.0.0.1:8001|g' /etc/nginx/sites-available/* /etc/nginx/sites-enabled/* 2>/dev/null || true
nginx -t && systemctl reload nginx

echo "==> [5/5] Done. Verify at your domain."
echo "    Landing page should now show INR (₹35/₹199/₹599) and title 'Live Adda'."
echo "    If the browser still shows old prices, hard-refresh (Ctrl+Shift+R) to bypass cache."
