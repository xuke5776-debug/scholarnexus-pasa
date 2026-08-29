"""向量化：商业 API / 本地服务 / 零依赖哈希 TF-IDF 三级链路。"""
from __future__ import annotations

import hashlib
import math
import os
from collections import Counter
from typing import List, Sequence

import numpy as np

from ..utils import ngrams, tokenize


class Embedder:
    dim = 0
    name = "base"

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        raise NotImplementedError


class HashingEmbedder(Embedder):
    """哈希技巧 + 子词二元组的稀疏向量，L2 归一化后当 dense 用。

    没有任何模型权重，但对学术标题/摘要这种术语驱动的文本效果稳定，
    且能作为「零成本 dense 通道」参与 RRF 融合与消融对照。
    """
    name = "hashing"

    def __init__(self, dim: int = 4096, use_bigrams: bool = True, **kw):
        self.dim = dim
        self.use_bigrams = use_bigrams
        self._idf: dict | None = None

    def fit_idf(self, corpus: Sequence[str]):
        df = Counter()
        for t in corpus:
            df.update(set(self._features(t)))
        n = max(1, len(corpus))
        self._idf = {f: math.log(1 + n / (1 + c)) for f, c in df.items()}
        return self

    def _features(self, text: str) -> List[str]:
        toks = tokenize(text)
        return toks + (ngrams(toks, 2) if self.use_bigrams else [])

    def _hash(self, f: str) -> int:
        return int(hashlib.md5(f.encode()).hexdigest()[:8], 16) % self.dim

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        M = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for f, c in Counter(self._features(t)).items():
                w = (1 + math.log(c)) * (self._idf.get(f, 1.0) if self._idf else 1.0)
                M[i, self._hash(f)] += w
        norms = np.linalg.norm(M, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return M / norms


class APIEmbedder(Embedder):
    """OpenAI 兼容 /embeddings 端点。商业 API 与本地 vLLM/TEI 共用。"""
    name = "api"

    def __init__(self, model: str, base_url: str, api_key_env: str = "OPENAI_API_KEY",
                 dim: int = 1024, batch: int = 32, timeout: int = 60, ledger=None):
        import requests
        self.model, self.base_url = model, base_url.rstrip("/")
        self.api_key = os.environ.get(api_key_env, "")
        self.dim, self.batch, self.timeout = dim, batch, timeout
        self.ledger = ledger
        self.session = requests.Session()
        self._fallback = HashingEmbedder(4096)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        vecs: List[List[float]] = []
        try:
            for i in range(0, len(texts), self.batch):
                chunk = list(texts[i:i + self.batch])
                r = self.session.post(f"{self.base_url}/embeddings", headers=headers,
                                      json={"model": self.model, "input": chunk},
                                      timeout=self.timeout)
                r.raise_for_status()
                vecs.extend(d["embedding"] for d in r.json()["data"])
                if self.ledger:
                    self.ledger.add_api("embed")
        except Exception:                                        # noqa: BLE001
            if self.ledger:
                self.ledger.mark("errors::embed")
                self.ledger.note("embed", "向量服务不可用，降级到哈希向量")
            return self._fallback.fit_idf(list(texts)).encode(texts)
        M = np.array(vecs, dtype=np.float32)
        norms = np.linalg.norm(M, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return M / norms


def build_embedder(cfg: dict, ledger=None) -> Embedder:
    cfg = cfg or {}
    if (cfg.get("backend") or "hashing") == "hashing":
        return HashingEmbedder(dim=cfg.get("dim", 4096))
    return APIEmbedder(model=cfg["model"], base_url=cfg["base_url"],
                       api_key_env=cfg.get("api_key_env", "OPENAI_API_KEY"),
                       dim=cfg.get("dim", 1024), ledger=ledger)
