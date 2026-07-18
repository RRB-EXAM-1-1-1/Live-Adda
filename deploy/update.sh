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

echo "==> [1/5] Pulling latest code..."
git pull

echo "==> [2/5] Backend deps + restart..."
cd "$INSTALL_DIR/backend"
source venv/bin/activate
pip install -r requirements.txt
# emergentintegrations comes from a custom index (safe to re-run)
pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ >/dev/null 2>&1 || true

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
yarn build

echo "==> [4/5] Reloading Nginx..."
systemctl reload nginx

echo "==> [5/5] Done. Verify at your domain."
echo "    Landing page should now show INR (₹35/₹199/₹599) and title 'Live Adda'."
echo "    If the browser still shows old prices, hard-refresh (Ctrl+Shift+R) to bypass cache."
