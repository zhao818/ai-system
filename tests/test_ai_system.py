import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router import _extract_tier, route, get_models_for_tier
from policy import should_upgrade, calculate_cost_ratio, should_force_premium
from models import ModelTier, TaskRequest, TaskResponse
from config import validate_config, get_model_display_name, MODEL_POOL


def _resp(result="", success=True, error=None):
    return TaskResponse(success=success, model_used="m", tier_used=ModelTier.CHEAP, result=result, error=error)


def test_extract_tier_exact():
    assert _extract_tier("cheap") == "cheap"
    assert _extract_tier("  PREMIUM  ") == "premium"


def test_extract_tier_last_keyword():
    assert _extract_tier("maybe cheap or mid, final: premium") == "premium"


def test_extract_tier_none():
    assert _extract_tier("no idea") == ""


def test_route_preferred_tier_skips_llm():
    decision = route(TaskRequest(task="x", preferred_tier=ModelTier.PREMIUM))
    assert decision.tier == ModelTier.PREMIUM
    assert decision.confidence == 1.0


def test_route_with_braces_in_task_does_not_crash():
    # preferred_tier short-circuits before LLM, but braces must never break formatting
    decision = route(TaskRequest(task="fix def f(): return {'a': 1}", preferred_tier=ModelTier.MID))
    assert decision.tier == ModelTier.MID


def test_get_models_for_tier():
    assert get_models_for_tier(ModelTier.CHEAP) == MODEL_POOL["cheap"]


def test_should_upgrade_empty_result():
    assert should_upgrade(_resp(result="")) is True


def test_should_upgrade_on_error():
    assert should_upgrade(_resp(success=False)) is True


def test_should_upgrade_keyword():
    assert should_upgrade(_resp(result="抱歉，我无法完成这个任务，出错了")) is True


def test_should_upgrade_short_english():
    assert should_upgrade(_resp(result="ok done")) is True


def test_should_not_upgrade_good_result():
    long_answer = "def add(a, b):\n    return a + b  # a simple, valid implementation here"
    assert should_upgrade(_resp(result=long_answer)) is False


def test_calculate_cost_ratio_empty():
    assert calculate_cost_ratio({"cheap": 0, "mid": 0, "premium": 0}) == {"cheap": 0, "mid": 0, "premium": 0}


def test_calculate_cost_ratio():
    ratio = calculate_cost_ratio({"cheap": 8, "mid": 1, "premium": 1})
    assert abs(ratio["cheap"] - 0.8) < 1e-9


def test_should_force_premium():
    assert should_force_premium({"premium": 0.5}) is True
    assert should_force_premium({"premium": 0.01}) is False


def test_validate_config_ok():
    assert validate_config() == []


def test_get_model_display_name():
    assert get_model_display_name("opencode/mimo-v2.5-free") == "mimo-v2.5-free"
    assert get_model_display_name("plain") == "plain"
