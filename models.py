from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


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
    preferred_tier: Optional[ModelTier] = None
    context: Optional[str] = None
    require_code_execution: bool = False


@dataclass
class TaskResponse:
    success: bool
    model_used: str
    tier_used: ModelTier
    result: str
    error: Optional[str] = None
    fallback_count: int = 0


@dataclass
class RouterDecision:
    tier: ModelTier
    reasoning: str
    confidence: float