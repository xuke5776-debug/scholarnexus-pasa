"""CascadeJudge：四级判定级联（创新点 3「信息价值驱动的判定预算分配」）。

    L0  元数据硬过滤     零成本   年份 / venue / 文献类型 / 明显缺字段
    L1  多信号融合粗排   零成本   RRF + 图先验 + 词法覆盖，剪掉 90% 候选
    L2  cross-encoder    零 token 本地精排，判别力接近小参数量 LLM
    L3  大模型约束核验   计费     只判「结果可能跨越门限」的不确定带

关键在 L3 的**分配**而非 L3 本身。定义信息价值

    VoI(i) ∝ Pr[精判后 p_i 跨越 p*] · ΔF1(i)

只有当一篇论文的判定结果可能改变它的去留时，昂贵判定才有价值。而 p* 正是
F1-Gate 解出的不动点门限 —— **创新点 1 的阈值直接告诉创新点 3 该把钱花在哪**。
这是整套方案的理论闭环，不是模块堆叠。

L3 的证据对齐强校验
-------------------
每条判为满足的约束必须附带论文原文证据片段，且证据必须能在标题/摘要中被验证
存在（`_verify_evidence`）。模型说满足却给不出原文、或给出的「原文」根本不在
论文里（幻觉），一律降级为 unknown 并扣减相关度。这一条是精确率的主要来源，
机制借鉴自 Ray-Source 的答案—证据对齐校验（见 docs/CREDITS.md）。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..llm import BudgetExhausted, LLMClient
from ..llm.prompts import (JUDGE_SYSTEM, JUDGE_USER, render_constraints,
                           render_papers)
from ..rank.rerank import BaseReranker, RerankItem
from ..schema import (Candidate, Constraint, ConstraintCheck, ConstraintKind,
                      ConstraintRole, QueryPlan)
from ..utils import title_similarity, tokenize
from .constraint_graph import match_paper

# 各判定层级的分数不确定度（供 VoI 的高斯近似使用）
SIGMA_BY_LEVEL = {0: 0.35, 1: 0.30, 2: 0.16, 3: 0.07}


@dataclass
class JudgeStats:
    l0_dropped: int = 0
    l1_kept: int = 0
    l2_scored: int = 0
    l3_judged: int = 0
    l3_calls: int = 0
    evidence_rejected: int = 0        # 因证据不可验证被降级的约束数


class CascadeJudge:
    def __init__(self, reranker: BaseReranker, llm: Optional[LLMClient] = None,
                 ledger=None, cfg: Optional[Dict] = None):
        self.reranker = reranker
        self.llm = llm
        self.ledger = ledger
        self.cfg = cfg or {}
        self.stats = JudgeStats()

    # ================================================================== #
    # L0：元数据硬过滤（零成本）
    # ================================================================== #
    def l0_filter(self, cands: Sequence[Candidate],
                  plan: QueryPlan) -> List[Candidate]:
        """硬约束直接过滤。注意这里只处理**确定性可判**的约束。

        年份缺失不等于不满足 —— 元数据缺失在学术 API 里很常见，
        把缺失当作违反会误杀真正的目标论文。所以缺失一律放行，交给后续层级。
        """
        f = plan.api_filters()
        ymin, ymax = f.get("year_min"), f.get("year_max")
        venues = {v.upper() for v in f.get("venues", [])}
        neg_review = any(c.role == ConstraintRole.NEGATIVE
                         and c.kind == ConstraintKind.DOC_TYPE
                         for c in plan.constraints)
        out = []
        for c in cands:
            p = c.paper
            if not p.title or len(p.title) < 8:
                self.stats.l0_dropped += 1
                continue
            if ymin and p.year and p.year < int(ymin):
                self.stats.l0_dropped += 1
                continue
            if ymax and p.year and p.year > int(ymax):
                self.stats.l0_dropped += 1
                continue
            if venues and p.venue:
                vu = p.venue.upper()
                if not any(v in vu for v in venues):
                    self.stats.l0_dropped += 1
                    continue
            if neg_review and p.is_review:
                self.stats.l0_dropped += 1
                continue
            out.append(c)
        return out

    # ================================================================== #
    # L1：多信号融合粗排（零成本）
    # ================================================================== #
    def l1_rank(self, cands: Sequence[Candidate], plan: QueryPlan,
                keep: int = 220,
                channel_quotas: Optional[Dict[str, int]] = None,
                unique_channel_quotas: Optional[Dict[str, int]] = None) -> List[Candidate]:
        """RRF + 图先验 + 词法覆盖 + 通道多样性的线性融合。

        通道多样性项（被几个独立通道命中）是一个很强的弱监督信号：
        一篇论文同时被词法、语义、引文三条通道捞到，几乎不可能是噪声。
        它也正是捕获–再捕获估计的物理量，两处复用同一个信号。
        """
        if not cands:
            return []
        qtok = set(tokenize(plan.raw_query))
        spans = plan.quoted_spans or []
        for c in cands:
            ptok = set(tokenize(c.paper.text()))
            cov = len(qtok & ptok) / max(1, len(qtok))
            # 引用片段与标题的整体相似度。定位型查询里这一项常常就是答案本身，
            # 而把它拆成词袋会让它淹没在同领域的近邻噪声里。
            c.s_title = max((title_similarity(s, c.paper.title) for s in spans),
                            default=0.0)
            graph_match = match_paper(plan.constraint_graph, c.paper)
            c.s_constraint = graph_match.score
            c.s_lexical = cov
            n_ch = len({ch.split(":", 1)[0] for ch in c.channels})
            diversity = 1.0 - math.exp(-0.8 * n_ch)
            best_rank = min(c.channel_ranks.values()) if c.channel_ranks else 50
            pos = 1.0 / (1.0 + 0.08 * best_rank)
            base_l1 = (0.29 * _norm_rrf(c.s_rrf)
                       + 0.19 * c.s_graph
                       + 0.16 * cov
                       + 0.12 * diversity
                       + 0.08 * pos
                       + 0.11 * c.s_title
                       + 0.05 * c.s_constraint)
            # Native dense score is an opt-in ablation.  The frozen baseline
            # remains byte-for-byte compatible when the weight is zero, while
            # repaired train rollouts can test whether cosine quality helps
            # L1 admission rather than only the later fusion model.
            dense_weight = min(1.0, max(0.0, float(self.cfg.get("l1_dense_weight", 0.0) or 0.0)))
            dense_score = min(1.0, max(0.0, float(c.s_dense)))
            c.s_l1 = ((1.0 - dense_weight) * base_l1
                      + dense_weight * dense_score)
            c.judged_level = max(c.judged_level, 1)
            c.sigma = SIGMA_BY_LEVEL[1]
        ranked_all = sorted(cands, key=lambda c: (-c.s_l1, c.pid))
        ranked = self._preserve_channel_quotas(
            ranked_all, keep=keep, quotas=channel_quotas or {},
            unique_quotas=unique_channel_quotas or {})
        self.stats.l1_kept = len(ranked)
        return ranked

    @staticmethod
    def _preserve_channel_quotas(ranked: Sequence[Candidate], keep: int,
                                 quotas: Dict[str, int],
                                 unique_quotas: Optional[Dict[str, int]] = None,
                                 protected: Optional[Sequence[Candidate]] = None) -> List[Candidate]:
        """在全局 L1 截断前保留独立通道的候选。

        RRF 的“多通道一致性加分”不应变成“单通道发现即淘汰”：PaSa 的细粒度
        问题里，答案常仅通过 title、dense 或 section-reference 通道第一次出现。
        ``quotas`` 先从每个显式配置通道取其 L1 高分前 N 篇；
        ``unique_quotas`` 更严格，只保护*仅由该通道首次发现*的候选，并按该通道
        原始检索 rank 取前 N 篇。这让 dense / citation 的独有发现不会被多个高度
        相关的 lexical view 在 RRF 中投票淘汰。二者都只控制 membership：返回值仍
        按 L1 分数排序，配额不会变成伪相关性加分。

        ``protected`` 是一个已经由独立、冻结且 label-blind 的 admission scorer
        选出的候选列表。它也只控制 membership；插入在显式 channel quota 之前，
        所以调用方可以把其数量限制为 L1 预算的非配额余量，同时不破坏已有的
        lexical/citation 覆盖承诺。
        """
        n_keep = max(0, int(keep))
        if n_keep == 0 or not ranked:
            return []
        clean = {str(ch): max(0, int(n)) for ch, n in (quotas or {}).items()
                 if int(n) > 0}
        unique_clean = {str(ch): max(0, int(n))
                        for ch, n in (unique_quotas or {}).items()
                        if int(n) > 0}
        protected = list(protected or [])
        if not clean and not unique_clean and not protected:
            return list(ranked[:n_keep])

        selected: List[Candidate] = []
        used = set()
        ranked_pids = {cand.pid for cand in ranked}
        for cand in protected:
            if len(selected) >= n_keep:
                break
            if cand.pid not in ranked_pids or cand.pid in used:
                continue
            selected.append(cand)
            used.add(cand.pid)
        # Exact-one-channel membership is intentional.  A candidate already
        # found by another source is not an independent discovery and should
        # compete through the normal fusion path instead of consuming this
        # scarce protection budget.
        for channel, quota in unique_clean.items():
            unique = [cand for cand in ranked
                      if cand.channels == {channel} and cand.pid not in used]
            unique.sort(key=lambda cand: (
                cand.channel_ranks.get(channel, 10 ** 9), -cand.s_l1, cand.pid))
            for cand in unique[:quota]:
                if len(selected) >= n_keep:
                    break
                selected.append(cand)
                used.add(cand.pid)
            if len(selected) >= n_keep:
                break

        for channel, quota in clean.items():
            taken = 0
            for cand in ranked:
                if cand.pid in used or channel not in cand.channels:
                    continue
                selected.append(cand)
                used.add(cand.pid)
                taken += 1
                if taken >= quota or len(selected) >= n_keep:
                    break
            if len(selected) >= n_keep:
                break

        for cand in ranked:
            if len(selected) >= n_keep:
                break
            if cand.pid not in used:
                selected.append(cand)
                used.add(cand.pid)
        # 输出仍按 L1 分排序；配额只控制存活，不改变下游候选的顺序语义。
        return sorted(selected, key=lambda c: (-c.s_l1, c.pid))

    # ================================================================== #
    # L2：cross-encoder 精排（本地推理，零 token）
    # ================================================================== #
    def l2_rerank(self, cands: Sequence[Candidate], plan: QueryPlan,
                  keep: int = 80,
                  protected: Optional[Sequence[Candidate]] = None) -> List[Candidate]:
        """把查询与论文送进 cross-encoder 打分。

        这里喂给 reranker 的查询是**原始查询 + anchor 约束**，不是全部约束串联。
        原因同检索：全约束串会稀释 cross-encoder 的注意力，反而降低判别力。
        """
        if not cands:
            return []
        q = plan.raw_query
        query_mode = str(self.cfg.get("l2_query_mode", "raw_plus_anchor") or "raw_plus_anchor").lower()
        if query_mode not in ("raw", "raw_plus_anchor"):
            raise ValueError(f"unsupported l2_query_mode: {query_mode}")
        anchors = [c.text for c in plan.constraints
                   if c.role == ConstraintRole.ANCHOR]
        if query_mode == "raw_plus_anchor" and anchors:
            q = f"{plan.raw_query} [{'; '.join(anchors[:2])}]"
        items = [RerankItem(pid=c.pid, title=c.paper.title,
                            abstract=c.paper.abstract, venue=c.paper.venue,
                            year=c.paper.year) for c in cands]
        scores = self.reranker.score(q, items)
        sigma = getattr(self.reranker, "sigma", SIGMA_BY_LEVEL[2])
        for c, s in zip(cands, scores):
            c.s_l2 = float(s)
            c.judged_level = max(c.judged_level, 2)
            c.sigma = sigma
        self.stats.l2_scored = len(cands)

        # Optional candidate-internal blend for the widened L2 profile.  A
        # larger L2 input can otherwise let a low-L1 lexical match displace a
        # strong multi-channel candidate in the top-100.  The switch is
        # deliberately opt-in: the frozen baseline keeps the original L2
        # semantics, while train-only experiments can compare a bounded,
        # auditable score blend without changing candidate membership.
        l1_weight = float(self.cfg.get("l2_rank_blend_l1_weight", 0.0) or 0.0)
        l1_weight = min(1.0, max(0.0, l1_weight))
        if l1_weight > 0.0 and len(cands) > 1:
            base = np.asarray([float(candidate.s_l2 if candidate.s_l2 is not None else 0.0)
                               for candidate in cands], dtype=np.float64)
            l1 = np.asarray([float(candidate.s_l1) for candidate in cands], dtype=np.float64)
            # Normalize per admitted pool so the knob remains comparable when
            # a reranker changes score calibration (the train-only scan uses
            # this same min-max transform).
            base_span, l1_span = float(base.max() - base.min()), float(l1.max() - l1.min())
            base = (base - base.min()) / base_span if base_span > 1e-12 else np.zeros_like(base)
            l1 = (l1 - l1.min()) / l1_span if l1_span > 1e-12 else np.zeros_like(l1)
            blended = (1.0 - l1_weight) * base + l1_weight * l1
            for candidate, score in zip(cands, blended):
                candidate.s_l2 = float(score)
        ranked = sorted(cands, key=lambda c: (-(c.s_l2 or 0.0), c.pid))
        # This is an explicit membership sidecar, not a score boost: a
        # candidate independently selected by a frozen, label-blind admission
        # model may occupy a bounded L2 slot, but remains ordered according to
        # the ordinary L2 score after all candidates have been scored.  It is
        # needed when a semantic discovery is intentionally retained at L1 but
        # then loses the separate L2 truncation solely because lexical L2 has
        # no way to express the semantic discovery signal.
        protected_ids = {candidate.pid for candidate in (protected or [])}
        if not protected_ids:
            return ranked[:keep]
        selected: List[Candidate] = []
        used = set()
        for candidate in cands:
            if candidate.pid in protected_ids and candidate.pid not in used:
                selected.append(candidate)
                used.add(candidate.pid)
                if len(selected) >= keep:
                    break
        for candidate in ranked:
            if len(selected) >= keep:
                break
            if candidate.pid not in used:
                selected.append(candidate)
                used.add(candidate.pid)
        return sorted(selected, key=lambda c: (-(c.s_l2 or 0.0), c.pid))

    # ================================================================== #
    # L3：大模型约束核验（计费，只花在不确定带）
    # ================================================================== #
    def l3_verify(self, cands: Sequence[Candidate], plan: QueryPlan,
                  order: Sequence[int], batch_size: int = 6,
                  max_calls: Optional[int] = None) -> None:
        """按 VoI 顺序对候选做逐条约束核验。就地写回 s_l3 / checks / rationale。

        `order` 是 VoI 排好序的下标序列，由 pipeline 传入 —— 判定器不该自己
        决定预算优先级，那是 F1-Gate 门限的职责。
        """
        if self.llm is None or not cands or not order:
            return
        verify_cons = plan.verify_constraints() or plan.constraints
        cons_text = render_constraints(verify_cons)
        for i in range(0, len(order), batch_size):
            if self.ledger and self.ledger.exhausted():
                if self.ledger:
                    self.ledger.note("l3_verify", "预算耗尽，L3 提前停止")
                break
            if max_calls is not None and self.stats.l3_calls >= max_calls:
                break
            idxs = list(order[i:i + batch_size])
            batch = [cands[j] for j in idxs]
            try:
                data = self.llm.chat_json(
                    JUDGE_SYSTEM,
                    JUDGE_USER.format(query=plan.raw_query,
                                      query_type=plan.query_type.zh,
                                      constraints=cons_text,
                                      papers=render_papers(batch)),
                    stage="l3_verify", default={"results": []})
            except BudgetExhausted:
                break
            except Exception:                                    # noqa: BLE001
                continue
            self.stats.l3_calls += 1
            self._absorb_l3(batch, verify_cons, data)

    # ------------------------------------------------------------------ #
    def _absorb_l3(self, batch: Sequence[Candidate],
                   verify_cons: Sequence[Constraint], data: Dict) -> None:
        results = {int(r.get("id", -1)): r for r in (data.get("results") or [])
                   if isinstance(r, dict)}
        for k, cand in enumerate(batch, 1):
            r = results.get(k)
            if not r:
                continue
            checks: List[ConstraintCheck] = []
            for ch in (r.get("checks") or []):
                try:
                    cid = int(ch.get("cid", 0))
                except Exception:                                # noqa: BLE001
                    continue
                if not (1 <= cid <= len(verify_cons)):
                    continue
                status = str(ch.get("status", "unknown")).lower()
                if status not in ("yes", "partial", "no", "unknown"):
                    status = "unknown"
                evidence = str(ch.get("evidence", "") or "").strip()
                # ---- 证据对齐强校验 ----
                if status in ("yes", "partial"):
                    if not evidence or not self._verify_evidence(evidence, cand):
                        status = "unknown"
                        evidence = ""
                        self.stats.evidence_rejected += 1
                checks.append(ConstraintCheck(
                    constraint_text=verify_cons[cid - 1].text,
                    status=status, evidence=evidence[:180]))
            cand.checks = checks
            cand.rationale = str(r.get("rationale", ""))[:200]
            try:
                rel = float(r.get("relevance", 0.5))
            except Exception:                                    # noqa: BLE001
                rel = 0.5
            rel = min(max(rel, 0.0), 1.0)
            # 证据被拒得越多，越不能信任模型自报的 relevance
            if checks:
                unknown_ratio = sum(1 for c in checks if c.status == "unknown") / len(checks)
                rel *= (1.0 - 0.35 * unknown_ratio)
            cand.s_l3 = rel
            cand.judged_level = 3
            cand.sigma = SIGMA_BY_LEVEL[3]
            self.stats.l3_judged += 1

    @staticmethod
    def _verify_evidence(evidence: str, cand: Candidate) -> bool:
        """证据必须能在论文原文里找到踪迹，否则视为幻觉。

        不用精确子串匹配（模型常做轻微改写、大小写与标点归一化会失败），
        而是用词级覆盖率：证据里的实词至少 60% 出现在标题+摘要中。
        阈值取 0.6 是在「拦住幻觉」与「容忍合理改写」之间的折中。
        """
        ev = set(tokenize(evidence))
        if not ev:
            return False
        doc = set(tokenize(cand.paper.text()))
        if not doc:
            return False
        return len(ev & doc) / len(ev) >= 0.6

    # ================================================================== #
    # 融合：把各层分数合成单一相关度
    # ================================================================== #
    @staticmethod
    def fuse_scores(cands: Sequence[Candidate]) -> np.ndarray:
        """层级越高权重越大，未走到的层级不参与。

        L3 存在时它主导（0.62），但仍保留 L2 的一部分权重 —— 大模型偶尔会
        对某篇论文产生系统性误判，保留 cross-encoder 的意见能起到集成平滑作用。
        L3 缺失时由 L2 主导，L2 也缺失时退回 L1。这保证任何降级路径下
        分数都是**有序且可校准**的，F1-Gate 因此始终可用。
        """
        out = np.zeros(len(cands), dtype=np.float64)
        for i, c in enumerate(cands):
            if c.s_l3 is not None and c.s_l2 is not None:
                s = 0.62 * c.s_l3 + 0.23 * c.s_l2 + 0.15 * c.s_l1
                if c.checks:
                    s = 0.85 * s + 0.15 * c.constraint_satisfaction()
            elif c.s_l3 is not None:
                s = 0.75 * c.s_l3 + 0.25 * c.s_l1
            elif c.s_l2 is not None:
                s = 0.70 * c.s_l2 + 0.30 * c.s_l1
            else:
                s = c.s_l1
            out[i] = min(max(s, 0.0), 1.0)
        return out


def _norm_rrf(x: float) -> float:
    """RRF 分数量级很小（~1/60 起），压缩到 [0,1] 便于线性融合。"""
    return 1.0 - math.exp(-40.0 * max(x, 0.0))
