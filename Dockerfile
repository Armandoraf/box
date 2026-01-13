FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY webox ./webox

ENV PORT=8080

EXPOSE 8080

CMD ["sh", "-c", "gunicorn app:app -k uvicorn.workers.UvicornWorker --bind [::]:${PORT}"]
