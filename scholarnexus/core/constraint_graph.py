"""可执行约束图：宽召回、严验证、可审计。

每个查询约束形成一个 OR 组（原词与别名任选其一），不同正向组之间按 AND
解释，负向组按 NOT 解释。检索阶段只使用 anchor 组，排序阶段使用完整图。
这保留了高召回，同时避免把全部约束拼成脆弱的长查询串。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Sequence

from ..schema import Constraint, ConstraintRole, Paper
from ..utils import normalize_text, tokenize


@dataclass
class ConstraintGroup:
    gid: str
    role: str
    kind: str
    terms: List[str]
    weight: float
    operator: str = "OR"
    required: bool = True


@dataclass
class GraphMatch:
    score: float
    positive_score: float
    negative_penalty: float
    hard_violation: bool
    groups: Dict[str, float] = field(default_factory=dict)


def _term_key(value: str) -> str:
    toks = []
    for token in tokenize(normalize_text(value)):
        # 仅用于同义约束去重的轻量词形归一；不改变实际检索词。
        if token.isascii() and len(token) > 4 and token.endswith("s"):
            token = token[:-1]
        toks.append(token)
    return " ".join(toks)


def _values(value: Any) -> Iterable[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [str(v) for v in value.values() if v is not None]
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def _dedupe_terms(terms: Iterable[str]) -> List[str]:
    """去重并删除被更长短语包含的弱别名。"""
    uniq: Dict[str, str] = {}
    for term in terms:
        clean = normalize_text(str(term))[:120]
        key = _term_key(clean)
        if key:
            uniq.setdefault(key, clean)
    keys = sorted(uniq, key=lambda k: (-len(k.split()), k))
    kept: List[str] = []
    for key in keys:
        tokens = set(key.split())
        if any(tokens and tokens < set(other.split()) for other in kept):
            continue
        kept.append(key)
    return [uniq[key] for key in kept[:8]]


def prune_constraints(constraints: Sequence[Constraint]) -> List[Constraint]:
    """合并同类重复约束，避免 LLM 同义复述被重复计权。"""
    out: List[Constraint] = []
    for con in constraints:
        key = _term_key(con.text)
        merged = None
        for old in out:
            if old.kind != con.kind or old.role != con.role:
                continue
            old_key = _term_key(old.text)
            a, b = set(key.split()), set(old_key.split())
            if key == old_key or (a and b and len(a & b) / max(len(a | b), 1) >= 0.8):
                merged = old
                break
        if merged is None:
            terms = _dedupe_terms([con.text, *con.aliases, *_values(con.value)])
            text_key = _term_key(con.text)
            con.aliases = [term for term in terms if _term_key(term) != text_key][:7]
            out.append(con)
        else:
            terms = _dedupe_terms(
                [merged.text, *merged.aliases, con.text, *con.aliases, *_values(con.value)]
            )
            merged_key = _term_key(merged.text)
            merged.aliases = [term for term in terms if _term_key(term) != merged_key][:7]
            merged.weight = max(merged.weight, con.weight)
    return out


def compile_constraint_graph(constraints: Sequence[Constraint]) -> Dict[str, Any]:
    groups: List[ConstraintGroup] = []
    for index, con in enumerate(constraints, 1):
        role = con.role.value if hasattr(con.role, "value") else str(con.role)
        kind = con.kind.value if hasattr(con.kind, "value") else str(con.kind)
        terms = _dedupe_terms([con.text, *con.aliases, *_values(con.value)])
        if not terms:
            continue
        groups.append(ConstraintGroup(
            gid=f"g{index}", role=role, kind=kind, terms=terms,
            weight=max(float(con.weight), 0.05),
            required=role in {ConstraintRole.HARD_FILTER.value,
                              ConstraintRole.ANCHOR.value},
        ))
    return {
        "semantics": "AND(positive OR-groups) AND NOT(negative OR-groups)",
        "groups": [asdict(group) for group in groups],
        "retrieval_groups": [g.gid for g in groups if g.role == ConstraintRole.ANCHOR.value],
        "verification_groups": [g.gid for g in groups if g.role != ConstraintRole.ANCHOR.value],
    }


def _coverage(term: str, doc_tokens: set[str]) -> float:
    tokens = set(tokenize(term))
    if not tokens:
        return 0.0
    return len(tokens & doc_tokens) / len(tokens)


def match_paper(graph: Dict[str, Any], paper: Paper) -> GraphMatch:
    doc_tokens = set(tokenize(paper.text() + " " + paper.venue + " " + " ".join(paper.fields)))
    positive_sum = 0.0
    positive_weight = 0.0
    negative_penalty = 0.0
    hard_violation = False
    scores: Dict[str, float] = {}
    for group in graph.get("groups", []):
        score = max((_coverage(term, doc_tokens) for term in group.get("terms", [])), default=0.0)
        gid = str(group.get("gid", ""))
        scores[gid] = score
        weight = max(float(group.get("weight", 1.0)), 0.05)
        if group.get("role") == ConstraintRole.NEGATIVE.value:
            if score >= 0.8:
                negative_penalty += weight * score
            continue
        positive_sum += weight * score
        positive_weight += weight
        if group.get("role") == ConstraintRole.HARD_FILTER.value and score == 0.0:
            # 元数据缺失不在这里判死刑；确定性硬过滤仍由 L0 负责。
            hard_violation = False
    positive = positive_sum / max(positive_weight, 1e-9)
    penalty = min(1.0, negative_penalty)
    return GraphMatch(
        score=max(0.0, positive * (1.0 - penalty)),
        positive_score=positive,
        negative_penalty=penalty,
        hard_violation=hard_violation,
        groups=scores,
    )
