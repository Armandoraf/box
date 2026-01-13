#!/usr/bin/env python3
import sys
import urllib.parse
import urllib.request


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: scripts/open_url.py <url>")
        return 2

    url = sys.argv[1]
    endpoint = "http://localhost:9222/json/new?" + urllib.parse.quote(url, safe="")

    try:
        with urllib.request.urlopen(endpoint, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        print(body)
        return 0
    except Exception as exc:
        print(f"Failed to open URL via CDP: {exc}")
        print("Is the Chromium container running with remote debugging on port 9222?")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
