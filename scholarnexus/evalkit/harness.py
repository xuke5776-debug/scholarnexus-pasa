"""评测框架：批量跑查询、算集合级指标、导出可复现报告。

设计原则：**先有度量，再谈优化。** 所有消融实验都通过 `overrides` 走同一条
代码路径，只改配置不改逻辑——否则对照组之间会混入实现差异，结论不可信。
"""
from __future__ import annotations

import copy
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence

from ..config import Config
from ..core.pipeline import ScholarNexus
from ..schema import Budget
from .metrics import aggregate, composite, set_prf, structure_score


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


@dataclass
class EvalHarness:
    config: Config
    registry: Any = None
    max_workers: int = 4
    current_year: int = 2026

    # ------------------------------------------------------------------ #
    def run(self, queries: Sequence[Dict[str, Any]],
            overrides: Optional[Dict[str, Any]] = None,
            budget: Optional[Budget] = None,
            selector: Optional[Callable] = None,
            label: str = "default",
            verbose: bool = True) -> Dict[str, Any]:
        """跑一组查询。

        overrides : 覆盖 config.pipeline 的字段，用于消融
        selector  : (SearchResult) → List[pid]，用于替换输出集合决策策略
                    （默认用 F1-Gate 的 core 层；消融时可换成 Top-K）
        """
        cfg = copy.deepcopy(self.config)
        if overrides:
            cfg.pipeline.update(overrides)
        rows: List[Dict[str, Any]] = []
        t0 = time.time()

        def _one(q: Dict[str, Any]) -> Dict[str, Any]:
            try:
                # 每个查询独立引擎，避免并行评测共享校准快照/通道命中状态。
                engine = ScholarNexus(cfg, registry=self.registry,
                                      current_year=self.current_year)
                res = engine.search(q["query"], budget=budget)
            except Exception as e:                               # noqa: BLE001
                return {"qid": q.get("qid"), "error": f"{type(e).__name__}: {e}",
                        "precision": 0, "recall": 0, "f1": 0, "tp": 0,
                        "n_pred": 0, "n_gold": len(q.get("gold", [])),
                        "recall@20": 0, "recall@50": 0, "llm_calls": 0,
                        "tokens": 0, "api_calls": 0, "seconds": 0,
                        "structure": 0, "efficiency": 0, "score": 0,
                        "query_type": "?"}
            pred = selector(res) if selector else [c.pid for c in res.core]
            ranked = [c.pid for c in res.all_candidates]
            m = set_prf(pred, q.get("gold", []), ranked)
            tot = res.ledger.get("total", {})
            comp = composite(m, res.views, tot)
            row = {"qid": q.get("qid"), "query": q["query"],
                   "query_type": res.plan.query_type.value,
                   "query_type_hint": q.get("query_type_hint"),
                   **m.to_dict(),
                   "n_hat": round(res.n_hat, 2), "coverage": round(res.coverage, 3),
                   "threshold": round(res.threshold, 3),
                   "expected_f1": round(res.expected_f1, 3),
                   "rounds": res.rounds,
                   "llm_calls": tot.get("llm_calls", 0),
                   "tokens": tot.get("tokens", 0),
                   "api_calls": tot.get("api_calls", 0),
                   "seconds": tot.get("wall_seconds", 0),
                   "cost_cny": tot.get("est_cost_cny", 0),
                   **{k: round(v, 4) for k, v in comp.items() if k != "f1"}}
            return row

        if self.max_workers > 1 and len(queries) > 1:
            with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
                futs = {ex.submit(_one, q): q for q in queries}
                for fut in as_completed(futs):
                    rows.append(fut.result())
        else:
            for q in queries:
                rows.append(_one(q))

        rows.sort(key=lambda r: str(r.get("qid")))
        agg = aggregate(rows)
        agg["label"] = label
        agg["wall_seconds_total"] = round(time.time() - t0, 2)
        agg["errors"] = sum(1 for r in rows if r.get("error"))
        if verbose:
            self._print(agg)
        return {"label": label, "summary": agg, "rows": rows,
                "config": cfg.to_dict()}

    # ------------------------------------------------------------------ #
    @staticmethod
    def _print(a: Dict[str, Any]):
        print(f"\n[{a['label']}] n={a['n_queries']}  错误 {a.get('errors',0)}")
        print(f"  macro P/R/F1 = {a['macro_precision']:.4f} / "
              f"{a['macro_recall']:.4f} / {a['macro_f1']:.4f}   "
              f"micro-F1 = {a['micro_f1']:.4f}")
        print(f"  输出集合均值 {a['avg_pred_size']:.1f} vs 金标准均值 "
              f"{a['avg_gold_size']:.1f}   R@20={a['recall@20']:.3f}")
        print(f"  成本：LLM {a['avg_llm_calls']:.1f} 次 / "
              f"{a['avg_tokens']:.0f} tok / API {a['avg_api_calls']:.1f} 次 / "
              f"{a['avg_seconds']:.2f}s")
        print(f"  竞赛综合分 {a['composite_score']:.4f} "
              f"(F1 {a['macro_f1']:.3f} × .7 + 效率 {a['avg_efficiency']:.3f} × .2 "
              f"+ 结构 {a['avg_structure']:.3f} × .1)")
        print(f"  分类型 F1：{a['f1_by_type']}")

    @staticmethod
    def save(report: Dict[str, Any], path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        return path


# --------------------------------------------------------------------------- #
# 消融用的输出集合选择器
# --------------------------------------------------------------------------- #
def topk_selector(k: int):
    """固定 Top-K（PaSa 式）。消融对照组。"""
    def _sel(res):
        return [c.pid for c in res.all_candidates[:k]]
    return _sel


def threshold_selector(thr: float = 0.5):
    """固定人工阈值（SPAR 式）。消融对照组。"""
    def _sel(res):
        return [c.pid for c in res.all_candidates if c.p_gold >= thr]
    return _sel


def gate_selector(include_partial: bool = False):
    """本方案：F1-Gate 不动点门限。"""
    def _sel(res):
        out = [c.pid for c in res.core]
        if include_partial:
            out += [c.pid for c in res.partial]
        return out
    return _sel


def oracle_k_selector(gold_lookup: Dict[str, Sequence[str]]):
    """事后最优前缀（上界参考，不可实现，仅用于衡量剩余空间）。"""
    def _sel(res):
        gold = set(gold_lookup.get(res.query, []))
        ranked = [c.pid for c in res.all_candidates]
        best_k, best_f1 = 0, -1.0
        for k in range(1, min(len(ranked), 120) + 1):
            tp = len(set(ranked[:k]) & gold)
            f1 = 2 * tp / (k + len(gold)) if (k + len(gold)) else 0.0
            if f1 > best_f1:
                best_f1, best_k = f1, k
        return ranked[:best_k]
    return _sel
