#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-webox}"
REGION="${REGION:-sjc}"

if [[ ! -f .env ]]; then
  echo ".env not found. Create it with required variables before deploying." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if ! command -v flyctl >/dev/null 2>&1; then
  echo "flyctl not found. Install from https://fly.io/docs/flyctl/install/" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq not found. Please install jq to run this script." >&2
  exit 1
fi

missing=()
for key in WEBOX_API_KEY CUSTOM_SEARCH_API_KEY CUSTOM_SEARCH_CX; do
  if [[ -z "${!key:-}" ]]; then
    missing+=("$key")
  fi
done

if (( ${#missing[@]} )); then
  echo "Missing required env vars: ${missing[*]}" >&2
  echo "Export them, then re-run (e.g. export WEBOX_API_KEY=... )." >&2
  exit 1
fi

if ! flyctl apps list --json | jq -e --arg name "$APP_NAME" '.[] | select(.Name==$name)' >/dev/null; then
  flyctl apps create "$APP_NAME" --org personal
fi

deploy_args=(--app "$APP_NAME")
if [[ -n "${REGION:-}" ]]; then
  deploy_args+=(--primary-region "$REGION")
fi

flyctl deploy "${deploy_args[@]}"

flyctl secrets set \
  WEBOX_API_KEY="$WEBOX_API_KEY" \
  CUSTOM_SEARCH_API_KEY="$CUSTOM_SEARCH_API_KEY" \
  CUSTOM_SEARCH_CX="$CUSTOM_SEARCH_CX" \
  --app "$APP_NAME"

flyctl status --app "$APP_NAME"

# Ensure at least one machine is running after deploy.
machine_json="$(flyctl machines list --app "$APP_NAME" --json)"
machine_id="$(jq -r '.[0].id // empty' <<<"$machine_json")"
machine_state="$(jq -r '.[0].state // empty' <<<"$machine_json")"
if [[ -n "$machine_id" && "$machine_state" != "started" ]]; then
  flyctl machines start --app "$APP_NAME" "$machine_id"
fi
