"""Full-corpus PaSa dense source backed by normalized BGE-M3 vectors."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import requests

from ..schema import Paper
from .base import PaperSource


class PaSaDenseSource(PaperSource):
    """Exact cosine retrieval over a memory-mapped PaSa embedding matrix.

    Only the query is sent to the embedding API.  Corpus vectors and returned
    paper metadata remain local.  Exact blockwise inner product is preferred
    over an approximate index for the first reproducible benchmark; an ANN
    backend can later replace ``_top_positions`` without changing semantics.
    """

    name = "pasa_dense"
    cache_key_version = "native_score_v2"
    API = "https://api.siliconflow.cn/v1/embeddings"

    def __init__(self, index_dir: str, paper_db: str = "",
                 model: str = "BAAI/bge-m3",
                 api_key_env: str = "SILICONFLOW_API_KEY",
                 block_size: int = 8192, timeout: int = 60,
                 cache=None, ledger=None, **kw):
        super().__init__(cache, ledger)
        self.index_dir = Path(index_dir)
        manifest_path = self.index_dir / "manifest.json"
        vectors_path = self.index_dir / "vectors.f16.npy"
        if not vectors_path.is_file():
            # Pilot/evaluation assets used float32 and the generic filename.
            vectors_path = self.index_dir / "vectors.npy"
        ids_path = self.index_dir / "papers.jsonl"
        if not manifest_path.is_file() or not vectors_path.is_file() or not ids_path.is_file():
            raise FileNotFoundError(f"incomplete PaSa dense index: {self.index_dir}")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.model = str(self.manifest.get("model") or model)
        self.vectors = np.load(vectors_path, mmap_mode="r")
        self.records = []
        with ids_path.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    row = json.loads(line)
                    self.records.append({"arxiv_id": str(row["arxiv_id"]),
                                         "title": str(row.get("title") or ""),
                                         "abstract": str(row.get("abstract") or ""),
                                         "rowid": (int(row["rowid"])
                                                   if row.get("rowid") is not None else None)})
        if len(self.records) != len(self.vectors):
            raise ValueError("PaSa dense metadata/vector length mismatch")
        if self.vectors.ndim != 2:
            raise ValueError("PaSa dense vectors must be a 2-D matrix")
        self.paper_db = Path(paper_db) if paper_db else None
        self.api_key = os.environ.get(api_key_env, "")
        self.block_size = max(256, int(block_size))
        self.timeout = max(1, int(timeout))
        self.session = requests.Session()

    def close(self) -> None:
        mmap = getattr(self.vectors, "_mmap", None)
        if mmap is not None:
            mmap.close()
        self.session.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _embed_query(self, query: str) -> np.ndarray:
        if not self.api_key:
            raise RuntimeError("PaSa dense query embedding key is not configured")
        response = self.session.post(
            self.API, timeout=self.timeout,
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
            json={"model": self.model, "input": [query]},
        )
        response.raise_for_status()
        data = response.json().get("data") or []
        if len(data) != 1:
            raise RuntimeError("query embedding response did not contain one vector")
        q = np.asarray(data[0]["embedding"], dtype=np.float32)
        if q.shape != (self.vectors.shape[1],):
            raise ValueError("query/corpus embedding dimension mismatch")
        q /= max(float(np.linalg.norm(q)), 1e-12)
        if self.ledger:
            self.ledger.add_api("embed_query::pasa_dense")
        return q

    def _top_positions(self, query_vector: np.ndarray, limit: int) -> List[int]:
        return [position for position, _score in
                self._top_positions_with_scores(query_vector, limit)]

    def _top_positions_with_scores(self, query_vector: np.ndarray, limit: int):
        """Return ``(position, cosine)`` pairs in deterministic rank order."""
        n = len(self.vectors)
        k = min(max(1, int(limit)), n)
        best_pos = np.empty(0, dtype=np.int64)
        best_scores = np.empty(0, dtype=np.float32)
        for start in range(0, n, self.block_size):
            block = np.asarray(self.vectors[start:start + self.block_size], dtype=np.float32)
            scores = block @ query_vector
            positions = np.arange(start, start + len(block), dtype=np.int64)
            if len(best_scores):
                scores = np.concatenate((best_scores, scores))
                positions = np.concatenate((best_pos, positions))
            if len(scores) > k:
                take = np.argpartition(scores, -k)[-k:]
                scores, positions = scores[take], positions[take]
            best_scores, best_pos = scores, positions
        order = np.lexsort((best_pos, -best_scores))
        return [(int(position), float(score))
                for position, score in zip(best_pos[order[:k]],
                                           best_scores[order[:k]])]

    def _hydrate(self, positions: List[int], scores: Dict[int, float] | None = None) -> List[Paper]:
        selected = [self.records[pos] for pos in positions]
        hydrated: Dict[str, tuple[str, str]] = {}
        if self.paper_db and self.paper_db.is_file() and selected:
            # ``arxiv_id`` is UNINDEXED in the FTS table and an IN lookup on it
            # scans the entire corpus.  Full-index metadata stores the original
            # SQLite rowid, which is an O(k log N) primary-key lookup.  Older
            # 10k pilots already carry abstracts and need no hydration.
            rowids = [row["rowid"] for row in selected if row["rowid"] is not None]
            con = sqlite3.connect(f"file:{self.paper_db.resolve()}?mode=ro", uri=True)
            try:
                for start in range(0, len(rowids), 800):
                    chunk = rowids[start:start + 800]
                    marks = ",".join("?" for _ in chunk)
                    rows = con.execute(
                        f"SELECT arxiv_id,title,abstract FROM papers WHERE rowid IN ({marks})",
                        chunk).fetchall()
                    hydrated.update({str(aid): (title or "", abstract or "")
                                     for aid, title, abstract in rows})
            finally:
                con.close()
        out = []
        for position, row in zip(positions, selected):
            title, abstract = hydrated.get(
                row["arxiv_id"], (row["title"], row["abstract"]))
            out.append(Paper(pid=f"arxiv:{row['arxiv_id']}", arxiv_id=row["arxiv_id"],
                             title=title, abstract=abstract, source=self.name,
                             retrieval_score=(None if scores is None else
                                              float(scores.get(position)))))
        return out

    def _search(self, query: str, limit: int,
                filters: Dict[str, Any]) -> List[Paper]:
        scored = self._top_positions_with_scores(self._embed_query(query), limit)
        positions = [position for position, _score in scored]
        scores = {position: score for position, score in scored}
        return self._hydrate(positions, scores)
