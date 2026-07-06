import time
import functools
from enum import Enum
from typing import Callable, Optional, Any


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: float = 30.0, half_open_max_trials: int = 3):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_trials = half_open_max_trials

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.half_open_trials = 0
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0

    def call(self, fn: Callable, fallback: Optional[Callable] = None, *args, **kwargs) -> Any:
        self.total_calls += 1

        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_trials = 0
            else:
                return fallback(*args, **kwargs) if fallback else None

        try:
            result = fn(*args, **kwargs)

            if self.state == CircuitState.HALF_OPEN:
                self.half_open_trials += 1
                if self.half_open_trials >= self.half_open_max_trials:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.half_open_trials = 0

            self.total_successes += 1
            return result

        except Exception as e:
            self.failure_count += 1
            self.total_failures += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN

            if fallback:
                return fallback(*args, **kwargs)
            raise

    def reset(self):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.half_open_trials = 0

    def stats(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "failure_rate": (self.total_failures / max(self.total_calls, 1)) * 100,
        }


class CircuitBreakerRegistry:
    _breakers: dict = {}

    @classmethod
    def get(cls, name: str, **kwargs) -> CircuitBreaker:
        if name not in cls._breakers:
            cls._breakers[name] = CircuitBreaker(name, **kwargs)
        return cls._breakers[name]

    @classmethod
    def all_stats(cls) -> dict:
        return {name: cb.stats() for name, cb in cls._breakers.items()}

    @classmethod
    def reset_all(cls):
        cls._breakers.clear()


def circuit_breaker(name: str, fallback: Optional[Callable] = None, **kwargs):
    def decorator(fn):
        cb = CircuitBreakerRegistry.get(name, **kwargs)
        @functools.wraps(fn)
        def wrapper(*args, _fallback=None, **fkwargs):
            actual_fallback = _fallback or fallback
            return cb.call(fn, actual_fallback, *args, **fkwargs)
        return wrapper
    return decorator
