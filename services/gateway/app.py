import os
import time
import uuid
import requests
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from shared import Tracer, RateLimiter, RateLimiter as RL
from shared.config import RATE_LIMITER as RL_CFG, SERVICE_VERSION

app = FastAPI(title="API Gateway", version=SERVICE_VERSION)
tracer = Tracer("gateway")
rate_limiter = RateLimiter()
_start_time = time.time()

rate_limiter.set_global(RL_CFG["global_rate"], RL_CFG["global_capacity"])

SERVICE_URLS = {
    "router": os.environ.get("ROUTER_SVC_URL", "http://localhost:8001"),
    "executor": os.environ.get("EXECUTOR_SVC_URL", "http://localhost:8002"),
    "policy": os.environ.get("POLICY_SVC_URL", "http://localhost:8003"),
    "model_proxy": os.environ.get("MODEL_PROXY_SVC_URL", "http://localhost:8004"),
    "stats": os.environ.get("STATS_SVC_URL", "http://localhost:8005"),
}


class RunRequest(BaseModel):
    task: str
    preferred_tier: str = ""
    api_key: str = ""
    stream: bool = False


class RunResponse(BaseModel):
    success: bool
    result: str = ""
    model_used: str = ""
    tier_used: str = ""
    latency_ms: float = 0.0
    error: str = ""
    request_id: str = ""


def _forward(method: str, service: str, path: str, json_body: dict = None, params: dict = None):
    url = f"{SERVICE_URLS[service]}{path}"
    try:
        resp = requests.request(method, url, json=json_body, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"{service} unavailable: {e}")
    except requests.Timeout:
        raise HTTPException(status_code=504, detail=f"{service} timeout")
    except requests.HTTPError as e:
        raise HTTPException(status_code=resp.status_code,
                            detail=f"{service}: {resp.text[:200]}")


@app.post("/v1/run")
def run_task(req: RunRequest):
    span = tracer.start_span("http.request")
    start = time.monotonic()

    allowed, reason = rate_limiter.check_global()
    if not allowed:
        raise HTTPException(status_code=429, detail="global_rate_limit")

    rid = str(uuid.uuid4())

    step1 = _forward("POST", "router", "/v1/route", json_body={
        "task": req.task, "preferred_tier": req.preferred_tier or None,
        "api_key": req.api_key, "request_id": rid,
    })
    tier = step1.get("tier", "cheap")
    models = _forward("GET", "router", f"/v1/models/{tier}").get("models", [])

    result, model_used, error = "", "", ""
    for model in models:
        step2 = _forward("POST", "executor", "/v1/execute", json_body={
            "task": req.task, "model": model, "request_id": rid,
        })
        if step2.get("success"):
            result = step2.get("result", "")
            model_used = model

            step3 = _forward("POST", "policy", "/v1/check", json_body={
                "success": True, "result": result,
                "tier_used": tier, "request_id": rid,
            })
            if step3.get("should_upgrade"):
                continue
            break
        else:
            error = step2.get("error", "")

    if not result and tier != "premium":
        tier_order = ["cheap", "mid", "premium"]
        for higher_tier in tier_order[tier_order.index(tier) + 1:]:
            higher_models = _forward("GET", "router", f"/v1/models/{higher_tier}").get("models", [])
            for model in higher_models:
                step = _forward("POST", "executor", "/v1/execute", json_body={
                    "task": req.task, "model": model, "request_id": rid,
                })
                if step.get("success"):
                    result = step.get("result", "")
                    model_used = model
                    tier = higher_tier
                    error = ""
                    break
            if result:
                break

    latency = round((time.monotonic() - start) * 1000, 2)

    _forward("POST", "stats", "/v1/ingest", json_body={
        "request_id": rid, "model": model_used, "tier": tier,
        "success": bool(result), "latency_ms": latency, "error": error,
    })

    span.set_attribute("success", bool(result))
    span.set_attribute("tier", tier)
    span.set_attribute("latency_ms", latency)
    tracer.end_span(span)

    return RunResponse(
        success=bool(result), result=result[:2000],
        model_used=model_used, tier_used=tier,
        latency_ms=latency, error=error, request_id=rid,
    )


@app.get("/health")
def health(detail: bool = False):
    if not detail:
        return {"service": "gateway", "status": "ok", "version": SERVICE_VERSION,
                "uptime": time.time() - _start_time}

    deps = {}
    for name, url in SERVICE_URLS.items():
        try:
            r = requests.get(f"{url}/health", timeout=2)
            deps[name] = "ok" if r.ok else f"error:{r.status_code}"
        except Exception as e:
            deps[name] = f"unreachable:{e}"
    return {"service": "gateway", "status": "ok", "version": SERVICE_VERSION,
            "uptime": time.time() - _start_time, "dependencies": deps}


@app.get("/v1/stats")
def get_stats():
    return _forward("GET", "stats", "/v1/summary")


@app.get("/v1/history")
def get_history(limit: int = 20):
    return _forward("GET", "stats", f"/v1/history", params={"limit": limit})
