#!/usr/bin/env bash
set -euo pipefail

export DISPLAY=${DISPLAY:-:99}
export CHROME_DEBUG_PORT=${CHROME_DEBUG_PORT:-9225}
export CHROMIUM_ARGS=${CHROMIUM_ARGS:-"--no-sandbox --disable-gpu --disable-dev-shm-usage --display=:99 --remote-debugging-address=0.0.0.0 --remote-debugging-port=9223 about:blank"}

# Start Xvfb and supporting services for remote debugging
Xvfb "$DISPLAY" -screen 0 1280x720x24 &
x11vnc -display "$DISPLAY" -forever -shared -rfbport 5900 -nopw &
websockify --web=/usr/share/novnc 6080 localhost:5900 &

# Forward local CDP port to the Chromium remote debugging port
socat TCP-LISTEN:${CHROME_DEBUG_PORT},fork,bind=0.0.0.0 TCP:127.0.0.1:9223 &

# Start Chromium in the background
chromium $CHROMIUM_ARGS &

# Start the API server in the foreground
exec uvicorn app:app --host 0.0.0.0 --port 8000
