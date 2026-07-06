import re
from llm import call_llm
from models import ModelTier, RouterDecision, TaskRequest
from config import ROUTER_MODEL, ROUTER_PROMPT, MODEL_POOL


def _extract_tier(text: str) -> str:
    """取最后一个分类关键词（模型思考可能全部提到）"""
    text = text.lower().strip()
    if text in ("cheap", "mid", "premium"):
        return text

    keywords = re.findall(r'\b(cheap|mid|premium)\b', text)
    if keywords:
        return keywords[-1]
    return ""


def route(task_request: TaskRequest) -> RouterDecision:
    if task_request.preferred_tier:
        return RouterDecision(
            tier=task_request.preferred_tier,
            reasoning="用户指定",
            confidence=1.0
        )

    prompt = ROUTER_PROMPT.format(task=task_request.task)

    try:
        raw = call_llm(ROUTER_MODEL, prompt, max_tokens=1000)
        result = _extract_tier(raw)
    except Exception as e:
        print(f"  ⚠️ Router 失败: {e}")
        result = ""

    tier_map = {
        "cheap": ModelTier.CHEAP,
        "mid": ModelTier.MID,
        "premium": ModelTier.PREMIUM
    }

    tier = tier_map.get(result, ModelTier.MID)

    return RouterDecision(
        tier=tier,
        reasoning=f"Router: {result or 'fallback to mid'}",
        confidence=0.85 if result else 0.5
    )


def get_models_for_tier(tier: ModelTier) -> list:
    return MODEL_POOL.get(tier.value, [])
