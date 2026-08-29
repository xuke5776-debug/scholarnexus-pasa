"""OpenAlex：免 Key、覆盖全学科、自带引文图，作为主力元数据源。"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import requests

from ..schema import Paper
from ..utils import normalize_text, retry
from .base import PaperSource

API = "https://api.openalex.org"
FIELDS = ("id,doi,title,display_name,publication_year,cited_by_count,type,"
          "authorships,primary_location,abstract_inverted_index,referenced_works,"
          "concepts,ids,locations")


def _oa_id(url: str) -> str:
    return (url or "").rsplit("/", 1)[-1]


def _reconstruct_abstract(inv: Dict[str, List[int]] | None) -> str:
    if not inv:
        return ""
    pos: Dict[int, str] = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos)) if pos else ""


def _arxiv_id(work: Dict[str, Any]) -> str:
    """Return a stable arXiv identifier from every OpenAlex location/ID field.

    A work's primary location is often a DOI or publisher page even when the
    same OpenAlex record includes an arXiv preprint elsewhere.  PaSa's public
    gold labels are arXiv IDs, so examining only ``primary_location`` creates
    false negatives under strict evaluation.
    """
    values: List[str] = []
    ids = work.get("ids") or {}
    if isinstance(ids, dict):
        values.extend(str(v or "") for k, v in ids.items() if "arxiv" in str(k).lower())
    for loc in [work.get("primary_location")] + list(work.get("locations") or []):
        if isinstance(loc, dict):
            values.extend([str(loc.get("landing_page_url") or ""),
                           str(loc.get("pdf_url") or "")])
    for value in values:
        marker = "arxiv.org/abs/"
        if marker in value:
            return value.split(marker, 1)[1].split("?", 1)[0].split("#", 1)[0]
        marker = "arxiv.org/pdf/"
        if marker in value:
            return value.split(marker, 1)[1].split("?", 1)[0].split("#", 1)[0].removesuffix(".pdf")
        if "arxiv" in value.lower():
            tail = value.rsplit("/", 1)[-1]
            if tail:
                return tail.removeprefix("arXiv:").removeprefix("arxiv:").removesuffix(".pdf")
    return ""


def _to_paper(w: Dict[str, Any]) -> Paper:
    loc = (w.get("primary_location") or {}).get("source") or {}
    landing = (w.get("primary_location") or {}).get("landing_page_url") or ""
    arxiv = _arxiv_id(w)
    return Paper(
        pid="openalex:" + _oa_id(w.get("id", "")),
        title=normalize_text(w.get("title") or w.get("display_name") or ""),
        abstract=normalize_text(_reconstruct_abstract(w.get("abstract_inverted_index"))),
        year=w.get("publication_year"),
        venue=normalize_text(loc.get("display_name") or ""),
        authors=[a.get("author", {}).get("display_name", "")
                 for a in (w.get("authorships") or [])][:20],
        doi=(w.get("doi") or "").replace("https://doi.org/", ""),
        arxiv_id=arxiv,
        url=landing or w.get("id", ""),
        citation_count=w.get("cited_by_count") or 0,
        reference_ids=["openalex:" + _oa_id(x) for x in (w.get("referenced_works") or [])],
        fields=[c.get("display_name", "") for c in (w.get("concepts") or [])[:6]],
        source="openalex",
        doc_type=w.get("type") or "article",
    )


class OpenAlexSource(PaperSource):
    name = "openalex"
    supports_citations = True
    supports_references = True

    def __init__(self, cache=None, ledger=None, mailto: str = "",
                 timeout: int = 25, **kw):
        super().__init__(cache, ledger)
        self.mailto = mailto or os.environ.get("OPENALEX_MAILTO", "")
        self.timeout = timeout
        self.session = requests.Session()

    def _params(self, **kw) -> Dict[str, Any]:
        p = {"select": FIELDS}
        if self.mailto:
            p["mailto"] = self.mailto
        p.update(kw)
        return p

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        def _call():
            r = self.session.get(f"{API}{path}", params=params, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        return retry(_call, attempts=3)

    def _search(self, query: str, limit: int, filters: Dict[str, Any]) -> List[Paper]:
        flt = []
        if filters.get("year_min"):
            flt.append(f"from_publication_date:{int(filters['year_min'])}-01-01")
        if filters.get("year_max"):
            flt.append(f"to_publication_date:{int(filters['year_max'])}-12-31")
        if filters.get("doc_type"):
            flt.append(f"type:{filters['doc_type']}")
        params = self._params(search=query, per_page=min(limit, 50))
        if flt:
            params["filter"] = ",".join(flt)
        data = self._get("/works", params)
        return [_to_paper(w) for w in data.get("results", [])][:limit]

    def _references(self, pid: str, limit: int) -> List[Paper]:
        wid = pid.split(":", 1)[-1]
        data = self._get(f"/works/{wid}", self._params())
        refs = (data.get("referenced_works") or [])[:limit]
        if not refs:
            return []
        ids = "|".join(_oa_id(r) for r in refs)
        out = self._get("/works", self._params(filter=f"openalex_id:{ids}",
                                               per_page=min(limit, 50)))
        return [_to_paper(w) for w in out.get("results", [])]

    def _citations(self, pid: str, limit: int) -> List[Paper]:
        wid = pid.split(":", 1)[-1]
        data = self._get("/works", self._params(
            filter=f"cites:{wid}", per_page=min(limit, 50),
            sort="cited_by_count:desc"))
        return [_to_paper(w) for w in data.get("results", [])][:limit]
