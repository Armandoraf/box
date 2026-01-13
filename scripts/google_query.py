#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import urllib.parse
import urllib.request

import websockets


def _json_get(url: str) -> object:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


async def _navigate(ws_url: str, url: str) -> None:
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": url}}))
        # Wait for the response to our request id
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1:
                return


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: scripts/google_query.py <query>")
        return 2

    query = " ".join(sys.argv[1:])
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)

    port = os.environ.get("CHROME_DEBUG_PORT", "9225")
    list_url = f"http://localhost:{port}/json/list"

    try:
        targets = _json_get(list_url)
    except Exception as exc:
        print(f"Failed to query CDP targets: {exc}")
        print("Is the Chromium container running with remote debugging enabled?")
        return 1

    page = next((t for t in targets if t.get("type") == "page"), None)
    if not page or not page.get("webSocketDebuggerUrl"):
        print("No existing page target found. Open a tab first.")
        return 1

    try:
        asyncio.run(_navigate(page["webSocketDebuggerUrl"], url))
        print(f"Navigated current tab to: {url}")
        return 0
    except Exception as exc:
        print(f"Failed to navigate current tab via CDP: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
