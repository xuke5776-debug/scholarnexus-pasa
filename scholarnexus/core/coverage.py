"""CoverageMeter：多通道捕获–再捕获的召回覆盖度估计（ScholarNexus 创新点 2）。

思想
----
把语义检索、关键词检索、引文前向/后向扩散、作者-脉络扩散视作对同一"相关论文
种群"的多次**独立捕获**。生态学上估计种群总量的成熟工具（Chao1 / Chao2 /
jackknife）可以直接借来估计"这个查询到底存在多少篇相关论文"。

    N̂_chao1 = D + f₁² / (2 f₂)                (f₂ > 0)
    N̂_chao1 = D + f₁(f₁-1) / 2                (f₂ = 0，偏差修正式)

D = 已发现的相关论文数；f₁ = 仅被 1 个通道命中的数量；f₂ = 恰被 2 个通道命中的数量。

它一次性解决两件事：
1. 为 F1-Gate 提供 N̂（以及其不确定性的 bootstrap 样本）；
2. 给出**有统计依据的迭代停止准则**——当覆盖率 D/N̂ ≥ 1-ε，或下一轮预期新增
   相关论文的边际收益低于其成本时停止。把"什么时候停"从玄学变成估计问题，
   直击评测里 20% 的运行效率分。

已知偏差与修正（项目文档中如实讨论）
-----------------------------------
Chao1 假设通道间捕获独立。实际上语义检索与关键词检索高度正相关，会**低估** N。
本模块用两个手段缓解：
  a) `channel_correlation_penalty`：由通道命中矩阵估计平均成对 Jaccard，
     相关性越高 → 对 N̂ 做保守膨胀；
  b) 与查询类型先验做 Bayes 收缩（QueryType 绑定的 N 先验，见 querylens）。
故 N̂ 应被理解为**保守下界的修正估计**，而非无偏估计。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set

import numpy as np


@dataclass
class CoverageEstimate:
    n_hat: float                       # 修正后的基数点估计
    n_hat_raw: float                   # 未做相关性修正的 Chao1
    ci: tuple                          # 对数正态近似的 95% 区间
    samples: np.ndarray                # bootstrap 后验样本，直接喂给 F1-Gate
    discovered: float                  # D（期望意义下的已发现相关论文数）
    f1: float                          # 仅 1 个通道命中的概率质量
    f2: float                          # 恰 2 个通道命中的概率质量
    coverage: float                    # D / N̂
    correlation: float                 # 通道平均成对 Jaccard
    n_channels: int


def _chao1(D: float, f1: float, f2: float, max_ratio: float = 4.0) -> float:
    """偏差修正 Chao1。

    经典式 D + f1²/(2f2) 在 f2→0 时发散 —— 软计数场景下 f2 常常是 0.01 这种
    量级，直接用会算出几百倍于真值的基数（消融实验 A 中 N̂ 中位数达真值的
    21 倍）。这里统一采用 Chao (1987) 的偏差修正式：

        N̂ = D + f1(f1-1) / (2(f2+1))

    分母的 +1 是标准平滑，同时对外推量再设一个 max_ratio 上限兜底：
    捕获-再捕获无法可信地外推超过已观测量数倍的种群，硬截断比发散诚实。
    """
    if D <= 0:
        return 0.0
    extra = (f1 * max(f1 - 1.0, 0.0)) / (2.0 * (f2 + 1.0))
    return D + min(extra, D * max_ratio)


def _chao1_variance(D: float, f1: float, f2: float) -> float:
    """Chao (1987) 的方差近似，用于构造置信区间。"""
    if f2 > 0:
        r = f1 / f2
        return f2 * (0.5 * r ** 2 + r ** 3 + 0.25 * r ** 4)
    if f1 > 1:
        return 0.25 * f1 * (2 * f1 - 1) ** 2 / max(1.0, f1) + 0.5 * f1 * (f1 - 1)
    return float(max(D, 1.0))


def channel_correlation(channel_hits: Dict[str, Set[str]]) -> float:
    """通道之间的平均成对 Jaccard。0 = 完全互补，1 = 完全冗余。"""
    names = [k for k, v in channel_hits.items() if v]
    if len(names) < 2:
        return 0.0
    vals = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = channel_hits[names[i]], channel_hits[names[j]]
            u = len(a | b)
            vals.append(len(a & b) / u if u else 0.0)
    return float(np.mean(vals)) if vals else 0.0


def estimate(channel_hits: Dict[str, Set[str]],
             relevance: Optional[Dict[str, float]] = None,
             p_threshold: float = 0.5,
             prior_mean: Optional[float] = None,
             prior_strength: float = 2.0,
             n_bootstrap: int = 1000,
             seed: int = 0) -> CoverageEstimate:
    """估计相关论文总数 N。

    Parameters
    ----------
    channel_hits : {通道名: 该通道命中的 pid 集合}
    relevance    : {pid: 相关概率}。给定时用**概率加权**的 f1/f2，
                   避免把大量不相关论文的多通道命中计入捕获频次
                   —— 这是把生态学估计量迁移到检索场景的关键改动。
    prior_mean   : 查询类型绑定的 N 先验均值（QueryType → N̂ 先验）
    prior_strength: 先验等效样本量，用于 Bayes 收缩
    """
    rng = np.random.default_rng(seed)

    # 捕获频次统计。关键设计：**纯概率加权，不做硬阈值截断**。
    # 硬阈值(如 p>0.5 才计入)会把判定噪声产生的假阳性整个计入种群，
    # 在低信噪比查询上直接让 D 膨胀数倍、N̂ 随之爆掉。
    # 概率加权等价于统计"期望相关个体数"，是 Chao1 在软标签下的自然推广。
    freq: Counter = Counter()
    weights: Dict[str, float] = {}
    for ch, pids in channel_hits.items():
        for pid in pids:
            w = 1.0 if relevance is None else float(relevance.get(pid, 0.0))
            freq[pid] += 1
            weights[pid] = w

    D_eff = float(sum(weights.values()))          # 期望已发现的相关论文数
    D = D_eff
    if D_eff < 1e-6:
        n0 = float(prior_mean or 1.0)
        return CoverageEstimate(n0, n0, (n0, n0),
                                np.full(64, n0), 0, 0, 0, 0.0, 0.0,
                                len(channel_hits))

    f1 = float(sum(weights[p] for p, c in freq.items() if c == 1))
    f2 = float(sum(weights[p] for p, c in freq.items() if c == 2))

    raw = _chao1(D, f1, f2)

    # (a) 通道相关性修正：相关性 ρ 越高，独立性假设越差，N̂ 越被低估
    rho = channel_correlation(channel_hits)
    inflate = 1.0 + rho * max(0.0, raw - D) / max(raw, 1e-9)
    corrected = D + (raw - D) * inflate

    # (b) 与查询类型先验做对数域 Bayes 收缩
    if prior_mean and prior_mean > 0:
        w_obs = D / (D + prior_strength)   # D 小 → 更信查询类型先验
        corrected = float(np.exp(w_obs * np.log(max(corrected, 1e-9))
                                 + (1 - w_obs) * np.log(prior_mean)))
    corrected = max(corrected, float(D))

    # 置信区间：对 (N - D) 用对数正态近似（Chao & Lee 推荐做法）
    var = _chao1_variance(D, f1, f2)
    extra = max(corrected - D, 1e-6)
    sd_log = float(np.sqrt(np.log(1.0 + var / (extra ** 2))))
    lo = D + extra / np.exp(1.96 * sd_log)
    hi = D + extra * np.exp(1.96 * sd_log)

    samples = D + extra * np.exp(rng.normal(0.0, sd_log, size=n_bootstrap)
                                 - 0.5 * sd_log ** 2)
    samples = np.maximum(samples, float(D))

    return CoverageEstimate(
        n_hat=float(corrected), n_hat_raw=float(raw),
        ci=(float(lo), float(hi)), samples=samples,
        discovered=float(D), f1=float(f1), f2=float(f2),
        coverage=float(D / max(corrected, 1e-9)),
        correlation=rho, n_channels=len([v for v in channel_hits.values() if v]))


# --------------------------------------------------------------------------- #
# 停止准则
# --------------------------------------------------------------------------- #
@dataclass
class StopDecision:
    stop: bool
    reason: str
    coverage: float
    expected_new: float                # 下一轮预期新增相关论文数
    marginal_f1_gain: float            # 折算成的期望 F1 增益


def should_stop(est: CoverageEstimate,
                round_idx: int,
                max_rounds: int,
                budget_exhausted: bool = False,
                target_coverage: float = 0.85,
                last_round_new: Optional[int] = None,
                min_marginal_gain: float = 0.005) -> StopDecision:
    """迭代检索的停止判定。

    三条独立的停止理由，任一触发即停：
      1. 覆盖率达标：D/N̂ ≥ target_coverage
      2. 边际收益枯竭：下一轮预期新增相关论文带来的 F1 增益 < min_marginal_gain
      3. 预算/轮次耗尽
    """
    cov = est.coverage
    # 用 Good-Turing 思路估计"下一次捕获遇到新个体"的概率 ≈ f1 / 总捕获次数
    total_captures = max(est.discovered, 1.0)
    p_new = est.f1 / max(total_captures + est.f1, 1)
    expected_new = p_new * max(est.n_hat - est.discovered, 0.0)
    if last_round_new is not None:
        expected_new = min(expected_new, float(last_round_new))

    gain = 2.0 * expected_new / max(est.discovered + est.n_hat, 1e-9)

    if budget_exhausted:
        return StopDecision(True, "budget_exhausted", cov, expected_new, gain)
    if round_idx >= max_rounds:
        return StopDecision(True, "max_rounds", cov, expected_new, gain)
    if cov >= target_coverage:
        return StopDecision(True, "coverage_reached", cov, expected_new, gain)
    if gain < min_marginal_gain:
        return StopDecision(True, "marginal_gain_below_threshold",
                            cov, expected_new, gain)
    return StopDecision(False, "continue", cov, expected_new, gain)


def weakest_channel(channel_hits: Dict[str, Set[str]],
                    relevance: Dict[str, float],
                    p_threshold: float = 0.5) -> List[tuple]:
    """按"独有相关命中数"排序通道，用于下一轮把预算投给最互补的通道。

    返回 [(channel, unique_relevant, total_relevant), ...]，降序。
    这是策略演化的依据：不是盲目加轮次，而是加**最能带来新个体**的那条通道。
    """
    rel = {p for p, v in relevance.items() if v >= p_threshold}
    out = []
    for ch, pids in channel_hits.items():
        mine = pids & rel
        others: Set[str] = set()
        for ch2, p2 in channel_hits.items():
            if ch2 != ch:
                others |= (p2 & rel)
        out.append((ch, len(mine - others), len(mine)))
    return sorted(out, key=lambda x: -x[1])
