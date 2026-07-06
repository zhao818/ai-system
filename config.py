import os

# ===================== 模型池 (OpenCode 模型名) =====================
# opencode models 查看完整列表
# cheap: 简单任务
# mid: 开发任务
# premium: 复杂推理

MODEL_POOL = {
    "cheap": [
        "opencode/mimo-v2.5-free",
        "opencode/deepseek-v4-flash-free",
    ],
    "mid": [
        "deepseek/deepseek-reasoner",
        "mimo/mimo-v2.5-pro",
    ],
    "premium": [
        "deepseek/deepseek-reasoner",
        "mimo/mimo-v2.5-pro",
    ]
}

# Router 用的模型 (MIMO 原生模型名，直接 HTTP 调用)
ROUTER_MODEL = "mimo-v2.5"

ROUTER_PROMPT = """任务：{task}

请严格按分类规则只输出一个词。

cheap = 翻译、改写、格式化、简单代码片段
mid = 函数开发、算法、debug、数据处理
premium = 架构设计、系统设计、复杂推理

输出："""


# ===================== 成本策略 =====================
COST_POLICY = {
    "max_retries_per_tier": 2,
    "max_fallback_per_tier": 3,
    "upgrade_on_error": True,
    "upgrade_on_short_response": True,
    "min_response_length": 30,
    "upgrade_on_keywords": ["error", "failed", "timeout", "抱歉", "无法", "不支持"],
    "cheap_ratio_target": 0.80,
    "mid_ratio_target": 0.15,
    "premium_ratio_target": 0.05,
}


# ===================== 执行器 =====================
EXECUTOR_CONFIG = {
    "opencode_cmd": "opencode",
    "timeout": 300,
    "max_retries": 2,
    "auto_approve": True,
}


# ===================== 存储 =====================
STATS_FILE = "ai_system_stats.json"
HISTORY_FILE = "ai_system_history.jsonl"
MAX_HISTORY = 10000


# ===================== 工具函数 =====================
def validate_config():
    errors = []
    for tier, models in MODEL_POOL.items():
        if not models:
            errors.append(f"模型池 {tier} 为空")
    return errors


def get_model_display_name(model: str) -> str:
    parts = model.split("/")
    return parts[-1] if len(parts) > 1 else model