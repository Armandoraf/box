# Deployment Status (GCP Option A)

Date: 2026-01-13
Project: `web-searcher-2026`
Region: `us-west1`

## Summary
- Deployed **Option A**: 3 GCE runners with distinct egress IPs and a single HTTP load balancer entry point.
- Each runner runs FastAPI (`/fetch`, `/search`) + local Chromium (CDP on localhost).
- `/search` is serialized per runner to avoid CDP contention.
- Added a simple API key requirement via `X-API-Key` header.

## What we built
- **3 runners**:
  - `box-runner-1` (us-west1-a)
  - `box-runner-2` (us-west1-b)
  - `box-runner-3` (us-west1-c)
- **Load balancer**:
  - External HTTP LB
  - Health check `/healthz`
  - Rate-based balancing (`max-rate-per-instance=10`)
- **Firewall**:
  - Health check access to port 8080 from GCP LB ranges

## Endpoint
- Single entry point: HTTP LB IP (see `gcloud compute forwarding-rules describe box-http-rule --global`)

## Runtime notes / fixes applied
- Ubuntu 22.04 does not provide apt `chromium`; snap is required.
- Running Chromium via snap **requires root + XDG runtime**; we changed `chromium.service`:
  - `User=root`
  - `XDG_RUNTIME_DIR=/run/user/0`
  - `ExecStartPre=/bin/mkdir -p /run/user/0`
- `start-chromium.sh` was adjusted to:
  - Provide defaults if `CHROMIUM_ARGS` missing
  - Use snap Chromium if installed

## Current state
- Health checks are green for all 3 runners.
- `GET /healthz` via LB returns `{"ok":true}` when the API key is provided.

## Commands used (high-level)
- Reserve static IPs
- Create VMs with startup script
- Create unmanaged instance groups
- Configure health check + backend service
- Create URL map + target proxy + forwarding rule
- Set named ports to 8080 on instance groups

## Next steps
- Optional: move to HTTPS with a domain + managed cert
- Optional: migrate to Debian 12 or custom image to avoid root-run snap Chromium
- Optional: add SSRF protection to `/fetch`
