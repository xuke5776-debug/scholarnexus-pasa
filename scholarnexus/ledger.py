"""执行账本：把「效率」从口号变成可审计的数字（对应评测 20% 运行效率分）。"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List

# 参考单价（元/百万 token），仅用于成本估算展示，可在 config 中覆盖
DEFAULT_PRICE = {"prompt": 2.0, "completion": 8.0}


@dataclass
class StageRecord:
    stage: str
    seconds: float
    detail: Dict[str, Any] = field(default_factory=dict)


class Ledger:
    """线程安全的成本账本。所有耗时 / 调用都要经它记录。"""

    def __init__(self, budget=None, price: Dict[str, float] | None = None):
        self._lock = threading.Lock()
        self.records: List[StageRecord] = []
        self.t0 = time.time()
        self.budget = budget
        self.price = price or DEFAULT_PRICE
        self.counters: Dict[str, float] = defaultdict(float)
        self.events: List[Dict[str, Any]] = []

    # ---------------- 计数 ----------------
    def add_llm(self, stage: str, prompt_tokens: int, completion_tokens: int,
                calls: int = 1, model: str = ""):
        with self._lock:
            self.counters["llm_calls"] += calls
            self.counters["prompt_tokens"] += prompt_tokens
            self.counters["completion_tokens"] += completion_tokens
            self.counters["tokens"] += prompt_tokens + completion_tokens
            self.counters[f"llm_calls::{stage}"] += calls
            self.counters[f"tokens::{stage}"] += prompt_tokens + completion_tokens
            self.events.append({"t": round(time.time() - self.t0, 3),
                                "type": "llm", "stage": stage, "model": model,
                                "tok": prompt_tokens + completion_tokens})

    def add_api(self, stage: str, calls: int = 1, cache_hit: bool = False):
        with self._lock:
            if cache_hit:
                self.counters["cache_hits"] += calls
                self.counters[f"cache_hits::{stage}"] += calls
            else:
                self.counters["api_calls"] += calls
                self.counters[f"api_calls::{stage}"] += calls
                self.events.append({"t": round(time.time() - self.t0, 3),
                                    "type": "api", "stage": stage})

    def mark(self, key: str, value: float = 1.0):
        with self._lock:
            self.counters[key] += value

    def note(self, stage: str, message: str, **kw):
        with self._lock:
            ev = {"t": round(time.time() - self.t0, 3), "type": "note",
                  "stage": stage, "message": message}
            ev.update(kw)
            self.events.append(ev)

    # ---------------- 阶段计时 ----------------
    def stage(self, name: str):
        return _StageTimer(self, name)

    def _push_record(self, rec: StageRecord):
        with self._lock:
            self.records.append(rec)
            self.counters[f"seconds::{rec.stage}"] += rec.seconds

    # ---------------- 预算 ----------------
    @property
    def elapsed(self) -> float:
        return time.time() - self.t0

    def remaining_llm_calls(self) -> int:
        if not self.budget:
            return 10 ** 9
        return int(self.budget.max_llm_calls - self.counters["llm_calls"])

    def remaining_tokens(self) -> int:
        if not self.budget:
            return 10 ** 9
        return int(self.budget.max_tokens - self.counters["tokens"])

    def exhausted(self) -> bool:
        if not self.budget:
            return False
        return (self.counters["llm_calls"] >= self.budget.max_llm_calls
                or self.counters["tokens"] >= self.budget.max_tokens
                or self.elapsed >= self.budget.max_seconds)

    def cost_cny(self) -> float:
        return (self.counters["prompt_tokens"] * self.price["prompt"]
                + self.counters["completion_tokens"] * self.price["completion"]) / 1e6

    # ---------------- 导出 ----------------
    def summary(self) -> Dict[str, Any]:
        per_stage: Dict[str, Dict[str, float]] = {}
        for k, v in self.counters.items():
            if "::" in k:
                metric, stage = k.split("::", 1)
                per_stage.setdefault(stage, {})[metric] = round(v, 4)
        return {
            "total": {
                "llm_calls": int(self.counters["llm_calls"]),
                "api_calls": int(self.counters["api_calls"]),
                "cache_hits": int(self.counters["cache_hits"]),
                "prompt_tokens": int(self.counters["prompt_tokens"]),
                "completion_tokens": int(self.counters["completion_tokens"]),
                "tokens": int(self.counters["tokens"]),
                "wall_seconds": round(self.elapsed, 3),
                "est_cost_cny": round(self.cost_cny(), 5),
            },
            "per_stage": per_stage,
            "budget": None if not self.budget else {
                "max_llm_calls": self.budget.max_llm_calls,
                "max_tokens": self.budget.max_tokens,
                "max_seconds": self.budget.max_seconds,
            },
            "events": self.events[-200:],
        }


class _StageTimer:
    def __init__(self, ledger: Ledger, name: str):
        self.ledger, self.name = ledger, name

    def __enter__(self):
        self.t = time.time()
        return self

    def __exit__(self, *exc):
        self.ledger._push_record(StageRecord(self.name, time.time() - self.t))
        return False
