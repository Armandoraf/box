import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from itertools import cycle
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

app = FastAPI(title="box-router")

_RUNNER_URLS = [u.strip() for u in os.getenv("RUNNER_URLS", "").split(",") if u.strip()]
if not _RUNNER_URLS:
    _RUNNER_URLS = ["http://127.0.0.1:8000"]

_SEARCH_QUEUE_MAX = int(os.getenv("SEARCH_QUEUE_MAX", "50"))
_SEARCH_MAX_WAIT = float(os.getenv("SEARCH_MAX_WAIT", "60"))
_FETCH_TIMEOUT = float(os.getenv("FETCH_TIMEOUT", "30"))
_RUNNER_HEALTH_TIMEOUT = float(os.getenv("RUNNER_HEALTH_TIMEOUT", "2"))
_HEALTH_CHECK_INTERVAL = float(os.getenv("RUNNER_HEALTH_INTERVAL", "5"))
_FETCH_RETRIES = max(0, int(os.getenv("FETCH_RETRIES", "2")))
_FETCH_RETRY_BACKOFF = float(os.getenv("FETCH_RETRY_BACKOFF", "0.2"))


@dataclass
class RunnerState:
    url: str


_RUNNERS: List[RunnerState] = [RunnerState(url=u) for u in _RUNNER_URLS]

_SEARCH_AVAILABLE = asyncio.Queue(maxsize=len(_RUNNERS))
for idx in range(len(_RUNNERS)):
    _SEARCH_AVAILABLE.put_nowait(idx)

_PENDING_SEARCHES = 0
_PENDING_LOCK = asyncio.Lock()

_FETCH_LOCK = asyncio.Lock()
_FETCH_CYCLE = cycle(range(len(_RUNNERS)))

_RUNNER_HEALTH: Dict[int, Dict[str, object]] = {
    idx: {"healthy": True, "last_error": "", "last_check": 0.0} for idx in range(len(_RUNNERS))
}
_SEARCH_INFLIGHT: Dict[int, int] = {idx: 0 for idx in range(len(_RUNNERS))}
_FETCH_INFLIGHT: Dict[int, int] = {idx: 0 for idx in range(len(_RUNNERS))}
_INFLIGHT_LOCK = asyncio.Lock()

_LOG = logging.getLogger("box-router")


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

_METRICS_LOCK = asyncio.Lock()
_METRICS = {
    "requests_total": {},
    "request_duration_ms_sum": {},
    "request_duration_ms_count": {},
    "search_queue_wait_ms_sum": 0.0,
    "search_queue_wait_ms_count": 0,
    "runner_failures_total": {},
}


def _metric_key(endpoint: str, status: int) -> str:
    return f"{endpoint}|{status}"


async def _observe_request(endpoint: str, status: int, duration_ms: float) -> None:
    key = _metric_key(endpoint, status)
    async with _METRICS_LOCK:
        _METRICS["requests_total"][key] = _METRICS["requests_total"].get(key, 0) + 1
        _METRICS["request_duration_ms_sum"][key] = (
            _METRICS["request_duration_ms_sum"].get(key, 0.0) + duration_ms
        )
        _METRICS["request_duration_ms_count"][key] = (
            _METRICS["request_duration_ms_count"].get(key, 0) + 1
        )


async def _observe_search_queue(wait_ms: float) -> None:
    async with _METRICS_LOCK:
        _METRICS["search_queue_wait_ms_sum"] += wait_ms
        _METRICS["search_queue_wait_ms_count"] += 1


async def _observe_runner_failure(idx: int) -> None:
    async with _METRICS_LOCK:
        _METRICS["runner_failures_total"][idx] = (
            _METRICS["runner_failures_total"].get(idx, 0) + 1
        )


def _format_metrics() -> str:
    lines = [
        "# HELP box_router_requests_total Total HTTP requests",
        "# TYPE box_router_requests_total counter",
    ]
    for key, value in _METRICS["requests_total"].items():
        endpoint, status = key.split("|", 1)
        lines.append(
            f'box_router_requests_total{{endpoint="{endpoint}",status="{status}"}} {value}'
        )
    lines += [
        "# HELP box_router_request_duration_ms_sum Sum of request durations in ms",
        "# TYPE box_router_request_duration_ms_sum counter",
    ]
    for key, value in _METRICS["request_duration_ms_sum"].items():
        endpoint, status = key.split("|", 1)
        lines.append(
            f'box_router_request_duration_ms_sum{{endpoint="{endpoint}",status="{status}"}} {value:.3f}'
        )
    lines += [
        "# HELP box_router_request_duration_ms_count Count of request durations",
        "# TYPE box_router_request_duration_ms_count counter",
    ]
    for key, value in _METRICS["request_duration_ms_count"].items():
        endpoint, status = key.split("|", 1)
        lines.append(
            f'box_router_request_duration_ms_count{{endpoint="{endpoint}",status="{status}"}} {value}'
        )
    lines += [
        "# HELP box_router_search_queue_wait_ms_sum Sum of search queue wait in ms",
        "# TYPE box_router_search_queue_wait_ms_sum counter",
        f"box_router_search_queue_wait_ms_sum {_METRICS['search_queue_wait_ms_sum']:.3f}",
        "# HELP box_router_search_queue_wait_ms_count Count of queued search waits",
        "# TYPE box_router_search_queue_wait_ms_count counter",
        f"box_router_search_queue_wait_ms_count {_METRICS['search_queue_wait_ms_count']}",
        "# HELP box_router_runner_failures_total Runner failures observed by router",
        "# TYPE box_router_runner_failures_total counter",
    ]
    for idx, value in _METRICS["runner_failures_total"].items():
        lines.append(f'box_router_runner_failures_total{{runner="{idx}"}} {value}')
    lines += [
        "# HELP box_router_search_queue_depth Current search queue depth",
        "# TYPE box_router_search_queue_depth gauge",
        f"box_router_search_queue_depth {_SEARCH_AVAILABLE.qsize()}",
        "# HELP box_router_search_pending Current number of queued search requests",
        "# TYPE box_router_search_pending gauge",
        f"box_router_search_pending {_PENDING_SEARCHES}",
    ]
    for idx in range(len(_RUNNERS)):
        inflight_search = _SEARCH_INFLIGHT.get(idx, 0)
        inflight_fetch = _FETCH_INFLIGHT.get(idx, 0)
        lines.append(
            f'box_router_search_inflight{{runner="{idx}"}} {inflight_search}'
        )
        lines.append(
            f'box_router_fetch_inflight{{runner="{idx}"}} {inflight_fetch}'
        )
        health = 1 if _RUNNER_HEALTH.get(idx, {}).get("healthy") else 0
        lines.append(
            f'box_router_runner_healthy{{runner="{idx}"}} {health}'
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
        await _observe_request(request.url.path, status, duration_ms)
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


async def _mark_runner_health(idx: int, healthy: bool, error: str = "") -> None:
    _RUNNER_HEALTH[idx] = {
        "healthy": healthy,
        "last_error": error,
        "last_check": time.time(),
    }


def _healthy_runner_indices() -> List[int]:
    return [idx for idx, state in _RUNNER_HEALTH.items() if state.get("healthy")]


async def _health_probe_loop() -> None:
    while True:
        async with httpx.AsyncClient(timeout=_RUNNER_HEALTH_TIMEOUT) as client:
            for idx, runner in enumerate(_RUNNERS):
                try:
                    resp = await client.get(f"{runner.url}/health")
                    await _mark_runner_health(idx, resp.status_code == 200)
                except Exception as exc:
                    await _mark_runner_health(idx, False, exc.__class__.__name__)
        await asyncio.sleep(_HEALTH_CHECK_INTERVAL)


@app.on_event("startup")
async def _startup_health_loop() -> None:
    asyncio.create_task(_health_probe_loop())


async def _reserve_search_slot() -> tuple[int, float]:
    global _PENDING_SEARCHES
    if not _healthy_runner_indices():
        raise HTTPException(status_code=503, detail="No healthy runners available.")
    async with _PENDING_LOCK:
        if _PENDING_SEARCHES >= _SEARCH_QUEUE_MAX:
            raise HTTPException(status_code=429, detail="Search queue full. Try again.")
        _PENDING_SEARCHES += 1

    start = time.time()
    try:
        while True:
            elapsed = time.time() - start
            remaining = _SEARCH_MAX_WAIT - elapsed
            if remaining <= 0:
                raise HTTPException(status_code=429, detail="Search queue timeout. Try again.")
            try:
                idx = await asyncio.wait_for(_SEARCH_AVAILABLE.get(), timeout=remaining)
            except asyncio.TimeoutError as exc:
                raise HTTPException(status_code=429, detail="Search queue timeout. Try again.") from exc

            if _RUNNER_HEALTH.get(idx, {}).get("healthy", True):
                async with _INFLIGHT_LOCK:
                    _SEARCH_INFLIGHT[idx] += 1
                return idx, elapsed * 1000

            _SEARCH_AVAILABLE.put_nowait(idx)
            await asyncio.sleep(0.05)
    finally:
        async with _PENDING_LOCK:
            _PENDING_SEARCHES -= 1


def _release_search_slot(idx: int) -> None:
    _SEARCH_AVAILABLE.put_nowait(idx)


def _json_or_error_response(resp: httpx.Response) -> JSONResponse:
    try:
        payload = resp.json()
    except ValueError:
        snippet = (resp.text or "").strip()
        if len(snippet) > 1000:
            snippet = snippet[:1000] + "..."
        payload = {
            "error": "upstream returned non-JSON response",
            "status_code": resp.status_code,
            "body_snippet": snippet,
        }
    return JSONResponse(content=payload, status_code=resp.status_code)


async def _next_fetch_runner() -> int:
    async with _FETCH_LOCK:
        healthy = _healthy_runner_indices()
        if not healthy:
            raise HTTPException(status_code=503, detail="No healthy runners available.")
        for _ in range(len(_RUNNERS)):
            idx = next(_FETCH_CYCLE)
            if idx in healthy:
                return idx
        raise HTTPException(status_code=503, detail="No healthy runners available.")


@app.get("/health")
async def health() -> Dict[str, object]:
    started = time.time()
    results: List[Dict[str, object]] = []
    async with httpx.AsyncClient(timeout=_RUNNER_HEALTH_TIMEOUT) as client:
        for idx, runner in enumerate(_RUNNERS):
            status = "ok"
            try:
                resp = await client.get(f"{runner.url}/health")
                if resp.status_code != 200:
                    status = f"error:{resp.status_code}"
            except Exception as exc:
                status = f"error:{exc.__class__.__name__}"
            results.append(
                {
                    "url": runner.url,
                    "status": status,
                    "healthy": _RUNNER_HEALTH.get(idx, {}).get("healthy", True),
                    "last_error": _RUNNER_HEALTH.get(idx, {}).get("last_error", ""),
                }
            )
    return {
        "status": "ok",
        "runners": results,
        "elapsed_ms": int((time.time() - started) * 1000),
    }

@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(_format_metrics(), media_type="text/plain; version=0.0.4")


@app.get("/search")
async def search(
    q: str = Query(..., description="Search query"),
    news: bool = Query(False, description="Use Google News"),
):
    idx, wait_ms = await _reserve_search_slot()
    await _observe_search_queue(wait_ms)
    runner = _RUNNERS[idx]
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
            resp = await client.get(
                f"{runner.url}/search",
                params={"q": q, "news": str(news).lower()},
            )
            return _json_or_error_response(resp)
    except httpx.RequestError as exc:
        await _observe_runner_failure(idx)
        await _mark_runner_health(idx, False, exc.__class__.__name__)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        async with _INFLIGHT_LOCK:
            _SEARCH_INFLIGHT[idx] -= 1
        _release_search_slot(idx)


@app.get("/fetch")
async def fetch(
    url: str = Query(..., description="URL to fetch"),
    timeout: float = Query(20.0, ge=1.0, le=120.0),
    raw: bool = Query(False, description="Include raw HTML"),
    raw_text: bool = Query(False, description="Include raw text extraction"),
    user_agent: str = Query(""),
    accept_language: str = Query(""),
):
    attempts = 0
    params = {
        "url": url,
        "timeout": timeout,
        "raw": str(raw).lower(),
        "raw_text": str(raw_text).lower(),
    }
    if user_agent:
        params["user_agent"] = user_agent
    if accept_language:
        params["accept_language"] = accept_language

    last_exc: Optional[Exception] = None
    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
        while attempts <= _FETCH_RETRIES:
            idx = await _next_fetch_runner()
            runner = _RUNNERS[idx]
            async with _INFLIGHT_LOCK:
                _FETCH_INFLIGHT[idx] += 1
            try:
                resp = await client.get(f"{runner.url}/fetch", params=params)
                if resp.status_code >= 500 and attempts < _FETCH_RETRIES:
                    await _observe_runner_failure(idx)
                    await _mark_runner_health(idx, False, f"status:{resp.status_code}")
                    await asyncio.sleep(_FETCH_RETRY_BACKOFF * (2 ** attempts))
                    attempts += 1
                    continue
                return _json_or_error_response(resp)
            except httpx.RequestError as exc:
                last_exc = exc
                await _observe_runner_failure(idx)
                await _mark_runner_health(idx, False, exc.__class__.__name__)
                if attempts >= _FETCH_RETRIES:
                    break
                await asyncio.sleep(_FETCH_RETRY_BACKOFF * (2 ** attempts))
                attempts += 1
                continue
            finally:
                async with _INFLIGHT_LOCK:
                    _FETCH_INFLIGHT[idx] -= 1
    raise HTTPException(status_code=502, detail=str(last_exc or "Upstream failure"))
