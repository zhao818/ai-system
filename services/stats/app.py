import time
import json
import threading
from collections import defaultdict
from fastapi import FastAPI
from pydantic import BaseModel
from shared import Tracer
from shared.config import SERVICE_VERSION

app = FastAPI(title="Stats Service", version=SERVICE_VERSION)
tracer = Tracer("stats")
_start_time = time.time()
_lock = threading.Lock()


_stats = {
    "counts": defaultdict(int),
    "total_calls": 0,
    "total_latency_ms": 0.0,
    "model_usage": defaultdict(int),
    "errors": defaultdict(int),
    "tier_errors": defaultdict(int),
}

_history = []


class StatsEvent(BaseModel):
    request_id: str = ""
    model: str = ""
    tier: str = ""
    success: bool = True
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    error: str = ""
    timestamp: float = 0.0


@app.post("/v1/ingest")
def ingest(event: StatsEvent):
    with _lock:
        ts = event.timestamp or time.time()
        _stats["total_calls"] += 1
        _stats["total_latency_ms"] += event.latency_ms
        _stats["counts"][event.tier or "unknown"] += 1
        _stats["model_usage"][event.model or "unknown"] += 1

        if not event.success:
            _stats["errors"]["total"] += 1
            if event.error:
                _stats["errors"][event.error[:50]] += 1
            _stats["tier_errors"][event.tier or "unknown"] += 1

        _history.append({
            "ts": ts, "request_id": event.request_id,
            "model": event.model, "tier": event.tier,
            "success": event.success, "latency_ms": event.latency_ms,
            "tokens_in": event.tokens_in, "tokens_out": event.tokens_out,
        })

        if len(_history) > 10000:
            _history[:5000] = []

    return {"status": "ingested"}


@app.get("/v1/summary")
def summary():
    with _lock:
        total = _stats["total_calls"]
        ratios = {}
        if total > 0:
            for tier in ["cheap", "mid", "premium"]:
                ratios[tier] = round(_stats["counts"].get(tier, 0) / total, 4)
            avg_latency = round(_stats["total_latency_ms"] / total, 2)
        else:
            avg_latency = 0

        return {
            "total_calls": total,
            "counts": dict(_stats["counts"]),
            "ratios": ratios,
            "avg_latency_ms": avg_latency,
            "model_usage": dict(_stats["model_usage"]),
            "errors": {
                "total": _stats["errors"].get("total", 0),
                "by_tier": dict(_stats["tier_errors"]),
            },
            "error_rate": round(_stats["errors"].get("total", 0) / max(total, 1), 4),
        }


@app.get("/v1/history")
def history(limit: int = 20):
    with _lock:
        return {"history": _history[-limit:]}


@app.post("/v1/ratio")
def cost_ratio(stats_input: dict):
    total = sum(stats_input.values())
    if total == 0:
        return {"cheap": 0, "mid": 0, "premium": 0}
    return {
        "cheap": round(stats_input.get("cheap", 0) / total, 4),
        "mid": round(stats_input.get("mid", 0) / total, 4),
        "premium": round(stats_input.get("premium", 0) / total, 4),
    }


@app.get("/health")
def health():
    with _lock:
        return {
            "service": "stats", "status": "ok", "version": SERVICE_VERSION,
            "uptime": time.time() - _start_time,
            "total_calls_ingested": _stats["total_calls"],
        }
