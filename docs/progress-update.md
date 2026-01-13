# Progress Update

Date: 2026-01-13

## Summary
- Provisioned GCP infra in project `web-searcher-2026` (region `us-west1`, zone `us-west1-a`).
- Deployed 5 runner VMs with static external IPs and 1 router VM.
- Created external HTTP load balancer and Cloud Armor policy with API key enforcement.
- Router now supports health-aware routing and retries; runner and router expose `/metrics` and JSON request logs.

## GCP Outputs
- Load balancer IP: `34.49.91.205`
- Router external IP (SSH/admin): `34.82.73.93`
- Runner external IPs (egress):
  - `35.197.101.50`
  - `34.127.105.254`
  - `136.109.132.159`
  - `34.168.236.2`
  - `34.169.188.79`

## Access
- Cloud Armor API key header: `x-api-key`
- API key value: `28355ce8d64a54bf65dee440184e58e9b8f914f5c8c6f710`

## Next Steps
- Run smoke checks against the load balancer for `/health`, `/fetch`, and `/search`.
- Verify `/metrics` endpoints on runner and router.
- Consider adding HTTPS (managed SSL cert + HTTPS proxy) if needed.
