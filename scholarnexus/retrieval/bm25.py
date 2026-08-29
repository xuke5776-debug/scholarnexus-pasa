"""零依赖 BM25（Okapi）。用于本地重排与离线语料检索。"""
from __future__ import annotations

import math
from collections import Counter
from typing import List, Sequence, Tuple

from ..utils import tokenize


class BM25:
    def __init__(self, docs: Sequence[str], k1: float = 1.2, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [tokenize(d) for d in docs]
        self.N = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / max(1, self.N)
        self.tf: List[Counter] = [Counter(d) for d in self.docs]
        df = Counter()
        for d in self.docs:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5))
                    for t, n in df.items()}

    def score(self, query_tokens: Sequence[str], i: int) -> float:
        tf, dl = self.tf[i], len(self.docs[i])
        s = 0.0
        for t in query_tokens:
            f = tf.get(t, 0)
            if not f:
                continue
            denom = f + self.k1 * (1 - self.b + self.b * dl / max(1e-9, self.avgdl))
            s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / denom
        return s

    def search(self, query: str, top_k: int = 50) -> List[Tuple[int, float]]:
        qt = tokenize(query)
        scores = [(i, self.score(qt, i)) for i in range(self.N)]
        scores = [x for x in scores if x[1] > 0]
        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]
