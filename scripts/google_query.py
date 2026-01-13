#!/usr/bin/env python3
import subprocess
import sys
import urllib.parse


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: scripts/google_query.py <query>")
        return 2

    query = " ".join(sys.argv[1:])
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)

    try:
        return subprocess.call([sys.executable, "scripts/open_url.py", url])
    except FileNotFoundError:
        print("Could not find scripts/open_url.py")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
