"""F1-Gate：集合级 F1 的最优输出边界求解（ScholarNexus 创新点 1）。

背景
----
本赛题以**集合级 F1**（而非 Recall@K）为主指标，这意味着"返回多少篇"本身
就是一个必须被优化的决策变量。PaSa 式固定 Top-K 和固定人工阈值都不能自适应
查询规模。半 F1 阈值性质沿用 Lipton、Elkan、Naryanaswamy（2014）；本模块
重点实现其与 N̂ 不确定性、结果分层和预算控制的组合。

推导
----
设候选 i 的校准相关概率为 p_i，真值集合基数为 N。对输出集合 S：

    E[TP] = Σ_{i∈S} p_i ,  |G| = N

    Ẽ[F1](S) ≈ 2·Σ_{i∈S} p_i / (|S| + N)          … (1)

(1) 是"期望之比"而非"比之期望"，属一阶 delta 近似；在 |S|+N 较大时误差可忽略，
本模块另提供 Monte-Carlo 精确版 `expected_f1_mc` 用于校核。

给定 (1)，最优集合必为按 p 降序的前缀（证明：若 i∉S, j∈S 且 p_i>p_j，交换严格
不劣）。因此只需在 k 上做一维搜索。把第 k+1 项加入的增量条件为：

    2(S_k + p_{k+1})/(k+1+N) > 2 S_k/(k+N)
    ⟺ p_{k+1}·(k+N) > S_k
    ⟺ p_{k+1} > S_k/(k+N) = Ẽ[F1]_k / 2          … (2)

即 **最优纳入门限恰为最优 F1 值的一半**，是一个不动点。三个直接推论：

1. 必须输出**校准过的概率**，LLM 随口给的 1–10 分不可用 → calibrate.py
2. 必须估计**真值集合基数 N̂**："找某一篇"(N≈1) 与"某方向全部工作"(N≈60)
   的最优操作点相差一个数量级 → coverage.py
3. 昂贵的 LLM 精判只应花在 p_i 落在门限附近的**不确定带** → 判定预算分配

N̂ 的不确定性
-------------
Chao1 等估计量方差很大，直接代入点估计会系统性偏保守或偏激进。
`optimal_cutoff` 支持传入 N 的样本（或均值/标准差），对 F1 关于 N 求期望后再
取 argmax —— 这比"先估 N 再算 F1"更稳健，也是本模块与朴素实现的区别。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

import numpy as np


# --------------------------------------------------------------------------- #
# 基础量
# --------------------------------------------------------------------------- #
def expected_f1_curve(p_sorted: Sequence[float], n_hat: float) -> np.ndarray:
    """返回 k=1..n 时的 Ẽ[F1]，p_sorted 必须已按降序排列。"""
    p = np.asarray(p_sorted, dtype=np.float64)
    if p.size == 0:
        return np.zeros(0)
    cum = np.cumsum(p)
    k = np.arange(1, p.size + 1, dtype=np.float64)
    return 2.0 * cum / (k + max(n_hat, 1e-9))


def expected_f1_mc(p_sorted: Sequence[float], k: int, n_samples: np.ndarray,
                   rng: Optional[np.random.Generator] = None,
                   draws: int = 2000) -> float:
    """Monte-Carlo 精确期望 F1，用于校核 (1) 式的近似误差。

    对每次抽样：TP ~ PoissonBinomial(p_1..p_k)，N 从 n_samples 抽取，
    并强制 N >= TP（真值集合至少包含被命中的部分）。
    """
    rng = rng or np.random.default_rng(0)
    p = np.asarray(p_sorted[:k], dtype=np.float64)
    if p.size == 0:
        return 0.0
    hits = (rng.random((draws, p.size)) < p).sum(axis=1)
    n = rng.choice(np.asarray(n_samples, dtype=np.float64), size=draws)
    n = np.maximum(n, hits)
    return float(np.mean(2.0 * hits / np.maximum(k + n, 1e-9)))


# --------------------------------------------------------------------------- #
# 主入口
# --------------------------------------------------------------------------- #
@dataclass
class GateDecision:
    k: int                      # 纳入的论文数
    threshold: float            # 生效门限 p*（= 最优 F1 / 2 的不动点）
    expected_f1: float          # 该 k 下的期望 F1
    core_k: int                 # "高度相关"分层的截断位置
    n_hat_used: float           # 实际生效的 N̂（期望意义）
    curve: np.ndarray           # 完整 F1(k) 曲线，供审计与可视化
    uncertainty_band: tuple     # (lo_idx, hi_idx)：p 落在门限附近的不确定带


def optimal_cutoff(p_scores: Sequence[float],
                   n_hat: float | None = None,
                   n_samples: Optional[Sequence[float]] = None,
                   min_k: int = 1,
                   max_k: Optional[int] = None,
                   core_ratio: float = 1.0,
                   band_width: float = 0.15,
                   enforce_consistency: bool = True) -> GateDecision:
    """求解 F1 最优输出边界。

    Parameters
    ----------
    p_scores : 候选的校准相关概率（无需预排序）
    n_hat    : 真值集合基数点估计；与 n_samples 二选一
    n_samples: 真值集合基数的后验样本（推荐，来自 coverage.py 的 bootstrap）
    core_ratio: 高度相关分层的门限倍率。1.0 表示 core 门限 = p*，
                取 1.5 则 core 更严格（p > 1.5·p*），partial 落在 [p*, 1.5p*)
    band_width: 不确定带半宽（以概率绝对值计），用于 VoI 预算分配

    Returns
    -------
    GateDecision
    """
    p = np.asarray(p_scores, dtype=np.float64)
    if p.size == 0:
        return GateDecision(0, 1.0, 0.0, 0, float(n_hat or 0.0),
                            np.zeros(0), (0, 0))

    order = np.argsort(-p)
    ps = p[order]
    n_cap = int(max_k or ps.size)
    n_cap = min(n_cap, ps.size)

    # 一致性约束：候选池内的期望相关论文数 Σp 不可能超过真值集合基数 N。
    # 违反它会让 Ẽ[F1] 算出 >1 的荒谬值，并使门限系统性偏高。
    # 这条约束把「校准」与「基数估计」两个模块耦合成自洽的整体。
    if enforce_consistency:
        mass = float(ps.sum())
        if n_hat is not None:
            n_hat = max(float(n_hat), mass)
        if n_samples is not None and len(n_samples) > 0:
            n_samples = np.maximum(np.asarray(n_samples, dtype=np.float64), mass)

    if n_samples is not None and len(n_samples) > 0:
        # 对 N 的不确定性取期望：E_N[ 2·S_k/(k+N) ]
        ns = np.asarray(n_samples, dtype=np.float64)
        ns = np.maximum(ns, 1e-9)
        cum = np.cumsum(ps)[:n_cap]
        k = np.arange(1, n_cap + 1, dtype=np.float64)
        # (n_cap, n_draws) 广播；n_draws 通常 <= 2000，内存可控
        curve = np.mean(2.0 * cum[:, None] / (k[:, None] + ns[None, :]), axis=1)
        n_used = float(np.mean(ns))
    else:
        n_used = float(n_hat if n_hat is not None else max(1.0, 0.1 * ps.size))
        curve = expected_f1_curve(ps[:n_cap], n_used)

    lo = max(0, min_k - 1)
    k_star = int(np.argmax(curve[lo:]) + lo) + 1
    f1_star = float(curve[k_star - 1])
    thr = f1_star / 2.0                       # 不动点：p* = F1* / 2

    # 分层：core = 明确高于门限的部分
    core_thr = thr * core_ratio
    core_k = int(np.sum(ps[:k_star] > core_thr))
    core_k = max(min(core_k, k_star), 1 if k_star > 0 else 0)

    # 不确定带：判定结果可能跨越门限的候选区间（VoI 精判的目标区）
    band_lo = int(np.searchsorted(-ps, -(thr + band_width), side="left"))
    band_hi = int(np.searchsorted(-ps, -(thr - band_width), side="right"))

    return GateDecision(k=k_star, threshold=float(thr), expected_f1=f1_star,
                        core_k=core_k, n_hat_used=n_used, curve=curve,
                        uncertainty_band=(band_lo, band_hi))


def verify_fixed_point(p_scores: Sequence[float], n_hat: float,
                       tol: float = 1e-9) -> dict:
    """验证不动点性质 (2)：k* 处应满足 p_{k*} >= F1*/2 > p_{k*+1}。

    作为单元测试与项目文档中的形式化论证依据。
    """
    ps = np.sort(np.asarray(p_scores, dtype=np.float64))[::-1]
    d = optimal_cutoff(ps, n_hat=n_hat)
    k = d.k
    inside = float(ps[k - 1]) if k >= 1 else 1.0
    outside = float(ps[k]) if k < ps.size else -1.0
    return {
        "k": k,
        "f1_star": d.expected_f1,
        "threshold": d.threshold,
        "p_at_k": inside,
        "p_at_k_plus_1": outside,
        "holds": bool(inside + tol >= d.threshold >= outside - tol),
    }


def voi_scores(p_scores: Sequence[float], sigma: Sequence[float],
               threshold: float, n_hat: float) -> np.ndarray:
    """信息价值：精判一篇论文能改变纳入决策的概率 × 该决策的 F1 影响。

    VoI(i) ∝ Pr[ 精判后 p_i 跨越 p* ] · |ΔF1|

    用高斯近似 Pr[跨越] = Φ(-|p_i - p*| / σ_i)。σ_i 由判定层级给出
    （L1 粗排 σ 大、L3 精判 σ 小）。ΔF1 用 (1) 式对单篇的边际影响近似。
    这条把创新点 1 的门限与创新点 3 的预算分配串成闭环：
    **门限告诉我们该把钱花在哪。**
    """
    p = np.asarray(p_scores, dtype=np.float64)
    s = np.maximum(np.asarray(sigma, dtype=np.float64), 1e-6)
    from math import erf, sqrt
    z = -np.abs(p - threshold) / (s * np.sqrt(2.0))
    cross = 0.5 * (1.0 + np.vectorize(erf)(z))          # = Φ(-|Δ|/σ)
    delta_f1 = 2.0 * np.abs(p - threshold) / max(1.0 + n_hat, 1e-9)
    return cross * delta_f1
