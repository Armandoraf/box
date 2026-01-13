from fastapi import FastAPI, HTTPException, Query

from box.fetch import DEFAULT_USER_AGENT, build_headers, fetch
from box.search import search_google

app = FastAPI(title="box")


@app.get("/fetch")
def fetch_endpoint(
    url: str = Query(..., description="URL to fetch"),
    timeout: float = Query(20.0, ge=1.0, le=120.0),
    raw: bool = Query(False, description="Include raw HTML"),
    raw_text: bool = Query(False, description="Include raw text extraction"),
    user_agent: str = Query(DEFAULT_USER_AGENT),
    accept_language: str = Query("en-US,en;q=0.9"),
):
    headers = build_headers(user_agent, accept_language)
    try:
        return fetch(url, timeout, headers, raw, raw_text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/search")
def search_endpoint(
    q: str = Query(..., description="Search query"),
    news: bool = Query(False, description="Use Google News"),
    chrome_debug_port: int = Query(9225, ge=1, le=65535),
):
    try:
        return search_google(q, news=news, chrome_debug_port=chrome_debug_port)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
