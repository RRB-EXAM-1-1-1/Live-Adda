#!/usr/bin/env bash
#
# Live Adda - one-shot RECOVERY script for a broken DigitalOcean deployment.
#
# Use this when:
#   - `pip install -r requirements.txt` failed with emergentintegrations/litellm errors
#   - `yarn build` was OOM-killed on a 1GB droplet
#
# Usage on your droplet (run as root):
#   cd /opt/live-adda
#   git pull
#   sudo bash deploy/fix-deployment.sh
#
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/live-adda}"

if [ ! -d "$INSTALL_DIR" ]; then
  echo "ERROR: $INSTALL_DIR does not exist. Set INSTALL_DIR=... or run setup.sh first." >&2
  exit 1
fi

echo "======================================================================"
echo " Live Adda deployment recovery"
echo " Install dir: $INSTALL_DIR"
echo "======================================================================"

# ---------------------------------------------------------------------------
# 1. Ensure at least 2GB of swap so yarn build doesn't OOM-kill on 1GB RAM
# ---------------------------------------------------------------------------
CURRENT_SWAP_MB=$(free -m | awk '/^Swap:/ {print $2}')
echo "==> [1/6] Current swap: ${CURRENT_SWAP_MB}MB"
if [ "${CURRENT_SWAP_MB:-0}" -lt 2000 ]; then
  echo "    Allocating 2GB swap at /swapfile ..."
  swapoff /swapfile 2>/dev/null || true
  rm -f /swapfile
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=progress
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q "/swapfile" /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
  sysctl vm.swappiness=10 || true
  echo "    New swap: $(free -h | awk '/^Swap:/ {print $2}')"
else
  echo "    Swap OK (>=2GB), skipping."
fi

# ---------------------------------------------------------------------------
# 2. Sanitize requirements.txt (defensive - remove Emergent-internal lines if
#    the user still has an old copy from a stale git checkout)
# ---------------------------------------------------------------------------
echo "==> [2/6] Sanitizing backend/requirements.txt ..."
REQ="$INSTALL_DIR/backend/requirements.txt"
if [ -f "$REQ" ]; then
  sed -i \
    -e '/^emergentintegrations/d' \
    -e '/^litellm[[:space:]]*@[[:space:]]*https:\/\/customer-assets.emergentagent.com/d' \
    -e '/^litellm[[:space:]]*@[[:space:]]*https:\/\/d33sy5i8bnduwe.cloudfront.net/d' \
    "$REQ"
  echo "    OK. emergentintegrations & internal litellm URL removed if present."
else
  echo "    !! $REQ not found — skipping."
fi

# ---------------------------------------------------------------------------
# 3. Backend: wipe venv (in case corrupted from failed installs) & reinstall
# ---------------------------------------------------------------------------
echo "==> [3/6] Rebuilding Python venv & installing backend deps ..."
cd "$INSTALL_DIR/backend"
if [ -d venv ]; then
  # Only nuke venv if the user passes REBUILD_VENV=1; otherwise reuse it.
  if [ "${REBUILD_VENV:-0}" = "1" ]; then
    echo "    REBUILD_VENV=1 -> deleting existing venv/"
    rm -rf venv
  fi
fi
if [ ! -d venv ]; then
  python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt

# ---------------------------------------------------------------------------
# 4. Frontend build with capped memory
# ---------------------------------------------------------------------------
echo "==> [4/6] Building frontend with capped memory ..."
cd "$INSTALL_DIR/frontend"
yarn install
export NODE_OPTIONS="--max-old-space-size=1536"
export GENERATE_SOURCEMAP=false
export CI=false
yarn build
echo "    Frontend built at $INSTALL_DIR/frontend/build"

# ---------------------------------------------------------------------------
# 5. Restart backend via Supervisor
# ---------------------------------------------------------------------------
echo "==> [5/6] Restarting backend via Supervisor ..."
supervisorctl reread || true
supervisorctl update || true
supervisorctl restart live-adda-backend || supervisorctl start live-adda-backend
sleep 2
supervisorctl status live-adda-backend || true

# ---------------------------------------------------------------------------
# 6. Reload Nginx
# ---------------------------------------------------------------------------
echo "==> [6/6] Reloading Nginx ..."
nginx -t && systemctl reload nginx

echo ""
echo "======================================================================"
echo " Recovery complete."
echo " - Verify: curl -sSf https://liveadda.org/ | head -c 200 ; echo"
echo " - Backend logs: tail -n 100 /var/log/live-adda/backend.err.log"
echo " - If browser still shows old prices, hard-refresh with Ctrl+Shift+R."
echo "======================================================================"
