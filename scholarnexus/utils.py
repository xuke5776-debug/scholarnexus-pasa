"""通用工具：文本归一化、分词、相似度、RRF 融合、限速重试。"""
from __future__ import annotations

import math
import re
import time
import unicodedata
from collections import Counter
from typing import Callable, Dict, Iterable, List, Sequence, TypeVar

T = TypeVar("T")

_STOP = set("""a an the of for on in to and or with without via using use used
by from at as is are be been that this these those we our their its it can may
towards toward through into over under between among about across new novel
approach approaches method methods model models framework paper papers study studies
propose proposed based do does how what which when where who why
could would should you your me my i us please provide give tell show find get
some any work works research focused focus focusing intersection related relevant
including include introduce list lists looking look want need like""".split())

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("\u2010", "-").replace("\u2019", "'")
    return re.sub(r"\s+", " ", s).strip()


def has_cjk(s: str) -> bool:
    return bool(_CJK_RE.search(s or ""))


def tokenize(s: str, drop_stop: bool = True) -> List[str]:
    """英文分词 + 中文按字二元组（避免引入 jieba 依赖，学术术语多为英文）。"""
    s = normalize_text(s).lower()
    toks = _TOKEN_RE.findall(s)
    if drop_stop:
        toks = [t for t in toks if t not in _STOP and len(t) > 1]
    cjk = _CJK_RE.findall(s)
    if len(cjk) >= 2:
        toks += ["".join(cjk[i:i + 2]) for i in range(len(cjk) - 1)]
    elif cjk:
        toks += cjk
    return toks


def ngrams(tokens: Sequence[str], n: int = 2) -> List[str]:
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def cosine_counter(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    num = sum(a[t] * b[t] for t in common)
    da = math.sqrt(sum(v * v for v in a.values()))
    db = math.sqrt(sum(v * v for v in b.values()))
    return num / (da * db) if da and db else 0.0


def title_similarity(t1: str, t2: str) -> float:
    """用于跨源实体消歧 / 版本合并。"""
    a, b = tokenize(t1, drop_stop=False), tokenize(t2, drop_stop=False)
    if not a or not b:
        return 0.0
    return jaccard(a, b) * 0.5 + jaccard(ngrams(a), ngrams(b)) * 0.5


def rrf_fuse(rank_lists: Dict[str, List[str]], k: int = 60,
             weights: Dict[str, float] | None = None) -> Dict[str, float]:
    """Reciprocal Rank Fusion：无需分数标定即可融合异构通道。"""
    weights = weights or {}
    scores: Dict[str, float] = {}
    for ch, lst in rank_lists.items():
        w = weights.get(ch, 1.0)
        for r, pid in enumerate(lst):
            scores[pid] = scores.get(pid, 0.0) + w / (k + r + 1)
    return scores


def minmax(d: Dict[str, float]) -> Dict[str, float]:
    if not d:
        return {}
    lo, hi = min(d.values()), max(d.values())
    if hi - lo < 1e-12:
        return {k: 0.5 for k in d}
    return {k: (v - lo) / (hi - lo) for k, v in d.items()}


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-min(x, 60)))
    e = math.exp(max(x, -60))
    return e / (1.0 + e)


def logit(p: float, eps: float = 1e-6) -> float:
    p = min(max(p, eps), 1 - eps)
    return math.log(p / (1 - p))


def retry(fn: Callable[[], T], attempts: int = 3, base_delay: float = 0.6,
          exceptions=(Exception,)) -> T:
    last = None
    for i in range(attempts):
        try:
            return fn()
        except exceptions as e:          # noqa: PERF203
            last = e
            if i < attempts - 1:
                time.sleep(base_delay * (2 ** i))
    raise last


def chunked(seq: Sequence[T], n: int) -> List[Sequence[T]]:
    return [seq[i:i + n] for i in range(0, len(seq), n)]


def approx_tokens(text: str) -> int:
    """粗略 token 估计：英文 ~4 字符/token，中文 ~1.5 字符/token。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return int(cjk / 1.5 + other / 4) + 1
