#!/usr/bin/env bash
set -euo pipefail

IMAGE=${IMAGE:-"ghcr.io/your-org/box-router:latest"}
SERVICE_NAME=${SERVICE_NAME:-"box-router"}
RUNNER_URLS=${RUNNER_URLS:-"http://10.0.0.2:8000,http://10.0.0.3:8000,http://10.0.0.4:8000,http://10.0.0.5:8000,http://10.0.0.6:8000"}

sudo apt-get update -y
sudo apt-get install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker

cat <<UNIT | sudo tee /etc/systemd/system/${SERVICE_NAME}.service >/dev/null
[Unit]
Description=Box Router
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
RestartSec=5
Environment=RUNNER_URLS=${RUNNER_URLS}
ExecStart=/usr/bin/docker run --rm \
  --name ${SERVICE_NAME} \
  -p 8080:8080 \
  -e RUNNER_URLS=${RUNNER_URLS} \
  ${IMAGE} \
  uvicorn router_app:app --host 0.0.0.0 --port 8080
ExecStop=/usr/bin/docker stop ${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl start ${SERVICE_NAME}

sudo systemctl status --no-pager ${SERVICE_NAME}
