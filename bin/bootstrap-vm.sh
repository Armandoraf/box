#!/usr/bin/env bash
set -euo pipefail

IMAGE=${IMAGE:-"ghcr.io/your-org/box:latest"}
SERVICE_NAME=${SERVICE_NAME:-"box-runner"}
CHROME_DEBUG_PORT=${CHROME_DEBUG_PORT:-9225}

sudo apt-get update -y
sudo apt-get install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker

sudo mkdir -p /etc/${SERVICE_NAME}

cat <<UNIT | sudo tee /etc/systemd/system/${SERVICE_NAME}.service >/dev/null
[Unit]
Description=Box Runner (FastAPI + Chromium)
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
RestartSec=5
Environment=CHROME_DEBUG_PORT=${CHROME_DEBUG_PORT}
ExecStart=/usr/bin/docker run --rm \
  --name ${SERVICE_NAME} \
  -p 8000:8000 -p ${CHROME_DEBUG_PORT}:9225 \
  ${IMAGE}
ExecStop=/usr/bin/docker stop ${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl start ${SERVICE_NAME}

sudo systemctl status --no-pager ${SERVICE_NAME}
