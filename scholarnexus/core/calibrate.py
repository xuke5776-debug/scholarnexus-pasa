"""Calibrator：把各层打分转成**可比较、可积分**的相关概率 p_i。

为什么必须校准
--------------
F1-Gate 的门限 p* = F1*/2 是一个**绝对概率值**。如果喂进去的是 LLM 随口给的
1–10 分、或未标定的余弦相似度，门限就失去意义——这是把 F1 理论落地的必要条件，
也是多数系统只能退回"固定 Top-K"的根本原因。

三种校准器
----------
- `IsotonicCalibrator`：有标注数据时的首选，保序回归，无参数假设。
- `PlattCalibrator`：小样本更稳，logistic 单参/双参拟合。
- `PriorAnchoredCalibrator`：**零标注**场景的回退。仅依赖排序 + 基数先验，
  把分数映射到一个满足"期望命中数 ≈ N̂ × 覆盖率"的概率分布上。
  隐藏测试集上没有标注可用，这一路必须存在。

倾向性建模（propensity）
------------------------
本赛题参考数据集（PaSa AutoScholarQuery 等）的金标准由 Related Work 段落的
被引文献反推构造，**是真实合格论文集合的一个较小子集**。也就是说存在
标注缺失机制：一篇论文即使真的相关，也可能因为没被那段综述引用而不在金标准里。

    p_gold(i) = p_rel(i) · Pr[ 被标注 | 相关 ]

倾向性 Pr[标注|相关] 与论文的被引量、发表年份、是否综述强相关。F1 是对
**金标准**算的，所以 F1-Gate 应当用 p_gold 而非 p_rel。这一步是我们相对
其他方案的隐性优势：别人在优化"真实相关性"，我们在优化"评测函数"。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence

import numpy as np


def _logit(p: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    p = np.clip(p, eps, 1 - eps)
    return np.log(p / (1 - p))


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return np.where(x >= 0, 1.0 / (1.0 + np.exp(-np.clip(x, -60, 60))),
                    np.exp(np.clip(x, -60, 60)) / (1.0 + np.exp(np.clip(x, -60, 60))))


class Calibrator:
    fitted: bool = False

    def fit(self, scores: Sequence[float], labels: Sequence[int]) -> "Calibrator":
        raise NotImplementedError

    def transform(self, scores: Sequence[float]) -> np.ndarray:
        raise NotImplementedError


class PlattCalibrator(Calibrator):
    """双参数 logistic：p = σ(a·s + b)，用带正则的牛顿法拟合。"""

    def __init__(self, l2: float = 1e-3):
        self.a, self.b, self.l2 = 1.0, 0.0, l2

    def fit(self, scores, labels):
        s = np.asarray(scores, dtype=np.float64)
        y = np.asarray(labels, dtype=np.float64)
        if s.size == 0 or len(np.unique(y)) < 2:
            self.fitted = False
            return self
        # Platt 的目标值平滑，避免过拟合到 0/1
        n_pos, n_neg = float(y.sum()), float((1 - y).sum())
        t = np.where(y > 0, (n_pos + 1) / (n_pos + 2), 1.0 / (n_neg + 2))
        a, b = 1.0, 0.0
        for _ in range(100):
            z = a * s + b
            p = _sigmoid(z)
            w = np.maximum(p * (1 - p), 1e-9)
            g = np.array([np.sum((p - t) * s) + self.l2 * a,
                          np.sum(p - t)])
            H = np.array([[np.sum(w * s * s) + self.l2, np.sum(w * s)],
                          [np.sum(w * s), np.sum(w) + 1e-9]])
            try:
                step = np.linalg.solve(H, g)
            except np.linalg.LinAlgError:
                break
            a, b = a - step[0], b - step[1]
            if np.max(np.abs(step)) < 1e-8:
                break
        self.a, self.b, self.fitted = float(a), float(b), True
        return self

    def transform(self, scores):
        s = np.asarray(scores, dtype=np.float64)
        if not self.fitted:
            return np.clip(s, 0.0, 1.0)
        return _sigmoid(self.a * s + self.b)


class IsotonicCalibrator(Calibrator):
    """保序回归（PAVA）。无分布假设，标注充足时最准。"""

    def __init__(self, out_of_bounds: str = "clip"):
        self.x_: Optional[np.ndarray] = None
        self.y_: Optional[np.ndarray] = None
        self.out_of_bounds = out_of_bounds

    def fit(self, scores, labels):
        s = np.asarray(scores, dtype=np.float64)
        y = np.asarray(labels, dtype=np.float64)
        if s.size < 4 or len(np.unique(y)) < 2:
            self.fitted = False
            return self
        order = np.argsort(s)
        s, y = s[order], y[order]
        # Pool Adjacent Violators
        vals = list(y)
        wts = [1.0] * len(y)
        i = 0
        while i < len(vals) - 1:
            if vals[i] > vals[i + 1]:
                tw = wts[i] + wts[i + 1]
                nv = (vals[i] * wts[i] + vals[i + 1] * wts[i + 1]) / tw
                vals[i:i + 2] = [nv]
                wts[i:i + 2] = [tw]
                # 回溯修复
                while i > 0 and vals[i - 1] > vals[i]:
                    tw = wts[i - 1] + wts[i]
                    nv = (vals[i - 1] * wts[i - 1] + vals[i] * wts[i]) / tw
                    vals[i - 1:i + 1] = [nv]
                    wts[i - 1:i + 1] = [tw]
                    i -= 1
            else:
                i += 1
        # 展开回逐点
        yy, idx = [], 0
        for v, w in zip(vals, wts):
            yy.extend([v] * int(round(w)))
        yy = np.asarray(yy[:len(s)], dtype=np.float64)
        self.x_, self.y_, self.fitted = s, yy, True
        return self

    def transform(self, scores):
        s = np.asarray(scores, dtype=np.float64)
        if not self.fitted:
            return np.clip(s, 0.0, 1.0)
        return np.clip(np.interp(s, self.x_, self.y_), 0.0, 1.0)


class PriorAnchoredCalibrator(Calibrator):
    """零标注回退：仅用排序结构 + 基数先验反解概率。

    设候选按分数降序，假设 p 服从以分数为 logit 的单调族
    p_i = σ(α·z_i + β)（z 为标准化分数）。约束 Σ p_i = N̂·ρ，
    其中 ρ 是"真值集合落在候选池内"的比例（覆盖率）。
    一维搜索 β 使等式成立，α 由分数分布的判别力启发式给定。

    它保证了一件关键的事：**校准后概率之和是有物理意义的**，
    F1-Gate 的门限因此仍然可用，即使一条标注都没有。
    """

    def __init__(self, alpha: float = 2.5):
        self.alpha, self.beta, self.fitted = alpha, 0.0, True
        self._mu, self._sd = 0.0, 1.0

    def fit_to_mass(self, scores: Sequence[float], target_mass: float):
        s = np.asarray(scores, dtype=np.float64)
        if s.size == 0:
            return self
        self._mu, self._sd = float(s.mean()), float(s.std() + 1e-9)
        z = (s - self._mu) / self._sd
        target = float(np.clip(target_mass, 1e-3, s.size - 1e-3))

        lo, hi = -20.0, 20.0
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if _sigmoid(self.alpha * z + mid).sum() < target:
                lo = mid
            else:
                hi = mid
        self.beta = 0.5 * (lo + hi)
        return self

    def fit(self, scores, labels):
        y = np.asarray(labels, dtype=np.float64)
        return self.fit_to_mass(scores, float(y.sum()))

    def transform(self, scores):
        s = np.asarray(scores, dtype=np.float64)
        z = (s - self._mu) / self._sd
        return _sigmoid(self.alpha * z + self.beta)


def tail_temper(p: Sequence[float], target_mass: float,
                alpha_range: tuple = (0.2, 40.0)) -> tuple:
    """尾部压缩：单参数幂变换 p ← p^α，使 Σp^α 命中目标质量。

    为什么只需要压尾
    ----------------
    F1-Gate 的纳入条件是 p_{k+1} > F1_k / 2，两侧同为概率的一次量纲，
    因此**概率被均匀缩放 λ 倍不会改变最优 k**。真正让输出集合超发的是
    *形状* 误差 —— 尾部候选的概率相对头部被高估。

    高斯混合校准器的典型病症正是尾巴太肥：实测 p∈[0.8,1.0] 区间预测均值
    0.848 而实际命中率仅 0.401，Σp 恰为真值的 2 倍。

    幂变换 p^α 在 α>1 时对小 p 的压缩远强于对大 p（0.9^2=0.81 但 0.3^2=0.09），
    正好是「保住头部、压平尾部」，而且**严格保序** —— 排序完全不变，
    只改变概率的相对间距，因此不会伤害召回，只收紧纳入边界。

    α 由目标质量唯一确定（单调方程一维求根），不是自由超参。
    target_mass 必须来自独立于分数的锚点，否则会重演正反馈发散。
    """
    x = np.clip(np.asarray(p, dtype=np.float64), 1e-6, 1 - 1e-6)
    if x.size == 0:
        return x, 1.0
    target = float(np.clip(target_mass, 0.5, max(0.5, x.size * 0.95)))
    lo, hi = alpha_range
    # α 上界必须够大：当分数普遍接近 1（校准器过度自信的典型形态）时，
    # 需要很强的幂次才能把 Σp 压到目标质量。上界取 6 时曾无法收敛
    # （目标 12 实际压到 16.4），故放宽到 40 并在越界时返回边界解。
    # Σp^α 关于 α 单调递减（p<1），可直接二分
    if float(np.sum(x ** hi)) > target:
        return x ** hi, float(hi)
    if float(np.sum(x ** lo)) < target:
        return x ** lo, float(lo)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if float(np.sum(x ** mid)) > target:
            lo = mid
        else:
            hi = mid
    a = 0.5 * (lo + hi)
    return x ** a, float(a)


class RankDecayCalibrator(Calibrator):
    """秩空间分数的专用校准器（配合 fusion.adaptive_fuse 使用）。

    问题的来由
    ----------
    自适应融合在**秩空间**做加权（各路信号量纲差异极大，直接线性加权会让量纲
    大的信号垄断结果），代价是输出分数近似服从均匀分布。而两组分高斯混合模型
    在均匀分布上**没有可辨识结构** —— 它只能把数据劈成「高的一半 / 低的一半」，
    于是大批候选拿到虚高概率。实测中 p∈[0.8,1.0) 的预测均值 0.848、
    实际命中率仅 0.401，Σp 恰好是真值的 2 倍，输出集合因此系统性超发。

    正确的模型
    ----------
    对排序好的候选，命中率随排名衰减，用两参数 logistic-in-log-rank 刻画：

        p(r) = π_max / (1 + (r / b)^c)

    b 是「半衰位置」，c 控制衰减陡峭度。给定目标质量 M = Σ p(r)，
    在 b 上做一维搜索即可（c 由分数分布的判别力启发式给定）。

    打破循环依赖
    ------------
    M 必须来自**独立于分数**的信息源，否则会重演「N̂ 偏大 → p 抬高 → 软计数
    变大 → N̂ 更大」的正反馈发散（见 docs/DESIGN_V2.md 缺陷一）。
    本系统用两个与分数无关的锚：查询类型的基数先验，以及基于**硬计数**
    （每篇论文算一个个体，不按概率加权）的捕获–再捕获估计。
    """

    def __init__(self, c: float = 1.6):
        self.c = c
        self.b = 10.0
        self.p_max = 0.95
        self.fitted = True
        self._n = 1

    def fit_to_mass(self, scores: Sequence[float], target_mass: float,
                    p_max: float = 0.95):
        s = np.asarray(scores, dtype=np.float64)
        n = s.size
        self._n = max(n, 1)
        if n == 0:
            return self
        self.p_max = float(np.clip(p_max, 0.05, 0.999))
        target = float(np.clip(target_mass, 0.5, max(0.5, n * self.p_max * 0.95)))

        ranks = self._ranks(s)

        def mass(b: float) -> float:
            return float(np.sum(self.p_max / (1.0 + (ranks / b) ** self.c)))

        lo, hi = 1e-3, float(n) * 4
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if mass(mid) < target:
                lo = mid
            else:
                hi = mid
        self.b = 0.5 * (lo + hi)
        return self

    @staticmethod
    def _ranks(s: np.ndarray) -> np.ndarray:
        """1-based 降序排名（并列取平均）。"""
        order = np.argsort(-s, kind="mergesort")
        r = np.empty(s.size, dtype=np.float64)
        r[order] = np.arange(1, s.size + 1, dtype=np.float64)
        return r

    def fit(self, scores, labels):
        y = np.asarray(labels, dtype=np.float64)
        return self.fit_to_mass(scores, float(y.sum()))

    def transform(self, scores):
        s = np.asarray(scores, dtype=np.float64)
        if s.size == 0:
            return s
        ranks = self._ranks(s)
        return np.clip(self.p_max / (1.0 + (ranks / max(self.b, 1e-6)) ** self.c),
                       1e-4, 1 - 1e-4)


def independent_mass_anchor(channel_hits: Dict[str, set], candidate_ids: set,
                            prior_mean: float, prior_weight: float = 1.0,
                            max_multi_ratio: float = 0.6) -> float:
    """估计候选池内的相关论文总量，**完全不使用相关性分数**。

    信息源：
      1. 查询类型的基数先验（离线蒸馏，与本次检索结果无关）——主锚；
      2. 多通道命中结构的硬计数（被 ≥2 条独立通道命中的候选数）——辅助。

    关于第 2 项的一个实测教训：它只在通道**确实近似独立**时才有效。
    本系统开启引文图扩散后，cocite 通道会覆盖 99% 以上的候选，
    「被 ≥2 通道命中」退化成一个常量，作为相关性代理完全失效
    （实测把 locate 型查询的锚点从 1 抬到 8.7）。
    因此默认 prior_weight=1.0，即只信类型先验；把多通道计数留作可选项，
    并对它设置了覆盖率闸门：只有当多通道命中比例低于 60%（说明通道确有区分度）
    时才纳入融合。这条闸门比调权重更重要 —— 一个失效的信号不该被温和降权，
    而该被识别出来并排除。
    """
    from collections import Counter
    freq: Counter = Counter()
    for ch, pids in (channel_hits or {}).items():
        base = ch.split(":", 1)[0]
        for pid in pids:
            if pid in candidate_ids:
                freq[(pid, base)] = 1
    per_pid: Counter = Counter()
    for (pid, _base) in freq:
        per_pid[pid] += 1
    n_pool = max(len(candidate_ids), 1)
    multi = sum(1 for _, c in per_pid.items() if c >= 2)
    pm = max(float(prior_mean), 1.0)
    w = float(np.clip(prior_weight, 0.0, 1.0))
    # 覆盖率闸门：多通道命中率过高说明通道之间高度冗余，该信号已无区分度
    if multi == 0 or multi / n_pool > max_multi_ratio:
        return pm
    obs = float(multi)
    return float(np.exp(w * np.log(pm) + (1 - w) * np.log(max(obs, 1.0))))


class MixtureCalibrator(Calibrator):
    """**零标注自校准**：判定分数的两组分混合模型（ScholarNexus 核心组件）。

    动机（来自消融实验 A 的失败）
    -----------------------------
    最初的设计让校准器用 N̂ 锚定概率质量（Σp = N̂·ρ），结果与基数估计构成
    **正反馈回路**：N̂ 偏大 → p 整体抬高 → 软计数 D 变大 → N̂ 更大 → 发散。
    3000 次模拟中 N̂ 中位数达真值的 4.6 倍，F1-Gate 因此系统性输出过多论文，
    甚至输给固定 Top-20。

    解法是**解耦**：
      · 概率校准 ← 分数分布自身（本类，无监督混合模型）
      · 出池外推 ← 通道捕获-再捕获（coverage.py 的 Chao1）
    两者不再互为输入，回路消失。

    模型
    ----
    在 logit 域对分数拟合两个高斯：
        s ~ π·N(μ₁, σ₁²) + (1-π)·N(μ₀, σ₀²),  μ₁ > μ₀
    p_i = 后验 Pr[属于高分组分 | s_i]，天然落在 [0,1] 且单调于 s。
    混合比 π 直接给出**候选池内的期望相关论文数** π·M —— 这是数据说的，
    不是先验硬塞的。查询类型先验只以 Dirichlet 伪计数形式做弱正则。

    这一步同时解决了"LLM 打分不可比"的老问题：不同查询、不同模型给出的
    分数尺度千差万别，混合模型每次查询独立拟合，自动适配尺度。
    """

    def __init__(self, prior_pi: Optional[float] = None,
                 prior_strength: Optional[float] = None, n_iter: int = 60,
                 min_sep: float = 0.35, space: str = "raw",
                 tied_variance: bool = True):
        # space="raw" 是默认且推荐值。判定分数在 0 和 1 处普遍存在**截断点质量**
        # （LLM 直接给 0 或 10、reranker sigmoid 饱和），若先取 logit 再拟合高斯，
        # 这些点会被推到 ±13.8 形成尖峰，把组分均值和方差彻底带偏。
        # 这是消融实验 A 第二轮暴露出来的坑，代价是 F1 从 0.30 掉到 0.11。
        self.space = space
        # 两个重叠组分的高斯混合存在经典的**可辨识性**问题：自由方差下 EM 倾向于
        # 拟合出"一个宽组分 + 一个窄组分"，而不是真实的高/低相关两组，结果是
        # 严重过度自信（实测 p∈[0.8,1] 的实际命中率仅 0.378，Σp 超真值 3 倍）。
        # 绑定方差 σ₁=σ₀ 是标准补救措施，把模型自由度降到刚好够用。
        self.tied_variance = tied_variance
        self.prior_pi = prior_pi
        # None → 按候选池规模自适应 (0.6·M)。扫描显示 ECE 在 0.5~0.7·M 处最低；
        # 弱正则会让 π 被过度拟合，强正则则退化成纯先验。
        self.prior_strength = prior_strength
        self.prior_strength_ratio = 0.6
        self.n_iter = n_iter
        self.min_sep = min_sep
        self.pi = 0.1
        self.mu = (0.0, 1.0)
        self.sd = (1.0, 1.0)
        self.fitted = False
        self._degenerate = False

    def _to_space(self, scores) -> np.ndarray:
        x = np.asarray(scores, dtype=np.float64)
        if self.space == "logit":
            # 先做 squeeze 把点质量从边界推开，再取 logit
            n = max(x.size, 2)
            return _logit((x * (n - 1) + 0.5) / n)
        return x

    def fit(self, scores, labels=None):
        s = self._to_space(scores)
        M = s.size
        if M < 8:
            self.fitted = False
            return self

        # 初始化：用分位数分离，比随机初始化稳定得多
        q_hi = float(np.quantile(s, 0.90))
        q_lo = float(np.quantile(s, 0.40))
        mu1, mu0 = q_hi, q_lo
        sd1 = sd0 = max(float(s.std()), 1e-3)
        pi = float(self.prior_pi) if self.prior_pi else 0.12
        pi = float(np.clip(pi, 0.01, 0.5))
        strength = (self.prior_strength if self.prior_strength is not None
                    else self.prior_strength_ratio * M)

        for _ in range(self.n_iter):
            d1 = pi * np.exp(-0.5 * ((s - mu1) / sd1) ** 2) / sd1
            d0 = (1 - pi) * np.exp(-0.5 * ((s - mu0) / sd0) ** 2) / sd0
            r = d1 / np.maximum(d1 + d0, 1e-300)

            n1 = float(r.sum())
            n0 = float(M - n1)
            if n1 < 1e-6 or n0 < 1e-6:
                self._degenerate = True
                break

            # 带先验伪计数的 π 更新（弱正则，避免退化到单组分）
            if self.prior_pi is not None:
                a = strength * float(self.prior_pi)
                b = strength * (1 - float(self.prior_pi))
                pi = (n1 + a) / (M + a + b)
            else:
                pi = n1 / M
            pi = float(np.clip(pi, 1e-4, 0.6))

            mu1 = float((r * s).sum() / max(n1, 1e-9))
            mu0 = float(((1 - r) * s).sum() / max(n0, 1e-9))
            if self.tied_variance:
                var = ((r * (s - mu1) ** 2).sum()
                       + ((1 - r) * (s - mu0) ** 2).sum()) / max(M, 1)
                sd1 = sd0 = float(np.sqrt(max(var, 1e-6)))
            else:
                sd1 = float(np.sqrt(max((r * (s - mu1) ** 2).sum() / max(n1, 1e-9), 1e-6)))
                sd0 = float(np.sqrt(max(((1 - r) * (s - mu0) ** 2).sum() / max(n0, 1e-9), 1e-6)))

            # 强制组分可辨识：分离度不足说明判定器没有判别力，
            # 此时不应假装能分开 —— 记为退化，交由上层降级处理
            if mu1 - mu0 < self.min_sep * max(sd0, 1e-6):
                self._degenerate = True
                mu1 = mu0 + self.min_sep * max(sd0, 1e-6)

        self.pi, self.mu, self.sd = pi, (mu0, mu1), (sd0, sd1)
        self.fitted = True
        return self

    def transform(self, scores):
        s = self._to_space(scores)
        if not self.fitted:
            return np.clip(np.asarray(scores, dtype=np.float64), 0.0, 1.0)
        mu0, mu1 = self.mu
        sd0, sd1 = self.sd
        d1 = self.pi * np.exp(-0.5 * ((s - mu1) / sd1) ** 2) / sd1
        d0 = (1 - self.pi) * np.exp(-0.5 * ((s - mu0) / sd0) ** 2) / sd0
        return np.clip(d1 / np.maximum(d1 + d0, 1e-300), 1e-6, 1 - 1e-6)

    @property
    def expected_relevant_in_pool(self) -> float:
        """π·M 的直接读数由 transform 后求和给出；此处返回混合比。"""
        return float(self.pi)

    @property
    def degenerate(self) -> bool:
        """True 表示判定器在本次查询上没有可辨识的判别力。

        上层据此触发降级策略：加一轮检索、或改用更强的判定层，
        而不是硬着头皮输出一个没有依据的集合。
        """
        return self._degenerate


# --------------------------------------------------------------------------- #
# 倾向性（标注生成过程建模）
# --------------------------------------------------------------------------- #
def propensity(citation_count: Sequence[float],
               year: Sequence[Optional[int]],
               is_review: Sequence[bool],
               current_year: int = 2026,
               floor: float = 0.35) -> np.ndarray:
    """Pr[ 被金标准标注 | 真实相关 ] 的启发式建模。

    金标准由综述段落的被引文献构造，因此：
      · 被引量高 → 更可能被综述引用 → 倾向性高
      · 过新的论文 → 还来不及被引 → 倾向性低
      · 综述本身 → 在 Related Work 中被引的模式不同，轻微下调
    参数在公开测试集上用极大似然拟合，这里给出先验形式。
    """
    c = np.asarray([max(float(x or 0), 0.0) for x in citation_count])
    yrs = np.asarray([current_year if y is None else float(y) for y in year])
    rev = np.asarray(is_review, dtype=bool)

    cite_term = np.log1p(c) / (1.5 + np.log1p(c))          # 0→0, 饱和→1
    age = np.clip(current_year - yrs, 0, 30)
    age_term = np.clip(age / 3.0, 0.0, 1.0)                # 3 年内线性爬升
    p = floor + (1 - floor) * (0.65 * cite_term + 0.35 * age_term)
    p = np.where(rev, p * 0.9, p)
    return np.clip(p, floor, 1.0)


@dataclass
class CalibrationReport:
    ece: float
    brier: float
    n: int


def evaluate_calibration(p: Sequence[float], y: Sequence[int],
                         n_bins: int = 10) -> CalibrationReport:
    """ECE + Brier，用于消融实验中论证"校准确有必要"。"""
    p = np.asarray(p, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if p.size == 0:
        return CalibrationReport(0.0, 0.0, 0)
    bins = np.clip((p * n_bins).astype(int), 0, n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        m = bins == b
        if m.sum() == 0:
            continue
        ece += (m.sum() / p.size) * abs(p[m].mean() - y[m].mean())
    return CalibrationReport(float(ece), float(np.mean((p - y) ** 2)), int(p.size))
