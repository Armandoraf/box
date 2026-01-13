# Infrastructure (GCP)

This directory contains a minimal Terraform setup to provision:
- 5 runner VMs with static external IPs
- 1 router VM
- External HTTP load balancer in front of the router
- Cloud Armor policy with API key enforcement and optional rate limiting

## Prereqs
- Terraform >= 1.5
- GCP project with billing
- `gcloud auth application-default login`

## Quick start
```bash
cd infra/terraform
terraform init
terraform apply \
  -var="project_id=YOUR_PROJECT_ID" \
  -var="runner_image=ghcr.io/armandoraf/box:latest" \
  -var="router_image=ghcr.io/armandoraf/box-router:latest" \
  -var="api_key=REPLACE_ME"
```

## Outputs
- `load_balancer_ip`: public IP for the router entrypoint (HTTP)
- `runner_external_ips`: static egress IPs for each runner

## Notes
- HTTPS: This config provisions HTTP only. To enable HTTPS, add a managed SSL cert and a target HTTPS proxy.
- Firewall: SSH is open to `0.0.0.0/0` by default. Set `allowed_ssh_cidrs` to your admin IP ranges.
- Cloud Armor: Requests must include the header defined by `api_key_header` (default `x-api-key`).

## Validation
- `curl http://<lb_ip>/health` should return router health
- `/search` should queue when all runners are busy
- `/fetch` should distribute across runners
