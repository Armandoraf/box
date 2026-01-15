"""
High-stealth HTTP client utilities.

Always uses TLS fingerprint impersonation via curl_cffi and realistic
browser headers with User-Agent rotation.
"""

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

try:
    from curl_cffi import requests
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "Missing dependency: curl_cffi. Install with: pip install curl_cffi"
    ) from exc


class BrowserType(Enum):
    CHROME_WIN = "chrome_win"
    CHROME_MAC = "chrome_mac"
    CHROME_LINUX = "chrome_linux"
    FIREFOX_WIN = "firefox_win"
    FIREFOX_MAC = "firefox_mac"
    SAFARI_MAC = "safari_mac"
    EDGE_WIN = "edge_win"
    CHROME_ANDROID = "chrome_android"
    SAFARI_IOS = "safari_ios"


@dataclass
class StealthResponse:
    status_code: int
    text: str
    headers: Dict[str, str]
    url: str
    browser_used: str
    tls_fingerprint: str
    content: bytes = b""
    content_encoding: str = ""
    redirect_chain: List[str] = field(default_factory=list)
    redirect_statuses: List[int] = field(default_factory=list)


USER_AGENTS = {
    BrowserType.CHROME_WIN: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    ],
    BrowserType.CHROME_MAC: [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    ],
    BrowserType.CHROME_LINUX: [
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    ],
    BrowserType.FIREFOX_WIN: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
    ],
    BrowserType.FIREFOX_MAC: [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0",
    ],
    BrowserType.SAFARI_MAC: [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    ],
    BrowserType.EDGE_WIN: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.0.0 Safari/537.36 Edg/101.0.0.0",
    ],
    BrowserType.CHROME_ANDROID: [
        "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    ],
    BrowserType.SAFARI_IOS: [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Mobile/15E148 Safari/604.1",
    ],
}

TLS_FINGERPRINTS = {
    BrowserType.CHROME_WIN: "chrome136",
    BrowserType.CHROME_MAC: "chrome136",
    BrowserType.CHROME_LINUX: "chrome136",
    BrowserType.FIREFOX_WIN: "firefox135",
    BrowserType.FIREFOX_MAC: "firefox135",
    BrowserType.SAFARI_MAC: "safari184",
    BrowserType.EDGE_WIN: "edge101",
    BrowserType.CHROME_ANDROID: "chrome131_android",
    BrowserType.SAFARI_IOS: "safari184_ios",
}


def _select_browser() -> Tuple[BrowserType, str]:
    weights = {
        BrowserType.CHROME_WIN: 35,
        BrowserType.CHROME_MAC: 20,
        BrowserType.FIREFOX_WIN: 10,
        BrowserType.FIREFOX_MAC: 5,
        BrowserType.SAFARI_MAC: 10,
        BrowserType.EDGE_WIN: 10,
        BrowserType.CHROME_ANDROID: 5,
        BrowserType.SAFARI_IOS: 5,
    }
    browser_type = random.choices(
        list(weights.keys()),
        weights=list(weights.values()),
        k=1,
    )[0]
    user_agent = random.choice(USER_AGENTS[browser_type])
    return browser_type, user_agent


def _headers_for_browser(browser_type: BrowserType, user_agent: str) -> Dict[str, str]:
    base_headers = {
        "User-Agent": user_agent,
        "Accept-Language": random.choice([
            "en-US,en;q=0.9",
            "en-US,en;q=0.9,es;q=0.8",
            "en-GB,en;q=0.9,en-US;q=0.8",
        ]),
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    if browser_type in {
        BrowserType.CHROME_WIN,
        BrowserType.CHROME_MAC,
        BrowserType.CHROME_LINUX,
        BrowserType.CHROME_ANDROID,
    }:
        base_headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?1" if "Android" in user_agent else "?0",
            "sec-ch-ua-platform": (
                '"Windows"' if "Windows" in user_agent else '"macOS"' if "Mac" in user_agent else '"Linux"'
            ),
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        })
    elif browser_type in {BrowserType.FIREFOX_WIN, BrowserType.FIREFOX_MAC}:
        base_headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        })
    elif browser_type in {BrowserType.SAFARI_MAC, BrowserType.SAFARI_IOS}:
        base_headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
    elif browser_type == BrowserType.EDGE_WIN:
        base_headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        })

    return base_headers


def _randomize_header_order(headers: Dict[str, str]) -> Dict[str, str]:
    items = list(headers.items())
    random.shuffle(items)
    return dict(items)


def stealth_get(
    url: str,
    timeout: float = 30.0,
    follow_redirects: bool = True,
    extra_headers: Optional[Dict[str, str]] = None,
) -> StealthResponse:
    browser_type, user_agent = _select_browser()
    headers = _headers_for_browser(browser_type, user_agent)
    if extra_headers:
        headers.update(extra_headers)
    headers = _randomize_header_order(headers)

    fingerprint = TLS_FINGERPRINTS.get(browser_type, "chrome120")

    with requests.Session() as session:
        response = session.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=follow_redirects,
            impersonate=fingerprint,
        )

    history = getattr(response, "history", []) or []
    redirect_chain = [str(item.url) for item in history if getattr(item, "url", None)]
    redirect_statuses = [
        item.status_code for item in history if getattr(item, "status_code", None)
    ]

    return StealthResponse(
        status_code=response.status_code,
        text=response.text,
        headers=dict(response.headers),
        url=str(response.url),
        browser_used=browser_type.value,
        tls_fingerprint=fingerprint,
        content=response.content,
        content_encoding=response.headers.get("content-encoding", ""),
        redirect_chain=redirect_chain,
        redirect_statuses=redirect_statuses,
    )
