import json
import logging
import os
import threading
import time
import uuid

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from box.fetch import DEFAULT_USER_AGENT, FetchCapacityError, build_headers, fetch
from box.search import search_google

app = FastAPI(title="box")
_SEARCH_LOCK = threading.BoundedSemaphore(value=1)
_SEARCH_LOCK_TIMEOUT = float(os.getenv("SEARCH_LOCK_TIMEOUT", "60"))

_LOG = logging.getLogger("box")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": int(record.created * 1000),
        }
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            payload.update(record.extra)
        return json.dumps(payload, ensure_ascii=True)


_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
_LOG.setLevel(os.getenv("LOG_LEVEL", "INFO"))
_LOG.addHandler(_handler)
_LOG.propagate = False

_METRICS_LOCK = threading.Lock()
_METRICS = {
    "requests_total": {},
    "request_duration_ms_sum": {},
    "request_duration_ms_count": {},
}


def _metric_key(endpoint: str, status: int) -> str:
    return f"{endpoint}|{status}"


def _observe_request(endpoint: str, status: int, duration_ms: float) -> None:
    key = _metric_key(endpoint, status)
    with _METRICS_LOCK:
        _METRICS["requests_total"][key] = _METRICS["requests_total"].get(key, 0) + 1
        _METRICS["request_duration_ms_sum"][key] = (
            _METRICS["request_duration_ms_sum"].get(key, 0.0) + duration_ms
        )
        _METRICS["request_duration_ms_count"][key] = (
            _METRICS["request_duration_ms_count"].get(key, 0) + 1
        )


def _format_metrics() -> str:
    lines = [
        "# HELP box_requests_total Total HTTP requests",
        "# TYPE box_requests_total counter",
    ]
    for key, value in _METRICS["requests_total"].items():
        endpoint, status = key.split("|", 1)
        lines.append(
            f'box_requests_total{{endpoint="{endpoint}",status="{status}"}} {value}'
        )
    lines += [
        "# HELP box_request_duration_ms_sum Sum of request durations in ms",
        "# TYPE box_request_duration_ms_sum counter",
    ]
    for key, value in _METRICS["request_duration_ms_sum"].items():
        endpoint, status = key.split("|", 1)
        lines.append(
            f'box_request_duration_ms_sum{{endpoint="{endpoint}",status="{status}"}} {value:.3f}'
        )
    lines += [
        "# HELP box_request_duration_ms_count Count of request durations",
        "# TYPE box_request_duration_ms_count counter",
    ]
    for key, value in _METRICS["request_duration_ms_count"].items():
        endpoint, status = key.split("|", 1)
        lines.append(
            f'box_request_duration_ms_count{{endpoint="{endpoint}",status="{status}"}} {value}'
        )
    return "\n".join(lines) + "\n"


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    start = time.time()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        duration_ms = (time.time() - start) * 1000
        _observe_request(request.url.path, status, duration_ms)
        _LOG.info(
            "request",
            extra={
                "extra": {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round(duration_ms, 2),
                    "client": request.client.host if request.client else "",
                }
            },
        )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    return PlainTextResponse(_format_metrics(), media_type="text/plain; version=0.0.4")


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
    except FetchCapacityError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/search")
def search_endpoint(
    q: str = Query(..., description="Search query"),
    news: bool = Query(False, description="Use Google News"),
    chrome_debug_port: int = Query(9225, ge=1, le=65535),
):
    acquired = _SEARCH_LOCK.acquire(timeout=_SEARCH_LOCK_TIMEOUT)
    if not acquired:
        raise HTTPException(status_code=429, detail="Search capacity full. Try again.")
    try:
        return search_google(q, news=news, chrome_debug_port=chrome_debug_port)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        _SEARCH_LOCK.release()
