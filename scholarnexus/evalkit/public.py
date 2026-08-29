"""SPAR/AutoScholarQuery 与 Asta 风格公开评测适配器。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from ..schema import Paper


@dataclass
class PublicCase:
    qid: str
    query: str
    gold_titles: List[str]
    gold_arxiv_ids: List[str]


def normalize_title(value: str) -> str:
    return "".join(ch for ch in str(value).casefold() if ch.isalnum())


def normalize_arxiv_id(value: str) -> str:
    # Local PaSa sources expose their corpus key as ``arxiv:YYMM.NNNNN``
    # whereas official labels and exported predictions use ``YYMM.NNNNN``.
    # Treat those as the same strict identifier.  This must happen before
    # stripping a URL path: `arxiv:` itself contains no slash.
    clean = re.sub(r"^arxiv:\s*", "", str(value).strip(), flags=re.I)
    clean = clean.rsplit("/", 1)[-1]
    return re.sub(r"v\d+$", "", clean, flags=re.I).casefold()


def load_spar(path: str | Path) -> List[PublicCase]:
    cases: List[PublicCase] = []
    with open(path, encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            query = row.get("question") or row.get("query")
            if not query:
                raise ValueError(f"line {line_no}: query missing")
            titles = row.get("answer") or row.get("answers") or []
            arxiv = row.get("answer_arxiv_id") or row.get("arxiv_ids") or []
            if isinstance(titles, str):
                titles = [titles]
            if isinstance(arxiv, str):
                arxiv = [arxiv]
            cases.append(PublicCase(
                qid=str(row.get("qid") or f"spar-{line_no}"), query=str(query),
                gold_titles=[str(v) for v in titles],
                gold_arxiv_ids=[str(v) for v in arxiv],
            ))
    return cases


def match_metrics(papers: Iterable[Paper], case: PublicCase,
                  strict_arxiv_ids: bool = False) -> dict:
    """Score a prediction set against one public case.

    PaSa provides ``answer_arxiv_id`` and it is the only unambiguous identity
    for the benchmark.  ``strict_arxiv_ids=True`` therefore disables title
    fallback when IDs exist; title fallback remains available for older public
    corpora that genuinely lack identifiers.
    """
    predicted = list(papers)
    title_gold = {normalize_title(v): i for i, v in enumerate(case.gold_titles) if v}
    arxiv_gold = {normalize_arxiv_id(v): i for i, v in enumerate(case.gold_arxiv_ids) if v}
    gold_n = max(len(case.gold_titles), len(case.gold_arxiv_ids), 1)
    matched: set[int] = set()
    hit_predictions = 0
    for paper in predicted:
        indexes = set()
        title = normalize_title(paper.title)
        arxiv = normalize_arxiv_id(paper.arxiv_id) if paper.arxiv_id else ""
        if not (strict_arxiv_ids and arxiv_gold) and title in title_gold:
            indexes.add(title_gold[title])
        if arxiv and arxiv in arxiv_gold:
            indexes.add(arxiv_gold[arxiv])
        new = indexes - matched
        if new:
            matched.add(min(new))
            hit_predictions += 1
    precision = hit_predictions / len(predicted) if predicted else 0.0
    recall = len(matched) / gold_n
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1,
            "hits": len(matched), "predicted": len(predicted), "gold": gold_n}


def macro(rows: Sequence[dict], k_values: Sequence[int]) -> dict:
    valid = [row for row in rows if "metrics" in row]
    summary = {"successful": len(valid), "failed": len(rows) - len(valid)}
    for k in k_values:
        label = f"at_{k}"
        summary[label] = {
            metric: (sum(row["metrics"][label][metric] for row in valid) / len(valid)
                     if valid else 0.0)
            for metric in ("precision", "recall", "f1")
        }
    if valid:
        summary["avg_api_calls"] = sum(row["api_calls"] for row in valid) / len(valid)
        summary["avg_llm_calls"] = sum(row["llm_calls"] for row in valid) / len(valid)
        summary["avg_seconds"] = sum(row["seconds"] for row in valid) / len(valid)
    else:
        summary.update(avg_api_calls=0.0, avg_llm_calls=0.0, avg_seconds=0.0)
    return summary
