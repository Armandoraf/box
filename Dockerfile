FROM debian:bookworm-slim

# Keep image small; Chromium + Xvfb + fonts + Python runtime
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
       chromium \
       xvfb \
       python3 \
       python3-pip \
       python3-venv \
       ca-certificates \
       fonts-liberation \
       fonts-noto-color-emoji \
       socat \
       x11vnc \
       novnc \
       websockify \
       dumb-init \
  && rm -rf /var/lib/apt/lists/*

ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1

# Default args; override at runtime if needed
ENV CHROMIUM_ARGS="--no-sandbox --disable-gpu --disable-dev-shm-usage --display=:99 --remote-debugging-address=0.0.0.0 --remote-debugging-port=9223 about:blank"

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python3 -m venv /opt/venv \
  && /opt/venv/bin/pip install --no-cache-dir -r /app/requirements.txt

ENV PATH="/opt/venv/bin:${PATH}"

COPY app.py /app/app.py
COPY router_app.py /app/router_app.py
COPY box /app/box
COPY bin/entrypoint.sh /app/bin/entrypoint.sh

EXPOSE 8000 9225 5900 6080

# Start Xvfb, Chromium, and API server
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/app/bin/entrypoint.sh"]
