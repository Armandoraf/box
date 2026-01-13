FROM debian:bookworm-slim

ARG DEBUG_IMAGE=0
ARG INCLUDE_NOVNC=0

# Keep image small; debug deps are optional.
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
       chromium \
       ca-certificates \
       fonts-liberation \
       socat \
       dumb-init \
  && if [ "$DEBUG_IMAGE" = "1" ]; then \
       apt-get install -y --no-install-recommends \
         xvfb \
         x11vnc; \
     fi \
  && if [ "$INCLUDE_NOVNC" = "1" ]; then \
       apt-get install -y --no-install-recommends \
         novnc \
         websockify; \
     fi \
  && rm -rf /var/lib/apt/lists/* \
  && rm -rf /usr/share/doc /usr/share/man /usr/share/info /usr/share/locale /usr/share/icons

# Default args; override at runtime if needed
ENV CHROMIUM_ARGS="--no-sandbox --disable-gpu --disable-dev-shm-usage --disable-blink-features=AutomationControlled --disable-features=IsolateOrigins,site-per-process --remote-debugging-address=0.0.0.0 --remote-debugging-port=9223 about:blank"
ENV CHROMIUM_ARGS_DEBUG="--no-sandbox --disable-gpu --disable-dev-shm-usage --disable-blink-features=AutomationControlled --disable-features=IsolateOrigins,site-per-process --display=:99 --remote-debugging-address=0.0.0.0 --remote-debugging-port=9223 about:blank"
ENV DEBUG=0
ENV ENABLE_NOVNC=

COPY bin/start-chromium.sh /usr/local/bin/start-chromium

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/usr/local/bin/start-chromium"]
