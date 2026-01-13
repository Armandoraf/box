# Deployment Plan (GCP + VMs, 5 Egress IPs)

## Goals
- Single public entrypoint for `/search` and `/fetch`.
- Exactly 5 runners, each with its own fixed egress IP.
- `/search` concurrency capped at 1 per runner, with queueing when all 5 are busy.
- `/fetch` distributed evenly with per-host throttling to reduce upstream rate limits.
- Simple, deterministic operations on GCP using VMs.

---

## Topology

```
Client
  |
  v
Cloud HTTP(S) Load Balancer (TLS, WAF/rate limits)
  |
  v
Router Service (stateless)
  |
  +-- /search -> least-busy runner, enqueue when all busy
  |
  +-- /fetch  -> round-robin / least-connections
  |
  v
Runner Pool (5 VMs, each with its own static external IP)
  - Single container per VM: FastAPI + Chromium + Xvfb
  - Local CDP on 127.0.0.1:9225
```

---

## Components

### 1) Router service
- Purpose: single public API entrypoint and smart routing to runners.
- Stateless; maintains a small in-memory state of runner capacity.
- `/search` routing: pick any runner with `active_searches == 0`.
- If all 5 are busy: enqueue request (FIFO). If queue is full, return 429.
- `/fetch` routing: round-robin or least-connections.
- Health checks to each runner (e.g., `GET /health`).

### 2) Runner VM (x5)
- One VM = one static external IP.
- One container on each VM that runs:
  - FastAPI app (`app.py`) for `/search` and `/fetch`.
  - Chromium + Xvfb locally (CDP at 127.0.0.1:9225).

### 3) Load balancer + WAF
- Cloud HTTP(S) Load Balancer in front of Router.
- Cloud Armor:
  - API key enforcement
  - Basic per-key rate limits
  - Optional IP allowlist

---

## Networking / Egress IPs

- Each runner is a VM with its own static external IP.
- Egress IP is the VM’s external IP (no Cloud NAT needed).
- Ensure static external IPs are reserved so they do not change.

---

## Concurrency and Rate Limiting

### `/search`
- Enforce a per-runner lock (capacity = 1).
- Router queue for overflow. Suggested defaults:
  - Max queue length: 50
  - Max wait time: 60s, then 429

### `/fetch`
- Per-runner max concurrency: 10–20 in flight.
- Per-host (origin) limit: 2–4 in flight.
- Jittered exponential backoff on 429/5xx.

---

## Container Runtime (single container per VM)

The container should start both:
- FastAPI app server (uvicorn)
- Chromium + Xvfb

Recommended approach:
- Use `dumb-init` or `tini` and a small process supervisor (e.g., `supervisord`) to manage both.
- Keep CDP bound to `127.0.0.1:9225`.

---

## VM Sizing (baseline)

Start with:
- `e2-small` or `e2-medium` per runner VM
- 10–20 GB boot disk

Scale up if:
- CPU becomes the bottleneck during concurrent `/fetch`.
- Chromium becomes sluggish on `/search`.

---

## Observability

Minimum metrics:
- Router: request rate, queue depth, queue wait time, per-runner in-flight counts.
- Runner: `/search` duration, `/fetch` duration, error rates, status codes.
- Egress: bytes out per runner (alerts if spiking).

Logs:
- Store request metadata (timestamp, endpoint, runner, status, duration, size).
- Avoid logging full page contents unless necessary.

---

## Deployment Steps (high level)

1) Build container image that runs FastAPI + Chromium/Xvfb.
2) Provision 5 VMs with static external IPs.
3) Deploy the container to each VM (systemd or Docker).
4) Deploy Router service (VM or managed service).
5) Configure Cloud HTTP(S) Load Balancer to route to Router.
6) Configure Cloud Armor (API keys + basic rate limits).
7) Validate:
   - `/search` routes to only idle runner, queue works under load.
   - `/fetch` distributes evenly across runners.
   - Each runner shows unique egress IP.

---

## Validation Checklist

- `curl` from each runner shows unique external IP.
- `/search` concurrency never exceeds 1 per runner.
- Router queue rejects after max wait.
- `/fetch` distribution roughly even (check logs).
- Upstream rate-limit errors are under control (429s trending down).

---

## Future Enhancements

- Add per-domain caching for `/fetch` results.
- Add automatic runner health replacement (recreate VM on failure).
- Consider per-runner Chromium profiles to reduce consent flows.
