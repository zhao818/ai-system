import re
import os
import time
import uuid
from fastapi import FastAPI, HTTPException
from shared import (
    TaskRequest, RouterDecision, Tracer, CircuitBreakerRegistry,
    RateLimiter, ServiceHealth
)
from shared.config import (
    MODEL_POOL, ROUTER_MODEL, ROUTER_PROMPT, CIRCUIT_BREAKER,
    RATE_LIMITER as RL_CFG, SERVICE_VERSION
)

app = FastAPI(title="Router Service", version=SERVICE_VERSION)
tracer = Tracer("router")
rate_limiter = RateLimiter()
_start_time = time.time()
_router_cb = CircuitBreakerRegistry.get("router", **CIRCUIT_BREAKER)

rate_limiter.set_global(RL_CFG["global_rate"], RL_CFG["global_capacity"])
rate_limiter.set_key_limit("default", RL_CFG["key_limit"], RL_CFG["key_window"])


def _call_llm(model: str, prompt: str) -> str:
    import requests
    api_key = os.environ.get("MIMO_API_KEY", "")
    base = os.environ.get("MIMO_API_BASE", "https://token-plan-cn.xiaomimimo.com/v1")
    resp = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}],
              "max_tokens": 10, "temperature": 0},
        timeout=10,
    )
    resp.raise_for_status()
    msg = resp.json()["choices"][0]["message"]
    return msg.get("content", "").strip() or msg.get("reasoning_content", "").strip()


def _classify_tier(task: str) -> tuple[str, float]:
    prompt = ROUTER_PROMPT.format(task=task)
    try:
        raw = _call_llm(ROUTER_MODEL, prompt)
        tier = _extract_tier(raw)
        if tier:
            return tier, 0.85
    except Exception:
        pass
    tier = _keyword_classify(task)
    return tier, 0.6


def _extract_tier(text: str) -> str:
    text = text.lower().strip()
    if text in ("cheap", "mid", "premium"):
        return text
    m = re.search(r'\b(premium)\b', text)
    if m: return "premium"
    m = re.search(r'\b(mid)\b', text)
    if m: return "mid"
    m = re.search(r'\b(cheap)\b', text)
    if m: return "cheap"
    return ""


_keyword_patterns = {
    "premium": [r'\b架构\b', r'\b设计模式\b', r'\b微服务\b', r'\b系统设计\b',
                r'\b百万并发\b', r'\b分布式\b', r'\b高可用\b', r'\b复杂推理\b'],
    "mid": [r'\b算法\b', r'\bdebug\b', r'\b调试\b', r'\b优化\b', r'\brefactor\b',
            r'\b重构\b', r'\b函数\b', r'\b测试\b', r'\b单元测试\b'],
}


def _keyword_classify(task: str) -> str:
    for tier, patterns in _keyword_patterns.items():
        for p in patterns:
            if re.search(p, task):
                return tier
    return "cheap"


@app.post("/v1/route")
def route_task(req: TaskRequest):
    span = tracer.start_span("router.decision", trace_id=req.request_id or str(uuid.uuid4()))
    allowed, reason = rate_limiter.check_all(req.api_key)
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)

    start = time.monotonic()

    if req.preferred_tier:
        tier, confidence = req.preferred_tier, 1.0
        reasoning = "user specified"
    else:
        tier, confidence = _classify_tier(req.task)
        reasoning = f"LLM+keyword classified as {tier}"

    decision = RouterDecision(
        tier=tier, reasoning=reasoning, confidence=confidence,
        request_id=span.trace_id, latency_ms=round((time.monotonic() - start) * 1000, 2),
    )
    span.set_attribute("tier", tier)
    span.set_attribute("confidence", confidence)
    tracer.end_span(span)
    return decision


@app.get("/v1/models/{tier}")
def get_models(tier: str):
    models = MODEL_POOL.get(tier, [])
    if not models:
        raise HTTPException(status_code=404, detail=f"tier '{tier}' not found")
    return {"tier": tier, "models": models}


@app.get("/health")
def health():
    return ServiceHealth(
        service="router", status="ok", version=SERVICE_VERSION,
        uptime=time.time() - _start_time,
        dependencies={"llm_api": "unknown"},
    )


@app.get("/cb/stats")
def circuit_breaker_stats():
    return CircuitBreakerRegistry.all_stats()
