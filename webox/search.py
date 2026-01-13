import json
import os
import urllib.parse
import urllib.request

from dotenv import load_dotenv

load_dotenv()

def _json_get(url: str, headers: dict[str, str] | None = None) -> object:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _build_request_url(query: str, params: dict[str, str]) -> str:
    base = "https://customsearch.googleapis.com/customsearch/v1"
    qs = urllib.parse.urlencode({"q": query, **params})
    return f"{base}?{qs}"


def search_google(
    query: str,
) -> dict:
    api_key = os.getenv("CUSTOM_SEARCH_API_KEY")
    cx = os.getenv("CUSTOM_SEARCH_CX")
    if not api_key or not cx:
        raise RuntimeError(
            "Custom Search credentials missing. Set CUSTOM_SEARCH_API_KEY and CUSTOM_SEARCH_CX."
        )

    params: dict[str, str] = {
        "key": api_key,
        "cx": cx,
    }

    optional_params = {
        "num": "CUSTOM_SEARCH_NUM",
        "start": "CUSTOM_SEARCH_START",
        "gl": "CUSTOM_SEARCH_GL",
        "lr": "CUSTOM_SEARCH_LR",
        "safe": "CUSTOM_SEARCH_SAFE",
        "sort": "CUSTOM_SEARCH_SORT",
        "dateRestrict": "CUSTOM_SEARCH_DATE_RESTRICT",
    }
    for key, env_name in optional_params.items():
        value = os.getenv(env_name)
        if value:
            params[key] = value

    url = _build_request_url(query, params)
    data = _json_get(url)

    if isinstance(data, dict) and data.get("error"):
        error = data["error"]
        code = error.get("code", "?")
        message = error.get("message", "Unknown error")
        raise RuntimeError(f"Custom Search API error ({code}): {message}")

    results: list[dict] = []
    if isinstance(data, dict):
        for item in data.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip()
            link = (item.get("link") or "").strip()
            snippet = (item.get("snippet") or "").strip()
            if title and link:
                results.append({"title": title, "link": link, "snippet": snippet})

    public_params = {k: v for k, v in params.items() if k != "key"}
    public_url = _build_request_url(query, public_params)
    return {"query": query, "url": public_url, "results": results}
