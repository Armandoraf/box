#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/box
ENV_DIR=/etc/box
REPO_URL=${REPO_URL:-}
GIT_REF=${GIT_REF:-main}

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  git \
  python3 \
  python3-venv \
  python3-pip \
  chromium \
  socat \
  dumb-init \
  fonts-liberation

if ! id -u box >/dev/null 2>&1; then
  useradd --system --home /opt/box --shell /usr/sbin/nologin box
fi

mkdir -p "$APP_DIR" "$ENV_DIR"

if [[ -n "$REPO_URL" ]]; then
  if [[ ! -d "$APP_DIR/.git" ]]; then
    rm -rf "$APP_DIR"
    git clone "$REPO_URL" "$APP_DIR"
  fi
  (cd "$APP_DIR" && git fetch --all && git checkout "$GIT_REF" && git pull)
fi

if [[ -f "$APP_DIR/requirements.txt" ]]; then
  python3 -m venv "$APP_DIR/venv"
  "$APP_DIR/venv/bin/pip" install --upgrade pip
  "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
fi

if [[ -f "$APP_DIR/bin/start-chromium.sh" ]]; then
  install -m 0755 "$APP_DIR/bin/start-chromium.sh" /usr/local/bin/start-chromium
fi

if [[ -f "$APP_DIR/deploy/gcp/box.env" ]]; then
  install -m 0640 "$APP_DIR/deploy/gcp/box.env" "$ENV_DIR/box.env"
  chown root:root "$ENV_DIR/box.env"
fi

if [[ -f "$APP_DIR/deploy/gcp/box.service" ]]; then
  install -m 0644 "$APP_DIR/deploy/gcp/box.service" /etc/systemd/system/box.service
fi

if [[ -f "$APP_DIR/deploy/gcp/chromium.service" ]]; then
  install -m 0644 "$APP_DIR/deploy/gcp/chromium.service" /etc/systemd/system/chromium.service
fi

chown -R box:box "$APP_DIR"

systemctl daemon-reload
systemctl enable chromium.service box.service
systemctl restart chromium.service
systemctl restart box.service
