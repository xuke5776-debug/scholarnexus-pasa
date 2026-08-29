"""LLM 抽象层：统一 chat / json 接口，全部调用经 Ledger 计费。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""


_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text: str) -> Any:
    """从模型输出中稳健抽取 JSON（容忍围栏、前后缀、单引号、尾逗号）。"""
    if not text:
        raise ValueError("empty llm output")
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1)
    text = text.strip()
    for start, end in (("{", "}"), ("[", "]")):
        i, j = text.find(start), text.rfind(end)
        if i != -1 and j > i:
            frag = text[i:j + 1]
            for attempt in (frag,
                            re.sub(r",\s*([}\]])", r"\1", frag),
                            re.sub(r",\s*([}\]])", r"\1", frag).replace("'", '"')):
                try:
                    return json.loads(attempt)
                except json.JSONDecodeError:
                    continue
    raise ValueError(f"cannot parse json from: {text[:200]}")


class BudgetExhausted(RuntimeError):
    """预算耗尽。上层捕获后应降级而非崩溃。"""


class LLMClient:
    """所有 LLM 后端的公共基类。子类只需实现 _raw_chat。"""

    name = "base"

    def __init__(self, model: str, ledger=None, temperature: float = 0.0,
                 max_tokens: int = 1024):
        self.model = model
        self.ledger = ledger
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.available = True

    def _raw_chat(self, messages: List[Dict[str, str]], stage: str = "misc",
                  **kw) -> LLMResponse:
        raise NotImplementedError

    def chat(self, system: str, user: str, stage: str = "misc", **kw) -> str:
        if self.ledger and self.ledger.remaining_llm_calls() <= 0:
            raise BudgetExhausted(f"LLM call budget exhausted at stage={stage}")
        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
        resp = self._raw_chat(msgs, stage=stage, **kw)
        if self.ledger:
            self.ledger.add_llm(stage, resp.prompt_tokens, resp.completion_tokens,
                                model=self.model)
        return resp.text

    def chat_json(self, system: str, user: str, stage: str = "misc",
                  default: Any = None, **kw) -> Any:
        try:
            return extract_json(self.chat(system, user, stage=stage, **kw))
        except BudgetExhausted:
            raise
        except Exception as e:                                   # noqa: BLE001
            if self.ledger:
                self.ledger.mark(f"errors::{stage}")
                self.ledger.note(stage, f"LLM JSON 解析失败，降级: {type(e).__name__}")
            if default is not None:
                return default
            raise


def build_llm(cfg: Dict[str, Any], ledger=None) -> LLMClient:
    backend = (cfg.get("backend") or "mock").lower()
    if backend == "mock":
        from .mock import MockLLM
        return MockLLM(cfg.get("model", "mock-1"), ledger=ledger)
    from .openai_compat import OpenAICompatLLM
    return OpenAICompatLLM(
        model=cfg["model"],
        base_url=cfg.get("base_url", "https://api.openai.com/v1"),
        api_key_env=cfg.get("api_key_env", "OPENAI_API_KEY"),
        ledger=ledger,
        temperature=cfg.get("temperature", 0.0),
        max_tokens=cfg.get("max_tokens", 1024),
        timeout=cfg.get("timeout", 60),
    )
