"""Label-blind retrieval control inspired by AgenticArXiv-RL.

The upstream project trains a ReAct policy for choosing tools in a mock arXiv
environment.  PaSa is a different task: the useful action is a retrieval
channel, citation expansion, deterministic rewrite, or stop.  This module is
the small, auditable controller used for that transfer experiment.  It never
receives development answers and it does not score or rank papers itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence

from .crawler_gate import CrawlerExpandGate
from ..schema import Candidate, QueryPlan, QueryType


@dataclass(frozen=True)
class AgenticDecision:
    """One action decision plus the observable state that justified it."""

    action: str
    reason: str
    features: Dict[str, Any] = field(default_factory=dict)


class AgenticController:
    """A deterministic finite-state policy over retrieval tools.

    This is intentionally not presented as a trained RL checkpoint.  It is a
    zero-shot policy that makes the AgenticArXiv-RL action/observation idea
    testable on PaSa before investing in a PaSa-specific SFT/DPO/GRPO run.
    """

    _DENSE_TYPES = {QueryType.SURVEY, QueryType.METHOD_CROSS,
                    QueryType.BENCHMARK, QueryType.LINEAGE}

    def __init__(self, cfg: Dict[str, Any] | None = None):
        self.cfg = dict(cfg or {})
        self.enabled = bool(self.cfg.get("enabled", False))
        self.decisions: List[AgenticDecision] = []
        gate_path = str(self.cfg.get("crawler_expand_gate_path", "") or "").strip()
        # A disabled controller must preserve the old no-policy behavior and
        # must not require optional local SFT artifacts to exist.
        gate_path = gate_path if self.enabled else ""
        self._crawler_expand_gate = CrawlerExpandGate(gate_path) if gate_path else None

    @staticmethod
    def _features(plan: QueryPlan, candidates: Sequence[Candidate]) -> Dict[str, Any]:
        channels: Dict[str, int] = {}
        for cand in candidates:
            for channel in cand.channels:
                channels[channel] = channels.get(channel, 0) + 1
        lexical = [name for name in channels if name.startswith("lexical:")]
        lexical_sets = []
        for name in lexical:
            lexical_sets.append({cand.pid for cand in candidates if name in cand.channels})
        overlap = 0.0
        if lexical_sets and candidates:
            overlap = sum(len(ids) for ids in lexical_sets) / max(1, len(candidates) * len(lexical_sets))
        top = sorted((float(c.s_l1) for c in candidates), reverse=True)
        return {
            "query_type": plan.query_type.value,
            "candidate_count": len(candidates),
            "lexical_channel_count": len(lexical),
            "lexical_channel_overlap": round(float(overlap), 6),
            "top_l1": round(top[0], 6) if top else 0.0,
            "median_top_l1": round(top[min(len(top) - 1, 19)] if top else 0.0, 6),
            "quoted_span_count": len(plan.quoted_spans),
        }

    def _record(self, action: str, reason: str, features: Dict[str, Any]) -> AgenticDecision:
        decision = AgenticDecision(action=action, reason=reason, features=dict(features))
        self.decisions.append(decision)
        return decision

    def choose_dense(self, plan: QueryPlan, candidates: Sequence[Candidate], *, available: bool) -> AgenticDecision:
        """Decide whether to call the raw-question dense tool."""
        features = self._features(plan, candidates)
        if not self.enabled:
            return self._record("dense", "controller_disabled", features)
        if not available:
            return self._record("skip_dense", "dense_tool_unavailable", features)
        if bool(self.cfg.get("dense_always", False)):
            return self._record("dense", "configured_always", features)
        types = {str(value).lower() for value in self.cfg.get("dense_types", [])}
        dense_types = types or {item.value for item in self._DENSE_TYPES}
        min_pool = int(self.cfg.get("dense_if_pool_below", 260))
        min_overlap = float(self.cfg.get("dense_if_overlap_below", 0.36))
        min_top = float(self.cfg.get("dense_if_top_l1_below", 0.42))
        if features["query_type"] in dense_types:
            return self._record("dense", "query_type_requires_semantic_tool", features)
        if features["candidate_count"] < min_pool:
            return self._record("dense", "lexical_pool_sparse", features)
        if features["lexical_channel_overlap"] < min_overlap:
            return self._record("dense", "lexical_channels_disagree", features)
        if features["top_l1"] < min_top:
            return self._record("dense", "lexical_confidence_low", features)
        return self._record("skip_dense", "lexical_evidence_sufficient", features)

    def choose_citation(self, plan: QueryPlan, candidates: Sequence[Candidate],
                        seeds: Sequence[Candidate]) -> AgenticDecision:
        """Choose citation expansion after an initial text/tool observation."""
        features = self._features(plan, candidates)
        seed_count = len(seeds)
        features["seed_count"] = int(seed_count)
        if not self.enabled:
            return self._record("citation", "controller_disabled", features)
        if seed_count <= 0:
            return self._record("skip_citation", "no_eligible_seed", features)
        skip_types = {str(value).lower() for value in self.cfg.get(
            "skip_citation_types", [QueryType.LOCATE.value])}
        if features["query_type"] in skip_types:
            return self._record("skip_citation", "locate_query_prefers_direct_match", features)
        max_pool = int(self.cfg.get("skip_citation_if_pool_above", 1000000))
        if features["candidate_count"] > max_pool:
            return self._record("skip_citation", "pool_budget_guard", features)
        if self._crawler_expand_gate is not None:
            gate_scores = self._crawler_expand_gate.score(plan.raw_query, seeds)
            gate_features = self._crawler_expand_gate.trace_metadata(gate_scores)
            features["crawler_expand_gate"] = gate_features
            if not gate_features["eligible_seed_count"]:
                return self._record("skip_citation", "crawler_sft_no_expand_action", features)
        return self._record("citation", "graph_tool_has_eligible_seed", features)

    def choose_admission(self, plan: QueryPlan, candidates: Sequence[Candidate],
                         base_keep: int) -> AgenticDecision:
        """Choose the L1 admission budget from the observed candidate state."""
        features = self._features(plan, candidates)
        base_keep = max(1, int(base_keep))
        features["base_l1_keep"] = base_keep
        if not self.enabled:
            features["l1_keep"] = base_keep
            return self._record("keep_admission", "controller_disabled", features)
        max_keep = max(base_keep, int(self.cfg.get("admission_max_keep", base_keep)))
        min_overlap = float(self.cfg.get("widen_if_overlap_below", 0.72))
        min_pool = int(self.cfg.get("widen_if_pool_above", base_keep * 2))
        if (features["lexical_channel_overlap"] < min_overlap
                or features["candidate_count"] > min_pool):
            features["l1_keep"] = max_keep
            return self._record("widen_admission", "candidate_state_uncertain", features)
        features["l1_keep"] = base_keep
        return self._record("keep_admission", "candidate_state_concentrated", features)

    def choose_followup(self, plan: QueryPlan, candidates: Sequence[Candidate],
                        *, round_index: int, max_rounds: int,
                        coverage: float | None, new_count: int) -> AgenticDecision:
        """Choose deterministic rewrite or stop after a round."""
        features = self._features(plan, candidates)
        features.update({"round": int(round_index), "max_rounds": int(max_rounds),
                         "coverage": None if coverage is None else round(float(coverage), 6),
                         "new_count": int(new_count)})
        if not self.enabled:
            return self._record("stop", "controller_disabled", features)
        min_coverage = float(self.cfg.get("rewrite_if_coverage_below", 0.72))
        if round_index < max_rounds and (coverage is None or coverage < min_coverage):
            return self._record("rewrite", "coverage_below_agent_threshold", features)
        return self._record("stop", "coverage_or_round_budget_sufficient", features)

    @staticmethod
    def rewrite_queries(plan: QueryPlan, current: Iterable[str]) -> List[str]:
        """Produce two reproducible lexical probes without an LLM call."""
        current = list(current)
        out: List[str] = []
        if plan.quoted_spans:
            out.append(plan.quoted_spans[0])
        words = [word for word in plan.raw_query.split()
                 if any(ch.isalnum() for ch in word) and len(word) > 2]
        if words:
            out.append(" ".join(words[:8]))
            if len(words) > 5:
                out.append(" ".join(words[2:10]))
        for query in [*out, *current]:
            query = " ".join(str(query).split())
            if query and query not in out:
                out.append(query)
        return out[:3]
