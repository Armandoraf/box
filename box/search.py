import json
import os
import urllib.parse
import urllib.request


def _json_get(url: str, headers: dict[str, str] | None = None) -> object:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _build_request_url(query: str, params: dict[str, str]) -> str:
    base = "https://customsearch.googleapis.com/customsearch/v1"
    qs = urllib.parse.urlencode({"q": query, **params})
    return f"{base}?{qs}"


def search_google(
    query: str,
) -> dict:
    api_key = _env("CUSTOM_SEARCH_API_KEY") or _env("CSE_API_KEY")
    cx = _env("CUSTOM_SEARCH_CX") or _env("CUSTOM_SEARCH_ENGINE_ID") or _env("CSE_CX")
    if not api_key or not cx:
        raise RuntimeError(
            "Custom Search credentials missing. Set CUSTOM_SEARCH_API_KEY and CUSTOM_SEARCH_CX."
        )

    params: dict[str, str] = {
        "key": api_key,
        "cx": cx,
    }

    num = _env("CUSTOM_SEARCH_NUM")
    if num:
        params["num"] = num

    start = _env("CUSTOM_SEARCH_START")
    if start:
        params["start"] = start

    gl = _env("CUSTOM_SEARCH_GL")
    if gl:
        params["gl"] = gl

    lr = _env("CUSTOM_SEARCH_LR")
    if lr:
        params["lr"] = lr

    safe = _env("CUSTOM_SEARCH_SAFE")
    if safe:
        params["safe"] = safe

    sort = _env("CUSTOM_SEARCH_SORT")
    if sort:
        params["sort"] = sort

    date_restrict = _env("CUSTOM_SEARCH_DATE_RESTRICT")
    if date_restrict:
        params["dateRestrict"] = date_restrict

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
