FROM debian:bookworm-slim

# Keep image small; Chromium + Xvfb + fonts
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
       chromium \
       xvfb \
       ca-certificates \
       fonts-liberation \
       fonts-noto-color-emoji \
       socat \
       iproute2 \
       dumb-init \
  && rm -rf /var/lib/apt/lists/*

ENV DISPLAY=:99

# Default args; override at runtime if needed
ENV CHROMIUM_ARGS="--no-sandbox --disable-gpu --disable-dev-shm-usage --display=:99 --remote-debugging-address=0.0.0.0 --remote-debugging-port=9223 about:blank"

# Start Xvfb and Chromium in the foreground
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["bash", "-lc", "Xvfb :99 -screen 0 1280x720x24 & socat TCP-LISTEN:9222,fork,bind=0.0.0.0 TCP:127.0.0.1:9223 & exec chromium $CHROMIUM_ARGS"]
