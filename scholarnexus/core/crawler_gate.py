"""Runtime loader for a PaSa Crawler-SFT citation-expansion action gate.

The official Crawler-SFT data supervises an action that is available in the
local PaSa corpus: whether an anchor paper has a section worth expanding for
the user's query.  This module deliberately does not know any AutoScholarQuery
answers.  It only scores the observable query--anchor state supplied at
retrieval time.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Sequence

import numpy as np

from ..schema import Candidate


_EXPECTED_KIND = "pasa_crawler_expand_gate_hashing_logreg_v1"


@dataclass(frozen=True)
class ExpandGateScores:
    """Scores and immutable model metadata emitted into the retrieval trace."""

    values: tuple[float, ...]
    threshold: float
    model_kind: str


class CrawlerExpandGate:
    """Small, local action model distilled from official PaSa Crawler-SFT.

    The stored value is an *action score*, not a calibrated estimate that the
    final retrieved paper is relevant.  It predicts whether the Crawler-SFT
    demonstrator chose at least one section of an anchor to expand.
    """

    def __init__(self, artifact_path: str):
        path = Path(artifact_path)
        if not path.is_file():
            raise ValueError(f"crawler expand-gate artifact does not exist: {path}")
        try:
            import joblib
        except ImportError as exc:  # pragma: no cover - optional local dependency
            raise RuntimeError(
                "crawler expand-gate requires joblib/scikit-learn; install the local extras") from exc
        bundle = joblib.load(path)
        if not isinstance(bundle, dict) or bundle.get("kind") != _EXPECTED_KIND:
            actual = bundle.get("kind") if isinstance(bundle, dict) else type(bundle).__name__
            raise ValueError(f"unsupported crawler expand-gate artifact: {actual!r}")
        if "vectorizer" not in bundle or "model" not in bundle:
            raise ValueError("crawler expand-gate artifact is missing vectorizer or model")
        threshold = float(bundle.get("threshold", -1.0))
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("crawler expand-gate artifact has an invalid threshold")
        self.path = path
        self.vectorizer = bundle["vectorizer"]
        self.model = bundle["model"]
        self.threshold = threshold
        self.model_kind = str(bundle["kind"])

    @staticmethod
    def _state_text(query: str, candidate: Candidate) -> str:
        paper = candidate.paper
        # Field markers keep title and abstract semantics distinguishable in a
        # bag-of-ngrams model while retaining a single compact vectorizer.
        return (f"[QUERY] {query}\n[ANCHOR_TITLE] {paper.title}\n"
                f"[ANCHOR_ABSTRACT] {paper.abstract}")

    def score(self, query: str, seeds: Sequence[Candidate]) -> ExpandGateScores:
        if not seeds:
            return ExpandGateScores((), self.threshold, self.model_kind)
        states = [self._state_text(query, seed) for seed in seeds]
        matrix = self.vectorizer.transform(states)
        values = np.asarray(self.model.predict_proba(matrix)[:, 1], dtype=np.float64)
        if len(values) != len(seeds) or not np.isfinite(values).all():
            raise RuntimeError("crawler expand-gate produced invalid score output")
        return ExpandGateScores(tuple(float(x) for x in values), self.threshold,
                                self.model_kind)

    def trace_metadata(self, scores: ExpandGateScores) -> Dict[str, object]:
        values = scores.values
        return {
            "model_kind": scores.model_kind,
            "threshold": round(float(scores.threshold), 8),
            "seed_count": len(values),
            "eligible_seed_count": sum(value >= scores.threshold for value in values),
            "max_score": round(max(values), 8) if values else 0.0,
            "mean_score": round(float(sum(values) / len(values)), 8) if values else 0.0,
        }
