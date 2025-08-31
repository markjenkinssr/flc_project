#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="/srv/flc_project/app"
VENV="$REPO_DIR/.venv"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
ENV_FILE="/etc/flc_project.env"

# -------- args --------
# Usage:
#   deploy.sh                -> deploy 'main'
#   deploy.sh <branch>       -> deploy that branch
#   deploy.sh --tag <tag>    -> deploy that tag
MODE="branch"
TARGET="${1:-main}"
if [[ "${1:-}" == "--tag" ]]; then
  MODE="tag"
  [[ $# -ge 2 ]] || { echo "Usage: $0 --tag <tag>"; exit 2; }
  TARGET="$2"
fi

echo "==> Deploy target: $MODE '$TARGET'"

# -------- code update --------
cd "$REPO_DIR"
OLD_REV="$(git rev-parse --short HEAD || echo unknown)"
echo "==> Current rev: $OLD_REV"
git fetch origin --tags --prune

if [[ "$MODE" == "tag" ]]; then
  echo "==> Checking out tag $TARGET"
  git checkout -q "$TARGET"
else
  echo "==> Checking out branch $TARGET and fast-forwarding"
  git checkout -q "$TARGET" || git checkout -q -b "$TARGET" "origin/$TARGET"
  git reset --hard "origin/$TARGET"
fi

# -------- virtualenv & deps --------
if [[ ! -x "$PY" ]]; then
  echo "==> Creating virtualenv"
  python3 -m venv "$VENV"
fi

echo "==> Installing dependencies"
"$PIP" install --upgrade pip wheel
"$PIP" install -r requirements.txt

# -------- django mgmt helpers (read env as root) --------
manage () {
  sudo bash -lc "set -a; . $ENV_FILE; set +a; cd $REPO_DIR; $PY manage.py $*"
}

echo "==> Django checks & migrations"
manage check -v 1 || true
manage migrate --noinput
manage collectstatic --noinput

# -------- restart app --------
echo "==> Restarting gunicorn"
sudo systemctl restart gunicorn

echo "==> Waiting for app to boot..."
sleep 2

# -------- health checks --------
echo "==> Health check (gunicorn direct)"
if curl -sf -o /dev/null http://127.0.0.1:8000/registrations/sanity/; then
  echo "OK: gunicorn is serving."
else
  echo "FAIL: gunicorn health check failed. Rolling back to $OLD_REV"
  git reset --hard "$OLD_REV"
  sudo systemctl restart gunicorn
  exit 1
fi

echo "==> Health check (through nginx/public)"
if curl -sf -o /dev/null http://155.117.20.66/registrations/sanity/; then
  echo "OK: public endpoint is serving."
else
  echo "WARN: public endpoint failed. Check nginx logs: sudo tail -n 200 /var/log/nginx/error.log"
fi

echo "==> Deploy complete."
