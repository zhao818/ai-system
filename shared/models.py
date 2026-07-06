from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import time


class ModelTier(Enum):
    CHEAP = "cheap"
    MID = "mid"
    PREMIUM = "premium"


@dataclass
class ModelConfig:
    name: str
    tier: ModelTier
    max_tokens: int = 4096
    temperature: float = 0.7
    enabled: bool = True


@dataclass
class TaskRequest:
    task: str
    preferred_tier: Optional[str] = None
    context: Optional[str] = None
    require_code_execution: bool = False
    request_id: str = ""
    api_key: str = ""
    timestamp: float = 0.0


@dataclass
class TaskResponse:
    success: bool
    model_used: str
    tier_used: str
    result: str
    error: Optional[str] = None
    fallback_count: int = 0
    request_id: str = ""
    latency_ms: float = 0.0


@dataclass
class RouterDecision:
    tier: str
    reasoning: str
    confidence: float
    request_id: str = ""
    latency_ms: float = 0.0


@dataclass
class ServiceHealth:
    service: str
    status: str
    version: str
    uptime: float
    dependencies: dict = field(default_factory=dict)
