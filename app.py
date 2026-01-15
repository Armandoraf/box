import os

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from webox.fetch import ExtractionError, UpstreamFetchError, fetch
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
    _: None = Depends(_require_api_key),
):
    try:
        return fetch(url, timeout, {}, raw, raw_text)
    except UpstreamFetchError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "type": "upstream_http_error",
                    "message": str(exc),
                    "upstream_status": exc.status_code,
                    "url": exc.url,
                }
            },
        )
    except ExtractionError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "type": "extraction_error",
                    "message": str(exc),
                    "kind": exc.kind,
                }
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "type": "unexpected_error",
                    "message": str(exc),
                }
            },
        )


@app.get("/search")
def search_endpoint(
    q: str = Query(..., description="Search query"),
    _: None = Depends(_require_api_key),
):
    try:
        return search_google(q)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
