import os


SERVICE_PORT = int(os.environ.get("SERVICE_PORT", "0"))
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")

MODEL_POOL = {
    "cheap": [
        "deepseek/deepseek-chat",
        "mimo/mimo-v2.5",
    ],
    "mid": [
        "deepseek/deepseek-reasoner",
        "mimo/mimo-v2.5-pro",
    ],
    "premium": [
        "deepseek/deepseek-reasoner",
        "mimo/mimo-v2.5-pro",
    ],
}

ROUTER_MODEL = "mimo-v2.5"

ROUTER_PROMPT = """任务：{task}

请严格按分类规则只输出一个词。

cheap = 翻译、改写、格式化、简单代码片段
mid = 函数开发、算法、debug、数据处理
premium = 架构设计、系统设计、复杂推理

输出："""

COST_POLICY = {
    "max_retries_per_tier": 2,
    "min_response_length": 30,
    "upgrade_on_error": True,
    "upgrade_on_short_response": True,
    "cheap_ratio_target": 0.80,
    "mid_ratio_target": 0.15,
    "premium_ratio_target": 0.05,
}

CIRCUIT_BREAKER = {
    "failure_threshold": 5,
    "recovery_timeout": 30.0,
    "half_open_max_trials": 3,
}

RATE_LIMITER = {
    "global_rate": 50000,
    "global_capacity": 50000,
    "key_limit": 1000,
    "key_window": 1.0,
    "model_concurrency": 50,
}

EXECUTOR_CONFIG = {
    "opencode_cmd": "opencode",
    "timeout": 300,
    "max_retries": 2,
}

SERVICE_VERSION = "1.0.0"
SERVICE_START_TIME = None
