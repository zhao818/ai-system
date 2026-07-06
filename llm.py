import os
import litellm

# MIMO 自定义 API
MIMO_API_BASE = "https://api.xiaomimimo.com/v1"
MIMO_API_KEY = os.getenv("MIMO_API_KEY", "")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")


def get_api_params(model: str) -> dict:
    """根据模型名返回对应的 api_base 和 api_key"""
    if model.startswith("mimo/"):
        return {
            "api_base": MIMO_API_BASE,
            "api_key": MIMO_API_KEY,
            "model": model.replace("mimo/", "openai/"),
        }
    if model.startswith("deepseek/"):
        return {
            "api_key": DEEPSEEK_API_KEY or MIMO_API_KEY,
            "model": model,
        }
    if model.startswith("qwen/"):
        return {
            "api_key": QWEN_API_KEY or MIMO_API_KEY,
            "model": model,
        }
    # 默认走 MIMO
    return {
        "api_base": MIMO_API_BASE,
        "api_key": MIMO_API_KEY,
        "model": f"openai/{model}",
    }


def call_llm(model: str, prompt: str, **kwargs) -> str:
    params = get_api_params(model)

    try:
        res = litellm.completion(
            **params,
            messages=[{"role": "user", "content": prompt}],
            timeout=60,
            max_retries=2,
            drop_params=True,
            **kwargs
        )
        return res["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"LLM call failed for {model}: {e}")


def call_llm_with_system(model: str, system_prompt: str, user_prompt: str, **kwargs) -> str:
    params = get_api_params(model)

    try:
        res = litellm.completion(
            **params,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            timeout=60,
            max_retries=2,
            drop_params=True,
            **kwargs
        )
        return res["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"LLM call failed for {model}: {e}")