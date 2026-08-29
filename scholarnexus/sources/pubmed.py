"""PubMed (E-utilities)：生物医学通道，用于验证跨学科泛化能力。"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Dict, List

import requests

from ..schema import Paper
from ..utils import normalize_text, retry
from .base import PaperSource

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedSource(PaperSource):
    name = "pubmed"

    def __init__(self, cache=None, ledger=None, timeout: int = 25,
                 email: str = "", **kw):
        super().__init__(cache, ledger)
        self.timeout, self.email = timeout, email
        self.session = requests.Session()

    def _search(self, query: str, limit: int, filters: Dict[str, Any]) -> List[Paper]:
        term = query
        if filters.get("year_min"):
            term += f" AND {int(filters['year_min'])}:3000[dp]"

        def _esearch():
            r = self.session.get(f"{BASE}/esearch.fcgi", params={
                "db": "pubmed", "term": term, "retmax": min(limit, 50),
                "retmode": "json", "email": self.email}, timeout=self.timeout)
            r.raise_for_status()
            return r.json()

        ids = retry(_esearch)["esearchresult"].get("idlist", [])
        if not ids:
            return []

        def _efetch():
            r = self.session.get(f"{BASE}/efetch.fcgi", params={
                "db": "pubmed", "id": ",".join(ids), "retmode": "xml",
                "email": self.email}, timeout=self.timeout)
            r.raise_for_status()
            return r.text

        root = ET.fromstring(retry(_efetch))
        out: List[Paper] = []
        for art in root.findall(".//PubmedArticle"):
            pmid = art.findtext(".//PMID", "")
            abst = " ".join(t.text or "" for t in art.findall(".//AbstractText"))
            year = art.findtext(".//PubDate/Year") or ""
            out.append(Paper(
                pid="pubmed:" + pmid,
                title=normalize_text(art.findtext(".//ArticleTitle") or ""),
                abstract=normalize_text(abst),
                year=int(year) if str(year).isdigit() else None,
                venue=normalize_text(art.findtext(".//Journal/Title") or ""),
                authors=[f"{a.findtext('ForeName','')} {a.findtext('LastName','')}".strip()
                         for a in art.findall(".//Author")][:20],
                doi=next((e.text for e in art.findall(".//ArticleId")
                          if e.get("IdType") == "doi"), "") or "",
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", source="pubmed"))
        return out
