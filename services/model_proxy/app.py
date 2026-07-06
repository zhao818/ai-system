import os
import time
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from shared import Tracer, CircuitBreakerRegistry, RateLimiter
from shared.config import CIRCUIT_BREAKER, RATE_LIMITER as RL_CFG, SERVICE_VERSION

app = FastAPI(title="Model Proxy Service", version=SERVICE_VERSION)
tracer = Tracer("model_proxy")
rate_limiter = RateLimiter()
_start_time = time.time()
_model_cbs: dict[str, CircuitBreakerRegistry] = {}

MIMO_API_BASE = os.environ.get("MIMO_API_BASE", "https://token-plan-cn.xiaomimimo.com/v1")
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
HEADERS = {"Authorization": f"Bearer {MIMO_API_KEY}", "Content-Type": "application/json"}

rate_limiter.set_global(RL_CFG["global_rate"], RL_CFG["global_capacity"])
rate_limiter.set_model_concurrency("*", RL_CFG["model_concurrency"])


class ModelCallRequest(BaseModel):
    model: str
    messages: list
    max_tokens: int = 2048
    temperature: float = 0.7
    stream: bool = False
    request_id: str = ""


class ModelCallResponse(BaseModel):
    success: bool
    content: str = ""
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    error: str = ""


def _get_cb(model: str):
    cb_name = f"model:{model}"
    if cb_name not in _model_cbs:
        _model_cbs[cb_name] = CircuitBreakerRegistry.get(cb_name, **CIRCUIT_BREAKER)
    return _model_cbs[cb_name]


@app.post("/v1/chat/completions", response_model=ModelCallResponse)
def chat_completions(req: ModelCallRequest):
    span = tracer.start_span("model.call", trace_id=req.request_id)
    start = time.monotonic()
    span.set_attribute("model", req.model)

    allowed, reason = rate_limiter.check_all("internal", req.model)
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)

    cb = _get_cb(req.model)
    payload = {
        "model": req.model,
        "messages": req.messages,
        "max_tokens": req.max_tokens,
        "temperature": req.temperature,
    }

    try:
        def _call():
            resp = requests.post(
                f"{MIMO_API_BASE}/chat/completions",
                headers=HEADERS, json=payload, timeout=60
            )
            resp.raise_for_status()
            return resp.json()

        data = cb.call(_call)
        choice = data["choices"][0]["message"]
        content = choice.get("content", "").strip() or choice.get("reasoning_content", "").strip()
        usage = data.get("usage", {})

        response = ModelCallResponse(
            success=True, content=content, model=req.model,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            latency_ms=round((time.monotonic() - start) * 1000, 2),
        )

    except Exception as e:
        response = ModelCallResponse(
            success=False, error=str(e), model=req.model,
            latency_ms=round((time.monotonic() - start) * 1000, 2),
        )

    span.set_attribute("success", response.success)
    span.set_attribute("tokens_in", response.tokens_in)
    span.set_attribute("tokens_out", response.tokens_out)
    span.set_attribute("latency_ms", response.latency_ms)
    tracer.end_span(span)
    return response


@app.get("/v1/models")
def list_models():
    return {
        "models": [
            "deepseek/deepseek-chat", "deepseek/deepseek-reasoner",
            "mimo/mimo-v2.5", "mimo/mimo-v2.5-pro",
        ]
    }


@app.get("/health")
def health():
    return {"service": "model_proxy", "status": "ok", "version": SERVICE_VERSION,
            "uptime": time.time() - _start_time,
            "dependencies": {"mimo_api": MIMO_API_BASE}}


@app.get("/cb/stats")
def circuit_breaker_stats():
    return CircuitBreakerRegistry.all_stats()
