import os
import time
import uuid
import subprocess
from fastapi import FastAPI, HTTPException
from shared import TaskRequest, TaskResponse, Tracer, CircuitBreakerRegistry
from shared.config import EXECUTOR_CONFIG, CIRCUIT_BREAKER, SERVICE_VERSION

app = FastAPI(title="Executor Service", version=SERVICE_VERSION)
tracer = Tracer("executor")
_start_time = time.time()
_executor_cb = CircuitBreakerRegistry.get("executor", **CIRCUIT_BREAKER)


@app.post("/v1/execute")
def execute(req: TaskRequest):
    span = tracer.start_span("executor.run", trace_id=req.request_id or str(uuid.uuid4()))
    start = time.monotonic()

    model = os.environ.get("EXECUTOR_DEFAULT_MODEL", "deepseek/deepseek-chat")

    cmd = _build_cmd(model, req.task)
    try:
        result = _executor_cb.call(_run_subprocess, cmd)
        response = TaskResponse(
            success=True, model_used=model, tier_used="",
            result=result, request_id=span.trace_id,
            latency_ms=round((time.monotonic() - start) * 1000, 2),
        )
    except Exception as e:
        response = TaskResponse(
            success=False, model_used=model, tier_used="",
            result="", error=str(e), request_id=span.trace_id,
            latency_ms=round((time.monotonic() - start) * 1000, 2),
        )

    span.set_attribute("success", response.success)
    span.set_attribute("model", model)
    span.set_attribute("latency_ms", response.latency_ms)
    tracer.end_span(span)
    return response


def _build_cmd(model: str, task: str) -> list:
    cmd = [EXECUTOR_CONFIG["opencode_cmd"], "run", task, "-m", model]
    if EXECUTOR_CONFIG.get("auto_approve"):
        cmd.append("--auto")
    return cmd


def _run_subprocess(cmd: list) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True,
                            timeout=EXECUTOR_CONFIG["timeout"])
    if result.returncode != 0:
        raise RuntimeError(f"OpenCode exited with {result.returncode}: {result.stderr[:500]}")
    return result.stdout.strip()


@app.get("/health")
def health():
    return {"service": "executor", "status": "ok", "version": SERVICE_VERSION,
            "uptime": time.time() - _start_time}


@app.get("/cb/stats")
def circuit_breaker_stats():
    return CircuitBreakerRegistry.all_stats()
