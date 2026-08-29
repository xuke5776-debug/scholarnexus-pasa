"""OpenAI 兼容后端。

同一份代码覆盖两条路线：
  · 商业 API：DashScope / 硅基流动 / DeepSeek / Moonshot（初赛主用）
  · 本地部署：vLLM / SGLang / Ollama（决赛与私有化交付）
两者只差一个 base_url，这是「商业优先但不放弃本地」的最小成本实现。
"""
from __future__ import annotations

import os
from typing import Dict, List

import requests

from ..utils import approx_tokens, retry
from .base import LLMClient, LLMResponse


class OpenAICompatLLM(LLMClient):
    name = "openai_compat"

    def __init__(self, model: str, base_url: str, api_key_env: str = "OPENAI_API_KEY",
                 ledger=None, temperature: float = 0.0, max_tokens: int = 1024,
                 timeout: int = 60):
        super().__init__(model, ledger, temperature, max_tokens)
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.api_key = os.environ.get(api_key_env, "")
        self.timeout = timeout
        self.session = requests.Session()

    def _raw_chat(self, messages: List[Dict[str, str]], stage: str = "misc",
                  **kw) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kw.get("temperature", self.temperature),
            "max_tokens": kw.get("max_tokens", self.max_tokens),
        }
        if kw.get("json_mode", True):
            payload["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        def _call():
            r = self.session.post(f"{self.base_url}/chat/completions",
                                  headers=headers, json=payload, timeout=self.timeout)
            if r.status_code == 400 and "response_format" in payload:
                # 部分端点不支持 json_object，去掉重试一次
                payload.pop("response_format", None)
                r = self.session.post(f"{self.base_url}/chat/completions",
                                      headers=headers, json=payload,
                                      timeout=self.timeout)
            r.raise_for_status()
            return r.json()

        data = retry(_call, attempts=3)
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        pt = usage.get("prompt_tokens") or approx_tokens(
            "".join(m["content"] for m in messages))
        ct = usage.get("completion_tokens") or approx_tokens(text)
        return LLMResponse(text=text, prompt_tokens=pt, completion_tokens=ct,
                           model=self.model)
