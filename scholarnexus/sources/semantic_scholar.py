"""Semantic Scholar Graph API：语义检索质量最好，且提供引文上下文。"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import requests

from ..schema import Paper
from ..utils import normalize_text, retry
from .base import PaperSource, cache_key

API = "https://api.semanticscholar.org/graph/v1"
PAPER_FIELDS = ("paperId,title,abstract,year,venue,authors,externalIds,url,"
                "citationCount,fieldsOfStudy,publicationTypes")


def _to_paper(d: Dict[str, Any]) -> Paper:
    ext = d.get("externalIds") or {}
    ptypes = d.get("publicationTypes") or []
    return Paper(
        pid="s2:" + (d.get("paperId") or ""),
        title=normalize_text(d.get("title") or ""),
        abstract=normalize_text(d.get("abstract") or ""),
        year=d.get("year"),
        venue=normalize_text(d.get("venue") or ""),
        authors=[a.get("name", "") for a in (d.get("authors") or [])][:20],
        doi=ext.get("DOI", "") or "",
        arxiv_id=ext.get("ArXiv", "") or "",
        url=d.get("url", "") or "",
        citation_count=d.get("citationCount") or 0,
        fields=d.get("fieldsOfStudy") or [],
        source="s2",
        doc_type=("review" if "Review" in ptypes else "article"),
    )


class SemanticScholarSource(PaperSource):
    name = "s2"
    supports_citations = True
    supports_references = True

    def __init__(self, cache=None, ledger=None, api_key_env: str = "S2_API_KEY",
                 timeout: int = 30, **kw):
        super().__init__(cache, ledger)
        self.api_key = os.environ.get(api_key_env, "")
        self.timeout = timeout
        self.session = requests.Session()

    def _headers(self):
        return {"x-api-key": self.api_key} if self.api_key else {}

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        def _call():
            r = self.session.get(f"{API}{path}", params=params,
                                 headers=self._headers(), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        return retry(_call, attempts=3, base_delay=1.2)

    def _search(self, query: str, limit: int, filters: Dict[str, Any]) -> List[Paper]:
        params = {"query": query, "limit": min(limit, 100), "fields": PAPER_FIELDS}
        if filters.get("year_min") or filters.get("year_max"):
            params["year"] = f"{filters.get('year_min','')}-{filters.get('year_max','')}".strip("-")
        if filters.get("venues"):
            params["venue"] = ",".join(filters["venues"])
        data = self._get("/paper/search", params)
        return [_to_paper(d) for d in data.get("data", [])][:limit]

    def _references(self, pid: str, limit: int) -> List[Paper]:
        sid = pid.split(":", 1)[-1]
        data = self._get(f"/paper/{sid}/references",
                         {"limit": min(limit, 100), "fields": PAPER_FIELDS})
        return [_to_paper(x["citedPaper"]) for x in data.get("data", [])
                if x.get("citedPaper")]

    def _citations(self, pid: str, limit: int) -> List[Paper]:
        sid = pid.split(":", 1)[-1]
        data = self._get(f"/paper/{sid}/citations",
                         {"limit": min(limit, 100), "fields": PAPER_FIELDS})
        return [_to_paper(x["citingPaper"]) for x in data.get("data", [])
                if x.get("citingPaper")]

    def citation_contexts(self, pid: str, limit: int = 100) -> List[Dict[str, Any]]:
        """引文上下文：判断候选是否与种子被**同一段综述文字共同引用**。

        这是对齐评测金标准构造过程的关键信号（金标准由 Related Work 段落的
        被引文献反推而来），详见 core/cocite.py。
        """
        k = cache_key(self.name, "ctx", pid, limit)
        if self.cache:
            hit = self.cache.get(k)
            if hit is not None:
                if self.ledger:
                    self.ledger.add_api("cocite::s2", cache_hit=True)
                return hit
        sid = pid.split(":", 1)[-1]
        try:
            data = self._get(f"/paper/{sid}/citations",
                             {"limit": min(limit, 100),
                              "fields": "contexts,intents,isInfluential,"
                                        "citingPaper.paperId,citingPaper.title,"
                                        "citingPaper.year,citingPaper.publicationTypes"})
        except Exception:                                        # noqa: BLE001
            return []
        if self.ledger:
            self.ledger.add_api("cocite::s2")
        out = data.get("data", [])
        if self.cache:
            self.cache.set(k, out, ns=self.name)
        return out
