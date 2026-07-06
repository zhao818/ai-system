import os
import requests
from dotenv import load_dotenv

load_dotenv()

MIMO_API_BASE = os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ.get('MIMO_API_KEY', MIMO_API_KEY)}",
        "Content-Type": "application/json",
    }


def call_llm(model: str, prompt: str, max_tokens: int = 200, timeout: int = 30) -> str:
    """直接调 MIMO API (OpenAI 兼容)，支持 reasoning_content"""
    if not os.environ.get("MIMO_API_KEY", MIMO_API_KEY):
        raise RuntimeError(
            "MIMO_API_KEY 未设置。请复制 .env.example 为 .env 并填入 key，或 export MIMO_API_KEY。"
        )

    base = os.environ.get("MIMO_BASE_URL", MIMO_API_BASE)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }

    try:
        resp = requests.post(
            f"{base}/chat/completions",
            headers=_headers(),
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        msg = data["choices"][0]["message"]
        # MIMO 是推理模型，最终答案可能在 content 或 reasoning_content
        return (msg.get("content") or "").strip() or (msg.get("reasoning_content") or "").strip()
    except requests.RequestException as e:
        raise RuntimeError(f"LLM call failed for {model}: {e}")
