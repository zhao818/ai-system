import time
from fastapi import FastAPI
from pydantic import BaseModel
from shared import Tracer, CircuitBreakerRegistry
from shared.config import COST_POLICY, CIRCUIT_BREAKER, SERVICE_VERSION

app = FastAPI(title="Policy Service", version=SERVICE_VERSION)
tracer = Tracer("policy")
_start_time = time.time()


class PolicyCheckRequest(BaseModel):
    success: bool
    result: str = ""
    error: str = ""
    tier_used: str = ""
    fallback_count: int = 0
    request_id: str = ""


class PolicyAction(BaseModel):
    should_upgrade: bool
    upgrade_to: str = ""
    reason: str = ""


@app.post("/v1/check")
def check_policy(req: PolicyCheckRequest):
    span = tracer.start_span("policy.check", trace_id=req.request_id)

    should = _should_upgrade(req)
    if should:
        tier_order = ["cheap", "mid", "premium"]
        current_idx = tier_order.index(req.tier_used) if req.tier_used in tier_order else -1
        next_tier = ""
        if current_idx < len(tier_order) - 1:
            next_tier = tier_order[current_idx + 1]

        action = PolicyAction(
            should_upgrade=True,
            upgrade_to=next_tier,
            reason=f"quality insufficient (len={len(req.result or '')})"
        )
    else:
        action = PolicyAction(should_upgrade=False)

    tracer.end_span(span)
    return action


@app.post("/v1/ratio")
def calculate_ratio(stats: dict):
    total = sum(stats.values())
    if total == 0:
        return {"cheap": 0, "mid": 0, "premium": 0}
    return {
        "cheap": round(stats.get("cheap", 0) / total, 4),
        "mid": round(stats.get("mid", 0) / total, 4),
        "premium": round(stats.get("premium", 0) / total, 4),
    }


def _should_upgrade(req: PolicyCheckRequest) -> bool:
    if not req.success:
        return COST_POLICY["upgrade_on_error"]
    if req.error and "error" in req.error.lower():
        return COST_POLICY["upgrade_on_error"]
    if len(req.result.strip()) < COST_POLICY["min_response_length"]:
        return COST_POLICY["upgrade_on_short_response"]
    return False


@app.get("/health")
def health():
    return {"service": "policy", "status": "ok", "version": SERVICE_VERSION,
            "uptime": time.time() - _start_time}
