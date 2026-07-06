from llm import call_llm
from models import ModelTier, RouterDecision, TaskRequest
from config import MODEL_POOL


ROUTER_PROMPT = """
你是AI任务分类器。

任务：
{task}

上下文：
{context}

分类只能选一个：
cheap / mid / premium

规则：
- 简单代码/翻译/摘要/格式化 → cheap
- 代码编写/debug/重构/开发任务 → mid
- 架构设计/复杂推理/多步规划/核心业务逻辑 → premium

只输出一个词：cheap、mid 或 premium
"""


def route(task_request: TaskRequest) -> RouterDecision:
    if task_request.preferred_tier:
        return RouterDecision(
            tier=task_request.preferred_tier,
            reasoning="User specified tier",
            confidence=1.0
        )

    context = task_request.context or "无"
    prompt = ROUTER_PROMPT.format(task=task_request.task, context=context)

    try:
        result = call_llm("gpt-4o-mini", prompt).strip().lower()
    except Exception:
        result = "mid"

    tier_map = {
        "cheap": ModelTier.CHEAP,
        "mid": ModelTier.MID,
        "premium": ModelTier.PREMIUM
    }

    tier = tier_map.get(result, ModelTier.MID)

    return RouterDecision(
        tier=tier,
        reasoning=f"Router classified as: {result}",
        confidence=0.9 if result in tier_map else 0.5
    )


def get_models_for_tier(tier: ModelTier) -> list:
    return MODEL_POOL.get(tier.value, [])