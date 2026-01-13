#!/usr/bin/env bash
set -euo pipefail

IMAGE="${image}"
SERVICE_NAME="box-router"
RUNNER_URLS="${runner_urls}"

apt-get update -y
apt-get install -y docker.io
systemctl enable docker
systemctl start docker

cat <<UNIT > /etc/systemd/system/$${SERVICE_NAME}.service
[Unit]
Description=Box Router
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
RestartSec=5
Environment=RUNNER_URLS=${runner_urls}
ExecStart=/usr/bin/docker run --rm \
  --name $${SERVICE_NAME} \
  -p 8080:8080 \
  -e RUNNER_URLS=${runner_urls} \
  ${image} \
  uvicorn router_app:app --host 0.0.0.0 --port 8080
ExecStop=/usr/bin/docker stop $${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable $${SERVICE_NAME}
systemctl start $${SERVICE_NAME}
