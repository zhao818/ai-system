import os
from dataclasses import dataclass
from typing import List, Dict

# 环境变量加载
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ===================== 模型池配置 =====================
# 格式遵循 LiteLLM 标准：provider/model-name
# MIMO: mimo/tp-xxx (Token Plan) 或 mimo/sk-xxx (按量)
# 千问: qwen/qwen3-235b-a22b 等
# DeepSeek: deepseek/deepseek-chat (v3) 或 deepseek/deepseek-reasoner (r1)

MODEL_POOL: Dict[str, List[str]] = {
    "cheap": [
        "mimo/qwen3-235b-a22b",      # MIMO 千问3 235B (便宜)
        "deepseek/deepseek-chat",     # DeepSeek V3 (便宜)
        "mimo/deepseek-v3",           # MIMO 代理 DeepSeek V3
    ],
    "mid": [
        "mimo/qwen3-235b-a22b",       # MIMO 千问3 (中等任务)
        "deepseek/deepseek-reasoner", # DeepSeek R1 推理模型
        "mimo/deepseek-r1",           # MIMO 代理 DeepSeek R1
    ],
    "premium": [
        "mimo/qwen3-235b-a22b",       # MIMO 千问3 当作高端用
        "deepseek/deepseek-reasoner", # DeepSeek R1 复杂推理
    ]
}

# 模型别名映射 (方便显示)
MODEL_ALIASES = {
    "mimo/qwen3-235b-a22b": "MIMO-Qwen3-235B",
    "deepseek/deepseek-chat": "DeepSeek-V3",
    "mimo/deepseek-v3": "MIMO-DeepSeek-V3",
    "deepseek/deepseek-reasoner": "DeepSeek-R1",
    "mimo/deepseek-r1": "MIMO-DeepSeek-R1",
}


# ===================== 成本策略 =====================
COST_POLICY = {
    "max_retries_per_tier": 2,          # 每层最多重试次数
    "max_fallback_per_tier": 3,         # 每层最多尝试模型数
    "upgrade_on_error": True,           # 报错自动升级层级
    "upgrade_on_short_response": True,  # 回复过短自动升级
    "min_response_length": 30,          # 最小有效回复长度
    "upgrade_on_keywords": ["error", "failed", "timeout", "抱歉", "无法", "不支持"],  # 触发升级的关键词
    
    # 目标分布 (用于监控告警)
    "cheap_ratio_target": 0.80,
    "mid_ratio_target": 0.15,
    "premium_ratio_target": 0.05,
    
    # 成本估算 (USD per 1M tokens, 仅作参考)
    "cost_estimates": {
        "cheap": {"input": 0.10, "output": 0.30},
        "mid": {"input": 0.50, "output": 1.50},
        "premium": {"input": 1.00, "output": 3.00},
    }
}


# ===================== 路由器配置 =====================
ROUTER_MODEL = "mimo/qwen3-235b-a22b"  # 用于分类的便宜模型

ROUTER_PROMPT = """你是任务分类器。将用户任务分类为三个等级之一：
- cheap: 简单翻译、改写、注释、基础代码片段、格式转换
- mid: 完整功能开发、调试修Bug、重构、数据处理、算法实现
- premium: 架构设计、复杂推理、系统设计、多模块协作、疑难杂症诊断

只输出一个词：cheap / mid / premium

任务：
{task}

分类："""


# ===================== 执行器配置 =====================
EXECUTOR_CONFIG = {
    "opencode_cmd": "opencode",
    "timeout": 300,          # 单次执行超时(秒)
    "max_retries": 2,        # 执行失败重试
    "auto_approve": True,    # OpenCode --yes 模式
}


# ===================== 统计存储 =====================
STATS_FILE = "ai_system_stats.json"
HISTORY_FILE = "ai_system_history.jsonl"
MAX_HISTORY = 10000


# ===================== 验证配置 =====================
def validate_config() -> List[str]:
    """验证配置完整性，返回错误列表"""
    errors = []
    
    # 检查至少有一个 API Key
    has_key = any([
        os.getenv("MIMO_API_KEY"),
        os.getenv("QWEN_API_KEY"),
        os.getenv("DEEPSEEK_API_KEY"),
    ])
    if not has_key:
        errors.append("未配置任何 API Key (MIMO_API_KEY / QWEN_API_KEY / DEEPSEEK_API_KEY)")
    
    # 检查模型池非空
    for tier, models in MODEL_POOL.items():
        if not models:
            errors.append(f"模型池 {tier} 为空")
    
    # 检查路由模型在池中
    all_models = sum(MODEL_POOL.values(), [])
    if ROUTER_MODEL not in all_models:
        errors.append(f"路由模型 {ROUTER_MODEL} 不在模型池中")
    
    return errors


def get_model_display_name(model: str) -> str:
    """获取模型显示名"""
    return MODEL_ALIASES.get(model, model.split("/")[-1])


def estimate_cost(tier: str, input_tokens: int, output_tokens: int) -> float:
    """估算成本 (USD)"""
    costs = COST_POLICY["cost_estimates"].get(tier, {"input": 0, "output": 0})
    return (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000


# ===================== 配置类 =====================
@dataclass
class SystemConfig:
    model_pool: Dict[str, List[str]]
    cost_policy: Dict
    router_model: str
    router_prompt: str
    executor_config: Dict
    stats_file: str
    history_file: str
    max_history: int
    
    @classmethod
    def from_env(cls) -> "SystemConfig":
        return cls(
            model_pool=MODEL_POOL,
            cost_policy=COST_POLICY,
            router_model=ROUTER_MODEL,
            router_prompt=ROUTER_PROMPT,
            executor_config=EXECUTOR_CONFIG,
            stats_file=STATS_FILE,
            history_file=HISTORY_FILE,
            max_history=MAX_HISTORY,
        )


# 单例配置实例
CONFIG = SystemConfig.from_env()

if __name__ == "__main__":
    # 配置自检
    errs = validate_config()
    if errs:
        print("❌ 配置错误:")
        for e in errs:
            print(f"  - {e}")
    else:
        print("✅ 配置验证通过")
        print(f"模型池: {MODEL_POOL}")
        print(f"路由模型: {ROUTER_MODEL}")