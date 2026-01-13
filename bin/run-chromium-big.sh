#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME=${IMAGE_NAME:-box-chromium-xvfb}
CONTAINER_NAME=${CONTAINER_NAME:-box-chromium-xvfb}
ENABLE_NOVNC=${ENABLE_NOVNC:-0}

# Stop existing container if running
if docker ps -q --filter "name=^/${CONTAINER_NAME}$" | grep -q .; then
  docker stop "$CONTAINER_NAME" >/dev/null
fi

# Stop any container already binding required ports
for port in 9225 5900 6080; do
  if docker ps -q --filter "publish=${port}" | grep -q .; then
    docker ps -q --filter "publish=${port}" | xargs docker stop >/dev/null
  fi
done

# Build debug image
BUILD_ARGS=(--build-arg DEBUG_IMAGE=1)
if [[ "$ENABLE_NOVNC" == "1" ]]; then
  BUILD_ARGS+=(--build-arg INCLUDE_NOVNC=1)
fi
docker build -t "$IMAGE_NAME" "${BUILD_ARGS[@]}" .

# Run container in background with long-lived Chromium process
RUN_ARGS=(
  -d --rm
  --name "$CONTAINER_NAME"
  --shm-size=2g
  -p 9225:9225
  -p 5900:5900
  -e DEBUG=1
  -e ENABLE_NOVNC="$ENABLE_NOVNC"
)

if [[ "$ENABLE_NOVNC" == "1" ]]; then
  RUN_ARGS+=(-p 6080:6080)
fi

exec docker run \
  "${RUN_ARGS[@]}" \
  -e CHROMIUM_ARGS="--no-sandbox --disable-gpu --disable-dev-shm-usage --display=:99 --remote-debugging-address=0.0.0.0 --remote-debugging-port=9223 about:blank" \
  "$IMAGE_NAME"
