"""本地语料源：离线复现、单测、以及「离线重放评测」。

它同时充当无网络环境下的完整检索后端：BM25 + 真实引文边。
把线上抓到的候选池冻结成 fixture 后，消融实验就能在**完全相同的候选池**上
对比不同判定/截断策略——这是让消融结论可信的前提。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..schema import Paper
from .base import PaperSource


class LocalCorpusSource(PaperSource):
    name = "local"
    supports_citations = True
    supports_references = True

    def __init__(self, path: str = "", papers: Optional[List[Paper]] = None,
                 cache=None, ledger=None, **kw):
        super().__init__(cache, ledger)
        self.papers: List[Paper] = []
        if path:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self.papers.append(Paper(**json.loads(line)))
        if papers:
            self.papers.extend(papers)
        self.by_id = {p.pid: p for p in self.papers}
        self._index = None
        self._build_citing()

    def _build_citing(self):
        for p in self.papers:
            p.citing_ids = []
        for p in self.papers:
            for r in p.reference_ids:
                tgt = self.by_id.get(r)
                if tgt is not None:
                    tgt.citing_ids.append(p.pid)

    def _ensure_index(self):
        if self._index is None:
            from ..retrieval.bm25 import BM25
            self._index = BM25([p.text() for p in self.papers])

    def _search(self, query: str, limit: int, filters: Dict[str, Any]) -> List[Paper]:
        self._ensure_index()
        out = []
        for idx, _s in self._index.search(query, top_k=limit * 4):
            p = self.papers[idx]
            if filters.get("year_min") and p.year and p.year < int(filters["year_min"]):
                continue
            if filters.get("year_max") and p.year and p.year > int(filters["year_max"]):
                continue
            if filters.get("venues") and p.venue.upper() not in \
                    [v.upper() for v in filters["venues"]]:
                continue
            out.append(self._clone(p))
            if len(out) >= limit:
                break
        return out

    def _references(self, pid: str, limit: int) -> List[Paper]:
        p = self.by_id.get(pid)
        return [] if not p else [self._clone(self.by_id[r])
                                 for r in p.reference_ids[:limit] if r in self.by_id]

    def _citations(self, pid: str, limit: int) -> List[Paper]:
        p = self.by_id.get(pid)
        return [] if not p else [self._clone(self.by_id[c])
                                 for c in p.citing_ids[:limit] if c in self.by_id]

    @staticmethod
    def _clone(paper: Paper) -> Paper:
        """候选必须按查询隔离；去重合并不得反向污染共享离线语料。"""
        return Paper(**paper.to_dict())

    def citation_contexts(self, pid: str, limit: int = 100) -> List[Dict[str, Any]]:
        """本地语料用「引用了它的论文的完整参考文献表」模拟共引上下文。"""
        out = []
        for c in self._citations(pid, limit):
            out.append({
                "contexts": [f"cited alongside {len(c.reference_ids)} refs"],
                "citingPaper": {"paperId": c.pid, "title": c.title, "year": c.year,
                                "publicationTypes": ["Review"] if c.is_review
                                else ["JournalArticle"]},
                "_reference_ids": c.reference_ids,
            })
        return out
