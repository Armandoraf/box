import os

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from webox.fetch import DEFAULT_USER_AGENT, build_headers, fetch
from webox.search import search_google

app = FastAPI(title="webox")
_API_KEY = os.environ.get("WEBOX_API_KEY", "")


def _require_api_key(x_api_key: str | None = Header(None)) -> None:
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/fetch")
def fetch_endpoint(
    url: str = Query(..., description="URL to fetch"),
    timeout: float = Query(20.0, ge=1.0, le=120.0),
    raw: bool = Query(False, description="Include raw HTML"),
    raw_text: bool = Query(False, description="Include raw text extraction"),
    user_agent: str = Query(DEFAULT_USER_AGENT),
    accept_language: str = Query("en-US,en;q=0.9"),
    _: None = Depends(_require_api_key),
):
    headers = build_headers(user_agent, accept_language)
    try:
        return fetch(url, timeout, headers, raw, raw_text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/search")
def search_endpoint(
    q: str = Query(..., description="Search query"),
    _: None = Depends(_require_api_key),
):
    try:
        return search_google(q)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
