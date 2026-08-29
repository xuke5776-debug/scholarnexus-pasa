"""集合级评测指标。

**必须是集合级 P/R/F1，不是 Recall@K。** 这是本赛题与 PaSa 公开评测最大的差别，
也是整套方案的立论起点：既然指标是 F1，"返回多少篇"就是一个必须被优化的
决策变量，而不是一个可以随便定的超参。

同时统计成本指标（20% 运行效率分）与结构化指标（10%），
让每次实验都能直接读出**综合得分**，而不是只看 F1 自我感觉良好。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence, Set


@dataclass
class SetMetrics:
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    tp: int = 0
    n_pred: int = 0
    n_gold: int = 0
    # 参考指标：便于与 PaSa 等系统的公开数字对齐
    recall_at_20: float = 0.0
    recall_at_50: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"precision": round(self.precision, 4),
                "recall": round(self.recall, 4), "f1": round(self.f1, 4),
                "tp": self.tp, "n_pred": self.n_pred, "n_gold": self.n_gold,
                "recall@20": round(self.recall_at_20, 4),
                "recall@50": round(self.recall_at_50, 4)}


def set_prf(pred: Sequence[str], gold: Iterable[str],
            ranked: Sequence[str] | None = None) -> SetMetrics:
    """集合级 P/R/F1。pred 是最终输出集合，ranked 是完整排序（算 Recall@K 用）。"""
    g: Set[str] = set(gold)
    p: List[str] = list(dict.fromkeys(pred))
    tp = len(set(p) & g)
    prec = tp / len(p) if p else 0.0
    rec = tp / len(g) if g else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    r = list(ranked or p)
    r20 = len(set(r[:20]) & g) / len(g) if g else 0.0
    r50 = len(set(r[:50]) & g) / len(g) if g else 0.0
    return SetMetrics(prec, rec, f1, tp, len(p), len(g), r20, r50)


# --------------------------------------------------------------------------- #
def structure_score(views: Dict[str, Any]) -> float:
    """结构化程度评分（对应评测 10%）。

    赛题原文是「返回的结果是否使用列表、关系图等」。我们把它拆成可核查的四项，
    并要求**视图与查询意图匹配**才计分 —— 给定位型查询硬塞一张关系图不该得分。
    """
    if not views:
        return 0.0
    s = 0.0
    m = views.get("matrix") or {}
    if m.get("rows"):
        s += 0.30                                     # 列表 / 矩阵
        if m.get("columns") and len(m["columns"]) >= 3:
            s += 0.10                                 # 多维约束列
        if any(c.get("evidence") for r in m["rows"] for c in r.get("cells", [])):
            s += 0.15                                 # 证据可溯源
    g = views.get("graph") or {}
    if g.get("nodes") and g.get("edges"):
        s += 0.20                                     # 关系图
    qt = views.get("query_type")
    intent_view = {"locate": "disambiguation", "survey": "facets",
                   "method_cross": "comparison", "benchmark": "comparison",
                   "lineage": "timeline"}.get(qt)
    if intent_view and views.get(intent_view):
        s += 0.15                                     # 意图自适应视图
    if (views.get("themes") or {}).get("themes"):
        s += 0.10                                     # 语义归纳
    return min(s, 1.0)


def efficiency_score(ledger_total: Dict[str, Any],
                     ref: Dict[str, float] | None = None) -> float:
    """运行效率评分（对应评测 20%）。

    以「参考预算」为基准做对数衰减：低于基准得满分，超出后平滑扣分。
    用对数而非线性，是因为 2 倍超支和 20 倍超支应该有量级上的区别。
    """
    import math
    ref = ref or {"llm_calls": 16.0, "tokens": 60000.0, "wall_seconds": 45.0}
    parts = []
    for k, base in ref.items():
        v = float(ledger_total.get(k, 0) or 0)
        parts.append(1.0 if v <= base else max(0.0, 1.0 - math.log(v / base) / math.log(6)))
    return sum(parts) / len(parts)


def composite(metrics: SetMetrics, views: Dict[str, Any],
              ledger_total: Dict[str, Any]) -> Dict[str, float]:
    """按赛题权重合成竞赛得分：F1 70% + 效率 20% + 结构化 10%。"""
    eff = efficiency_score(ledger_total)
    st = structure_score(views)
    return {"f1": metrics.f1, "efficiency": eff, "structure": st,
            "score": 0.70 * metrics.f1 + 0.20 * eff + 0.10 * st}


# --------------------------------------------------------------------------- #
def aggregate(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """跨查询聚合。

    同时报告 **macro-F1**（每条查询算 F1 再平均）和 **micro-F1**（先汇总 TP 再算）。
    两者差异本身是有信息量的：macro 远低于 micro 说明系统在小 gold 集合的查询上
    失分严重（通常是定位型），这正是固定 Top-K 方案的典型病征。
    """
    if not rows:
        return {}
    n = len(rows)
    def _m(k, default=0.0):
        return sum(float(r.get(k, default) or 0) for r in rows) / n

    tp = sum(int(r.get("tp", 0)) for r in rows)
    npred = sum(int(r.get("n_pred", 0)) for r in rows)
    ngold = sum(int(r.get("n_gold", 0)) for r in rows)
    mp = tp / npred if npred else 0.0
    mr = tp / ngold if ngold else 0.0
    micro = 2 * mp * mr / (mp + mr) if (mp + mr) > 0 else 0.0

    by_type: Dict[str, List[float]] = {}
    for r in rows:
        by_type.setdefault(r.get("query_type", "?"), []).append(float(r.get("f1", 0)))

    return {
        "n_queries": n,
        "macro_precision": round(_m("precision"), 4),
        "macro_recall": round(_m("recall"), 4),
        "macro_f1": round(_m("f1"), 4),
        "micro_f1": round(micro, 4),
        "recall@20": round(_m("recall@20"), 4),
        "recall@50": round(_m("recall@50"), 4),
        "avg_pred_size": round(_m("n_pred"), 2),
        "avg_gold_size": round(_m("n_gold"), 2),
        "avg_llm_calls": round(_m("llm_calls"), 2),
        "avg_tokens": round(_m("tokens"), 1),
        "avg_api_calls": round(_m("api_calls"), 2),
        "avg_seconds": round(_m("seconds"), 2),
        "avg_structure": round(_m("structure"), 4),
        "avg_efficiency": round(_m("efficiency"), 4),
        "composite_score": round(_m("score"), 4),
        "f1_by_type": {k: round(sum(v) / len(v), 4) for k, v in sorted(by_type.items())},
    }
