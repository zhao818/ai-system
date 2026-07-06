import time
import asyncio
from collections import defaultdict
from threading import Lock


class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = Lock()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_time(self) -> float:
        with self._lock:
            self._refill()
            if self.tokens >= 1:
                return 0.0
            return (1 - self.tokens) / self.rate


class SlidingWindowCounter:
    def __init__(self, limit: int, window_seconds: float = 1.0):
        self.limit = limit
        self.window_seconds = window_seconds
        self._timestamps = []

    def allow(self) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._timestamps = [t for t in self._timestamps if t > cutoff]
        if len(self._timestamps) < self.limit:
            self._timestamps.append(now)
            return True
        return False


class RateLimiter:
    def __init__(self):
        self._global_bucket: TokenBucket = None
        self._key_counters: dict[str, SlidingWindowCounter] = {}
        self._model_semaphores: dict[str, int] = {}
        self._lock = Lock()

    def set_global(self, rate: float, capacity: int):
        self._global_bucket = TokenBucket(rate, capacity)

    def set_key_limit(self, key: str, limit: int, window_seconds: float = 1.0):
        with self._lock:
            self._key_counters[key] = SlidingWindowCounter(limit, window_seconds)

    def set_model_concurrency(self, model: str, max_concurrent: int):
        with self._lock:
            self._model_semaphores[model] = max_concurrent

    def check_global(self, tokens: int = 1) -> bool:
        return not self._global_bucket or self._global_bucket.consume(tokens)

    def check_key(self, key: str) -> bool:
        counter = self._key_counters.get(key)
        return not counter or counter.allow()

    def check_model(self, model: str) -> bool:
        limit = self._model_semaphores.get(model)
        return limit is None or limit > 0

    def check_all(self, api_key: str, model: str = "", tokens: int = 1) -> tuple[bool, str]:
        if not self.check_global(tokens):
            return False, "global_rate_limit"
        if not self.check_key(api_key):
            return False, "key_rate_limit"
        if model and not self.check_model(model):
            return False, "model_concurrency_limit"
        return True, ""
