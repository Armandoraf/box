#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME=${IMAGE_NAME:-box-chromium-xvfb}
CONTAINER_NAME=${CONTAINER_NAME:-box-chromium-xvfb}

# Stop existing container if running
if docker ps -q --filter "name=^/${CONTAINER_NAME}$" | grep -q .; then
  docker stop "$CONTAINER_NAME" >/dev/null
fi

# Stop any container already binding port 9225
if docker ps -q --filter "publish=9225" | grep -q .; then
  docker ps -q --filter "publish=9225" | xargs docker stop >/dev/null
fi

# Build slim image
docker build -t "$IMAGE_NAME" .

# Run container in background (headless Chromium)
exec docker run -d --rm \
  --name "$CONTAINER_NAME" \
  --shm-size=2g \
  -p 9225:9225 \
  -e CHROME_BLOCK_MEDIA=1 \
  "$IMAGE_NAME"
