#!/usr/bin/env bash
set -euo pipefail

API=${API:-"http://127.0.0.1:8000"}
ROUTER=${ROUTER:-"http://127.0.0.1:8080"}
SLEEP=${SLEEP:-"0.2"}

sep() {
  echo "-----"
}

sep
printf "[1/6] Runner health... "
curl -fsS "${API}/health" >/dev/null && echo "ok"

sep
printf "[2/6] Fetch example... "
status=$(curl -s -o /tmp/box_fetch.json -w "%{http_code}" "${API}/fetch?url=https%3A%2F%2Fexample.com")
echo "status ${status}"

sep
printf "[3/6] Search example... "
status=$(curl -s -o /tmp/box_search.json -w "%{http_code}" "${API}/search?q=OpenAI")
echo "status ${status}"

sep
echo "[4/6] Router health..."
curl -fsS "${ROUTER}/health" | python -m json.tool

sep
echo "[5/6] Router search (queued test w/ 3 parallel)"
for i in 1 2 3; do
  curl -s -o "/tmp/box_router_search_${i}.json" -w "search ${i}: %{http_code}\n" "${ROUTER}/search?q=OpenAI" &
  sleep "$SLEEP"
done
wait

sep
echo "[6/6] Router fetch (round robin)"
for i in 1 2 3 4 5; do
  curl -s -o "/tmp/box_router_fetch_${i}.json" -w "fetch ${i}: %{http_code}\n" "${ROUTER}/fetch?url=https%3A%2F%2Fexample.com" &
  sleep "$SLEEP"
done
wait

sep
echo "Artifacts: /tmp/box_fetch.json /tmp/box_search.json /tmp/box_router_search_*.json /tmp/box_router_fetch_*.json"
