"""自适应信号融合：用无监督一致性在线估计各路信号的可靠性。

为什么需要它（这是被实测数据逼出来的模块）
------------------------------------------
判定级联的常规做法是硬编码「层级越高、权重越大」：L3 大模型 0.62、
L2 精排 0.23、L1 粗排 0.15。这个假设看起来天经地义，但它在两种常见情况下
会直接把系统打坏：

  · 部署降级：reranker 降到词法回退、LLM 降到规则回退时，高层反而更弱；
  · 领域偏移：LLM 在某些冷门子领域的判别力可能低于引文图信号。

我们在合成语料上实测到的信号 AUC 就是这样一组数字：
s_rrf 0.811、s_l1 0.792、s_graph 0.780，而 s_l2 只有 0.580、s_l3 只有 0.487。
硬编码权重把最终分数的 AUC 从 0.792 拖到 0.655 —— **级联在倒退**。

无监督可靠性估计
----------------
没有标注时如何判断一路信号是好是坏？用信号间的**排序一致性**：

    ρ_j = mean_{k≠j} spearman(rank_j, rank_k)

若某路信号与其余所有信号的共识严重背离，它更可能是噪声而不是独到见解。
这是经典的无监督集成思想（多个近似独立的弱信号的共识逼近真相），
在检索场景里尤其成立，因为各通道的错误模式彼此独立。

最终权重把**先验**与**实测一致性**相乘：

    w_j ∝ w0_j · max(ρ_j, 0)^γ

w0 保留领域知识（大模型看了完整语义，先验上应更强），
ρ^γ 则让实测说话。γ=1.5 使明显失准的信号被强惩罚而非温和降权。

这条机制同时是「算法泛化性」的直接答案：换一个学科、换一套模型后端，
系统不需要重新调权重，它自己会调。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# 各信号的先验权重（领域知识）与最低权重下限
PRIOR_WEIGHTS: Dict[str, float] = {
    "l3": 0.42,        # 大模型逐条约束核验：先验最强
    "l2": 0.20,        # cross-encoder 精排
    "l1": 0.16,        # 多信号粗排
    "rrf": 0.12,       # 多通道 RRF 融合
    "graph": 0.10,     # 引文图先验（共被引 + 双向 PPR）
    "title": 0.06,     # 引用片段精确匹配（定位型查询下会被上调，见 TYPE_PRIOR）
}

# 查询类型对先验权重的调整。同一套信号在不同意图下价值差别很大：
# 定位型要找的就是标题里那一篇，引用片段匹配压倒一切；
# 综述覆盖型则相反，靠单篇标题匹配会严重伤害召回，引文图才是主力。
TYPE_PRIOR: Dict[str, Dict[str, float]] = {
    "locate": {"title": 0.40, "l3": 0.26, "l2": 0.14, "l1": 0.10,
               "rrf": 0.06, "graph": 0.04},
    "survey": {"l3": 0.36, "graph": 0.18, "l2": 0.18, "l1": 0.14,
               "rrf": 0.11, "title": 0.03},
    "lineage": {"l3": 0.34, "graph": 0.22, "l2": 0.16, "l1": 0.13,
                "rrf": 0.10, "title": 0.05},
}
MIN_WEIGHT = 0.02      # 任何信号都保留一点权重，避免一致性估计本身出错时全押一路


def type_prior(query_type: str) -> Dict[str, float]:
    """按查询类型取先验权重表，未特别定义的类型用通用权重。"""
    return TYPE_PRIOR.get(query_type, PRIOR_WEIGHTS)


def _rankdata(x: np.ndarray) -> np.ndarray:
    """平均秩（处理并列）。并列不处理会让常量信号的相关性虚高。"""
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=np.float64)
    ranks[order] = np.arange(1, len(x) + 1, dtype=np.float64)
    # 并列取平均
    sx = x[order]
    i = 0
    while i < len(sx):
        j = i
        while j + 1 < len(sx) and sx[j + 1] == sx[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    return ranks


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3:
        return 0.0
    ra, rb = _rankdata(a), _rankdata(b)
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    d = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / d) if d > 1e-12 else 0.0


@dataclass
class FusionReport:
    weights: Dict[str, float] = field(default_factory=dict)
    consistency: Dict[str, float] = field(default_factory=dict)
    used: List[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self):
        return {"weights": {k: round(v, 4) for k, v in self.weights.items()},
                "consistency": {k: round(v, 4) for k, v in self.consistency.items()},
                "used": self.used, "note": self.note}


def spectral_reliability(mats: List[np.ndarray]) -> Optional[np.ndarray]:
    """用谱方法从信号间相关矩阵估计各信号的可靠性（无需任何标注）。

    理论依据
    --------
    Parisi et al. (PNAS 2014, *Ranking and combining multiple predictors without
    a labelled dataset*) 证明：若一组预测器的**错误彼此独立**，则其预测值协方差
    矩阵（去对角）的主特征向量分量正比于各预测器的平衡准确率。

    直觉：真信号只有一个方向，噪声方向各不相同。多路信号共同张成的最大方差方向
    就是真相所在，每路信号在这个方向上的投影长度即它的可靠性。

    相比启发式的「平均相关性 ^ γ」，谱方法有三个实际好处：
      1. 不需要拍 γ —— 少一个没有依据的超参；
      2. 天然处理反相关信号：与真相方向相反的信号得到负分量，直接归零，
         而平均相关性法只会把它温和降权（实测中这正是垃圾 L3 仍拿到
         0.08~0.22 权重的原因）；
      3. 能区分「与所有人都不像」（噪声）和「与多数人不像但与最强者一致」
         （独到见解），平均法把这两种情况混为一谈。

    错误独立性假设在本系统中大致成立：词法检索、引文图、cross-encoder、
    大模型判定的失效模式彼此差异很大。
    """
    if len(mats) < 3:
        return None
    n = len(mats)
    R = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            r = spearman(mats[i], mats[j])
            R[i, j] = R[j, i] = r
    Q = R - np.diag(np.diag(R))          # 去对角：只保留互信息，剔除自相关
    try:
        vals, vecs = np.linalg.eigh(Q)
    except np.linalg.LinAlgError:
        return None
    v = vecs[:, int(np.argmax(vals))]
    if v.sum() < 0:                      # 特征向量符号不定，取多数为正的方向
        v = -v
    return v


def adaptive_fuse(signals: Dict[str, np.ndarray], gamma: float = 1.5,
                  prior: Optional[Dict[str, float]] = None,
                  method: str = "spectral"
                  ) -> Tuple[np.ndarray, FusionReport]:
    """把多路信号融合成单一分数。

    Parameters
    ----------
    signals : {信号名: 分数数组}。允许含 NaN（表示该候选未被该层评过），
              NaN 会被该信号的中位数填充 —— 直接填 0 会让未评候选被系统性打压，
              而「未评」不等于「不相关」。
    method  : "spectral"（默认，谱可靠性估计）或 "consistency"（平均相关性，
              作为消融对照保留）
    gamma   : 仅 method="consistency" 时生效
    """
    names = [k for k, v in signals.items() if v is not None and len(v) > 0]
    if not names:
        return np.zeros(0), FusionReport(note="无可用信号")
    n = len(signals[names[0]])

    # ---- 清洗：填补缺失、剔除常量信号 ----
    clean: Dict[str, np.ndarray] = {}
    for k in names:
        v = np.asarray(signals[k], dtype=np.float64).copy()
        if len(v) != n:
            continue
        mask = np.isnan(v)
        if mask.all():
            continue
        if mask.any():
            v[mask] = np.median(v[~mask])
        if float(np.std(v)) < 1e-9:
            continue                       # 常量信号不携带排序信息
        clean[k] = v
    if not clean:
        return np.zeros(n), FusionReport(note="所有信号均为常量")

    prior = prior or PRIOR_WEIGHTS
    keys = list(clean)
    mats = [clean[k] for k in keys]

    # ---- 可靠性估计 ----
    cons: Dict[str, float] = {}
    rel: Optional[np.ndarray] = None
    used_method = method
    if method == "spectral":
        rel = spectral_reliability(mats)
        if rel is None:
            used_method = "consistency"
    if rel is not None:
        for k, v in zip(keys, rel):
            cons[k] = float(v)
    else:
        if len(keys) == 1:
            cons[keys[0]] = 1.0
        else:
            for k in keys:
                rs = [spearman(clean[k], clean[o]) for o in keys if o != k]
                cons[k] = float(np.mean(rs)) if rs else 0.0

    # ---- 权重 = 先验 × 可靠性 ----
    # 谱分量已经是"可靠性"的线性标度，直接相乘即可，不需要再拍一个幂次；
    # 退化到 consistency 模式时才用 γ 做惩罚。
    w: Dict[str, float] = {}
    mx = max((cons[k] for k in keys), default=0.0)
    for k in keys:
        p = prior.get(k, 0.1)
        if used_method == "spectral":
            r = max(cons[k], 0.0) / mx if mx > 1e-9 else 0.0
        else:
            r = max(cons[k], 0.0) ** gamma
        w[k] = max(p * r, MIN_WEIGHT * p)
    tot = sum(w.values()) or 1.0
    w = {k: v / tot for k, v in w.items()}

    # ---- 在秩空间融合：各信号量纲差异极大（RRF ~0.02，LLM ~0.8），
    #      直接线性加权会让量纲大的信号事实上垄断结果 ----
    out = np.zeros(n, dtype=np.float64)
    for k in keys:
        r = _rankdata(clean[k]) / n
        out += w[k] * r
    lo, hi = out.min(), out.max()
    out = (out - lo) / (hi - lo) if hi - lo > 1e-12 else np.full(n, 0.5)

    return out, FusionReport(weights=w, consistency=cons, used=keys,
                             note=f"{len(keys)} 路信号 {used_method} 自适应融合")


def collect_signals(cands: Sequence) -> Dict[str, np.ndarray]:
    """从候选对象抽取各路信号。未评过的层用 NaN 标记而非 0。"""
    n = len(cands)
    if n == 0:
        return {}
    def _col(attr, default=np.nan):
        return np.array([
            (getattr(c, attr) if getattr(c, attr, None) is not None else default)
            for c in cands], dtype=np.float64)
    return {
        "title": _col("s_title", 0.0),
        "l3": _col("s_l3"),
        "l2": _col("s_l2"),
        "l1": _col("s_l1", 0.0),
        "rrf": _col("s_rrf", 0.0),
        "graph": _col("s_graph", 0.0),
    }
