"""Features shared by the PaSa Crawler-SFT section-selection distillation.

The official PaSa archive stores only ``section heading -> cited titles``; it
does *not* contain section text.  This module consequently models the honest
decision that is available locally: which headings are worth expanding for a
query and its anchor paper.  It deliberately has no dependency on public
AutoScholarQuery dev/test labels.
"""
from __future__ import annotations

import re
from typing import List, Sequence

import numpy as np
from sklearn.preprocessing import normalize


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,}")
_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "it", "of", "on", "or", "that", "the", "this", "to", "we",
    "with", "without", "you", "your",
}

# These are deliberately transparent heading *types*, not labels inferred from
# PaSa dev/test.  They let a compact classifier express that a query asking
# about prior work and one asking about a proposed algorithm tend to navigate
# different parts of an anchor paper.
_HEADING_TYPES = (
    "introduction", "background", "related_work", "literature_review",
    "method", "model", "approach", "theory", "experiment", "result",
    "dataset", "evaluation", "discussion", "conclusion", "appendix",
)
_TYPE_PATTERNS = {
    "introduction": ("introduction",),
    "background": ("background", "preliminar"),
    "related_work": ("related work", "prior work", "previous work"),
    "literature_review": ("literature review", "survey"),
    "method": ("method", "methodology", "algorithm", "procedure"),
    "model": ("model", "architecture", "representation"),
    "approach": ("approach", "framework", "formulation"),
    "theory": ("theor", "proof", "guarantee", "bound", "analysis"),
    "experiment": ("experiment", "implementation", "training"),
    "result": ("result", "finding", "ablation"),
    "dataset": ("dataset", "data set", "benchmark", "corpus"),
    "evaluation": ("evaluation", "comparison", "performance"),
    "discussion": ("discussion", "limitation", "future work"),
    "conclusion": ("conclusion", "concluding", "summary"),
    "appendix": ("appendix", "supplement"),
}


def tokens(text: str) -> List[str]:
    """Lower-cased English lexical units for transparent overlap features."""
    return [x.lower() for x in _TOKEN_RE.findall(str(text or ""))
            if x.lower() not in _STOP]


def heading_type_features(headings: Sequence[str]) -> np.ndarray:
    out = np.zeros((len(headings), len(_HEADING_TYPES)), dtype=np.float32)
    for row, value in enumerate(headings):
        heading = str(value or "").casefold()
        for col, kind in enumerate(_HEADING_TYPES):
            out[row, col] = float(any(part in heading
                                      for part in _TYPE_PATTERNS[kind]))
    return out


def _row_dot(left, right) -> np.ndarray:
    return np.asarray(left.multiply(right).sum(axis=1)).ravel().astype(np.float32)


def _lexical_features(queries: Sequence[str], headings: Sequence[str],
                      positions: Sequence[float], total_sections: Sequence[float]) -> np.ndarray:
    out = np.zeros((len(headings), 5), dtype=np.float32)
    for i, (query, heading) in enumerate(zip(queries, headings)):
        q_terms, h_terms = set(tokens(query)), set(tokens(heading))
        common = q_terms & h_terms
        out[i, 0] = len(common) / max(1, len(h_terms))       # heading precision
        out[i, 1] = len(common) / max(1, len(q_terms))       # query coverage
        out[i, 2] = min(1.0, len(common) / 4.0)              # robust raw overlap
        out[i, 3] = min(1.0, len(h_terms) / 18.0)
        out[i, 4] = min(1.0, max(0.0, float(positions[i])) /
                        max(1.0, float(total_sections[i]) - 1.0))
    return out


def make_features(word_vectorizer, char_vectorizer, queries: Sequence[str],
                  titles: Sequence[str], abstracts: Sequence[str],
                  headings: Sequence[str], positions: Sequence[float],
                  total_sections: Sequence[float]) -> np.ndarray:
    """Build compact, order-aware query--anchor--heading features.

    The output has a fixed schema saved with the model bundle.  Similarity
    features are calculated row-wise, avoiding any accidental comparison of a
    query with a different anchor's section in a batched inference call.
    """
    if not (len(queries) == len(titles) == len(abstracts) == len(headings)
            == len(positions) == len(total_sections)):
        raise ValueError("Section selector feature inputs must have equal length")
    if not headings:
        return np.zeros((0, 5 + len(_HEADING_TYPES) + 5), dtype=np.float32)

    q_word = normalize(word_vectorizer.transform(queries))
    h_word = normalize(word_vectorizer.transform(headings))
    t_word = normalize(word_vectorizer.transform(titles))
    a_word = normalize(word_vectorizer.transform(abstracts))
    anchor_word = normalize(t_word + a_word)
    q_char = normalize(char_vectorizer.transform(queries))
    h_char = normalize(char_vectorizer.transform(headings))

    similarities = np.column_stack((
        _row_dot(q_word, h_word),
        _row_dot(q_char, h_char),
        _row_dot(q_word, t_word),
        _row_dot(q_word, a_word),
        _row_dot(q_word, anchor_word),
    )).astype(np.float32)
    return np.hstack((similarities,
                      _lexical_features(queries, headings, positions, total_sections),
                      heading_type_features(headings))).astype(np.float32)


FEATURE_NAMES = (
    "word_query_heading_cosine", "char_query_heading_cosine",
    "word_query_title_cosine", "word_query_abstract_cosine",
    "word_query_anchor_cosine", "heading_query_precision",
    "heading_query_coverage", "heading_query_overlap_capped",
    "heading_length", "heading_relative_position",
    *tuple("heading_type_" + x for x in _HEADING_TYPES),
)
