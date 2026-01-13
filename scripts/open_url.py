#!/usr/bin/env python3
import sys
import os
import urllib.parse
import urllib.request


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: scripts/open_url.py <url>")
        return 2

    url = sys.argv[1]
    port = os.environ.get("CHROME_DEBUG_PORT", "9225")
    endpoint = f"http://localhost:{port}/json/new?" + urllib.parse.quote(url, safe="")

    try:
        req = urllib.request.Request(endpoint, method="PUT")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        print(body)
        return 0
    except Exception as exc:
        print(f"Failed to open URL via CDP: {exc}")
        print("Is the Chromium container running with remote debugging on port 9222?")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
