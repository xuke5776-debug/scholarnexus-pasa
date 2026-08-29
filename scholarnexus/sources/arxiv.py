"""arXiv：时效性通道，补齐最近数月尚未被索引的预印本。"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

import requests

from ..schema import Paper
from ..utils import normalize_text, retry
from .base import PaperSource

API = "http://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}


class ArxivSource(PaperSource):
    name = "arxiv"

    def __init__(self, cache=None, ledger=None, timeout: int = 25, **kw):
        super().__init__(cache, ledger)
        self.timeout = timeout
        self.session = requests.Session()

    def _search(self, query: str, limit: int, filters: Dict[str, Any]) -> List[Paper]:
        terms = [t for t in re.sub(r"[^\w\s]", " ", query).split() if t.isascii()]
        q = " AND ".join(f'all:"{t}"' for t in terms[:6]) or f"all:{query}"

        def _call():
            r = self.session.get(API, params={
                "search_query": q, "start": 0, "max_results": min(limit, 50),
                "sortBy": "relevance"}, timeout=self.timeout)
            r.raise_for_status()
            return r.text

        root = ET.fromstring(retry(_call, attempts=3))
        out: List[Paper] = []
        ymin = filters.get("year_min")
        for e in root.findall("a:entry", NS):
            aid = (e.findtext("a:id", "", NS) or "").rsplit("/", 1)[-1]
            pub = e.findtext("a:published", "", NS) or ""
            year = int(pub[:4]) if pub[:4].isdigit() else None
            if ymin and year and year < int(ymin):
                continue
            out.append(Paper(
                pid="arxiv:" + aid.split("v")[0],
                title=normalize_text(e.findtext("a:title", "", NS)),
                abstract=normalize_text(e.findtext("a:summary", "", NS)),
                year=year, venue="arXiv",
                authors=[a.findtext("a:name", "", NS)
                         for a in e.findall("a:author", NS)][:20],
                arxiv_id=aid.split("v")[0],
                url=f"https://arxiv.org/abs/{aid}", source="arxiv"))
        return out[:limit]
