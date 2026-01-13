# Implementation Progress

## Summary
- Single-container image now runs FastAPI + Chromium/Xvfb.
- Local build succeeds with Python dependencies installed in a venv.
- `/fetch` endpoint validated locally.
- `/search` endpoint responds (results empty in local run; likely consent/anti-bot).
- Added `/health` endpoint for router checks.
- Added structured JSON logging and `/metrics` endpoints for router and runner.
- Added health-aware routing with retries in the router.
- Added Terraform GCP provisioning for VMs, static IPs, LB, and Cloud Armor.

## Changes Made
- Added container entrypoint to start Xvfb, Chromium, CDP proxy, and uvicorn.
- Added Python dependencies file and venv setup in Dockerfile.
- Added `/health` endpoint in `app.py`.
- Added `/search` concurrency lock (capacity = 1 per runner).
- Implemented `/fetch` per-host throttling and jittered backoff.
- Added router service skeleton (health checks, runner registry, queue).
- Added deployment bootstrap for GCP VMs (systemd + Docker).
- Added router health-aware routing with retries/backoff and runner exclusion.
- Added JSON request logs and Prometheus-format `/metrics` endpoints.
- Added Terraform config for VPC, static IPs, VMs, LB, and Cloud Armor.

## Local Smoke Test
- Build: `docker build -t box-local .`
- Run: `docker run -d --rm --name box-local-test -p 8000:8000 -p 9226:9225 box-local`
- Fetch: `GET /fetch?url=https%3A%2F%2Fexample.com` -> HTTP 200 with content.
- Search: `GET /search?q=OpenAI` -> HTTP 200, results empty.
- Concurrency lock: with `SEARCH_LOCK_TIMEOUT=0.1` and 10 parallel `/search` calls, observed 1x `200`, 9x `429`.

## Open Items
- Decide whether to implement Google consent handling or CDP request blocking.
- Validate /fetch throttle defaults under load.

## Next-Step Checklist
- Add `/search` concurrency lock (capacity = 1 per runner). (done)
- Implement `/fetch` per-host throttling and jittered backoff. (done)
- Add router service skeleton (health checks, runner registry, queue). (done)
- Add deployment bootstrap for GCP VMs (systemd + Docker). (done)
- Add router health-aware routing with retries/backoff. (done)
- Add observability (logs + metrics). (done)
- Add GCP provisioning (Terraform). (done)
- Run next-steps smoke checklist.
