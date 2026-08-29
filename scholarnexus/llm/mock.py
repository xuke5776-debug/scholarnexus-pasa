"""确定性 Mock LLM。

它有三个不可替代的作用：
1. 无网络 / 无 API Key 时，整条流水线仍可端到端跑通与单元测试（CI 必须绿）；
2. 作为消融实验的「零 LLM」基线 —— 衡量 LLM 究竟贡献了多少 F1，
   这是项目文档里论证「LLM 不是装饰」的唯一严谨方式；
3. 保证 prompt 契约（输入/输出 schema）不被后续改动悄悄改坏。

实现方式是词法重叠 + 规则解析，输出格式与真实模型**完全一致**。
"""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Dict, List

from ..utils import approx_tokens, cosine_counter, tokenize
from .base import LLMClient, LLMResponse

_YEAR_RE = re.compile(r"(?:19|20)\d{2}")
_VENUES = ["cvpr", "iccv", "eccv", "neurips", "nips", "icml", "iclr", "acl",
           "emnlp", "naacl", "aaai", "ijcai", "kdd", "sigir", "www", "nature",
           "science", "tpami", "jmlr", "miccai", "interspeech", "chi"]


class MockLLM(LLMClient):
    name = "mock"

    def _raw_chat(self, messages: List[Dict[str, str]], stage: str = "misc",
                  **kw) -> LLMResponse:
        user = messages[-1]["content"]
        if stage.startswith("query_lens"):
            out = self._plan(user)
        elif stage.startswith("expand"):
            out = self._expand(user)
        elif stage.startswith("l3_verify") or stage.startswith("judge"):
            out = self._verify(user)
        elif stage.startswith("summarize"):
            out = self._summarize(user)
        else:
            out = json.dumps({"ok": True})
        return LLMResponse(text=out, prompt_tokens=approx_tokens(user),
                           completion_tokens=approx_tokens(out), model=self.model)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _query_of(user: str) -> str:
        m = re.search(r"<query>(.*?)</query>", user, re.S)
        return m.group(1).strip() if m else user[:400]

    # ---------------- ① 查询解析 ----------------
    def _plan(self, user: str) -> str:
        q = self._query_of(user)
        ql = q.lower()
        toks = tokenize(q)
        eng = [t for t in toks if t.isascii()]
        cons: List[Dict] = []

        years = [int(y) for y in _YEAR_RE.findall(q)]
        if years:
            cons.append({"kind": "year", "role": "hard_filter",
                         "text": f"发表年份不早于 {min(years)}",
                         "value": {"min": min(years)}, "aliases": [], "weight": 1.0})
        # 必须用词边界匹配：子串匹配会把 "Hierarchical" 里的 "chi" 误判成 CHI 会议，
        # 进而生成一条错误的硬过滤约束，静默滤掉全部正确结果。
        vs = [v for v in _VENUES if re.search(rf"\b{v}\b", ql)]
        if vs:
            cons.append({"kind": "venue", "role": "hard_filter",
                         "text": "发表于 " + "/".join(v.upper() for v in vs),
                         "value": [v.upper() for v in vs], "aliases": [],
                         "weight": 1.0})
        if any(w in ql for w in ["不要综述", "排除综述", "exclude survey"]):
            cons.append({"kind": "doc_type", "role": "negative",
                         "text": "排除综述类文献", "value": "review",
                         "aliases": ["survey", "review"], "weight": 1.0})

        bigrams = [" ".join(eng[i:i + 2]) for i in range(len(eng) - 1)]
        # Match the rule fallback: generic request phrasing is removed by
        # ``tokenize`` and two distant facets are more useful than overlapping
        # bigrams for a cross-method literature query.
        anchors = ([bigrams[0], bigrams[-1]] if len(bigrams) > 1
                   else (bigrams or eng[:2]))
        for a in anchors:
            cons.append({"kind": "topic", "role": "anchor", "text": a,
                         "value": a, "aliases": [], "weight": 1.0})
        for t in eng[:8]:
            if not any(t in c["text"] for c in cons):
                cons.append({"kind": "other", "role": "verify", "text": t,
                             "value": t, "aliases": [], "weight": 0.6})

        qtype, prior = "method_cross", 12
        if any(w in ql for w in ["which paper", "the paper that", "哪篇", "那篇"]):
            qtype, prior = "locate", 2
        elif any(w in ql for w in ["survey", "all work", "全部", "所有", "综述", "有哪些"]):
            qtype, prior = "survey", 45
        elif any(w in ql for w in ["dataset", "benchmark", "基准", "数据集"]):
            qtype, prior = "benchmark", 15
        elif any(w in ql for w in ["follow-up", "后续", "团队", "脉络", "et al"]):
            qtype, prior = "lineage", 12

        subs = [{"text": " ".join(eng[:6]), "facet": "core", "weight": 1.0}]
        if len(eng) > 6:
            subs.append({"text": " ".join(eng[3:9]), "facet": "secondary",
                         "weight": 0.8})
        # Run each distant facet independently as a weak FTS probe; their
        # concatenation is an unnecessary AND-like retrieval constraint.
        ss = [" ".join(eng[:5]), *anchors]
        if len(eng) > 4:
            ss.append(" ".join(eng[2:6]))
        return json.dumps({
            "query_type": qtype, "reasoning": "mock rule-based routing",
            "constraints": cons, "subqueries": subs,
            "search_strings": [s for s in dict.fromkeys(ss) if s.strip()],
            "n_hat_prior": prior,
        }, ensure_ascii=False)

    # ---------------- ② 查询演化 ----------------
    def _expand(self, user: str) -> str:
        titles = re.findall(r"^- (.+?) \(", user, re.M)
        used = set()
        for line in re.findall(r"^\s*[-•]?\s*(.+)$", user, re.M):
            if line.strip().startswith("- ") is False and len(line.split()) <= 8:
                used.update(tokenize(line))
        cnt = Counter()
        for t in titles:
            cnt.update(tokenize(t))
        fresh = [w for w, _ in cnt.most_common(30) if w.isascii() and w not in used]
        qs = [" ".join(fresh[i:i + 3]) for i in range(0, min(len(fresh), 9), 3)]
        return json.dumps({"queries": [q for q in qs if q.strip()][:4],
                           "reasoning": "mock term mining from confirmed titles"},
                          ensure_ascii=False)

    # ---------------- ③ 约束核验 ----------------
    def _verify(self, user: str) -> str:
        q = self._query_of(user)
        qv = Counter(tokenize(q))
        cons = re.findall(r"^\[c(\d+)\]\s*(.*)$", user, re.M)
        # 拆出候选论文块
        blocks = re.split(r"\n(?=\[\d+\]\s)", user[user.find("候选论文："):])
        results = []
        for blk in blocks:
            m = re.match(r"\[(\d+)\]\s*(.*)", blk.strip(), re.S)
            if not m:
                continue
            idx, body = int(m.group(1)), m.group(2)
            pv = Counter(tokenize(body))
            rel = min(1.0, cosine_counter(qv, pv) * 2.2)
            checks = []
            for cid, ctext in cons:
                ct = set(tokenize(ctext))
                hit = len(ct & set(pv)) / max(1, len(ct))
                status = "yes" if hit > 0.6 else ("partial" if hit > 0.25 else "no")
                checks.append({"cid": int(cid), "status": status,
                               "evidence": body[:60].replace("\n", " ")
                               if status != "no" else ""})
            results.append({"id": idx, "relevance": round(rel, 3),
                            "checks": checks,
                            "rationale": "mock 词法核验"})
        return json.dumps({"results": results}, ensure_ascii=False)

    # ---------------- ④ 结果归纳 ----------------
    def _summarize(self, user: str) -> str:
        ids = [int(x) for x in re.findall(r"^(\d+)\s*\|", user, re.M)]
        half = max(1, len(ids) // 2)
        themes = [{"name": "主线方法", "ids": ids[:half], "summary": "mock 主题归纳"}]
        if ids[half:]:
            themes.append({"name": "相关拓展", "ids": ids[half:],
                           "summary": "mock 次要分组"})
        return json.dumps({"themes": themes, "timeline": [],
                           "takeaway": "mock summary", "gaps": []},
                          ensure_ascii=False)
