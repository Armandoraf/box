#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME=${IMAGE_NAME:-box-chromium-xvfb}
CONTAINER_NAME=${CONTAINER_NAME:-box-chromium-xvfb}

# Stop existing container if running
if docker ps -q --filter "name=^/${CONTAINER_NAME}$" | grep -q .; then
  docker stop "$CONTAINER_NAME" >/dev/null
fi

# Build image
docker build -t "$IMAGE_NAME" .

# Run container in background with long-lived Chromium process
exec docker run -d --rm \
  --name "$CONTAINER_NAME" \
  --shm-size=2g \
  -p 9222:9222 \
  -e CHROMIUM_ARGS="--no-sandbox --disable-gpu --disable-dev-shm-usage --display=:99 --remote-debugging-address=0.0.0.0 --remote-debugging-port=9223 about:blank" \
  "$IMAGE_NAME"
