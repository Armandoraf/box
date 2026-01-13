#!/usr/bin/env bash
set -euo pipefail

if [[ "${DEBUG:-0}" == "1" ]]; then
  Xvfb :99 -screen 0 1280x720x24 &
  x11vnc -display :99 -forever -shared -rfbport 5900 -nopw &

  if [[ -z "${ENABLE_NOVNC:-}" ]]; then
    ENABLE_NOVNC=1
  fi

  if [[ "${ENABLE_NOVNC:-0}" == "1" ]]; then
    websockify --web=/usr/share/novnc 6080 localhost:5900 &
  fi

  socat TCP-LISTEN:9225,fork,bind=0.0.0.0 TCP:127.0.0.1:9223 &
  exec chromium $CHROMIUM_ARGS_DEBUG
fi

socat TCP-LISTEN:9225,fork,bind=0.0.0.0 TCP:127.0.0.1:9223 &
exec chromium --headless=new $CHROMIUM_ARGS
