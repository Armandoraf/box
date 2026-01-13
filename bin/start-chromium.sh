#!/usr/bin/env bash
set -euo pipefail

DEFAULT_ARGS="--no-sandbox --disable-gpu --disable-dev-shm-usage --disable-blink-features=AutomationControlled --disable-features=IsolateOrigins,site-per-process --remote-debugging-address=127.0.0.1 --remote-debugging-port=9223 about:blank"
CHROMIUM_ARGS=${CHROMIUM_ARGS:-$DEFAULT_ARGS}
CHROMIUM_ARGS_DEBUG=${CHROMIUM_ARGS_DEBUG:-$DEFAULT_ARGS}

CHROMIUM_CMD=(chromium)
if [[ -x /snap/bin/chromium ]]; then
  CHROMIUM_CMD=(/usr/bin/snap run chromium)
fi

if [[ "${DEBUG:-0}" == "1" ]]; then
  Xvfb :99 -screen 0 1280x720x24 &
  x11vnc -display :99 -forever -shared -rfbport 5900 -nopw &

  if [[ -z "${ENABLE_NOVNC:-}" ]]; then
    ENABLE_NOVNC=1
  fi

  if [[ "${ENABLE_NOVNC:-0}" == "1" ]]; then
    websockify --web=/usr/share/novnc 6080 localhost:5900 &
  fi

  socat TCP-LISTEN:9225,fork,bind=127.0.0.1 TCP:127.0.0.1:9223 &
  exec "${CHROMIUM_CMD[@]}" $CHROMIUM_ARGS_DEBUG
fi

socat TCP-LISTEN:9225,fork,bind=127.0.0.1 TCP:127.0.0.1:9223 &
exec "${CHROMIUM_CMD[@]}" --headless=new $CHROMIUM_ARGS
