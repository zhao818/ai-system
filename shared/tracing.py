import time
import uuid
import threading
from contextvars import ContextVar
from typing import Optional


class SpanContext:
    def __init__(self, trace_id: str, parent_span_id: Optional[str] = None):
        self.trace_id = trace_id
        self.span_id = str(uuid.uuid4())[:16]
        self.parent_span_id = parent_span_id
        self.start_time = time.monotonic()
        self.attributes: dict = {}
        self.events: list = []

    def set_attribute(self, key: str, value):
        self.attributes[key] = value

    def add_event(self, name: str, attrs: dict = None):
        self.events.append({"name": name, "timestamp": time.monotonic(), "attributes": attrs or {}})

    def end(self) -> dict:
        duration = (time.monotonic() - self.start_time) * 1000
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "duration_ms": round(duration, 2),
            "attributes": self.attributes,
            "events": self.events,
        }


_current_span: ContextVar[Optional[SpanContext]] = ContextVar("current_span", default=None)


class Tracer:
    def __init__(self, name: str, exporter: Optional[callable] = None):
        self.name = name
        self.exporter = exporter
        self._spans: list = []

    def start_span(self, span_name: str, trace_id: Optional[str] = None,
                   parent: Optional[SpanContext] = None) -> SpanContext:
        parent_ctx = parent or _current_span.get()
        tid = trace_id or (parent_ctx.trace_id if parent_ctx else str(uuid.uuid4()))
        span = SpanContext(tid, parent_ctx.span_id if parent_ctx else None)
        span.set_attribute("span.name", span_name)
        span.set_attribute("service", self.name)
        _current_span.set(span)
        return span

    def end_span(self, span: SpanContext):
        result = span.end()
        self._spans.append(result)
        if self.exporter:
            self.exporter(result)
        return result

    def collect(self) -> list:
        spans = self._spans.copy()
        self._spans.clear()
        return spans

    @staticmethod
    def inject_headers(span: SpanContext) -> dict:
        return {
            "X-Trace-Id": span.trace_id,
            "X-Span-Id": span.span_id,
        }

    @staticmethod
    def extract_headers(headers: dict) -> tuple[Optional[str], Optional[str]]:
        return headers.get("X-Trace-Id"), headers.get("X-Span-Id")


class NoopTracer(Tracer):
    def start_span(self, *args, **kwargs) -> SpanContext:
        return SpanContext("noop")
    def end_span(self, *args, **kwargs):
        return {}
