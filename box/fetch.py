import html.parser
from typing import Dict, Optional

from box.stealth_client import stealth_get

try:
    import trafilatura
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "Missing dependency: trafilatura. Install with: pip install trafilatura"
    ) from exc


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
    # Avoid overriding stealth client UA and browser fingerprint headers.
    blocked = {
        "User-Agent",
        "Accept",
        "Accept-Language",
        "Accept-Encoding",
        "DNT",
        "Connection",
        "Upgrade-Insecure-Requests",
        "Sec-Fetch-Dest",
        "Sec-Fetch-Mode",
        "Sec-Fetch-Site",
        "Sec-Fetch-User",
        "sec-ch-ua",
        "sec-ch-ua-mobile",
        "sec-ch-ua-platform",
    }
    extra_headers = {k: v for k, v in headers.items() if k not in blocked}
    resp = stealth_get(url, timeout=timeout, extra_headers=extra_headers or None)
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
