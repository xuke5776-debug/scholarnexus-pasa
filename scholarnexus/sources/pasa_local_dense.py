"""Offline local dense retrieval over a PaSa SentenceTransformer index.

Unlike :mod:`pasa_dense`, this source makes no embedding API request.  Both
the query encoder and the document vectors stay local, which makes it useful
as a reproducible *independent* admission channel alongside PaSa FTS.  The
builder records a normalized title+abstract matrix; retrieval therefore uses
exact blockwise cosine/inner-product search without an approximate-index
recall confound.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from ..schema import Paper
from .base import PaperSource


class PaSaLocalDenseSource(PaperSource):
    """Exact local MiniLM retrieval over a memory-mapped PaSa index.

    Loading SentenceTransformers is intentionally lazy.  A normal lightweight
    install can still construct a registry containing lexical PaSa sources;
    this source simply fails independently at first use if its optional dense
    environment/model is unavailable.  The standard ``PaperSource`` wrapper
    turns that failure into an empty channel and records it in the ledger.
    """

    name = "pasa_local_dense"
    cache_key_version = "native_score_v2"

    def __init__(self, index_dir: str, paper_db: str = "", model_path: str = "",
                 device: str = "cuda", search_device: str = "cpu", block_size: int = 8192,
                 query_batch_size: int = 1, query_adapter_path: str = "",
                 query_adapter_mix: float = 0.25, cache=None, ledger=None, **kw):
        super().__init__(cache, ledger)
        self.index_dir = Path(index_dir)
        manifest_path = self.index_dir / "manifest.json"
        vectors_path = self.index_dir / "vectors.f16.npy"
        records_path = self.index_dir / "papers.jsonl"
        if not all(path.is_file() for path in (manifest_path, vectors_path, records_path)):
            raise FileNotFoundError(f"incomplete local PaSa dense index: {self.index_dir}")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not self.manifest.get("normalized"):
            raise ValueError("local PaSa dense vectors must be normalized")
        self.model_path = Path(model_path or self.manifest.get("model_path") or "")
        if not self.model_path:
            raise ValueError("local PaSa dense index does not declare a model_path")
        self.device = str(device or self.manifest.get("device") or "cpu")
        self.vectors = np.load(vectors_path, mmap_mode="r")
        if self.vectors.ndim != 2 or self.vectors.dtype != np.float16:
            raise ValueError("local PaSa dense vectors must be a 2-D float16 matrix")
        self.records: list[dict[str, Any]] = []
        with records_path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                self.records.append({
                    "arxiv_id": str(row.get("arxiv_id") or ""),
                    "title": str(row.get("title") or ""),
                    "rowid": int(row["rowid"]) if row.get("rowid") is not None else None,
                })
        if len(self.records) != len(self.vectors):
            raise ValueError("local PaSa dense metadata/vector length mismatch")
        if any(not row["arxiv_id"] for row in self.records):
            raise ValueError("local PaSa dense metadata has an empty arXiv ID")
        self.paper_db = Path(paper_db) if paper_db else None
        self.block_size = max(256, int(block_size))
        self.query_batch_size = max(1, int(query_batch_size))
        self.query_adapter_path = (Path(query_adapter_path).resolve()
                                   if str(query_adapter_path or "").strip() else None)
        self.query_adapter_mix = min(1.0, max(0.0, float(query_adapter_mix)))
        if self.query_adapter_path is not None and not self.query_adapter_path.is_file():
            raise FileNotFoundError(f"local query adapter not found: {self.query_adapter_path}")
        self.search_device = str(search_device or "cpu").strip().lower()
        if self.search_device not in ("cpu", "cuda"):
            raise ValueError("local PaSa dense search_device must be 'cpu' or 'cuda'")
        self._model = None
        self._query_adapter = None
        self._model_lock = threading.RLock()
        self._gpu_vectors = None
        self._gpu_lock = threading.RLock()

    def close(self) -> None:
        with getattr(self, "_gpu_lock", threading.RLock()):
            # Do not retain a nearly-1GB float32 matrix after an engine exits;
            # otherwise a subsequent large reranker may OOM on a 4GB laptop
            # GPU.  ``torch`` is deliberately optional for CPU-only installs.
            self._gpu_vectors = None
            if getattr(self, "search_device", "cpu") == "cuda":
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
        with getattr(self, "_model_lock", threading.RLock()):
            self._query_adapter = None
        vectors = getattr(self, "vectors", None)
        mmap = getattr(vectors, "_mmap", None)
        if mmap is not None:
            mmap.close()

    def release_accelerators(self) -> None:
        """Free GPU-only dense runtime state while keeping the CPU index valid.

        A 4 GB GPU can execute exact MiniLM full-corpus search *or* a larger
        BGE cross-encoder safely, but retaining both model lifecycles and the
        0.87 GB dense matrix invites fragile allocator behaviour on Windows.
        This method is therefore narrower than :meth:`close`: it deliberately
        preserves the read-only memmap and metadata so the same source can
        re-encode a later query after its admission scorer has been released.
        """
        with getattr(self, "_model_lock", threading.RLock()):
            self._model = None
            self._query_adapter = None
        with getattr(self, "_gpu_lock", threading.RLock()):
            self._gpu_vectors = None
        try:
            import gc
            gc.collect()
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _load_model(self):
        with self._model_lock:
            if self._model is not None:
                return self._model
            if not self.model_path.is_dir():
                raise FileNotFoundError(f"local dense model not found: {self.model_path}")
            # This channel must never silently download weights at query time.
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(str(self.model_path), device=self.device,
                                        local_files_only=True)
            max_length = int(self.manifest.get("max_seq_length") or 128)
            model.max_seq_length = max(8, max_length)
            dimension = int(model.get_sentence_embedding_dimension())
            if dimension != int(self.vectors.shape[1]):
                raise ValueError(
                    f"query model dimension {dimension} != index dimension {self.vectors.shape[1]}")
            self._model = model
            return model

    def _embed_query(self, query: str) -> np.ndarray:
        model = self._load_model()
        # Model inference is serialised.  MultiProbe can issue several query
        # probes concurrently, but CUDA model calls from concurrent threads
        # are less deterministic and can oversubscribe a 4GB mobile GPU.
        with self._model_lock:
            vector = model.encode([query], batch_size=self.query_batch_size,
                                  normalize_embeddings=True, show_progress_bar=False,
                                  convert_to_numpy=True)
        value = np.asarray(vector, dtype=np.float32)
        if value.shape != (1, self.vectors.shape[1]):
            raise RuntimeError(f"unexpected local query vector shape: {value.shape}")
        q = value[0]
        if self.query_adapter_path is not None and self.query_adapter_mix > 0.0:
            q = self._apply_query_adapter(q)
        q /= max(float(np.linalg.norm(q)), 1e-12)
        return q

    def _apply_query_adapter(self, query: np.ndarray) -> np.ndarray:
        """Apply an optional train-only residual adapter on CPU.

        The adapter is deliberately opt-in and tiny.  Keeping it on CPU avoids
        retaining another CUDA module beside the SentenceTransformer encoder
        and the exact dense search buffers on 4 GB cards.
        """
        with self._model_lock:
            if self._query_adapter is None:
                try:
                    import torch
                    import torch.nn as nn
                except Exception as exc:  # pragma: no cover - optional path
                    raise RuntimeError("query adapter requires PyTorch") from exc
                bundle = torch.load(str(self.query_adapter_path), map_location="cpu",
                                    weights_only=False)
                if not isinstance(bundle, dict) or bundle.get("kind") != "PaSa residual query adapter v1":
                    raise ValueError("invalid PaSa query adapter artifact")
                dimension = int(bundle.get("dimension") or 0)
                hidden = int(bundle.get("hidden") or 0)
                if dimension != int(self.vectors.shape[1]) or hidden <= 0:
                    raise ValueError("query adapter dimension does not match dense index")
                network = nn.Sequential(nn.Linear(dimension, hidden), nn.Tanh(),
                                        nn.Linear(hidden, dimension, bias=False))
                state = bundle.get("state_dict")
                if not isinstance(state, dict):
                    raise ValueError("query adapter has no state_dict")
                network.load_state_dict(state, strict=True)
                network.eval()
                self._query_adapter = network
            import torch
            with torch.inference_mode():
                x = torch.from_numpy(np.asarray(query, dtype=np.float32)).view(1, -1)
                residual = self._query_adapter(x).numpy()[0].astype(np.float32, copy=False)
            adapted = np.asarray(query, dtype=np.float32) + self.query_adapter_mix * residual
            adapted /= max(float(np.linalg.norm(adapted)), 1e-12)
            return adapted

    def _top_positions(self, query_vector: np.ndarray, limit: int) -> List[int]:
        """Return exact top positions with deterministic score/position ties."""
        return [position for position, _score in
                self._top_positions_with_scores(query_vector, limit)]

    def _top_positions_with_scores(self, query_vector: np.ndarray, limit: int):
        """Return ``(position, cosine)`` pairs in deterministic rank order."""
        if self.search_device == "cuda":
            return self._top_positions_cuda_with_scores(query_vector, limit)
        count = len(self.vectors)
        keep = min(max(1, int(limit)), count)
        best_positions = np.empty(0, dtype=np.int64)
        best_scores = np.empty(0, dtype=np.float32)
        for start in range(0, count, self.block_size):
            block = np.asarray(self.vectors[start:start + self.block_size], dtype=np.float32)
            scores = block @ query_vector
            positions = np.arange(start, start + len(block), dtype=np.int64)
            if len(best_scores):
                scores = np.concatenate((best_scores, scores))
                positions = np.concatenate((best_positions, positions))
            if len(scores) > keep:
                chosen = np.argpartition(scores, -keep)[-keep:]
                scores, positions = scores[chosen], positions[chosen]
            best_scores, best_positions = scores, positions
        order = np.lexsort((best_positions, -best_scores))
        return [(int(position), float(score))
                for position, score in zip(best_positions[order[:keep]],
                                           best_scores[order[:keep]])]

    def _cuda_vectors(self):
        """Materialize the stored float16 index as one float32 CUDA matrix.

        Candidate search uses the *same stored float16 index values* as the
        CPU path, merely evaluated with a GPU float32 matvec.  The one-time
        upload is about 0.87GB for PaSa and makes a 568k-document exact scan
        practical for an 80-query audit on a 4GB GPU.  It is opt-in because a
        production process may instead reserve VRAM for a reranker.
        """
        with self._gpu_lock:
            if self._gpu_vectors is not None:
                return self._gpu_vectors
            try:
                import torch
            except Exception as exc:  # pragma: no cover - optional dependency path
                raise RuntimeError("CUDA dense search requires PyTorch") from exc
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA dense search requested but CUDA is unavailable")
            # ``np.asarray(..., dtype=float32)`` copies a read-only memmap to
            # writable host storage before one CUDA transfer; torch otherwise
            # warns about an unsafe non-writable ndarray view.
            host = np.asarray(self.vectors, dtype=np.float32)
            self._gpu_vectors = torch.from_numpy(host).to(device="cuda", dtype=torch.float32)
            return self._gpu_vectors

    def _top_positions_cuda(self, query_vector: np.ndarray, limit: int) -> List[int]:
        return [position for position, _score in
                self._top_positions_cuda_with_scores(query_vector, limit)]

    def _top_positions_cuda_with_scores(self, query_vector: np.ndarray, limit: int):
        """Float32 CUDA equivalent of the CPU exact cosine ranking.

        The index is streamed to the accelerator in bounded blocks.  Keeping
        the complete 568k-document matrix on a 4 GB GPU used to consume about
        0.87 GB in float32 before the encoder and reranker were accounted for,
        which made the otherwise exact CUDA path fail with OOM.  Each block is
        reduced to its local top-k immediately, so peak VRAM is proportional to
        ``block_size`` while the final CPU merge remains exact and deterministic.
        """
        try:
            import torch
        except Exception as exc:  # pragma: no cover - optional dependency path
            raise RuntimeError("CUDA dense search requires PyTorch") from exc
        count = len(self.vectors)
        keep = min(max(1, int(limit)), count)
        q = torch.as_tensor(np.asarray(query_vector, dtype=np.float32),
                            dtype=torch.float32, device="cuda")
        block_scores: list[np.ndarray] = []
        block_positions: list[np.ndarray] = []
        with torch.inference_mode():
            for start in range(0, count, self.block_size):
                stop = min(start + self.block_size, count)
                # Convert only one read-only memmap block at a time.  The
                # float32 host copy is bounded by block_size and is released
                # before the next transfer.
                host = np.asarray(self.vectors[start:stop], dtype=np.float32)
                matrix = torch.from_numpy(host).to(device="cuda", dtype=torch.float32)
                scores = torch.mv(matrix, q)
                local_keep = min(keep, stop - start)
                local_scores, local_positions = torch.topk(
                    scores, k=local_keep, largest=True, sorted=False)
                block_scores.append(local_scores.detach().cpu().numpy().astype(
                    np.float32, copy=False))
                block_positions.append((local_positions.detach().cpu().numpy().astype(
                    np.int64, copy=False) + start))
                del local_positions, local_scores, scores, matrix, host
        score_array = np.concatenate(block_scores) if block_scores else np.empty(0, dtype=np.float32)
        position_array = (np.concatenate(block_positions)
                          if block_positions else np.empty(0, dtype=np.int64))
        if len(score_array) > keep:
            chosen = np.argpartition(score_array, -keep)[-keep:]
            score_array, position_array = score_array[chosen], position_array[chosen]
        # Restore deterministic tie ordering after merging block-local top-k.
        order = np.lexsort((position_array, -score_array))
        return [(int(position), float(score))
                for position, score in zip(position_array[order[:keep]],
                                           score_array[order[:keep]])]

    def _hydrate(self, positions: List[int], scores: Dict[int, float] | None = None) -> List[Paper]:
        selected = [self.records[position] for position in positions]
        hydrated: Dict[str, tuple[str, str]] = {}
        if self.paper_db and self.paper_db.is_file() and selected:
            rowids = [row["rowid"] for row in selected if row["rowid"] is not None]
            con = sqlite3.connect(f"file:{self.paper_db.resolve()}?mode=ro", uri=True)
            try:
                for start in range(0, len(rowids), 800):
                    chunk = rowids[start:start + 800]
                    placeholders = ",".join("?" for _ in chunk)
                    rows = con.execute(
                        f"SELECT arxiv_id, title, abstract FROM papers WHERE rowid IN ({placeholders})",
                        chunk,
                    ).fetchall()
                    hydrated.update({str(arxiv_id): (title or "", abstract or "")
                                     for arxiv_id, title, abstract in rows})
            finally:
                con.close()
        out = []
        for position, row in zip(positions, selected):
            title, abstract = hydrated.get(row["arxiv_id"], (row["title"], ""))
            out.append(Paper(pid=f"arxiv:{row['arxiv_id']}", arxiv_id=row["arxiv_id"],
                             title=title, abstract=abstract, source=self.name,
                             retrieval_score=(None if scores is None else
                                              float(scores.get(position)))))
        return out

    def _search(self, query: str, limit: int,
                filters: Dict[str, Any]) -> List[Paper]:
        del filters  # metadata filters are not meaningful for this frozen corpus index
        scored = self._top_positions_with_scores(self._embed_query(query), limit)
        positions = [position for position, _score in scored]
        scores = {position: score for position, score in scored}
        return self._hydrate(positions, scores)
