import os, requests

MIMO_API_BASE = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")

HEADERS = {
    "Authorization": f"Bearer {MIMO_API_KEY}",
    "Content-Type": "application/json"
}


def call_llm(model: str, prompt: str, max_tokens: int = 200, timeout: int = 30) -> str:
    """直接调 MIMO API (OpenAI 兼容)，支持 reasoning_content"""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }

    try:
        resp = requests.post(
            f"{MIMO_API_BASE}/chat/completions",
            headers=HEADERS,
            json=payload,
            timeout=timeout
        )
        resp.raise_for_status()
        data = resp.json()
        msg = data["choices"][0]["message"]
        # MIMO 是推理模型，最终答案可能在 content 或 reasoning_content
        return msg.get("content", "").strip() or msg.get("reasoning_content", "").strip()
    except Exception as e:
        raise RuntimeError(f"LLM call failed for {model}: {e}")
