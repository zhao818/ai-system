from models import TaskResponse
from config import COST_POLICY


def should_upgrade(response: TaskResponse) -> bool:
    if not response.success:
        return COST_POLICY["upgrade_on_error"]

    if response.error and "error" in response.error.lower():
        return COST_POLICY["upgrade_on_error"]

    if len(response.result.strip()) < COST_POLICY["min_response_length"]:
        return COST_POLICY["upgrade_on_short_response"]

    return False


def calculate_cost_ratio(stats: dict) -> dict:
    total = sum(stats.values())
    if total == 0:
        return {"cheap": 0, "mid": 0, "premium": 0}

    return {
        "cheap": stats.get("cheap", 0) / total,
        "mid": stats.get("mid", 0) / total,
        "premium": stats.get("premium", 0) / total
    }


def should_force_premium(ratio: dict) -> bool:
    return ratio.get("premium", 0) > COST_POLICY["premium_ratio_target"] * 2