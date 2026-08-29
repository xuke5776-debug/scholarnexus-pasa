"""MultiProbe：多通道并行召回 + 跨源实体消歧 + 引文扩散。

三条设计要点
------------
1. **通道身份必须被记录下来**。每个候选被哪些通道命中，是 CoverageMeter 做
   捕获–再捕获估计的唯一输入。所以去重合并时不能只留一份，必须把通道集合并起来。
   这是本模块与普通「多路召回去重」实现的根本区别。

2. **弱约束检索**。只有 hard_filter 走 API 元数据参数，anchor 生成检索式，
   verify 类约束**一个字都不进检索式**。合取式查询会让召回率断崖下跌。

3. **跨源版本合并**。同一篇论文在 arXiv / OpenAlex / S2 里是三个 id。
   先按 DOI/arXiv id 精确合并，再对剩余的用标题相似度做模糊合并。
   合并时保留信息量最大的字段（摘要更长的、引文表更全的）。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from ..schema import Candidate, Paper, QueryPlan
from ..utils import rrf_fuse, title_similarity, tokenize
from .citation_graph import CitationGraph, graph_prior


@dataclass
class ProbeResult:
    candidates: Dict[str, Candidate]                    # pid → Candidate
    channel_hits: Dict[str, Set[str]] = field(default_factory=dict)
    rank_lists: Dict[str, List[str]] = field(default_factory=dict)
    graph: CitationGraph = field(default_factory=CitationGraph)
    queries_used: List[str] = field(default_factory=list)
    # One compact event per citation expansion.  It intentionally keeps the
    # section ranking once per anchor rather than duplicating it for every
    # discovered reference in Candidate.provenance.
    citation_traces: List[Dict] = field(default_factory=list)

    def merge(self, other: "ProbeResult"):
        for pid, c in other.candidates.items():
            if pid in self.candidates:
                _merge_candidate(self.candidates[pid], c)
            else:
                self.candidates[pid] = c
        for ch, pids in other.channel_hits.items():
            self.channel_hits.setdefault(ch, set()).update(pids)
        for ch, lst in other.rank_lists.items():
            base = self.rank_lists.setdefault(ch, [])
            for pid in lst:
                if pid not in base:
                    base.append(pid)
        for n in other.graph.nodes:
            self.graph.nodes.add(n)
        for a, bs in other.graph.out_edges.items():
            for b in bs:
                self.graph.add_edge(a, b)
        self.queries_used.extend(q for q in other.queries_used
                                 if q not in self.queries_used)
        for event in other.citation_traces:
            if event not in self.citation_traces:
                self.citation_traces.append(event)
        return self


def _merge_candidate(dst: Candidate, src: Candidate):
    dst.channels |= src.channels
    for ch, r in src.channel_ranks.items():
        dst.channel_ranks[ch] = min(dst.channel_ranks.get(ch, 10 ** 9), r)
    # Provenance is a diagnostic ledger, not a relevance feature.  Preserve
    # both discovery paths after cross-source entity resolution, while keeping
    # an accidental duplicate absorption from inflating the audit output.
    for event in src.provenance:
        if event not in dst.provenance:
            dst.provenance.append(event)
    # Preserve source-derived features computed before ProbeResult.merge().
    # Without this, a dense/citation hit discovered in a later round would
    # lose its score when the destination candidate already existed.
    dst.s_dense = max(float(dst.s_dense), float(src.s_dense))
    dst.s_reference = max(float(dst.s_reference), float(src.s_reference))
    _merge_paper(dst.paper, src.paper)


def _merge_paper(dst: Paper, src: Paper):
    """字段级合并：每个字段取信息量更大的一方。"""
    if len(src.abstract or "") > len(dst.abstract or ""):
        dst.abstract = src.abstract
    if not dst.year and src.year:
        dst.year = src.year
    if not dst.venue and src.venue:
        dst.venue = src.venue
    if not dst.doi and src.doi:
        dst.doi = src.doi
    if not dst.arxiv_id and src.arxiv_id:
        dst.arxiv_id = src.arxiv_id
    if not dst.url and src.url:
        dst.url = src.url
    if len(src.authors) > len(dst.authors):
        dst.authors = src.authors
    dst.citation_count = max(dst.citation_count, src.citation_count)
    if len(src.reference_ids) > len(dst.reference_ids):
        dst.reference_ids = src.reference_ids
    if len(src.citing_ids) > len(dst.citing_ids):
        dst.citing_ids = src.citing_ids
    if src.is_review and not dst.is_review:
        dst.doc_type = src.doc_type
    if src.source and src.source not in dst.source:
        dst.source = f"{dst.source}+{src.source}" if dst.source else src.source
    # Keep the strongest source-native retrieval score when two views resolve
    # to the same paper.  Older cached records have no score, so this remains
    # backwards compatible with the existing Paper schema.
    src_score = getattr(src, "retrieval_score", None)
    dst_score = getattr(dst, "retrieval_score", None)
    if src_score is not None and (dst_score is None or float(src_score) > float(dst_score)):
        dst.retrieval_score = float(src_score)


class MultiProbe:
    def __init__(self, registry, ledger=None, max_workers: int = 8):
        self.registry = registry
        self.ledger = ledger
        self.max_workers = max_workers

    # ------------------------------------------------------------------ #
    def probe(self, plan: QueryPlan, queries: Sequence[str],
              per_query_limit: int = 20, round_idx: int = 0,
              audit_provenance: bool = False,
              source_names: Optional[Sequence[str]] = None,
              channel_tag: str = "") -> ProbeResult:
        """并行跑「检索式 × 数据源」的笛卡尔积。

        通道命名规则：`{通道类型}:{数据源}`。词法 vs 语义的区分由数据源特性决定
        （arXiv 是词法型、S2 是语义型、OpenAlex 介于两者之间），这样通道之间的
        独立性更真实，捕获–再捕获估计才不会被系统性低估。

        ``source_names`` permits an explicitly isolated probe without changing
        the registry.  It is used by the PaSa experiment that sends the
        original, un-decomposed question to a dense source while retaining
        controlled QueryLens strings for lexical FTS.  ``channel_tag`` keeps
        the result provenance-distinct, so later admission or audit code
        cannot accidentally treat the two query representations as one rank
        list.
        """
        filters = plan.api_filters()
        sources = self.registry.all()
        if source_names is not None:
            selected = set(source_names)
            sources = [src for src in sources if src.name in selected]
        if not sources or not queries:
            return ProbeResult(candidates={})

        jobs: List[Tuple[int, str, object, str]] = []
        for query_index, q in enumerate(queries):
            for src in sources:
                channel = self._channel_of(src)
                if channel_tag:
                    channel = f"{channel}:{channel_tag}"
                jobs.append((query_index, q, src, channel))

        out = ProbeResult(candidates={}, queries_used=list(queries))
        # 并行执行、但**按提交顺序聚合**。用 as_completed 会让 rank_lists 的顺序
        # 取决于线程调度与网络抖动，进而让 RRF 融合分、乃至最终输出集合不可复现。
        # 自动评测要求同一输入给出同一输出，这里的确定性不是洁癖而是硬要求。
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futs = []
            for query_index, q, src, ch in jobs:
                fn = getattr(src, "search_channels", None)
                if callable(fn):
                    futs.append((ex.submit(fn, q, per_query_limit, filters), ch, True,
                                 query_index))
                else:
                    futs.append((ex.submit(src.search, q, per_query_limit, filters), ch, False,
                                 query_index))
            for fut, ch, is_multi, query_index in futs:
                try:
                    value = fut.result()
                except Exception:                                # noqa: BLE001
                    continue
                if is_multi and isinstance(value, dict):
                    # Preserve insertion order from the source for deterministic
                    # aggregation; each view remains an independent RRF channel.
                    for suffix, papers in value.items():
                        self._absorb(
                            out, papers, f"{ch}:{suffix}", round_idx,
                            provenance=({"kind": "retrieval", "round": round_idx,
                                         "query_index": query_index}
                                        if audit_provenance else None))
                else:
                    self._absorb(
                        out, value, ch, round_idx,
                        provenance=({"kind": "retrieval", "round": round_idx,
                                     "query_index": query_index}
                                    if audit_provenance else None))
        self._dedupe_fuzzy(out)
        return out

    @staticmethod
    def _channel_of(src) -> str:
        return {"arxiv": "lexical:arxiv", "openalex": "lexical:openalex",
                "s2": "dense:s2", "pubmed": "lexical:pubmed",
                "local": "lexical:local", "pasa": "lexical:pasa",
                "pasa_dense": "dense:pasa",
                "pasa_local_dense": "dense:pasa_local_minilm"}.get(
                    src.name, f"lexical:{src.name}")

    def _absorb(self, out: ProbeResult, papers: Sequence[Paper], channel: str,
                round_idx: int, provenance: Optional[Dict] = None):
        lst = out.rank_lists.setdefault(channel, [])
        hits = out.channel_hits.setdefault(channel, set())
        for rank, p in enumerate(papers):
            if not p.title:
                continue
            pid = p.pid
            cand = out.candidates.get(pid)
            if cand is None:
                cand = Candidate(paper=p, seed_round=round_idx)
                out.candidates[pid] = cand
            else:
                _merge_paper(cand.paper, p)
            cand.channels.add(channel)
            cand.channel_ranks.setdefault(channel, rank)
            if channel.startswith("dense:"):
                # Dense sources now expose their native cosine.  The rank
                # fallback keeps synthetic/test sources useful and preserves
                # a nonzero, deterministic feature when an old cache lacks it.
                native = getattr(cand.paper, "retrieval_score", None)
                try:
                    dense_signal = (float(native) if native is not None
                                    else 1.0 / (1.0 + max(0, int(rank))))
                except (TypeError, ValueError):
                    dense_signal = 1.0 / (1.0 + max(0, int(rank)))
                cand.s_dense = max(float(cand.s_dense), dense_signal)
            elif channel.startswith("cite_"):
                # Citation expansion is a separate discovery signal; expose a
                # bounded rank-derived value for the fusion model rather than
                # leaving the reference feature permanently at zero.
                cand.s_reference = max(float(cand.s_reference),
                                       1.0 / (1.0 + max(0, int(rank))))
            if provenance is not None:
                # ``papers`` can carry a citation-specific detail map keyed by
                # pid.  Pull that detail into the per-candidate event instead
                # of repeating every selected section for every reference.
                event = {k: v for k, v in provenance.items() if k != "papers"}
                event.update((provenance.get("papers") or {}).get(pid, {}))
                event["channel"] = channel
                event["rank"] = rank
                if event not in cand.provenance:
                    cand.provenance.append(event)
            hits.add(pid)
            if pid not in lst:
                lst.append(pid)
            out.graph.add_paper(p)

    # ------------------------------------------------------------------ #
    def _dedupe_fuzzy(self, out: ProbeResult, threshold: float = 0.86):
        """跨源实体消歧：先按 dedup_key 精确合并，再按标题相似度模糊合并。

        模糊合并只在**同一 dedup 分桶前缀**内比较（标题首词哈希），
        避免 O(n²) 全量比较把延迟拖垮。
        """
        # ---- 精确合并 ----
        by_key: Dict[str, str] = {}
        alias: Dict[str, str] = {}
        for pid, c in list(out.candidates.items()):
            k = c.paper.dedup_key()
            keep = by_key.get(k)
            if keep is None:
                by_key[k] = pid
            elif keep != pid:
                _merge_candidate(out.candidates[keep], c)
                alias[pid] = keep
                out.candidates.pop(pid, None)

        # ---- 模糊合并（同首词分桶） ----
        buckets: Dict[str, List[str]] = {}
        for pid, c in out.candidates.items():
            toks = tokenize(c.paper.title)
            buckets.setdefault(toks[0] if toks else "_", []).append(pid)
        for _, pids in buckets.items():
            if len(pids) < 2:
                continue
            for i in range(len(pids)):
                a = pids[i]
                if a not in out.candidates:
                    continue
                for j in range(i + 1, len(pids)):
                    b = pids[j]
                    if b not in out.candidates or a == b:
                        continue
                    if title_similarity(out.candidates[a].paper.title,
                                        out.candidates[b].paper.title) >= threshold:
                        _merge_candidate(out.candidates[a], out.candidates[b])
                        alias[b] = a
                        out.candidates.pop(b, None)

        if not alias:
            return
        # 通道命中集合与排序表要跟着改名，否则捕获–再捕获会把同一篇算成两个个体
        for ch, pids in out.channel_hits.items():
            out.channel_hits[ch] = {alias.get(p, p) for p in pids}
        for ch, lst in out.rank_lists.items():
            seen, new = set(), []
            for p in lst:
                q = alias.get(p, p)
                if q not in seen:
                    seen.add(q)
                    new.append(q)
            out.rank_lists[ch] = new

    # ------------------------------------------------------------------ #
    def expand_citations(self, out: ProbeResult, seeds: Dict[str, float],
                         limit_per_seed: int = 40, max_seeds: int = 6,
                         round_idx: int = 1, query: str = "",
                         section_max_sections: int = 0,
                         audit_provenance: bool = False) -> ProbeResult:
        """引文扩散：以高置信种子为起点，双向抓取一跳邻居。

        种子按置信度取 top-N；前向（施引）与后向（被引）各算一个通道，
        因为它们的发现机制完全不同 —— 这对捕获–再捕获的通道独立性假设很重要。
        """
        srcs = [s for s in self.registry.all() if s.supports_citations]
        if not srcs or not seeds:
            return out
        # ``seeds`` can originate from a dict assembled by multiple sources.
        # Break equal scores by pid so graph expansion is reproducible across
        # Python processes (hash randomisation must not decide a benchmark
        # result).
        top = sorted(seeds.items(), key=lambda x: (-x[1], x[0]))[:max_seeds]
        jobs = []
        for pid, _ in top:
            candidate = out.candidates.get(pid)
            # arXiv IDs deliberately use the neutral ``arxiv:`` prefix so
            # they align with PaSa gold labels.  They therefore cannot tell
            # us which provider owns the citation graph; preserve/use the
            # paper source instead of falling back to the first registry
            # source (which previously sent PaSa seeds to OpenAlex).
            src = self._source_for(pid, srcs,
                                   source_name=(candidate.paper.source if candidate else ""))
            if src is None:
                continue
            section_fn = getattr(src, "references_for_query", None)
            if (section_max_sections > 0 and query and callable(section_fn)):
                jobs.append((src, "references_section", pid))
            else:
                jobs.append((src, "references", pid))
            jobs.append((src, "citations", pid))

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futs = []
            for src, kind, pid in jobs:
                if kind == "references_section":
                    trace_fn = getattr(src, "references_for_query_with_trace", None)
                    fn = trace_fn if audit_provenance and callable(trace_fn) else src.references_for_query
                    args = (pid, query, limit_per_seed, section_max_sections)
                else:
                    fn = src.references if kind == "references" else src.citations
                    args = (pid, limit_per_seed)
                futs.append((ex.submit(fn, *args), kind, pid))
            for fut, kind, pid in futs:                # 同上：按提交顺序聚合
                try:
                    value = fut.result()
                except Exception:                                # noqa: BLE001
                    continue
                source_trace = {}
                if (kind == "references_section" and audit_provenance
                        and isinstance(value, tuple) and len(value) == 2):
                    papers, source_trace = value
                else:
                    papers = value
                ch = ("cite_bwd_section" if kind == "references_section"
                      else "cite_bwd" if kind == "references" else "cite_fwd")
                provenance = None
                if audit_provenance:
                    provenance = {
                        "kind": "citation",
                        "round": round_idx,
                        "anchor_pid": pid,
                        "direction": ("backward_section" if kind == "references_section"
                                      else "backward" if kind == "references" else "forward"),
                        "papers": dict(source_trace.get("papers") or {}),
                    }
                    if kind == "references_section":
                        out.citation_traces.append({
                            "round": round_idx,
                            "anchor_pid": pid,
                            "direction": "backward_section",
                            "selected_sections": list(
                                source_trace.get("selected_sections") or []),
                            "section_scores": list(
                                source_trace.get("section_scores") or []),
                            "returned_papers": len(papers),
                            "hydration_attempted": sum(
                                bool(v.get("hydration_attempted"))
                                for v in (source_trace.get("papers") or {}).values()),
                        })
                self._absorb(out, papers, ch, round_idx, provenance=provenance)
                for p in papers:
                    if kind in ("references", "references_section"):
                        out.graph.add_edge(pid, p.pid)
                    else:
                        out.graph.add_edge(p.pid, pid)
        self._dedupe_fuzzy(out)
        return out

    @staticmethod
    def _source_for(pid: str, srcs, source_name: str = "") -> Optional[object]:
        for s in srcs:
            if s.name == source_name:
                return s
        prefix = pid.split(":", 1)[0]
        for s in srcs:
            if s.name == prefix:
                return s
        return srcs[0] if srcs else None

    # ------------------------------------------------------------------ #
    def apply_graph_signal(self, out: ProbeResult, seeds: Dict[str, float],
                           min_constraint: float = 0.0) -> int:
        """把图先验写回候选的 s_graph，并把「仅由图信号发现」的论文登记为 cocite 通道。"""
        cand_ids = set(out.candidates)
        prior = graph_prior(out.graph, seeds, candidates=cand_ids)
        hits = out.channel_hits.setdefault("cocite", set())
        n = 0
        for pid, g in prior.items():
            c = out.candidates.get(pid)
            if c is None:
                continue
            # 图邻近不是语义相关性的替代品。只有已经通过查询约束初筛的论文
            # 才能把图先验作为加分项；其余候选保留为文本排序候选，但不得因
            # 共同引用/高中心性伪装成相关论文。
            if c.s_constraint < min_constraint:
                c.s_graph = 0.0
                continue
            c.s_graph = float(g)
            if g >= 0.25:
                c.channels.add("cocite")
                hits.add(pid)
                n += 1
        # Citation priors frequently tie.  ``prior`` is built through sets in
        # the graph routine, so score-only sorting leaks hash iteration order
        # into RRF and may move different papers across the L2 input cap.
        lst = sorted((p for p in prior if p in cand_ids),
                     key=lambda p: (-prior[p], p))
        out.rank_lists["cocite"] = lst[:200]
        return n

    # ------------------------------------------------------------------ #
    @staticmethod
    def fuse(out: ProbeResult, weights: Dict[str, float]) -> Dict[str, float]:
        """RRF 融合各通道排序表。通道权重来自查询类型策略表。"""
        def _w(ch: str) -> float:
            base = ch.split(":", 1)[0]
            return weights.get(ch, weights.get(base, 1.0))
        wmap = {ch: _w(ch) for ch in out.rank_lists}
        scores = rrf_fuse(out.rank_lists, k=60, weights=wmap)
        for pid, s in scores.items():
            c = out.candidates.get(pid)
            if c is not None:
                c.s_rrf = float(s)
        return scores
