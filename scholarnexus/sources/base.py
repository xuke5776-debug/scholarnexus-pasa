"""学术数据源抽象。所有源统一返回 Paper 列表，并经缓存与账本计费。

失败语义：单源异常**不抛出**，返回空列表并在账本中标注。多源并行时，
一个源挂掉不应该让整次查询失败——学术 API 的限流与偶发 5xx 是常态。
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from ..schema import Paper


def cache_key(*parts: Any) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


class PaperSource:
    name = "base"
    supports_citations = False
    supports_references = False

    def __init__(self, cache=None, ledger=None, **kw):
        self.cache = cache
        self.ledger = ledger
        self.errors = 0

    # ---- 子类实现 ----
    def _search(self, query: str, limit: int, filters: Dict[str, Any]) -> List[Paper]:
        raise NotImplementedError

    def _references(self, pid: str, limit: int) -> List[Paper]:
        return []

    def _citations(self, pid: str, limit: int) -> List[Paper]:
        return []

    # ---- 带缓存的对外接口 ----
    def search(self, query: str, limit: int = 20,
               filters: Optional[Dict[str, Any]] = None) -> List[Paper]:
        filters = filters or {}
        version = getattr(self, "cache_key_version", "")
        key_parts = (self.name, version, "search", query, limit,
                     sorted(filters.items())) if version else (
                         self.name, "search", query, limit, sorted(filters.items()))
        k = cache_key(*key_parts)
        if self.cache:
            hit = self.cache.get(k)
            if hit is not None:
                if self.ledger:
                    self.ledger.add_api(f"search::{self.name}", cache_hit=True)
                return [Paper(**p) for p in hit]
        try:
            papers = self._search(query, limit, filters)
        except Exception as e:                                   # noqa: BLE001
            self.errors += 1
            if self.ledger:
                self.ledger.mark(f"errors::{self.name}")
                self.ledger.note(f"search::{self.name}",
                                 f"检索失败已跳过: {type(e).__name__}")
            return []
        if self.ledger:
            self.ledger.add_api(f"search::{self.name}")
        if self.cache:
            self.cache.set(k, [p.to_dict() for p in papers], ns=self.name)
        return papers

    def references(self, pid: str, limit: int = 60) -> List[Paper]:
        return self._cached_edge("references", pid, limit)

    def citations(self, pid: str, limit: int = 60) -> List[Paper]:
        return self._cached_edge("citations", pid, limit)

    def _cached_edge(self, kind: str, pid: str, limit: int) -> List[Paper]:
        k = cache_key(self.name, kind, pid, limit)
        if self.cache:
            hit = self.cache.get(k)
            if hit is not None:
                if self.ledger:
                    self.ledger.add_api(f"{kind}::{self.name}", cache_hit=True)
                return [Paper(**p) for p in hit]
        try:
            fn = self._references if kind == "references" else self._citations
            papers = fn(pid, limit)
        except Exception:                                        # noqa: BLE001
            self.errors += 1
            if self.ledger:
                self.ledger.mark(f"errors::{self.name}")
            return []
        if self.ledger:
            self.ledger.add_api(f"{kind}::{self.name}")
        if self.cache:
            self.cache.set(k, [p.to_dict() for p in papers], ns=self.name)
        return papers


class SourceRegistry:
    def __init__(self):
        self._sources: Dict[str, PaperSource] = {}
        # Optional sources may be unavailable in an offline install, but the
        # exact construction error must remain observable for reproducible
        # evaluation instead of becoming a misleading "not registered" error.
        self.initialization_errors: Dict[str, str] = {}

    def register(self, src: PaperSource):
        self._sources[src.name] = src
        return self

    def get(self, name: str) -> Optional[PaperSource]:
        return self._sources.get(name)

    def all(self) -> List[PaperSource]:
        return list(self._sources.values())

    def with_citations(self) -> List[PaperSource]:
        return [s for s in self._sources.values() if s.supports_citations]

    def __contains__(self, name):
        return name in self._sources

    def __len__(self):
        return len(self._sources)


def build_registry(cfg: Dict[str, Any], cache=None, ledger=None) -> SourceRegistry:
    """按配置装配数据源。任何一个源导入/构造失败都只跳过它本身。"""
    import os
    reg = SourceRegistry()
    cfg = cfg or {}

    def record_init_error(name: str, exc: Exception) -> None:
        message = f"{type(exc).__name__}: {exc}".strip()
        reg.initialization_errors[name] = message[:500]
        if ledger:
            ledger.mark(f"source_init_errors::{name}")
            ledger.note("source_registry", f"{name} 构造失败: {message[:240]}")

    if (cfg.get("openalex") or {}).get("enabled"):
        try:
            from .openalex import OpenAlexSource
            reg.register(OpenAlexSource(
                cache=cache, ledger=ledger,
                mailto=os.environ.get(cfg["openalex"].get("mailto_env", ""), "")))
        except Exception as exc:                                # noqa: BLE001
            record_init_error("openalex", exc)
    if (cfg.get("s2") or {}).get("enabled"):
        try:
            from .semantic_scholar import SemanticScholarSource
            reg.register(SemanticScholarSource(
                cache=cache, ledger=ledger,
                api_key_env=cfg["s2"].get("api_key_env", "S2_API_KEY")))
        except Exception as exc:                                # noqa: BLE001
            record_init_error("s2", exc)
    if (cfg.get("arxiv") or {}).get("enabled"):
        try:
            from .arxiv import ArxivSource
            reg.register(ArxivSource(cache=cache, ledger=ledger))
        except Exception as exc:                                # noqa: BLE001
            record_init_error("arxiv", exc)
    if (cfg.get("pubmed") or {}).get("enabled"):
        try:
            from .pubmed import PubMedSource
            reg.register(PubMedSource(cache=cache, ledger=ledger,
                                      email=cfg["pubmed"].get("email", "")))
        except Exception as exc:                                # noqa: BLE001
            record_init_error("pubmed", exc)
    if (cfg.get("local") or {}).get("enabled"):
        try:
            from .local_corpus import LocalCorpusSource
            reg.register(LocalCorpusSource(path=cfg["local"].get("path", ""),
                                           cache=None, ledger=ledger))
        except Exception as exc:                                # noqa: BLE001
            record_init_error("local", exc)
    if (cfg.get("pasa") or {}).get("enabled"):
        try:
            from .pasa_corpus import PaSaCorpusSource
            reg.register(PaSaCorpusSource(index_path=cfg["pasa"].get("index_path", ""),
                                          paper_zip=cfg["pasa"].get("paper_zip", ""),
                                          id_map=cfg["pasa"].get("id_map", ""),
                                          reference_hydrate_limit=cfg["pasa"].get("reference_hydrate_limit", 12),
                                          section_selector_path=cfg["pasa"].get("section_selector_path", ""),
                                          section_selector_min_score=cfg["pasa"].get("section_selector_min_score", 0.0),
                                          section_cited_title_weight=cfg["pasa"].get("section_cited_title_weight", 0.0),
                                          section_cited_title_top_k=cfg["pasa"].get("section_cited_title_top_k", 8),
                                          max_search_limit=cfg["pasa"].get("max_search_limit", 2000),
                                          cache=cache, ledger=ledger))
        except Exception as exc:                                # noqa: BLE001
            record_init_error("pasa", exc)
    if (cfg.get("pasa_dense") or {}).get("enabled"):
        try:
            from .pasa_dense import PaSaDenseSource
            dense_cfg = cfg["pasa_dense"]
            reg.register(PaSaDenseSource(
                index_dir=dense_cfg.get("index_dir", ""),
                paper_db=dense_cfg.get("paper_db", ""),
                model=dense_cfg.get("model", "BAAI/bge-m3"),
                api_key_env=dense_cfg.get("api_key_env", "SILICONFLOW_API_KEY"),
                block_size=dense_cfg.get("block_size", 8192),
                timeout=dense_cfg.get("timeout", 60), cache=cache, ledger=ledger))
        except Exception as exc:                                # noqa: BLE001
            record_init_error("pasa_dense", exc)
    if (cfg.get("pasa_local_dense") or {}).get("enabled"):
        try:
            from .pasa_local_dense import PaSaLocalDenseSource
            local_dense_cfg = cfg["pasa_local_dense"]
            reg.register(PaSaLocalDenseSource(
                index_dir=local_dense_cfg.get("index_dir", ""),
                paper_db=local_dense_cfg.get("paper_db", ""),
                model_path=local_dense_cfg.get("model_path", ""),
                device=local_dense_cfg.get("device", "cuda"),
                search_device=local_dense_cfg.get("search_device", "cpu"),
                block_size=local_dense_cfg.get("block_size", 8192),
                query_batch_size=local_dense_cfg.get("query_batch_size", 1),
                query_adapter_path=local_dense_cfg.get("query_adapter_path", ""),
                query_adapter_mix=local_dense_cfg.get("query_adapter_mix", 0.25),
                cache=cache, ledger=ledger))
        except Exception as exc:                                # noqa: BLE001
            record_init_error("pasa_local_dense", exc)
    return reg
