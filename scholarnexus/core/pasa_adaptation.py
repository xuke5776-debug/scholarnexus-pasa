"""Validated local models used by the PaSa adaptation experiments.

All loaders are opt-in.  A missing artifact never changes retrieval behavior;
an incompatible artifact is an explicit configuration error rather than a
silent fallback.  The models receive only query, candidate, and controller
state observable before ranking/output selection.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import numpy as np

from ..schema import Candidate, QueryPlan, QueryType


PROFILE_NAMES = ("P0", "P1", "P2", "P3")
PROFILE_SPECS: Dict[str, Dict[str, int | bool]] = {
    "P0": {"citation_enabled": False, "l1_keep": 700, "l2_input_keep": 150, "l2_keep": 150},
    "P1": {"citation_enabled": True, "l1_keep": 700, "l2_input_keep": 150, "l2_keep": 150},
    "P2": {"citation_enabled": True, "l1_keep": 1000, "l2_input_keep": 150, "l2_keep": 150},
    "P3": {"citation_enabled": True, "l1_keep": 1000, "l2_input_keep": 300, "l2_keep": 300},
}

_QUERY_TYPES = tuple(item.value for item in QueryType)
_L2_KIND = "pasa_l2_fusion_v1"
_CARDINALITY_KIND = "pasa_cardinality_predictor_v1"
_PROFILE_KIND = "pasa_profile_policy_v1"


def normalized_pasa_query(value: str) -> str:
    """Canonical query identity for every train-only PaSa split."""
    return " ".join(str(value or "").casefold().split())


def pasa_query_hash(value: str, seed: int) -> int:
    return int.from_bytes(hashlib.blake2b(
        f"{seed}:{normalized_pasa_query(value)}".encode(), digest_size=8).digest(), "big")


def is_pasa_policy_train_query(value: str, seed: int) -> bool:
    return pasa_query_hash(value, seed) % 10_000 < 8_000


def _load_bundle(path: str, expected_kind: str) -> Mapping[str, Any]:
    artifact = Path(path)
    if not artifact.is_file():
        raise ValueError(f"PaSa adaptation artifact does not exist: {artifact}")
    try:
        import joblib
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("PaSa adaptation artifacts require joblib/scikit-learn") from exc
    bundle = joblib.load(artifact)
    if not isinstance(bundle, Mapping) or bundle.get("kind") != expected_kind:
        actual = bundle.get("kind") if isinstance(bundle, Mapping) else type(bundle).__name__
        raise ValueError(f"unexpected PaSa adaptation artifact kind: {actual!r}")
    if not bool(bundle.get("promoted", False)):
        raise ValueError("refusing an adaptation artifact that did not pass its promotion gate")
    return bundle


def query_state_features(plan: QueryPlan, candidates: Sequence[Candidate]) -> Dict[str, float]:
    """Stable label-blind controller features shared by policy/cardinality models."""
    count = len(candidates)
    query_words = normalized_pasa_query(plan.raw_query).split()
    query_word_set = set(query_words)
    ranks = [min(c.channel_ranks.values()) for c in candidates if c.channel_ranks]
    # Profiles are selected immediately after the mandatory lexical+dense
    # probe.  At that point L1 has not necessarily run, so fall back to the
    # already-observed RRF score rather than smuggling in a later signal.
    admission_scores = sorted((float(c.s_l1) if abs(float(c.s_l1)) > 1e-12
                               else float(c.s_rrf) for c in candidates), reverse=True)
    channels = {channel for candidate in candidates for channel in candidate.channels}
    pairs = count * (count - 1) / 2
    shared_pairs = sum(
        len([candidate for candidate in candidates if channel in candidate.channels])
        * (len([candidate for candidate in candidates if channel in candidate.channels]) - 1) / 2
        for channel in channels)
    overlap = shared_pairs / pairs if pairs else 0.0
    out = {
        "log_candidate_count": math.log1p(count),
        "log_query_chars": math.log1p(len(plan.raw_query.strip())),
        "log_query_words": math.log1p(len(query_words)),
        # These are deliberately coarse wording cues, not answer-derived
        # features.  They let a train-only gate distinguish a request for a
        # complete literature set from one asking for representative work.
        "cue_exhaustive": float(bool(query_word_set & {"all", "every", "complete", "comprehensive"})),
        "cue_representative": float(bool(query_word_set & {"representative", "example", "examples", "key"})),
        "cue_comparison": float(bool(query_word_set & {"compare", "comparison", "versus", "vs"})),
        "cue_list": float(bool(query_word_set & {"papers", "works", "studies", "methods", "approaches"})),
        "channel_count": float(len(channels)),
        "mean_channel_count": float(sum(len(c.channels) for c in candidates) / max(1, count)),
        "channel_pair_overlap": float(overlap),
        "best_channel_rank": float(min(ranks) if ranks else 0),
        "top_l1": float(admission_scores[0] if admission_scores else 0.0),
        "l1_at_20": float(admission_scores[min(19, len(admission_scores) - 1)]
                          if admission_scores else 0.0),
        "l1_decay_20": float((admission_scores[0] - admission_scores[min(19, len(admission_scores) - 1)])
                             if admission_scores else 0.0),
        "quoted_span_count": float(len(plan.quoted_spans)),
        "constraint_count": float(len(plan.constraints)),
    }
    for value in _QUERY_TYPES:
        out[f"query_type_{value}"] = float(plan.query_type.value == value)
    return out


def _matrix(rows: Sequence[Mapping[str, float]], names: Sequence[str]) -> np.ndarray:
    return np.asarray([[float(row.get(name, 0.0)) for name in names] for row in rows],
                      dtype=np.float32)


def l2_feature_row(plan: QueryPlan, candidate: Candidate) -> Dict[str, float]:
    """Feature schema for a candidate already admitted to L2.

    ``s_l2`` at this point is the frozen BGE/lexical base score.  The fused
    model replaces it only after every listed input has been observed.
    """
    ranks = list(candidate.channel_ranks.values())
    row = {
        "base_l2": float(candidate.s_l2 if candidate.s_l2 is not None else candidate.s_l1),
        "l1": float(candidate.s_l1), "rrf": float(candidate.s_rrf),
        "lexical": float(candidate.s_lexical), "dense": float(candidate.s_dense),
        "graph": float(candidate.s_graph), "reference": float(candidate.s_reference),
        "title": float(candidate.s_title), "constraint": float(candidate.s_constraint),
        "channel_count": float(len(candidate.channels)),
        "best_channel_rank": float(min(ranks) if ranks else 0),
        "has_dense": float(any(name.startswith("dense:") for name in candidate.channels)),
        "has_citation": float(any(name.startswith("cite_") for name in candidate.channels)),
        "has_lexical": float(any(name.startswith("lexical:") for name in candidate.channels)),
    }
    for value in _QUERY_TYPES:
        row[f"query_type_{value}"] = float(plan.query_type.value == value)
    return row


@dataclass(frozen=True)
class ProfileDecision:
    profile: str
    predicted_rewards: Dict[str, float]
    state: Dict[str, float]


class ProfilePolicy:
    """Choose one bounded retrieval profile after the mandatory dense probe."""

    def __init__(self, artifact_path: str):
        bundle = _load_bundle(artifact_path, _PROFILE_KIND)
        self.model = bundle.get("model")
        self.feature_names = tuple(str(value) for value in bundle.get("feature_names") or ())
        self.profile_names = tuple(str(value) for value in bundle.get("profiles") or ())
        if self.model is None or not self.feature_names or self.profile_names != PROFILE_NAMES:
            raise ValueError("profile-policy artifact has an invalid schema")

    def choose(self, plan: QueryPlan, candidates: Sequence[Candidate]) -> ProfileDecision:
        state = query_state_features(plan, candidates)
        rows = []
        for profile in PROFILE_NAMES:
            row = dict(state)
            for name in PROFILE_NAMES:
                row[f"profile_{name}"] = float(name == profile)
            rows.append(row)
        values = np.asarray(self.model.predict(_matrix(rows, self.feature_names)), dtype=np.float64)
        if values.shape != (len(PROFILE_NAMES),) or not np.isfinite(values).all():
            raise RuntimeError("profile policy emitted invalid reward predictions")
        raw_predicted = {name: float(value) for name, value in zip(PROFILE_NAMES, values)}
        predicted = {name: round(value, 8) for name, value in raw_predicted.items()}
        # Baseline P2 is the deterministic tie-breaker, retaining known-safe
        # dense + wide-admission behavior when a learned policy is indifferent.
        best = max(PROFILE_NAMES, key=lambda name: (raw_predicted[name], name == "P2", name))
        return ProfileDecision(best, predicted, state)


class L2FusionModel:
    """Replace an L2 base score with a promoted train-only fused probability."""

    def __init__(self, artifact_path: str):
        bundle = _load_bundle(artifact_path, _L2_KIND)
        self.model = bundle.get("model")
        self.feature_names = tuple(str(value) for value in bundle.get("feature_names") or ())
        if self.model is None or not self.feature_names:
            raise ValueError("L2 fusion artifact has an invalid schema")

    def rerank(self, plan: QueryPlan, candidates: Sequence[Candidate],
               blend_weight: float = 1.0, blend_mode: str = "linear") -> list[Candidate]:
        """Score admitted candidates with an optional base-score residual.

        A promoted model is trained to replace the L2 score, but deployment
        can request a bounded interpolation with the pre-model L2 score.  The
        interpolation is performed in the current pool's unit interval so a
        classifier probability cannot dominate solely because its calibration
        scale differs from the lexical/cross-encoder score.
        """
        rows = [l2_feature_row(plan, candidate) for candidate in candidates]
        if not rows:
            return []
        values = np.asarray(self.model.predict_proba(_matrix(rows, self.feature_names))[:, 1],
                            dtype=np.float64)
        if len(values) != len(candidates) or not np.isfinite(values).all():
            raise RuntimeError("L2 fusion model emitted invalid scores")
        try:
            weight = min(1.0, max(0.0, float(blend_weight)))
        except (TypeError, ValueError):
            weight = 1.0
        base = np.asarray([float(candidate.s_l2 or 0.0) for candidate in candidates],
                          dtype=np.float64)
        def _unit(value: np.ndarray) -> np.ndarray:
            lo, hi = float(value.min()), float(value.max())
            return ((value - lo) / (hi - lo)
                    if hi - lo > 1e-12 else np.zeros_like(value))
        base_unit, model_unit = _unit(base), _unit(values)
        mode = str(blend_mode or "linear").strip().casefold()
        if mode in {"geometric", "geom", "product"}:
            # A geometric mean is conservative when either arm is low, which
            # protects long-tail candidates from a brittle model-only jump.
            scores = np.power(np.maximum(base_unit, 1e-12), 1.0 - weight)
            scores *= np.power(np.maximum(model_unit, 1e-12), weight)
        elif mode == "min":
            scores = np.minimum(base_unit, model_unit)
        elif mode == "max":
            scores = np.maximum(base_unit, model_unit)
        else:
            scores = (1.0 - weight) * base_unit + weight * model_unit
        for candidate, score in zip(candidates, scores):
            candidate.s_l2 = float(score)
            candidate.judged_level = max(candidate.judged_level, 2)
        return sorted(candidates, key=lambda candidate: (-(candidate.s_l2 or 0.0), candidate.pid))


class CardinalityPredictor:
    """Train-only cardinality estimate used by F1-Gate after L2 scoring."""

    def __init__(self, artifact_path: str):
        bundle = _load_bundle(artifact_path, _CARDINALITY_KIND)
        self.model = bundle.get("model")
        self.feature_names = tuple(str(value) for value in bundle.get("feature_names") or ())
        self.min_value = float(bundle.get("min_value", 1.0))
        self.max_value = float(bundle.get("max_value", 100.0))
        if self.model is None or not self.feature_names or self.min_value <= 0 or self.max_value < self.min_value:
            raise ValueError("cardinality artifact has an invalid schema")

    def predict(self, plan: QueryPlan, candidates: Sequence[Candidate]) -> float:
        state = query_state_features(plan, candidates)
        l2 = sorted((float(candidate.s_l2 or 0.0) for candidate in candidates), reverse=True)
        state["top_l2"] = l2[0] if l2 else 0.0
        state["l2_at_20"] = l2[min(19, len(l2) - 1)] if l2 else 0.0
        value = float(np.asarray(self.model.predict(_matrix([state], self.feature_names))).ravel()[0])
        if not math.isfinite(value):
            raise RuntimeError("cardinality predictor emitted a non-finite value")
        return min(self.max_value, max(self.min_value, value))
