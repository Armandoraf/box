#!/usr/bin/env python3
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    if len(sys.argv) != 2:
        print("Usage: scripts/fetch_via_fly.py <url>", file=sys.stderr)
        return 2

    target_url = sys.argv[1]
    base = os.environ.get("WEBOX_BASE_URL", "https://webox.fly.dev")
    endpoint = urllib.parse.urljoin(base.rstrip("/") + "/", "fetch")
    query = urllib.parse.urlencode({"url": target_url})
    request_url = f"{endpoint}?{query}"

    headers = {"Accept": "application/json"}
    api_key = os.environ.get("WEBOX_API_KEY", "")
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(request_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 401 and not api_key:
            print(
                "Unauthorized (401). WEBOX_API_KEY is not set. "
                "Add it to .env or export it before running.",
                file=sys.stderr,
            )
        raise
    try:
        data = json.loads(body)
        print(json.dumps(data, indent=2, sort_keys=True))
    except json.JSONDecodeError:
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
