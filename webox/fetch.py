import gzip
import html.parser
import io
import logging
from typing import Dict, Optional

from webox.stealth_client import stealth_get

try:
    import trafilatura
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "Missing dependency: trafilatura. Install with: pip install trafilatura"
    ) from exc

try:
    from pypdf import PdfReader
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "Missing dependency: pypdf. Install with: pip install pypdf"
    ) from exc


logger = logging.getLogger("webox.fetch")


class UpstreamFetchError(RuntimeError):
    def __init__(self, status_code: int, url: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class ExtractionError(RuntimeError):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


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


def _extract_pdf_text(content_bytes: bytes) -> str:
    if not content_bytes:
        return ""
    reader = PdfReader(io.BytesIO(content_bytes))
    chunks = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text:
            chunks.append(text)
    return "\n\n".join(chunks).strip()


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
    redirect_chain = list(resp.redirect_chain or [])
    redirect_statuses = list(resp.redirect_statuses or [])
    if resp.status_code >= 400:
        logger.warning(
            "webox fetch upstream_error url=%s final_url=%s status=%s redirects=%s redirect_statuses=%s",
            url,
            resp.url,
            resp.status_code,
            redirect_chain,
            redirect_statuses,
        )
        raise UpstreamFetchError(
            resp.status_code,
            str(resp.url),
            f"Upstream HTTP error {resp.status_code} while fetching {resp.url}",
        )
    content_type = (
        (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
    )
    url_lower = str(resp.url).lower()
    is_pdf = content_type == "application/pdf" or url_lower.endswith(".pdf")
    is_xml = content_type in {
        "text/xml",
        "application/xml",
        "application/rss+xml",
        "application/atom+xml",
        "application/sitemap+xml",
    } or url_lower.endswith((".xml", ".xml.gz"))
    is_json = (
        content_type in {"application/json", "text/json"}
        or content_type.endswith("+json")
        or url_lower.endswith(".json")
    )
    content_encoding = (resp.headers.get("content-encoding") or "").lower()
    has_gzip_magic = resp.content[:2] == b"\x1f\x8b"
    looks_gzip = has_gzip_magic
    html = resp.text or ""
    if not is_xml and html:
        xml_prefix = html.lstrip()[:200].lower()
        if xml_prefix.startswith(("<?xml", "<rss", "<feed", "<urlset", "<sitemapindex")):
            is_xml = True
    if is_pdf:
        extracted = _extract_pdf_text(resp.content)
        if resp.content and not extracted:
            logger.warning(
                "webox fetch pdf_extraction_empty url=%s final_url=%s status=%s redirects=%s redirect_statuses=%s content_type=%s",
                url,
                resp.url,
                resp.status_code,
                redirect_chain,
                redirect_statuses,
                content_type,
            )
            raise ExtractionError("pdf_extraction_empty", "PDF text extraction produced no text")
        raw_text = extracted if include_raw_text else ""
        html = ""
    elif is_xml:
        content_bytes = resp.content or b""
        if url_lower.endswith(".gz") and not looks_gzip and content_bytes:
            logger.warning(
                "webox fetch gzip_hint_without_signature url=%s final_url=%s status=%s content_type=%s content_encoding=%s",
                url,
                resp.url,
                resp.status_code,
                content_type,
                content_encoding,
            )
        if ("gzip" in content_encoding) and not has_gzip_magic and content_bytes:
            logger.warning(
                "webox fetch gzip_encoding_without_signature url=%s final_url=%s status=%s content_type=%s content_encoding=%s",
                url,
                resp.url,
                resp.status_code,
                content_type,
                content_encoding,
            )
        if looks_gzip and content_bytes:
            try:
                content_bytes = gzip.decompress(content_bytes)
            except Exception as exc:
                logger.warning(
                    "webox fetch gzip_decompress_failed url=%s final_url=%s status=%s redirects=%s redirect_statuses=%s content_type=%s error=%s",
                    url,
                    resp.url,
                    resp.status_code,
                    redirect_chain,
                    redirect_statuses,
                    content_type,
                    str(exc),
                )
                raise ExtractionError("gzip_decompress_failed", "Failed to decompress gzip content") from exc
        xml_text = ""
        if content_bytes:
            xml_text = content_bytes.decode("utf-8", errors="replace")
        extracted = xml_text
        raw_text = xml_text if include_raw_text else ""
        html = ""
    elif is_json:
        json_text = resp.text or ""
        extracted = json_text
        raw_text = json_text if include_raw_text else ""
        html = ""
    else:
        extracted = _extract_trafilatura(html) if html else None
        if html and extracted is None:
            logger.warning(
                "webox fetch html_extraction_failed url=%s final_url=%s status=%s redirects=%s redirect_statuses=%s content_type=%s html_len=%s",
                url,
                resp.url,
                resp.status_code,
                redirect_chain,
                redirect_statuses,
                content_type,
                len(html),
            )
            extracted = ""
        raw_text = _to_text(html) if (include_raw_text and html) else ""
    return {
        "final_url": str(resp.url),
        "status_code": resp.status_code,
        "headers": dict(resp.headers),
        "redirect_chain": redirect_chain,
        "redirect_statuses": redirect_statuses,
        "content": extracted or "",
        "raw_text": raw_text,
        "html": html if include_raw else "",
        "stealth": {
            "browser_used": resp.browser_used,
            "tls_fingerprint": resp.tls_fingerprint,
        },
    }
