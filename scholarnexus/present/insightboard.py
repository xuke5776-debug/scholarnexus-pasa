"""InsightBoard：结构化输出（创新点 7）。

赛题第 (4) 条要求「根据用户查询意图，自主整理归纳搜索结果返回结构化展示」。
关键词是**自主**与**意图驱动** —— 所以这里不是给所有查询套同一个模板，
而是由 QueryType 决定生成哪几个视图：

    locate     → 候选消歧对照表（逐条约束差异，帮用户确认"是不是这一篇"）
    survey     → 分面聚类树 + 时间轴 + 引文关系图
    method_cross → 方法×任务交叉矩阵 + 关系图
    benchmark  → 数据集/指标对比表
    lineage    → 时间轴引文谱系图

所有视图共享一张底座：**查询–论文约束满足矩阵**（行=论文，列=查询分解出的
各维约束，单元格=满足/部分/不满足 + 原文证据）。它是可解释性的核心，
也是「结构化」区别于「排版好看」的地方——每个断言都能追溯到证据句。
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Sequence

from ..llm import BudgetExhausted
from ..llm.prompts import SUMMARIZE_SYSTEM, SUMMARIZE_USER
from ..schema import Candidate, ConstraintRole, QueryPlan, QueryType
from ..utils import tokenize

# 从标题/摘要里抽取数据集与指标的轻量规则（零 LLM 成本）
_DATASET_HINTS = re.compile(
    r"\b(ImageNet|COCO|CIFAR-?\d*|MNIST|SQuAD|GLUE|SuperGLUE|WMT\d*|LibriSpeech|"
    r"MIMIC-?\w*|ChestX-?\w*|BraTS|ADNI|Cityscapes|ADE20K|KITTI|nuScenes|Waymo|"
    r"MS-?MARCO|BEIR|MTEB|HotpotQA|Natural Questions|TriviaQA|MMLU|GSM8K|HumanEval|"
    r"LAION|WebVid|Kinetics|AudioSet|PubMedQA|BioASQ)\b", re.I)
_METRIC_HINTS = re.compile(
    r"\b(accuracy|F1|BLEU|ROUGE|mAP|AUC|AUROC|Dice|IoU|mIoU|perplexity|WER|CER|"
    r"nDCG|MRR|Recall@\d+|Precision@\d+|PSNR|SSIM|FID|pass@\d+)\b", re.I)


# --------------------------------------------------------------------------- #
def build_views(plan: QueryPlan, core: Sequence[Candidate],
                partial: Sequence[Candidate], llm=None, ledger=None,
                graph=None) -> Dict[str, Any]:
    """生成该查询意图对应的全部视图。LLM 只用于主题归纳，其余全部零成本。"""
    papers = list(core) + list(partial)
    views: Dict[str, Any] = {
        "query_type": plan.query_type.value,
        "query_type_zh": plan.query_type.zh,
        "matrix": constraint_matrix(plan, papers),
        "stats": corpus_stats(papers),
    }

    qt = plan.query_type
    if qt == QueryType.LOCATE:
        views["disambiguation"] = disambiguation_table(plan, papers[:8])
    if qt in (QueryType.SURVEY, QueryType.METHOD_CROSS, QueryType.BENCHMARK):
        views["facets"] = facet_clusters(papers)
    if qt in (QueryType.BENCHMARK, QueryType.METHOD_CROSS):
        views["comparison"] = comparison_table(papers)
    if qt in (QueryType.LINEAGE, QueryType.SURVEY):
        views["timeline"] = timeline(papers)
    if graph is not None and qt != QueryType.LOCATE:
        views["graph"] = relation_graph(papers, graph)

    # LLM 主题归纳：只对 core 做，且只在候选足够多时才值得花这一次调用
    if llm is not None and len(core) >= 3:
        themes = llm_themes(plan, list(core)[:30], llm, ledger)
        if themes:
            views["themes"] = themes
    return views


# --------------------------------------------------------------------------- #
# 底座：约束满足矩阵
# --------------------------------------------------------------------------- #
def constraint_matrix(plan: QueryPlan, cands: Sequence[Candidate],
                      limit: int = 40) -> Dict[str, Any]:
    """行=论文，列=约束，单元格=状态 + 证据。

    没有走到 L3 的论文，其单元格状态为 "unrated"（而非 "unknown"）——
    这两者含义不同：unrated 是「没花钱判」，unknown 是「判了但说不出证据」。
    在审计界面上必须区分，否则用户无法判断该不该追加预算。
    """
    cols = [c.text for c in plan.verify_constraints()][:8]
    if not cols:
        cols = [c.text for c in plan.constraints][:8]
    rows = []
    for c in cands[:limit]:
        by_text = {ch.constraint_text: ch for ch in c.checks}
        cells = []
        for col in cols:
            ch = by_text.get(col)
            if ch is None:
                cells.append({"status": "unrated", "evidence": ""})
            else:
                cells.append({"status": ch.status, "evidence": ch.evidence})
        rows.append({
            "pid": c.pid, "title": c.paper.title, "year": c.paper.year,
            "venue": c.paper.venue, "url": c.paper.url, "tier": c.tier,
            "p_gold": round(c.p_gold, 3), "judged_level": c.judged_level,
            "cells": cells,
            "satisfaction": round(c.constraint_satisfaction(), 3),
            "rationale": c.rationale,
        })
    return {"columns": cols, "rows": rows}


def corpus_stats(cands: Sequence[Candidate]) -> Dict[str, Any]:
    years = [c.paper.year for c in cands if c.paper.year]
    venues = Counter(c.paper.venue for c in cands if c.paper.venue)
    channels = Counter()
    for c in cands:
        for ch in c.channels:
            channels[ch.split(":", 1)[0]] += 1
    return {
        "n": len(cands),
        "year_range": [min(years), max(years)] if years else None,
        "year_hist": dict(sorted(Counter(years).items())),
        "top_venues": venues.most_common(8),
        "channel_hits": channels.most_common(),
        "median_citations": _median([c.paper.citation_count for c in cands]),
    }


def _median(xs: Sequence[float]) -> float:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return 0.0
    n = len(xs)
    return float(xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2)


# --------------------------------------------------------------------------- #
# 意图专属视图
# --------------------------------------------------------------------------- #
def disambiguation_table(plan: QueryPlan, cands: Sequence[Candidate]) -> Dict[str, Any]:
    """定位型：把 top 候选并排放，突出**彼此的差异**而非共性。

    找特定论文时用户真正需要的不是「它们都相关」，而是「这几篇差在哪，
    哪一篇才是我要的」。所以只保留在候选间取值不同的字段。
    """
    rows = []
    for c in cands:
        p = c.paper
        rows.append({
            "pid": c.pid, "title": p.title, "year": p.year, "venue": p.venue,
            "first_author": p.authors[0] if p.authors else "",
            "citations": p.citation_count, "url": p.url,
            "p_gold": round(c.p_gold, 3), "tier": c.tier,
            "distinguishing": c.rationale or _first_sentence(p.abstract),
        })
    varying = [f for f in ("year", "venue", "first_author", "citations")
               if len({str(r[f]) for r in rows}) > 1]
    return {"rows": rows, "distinguishing_fields": varying}


def facet_clusters(cands: Sequence[Candidate], min_size: int = 2,
                   max_facets: int = 8) -> Dict[str, Any]:
    """分面聚类：用标题的高判别力术语做无监督分组（零 LLM 成本）。

    不用 KMeans —— 学术标题的术语本身就是最好的簇标签，聚类反而丢掉可解释性。
    这里选「出现次数 ≥2 且不过于普遍」的二元组作为分面，一篇论文可属多个分面。
    """
    grams = defaultdict(list)
    for c in cands:
        toks = [t for t in tokenize(c.paper.title) if t.isascii() and len(t) > 3]
        seen = set()
        for i in range(len(toks)):
            for g in (toks[i], " ".join(toks[i:i + 2]) if i + 1 < len(toks) else None):
                if g and g not in seen:
                    seen.add(g)
                    grams[g].append(c.pid)
    n = max(len(cands), 1)
    scored = [(g, pids) for g, pids in grams.items()
              if min_size <= len(pids) <= max(min_size, int(0.7 * n))]
    # 优先选覆盖多、但不是所有论文都有的术语（判别力）
    scored.sort(key=lambda x: -(len(x[1]) * (1 - len(x[1]) / n) * (1 + 0.5 * (" " in x[0]))))
    facets, covered = [], set()
    for g, pids in scored:
        if len(facets) >= max_facets:
            break
        fresh = [p for p in pids if p not in covered]
        if len(fresh) < min_size:
            continue
        facets.append({"name": g, "pids": pids, "size": len(pids)})
        covered.update(pids)
    rest = [c.pid for c in cands if c.pid not in covered]
    if rest:
        facets.append({"name": "其他", "pids": rest, "size": len(rest)})
    return {"facets": facets, "covered": len(covered), "total": n}


def comparison_table(cands: Sequence[Candidate], limit: int = 25) -> Dict[str, Any]:
    """方法–数据集–指标对比表。用规则从标题/摘要里抽取，零 LLM 成本。"""
    rows = []
    for c in cands[:limit]:
        text = c.paper.text()
        rows.append({
            "pid": c.pid, "title": c.paper.title, "year": c.paper.year,
            "venue": c.paper.venue, "url": c.paper.url,
            "datasets": sorted({m.group(0) for m in _DATASET_HINTS.finditer(text)})[:5],
            "metrics": sorted({m.group(0) for m in _METRIC_HINTS.finditer(text)})[:5],
            "citations": c.paper.citation_count,
        })
    all_ds = Counter(d for r in rows for d in r["datasets"])
    all_mt = Counter(m for r in rows for m in r["metrics"])
    return {"rows": rows, "common_datasets": all_ds.most_common(8),
            "common_metrics": all_mt.most_common(8)}


def timeline(cands: Sequence[Candidate]) -> Dict[str, Any]:
    """时间轴：按年分组，每年给出被引最高的代表工作。"""
    by_year: Dict[int, List[Candidate]] = defaultdict(list)
    for c in cands:
        if c.paper.year:
            by_year[int(c.paper.year)].append(c)
    out = []
    for y in sorted(by_year):
        items = sorted(by_year[y], key=lambda c: -c.paper.citation_count)
        out.append({
            "year": y, "count": len(items),
            "papers": [{"pid": c.pid, "title": c.paper.title,
                        "citations": c.paper.citation_count, "tier": c.tier}
                       for c in items[:4]],
        })
    return {"years": out}


def relation_graph(cands: Sequence[Candidate], graph,
                   max_nodes: int = 60) -> Dict[str, Any]:
    """引文关系图：节点=论文，边=引用关系。直接供前端力导向图渲染。

    只保留结果集合内部的边 —— 外部节点会让图爆炸且对用户无信息量。
    孤立节点保留（它们本身就是有价值的信号：说明该论文靠语义而非引文被找到）。
    """
    keep = [c for c in cands[:max_nodes]]
    ids = {c.pid for c in keep}
    nodes = [{"id": c.pid, "label": _short_title(c.paper.title),
              "title": c.paper.title, "year": c.paper.year,
              "tier": c.tier, "citations": c.paper.citation_count,
              "p_gold": round(c.p_gold, 3),
              "channels": sorted({ch.split(":", 1)[0] for ch in c.channels})}
             for c in keep]
    edges = []
    for a in ids:
        for b in graph.out_edges.get(a, ()):
            if b in ids and a != b:
                edges.append({"source": a, "target": b, "type": "cites"})
    deg = Counter()
    for e in edges:
        deg[e["source"]] += 1
        deg[e["target"]] += 1
    for nd in nodes:
        nd["degree"] = deg.get(nd["id"], 0)
    return {"nodes": nodes, "edges": edges,
            "isolated": sum(1 for n in nodes if n["degree"] == 0)}


def llm_themes(plan: QueryPlan, cands: Sequence[Candidate], llm,
               ledger=None) -> Optional[Dict[str, Any]]:
    """LLM 主题归纳。失败即返回 None，由规则分面兜底 —— 绝不因归纳失败丢结果。"""
    listing = "\n".join(f"{i} | {c.paper.year or 'n.d.'} | {c.paper.title}"
                        for i, c in enumerate(cands, 1))
    try:
        data = llm.chat_json(
            SUMMARIZE_SYSTEM,
            SUMMARIZE_USER.format(query=plan.raw_query,
                                  query_type=plan.query_type.zh, papers=listing),
            stage="summarize", default={})
    except BudgetExhausted:
        return None
    except Exception:                                            # noqa: BLE001
        return None
    if not isinstance(data, dict) or not data.get("themes"):
        return None
    idx2pid = {i: c.pid for i, c in enumerate(cands, 1)}
    themes = []
    for t in data["themes"]:
        pids = [idx2pid[i] for i in (t.get("ids") or []) if i in idx2pid]
        if pids:
            themes.append({"name": str(t.get("name", ""))[:60], "pids": pids,
                           "summary": str(t.get("summary", ""))[:300]})
    tl = []
    for t in (data.get("timeline") or []):
        pids = [idx2pid[i] for i in (t.get("ids") or []) if i in idx2pid]
        if pids:
            tl.append({"year": t.get("year"), "pids": pids,
                       "milestone": str(t.get("milestone", ""))[:200]})
    return {"themes": themes, "timeline": tl,
            "takeaway": str(data.get("takeaway", ""))[:600],
            "gaps": [str(g)[:160] for g in (data.get("gaps") or [])][:5]}


# --------------------------------------------------------------------------- #
def _short_title(t: str, n: int = 42) -> str:
    return t if len(t) <= n else t[:n - 1] + "…"


def _first_sentence(text: str, n: int = 160) -> str:
    if not text:
        return ""
    m = re.split(r"(?<=[.!?])\s", text.strip())
    return (m[0] if m else text)[:n]


# --------------------------------------------------------------------------- #
# Markdown 渲染（CLI 与项目文档用）
# --------------------------------------------------------------------------- #
_ICON = {"yes": "✔", "partial": "◐", "no": "✘", "unknown": "?", "unrated": "·"}


def render_markdown(result) -> str:
    v = result.views or {}
    plan = result.plan
    L = [f"# 检索结果：{result.query}", "",
         f"**查询类型**：{plan.query_type.zh}　|　"
         f"**核心结果**：{len(result.core)} 篇　|　**部分相关**：{len(result.partial)} 篇",
         f"**集合基数估计 N̂**：{result.n_hat:.1f} "
         f"(95% CI {result.n_hat_ci[0]:.1f}–{result.n_hat_ci[1]:.1f})　|　"
         f"**覆盖率**：{result.coverage:.1%}　|　"
         f"**纳入门限 p\\***：{result.threshold:.3f}　|　"
         f"**期望 F1**：{result.expected_f1:.3f}", ""]

    if plan.constraints:
        L += ["## 查询理解", ""]
        for c in plan.constraints:
            role = {"hard_filter": "元数据过滤", "anchor": "检索锚点",
                    "verify": "判定核验", "negative": "排除项"}.get(
                        c.role.value, c.role.value)
            L.append(f"- `{role}` {c.text}")
        L += ["", f"检索式：{', '.join(f'`{s}`' for s in plan.search_strings)}", ""]

    m = v.get("matrix") or {}
    if m.get("rows"):
        L += ["## 约束满足矩阵", "",
              "| # | 论文 | 年份 | " + " | ".join(m["columns"]) + " | p |",
              "|---|---|---|" + "---|" * (len(m["columns"]) + 1)]
        for i, r in enumerate(m["rows"][:25], 1):
            cells = " | ".join(_ICON.get(c["status"], "·") for c in r["cells"])
            tag = "**" if r["tier"] == "core" else ""
            L.append(f"| {i} | {tag}{_short_title(r['title'], 60)}{tag} | "
                     f"{r['year'] or ''} | {cells} | {r['p_gold']:.2f} |")
        L += ["", "图例：✔ 满足　◐ 部分满足　✘ 不满足　? 证据不足　· 未精判", ""]

    th = v.get("themes")
    if th and th.get("themes"):
        L += ["## 主题归纳", ""]
        for t in th["themes"]:
            L.append(f"### {t['name']}（{len(t['pids'])} 篇）")
            L.append(t["summary"])
            L.append("")
        if th.get("takeaway"):
            L += ["> " + th["takeaway"], ""]
        if th.get("gaps"):
            L += ["**研究空白**：" + "；".join(th["gaps"]), ""]
    elif v.get("facets"):
        L += ["## 分面聚类", ""]
        for f in v["facets"]["facets"]:
            L.append(f"- **{f['name']}**：{f['size']} 篇")
        L.append("")

    if v.get("timeline"):
        L += ["## 时间轴", ""]
        for y in v["timeline"]["years"]:
            titles = "；".join(_short_title(p["title"], 50) for p in y["papers"][:2])
            L.append(f"- **{y['year']}**（{y['count']} 篇）{titles}")
        L.append("")

    if v.get("comparison") and v["comparison"]["rows"]:
        L += ["## 数据集 / 指标对比", "", "| 论文 | 年份 | 数据集 | 指标 |",
              "|---|---|---|---|"]
        for r in v["comparison"]["rows"][:15]:
            L.append(f"| {_short_title(r['title'], 50)} | {r['year'] or ''} | "
                     f"{', '.join(r['datasets']) or '—'} | "
                     f"{', '.join(r['metrics']) or '—'} |")
        L.append("")

    g = v.get("graph")
    if g:
        L += [f"## 引文关系图", "",
              f"{len(g['nodes'])} 个节点、{len(g['edges'])} 条引用边，"
              f"其中 {g['isolated']} 篇无内部引文连接（由语义通道独立发现）。", ""]

    t = result.ledger.get("total", {})
    L += ["## 执行账本", "",
          f"- LLM 调用 **{t.get('llm_calls',0)}** 次，"
          f"Token **{t.get('tokens',0):,}**，估算成本 ¥{t.get('est_cost_cny',0):.4f}",
          f"- 学术 API 调用 **{t.get('api_calls',0)}** 次"
          f"（缓存命中 {t.get('cache_hits',0)} 次）",
          f"- 端到端耗时 **{t.get('wall_seconds',0):.2f}s**，检索轮次 {result.rounds}", ""]
    return "\n".join(L)
