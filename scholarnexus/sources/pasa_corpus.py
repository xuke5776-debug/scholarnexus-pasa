"""PaSa 论文库的只读 FTS 候选源。

PaSa 的 AutoScholarQuery 问题多由 Related Work 的语义改写得到；只依赖在线
关键词检索往往连正确论文都召回不到。这个源使用由官方 ``cs_paper_2nd.zip``
构建的 SQLite FTS5 索引做本地候选召回。它不读取金标、不依赖 test 标签，因而
可用于 dev 调参与 test 盲测。
"""
from __future__ import annotations

import re
import sqlite3
import json
import threading
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

from ..schema import Paper
from ..utils import rrf_fuse
from .base import PaperSource, cache_key


_STOP = {"a", "an", "can", "could", "you", "tell", "list", "some", "papers",
         "paper", "works", "work", "about", "there", "any", "that", "the",
         "and", "or", "for", "with", "without", "are", "which", "what",
         "have", "has", "been", "from", "into", "using", "use", "used",
         "in", "on", "of", "to", "by", "we", "do", "does", "discuss"}

# PaSa 的 query 多来自 Related Work 语义改写；因此在无 LLM crawler 的可复现
# 回退路径下，把“related work/background/prior work”作为弱先验，而不是把整篇
# 论文的每个 section 都展开。它只在 section 标题与 query 没有词面重叠时介入，
# 不能替代真正的 query-section 匹配。
_SECTION_PRIOR = {
    "related work": 0.85,
    "prior work": 0.85,
    "literature review": 0.85,
    "background": 0.45,
    "introduction": 0.20,
}


def _query_terms(query: str, limit: int = 18) -> List[str]:
    terms = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}|[\u4e00-\u9fff]{2,}", query)
    out: List[str] = []
    for raw in terms:
        term = raw.lower().replace('"', "")
        if term in _STOP or term in out:
            continue
        out.append(term)
        if len(out) >= limit:
            break
    return out


def _fts_query(query: str, field: str = "abstract") -> str:
    """把自然语言转成安全的 OR 检索式；FTS 语法字符不得进入查询。"""
    terms = _query_terms(query)
    prefix = f"{field}:" if field else ""
    return " OR ".join(prefix + '"' + t.replace('"', '') + '"' for t in terms)


def _fts_queries(query: str) -> Dict[str, str]:
    """Independent lexical views used as separate RRF channels.

    PaSa questions are paraphrases of related-work prose.  Abstract-only FTS
    misses named methods, while title-only FTS misses conceptual descriptions;
    keeping the views separate preserves both recall mechanisms and lets RRF
    reward papers found by more than one view.
    """
    terms = _query_terms(query)
    if not terms:
        return {}
    quoted = ['"' + t + '"' for t in terms]
    return {
        "abstract": " OR ".join("abstract:" + t for t in quoted),
        "title_abstract": " OR ".join(
            f"(title:{t} OR abstract:{t})" for t in quoted),
        "all_fields": " OR ".join(quoted),
    }


def _fts_channel_specs(query: str, profile: str) -> Dict[str, Tuple[str, Tuple[float, float, float]]]:
    """Return reproducible FTS channels and their BM25F-style field weights.

    ``legacy`` preserves the three historical views byte-for-byte.  The
    opt-in ``multifield_v1`` profile adds two *ranking* views over the same
    query-document match set: one favors title terms (named methods and
    datasets), while the other favors abstract terms (paraphrased concepts).
    This mirrors the multi-field first-stage retrieval used by PyTerrier and
    LitSearch without introducing a second index or an online dependency.

    The profile is intentionally selected in source configuration rather than
    inferred from a query.  It can therefore be evaluated as one frozen
    system and switched off without changing the corpus.
    """
    views = _fts_queries(query)
    if profile not in {"legacy", "multifield_v1"}:
        raise ValueError(f"unknown PaSa lexical profile: {profile}")
    # FTS5 columns are arXiv ID (unindexed), title, abstract.
    specs = {
        name: (match, (0.0, 3.0, 1.0))
        for name, match in views.items()
    }
    if profile == "multifield_v1" and "title_abstract" in views:
        broad = views["title_abstract"]
        specs.update({
            "title_focus": (broad, (0.0, 8.0, 1.0)),
            "abstract_focus": (broad, (0.0, 1.0, 3.0)),
        })
    return specs


def _title_key(title: str) -> str:
    return "".join(ch.lower() for ch in str(title) if ch.isalpha())


def _section_score(section: str, query: str) -> float:
    """给 PaSa archive 的 section 标题做保守的 query 匹配评分。"""
    heading = str(section or "").lower()
    h_terms = set(_query_terms(heading, limit=30))
    q_terms = set(_query_terms(query, limit=30))
    # 标题中的数字（"2 Related Work"）不携带检索语义；有交集时以覆盖为主。
    lexical = len(h_terms & q_terms) / max(1, len(h_terms))
    prior = max((v for phrase, v in _SECTION_PRIOR.items() if phrase in heading),
                default=0.0)
    return 2.0 * lexical + prior


class PaSaCorpusSource(PaperSource):
    name = "pasa"

    # ``sections`` in PaSa's paper archive contains section-wise cited-paper
    # titles.  It is a local, reproducible counterpart to the official PaSa
    # reference expansion, and is especially valuable when a related-work
    # query shares little vocabulary with its target paper's abstract.
    supports_citations = True

    def __init__(self, index_path: str = "", paper_zip: str = "",
                 id_map: str = "", reference_hydrate_limit: int = 12,
                 section_selector_path: str = "", section_selector_min_score: float = 0.0,
                 section_cited_title_weight: float = 0.0,
                 section_cited_title_top_k: int = 8,
                 section_dynamic_second_margin: float = -1.0,
                 section_dynamic_second_min_score: float = 2.0,
                 lexical_profile: str = "legacy",
                 max_search_limit: int = 2000,
                 cache=None, ledger=None, **kw):
        super().__init__(cache, ledger)
        self.index_path = Path(index_path)
        if not self.index_path.is_file():
            raise FileNotFoundError(f"PaSa FTS index not found: {self.index_path}")
        self.paper_zip = Path(paper_zip) if paper_zip else None
        self.id_map = Path(id_map) if id_map else None
        self.reference_hydrate_limit = max(0, int(reference_hydrate_limit))
        self.section_selector_path = Path(section_selector_path) if section_selector_path else None
        self.section_selector_min_score = max(0.0, min(1.0, float(section_selector_min_score)))
        # Section text is not distributed in the official archive, but its
        # cited-paper title set is.  This optional blend is 0 by default so old
        # configs retain heading-only behaviour.  A positive value blends the
        # Crawler-SFT heading score with query-to-cited-title MaxSim/SoftTopK.
        self.section_cited_title_weight = max(0.0, min(1.0, float(section_cited_title_weight)))
        self.section_cited_title_top_k = max(1, int(section_cited_title_top_k))
        # A negative margin disables dynamic section count and preserves the
        # historical fixed Top-N policy.  When enabled, Top-1 always expands;
        # Top-2 expands only for a close score tie or a genuinely high second
        # score.  This is candidate-control, not a relevance bonus.
        self.section_dynamic_second_margin = float(section_dynamic_second_margin)
        self.section_dynamic_second_min_score = float(section_dynamic_second_min_score)
        self.lexical_profile = str(lexical_profile or "legacy").strip().lower()
        if self.lexical_profile not in {"legacy", "multifield_v1"}:
            raise ValueError(
                "PaSa lexical_profile must be 'legacy' or 'multifield_v1'")
        self._section_selector = None
        self._section_selector_token = "heuristic"
        if self.section_selector_path:
            try:
                import joblib
                from ..section_selector import make_features
                bundle = joblib.load(self.section_selector_path)
                if not all(key in bundle for key in ("word_vectorizer", "char_vectorizer", "model")):
                    raise ValueError("not a PaSa Crawler section-selector bundle")
                self._section_selector = (bundle["word_vectorizer"],
                                          bundle["char_vectorizer"], bundle["model"],
                                          make_features)
                stamp = self.section_selector_path.stat().st_mtime_ns
                self._section_selector_token = f"crawler_selector:{self.section_selector_path}:{stamp}"
            except Exception:
                # Section expansion remains available without an ML artifact;
                # failure must never silently turn the whole PaSa source off.
                self._section_selector = None
                if self.ledger:
                    self.ledger.mark("errors::pasa_section_selector")
        self.max_search_limit = max(1, int(max_search_limit))
        self._zip_lock = threading.RLock()
        self._zip = None
        self._id_to_title: Dict[str, str] = {}
        self._title_to_ids: Dict[str, List[str]] = {}
        if self.paper_zip and self.id_map and self.paper_zip.is_file() and self.id_map.is_file():
            raw = json.loads(self.id_map.read_text(encoding="utf-8"))
            self._id_to_title = {str(k).split("v")[0]: str(v) for k, v in raw.items()}
            for aid, title in self._id_to_title.items():
                self._title_to_ids.setdefault(_title_key(title), []).append(aid)
            # Parsing the 2.5 GiB archive's central directory once is costly;
            # doing it once per citation seed made a single query take minutes.
            # ZipFile reads are protected because citation seeds run in a pool.
            self._zip = zipfile.ZipFile(self.paper_zip)

    def close(self) -> None:
        with self._zip_lock:
            if self._zip is not None:
                self._zip.close()
                self._zip = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _archive_json(self, key: str) -> Dict[str, Any]:
        if self._zip is None:
            raise FileNotFoundError("PaSa paper archive is not configured")
        with self._zip_lock:
            return json.loads(self._zip.read(key).decode("utf-8"))

    @staticmethod
    def _to_papers(rows: Sequence[Tuple[str, str, str]]) -> List[Paper]:
        return [Paper(pid=f"arxiv:{arxiv_id}", arxiv_id=arxiv_id,
                      title=title or "", abstract=abstract or "", source="pasa")
                for arxiv_id, title, abstract in rows]

    def _run_match(self, con: sqlite3.Connection, match: str, limit: int,
                   bm25_weights: Tuple[float, float, float] = (0.0, 3.0, 1.0)) -> List[Paper]:
        rows = con.execute(
            "SELECT arxiv_id, title, abstract FROM papers "
            "WHERE papers MATCH ? "
            "ORDER BY bm25(papers, ?, ?, ?) LIMIT ?",
            (match, *bm25_weights, min(max(1, int(limit)), self.max_search_limit)),
        ).fetchall()
        return self._to_papers(rows)

    def search_channels(self, query: str, limit: int = 20,
                        filters: Dict[str, Any] | None = None) -> Dict[str, List[Paper]]:
        """Return separately ranked PaSa lexical channels for MultiProbe."""
        filters = filters or {}
        specs = _fts_channel_specs(query, self.lexical_profile)
        if not specs:
            return {}
        result: Dict[str, List[Paper]] = {}
        # sqlite3 的连接上下文只负责提交/回滚，并不保证 close；在 Windows 上
        # 会因此长期占用索引文件，影响索引重建和临时评测清理。
        con = sqlite3.connect(f"file:{self.index_path}?mode=ro", uri=True)
        try:
            for channel, (match, bm25_weights) in specs.items():
                key = cache_key(self.name, "search_channel", channel, query,
                                limit, self.lexical_profile, bm25_weights,
                                sorted(filters.items()))
                cached = self.cache.get(key) if self.cache else None
                if cached is not None:
                    result[channel] = [Paper(**p) for p in cached]
                    if self.ledger:
                        self.ledger.add_api(f"search::pasa::{channel}", cache_hit=True)
                    continue
                try:
                    papers = self._run_match(con, match, limit, bm25_weights)
                except Exception as exc:  # one view must not erase the others
                    papers = []
                    self.errors += 1
                    if self.ledger:
                        self.ledger.mark(f"errors::pasa::{channel}")
                        self.ledger.note(f"search::pasa::{channel}",
                                         f"检索失败已跳过: {type(exc).__name__}")
                result[channel] = papers
                if self.ledger:
                    self.ledger.add_api(f"search::pasa::{channel}")
                if self.cache:
                    self.cache.set(key, [p.to_dict() for p in papers], ns=self.name)
        finally:
            con.close()
        return result

    def _search(self, query: str, limit: int, filters: Dict[str, Any]) -> List[Paper]:
        """Compatibility path: fuse all local lexical views with RRF."""
        channels = self.search_channels(query, limit, filters)
        if not channels:
            return []
        by_pid = {p.pid: p for papers in channels.values() for p in papers}
        scores = rrf_fuse({ch: [p.pid for p in papers]
                           for ch, papers in channels.items()}, k=60)
        ranked = sorted(scores, key=lambda pid: (-scores[pid], pid))[:limit]
        return [by_pid[pid] for pid in ranked]

    def _paper_by_title(self, title: str, aid: str) -> Paper:
        """Load title/abstract directly from the official archive when present."""
        abstract = ""
        if self._zip is not None:
            try:
                raw = self._archive_json(_title_key(title))
                abstract = str(raw.get("abstract") or "").replace("\n", " ")
            except Exception:
                pass
        return Paper(pid=f"arxiv:{aid}", arxiv_id=aid, title=title,
                     abstract=abstract, source="pasa")

    def _references(self, pid: str, limit: int) -> List[Paper]:
        """Expand one paper through PaSa's archived section/reference titles.

        This never consults benchmark labels.  A reference title is accepted
        only when it resolves through the official ``id2paper.json`` map.
        """
        if self._zip is None or not self._id_to_title or not self._title_to_ids:
            return []
        aid = str(pid).split(":", 1)[-1]
        title = self._id_to_title.get(re.sub(r"v\d+$", "", aid, flags=re.I))
        if not title:
            return []
        try:
            # Keep discovery + bounded hydration under one re-entrant lock so
            # concurrent seeds cannot seek the shared ZipFile simultaneously.
            with self._zip_lock:
                row = json.loads(self._zip.read(_title_key(title)).decode("utf-8"))
                sections = row.get("sections") or {}
                values = sections.values() if isinstance(sections, dict) else []
                titles: List[str] = []
                for refs in values:
                    if isinstance(refs, list):
                        titles.extend(str(v) for v in refs)
                out: List[Paper] = []
                seen = set()
                for ref_title in titles:
                    for ref_id in self._title_to_ids.get(_title_key(ref_title), []):
                        if ref_id == aid or ref_id in seen:
                            continue
                        seen.add(ref_id)
                        abstract = ""
                        if len(out) < self.reference_hydrate_limit:
                            try:
                                ref_row = json.loads(self._zip.read(
                                    _title_key(self._id_to_title[ref_id])).decode("utf-8"))
                                abstract = str(ref_row.get("abstract") or "").replace("\n", " ")
                            except Exception:
                                pass
                        out.append(Paper(pid=f"arxiv:{ref_id}", arxiv_id=ref_id,
                                         title=self._id_to_title[ref_id], abstract=abstract,
                                         source="pasa"))
                        if len(out) >= limit:
                            return out
        except Exception:
            return []
        return out

    def _rank_sections(self, query: str, row: Dict[str, Any],
                       sections: Dict[str, Any]) -> List[Tuple[str, float]]:
        """Rank an anchor's archived headings without accessing benchmark labels."""
        headings = list(sections)
        if self._section_selector is None:
            return [(heading, _section_score(heading, query)) for heading in headings]
        try:
            word, char, model, feature_fn = self._section_selector
            n = len(headings)
            x = feature_fn(word, char, [query] * n,
                           [str(row.get("title") or "")] * n,
                           [str(row.get("abstract") or "")] * n, headings,
                           list(range(n)), [n] * n)
            scores = np.asarray(model.predict_proba(x)[:, 1], dtype=np.float64)
            if self.section_cited_title_weight > 0:
                ref_scores = self._cited_title_set_scores(word, query, headings, sections)
                scores = ((1.0 - self.section_cited_title_weight) * scores
                          + self.section_cited_title_weight * ref_scores)
            return list(zip(headings, scores.tolist()))
        except Exception:
            if self.ledger:
                self.ledger.mark("errors::pasa_section_selector_score")
            return [(heading, _section_score(heading, query)) for heading in headings]

    def _cited_title_set_scores(self, word_vectorizer, query: str,
                                headings: Sequence[str], sections: Dict[str, Any]) -> np.ndarray:
        """Query-to-section cited-title MaxSim + SoftTopK score.

        This is intentionally not a fabricated section-body embedding: the
        paper archive truthfully stores a list of citations for each heading.
        Each cited title is independently compared with the query; the best
        matching title contributes 65%, and evidence from the top-k titles
        contributes 35%.  A Crawler-SFT grouped holdout selected this fixed
        form before it is exercised on AutoScholarQuery dev.
        """
        q = word_vectorizer.transform([query])
        out = np.zeros(len(headings), dtype=np.float64)
        for i, heading in enumerate(headings):
            refs = [str(x) for x in (sections.get(heading) or []) if str(x).strip()]
            if not refs:
                continue
            try:
                matrix = word_vectorizer.transform(refs)
                sims = np.asarray(matrix.multiply(q).sum(axis=1)).ravel()
                if len(sims):
                    best = np.sort(sims)[::-1]
                    out[i] = (0.65 * best[0]
                              + 0.35 * best[:min(self.section_cited_title_top_k,
                                                  len(best))].mean())
            except Exception:
                # An invalid/nonstandard citation entry must only lose this
                # auxiliary signal; the Crawler heading score remains valid.
                continue
        return out

    def _choose_sections(self, ranked_sections: Sequence[Tuple[str, float]],
                         max_sections: int) -> List[Tuple[str, float]]:
        """Choose a bounded section prefix, optionally gating only Top-2.

        This implements a deliberately narrow, testable version of adaptive
        section count.  It never reorders sections, never accesses labels, and
        leaves Top-3+ behaviour untouched if a future configuration asks for
        more than two sections.
        """
        chosen = list(ranked_sections[:max(1, int(max_sections))])
        if (self.section_dynamic_second_margin < 0 or len(chosen) < 2):
            return chosen
        first, second = chosen[0], chosen[1]
        close_tie = abs(float(first[1]) - float(second[1])) < self.section_dynamic_second_margin
        high_second = float(second[1]) > self.section_dynamic_second_min_score
        if close_tie or high_second:
            return chosen
        return [first, *chosen[2:]]

    def references_for_query(self, pid: str, query: str, limit: int = 60,
                             max_sections: int = 2) -> List[Paper]:
        """只扩展与 query 对齐的 PaSa section 引用。

        官方 archive 并不提供 section 正文，只提供 ``heading -> reference titles``。
        因而这里绝不伪装成全文理解：若配置了由官方 Crawler-SFT 训练的本地模型，
        它只观察 query、锚点标题/摘要和 heading；否则回退到透明的 heading 词面
        匹配与弱 Related Work/Background 先验。返回的论文仍是纯候选，必须在后续
        L1/L2/Selector 中再次判断，不能被视作正例。
        """
        papers, _ = self.references_for_query_with_trace(
            pid, query, limit=limit, max_sections=max_sections)
        return papers

    def references_for_query_with_trace(self, pid: str, query: str, limit: int = 60,
                                        max_sections: int = 2) -> Tuple[List[Paper], Dict[str, Any]]:
        """Return section references plus a label-blind provenance bundle.

        The companion to :meth:`references_for_query` is deliberately an
        observational interface.  ``trace`` contains only archived inputs and
        model scores already used to select sections; it never sees benchmark
        answers and MultiProbe never uses it to change ranking or admission.
        A separate cache namespace keeps old list-only cache entries valid.
        """
        if self._zip is None or not self._id_to_title or not self._title_to_ids:
            return [], {}
        aid = str(pid).split(":", 1)[-1]
        aid = re.sub(r"v\d+$", "", aid, flags=re.I)
        title = self._id_to_title.get(aid)
        if not title or max_sections <= 0:
            return [], {}
        key = cache_key(self.name, "references_for_query", aid, query,
                        limit, max_sections, self._section_selector_token,
                        self.section_selector_min_score,
                        self.section_cited_title_weight,
                        self.section_cited_title_top_k,
                        self.section_dynamic_second_margin,
                        self.section_dynamic_second_min_score,
                        "provenance_v1")
        cached = self.cache.get(key) if self.cache else None
        if isinstance(cached, dict) and isinstance(cached.get("papers"), list):
            if self.ledger:
                self.ledger.add_api("references_section::pasa", cache_hit=True)
            return ([Paper(**p) for p in cached["papers"]],
                    dict(cached.get("trace") or {}))
        try:
            with self._zip_lock:
                row = json.loads(self._zip.read(_title_key(title)).decode("utf-8"))
                sections = row.get("sections") or {}
                if not isinstance(sections, dict):
                    return [], {}
                ranked_sections = sorted(self._rank_sections(query, row, sections),
                                         key=lambda x: (-x[1], str(x[0])))
                if self._section_selector is not None and self.section_selector_min_score > 0:
                    ranked_sections = [x for x in ranked_sections
                                       if x[1] >= self.section_selector_min_score]
                chosen_pairs = self._choose_sections(ranked_sections, max_sections)
                chosen = [section for section, _ in chosen_pairs]
                out: List[Paper] = []
                seen = set()
                paper_trace: Dict[str, Dict[str, Any]] = {}
                for section in chosen:
                    refs = sections.get(section) or []
                    if not isinstance(refs, list):
                        continue
                    for ref_title in refs:
                        for ref_id in self._title_to_ids.get(_title_key(str(ref_title)), []):
                            if ref_id == aid:
                                continue
                            ref_pid = f"arxiv:{ref_id}"
                            if ref_id in seen:
                                detail = paper_trace.get(ref_pid)
                                if detail is not None and section not in detail["section_headings"]:
                                    detail["section_headings"].append(section)
                                continue
                            seen.add(ref_id)
                            abstract = ""
                            hydration_attempted = len(out) < self.reference_hydrate_limit
                            if hydration_attempted:
                                try:
                                    ref_row = json.loads(self._zip.read(
                                        _title_key(self._id_to_title[ref_id])).decode("utf-8"))
                                    abstract = str(ref_row.get("abstract") or "").replace("\n", " ")
                                except Exception:
                                    pass
                            out.append(Paper(pid=ref_pid, arxiv_id=ref_id,
                                             title=self._id_to_title[ref_id], abstract=abstract,
                                             source="pasa"))
                            paper_trace[ref_pid] = {
                                "section_headings": [section],
                                "hydration_attempted": hydration_attempted,
                                "abstract_present_at_discovery": bool(abstract.strip()),
                            }
                            if len(out) >= limit:
                                break
                        if len(out) >= limit:
                            break
                    if len(out) >= limit:
                        break
        except Exception:
            return [], {}
        trace = {
            "anchor_arxiv_id": aid,
            "selected_sections": [str(section) for section in chosen],
            "section_scores": [
                {"heading": str(section), "score": round(float(score), 8),
                 "reference_title_count": len(sections.get(section) or [])}
                for section, score in ranked_sections
            ],
            "papers": paper_trace,
        }
        if self.ledger:
            self.ledger.add_api("references_section::pasa")
        if self.cache:
            self.cache.set(key, {"papers": [p.to_dict() for p in out], "trace": trace},
                           ns=self.name)
        return out, trace
