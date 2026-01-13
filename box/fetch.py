import html.parser
import os
import random
import threading
import time
import urllib.parse
from typing import Dict, Optional

from box.stealth_client import stealth_get

try:
    import trafilatura
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "Missing dependency: trafilatura. Install with: pip install trafilatura"
    ) from exc

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class FetchCapacityError(RuntimeError):
    pass


_FETCH_MAX_INFLIGHT = max(1, int(os.getenv("FETCH_MAX_INFLIGHT", "15")))
_FETCH_HOST_MAX_INFLIGHT = max(1, int(os.getenv("FETCH_HOST_MAX_INFLIGHT", "3")))
_FETCH_ACQUIRE_TIMEOUT = float(os.getenv("FETCH_ACQUIRE_TIMEOUT", "5"))
_FETCH_MAX_RETRIES = max(0, int(os.getenv("FETCH_MAX_RETRIES", "2")))
_FETCH_BACKOFF_BASE = float(os.getenv("FETCH_BACKOFF_BASE", "0.5"))
_FETCH_BACKOFF_CAP = float(os.getenv("FETCH_BACKOFF_CAP", "6"))

_FETCH_SEMAPHORE = threading.BoundedSemaphore(value=_FETCH_MAX_INFLIGHT)
_HOST_SEMAPHORE_LOCK = threading.Lock()
_HOST_SEMAPHORES: Dict[str, threading.BoundedSemaphore] = {}


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


def _get_host_semaphore(host: str) -> threading.BoundedSemaphore:
    with _HOST_SEMAPHORE_LOCK:
        semaphore = _HOST_SEMAPHORES.get(host)
        if not semaphore:
            semaphore = threading.BoundedSemaphore(value=_FETCH_HOST_MAX_INFLIGHT)
            _HOST_SEMAPHORES[host] = semaphore
        return semaphore


def _sleep_backoff(attempt: int) -> None:
    base = min(_FETCH_BACKOFF_CAP, _FETCH_BACKOFF_BASE * (2 ** attempt))
    time.sleep(random.uniform(0, base))


def build_headers(user_agent: str, accept_language: str) -> Dict[str, str]:
    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": accept_language,
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def fetch(
    url: str,
    timeout: float,
    headers: Dict[str, str],
    include_raw: bool,
    include_raw_text: bool,
) -> Dict[str, object]:
    host = urllib.parse.urlparse(url).netloc or "unknown"
    if not _FETCH_SEMAPHORE.acquire(timeout=_FETCH_ACQUIRE_TIMEOUT):
        raise FetchCapacityError("Fetch capacity full. Try again.")
    host_semaphore = _get_host_semaphore(host)
    if not host_semaphore.acquire(timeout=_FETCH_ACQUIRE_TIMEOUT):
        _FETCH_SEMAPHORE.release()
        raise FetchCapacityError("Fetch host capacity full. Try again.")

    try:
        resp = None
        last_exc: Exception | None = None
        attempt = 0
        while True:
            try:
                resp = stealth_get(url, timeout=timeout, extra_headers=headers)
            except Exception as exc:  # pragma: no cover - retry for transient network issues
                last_exc = exc
                if attempt >= _FETCH_MAX_RETRIES:
                    raise
                _sleep_backoff(attempt)
                attempt += 1
                continue

            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt >= _FETCH_MAX_RETRIES:
                    break
                _sleep_backoff(attempt)
                attempt += 1
                continue
            break

        if resp is None and last_exc:
            raise last_exc

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
            "retries": attempt,
        }
    finally:
        host_semaphore.release()
        _FETCH_SEMAPHORE.release()
