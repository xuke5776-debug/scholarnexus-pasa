"""ScholarNexus 端到端流水线。

    ① QueryLens      约束图解析 + 类型路由 → QueryPlan
    ② MultiProbe     多通道并行召回 + 引文双向扩散 + 跨源消歧
    ③ CascadeJudge   L0 过滤 → L1 融合粗排 → L2 精排（零 token）
    ④ Calibrator     混合模型自校准 → 可比较的相关概率 p
    ⑤ CoverageMeter  Chao1 估 N̂ 与覆盖率 → 停止？否则演化检索式回到 ②
    ⑥ F1-Gate        不动点求解 p* = F1*/2 → VoI 分配 L3 预算 → 最终集合
    ⑦ InsightBoard   约束满足矩阵 + 意图自适应视图 + 执行账本

第 ⑥ 步在循环内外各生效一次，这不是冗余：循环内的门限用来**指导花钱**
（决定 L3 判谁），循环外的门限用来**决定输出**。同一个不动点，两处用途。
"""
from __future__ import annotations

import hashlib
import json
import copy
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

import numpy as np

from ..config import Config
from ..ledger import Ledger
from ..llm import BudgetExhausted, build_llm
from ..llm.prompts import EXPAND_SYSTEM, EXPAND_USER, render_titles
from ..rank.rerank import RerankItem, build_reranker
from ..retrieval.multiprobe import MultiProbe, ProbeResult
from ..schema import (Budget, Candidate, ConstraintRole, QueryPlan, QueryType,
                      SearchResult)
from ..sources.base import build_registry
from ..sources.cache import DiskCache
from . import coverage as cov_mod
from .agentic import AgenticController
from .pasa_adaptation import (CardinalityPredictor, L2FusionModel, PROFILE_SPECS,
                              ProfilePolicy, query_state_features)
from . import f1gate
from .calibrate import (MixtureCalibrator, RankDecayCalibrator,
                        independent_mass_anchor, propensity, tail_temper)
from .fusion import adaptive_fuse, collect_signals, type_prior
from .judge import CascadeJudge
from .querylens import TYPE_POLICY, QueryLens
from .supervised import FeatureCalibrator


class ScholarNexus:
    def __init__(self, config: Optional[Config] = None, registry=None,
                 cache=None, current_year: int = 2026):
        self.cfg = (config or Config.load()).resolved()
        self.current_year = current_year
        self._cache = cache if cache is not None else self._build_cache()
        self._registry_override = registry
        # Source construction can be expensive (the full MiniLM metadata is
        # hundreds of thousands of rows).  Keep one registry per engine and
        # rebind its ledger for each query instead of rebuilding every time.
        self._persistent_registry = registry
        self._registry_retry_used = False
        self._last_channel_hits: Dict[str, Any] = {}
        # Reusing a local embedding reranker avoids one model load per query
        # in a benchmark process.  The object never caches candidates or
        # labels; it only holds frozen local model weights.
        self._persistent_reranker = None
        # Anchor scoring is deliberately a separate concern from final L2
        # relevance.  It may use a frozen local selector to choose useful
        # citation seeds while final ranking remains lexical.
        self._persistent_anchor_reranker = None
        # Admission, citation anchoring, and final relevance are distinct
        # tasks.  Keep a dedicated local scorer lifecycle for admission so an
        # experiment cannot silently turn into a final-rerank ablation.
        self._persistent_dense_admission_reranker = None
        # Immutable, label-blind Selector scores may be generated in a
        # separate process on small Windows GPUs.  Cache only parsed score
        # artifacts, keyed by their explicit file path; never cache labels or
        # candidate decisions.
        self._precomputed_dense_admission_scores: Dict[str, Dict[str, Dict[str, float]]] = {}
        self.last_anchor = 0.0
        self.last_alpha = 1.0
        self._supervised = self._load_supervised()

    def _load_supervised(self):
        path = str(self.cfg.pipeline.get("supervised_calibrator_path", "") or "")
        try:
            model = FeatureCalibrator.load(path)
            if model is not None:
                model.blend = float(self.cfg.pipeline.get("supervised_blend", model.blend))
            return model
        except Exception:
            return None

    def _build_cache(self):
        try:
            return DiskCache(self.cfg.cache_path, self.cfg.cache_ttl_days)
        except Exception:                                        # noqa: BLE001
            return None

    def _registry_for(self, ledger):
        """Return the engine registry while attaching the current ledger."""
        if self._persistent_registry is None:
            self._persistent_registry = build_registry(
                self.cfg.sources, self._cache, ledger)
        else:
            for source in self._persistent_registry.all():
                source.ledger = ledger
        return self._persistent_registry

    @staticmethod
    def _close_registry(registry) -> None:
        if registry is None:
            return
        for source in registry.all():
            close = getattr(source, "close", None)
            if callable(close):
                close()

    def _retry_registry(self, ledger):
        """Retry one failed optional-source construction after releasing state."""
        if self._registry_override is not None or self._registry_retry_used:
            return self._persistent_registry
        self._registry_retry_used = True
        self._close_registry(self._persistent_registry)
        self._persistent_registry = None
        return self._registry_for(ledger)

    def _l2_requires_gpu(self) -> bool:
        """Whether the configured final reranker needs the dense GPU released."""
        cfg = self.cfg.reranker if isinstance(self.cfg.reranker, dict) else {}
        backend = str(cfg.get("backend", "lexical") or "lexical").lower()
        device = str(cfg.get("device", "cuda") or "cuda").lower()
        return (device.startswith("cuda") and backend in {
            "local", "local_embedding", "local_embed", "sentence_embedding",
            "pasa_bge_selector_head", "bge_selector_head"})

    # ================================================================== #
    def search(self, query: str, budget: Optional[Budget] = None,
               on_event=None) -> SearchResult:
        """执行一次完整检索。`on_event(stage, payload)` 用于 SSE 流式推送。"""
        pcfg = self.cfg.pipeline
        ledger = Ledger(budget or Budget())
        trace: List[Dict[str, Any]] = []
        # This switch is strictly observational.  Its records are constructed
        # from the candidate pool and current scores only; benchmark labels are
        # not available inside ScholarNexus and no audit record is fed back into
        # retrieval, ranking, calibration, or the final F1 gate.
        audit_enabled = bool(pcfg.get("candidate_audit", False))
        audit_stages: Dict[str, Set[str]] = {}
        # Membership alone cannot diagnose an L2 boundary change.  These
        # ordered, label-blind lists record exactly what L1/L2 received; they
        # are observational only and never feed back into the pipeline.
        audit_orders: Dict[str, List[str]] = {}
        audit_seeds: List[Dict[str, Any]] = []
        audit_admissions: List[Dict[str, Any]] = []
        # Optional fusion guard: preserve the pre-fusion L2 head membership
        # while still allowing the learned model to reorder that head.  It is
        # disabled by default and is only used by explicitly frozen trials.
        fusion_preserve_ids: Optional[Set[str]] = None
        fusion_base_l2_scores: Optional[Dict[str, float]] = None
        fusion_preserve_final_ids: Optional[Set[str]] = None

        def emit(stage: str, **payload):
            rec = {"stage": stage, "t": round(ledger.elapsed, 3), **payload}
            trace.append(rec)
            if on_event:
                try:
                    on_event(stage, rec)
                except Exception:                                # noqa: BLE001
                    pass

        for d in getattr(self.cfg, "degradations", []):
            ledger.note("config", f"{d['layer']} 降级到 {d['to']}：{d['reason']}")

        llm_fast = build_llm(self.cfg.llm_fast, ledger)
        llm_judge = build_llm(self.cfg.llm_judge, ledger)
        reranker = self._build_reranker(ledger)
        registry = self._registry_for(ledger)
        probe = MultiProbe(registry, ledger)
        judge = CascadeJudge(reranker, llm_judge, ledger, pcfg)
        # A dense encoder is not necessarily helped by keyword-like query
        # decomposition.  This optional, explicitly configured route probes
        # only the named dense sources with the original complete question;
        # lexical FTS remains on controlled QueryLens strings.  It is not a
        # silent default change, and its channel is tagged for later strict
        # candidate-flow attribution.
        raw_dense_cfg = pcfg.get("raw_query_dense_sources") or []
        if isinstance(raw_dense_cfg, str):
            raw_dense_sources = [raw_dense_cfg]
        elif isinstance(raw_dense_cfg, (list, tuple, set)):
            raw_dense_sources = [str(name).strip() for name in raw_dense_cfg
                                 if str(name).strip()]
        else:
            raise ValueError("pipeline.raw_query_dense_sources must be a source-name list")
        raw_dense_sources = list(dict.fromkeys(raw_dense_sources))
        if raw_dense_sources:
            registered_sources = {source.name for source in registry.all()}
            unavailable = sorted(set(raw_dense_sources) - registered_sources)
            if unavailable and not self._registry_retry_used:
                init_errors = getattr(registry, "initialization_errors", {})
                if any(name in init_errors for name in unavailable):
                    registry = self._retry_registry(ledger)
                    registered_sources = {source.name for source in registry.all()}
                    unavailable = sorted(set(raw_dense_sources) - registered_sources)
            if unavailable:
                init_errors = getattr(registry, "initialization_errors", {})
                details = "; ".join(
                    f"{name}={init_errors[name]}" for name in unavailable
                    if name in init_errors)
                raise ValueError(
                    "raw_query_dense_sources names are not registered: "
                    + ", ".join(unavailable)
                    + (f" (initialization errors: {details})" if details else ""))
        dense_admission_cfg = pcfg.get("dense_admission_selector") or {}
        if not isinstance(dense_admission_cfg, dict):
            raise ValueError("pipeline.dense_admission_selector must be an object")
        agentic_cfg = pcfg.get("agentic_controller") or {}
        if not isinstance(agentic_cfg, dict):
            raise ValueError("pipeline.agentic_controller must be an object")
        agentic = AgenticController(agentic_cfg)
        l2_fusion_path = str(pcfg.get("pasa_l2_fusion_path", "") or "").strip()
        cardinality_path = str(pcfg.get("pasa_cardinality_path", "") or "").strip()
        profile_policy_path = str(pcfg.get("pasa_profile_policy_path", "") or "").strip()
        l2_fusion = L2FusionModel(l2_fusion_path) if l2_fusion_path else None
        cardinality = CardinalityPredictor(cardinality_path) if cardinality_path else None
        profile_policy = ProfilePolicy(profile_policy_path) if profile_policy_path else None
        configured_profile = str(pcfg.get("pasa_profile_override", "") or "").strip().upper()
        if configured_profile and configured_profile not in PROFILE_SPECS:
            raise ValueError("pipeline.pasa_profile_override must be one of P0, P1, P2, P3")
        if configured_profile and profile_policy is not None:
            raise ValueError("pasa_profile_override and pasa_profile_policy_path are mutually exclusive")

        # ---------------- ① 查询理解 ----------------
        with ledger.stage("query_lens"):
            plan = QueryLens(llm_fast, ledger, self.current_year).parse(query)
        # 某些有独立开发集的基准会给出与通用产品查询完全不同的答案集合规模。
        # 允许在 *dev* 上确定一个显式先验锚点；test 运行只读取冻结配置，绝不
        # 从 test 标签反推。这样可避免通用 survey 先验把窄集合基准的 F1-Gate
        # 推向过大的输出集合。
        prior_override = float(pcfg.get("n_hat_prior_override", 0) or 0)
        if prior_override > 0:
            plan.n_hat_prior = prior_override
            plan.n_hat_prior_sd = min(float(plan.n_hat_prior_sd),
                                      float(pcfg.get("n_hat_prior_sd", prior_override)))
            ledger.note("query_lens", f"使用冻结的基准基数先验 N={prior_override:g}")
        if budget is None:
            ledger.budget = plan.budget          # 类型路由决定预算
        emit("query_lens", plan=plan.to_dict())

        pool = ProbeResult(candidates={})
        queries = list(plan.search_strings)
        est = None
        stop = None
        rounds = 0
        last_new = None
        gate = None
        gate_n_hat = None
        cands: List[Candidate] = []
        p = np.zeros(0)

        # ---------------- 迭代检索循环 ----------------
        max_rounds = min(plan.budget.max_rounds, ledger.budget.max_rounds,
                         int(pcfg.get("max_rounds", 2)))
        for rnd in range(max_rounds):
            rounds = rnd + 1
            before = len(pool.candidates)

            # On 4 GB GPUs, do not let the previous query's BGE admission
            # head coexist with the next query's exact full-corpus MiniLM
            # search matrix.  The release changes neither stored vectors nor
            # candidates; it only serialises two incompatible GPU workloads.
            if raw_dense_sources and dense_admission_cfg:
                self._release_dense_admission_reranker()

            with ledger.stage(f"probe_r{rounds}"):
                fresh = probe.probe(plan, queries,
                                    per_query_limit=int(pcfg.get("per_query_limit", 20)),
                                    round_idx=rnd,
                                    audit_provenance=audit_enabled,
                                    source_names=(None if not raw_dense_sources
                                                  else [source.name for source in registry.all()
                                                        if source.name not in raw_dense_sources]))
                # ---- 硬约束零召回回退 ----
                # 硬过滤是双刃剑：解析正确时零成本提精度，解析错误时**静默**滤掉
                # 全部正确答案且不报任何错。实测中 "Hierarchical" 被误判为 CHI 会议
                # 就导致过一次全量零召回。任何依赖 LLM 解析元数据约束的系统都会
                # 遇到这类错误，所以必须有架构级防御，而不是指望解析永不出错。
                if len(fresh.candidates) < self.MIN_RECALL and plan.hard_filters():
                    relaxed = self._relax_plan(plan)
                    ledger.note("probe", "硬过滤后召回过少，已放宽元数据约束重试")
                    fresh2 = probe.probe(relaxed, queries,
                                         per_query_limit=int(pcfg.get("per_query_limit", 20)),
                                         round_idx=rnd,
                                         audit_provenance=audit_enabled,
                                         source_names=(None if not raw_dense_sources
                                                       else [source.name for source in registry.all()
                                                             if source.name not in raw_dense_sources]))
                    if len(fresh2.candidates) > len(fresh.candidates):
                        fresh = fresh2
                        # 被放宽的约束降级为判定阶段核验，而不是直接丢弃
                        plan = relaxed
                        emit("relax", round=rounds,
                             recovered=len(fresh.candidates))
                dense_decision = None
                if raw_dense_sources:
                    # AgenticArXiv-RL's transferable idea is an explicit tool
                    # decision from observable state.  Preview scores are
                    # label-blind and are discarded; final L0/L1 is rerun
                    # below after all selected tools have merged.
                    if agentic.enabled:
                        probe.fuse(fresh, plan.channel_weights)
                        preview_alive = judge.l0_filter(
                            list(fresh.candidates.values()), plan)
                        judge.l1_rank(preview_alive, plan, len(preview_alive),
                                      pcfg.get("l1_channel_quotas") or {},
                                      pcfg.get("l1_unique_channel_quotas") or {})
                    dense_decision = agentic.choose_dense(
                        plan, list(fresh.candidates.values()), available=True)
                    emit("agent", round=rounds, action=dense_decision.action,
                         reason=dense_decision.reason,
                         features=dense_decision.features)
                if raw_dense_sources and dense_decision.action == "dense":
                    dense_limit = int(pcfg.get("raw_query_dense_limit", 0) or 0)
                    if dense_limit <= 0:
                        dense_limit = int(pcfg.get("per_query_limit", 20))
                    raw_question = str(plan.raw_query or query).strip()
                    dense_views = [("raw_question", raw_question)] if raw_question else []
                    if bool(pcfg.get("raw_query_dense_constraint_view", False)):
                        # A short positive-constraint view is an opt-in second
                        # representation.  Negative constraints stay out of
                        # retrieval and remain an L0/L2 verification concern.
                        anchors = [str(constraint.text).strip()
                                   for constraint in plan.constraints
                                   if getattr(constraint.role, "value", constraint.role) != "negative"
                                   and str(constraint.text).strip()]
                        constraint_query = " ".join(dict.fromkeys(anchors[:8]))
                        if constraint_query and constraint_query != raw_question:
                            dense_views.append(("constraint_view", constraint_query))
                    for view_tag, dense_query in dense_views:
                        raw_dense = probe.probe(
                            plan, [dense_query], per_query_limit=dense_limit,
                            round_idx=rnd, audit_provenance=audit_enabled,
                            source_names=raw_dense_sources,
                            channel_tag=view_tag)
                        fresh.merge(raw_dense)
                    emit("dense_views", round=rounds,
                         views=[tag for tag, value in dense_views if value],
                         views_run=sum(1 for _tag, value in dense_views if value))
                pool.merge(fresh)
            if audit_enabled:
                audit_stages[f"post_probe_r{rounds}"] = set(pool.candidates)
            emit("probe", round=rounds, queries=list(queries),
                 raw_dense_sources=list(raw_dense_sources),
                 dense_action=(dense_decision.action if dense_decision else "lexical_only"),
                 new=len(pool.candidates) - before, total=len(pool.candidates))

            if not pool.candidates:
                break

            # This is the common, label-blind lexical+dense observation from
            # which fixed profile arms and a promoted policy branch.  RRF is
            # computed before the decision so controller score-decay features
            # describe the observed pool rather than zero-initialised L1.
            probe.fuse(pool, plan.channel_weights)
            profile_spec = None
            if configured_profile:
                profile_spec = PROFILE_SPECS[configured_profile]
                emit("agent", round=rounds, action="profile",
                     reason="configured_profile_arm", profile=configured_profile,
                     predicted_rewards={}, features=query_state_features(
                         plan, list(pool.candidates.values())))
            elif profile_policy is not None:
                profile_decision = profile_policy.choose(plan, list(pool.candidates.values()))
                profile_spec = PROFILE_SPECS[profile_decision.profile]
                emit("agent", round=rounds, action="profile",
                     reason="train_validated_profile_policy",
                     profile=profile_decision.profile,
                     predicted_rewards=profile_decision.predicted_rewards,
                     features=profile_decision.state)

            base_l1_keep = int(profile_spec["l1_keep"] if profile_spec is not None
                               else pcfg.get("l1_keep", 220))
            if profile_spec is not None:
                # A profile arm is an experimental action, not a hint.  In
                # particular P0/P1 must stay at 700 and P2/P3 at 1000 even
                # when the generic controller would otherwise widen L1.
                agentic_l1_keep = base_l1_keep
                emit("agent", round=rounds, action="fixed_profile_admission",
                     reason="profile_l1_budget", features={
                         "profile": (configured_profile or profile_decision.profile),
                         "l1_keep": agentic_l1_keep})
            else:
                admission_decision = agentic.choose_admission(
                    plan, list(pool.candidates.values()), base_l1_keep)
                agentic_l1_keep = int(admission_decision.features.get(
                    "l1_keep", base_l1_keep))
                emit("agent", round=rounds, action=admission_decision.action,
                     reason=admission_decision.reason,
                     features=admission_decision.features)

            # ---- 引文扩散：先做零成本约束核验，再选种子 ----
            # 首轮尚无 L2/L3 分数时，不能直接拿 RRF 前几名做种子：宽泛词命中
            # 的高被引论文会把大量无关引文带入图，并在 PPR/共被引归一化后取得
            # 虚高图分。这里的 L1 只用于保护扩展动作；正式排序仍在后面的
            # L0→L1→L2 级联中重新完成。
            probe.fuse(pool, plan.channel_weights)
            seed_alive = judge.l0_filter(list(pool.candidates.values()), plan)
            seed_ranked = judge.l1_rank(seed_alive, plan,
                                        agentic_l1_keep,
                                        pcfg.get("l1_channel_quotas") or {},
                                        pcfg.get("l1_unique_channel_quotas") or {})
            seed_floor = float(pcfg.get("citation_seed_min_constraint", 0.42))
            seed_eligible = [c for c in seed_ranked if c.s_constraint >= seed_floor]
            seed_strategy = str(pcfg.get("citation_seed_rerank", "disabled") or "disabled").lower()
            if seed_strategy == "l2":
                # Final L2 answers “which paper itself satisfies the query?”;
                # citation anchor quality is a related but distinct question.
                # This optional probe tests the distinction without broadening
                # the graph: same L1-admitted candidates, same constraint gate,
                # same number of selected seeds.  The normal final L2 pass
                # below scores the full pool again, so these provisional scores
                # cannot leak into its candidate membership.
                # An empty eligible set is a valid outcome for a constrained
                # query.  It means “skip citation expansion”, not “l2 is an
                # unknown strategy”; the normal final ranking still proceeds.
                seed_ordered = (judge.l2_rerank(seed_eligible, plan, len(seed_eligible))
                                if seed_eligible else [])
                seed_scores = {c.pid: float(c.s_l2 if c.s_l2 is not None else c.s_l1)
                               for c in seed_ordered}
            elif seed_strategy in ("anchor", "anchor_selector"):
                # Anchor relevance is not final relevance.  This path uses a
                # separately configured, frozen scorer only to choose the
                # four papers whose section citations may enter the pool; it
                # does not write ``s_l2`` and therefore cannot silently alter
                # final scoring semantics.
                anchor_cfg = pcfg.get("citation_anchor_reranker") or {}
                if not isinstance(anchor_cfg, dict) or not anchor_cfg.get("backend"):
                    raise ValueError(
                        "citation_seed_rerank='anchor' requires pipeline.citation_anchor_reranker")
                cap = int(pcfg.get("citation_anchor_input_keep", 0) or 0)
                anchor_input = (seed_eligible if cap <= 0 else seed_eligible[:max(0, cap)])
                if anchor_input:
                    anchor_reranker = self._build_anchor_reranker(anchor_cfg, ledger)
                    anchor_items = [RerankItem(
                        pid=c.pid, title=c.paper.title, abstract=c.paper.abstract,
                        venue=c.paper.venue, year=c.paper.year) for c in anchor_input]
                    raw_scores = anchor_reranker.score(plan.raw_query, anchor_items)
                    if len(raw_scores) != len(anchor_input):
                        raise RuntimeError("citation anchor scorer returned an incorrect score count")
                    seed_scores = {cand.pid: float(score)
                                   for cand, score in zip(anchor_input, raw_scores)}
                    seed_ordered = sorted(anchor_input,
                                          key=lambda cand: (-seed_scores[cand.pid], cand.pid))
                else:
                    seed_scores = {}
                    seed_ordered = []
                seed_strategy = "anchor"
            elif seed_strategy in ("disabled", "none", "l1"):
                seed_strategy = "l1"
                seed_ordered = seed_eligible
                seed_scores = {c.pid: float(c.s_l1) for c in seed_ordered}
            else:
                raise ValueError(f"unknown citation_seed_rerank strategy: {seed_strategy}")
            seeds = {
                c.pid: float(seed_scores[c.pid])
                for c in seed_ordered
            }
            seeds = dict(sorted(seeds.items(), key=lambda x: (-x[1], x[0]))[
                :int(pcfg.get("citation_expand_seeds", 6))])
            seed_candidates = [cand for cand in seed_ordered if cand.pid in seeds]
            if audit_enabled:
                audit_seeds.extend({
                    "round": rounds,
                    "pid": cand.pid,
                    "title": cand.paper.title,
                    "selection_strategy": seed_strategy,
                    "selection_score": round(float(seed_scores[cand.pid]), 8),
                    "l1_score": round(float(cand.s_l1), 8),
                    "constraint_score": round(float(cand.s_constraint), 8),
                    "channels": sorted(cand.channels),
                    "channel_ranks": dict(sorted(cand.channel_ranks.items())),
                } for cand in seed_ordered if cand.pid in seeds)
            if profile_spec is not None and not bool(profile_spec["citation_enabled"]):
                citation_action = "skip_citation"
                citation_reason = "profile_P0_citation_disabled"
                citation_features = {"profile": "P0", "seed_count": len(seed_candidates)}
            else:
                citation_decision = agentic.choose_citation(
                    plan, list(pool.candidates.values()), seed_candidates)
                citation_action = citation_decision.action
                citation_reason = citation_decision.reason
                citation_features = citation_decision.features
            emit("agent", round=rounds, action=citation_action,
                 reason=citation_reason, features=citation_features)
            if seeds and citation_action == "citation":
                with ledger.stage(f"cite_expand_r{rounds}"):
                    probe.expand_citations(
                        pool, seeds,
                        limit_per_seed=int(pcfg.get("citation_expand_limit", 40)),
                        max_seeds=int(pcfg.get("citation_expand_seeds", 6)),
                        round_idx=rnd,
                        query=plan.raw_query,
                        section_max_sections=int(
                            pcfg.get("citation_section_max_sections", 0)),
                        audit_provenance=audit_enabled)
                # Seed admission stays deliberately strict: a weak lexical
                # match must never fan out into a giant irrelevant graph.
                # Once a seed has passed that test, its direct archived
                # references can use a lower *candidate* floor, because their
                # abstracts are checked again by L1/L2.  This is important for
                # related-work queries whose target title omits the exact
                # anchor phrase (for example a named compressed model).
                graph_floor = float(pcfg.get("citation_graph_min_constraint", seed_floor))
                n_graph = probe.apply_graph_signal(pool, seeds,
                    min_constraint=graph_floor)
                emit("cite_expand", round=rounds, seeds=len(seeds),
                     seed_strategy=seed_strategy,
                     graph=pool.graph.stats(), graph_hits=n_graph,
                     total=len(pool.candidates))
            else:
                ledger.note("cite_expand", (
                    "agent 跳过引文工具" if citation_action == "skip_citation"
                    else "没有通过约束一致性门槛的种子，跳过图扩展"))

            if audit_enabled:
                audit_stages[f"post_citation_r{rounds}"] = set(pool.candidates)

            probe.fuse(pool, plan.channel_weights)

            # ---- ③ 判定级联 L0→L1→L2 ----
            with ledger.stage(f"judge_r{rounds}"):
                alive = judge.l0_filter(list(pool.candidates.values()), plan)
                l1_keep = agentic_l1_keep
                protected: List[Candidate] = []
                preserve_selector_into_l2 = bool(
                    dense_admission_cfg.get("preserve_into_l2", False))
                if dense_admission_cfg:
                    # The raw dense probe is complete for this round.  Drop
                    # only its GPU runtime (not its memmap index) before the
                    # larger frozen BGE head is materialised for admission.
                    self._release_raw_dense_accelerators(registry, raw_dense_sources)
                    # Compute the historical L1 score across the whole pool
                    # first.  The frozen Selector below affects membership
                    # only: it never changes s_l1, s_l2, calibration, or the
                    # final ranking semantics.
                    ranked_all = judge.l1_rank(alive, plan, len(alive))
                    protected, admission_event = self._selector_gated_dense_candidates(
                        ranked_all, plan, dense_admission_cfg, ledger)
                    ranked = judge._preserve_channel_quotas(
                        ranked_all, l1_keep,
                        pcfg.get("l1_channel_quotas") or {},
                        pcfg.get("l1_unique_channel_quotas") or {},
                        protected=protected)
                    judge.stats.l1_kept = len(ranked)
                    if audit_enabled:
                        admission_event["preserve_into_l2"] = preserve_selector_into_l2
                        audit_admissions.append(admission_event)
                    emit("dense_admission", round=rounds,
                          protected=len(protected),
                          eligible=admission_event["eligible_count"],
                         scored=admission_event["scored_count"],
                         preserve_into_l2=preserve_selector_into_l2)
                else:
                    ranked = judge.l1_rank(
                        alive, plan, l1_keep,
                        pcfg.get("l1_channel_quotas") or {},
                        pcfg.get("l1_unique_channel_quotas") or {})
                # L1 is the candidate-admission stage and may intentionally
                # inspect a wide pool.  Some local rerankers (notably the
                # zero-dependency lexical fallback) are quadratic-ish in the
                # number of candidate tokens, so L2 must have its own *input*
                # budget.  This preserves broad L1 admission while making the
                # actual fine-ranking budget explicit and reproducible.
                l2_input_keep = int(profile_spec["l2_input_keep"] if profile_spec is not None
                                    else pcfg.get("l2_input_keep", 0) or 0)
                l2_input = (ranked if l2_input_keep <= 0 else
                             judge._preserve_channel_quotas(
                                 ranked, max(0, l2_input_keep),
                                 pcfg.get("l2_channel_quotas") or {},
                                 pcfg.get("l2_unique_channel_quotas") or {},
                                 protected=(protected if preserve_selector_into_l2 else None)))
                l2_keep = int(profile_spec["l2_keep"] if profile_spec is not None
                              else pcfg.get("l2_keep", 80))
                # Raw-question dense retrieval can materialize the complete
                # MiniLM index on a small GPU.  It is no longer needed once
                # L2 input membership has been frozen, so release only that
                # source's accelerator state before materializing BGE.  This
                # does not alter the candidates or their L1 scores; it merely
                # prevents two incompatible model footprints from coexisting.
                if raw_dense_sources and (dense_admission_cfg or self._l2_requires_gpu()):
                    self._release_raw_dense_accelerators(registry, raw_dense_sources)
                cands = judge.l2_rerank(
                    l2_input, plan, l2_keep,
                    protected=(protected if preserve_selector_into_l2 else None))
                if l2_fusion is not None and cands:
                    fusion_base_l2_scores = {
                        cand.pid: float(cand.s_l2 or 0.0) for cand in cands
                    }
                    preserve_top_k = 0
                    try:
                        preserve_top_k = int(pcfg.get("pasa_l2_fusion_preserve_top_k", 0) or 0)
                    except (TypeError, ValueError):
                        preserve_top_k = 0
                    # Capture the ordinary L2 membership before the learned
                    # reorder changes scores.  The final output stage may use
                    # this set to keep a declared top-k boundary stable.
                    if preserve_top_k > 0:
                        preserve_top_k = min(preserve_top_k, len(cands))
                        fusion_preserve_ids = {cand.pid for cand in cands[:preserve_top_k]}
                    else:
                        fusion_preserve_ids = None
                    try:
                        fusion_weight = float(pcfg.get("pasa_l2_fusion_weight", 1.0) or 0.0)
                    except (TypeError, ValueError):
                        fusion_weight = 1.0
                    fusion_mode = str(pcfg.get("pasa_l2_fusion_blend_mode", "linear") or "linear")
                    try:
                        fusion_head_keep = int(pcfg.get("pasa_l2_fusion_head_keep", 0) or 0)
                    except (TypeError, ValueError):
                        fusion_head_keep = 0
                    fusion_head_keep = max(0, min(fusion_head_keep, len(cands)))
                    if 0 < fusion_head_keep < len(cands):
                        # Restrict the learned reorder to a bounded head and
                        # preserve the ordinary L2 tail exactly.
                        head = l2_fusion.rerank(
                            plan, cands[:fusion_head_keep], blend_weight=fusion_weight,
                            blend_mode=fusion_mode)
                        cands = [*head, *cands[fusion_head_keep:]]
                    else:
                        cands = l2_fusion.rerank(plan, cands, blend_weight=fusion_weight,
                                                 blend_mode=fusion_mode)
                    emit("l2_fusion", round=rounds, candidates=len(cands),
                         kind="pasa_l2_fusion_v1", blend_weight=round(fusion_weight, 6),
                         blend_mode=fusion_mode, head_keep=fusion_head_keep,
                         preserve_top_k=preserve_top_k)
                elif l2_fusion is None:
                    fusion_preserve_ids = None
                    fusion_base_l2_scores = None
                    fusion_preserve_final_ids = None
            if audit_enabled:
                # These are membership sets, not label-derived "good/bad"
                # judgments.  Persisting them lets the offline evaluator name
                # the exact truncation that lost a gold paper after the fact.
                audit_stages["l0_final"] = {cand.pid for cand in alive}
                audit_stages["l1_final"] = {cand.pid for cand in ranked}
                audit_stages["l2_input_final"] = {cand.pid for cand in l2_input}
                audit_stages["l2_final"] = {cand.pid for cand in cands}
                audit_orders["l0_final"] = [cand.pid for cand in alive]
                audit_orders["l1_final"] = [cand.pid for cand in ranked]
                audit_orders["l2_input_final"] = [cand.pid for cand in l2_input]
                audit_orders["l2_final"] = [cand.pid for cand in cands]
            emit("judge", round=rounds, l0_dropped=judge.stats.l0_dropped,
                 l1_kept=judge.stats.l1_kept, l2_input=len(l2_input),
                 l2_scored=judge.stats.l2_scored)

            if not cands:
                break

            # ---- ④⑤⑥ 校准 → 基数估计 → 门限 → VoI 花钱 ----
            self._last_channel_hits = pool.channel_hits
            preserve_final_top_k = 0
            try:
                preserve_final_top_k = int(
                    pcfg.get("pasa_l2_fusion_preserve_final_top_k", 0) or 0)
            except (TypeError, ValueError):
                preserve_final_top_k = 0
            if (l2_fusion is not None and fusion_base_l2_scores
                    and preserve_final_top_k > 0):
                # Recompute the ordinary pre-fusion calibrated order on
                # shallow candidate copies.  This is label-blind and gives
                # the guard the same top-k boundary that P2 would have used,
                # rather than assuming raw L2 order equals final order.
                baseline_candidates = [copy.copy(candidate) for candidate in cands]
                for candidate in baseline_candidates:
                    candidate.s_l2 = fusion_base_l2_scores.get(
                        candidate.pid, float(candidate.s_l2 or 0.0))
                baseline_p = self._calibrate(baseline_candidates, judge, plan)
                baseline_p_gold = self._p_gold(baseline_candidates, baseline_p, plan)
                baseline_order = np.argsort(-baseline_p_gold)
                keep = min(preserve_final_top_k, len(baseline_order))
                fusion_preserve_final_ids = {
                    baseline_candidates[int(index)].pid
                    for index in baseline_order[:keep]
                }
            else:
                fusion_preserve_final_ids = None
            p = self._calibrate(cands, judge, plan)
            p = self._apply_final_rank_l2_blend(cands, p)
            est = self._estimate_coverage(pool, cands, p, plan)
            gate_n_hat = cardinality.predict(plan, cands) if cardinality is not None else None
            if gate_n_hat is not None:
                emit("cardinality", round=rounds, n_hat=round(gate_n_hat, 4),
                     kind="pasa_cardinality_predictor_v1")
            gate = f1gate.optimal_cutoff(
                self._p_gold(cands, p, plan),
                n_samples=None if gate_n_hat is not None else est.samples,
                n_hat=gate_n_hat,
                core_ratio=float(pcfg.get("core_ratio", 1.25)),
                band_width=float(pcfg.get("band_width", 0.15)))
            emit("estimate", round=rounds, n_hat=round(est.n_hat, 2),
                 coverage=round(est.coverage, 4), discovered=round(est.discovered, 2),
                 threshold=round(gate.threshold, 4),
                 expected_f1=round(gate.expected_f1, 4), k=gate.k)

            with ledger.stage(f"l3_r{rounds}"):
                n_l3 = self._spend_l3(judge, cands, p, gate, plan, pcfg)
            if n_l3:
                p = self._calibrate(cands, judge, plan)
                p = self._apply_final_rank_l2_blend(cands, p)
                est = self._estimate_coverage(pool, cands, p, plan)
                gate_n_hat = cardinality.predict(plan, cands) if cardinality is not None else None
                emit("l3", round=rounds, judged=n_l3,
                     llm_calls=judge.stats.l3_calls,
                     evidence_rejected=judge.stats.evidence_rejected)

            # ---- 停止准则 ----
            new_found = len(pool.candidates) - before
            stop = cov_mod.should_stop(
                est, rounds, max_rounds,
                budget_exhausted=ledger.exhausted(),
                target_coverage=float(pcfg.get("target_coverage", 0.85)),
                last_round_new=last_new)
            last_new = new_found
            emit("stop_check", round=rounds, stop=stop.stop, reason=stop.reason,
                 coverage=round(stop.coverage, 4),
                 expected_new=round(stop.expected_new, 2),
                 marginal_gain=round(stop.marginal_f1_gain, 5))
            followup_decision = agentic.choose_followup(
                plan, list(pool.candidates.values()), round_index=rounds,
                max_rounds=max_rounds, coverage=est.coverage if est else None,
                new_count=new_found)
            emit("agent", round=rounds, action=followup_decision.action,
                 reason=followup_decision.reason,
                 features=followup_decision.features)
            if followup_decision.action == "rewrite" and rounds < max_rounds:
                nxt = agentic.rewrite_queries(plan, queries)
                if nxt and set(nxt) != set(queries):
                    queries = nxt
                    ledger.note("agent", "无标签覆盖不足，执行确定性查询改写")
                    continue
            if stop.stop:
                break

            # ---- 策略演化：生成下一轮检索式 ----
            if not pcfg.get("enable_query_evolution", False):
                break
            with ledger.stage(f"expand_r{rounds}"):
                nxt = self._evolve_queries(llm_fast, plan, cands, p, queries,
                                           est.coverage, ledger)
            if not nxt:
                break
            queries = nxt

        # ---------------- ⑥ 最终输出决策 ----------------
        if not cands:
            return self._empty_result(query, plan, ledger, trace)

        p_gold = self._p_gold(cands, p, plan)
        gate_n_hat = cardinality.predict(plan, cands) if cardinality is not None else None
        gate = f1gate.optimal_cutoff(
            p_gold, n_samples=(None if gate_n_hat is not None
                                else (est.samples if est else None)),
            n_hat=(gate_n_hat if gate_n_hat is not None
                   else (None if est else plan.n_hat_prior)),
            core_ratio=float(pcfg.get("core_ratio", 1.25)),
            band_width=float(pcfg.get("band_width", 0.15)))

        order = np.argsort(-p_gold)
        if fusion_preserve_ids:
            # Keep the declared top-k membership from the pre-fusion L2
            # order, then rank both groups by the calibrated fused probability.
            # This preserves the ranked-prefix invariant and makes any recall
            # tradeoff explicit rather than allowing tail candidates to cross
            # the cutoff as a calibration side effect.
            head_order = [int(index) for index in order
                          if cands[int(index)].pid in fusion_preserve_ids]
            tail_order = [int(index) for index in order
                          if cands[int(index)].pid not in fusion_preserve_ids]
            order = np.asarray([*head_order, *tail_order], dtype=np.int64)
        if fusion_preserve_final_ids:
            head_order = [int(index) for index in order
                          if cands[int(index)].pid in fusion_preserve_final_ids]
            tail_order = [int(index) for index in order
                          if cands[int(index)].pid not in fusion_preserve_final_ids]
            order = np.asarray([*head_order, *tail_order], dtype=np.int64)
        for rank, idx in enumerate(order):
            c = cands[idx]
            c.p_rel = float(p[idx])
            c.p_gold = float(p_gold[idx])
            if rank < gate.core_k:
                c.tier = "core"
            elif rank < gate.k:
                c.tier = "partial"
            else:
                c.tier = "excluded"
        ordered = [cands[i] for i in order]
        core = [c for c in ordered if c.tier == "core"]
        partial = [c for c in ordered if c.tier == "partial"]
        emit("gate", k=gate.k, core=len(core), partial=len(partial),
             threshold=round(gate.threshold, 4),
             expected_f1=round(gate.expected_f1, 4))

        # ---------------- ⑦ 结构化归纳 ----------------
        from ..present.insightboard import build_views
        with ledger.stage("insight"):
            views = build_views(plan, core, partial, llm_fast, ledger,
                                graph=pool.graph)
        emit("insight", views=list(views.keys()))

        candidate_audit = (self._build_candidate_audit(
            pool, audit_stages, audit_orders, audit_seeds, audit_admissions,
            ordered, [*core, *partial], rounds)
            if audit_enabled else {})

        return SearchResult(
            query=query, plan=plan, core=core, partial=partial,
            all_candidates=ordered,
            n_hat=float(gate_n_hat if gate_n_hat is not None
                        else (est.n_hat if est else plan.n_hat_prior)),
            n_hat_ci=est.ci if est else (0.0, 0.0),
            coverage=float(est.coverage) if est else 0.0,
            threshold=float(gate.threshold), expected_f1=float(gate.expected_f1),
            rounds=rounds, ledger=ledger.summary(), views=views, trace=trace,
            candidate_audit=candidate_audit)

    def _build_reranker(self, ledger):
        backend = str((self.cfg.reranker or {}).get("backend") or "lexical").lower()
        if backend in ("local_embedding", "local_embed", "sentence_embedding",
                       "pasa_bge_selector_head", "bge_selector_head"):
            if self._persistent_reranker is None:
                self._persistent_reranker = build_reranker(self.cfg.reranker, ledger)
            else:
                # Attribute fallback diagnostics to the active query rather
                # than the first query which initialised the reusable model.
                self._persistent_reranker.ledger = ledger
            return self._persistent_reranker
        return build_reranker(self.cfg.reranker, ledger)

    def _build_anchor_reranker(self, cfg: Dict[str, Any], ledger):
        """Build/reuse the optional frozen citation-anchor scorer.

        It has its own lifecycle rather than borrowing final L2: reusing L2
        would make an anchor-only ablation change two stages at once.  The
        object caches only local model weights and never candidates or labels.
        """
        backend = str(cfg.get("backend") or "").lower()
        local = ("local_embedding", "local_embed", "sentence_embedding",
                 "pasa_bge_selector_head", "bge_selector_head")
        if backend in local:
            if self._persistent_anchor_reranker is None:
                self._persistent_anchor_reranker = build_reranker(cfg, ledger)
            else:
                self._persistent_anchor_reranker.ledger = ledger
            return self._persistent_anchor_reranker
        return build_reranker(cfg, ledger)

    def _build_dense_admission_reranker(self, cfg: Dict[str, Any], ledger):
        """Build/reuse the frozen scorer dedicated to dense admission.

        It deliberately has a separate cache slot from both final L2 and
        citation anchors.  Reusing either would entangle an admission-only
        experiment with a final-relevance or graph-ablation change.
        """
        backend = str(cfg.get("backend") or "").lower()
        local = ("local_embedding", "local_embed", "sentence_embedding",
                 "pasa_bge_selector_head", "bge_selector_head")
        if backend in local:
            if self._persistent_dense_admission_reranker is None:
                self._persistent_dense_admission_reranker = build_reranker(cfg, ledger)
            else:
                self._persistent_dense_admission_reranker.ledger = ledger
            return self._persistent_dense_admission_reranker
        return build_reranker(cfg, ledger)

    def _release_dense_admission_reranker(self) -> None:
        """Release a prior query's admission scorer before dense GPU search."""
        reranker = self._persistent_dense_admission_reranker
        self._persistent_dense_admission_reranker = None
        close = getattr(reranker, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _release_raw_dense_accelerators(registry, source_names: Sequence[str]) -> None:
        """Release only accelerator state for named raw-query dense sources."""
        for name in source_names:
            source = registry.get(name)
            release = getattr(source, "release_accelerators", None)
            if callable(release):
                release()

    def _selector_gated_dense_candidates(self, ranked: Sequence[Candidate],
                                         plan: QueryPlan, cfg: Dict[str, Any],
                                         ledger: Ledger) -> tuple[List[Candidate], Dict[str, Any]]:
        """Return high-confidence dense-only discoveries for L1 membership.

        This is not a dense score boost and not a final reranker.  Only papers
        found by the configured dense channel and by no lexical channel enter
        the frozen Selector; the normal L1 sort is retained after admission.
        """
        channel = str(cfg.get("channel") or "").strip()
        scorer_cfg = cfg.get("reranker") or {}
        if not channel:
            raise ValueError("dense_admission_selector.channel is required")
        if not isinstance(scorer_cfg, dict) or not scorer_cfg.get("backend"):
            raise ValueError("dense_admission_selector.reranker.backend is required")
        input_keep = int(cfg.get("input_keep", 0) or 0)
        max_protected = int(cfg.get("max_protected", 0) or 0)
        min_score = float(cfg.get("min_score", 0.5))
        if input_keep <= 0 or max_protected <= 0:
            raise ValueError("dense_admission_selector input_keep and max_protected must be positive")
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("dense_admission_selector.min_score must be in [0, 1]")

        eligible = [
            cand for cand in ranked
            if channel in cand.channels
            and not any(name.startswith("lexical:") for name in cand.channels)
        ]
        eligible.sort(key=lambda cand: (
            cand.channel_ranks.get(channel, 10 ** 9), -cand.s_l1, cand.pid))
        scored = eligible[:input_keep]
        event: Dict[str, Any] = {
            "kind": "selector_gated_dense_admission",
            "channel": channel,
            "eligible_count": len(eligible),
            "scored_count": len(scored),
            "input_keep": input_keep,
            "max_protected": max_protected,
            "min_score": min_score,
            "scorer_backend": str(scorer_cfg.get("backend")),
            "scored": [],
            "protected": [],
        }
        if not scored:
            return [], event
        items = [RerankItem(pid=cand.pid, title=cand.paper.title,
                            abstract=cand.paper.abstract, venue=cand.paper.venue,
                            year=cand.paper.year) for cand in scored]
        backend = str(scorer_cfg.get("backend") or "").lower()
        if backend in ("precomputed_selector_scores", "precomputed_pasa_selector_scores"):
            scores = self._score_dense_admission_precomputed(plan.raw_query, items, scorer_cfg)
        elif backend in ("pasa_bge_selector_head_subprocess", "bge_selector_head_subprocess"):
            scores = self._score_dense_admission_subprocess(plan.raw_query, items, scorer_cfg)
        else:
            scorer = self._build_dense_admission_reranker(scorer_cfg, ledger)
            scores = scorer.score(plan.raw_query, items)
        if len(scores) != len(scored) or not np.all(np.isfinite(scores)):
            raise RuntimeError("dense admission scorer returned invalid scores")
        scored_values = [(cand, float(score)) for cand, score in zip(scored, scores)]
        accepted = [(cand, score) for cand, score in scored_values if score >= min_score]
        accepted.sort(key=lambda item: (-item[1], -item[0].s_l1, item[0].pid))
        accepted = accepted[:max_protected]
        event["scored"] = [{
            "pid": cand.pid,
            "dense_rank": cand.channel_ranks.get(channel),
            "selector_score": round(score, 8),
            "passes_threshold": score >= min_score,
        } for cand, score in scored_values]
        event["protected"] = [{
            "pid": cand.pid,
            "dense_rank": cand.channel_ranks.get(channel),
            "selector_score": round(score, 8),
            # This is recorded for a post-hoc audit only; no label is present
            # in this function and l1_score does not affect acceptance.
            "l1_score": round(float(cand.s_l1), 8),
        } for cand, score in accepted]
        return [cand for cand, _ in accepted], event

    def _score_dense_admission_precomputed(self, query: str, items: Sequence[RerankItem],
                                           cfg: Dict[str, Any]) -> np.ndarray:
        """Read frozen label-blind Selector probabilities for one raw query.

        This is an execution isolation mechanism, not a learned cache: the
        referenced artifact must have been built from query/paper pairs before
        any dev labels were opened.  Failing closed on an absent query or PID
        prevents a partially generated score file from quietly changing which
        candidates receive protection.
        """
        path = Path(str(cfg.get("score_path") or "")).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"precomputed Selector score file is missing: {path}")
        cache_key = str(path)
        scores_by_query = self._precomputed_dense_admission_scores.get(cache_key)
        if scores_by_query is None:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("kind") != "PaSa raw-question dense Selector score artifact v1":
                raise ValueError("unrecognized precomputed Selector score artifact")
            scores_by_query = {}
            for row in payload.get("rows") or []:
                key = str(row.get("query_sha256") or "")
                raw_scores = row.get("scores") or {}
                if not key or not isinstance(raw_scores, dict) or key in scores_by_query:
                    raise ValueError("invalid or duplicate precomputed Selector score row")
                values = {str(pid): float(score) for pid, score in raw_scores.items()}
                if not values or not all(np.isfinite(score) and 0.0 <= score <= 1.0
                                          for score in values.values()):
                    raise ValueError("precomputed Selector artifact has invalid probabilities")
                scores_by_query[key] = values
            if not scores_by_query:
                raise ValueError("precomputed Selector artifact has no scored queries")
            self._precomputed_dense_admission_scores[cache_key] = scores_by_query
        query_key = hashlib.sha256(query.encode("utf-8")).hexdigest()
        by_pid = scores_by_query.get(query_key)
        if by_pid is None:
            raise KeyError("precomputed Selector artifact has no score row for this raw query")
        missing = [item.pid for item in items if item.pid not in by_pid]
        if missing:
            raise KeyError(
                "precomputed Selector artifact is missing requested candidate PIDs: "
                + ", ".join(missing[:5]))
        return np.asarray([by_pid[item.pid] for item in items], dtype=np.float64)

    @staticmethod
    def _score_dense_admission_subprocess(query: str, items: Sequence[RerankItem],
                                          cfg: Dict[str, Any]) -> np.ndarray:
        """Score a frozen Selector head outside the dense-retrieval process.

        This path is intentionally narrow and local-only.  It transfers a
        JSON list of candidate texts over stdin, receives probability values
        over stdout, and never passes a benchmark file, qid, or label to the
        worker.  A native worker crash becomes a normal, explanatory Python
        exception in the parent instead of terminating a long PaSa audit.
        """
        model_path = str(cfg.get("model_path") or "")
        head_path = str(cfg.get("selector_head_path") or "")
        if not model_path or not head_path:
            raise ValueError("subprocess Selector requires model_path and selector_head_path")
        worker = Path(__file__).resolve().parents[2] / "scripts" / "score_pasa_selector_pairs.py"
        if not worker.is_file():
            raise FileNotFoundError(f"Selector subprocess worker is missing: {worker}")
        command = [
            sys.executable, str(worker), "--model-path", model_path,
            "--selector-head-path", head_path,
            "--device", str(cfg.get("device") or "cuda"),
            "--batch", str(max(1, int(cfg.get("batch", 2)))),
            "--max-length", str(max(32, int(cfg.get("max_length", 384)))),
            "--abstract-chars", str(max(64, int(cfg.get("abstract_chars", 2500)))),
        ]
        if bool(cfg.get("fp16", True)):
            command.append("--fp16")
        payload = {"query": query, "items": [{
            "pid": item.pid, "title": item.title, "abstract": item.abstract,
            "venue": item.venue, "year": item.year,
        } for item in items]}
        timeout = max(30.0, float(cfg.get("timeout_seconds", 180.0)))
        try:
            completed = subprocess.run(
                command, input=json.dumps(payload, ensure_ascii=False), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Selector subprocess timed out after {timeout:g}s") from exc
        stdout = (completed.stdout or "").strip()
        try:
            response = json.loads(stdout)
        except json.JSONDecodeError as exc:
            stderr = (completed.stderr or "").strip().replace("\n", " ")[:500]
            raise RuntimeError(
                f"Selector subprocess produced non-JSON output (exit={completed.returncode}): {stderr}") from exc
        if completed.returncode != 0 or response.get("error"):
            message = str(response.get("error") or "unknown worker failure")
            raise RuntimeError(f"Selector subprocess failed (exit={completed.returncode}): {message}")
        values = np.asarray(response.get("scores") or [], dtype=np.float64)
        if values.shape != (len(items),) or not np.all(np.isfinite(values)):
            raise RuntimeError("Selector subprocess returned invalid score values")
        return np.clip(values, 0.0, 1.0)

    def close(self) -> None:
        """Best-effort release of a persistent optional local model."""
        reranker = self._persistent_reranker
        self._persistent_reranker = None
        close = getattr(reranker, "close", None)
        if callable(close):
            close()
        anchor_reranker = self._persistent_anchor_reranker
        self._persistent_anchor_reranker = None
        close = getattr(anchor_reranker, "close", None)
        if callable(close):
            close()
        dense_admission_reranker = self._persistent_dense_admission_reranker
        self._persistent_dense_admission_reranker = None
        close = getattr(dense_admission_reranker, "close", None)
        if callable(close):
            close()
        registry = self._persistent_registry
        self._persistent_registry = None
        if registry is not None and registry is not self._registry_override:
            self._close_registry(registry)

    @staticmethod
    def _build_candidate_audit(pool: ProbeResult, stages: Dict[str, Set[str]],
                               orders: Dict[str, List[str]],
                               seeds: Sequence[Dict[str, Any]],
                               admissions: Sequence[Dict[str, Any]],
                               ordered: Sequence[Candidate],
                               selected: Sequence[Candidate], rounds: int) -> Dict[str, Any]:
        """Serialize a compact, label-blind candidate-flow audit.

        This is intentionally performed only after the normal pipeline has
        completed.  It reads no relevance labels and therefore cannot
        influence the result above.  A separate offline script may *later*
        join it with dev gold in order to calculate first-seen/drop statistics.
        """
        l1_rank = {pid: rank for rank, pid in enumerate(
            sorted(stages.get("l1_final", set()),
                   key=lambda pid: (-pool.candidates[pid].s_l1, pid)), 1)}
        l2_input_rank = {pid: rank for rank, pid in enumerate(
            sorted(stages.get("l2_input_final", set()),
                   key=lambda pid: (-pool.candidates[pid].s_l1, pid)), 1)}
        final_rank = {cand.pid: rank for rank, cand in enumerate(ordered, 1)}
        selected_ids = {cand.pid for cand in selected}
        records: Dict[str, Dict[str, Any]] = {}
        for pid, cand in sorted(pool.candidates.items()):
            in_l0 = pid in stages.get("l0_final", set())
            in_l1 = pid in stages.get("l1_final", set())
            in_l2_input = pid in stages.get("l2_input_final", set())
            in_l2 = pid in stages.get("l2_final", set())
            rank = final_rank.get(pid)
            if not in_l0:
                dropped = "l0_filter"
            elif not in_l1:
                dropped = "l1_admission"
            elif not in_l2_input:
                dropped = "l2_input_cap"
            elif not in_l2:
                dropped = "l2_keep"
            elif pid not in selected_ids:
                dropped = "f1_gate"
            else:
                dropped = None
            events = list(cand.provenance)
            records[pid] = {
                "arxiv_id": cand.paper.arxiv_id,
                # Persist a stable fingerprint rather than full text: it
                # detects nondeterministic metadata merge effects at L1/L2
                # without bloating audit artifacts or exposing irrelevant
                # abstract contents a second time.
                "document_fingerprint": hashlib.sha256(
                    f"{cand.paper.title}\x1f{cand.paper.abstract}".encode("utf-8")
                ).hexdigest()[:16],
                "title_chars": len(cand.paper.title or ""),
                "abstract_chars": len(cand.paper.abstract or ""),
                "channels": sorted(cand.channels),
                "channel_ranks": dict(sorted(cand.channel_ranks.items())),
                "first_seen": dict(events[0]) if events else {},
                "provenance": events,
                "abstract_present": bool((cand.paper.abstract or "").strip()),
                "stages": {"l0": in_l0, "l1": in_l1,
                           "l2_input": in_l2_input, "l2": in_l2,
                           "selected": pid in selected_ids},
                "ranks": {"l1": l1_rank.get(pid),
                          "l2_input": l2_input_rank.get(pid),
                          "final": rank},
                "scores": {"rrf": round(float(cand.s_rrf), 8),
                           "lexical": round(float(cand.s_lexical), 8),
                           "dense": round(float(cand.s_dense), 8),
                           "graph": round(float(cand.s_graph), 8),
                           "reference": round(float(cand.s_reference), 8),
                           "title": round(float(cand.s_title), 8),
                           "constraint": round(float(cand.s_constraint), 8),
                           "l1": round(float(cand.s_l1), 8),
                           "l2": (None if cand.s_l2 is None
                                  else round(float(cand.s_l2), 8)),
                           "p_rel": (None if cand.p_rel is None
                                     else round(float(cand.p_rel), 8)),
                           "p_gold": (None if cand.p_gold is None
                                      else round(float(cand.p_gold), 8))},
                "drop_reason": dropped,
            }
        return {
            "version": "candidate_audit_v1",
            "label_policy": "recorded label-blind inside the search pipeline",
            "rounds": rounds,
            "queries_used": list(pool.queries_used),
            "stage_sizes": {name: len(ids) for name, ids in sorted(stages.items())},
            "stage_members": {name: sorted(ids) for name, ids in sorted(stages.items())},
            "stage_orders": {name: list(ids) for name, ids in sorted(orders.items())},
            "seed_selection": list(seeds),
            "selector_gated_admissions": list(admissions),
            "citation_expansions": list(pool.citation_traces),
            "candidates": records,
        }

    # ================================================================== #
    # 内部步骤
    # ================================================================== #
    def _apply_final_rank_l2_blend(self, cands: Sequence[Candidate], p: np.ndarray) -> np.ndarray:
        """Optionally align final calibrated order with the L2 scorer.

        This is disabled by default. Experimental train-only arms use the
        blend only to choose an order, then permute the existing calibrated
        probability values before F1-Gate. The probability mass is unchanged,
        preserving the ranked-prefix invariant and gate calibration.
        """
        try:
            weight = float(self.cfg.pipeline.get("final_rank_l2_weight", 0.0) or 0.0)
        except (TypeError, ValueError):
            weight = 0.0
        weight = min(1.0, max(0.0, weight))
        if weight <= 0.0 or not cands or len(p) != len(cands):
            return p
        values = np.asarray([
            float(candidate.s_l2) if candidate.s_l2 is not None else np.nan
            for candidate in cands
        ], dtype=np.float64)
        if not np.isfinite(values).all():
            return p
        lo, hi = float(values.min()), float(values.max())
        if hi - lo <= 1e-12:
            return p
        l2 = (values - lo) / (hi - lo)
        base = np.asarray(p, dtype=np.float64)
        # Permute the calibrated probability *values* by the blended order
        # instead of changing their multiset.  This improves top-k ordering
        # while preserving the probability mass used by F1-Gate, so a
        # promotion cannot silently inflate the selected prefix.
        order = np.argsort(-((1.0 - weight) * base + weight * l2),
                           kind="mergesort")
        reordered = np.empty_like(base)
        reordered[order] = np.sort(base)[::-1]
        return np.clip(reordered, 1e-4, 1.0 - 1e-4)

    def _calibrate(self, cands: Sequence[Candidate], judge: CascadeJudge,
                   plan: QueryPlan) -> np.ndarray:
        """自适应融合各路信号 → 无监督混合模型校准 → 可比较的相关概率。

        融合权重由信号间一致性在线估计（见 core/fusion.py），而不是硬编码
        「层级越高权重越大」—— 实测表明后者在降级部署下会让级联倒退。

        校准是 F1-Gate 能工作的前提：门限 p* = F1*/2 是一个**绝对概率值**，
        喂进未标定的分数会让它彻底失效（见 docs/DESIGN_V2.md 缺陷一/三）。
        """
        raw, report = adaptive_fuse(collect_signals(cands),
                                    prior=type_prior(plan.query_type.value))
        self.last_fusion = report
        if self.cfg.pipeline.get("constraint_bonus", True):
            # 通过证据对齐校验的约束满足度是一个独立于分数的可靠加成
            sat = np.array([c.constraint_satisfaction() if c.checks else np.nan
                            for c in cands])
            m = ~np.isnan(sat)
            if m.sum() >= 3:
                raw = raw.copy()
                raw[m] = 0.85 * raw[m] + 0.15 * sat[m]
        anchor = independent_mass_anchor(
            self._last_channel_hits or {}, {c.pid for c in cands},
            plan.n_hat_prior,
            prior_weight=float(self.cfg.pipeline.get("anchor_prior_weight", 1.0)))
        self.last_anchor = anchor

        mode = self.cfg.pipeline.get("calibrator", "mixture+temper")
        if mode == "rank_decay":
            cal = RankDecayCalibrator(c=float(self.cfg.pipeline.get("decay_c", 1.6)))
            p = cal.fit_to_mass(raw, anchor).transform(raw)
        else:
            pi = float(np.clip(plan.n_hat_prior / max(len(cands), 1), 0.01, 0.6))
            p = MixtureCalibrator(prior_pi=pi).fit(raw).transform(raw)
            if mode != "mixture":
                # 混合模型的排序可靠但尾部过度自信，用保序的幂变换压尾。
                # 不改排序 → 不伤召回；只收紧 F1-Gate 的纳入边界。
                p, self.last_alpha = tail_temper(p, anchor)
        p = np.clip(p, 1e-4, 1 - 1e-4)
        if self._supervised is not None:
            p = self._supervised.combine(p, cands, self.current_year)
        return p

    def _p_gold(self, cands: Sequence[Candidate], p: np.ndarray,
                plan: QueryPlan) -> np.ndarray:
        """p_gold = p_rel × Pr[被金标准标注 | 相关]。

        评测的 F1 是对金标准算的，而金标准由综述段落的被引文献反推构造，
        存在系统性的标注缺失。我们优化的应是**评测函数**而非抽象的真实相关性。
        可用 pipeline.use_propensity=false 关闭以做消融。
        """
        if not self.cfg.pipeline.get("use_propensity", True) or len(cands) == 0:
            for c, v in zip(cands, p):
                c.propensity = 1.0
                c.p_gold = float(v)
            return np.asarray(p, dtype=np.float64)
        prop = propensity([c.paper.citation_count for c in cands],
                          [c.paper.year for c in cands],
                          [c.paper.is_review for c in cands],
                          current_year=self.current_year)
        # 定位型查询的目标常常就是一篇冷门/新论文，倾向性修正会伤害它 → 弱化
        if plan.query_type == QueryType.LOCATE:
            prop = 0.5 + 0.5 * prop
        out = np.asarray(p, dtype=np.float64) * prop
        for c, pr, g in zip(cands, prop, out):
            c.propensity = float(pr)
            c.p_gold = float(g)
        return out

    @staticmethod
    def _estimate_coverage(pool: ProbeResult, cands: Sequence[Candidate],
                           p: np.ndarray, plan: QueryPlan):
        rel = {c.pid: float(v) for c, v in zip(cands, p)}
        return cov_mod.estimate(pool.channel_hits, relevance=rel,
                                prior_mean=plan.n_hat_prior, n_bootstrap=400)

    @staticmethod
    def _pick_seeds(pool: ProbeResult, cands: Sequence[Candidate],
                    p: np.ndarray, n: int) -> Dict[str, float]:
        """引文扩散的种子：优先用已判定的高分候选；首轮无判定则用 RRF 融合分。"""
        if len(cands) and len(p) == len(cands):
            top = sorted(zip(cands, p), key=lambda x: -x[1])[:n]
            return {c.pid: float(v) for c, v in top if v > 0.3}
        scored = sorted(pool.candidates.values(),
                        key=lambda c: -(c.s_rrf or 0.0))[:n]
        return {c.pid: 1.0 for c in scored}

    def _spend_l3(self, judge: CascadeJudge, cands: Sequence[Candidate],
                  p: np.ndarray, gate, plan: QueryPlan, pcfg: Dict) -> int:
        """按 VoI 排序把 L3 预算花在最能改变结果的候选上。

        这是创新点 1 与创新点 3 的接口：门限 p* 来自 F1-Gate，
        VoI 用它算出「精判后可能跨越门限」的概率，再乘以跨越带来的 F1 变化。
        已经判过 L3 的不再重复花钱。
        """
        policy = str(pcfg.get("l3_policy", "disabled")).lower()
        if policy == "disabled" or judge.llm is None or not len(cands):
            return 0
        budget = min(int(pcfg.get("max_l3_judgments", 40)),
                     plan.budget.max_l3_judgments)
        sigma = np.array([c.sigma for c in cands])
        voi = f1gate.voi_scores(p, sigma, gate.threshold,
                                gate.n_hat_used or plan.n_hat_prior)
        for c, v in zip(cands, voi):
            c.voi = float(v)
        if policy == "adaptive" and float(np.max(voi, initial=0.0)) < float(
                pcfg.get("l3_min_voi", 0.004)):
            return 0
        budget = min(budget, int(pcfg.get("l3_max_papers", 12)))
        voi_order = [i for i in np.argsort(-voi) if cands[i].s_l3 is None]
        if policy == "reference_first":
            # PaSa section references are only a discovery route, never an
            # automatic positive label.  Spend the expensive L3 judgment on
            # these otherwise low-ranked candidates first, then fill the
            # remaining budget by normal F1 value-of-information.
            refs = [i for i in voi_order if "cite_bwd" in cands[i].channels]
            rest = [i for i in voi_order if i not in set(refs)]
            idxs = (refs + rest)[:budget]
        else:
            idxs = voi_order[:budget]
        if not idxs:
            return 0
        before = judge.stats.l3_judged
        judge.l3_verify(cands, plan, idxs,
                        batch_size=int(pcfg.get("l3_batch_size", 6)))
        return judge.stats.l3_judged - before

    @staticmethod
    def _evolve_queries(llm, plan: QueryPlan, cands: Sequence[Candidate],
                        p: np.ndarray, used: Sequence[str], coverage: float,
                        ledger) -> List[str]:
        """基于已确认相关论文演化下一轮检索式（赛题要求的迭代式检索策略）。"""
        top = [c for c, v in sorted(zip(cands, p), key=lambda x: -x[1])[:12]
               if v > 0.5]
        if not top:
            return []
        try:
            data = llm.chat_json(
                EXPAND_SYSTEM,
                EXPAND_USER.format(query=plan.raw_query,
                                   used="\n".join(f"- {u}" for u in used),
                                   titles=render_titles(top),
                                   coverage=coverage),
                stage="expand", default={"queries": []})
        except BudgetExhausted:
            return []
        except Exception:                                        # noqa: BLE001
            return []
        seen = {u.lower().strip() for u in used}
        out = []
        for q in (data.get("queries") or []):
            q = str(q).strip()
            if q and q.lower() not in seen and len(q) > 3:
                out.append(q)
                seen.add(q.lower())
        if ledger and out:
            ledger.note("expand", f"演化出 {len(out)} 条新检索式")
        return out[:4]

    # 触发硬约束回退的召回下限
    MIN_RECALL = 5

    @staticmethod
    def _relax_plan(plan: QueryPlan) -> QueryPlan:
        """把硬过滤约束降级为判定阶段的核验约束，而非直接删除。

        「放宽」不等于「放弃」：venue / 年份约束仍然会在 L3 里被逐条核验并
        体现在约束满足矩阵上，只是不再作为检索前的一刀切过滤器。
        这样即使解析错了，代价也只是多召回一些候选，而不是丢掉全部答案。
        """
        import copy as _copy
        relaxed = _copy.deepcopy(plan)
        for c in relaxed.constraints:
            if c.role == ConstraintRole.HARD_FILTER:
                c.role = ConstraintRole.VERIFY
                c.weight = min(c.weight, 0.8)
        relaxed.notes = (plan.notes + " | 已放宽元数据硬过滤").strip(" |")
        return relaxed

    @staticmethod
    def _empty_result(query, plan, ledger, trace) -> SearchResult:
        return SearchResult(query=query, plan=plan, core=[], partial=[],
                            all_candidates=[], n_hat=0.0, n_hat_ci=(0.0, 0.0),
                            coverage=0.0, threshold=1.0, expected_f1=0.0,
                            rounds=0, ledger=ledger.summary(),
                            views={"empty": True}, trace=trace)
