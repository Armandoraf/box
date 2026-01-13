#!/usr/bin/env python3
import argparse
import html.parser
import json
import sys
from typing import Dict, Optional

try:
    from stealth_client import stealth_get
except Exception as exc:  # pragma: no cover
    print(str(exc), file=sys.stderr)
    raise SystemExit(1) from exc

try:
    import trafilatura
except Exception as exc:  # pragma: no cover
    print(
        "Missing dependency: trafilatura. Install with: pip install trafilatura",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


class _TextExtractor(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._chunks.append(text)

    def get_text(self) -> str:
        return "\n".join(self._chunks)


def _to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.get_text()


def _extract_trafilatura(html: str) -> Optional[str]:
    return trafilatura.extract(
        html,
        include_links=True,
        include_images=False,
        include_tables=False,
        output_format="txt",
    )


def fetch(
    url: str,
    timeout: float,
    headers: Dict[str, str],
    include_raw: bool,
    include_raw_text: bool,
) -> Dict[str, object]:
    resp = stealth_get(url, timeout=timeout, extra_headers=headers)
    html = resp.text or ""
    extracted = _extract_trafilatura(html) if html else None
    raw_text = _to_text(html) if (include_raw_text and html) else ""
    return {
        "final_url": str(resp.url),
        "status_code": resp.status_code,
        "headers": dict(resp.headers),
        "content": extracted or "",
        "raw_text": raw_text,
        "html": html if include_raw else "",
        "stealth": {
            "browser_used": resp.browser_used,
            "tls_fingerprint": resp.tls_fingerprint,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch a URL via high-stealth HTTP (curl_cffi) and return JSON."
    )
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--accept-language", default="en-US,en;q=0.9")
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Include raw HTML in output (disabled by default).",
    )
    parser.add_argument(
        "--raw-text",
        action="store_true",
        help="Include raw text extraction in output (disabled by default).",
    )
    parser.add_argument(
        "--user-agent",
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    args = parser.parse_args()

    headers = {
        "User-Agent": args.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": args.accept_language,
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        payload = fetch(args.url, args.timeout, headers, args.raw, args.raw_text)
    except Exception as exc:
        print(json.dumps({"error": str(exc), "url": args.url}), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
