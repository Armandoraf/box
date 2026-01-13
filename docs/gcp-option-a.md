# GCP Option A (3 runners + LB)

This deployment targets three Compute Engine VMs with distinct static egress IPs and a single external HTTP(S) Load Balancer. Each VM runs Chromium (CDP on localhost) and the FastAPI app with `/search` serialized per runner.

## Summary
- 3 GCE VMs (one per zone in `us-west1`), each with its own static external IP
- App + Chromium on the same VM (systemd services)
- External HTTP(S) Load Balancer -> unmanaged instance group
- Health check on `/healthz` (port 8080)
- Simple auth via `X-API-Key` header (set `BOX_API_KEY`)

## Prereqs
- `gcloud` authenticated
- A repo URL reachable by the VMs (set `REPO_URL` in the startup script metadata)

## 1) Reserve static IPs (egress per runner)
```bash
PROJECT_ID=your-project
REGION=us-west1

gcloud config set project "$PROJECT_ID"

gcloud compute addresses create box-runner-1-ip --region "$REGION"
gcloud compute addresses create box-runner-2-ip --region "$REGION"
gcloud compute addresses create box-runner-3-ip --region "$REGION"
```

## 2) Create the VMs (3 runners)
```bash
REGION=us-west1
ZONES=(us-west1-a us-west1-b us-west1-c)
MACHINE_TYPE=e2-standard-4
IMAGE_FAMILY=ubuntu-2204-lts
IMAGE_PROJECT=ubuntu-os-cloud
REPO_URL=https://your.git.repo/box.git
GIT_REF=main

for i in 1 2 3; do
  ZONE=${ZONES[$((i-1))]}
  IP_NAME=box-runner-${i}-ip
  IP_ADDR=$(gcloud compute addresses describe "$IP_NAME" --region "$REGION" --format='value(address)')

  gcloud compute instances create box-runner-$i \
    --zone "$ZONE" \
    --machine-type "$MACHINE_TYPE" \
    --image-family "$IMAGE_FAMILY" \
    --image-project "$IMAGE_PROJECT" \
    --address "$IP_ADDR" \
    --tags box-runner \
    --metadata-from-file startup-script=deploy/gcp/startup.sh \
    --metadata REPO_URL="$REPO_URL",GIT_REF="$GIT_REF"

done
```

## 3) Firewall rules (only allow LB + health checks)
```bash
# Allow health checks + LB to reach port 8080
# Google LB health check ranges:
# 35.191.0.0/16 and 130.211.0.0/22

gcloud compute firewall-rules create box-allow-healthcheck \
  --direction=INGRESS \
  --priority=1000 \
  --network=default \
  --action=ALLOW \
  --rules=tcp:8080 \
  --source-ranges=35.191.0.0/16,130.211.0.0/22 \
  --target-tags=box-runner
```

## 4) Create unmanaged instance groups (one per zone)
```bash
REGION=us-west1

gcloud compute instance-groups unmanaged create box-runners-ig-a --zone us-west1-a
gcloud compute instance-groups unmanaged create box-runners-ig-b --zone us-west1-b
gcloud compute instance-groups unmanaged create box-runners-ig-c --zone us-west1-c

gcloud compute instance-groups unmanaged add-instances box-runners-ig-a \
  --zone us-west1-a \
  --instances box-runner-1

gcloud compute instance-groups unmanaged add-instances box-runners-ig-b \
  --zone us-west1-b \
  --instances box-runner-2

gcloud compute instance-groups unmanaged add-instances box-runners-ig-c \
  --zone us-west1-c \
  --instances box-runner-3
```

## 5) Create health check and backend service
```bash
REGION=us-west1

gcloud compute health-checks create http box-hc \
  --port 8080 \
  --request-path /healthz

# Rate-based balancing, "even enough" distribution

gcloud compute backend-services create box-backend \
  --protocol HTTP \
  --health-checks box-hc \
  --global

gcloud compute backend-services add-backend box-backend \
  --instance-group box-runners-ig-a \
  --instance-group-zone us-west1-a \
  --balancing-mode RATE \
  --max-rate-per-instance 20 \
  --global

gcloud compute backend-services add-backend box-backend \
  --instance-group box-runners-ig-b \
  --instance-group-zone us-west1-b \
  --balancing-mode RATE \
  --max-rate-per-instance 20 \
  --global

gcloud compute backend-services add-backend box-backend \
  --instance-group box-runners-ig-c \
  --instance-group-zone us-west1-c \
  --balancing-mode RATE \
  --max-rate-per-instance 20 \
  --global
```

## 6) URL map, target proxy, forwarding rule
```bash
# HTTP only (upgrade to HTTPS if you add a cert)

gcloud compute url-maps create box-url-map --default-service box-backend

gcloud compute target-http-proxies create box-http-proxy --url-map box-url-map

gcloud compute forwarding-rules create box-http-rule \
  --global \
  --target-http-proxy box-http-proxy \
  --ports 80
```

## 7) Set API key (simplest auth)
SSH to each VM and edit `/etc/box/box.env`:
```bash
BOX_API_KEY=your-strong-key
CHROME_BLOCK_MEDIA=1
```
Then restart:
```bash
sudo systemctl restart box.service
```

## Notes
- `/search` is serialized per VM via a lock; keep `uvicorn --workers 1`.
- CDP is bound to localhost only, so it is not exposed externally.
- Consider adding an HTTPS cert to the LB if the endpoint is internet-facing.
