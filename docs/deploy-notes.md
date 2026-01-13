# Deploy Notes (2026-01-13)

## Status Summary
- GCP infrastructure is provisioned in project `web-searcher-2026` (region `us-west1`, zone `us-west1-a`).
- Load balancer and VM fleet exist, but services are not running because container images are not accessible.

## Key Findings
- Router and runners fail to start due to container pull errors:
  - `docker: Error response from daemon: Head "https://ghcr.io/v2/armandoraf/box/manifests/latest": denied.`
  - Same for `ghcr.io/armandoraf/box-router:latest`.
- GHCR packages do not exist under the user account:
  - `gh api /user/packages?package_type=container` returned `count 0`.
- GitHub Actions workflow `ghcr-build.yml` fails immediately without running steps:
  - Run `20953137397` completed with `failure` in ~4 seconds.
  - Logs only show runner provisioning; no build steps executed.
  - Likely cause: Actions minutes exhausted for a private repo or billing/permissions issue.

## Current GCP Outputs
- Load balancer IP: `34.49.91.205`
- Router external IP: `34.82.73.93`
- Runner external IPs (egress):
  - `35.197.101.50`
  - `34.127.105.254`
  - `136.109.132.159`
  - `34.168.236.2`
  - `34.169.188.79`

## Next Options
1) Use GCP Artifact Registry + Cloud Build (recommended).
2) Make the repo public so Actions can run and publish to GHCR.
3) Fix GitHub Actions billing/limits for private repo builds.
4) Push images from local if large layers succeed.

## Notes
- Terraform defaults now point to:
  - `ghcr.io/armandoraf/box:latest`
  - `ghcr.io/armandoraf/box-router:latest`
