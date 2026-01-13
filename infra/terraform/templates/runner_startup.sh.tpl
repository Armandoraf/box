#!/usr/bin/env bash
set -euo pipefail

IMAGE="${image}"
SERVICE_NAME="box-runner"
CHROME_DEBUG_PORT="${chrome_debug_port}"

apt-get update -y
apt-get install -y docker.io
systemctl enable docker
systemctl start docker

cat <<UNIT > /etc/systemd/system/$${SERVICE_NAME}.service
[Unit]
Description=Box Runner (FastAPI + Chromium)
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
RestartSec=5
Environment=CHROME_DEBUG_PORT=${chrome_debug_port}
ExecStart=/usr/bin/docker run --rm \
  --name $${SERVICE_NAME} \
  -p 8000:8000 -p ${chrome_debug_port}:9225 \
  ${image}
ExecStop=/usr/bin/docker stop $${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable $${SERVICE_NAME}
systemctl start $${SERVICE_NAME}
