"""测试套件（零依赖，不需要 pytest）。

运行：python tests/run_tests.py

重点覆盖三类：
  1. 数学性质 —— F1-Gate 的不动点、Chao1 的单调性、校准器的保序性。
     这些是可以被**证明**的性质，写成断言就是形式化论证的可执行版本。
  2. 鲁棒性 —— LLM 返回垃圾、数据源挂掉、预算耗尽、零结果时不崩溃。
  3. 回归 —— 已修复的缺陷各留一条测试，防止再犯。
"""
from __future__ import annotations

import os
import json
import sys
import tempfile
import traceback
import importlib.util
import io
import tarfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from scholarnexus.config import Config
from scholarnexus.json_records import JsonRecordError, load_json_records
from scholarnexus.core import coverage, f1gate
from scholarnexus.core.calibrate import (MixtureCalibrator, RankDecayCalibrator,
                                         evaluate_calibration,
                                         independent_mass_anchor, propensity,
                                         tail_temper)
from scholarnexus.core.fusion import adaptive_fuse, spearman
from scholarnexus.core.judge import CascadeJudge
from scholarnexus.core.pipeline import ScholarNexus
from scholarnexus.core.pasa_adaptation import (CardinalityPredictor, L2FusionModel,
                                               ProfilePolicy, l2_feature_row)
from scholarnexus.core.querylens import QueryLens, extract_quoted_spans
from scholarnexus.core.constraint_graph import (compile_constraint_graph,
                                                 match_paper, prune_constraints)
from scholarnexus.core.supervised import FEATURES, FeatureCalibrator
from scholarnexus.evalkit.public import (PublicCase, match_metrics as public_match,
                                         normalize_arxiv_id)
from scholarnexus.evalkit.metrics import set_prf, structure_score
from scholarnexus.llm import build_llm, extract_json
from scholarnexus.llm.base import LLMClient, LLMResponse
from scholarnexus.rank.rerank import (LexicalReranker, RerankItem,
                                      build_reranker, qwen_rerank_url)
from scholarnexus.retrieval.citation_graph import CitationGraph, graph_prior
from scholarnexus.retrieval.multiprobe import MultiProbe, ProbeResult
from scholarnexus.schema import (Budget, Candidate, Constraint, ConstraintKind,
                                 ConstraintRole, Paper, QueryType)
from scholarnexus.sources.base import PaperSource, SourceRegistry
from scholarnexus.sources.local_corpus import LocalCorpusSource
from scholarnexus.sources.pasa_dense import PaSaDenseSource

TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


class _FixedPredictor:
    """Pickle-friendly deterministic estimator used by adaptation tests."""

    def __init__(self, value: float):
        self.value = float(value)

    def predict(self, matrix):
        return np.full(len(matrix), self.value, dtype=np.float64)


class _EqualProfilePredictor:
    def predict(self, matrix):
        return np.zeros(len(matrix), dtype=np.float64)


# ========================================================================= #
# 1. 数学性质
# ========================================================================= #
@test
def t_f1gate_fixed_point():
    """最优截断处必须满足 p[k*] >= F1*/2 >= p[k*+1]（不动点性质）。"""
    rng = np.random.default_rng(3)
    for _ in range(50):
        p = np.sort(rng.random(rng.integers(20, 200)))[::-1]
        n = float(rng.integers(2, 80))
        chk = f1gate.verify_fixed_point(p, n)
        assert chk["holds"], f"不动点不成立: {chk}"


@test
def t_f1gate_optimal_is_prefix():
    """最优集合必为按 p 降序的前缀 —— 穷举验证。"""
    rng = np.random.default_rng(11)
    p = rng.random(14)
    n = 6.0
    d = f1gate.optimal_cutoff(p, n_hat=n)
    ps = np.sort(p)[::-1]
    best = max(range(1, len(ps) + 1),
               key=lambda k: 2 * ps[:k].sum() / (k + n))
    assert d.k == best, f"F1-Gate 选 {d.k}，穷举最优 {best}"


@test
def t_f1gate_expected_f1_bounded():
    """期望 F1 不得超过 1（一致性约束）。"""
    p = np.ones(50)
    d = f1gate.optimal_cutoff(p, n_hat=5.0)
    assert d.expected_f1 <= 1.0 + 1e-9, f"期望 F1 越界: {d.expected_f1}"


@test
def t_f1gate_empty():
    d = f1gate.optimal_cutoff([])
    assert d.k == 0 and d.expected_f1 == 0.0


@test
def t_normalize_arxiv_source_prefix():
    """本地 PaSa `arxiv:` PID 与官方 ID 必须严格等价。"""
    expected = "2111.08647"
    values = ("2111.08647", "2111.08647v3", "arxiv:2111.08647",
              "ArXiv: 2111.08647v1", "https://arxiv.org/abs/2111.08647")
    assert all(normalize_arxiv_id(value) == expected for value in values)


@test
def t_chao1_no_divergence():
    """回归测试：软计数下 f2→0 时 Chao1 曾经发散到真值的 21 倍。"""
    hits = {f"ch{i}": {f"p{j}" for j in range(30)} for i in range(2)}
    hits["ch0"] |= {f"u{j}" for j in range(40)}       # 大量单通道命中 → f1 大
    rel = {p: 0.9 for p in hits["ch0"] | hits["ch1"]}
    est = coverage.estimate(hits, relevance=rel, prior_mean=20.0)
    assert est.n_hat < est.discovered * 6, f"Chao1 发散: N̂={est.n_hat}, D={est.discovered}"
    assert est.n_hat >= est.discovered, "N̂ 不得小于已发现数"


@test
def t_coverage_monotone():
    """通道重叠越多，估出的未发现量应越小。"""
    a = {"x": {f"p{i}" for i in range(20)}, "y": {f"q{i}" for i in range(20)}}
    b = {"x": {f"p{i}" for i in range(20)}, "y": {f"p{i}" for i in range(20)}}
    ea, eb = coverage.estimate(a), coverage.estimate(b)
    assert eb.coverage >= ea.coverage, "完全重叠的覆盖率应更高"


@test
def t_tail_temper_order_preserving():
    """尾部压缩必须严格保序 —— 否则会伤召回。"""
    rng = np.random.default_rng(5)
    p = rng.random(100)
    q, alpha = tail_temper(p, target_mass=12.0)
    assert np.array_equal(np.argsort(-p), np.argsort(-q)), "尾部压缩改变了排序"
    assert abs(q.sum() - 12.0) < 0.5, f"未命中目标质量: {q.sum()}"


@test
def t_calibrator_monotone():
    """所有校准器都必须保序。"""
    rng = np.random.default_rng(7)
    s = rng.random(120)
    for cal in (MixtureCalibrator(prior_pi=0.15).fit(s),
                RankDecayCalibrator().fit_to_mass(s, 15.0)):
        p = cal.transform(s)
        assert np.array_equal(np.argsort(-s), np.argsort(-p)), \
            f"{type(cal).__name__} 未保序"


@test
def t_mixture_not_overconfident():
    """回归测试：自由方差的混合模型曾把 Σp 拉到真值 3 倍。"""
    rng = np.random.default_rng(9)
    n, k = 300, 30
    s = np.concatenate([rng.normal(0.7, 0.18, k), rng.normal(0.3, 0.18, n - k)])
    s = np.clip(s, 0, 1)
    p = MixtureCalibrator(prior_pi=k / n).fit(s).transform(s)
    assert p.sum() < k * 2.6, f"Σp={p.sum():.1f} 相对真值 {k} 过度自信"


@test
def t_propensity_range():
    p = propensity([0, 5, 500], [2026, 2020, 2015], [False, False, True])
    assert np.all((p >= 0.3) & (p <= 1.0))
    assert p[2] > p[0], "高被引老论文的标注倾向性应更高"


@test
def t_anchor_gate_on_redundant_channels():
    """回归测试：通道高度冗余时，多通道计数失效，应退回纯先验。"""
    ids = {f"p{i}" for i in range(50)}
    redundant = {"a": set(ids), "b": set(ids), "c": set(ids)}
    v = independent_mass_anchor(redundant, ids, prior_mean=2.0)
    assert abs(v - 2.0) < 1e-6, f"冗余通道未触发闸门: {v}"


# ========================================================================= #
# 2. 融合
# ========================================================================= #
@test
def t_spectral_rejects_noise():
    """纯噪声与反相关信号的权重都必须被压到极低。"""
    rng = np.random.default_rng(1)
    n = 250
    truth = rng.random(n)
    good = {f"s{i}": truth + rng.normal(0, 0.25, n) for i in range(4)}
    for name, bad in (("噪声", rng.random(n)), ("反相关", -truth)):
        sig = dict(good)
        sig["l3"] = bad
        _, rep = adaptive_fuse(sig)
        assert rep.weights["l3"] < 0.06, \
            f"{name}信号权重过高: {rep.weights['l3']:.3f}"


@test
def t_spectral_rewards_best():
    rng = np.random.default_rng(2)
    n = 250
    truth = rng.random(n)
    sig = {f"s{i}": truth + rng.normal(0, 0.4, n) for i in range(4)}
    sig["l3"] = truth + rng.normal(0, 0.05, n)
    _, rep = adaptive_fuse(sig)
    assert rep.weights["l3"] == max(rep.weights.values()), "最强信号未获最高权重"


@test
def t_fusion_handles_nan_and_constant():
    n = 60
    sig = {"a": np.arange(n, dtype=float),
           "b": np.full(n, 3.0),                   # 常量：应被剔除
           "c": np.concatenate([np.full(10, np.nan), np.arange(n - 10, dtype=float)])}
    out, rep = adaptive_fuse(sig)
    assert "b" not in rep.used, "常量信号未被剔除"
    assert len(out) == n and not np.isnan(out).any()


@test
def t_spearman_ties():
    a = np.array([1.0, 1.0, 2.0, 3.0])
    assert abs(spearman(a, a) - 1.0) < 1e-9


# ========================================================================= #
# 3. 查询理解
# ========================================================================= #
@test
def t_quoted_span_extraction():
    q = "哪篇论文提出了 Hierarchical dense retriever for query expansion？"
    spans = extract_quoted_spans(q)
    assert spans and "dense retriever" in spans[0].lower(), spans


@test
def t_venue_word_boundary():
    """回归测试：'Hierarchical' 曾被子串匹配成 CHI 会议，静默滤掉全部结果。"""
    plan = QueryLens(build_llm({"backend": "mock"})).parse(
        "Hierarchical architecture for machine learning")
    assert "venues" not in plan.api_filters(), \
        f"venue 误匹配: {plan.api_filters()}"


@test
def t_plan_always_has_anchor_and_query():
    """任何输入都必须产出可执行的计划，包括空串与纯符号。"""
    for q in ["", "???", "a", "深度学习", "x" * 500]:
        plan = QueryLens(build_llm({"backend": "mock"})).parse(q)
        assert plan.search_strings, f"无检索式: {q!r}"
        assert plan.subqueries, f"无子查询: {q!r}"


@test
def t_query_type_policy_applied():
    plan = QueryLens(build_llm({"backend": "mock"})).parse(
        "哪篇论文提出了 dense passage retrieval？")
    assert plan.query_type == QueryType.LOCATE
    assert plan.n_hat_prior < 6, f"定位型先验过大: {plan.n_hat_prior}"
    assert plan.channel_weights, "未应用通道权重策略"


@test
def t_querylens_strips_polite_prefixes_before_building_lexical_anchors():
    """A degraded/mock plan must retrieve the topic, not its request wording."""
    query = ("Could you provide me some works that focused on the intersection "
             "of algorithmic fairness and policy learning?")
    for lens in (QueryLens(None), QueryLens(build_llm({"backend": "mock"}))):
        plan = lens.parse(query)
        anchors = {item.text for item in plan.constraints
                   if item.role == ConstraintRole.ANCHOR}
        rendered = " ".join(plan.search_strings)
        assert "algorithmic fairness" in anchors, (anchors, plan.search_strings)
        assert "policy learning" in anchors, (anchors, plan.search_strings)
        assert "algorithmic fairness" in plan.search_strings, plan.search_strings
        assert "policy learning" in plan.search_strings, plan.search_strings
        assert "could you" not in rendered and "provide me" not in rendered, rendered


@test
def t_anchor_count_capped():
    """anchor 超过 2 条会让检索式退化成合取式 → 必须被就地纠正。"""
    class ManyAnchors(LLMClient):
        def _raw_chat(self, messages, stage="misc", **kw):
            import json
            return LLMResponse(text=json.dumps({
                "query_type": "survey",
                "constraints": [{"kind": "topic", "role": "anchor",
                                 "text": f"a{i}", "weight": 1.0} for i in range(6)],
                "subqueries": [], "search_strings": ["x y"], "n_hat_prior": 10}))
    plan = QueryLens(ManyAnchors("t")).parse("test query")
    n = sum(1 for c in plan.constraints if c.role == ConstraintRole.ANCHOR)
    assert n <= 2, f"anchor 未被限制: {n}"


# ========================================================================= #
# 4. 鲁棒性
# ========================================================================= #
@test
def t_extract_json_robust():
    cases = ['{"a":1}', '```json\n{"a":1}\n```', 'noise {"a":1} tail',
             "{'a':1}", '{"a":1,}', 'Here you go:\n```\n{"a": 1}\n```']
    for c in cases:
        assert extract_json(c)["a"] == 1, c


@test
def t_llm_garbage_degrades_not_crashes():
    class Garbage(LLMClient):
        def _raw_chat(self, messages, stage="misc", **kw):
            return LLMResponse(text="彻底不是 JSON 的一段话")
    plan = QueryLens(Garbage("g")).parse("对比学习用于医学影像")
    assert plan.degraded and plan.search_strings, "垃圾输出未降级到规则解析"


@test
def t_source_failure_isolated():
    """单个数据源抛异常时必须被隔离，返回空列表而非中断整次检索。"""
    class Broken(PaperSource):
        name = "broken"
        def _search(self, q, limit, filters):
            raise RuntimeError("boom")
    assert Broken().search("x") == []


@test
def t_budget_exhaustion():
    """预算耗尽时应正常返回结果，而不是抛异常。"""
    reg = SourceRegistry().register(
        LocalCorpusSource(path="data/fixture/corpus.jsonl"))
    eng = ScholarNexus(Config.load(profile="offline"), registry=reg)
    res = eng.search("contrastive learning medical imaging",
                     budget=Budget(max_llm_calls=1, max_tokens=200,
                                   max_seconds=2, max_rounds=1))
    assert res.ledger["total"]["llm_calls"] <= 2, "超出 LLM 预算"


@test
def t_empty_result_shape():
    """零命中时返回结构必须完整，前端与评测方不该因此崩溃。"""
    reg = SourceRegistry().register(LocalCorpusSource(papers=[]))
    eng = ScholarNexus(Config.load(profile="offline"), registry=reg)
    res = eng.search("zzz nonexistent topic qqq")
    d = res.to_dict()
    for k in ("core", "partial", "views", "ledger", "plan"):
        assert k in d, f"缺字段 {k}"
    assert d["core"] == []


@test
def t_json_record_loader_accepts_multiline_and_rejects_truncation():
    """数据记录可以跨物理行，但尾部不完整绝不能被静默忽略。"""
    with tempfile.TemporaryDirectory() as td:
        good = Path(td) / "good.jsonl"
        good.write_text('{\n  "qid": "a",\n  "text": "line1\\nline2"\n}\n{"qid":"b"}\n',
                        encoding="utf-8")
        rows = load_json_records(good)
        assert [row["qid"] for row in rows] == ["a", "b"]
        assert rows[0]["text"] == "line1\nline2"

        bad = Path(td) / "bad.jsonl"
        bad.write_text('{"qid":"a"}\n{"qid":"b", "text":"cut', encoding="utf-8")
        try:
            load_json_records(bad)
            raise AssertionError("尾部截断未被拒绝")
        except JsonRecordError as exc:
            assert exc.record_number == 2 and exc.line == 2, exc


@test
def t_deterministic():
    """回归测试：并发聚合曾依赖线程调度，导致同一输入结果漂移。"""
    reg = SourceRegistry().register(
        LocalCorpusSource(path="data/fixture/corpus.jsonl"))
    eng = ScholarNexus(Config.load(profile="offline"), registry=reg)
    q = "retrieval augmented generation 有哪些代表工作"
    a = [c.pid for c in eng.search(q).core]
    b = [c.pid for c in eng.search(q).core]
    assert a == b, "同一查询两次结果不一致"


@test
def t_l2_input_budget_preserves_wide_l1_admission():
    """L2 的计算预算不得反向缩小 L1 候选 admission。"""
    cfg = Config.load(profile="offline")
    cfg.pipeline.update({"max_rounds": 1, "per_query_limit": 20,
                         "l1_keep": 20, "l2_input_keep": 2, "l2_keep": 2,
                         "citation_expand_seeds": 0, "enable_query_evolution": False})
    reg = SourceRegistry().register(
        LocalCorpusSource(path="data/fixture/corpus.jsonl"))
    result = ScholarNexus(cfg, registry=reg).search(
        "contrastive learning medical imaging",
        budget=Budget(max_llm_calls=0, max_api_calls=0, max_rounds=1,
                      max_seconds=5, max_l3_judgments=0))
    judge_events = [event for event in result.trace if event.get("stage") == "judge"]
    assert judge_events and judge_events[0]["l1_kept"] >= judge_events[0]["l2_input"], judge_events
    assert judge_events[0]["l2_input"] <= 2, judge_events


@test
def t_candidate_audit_is_observational():
    """开启来源审计不得改变无引用本地流水线的排序或最终集合。"""
    common = {"max_rounds": 1, "per_query_limit": 20, "l1_keep": 20,
              "l2_keep": 20, "citation_expand_seeds": 0,
              "enable_query_evolution": False}
    plain_cfg = Config.load(profile="offline")
    plain_cfg.pipeline.update(common)
    audit_cfg = Config.load(profile="offline")
    audit_cfg.pipeline.update({**common, "candidate_audit": True})
    query = "contrastive learning medical imaging"
    budget = Budget(max_llm_calls=0, max_api_calls=0, max_rounds=1,
                    max_seconds=5, max_l3_judgments=0)
    plain = ScholarNexus(
        plain_cfg, registry=SourceRegistry().register(
            LocalCorpusSource(path="data/fixture/corpus.jsonl"))).search(query, budget=budget)
    audited = ScholarNexus(
        audit_cfg, registry=SourceRegistry().register(
            LocalCorpusSource(path="data/fixture/corpus.jsonl"))).search(query, budget=budget)
    assert [c.pid for c in plain.all_candidates] == [c.pid for c in audited.all_candidates]
    assert [c.pid for c in plain.core + plain.partial] == [c.pid for c in audited.core + audited.partial]
    records = audited.candidate_audit.get("candidates") or {}
    assert records and not plain.candidate_audit, audited.candidate_audit
    assert all((rec.get("first_seen") or {}).get("kind") == "retrieval"
               for rec in records.values()), records


@test
def t_multiprobe_can_isolate_and_tag_a_raw_question_dense_probe():
    """A raw dense probe must not also run FTS or lose its distinct channel."""
    class RecordingSource(PaperSource):
        def __init__(self, name):
            super().__init__()
            self.name = name
            self.calls = []

        def _search(self, query, limit, filters):
            self.calls.append((query, limit, dict(filters)))
            return [Paper(pid=f"{self.name}:{query}", title=f"{self.name} hit",
                          retrieval_score=0.77 if self.name == "pasa_local_dense" else None)]

    lexical = RecordingSource("pasa")
    dense = RecordingSource("pasa_local_dense")
    registry = SourceRegistry().register(lexical).register(dense)
    plan = type("Plan", (), {"api_filters": staticmethod(lambda: {})})()
    result = MultiProbe(registry).probe(
        plan, ["complete natural-language question"], per_query_limit=7,
        source_names=["pasa_local_dense"], channel_tag="raw_question",
        audit_provenance=True)
    assert lexical.calls == [], lexical.calls
    assert dense.calls == [("complete natural-language question", 7, {})], dense.calls
    assert list(result.rank_lists) == ["dense:pasa_local_minilm:raw_question"], result.rank_lists
    candidate = next(iter(result.candidates.values()))
    assert candidate.provenance[0]["channel"] == "dense:pasa_local_minilm:raw_question"
    assert candidate.s_dense == 0.77, candidate.s_dense


@test
def t_selector_protected_admission_keeps_existing_channel_quotas():
    """Selector-protected dense discoveries must not erase lexical/citation quotas."""
    def candidate(pid, score, channels):
        item = Candidate(Paper(pid=pid, title=pid))
        item.s_l1 = score
        item.channels.update(channels)
        return item

    lexical = candidate("lexical", .95, {"lexical:pasa:abstract"})
    citation = candidate("citation", .90, {"cite_bwd_section"})
    dense = candidate("dense", .10, {"dense:pasa_local_minilm:raw_question"})
    ranked = [lexical, citation, dense]
    kept = CascadeJudge._preserve_channel_quotas(
        ranked, 3, {"lexical:pasa:abstract": 1, "cite_bwd_section": 1},
        protected=[dense])
    assert {cand.pid for cand in kept} == {"lexical", "citation", "dense"}, kept
    assert [cand.pid for cand in kept] == ["lexical", "citation", "dense"], kept


@test
def t_selector_sidecar_preserves_membership_through_l2_without_score_boost():
    """A semantic sidecar must survive L2 capacity but retain ordinary L2 order."""
    class FixedReranker:
        sigma = 0.16

        @staticmethod
        def score(_query, _items):
            return np.asarray([0.90, 0.80, 0.10], dtype=np.float64)

    first = Candidate(Paper(pid="first", title="first"))
    second = Candidate(Paper(pid="second", title="second"))
    dense = Candidate(Paper(pid="dense", title="dense"))
    plan = type("Plan", (), {"raw_query": "query", "constraints": []})()
    kept = CascadeJudge(FixedReranker()).l2_rerank(
        [first, second, dense], plan, keep=2, protected=[dense])
    assert [candidate.pid for candidate in kept] == ["first", "dense"], kept
    assert dense.s_l2 == 0.10 and first.s_l2 == 0.90


@test
def t_l2_rank_blend_is_opt_in_and_uses_l1_signal():
    """Widened L2 experiments may blend L1, while the baseline stays unchanged."""
    class FixedReranker:
        sigma = 0.16

        @staticmethod
        def score(_query, _items):
            return np.asarray([0.90, 0.80, 0.10], dtype=np.float64)

    def rows():
        values = [("first", 0.10), ("second", 0.20), ("dense", 0.95)]
        output = []
        for pid, l1 in values:
            candidate = Candidate(Paper(pid=pid, title=pid))
            candidate.s_l1 = l1
            output.append(candidate)
        return output

    plan = type("Plan", (), {"raw_query": "query", "constraints": []})()
    baseline = CascadeJudge(FixedReranker()).l2_rerank(rows(), plan, keep=3)
    blended = CascadeJudge(FixedReranker(), cfg={"l2_rank_blend_l1_weight": 0.75}).l2_rerank(
        rows(), plan, keep=3)
    assert [candidate.pid for candidate in baseline] == ["first", "second", "dense"]
    assert [candidate.pid for candidate in blended] == ["dense", "second", "first"]


@test
def t_dense_admission_gpu_release_keeps_source_selection_explicit():
    """Only configured raw dense sources may release accelerator state."""
    class ReleasableSource(PaperSource):
        def __init__(self, name):
            super().__init__()
            self.name = name
            self.released = 0

        def release_accelerators(self):
            self.released += 1

    raw = ReleasableSource("pasa_local_dense")
    other = ReleasableSource("pasa")
    registry = SourceRegistry().register(raw).register(other)
    ScholarNexus._release_raw_dense_accelerators(registry, ["pasa_local_dense"])
    assert raw.released == 1 and other.released == 0, (raw.released, other.released)


@test
def t_config_degradation_chain():
    """无 Key 的云端配置必须就地降级，而不是运行到一半 401。"""
    for env in ("DASHSCOPE_API_KEY",):
        os.environ.pop(env, None)
    cfg = Config.load(profile="cloud").resolved()
    assert len(cfg.degradations) == 4, cfg.degradations
    assert cfg.llm_fast["backend"] == "mock"


@test
def t_local_embedding_config_does_not_require_api_key():
    """本地权重 reranker 绝不能因缺云端 Key 被误降级。"""
    cfg = Config.load(profile="offline")
    cfg.reranker = {"backend": "local_embedding", "model_path": "local-model"}
    resolved = cfg.resolved()
    assert resolved.reranker["backend"] == "local_embedding", resolved.degradations


@test
def t_pasa_bge_selector_head_config_does_not_require_api_key():
    """The validated local Selector-SFT backend must not be cloud-degraded."""
    cfg = Config.load(profile="offline")
    cfg.reranker = {
        "backend": "pasa_bge_selector_head", "model_path": "local-model",
        "selector_head_path": "local-head.joblib", "device": "cuda",
    }
    resolved = cfg.resolved()
    assert resolved.reranker["backend"] == "pasa_bge_selector_head", resolved.degradations


# ========================================================================= #
# 5. 判定与图
# ========================================================================= #
@test
def t_evidence_alignment_rejects_hallucination():
    """模型声称满足但给出论文里不存在的"原文" → 必须降级为 unknown。"""
    c = Candidate(paper=Paper(pid="x", title="Contrastive learning for segmentation",
                              abstract="We propose a contrastive objective."))
    ok = CascadeJudge._verify_evidence("contrastive objective", c)
    bad = CascadeJudge._verify_evidence("reinforcement learning with human feedback", c)
    assert ok and not bad, f"证据校验失效: ok={ok} bad={bad}"


@test
def t_l0_missing_metadata_passes():
    """元数据缺失不等于违反约束 —— 误杀比放行代价大得多。"""
    from scholarnexus.schema import Constraint, ConstraintKind, QueryPlan
    plan = QueryPlan("q", QueryType.SURVEY,
                     [Constraint(ConstraintKind.YEAR, ConstraintRole.HARD_FILTER,
                                 ">=2022", {"min": 2022})], [], ["x"], 10)
    j = CascadeJudge(LexicalReranker())
    cands = [Candidate(paper=Paper(pid="a", title="A paper with no year at all")),
             Candidate(paper=Paper(pid="b", title="Old paper title here", year=2010))]
    kept = j.l0_filter(cands, plan)
    assert [c.pid for c in kept] == ["a"], [c.pid for c in kept]


@test
def t_l1_channel_quotas_preserve_unique_discovery():
    """全局 L1 截断不得删掉某个独立通道唯一发现的候选。"""
    rows = []
    for pid, score, channel in (
        ("a0", 0.99, "lexical:pasa:abstract"),
        ("a1", 0.98, "lexical:pasa:abstract"),
        ("a2", 0.97, "lexical:pasa:abstract"),
        ("dense", 0.42, "dense:pasa"),
        ("section", 0.39, "cite_bwd_section"),
    ):
        cand = Candidate(Paper(pid=pid, title=f"Candidate {pid}"))
        cand.s_l1 = score
        cand.channels.add(channel)
        rows.append(cand)
    plain = CascadeJudge._preserve_channel_quotas(rows, 3, {})
    kept = CascadeJudge._preserve_channel_quotas(
        rows, 3, {"dense:pasa": 1, "cite_bwd_section": 1})
    assert [c.pid for c in plain] == ["a0", "a1", "a2"]
    assert {c.pid for c in kept} >= {"dense", "section"}, [c.pid for c in kept]


@test
def t_l1_native_dense_weight_is_opt_in():
    """Native dense cosine may affect L1 only in an explicit ablation."""
    from scholarnexus.schema import QueryPlan
    plan = QueryPlan("query", QueryType.METHOD_CROSS, [], [], ["query"], 5.0)
    candidate = Candidate(Paper(pid="dense", title="dense candidate"),
                          channels={"dense:pasa_local_minilm"},
                          channel_ranks={"dense:pasa_local_minilm": 4})
    candidate.s_dense = 0.91
    baseline = CascadeJudge(LexicalReranker())
    baseline.l1_rank([candidate], plan, keep=1)
    old_score = candidate.s_l1
    candidate.s_l1 = 0.0
    weighted = CascadeJudge(LexicalReranker(), cfg={"l1_dense_weight": 1.0})
    weighted.l1_rank([candidate], plan, keep=1)
    assert old_score != candidate.s_l1
    assert abs(candidate.s_l1 - 0.91) < 1e-9


@test
def t_l2_channel_quota_preserves_citation_candidate_without_score_boost():
    """L2 admission 可保护 citation 候选，但仍必须维持 L1 分数顺序。"""
    rows = []
    for pid, score, channel in (
        ("lexical0", 0.99, "lexical:pasa:abstract"),
        ("lexical1", 0.98, "lexical:pasa:abstract"),
        ("citation", 0.42, "cite_bwd_section"),
        ("dense", 0.37, "dense:pasa_local_minilm:raw_question"),
    ):
        cand = Candidate(Paper(pid=pid, title=f"Candidate {pid}"))
        cand.s_l1 = score
        cand.channels.add(channel)
        rows.append(cand)
    plain = CascadeJudge._preserve_channel_quotas(rows, 2, {})
    kept = CascadeJudge._preserve_channel_quotas(
        rows, 2, {"cite_bwd_section": 1})
    assert [c.pid for c in plain] == ["lexical0", "lexical1"]
    assert [c.pid for c in kept] == ["lexical0", "citation"], [c.pid for c in kept]
    assert kept[0].s_l1 > kept[1].s_l1


@test
def t_l2_quota_counterfactual_replays_runtime_membership():
    """训练后审计的 L2 配额重放必须和运行时 admission 完全一致。"""
    from scripts.analyze_pasa_l2_admission_counterfactual import select_l2_input

    rows, records = [], {}
    for pid, score, channels, ranks in (
        ("lexical0", .99, {"lexical:pasa:abstract"}, {}),
        ("lexical1", .98, {"lexical:pasa:abstract"}, {}),
        ("citation_late", .42, {"cite_bwd_section"}, {"cite_bwd_section": 0}),
        ("citation_second", .38, {"cite_bwd_section"}, {"cite_bwd_section": 1}),
    ):
        cand = Candidate(Paper(pid=pid, title=f"Candidate {pid}"))
        cand.s_l1 = score
        cand.channels.update(channels)
        cand.channel_ranks.update(ranks)
        rows.append(cand)
        records[pid] = {"stages": {"l1": True}, "scores": {"l1": score},
                        "channels": sorted(channels), "channel_ranks": ranks}
    ranked = sorted(rows, key=lambda cand: (-cand.s_l1, cand.pid))
    runtime_regular = CascadeJudge._preserve_channel_quotas(
        ranked, 2, {"cite_bwd_section": 1})
    replay_regular = select_l2_input(
        records, 2, channel="cite_bwd_section", quota=1, mode="regular")
    runtime_unique = CascadeJudge._preserve_channel_quotas(
        ranked, 2, {}, {"cite_bwd_section": 1})
    replay_unique = select_l2_input(
        records, 2, channel="cite_bwd_section", quota=1, mode="unique")
    assert {cand.pid for cand in runtime_regular} == set(replay_regular)
    assert {cand.pid for cand in runtime_unique} == set(replay_unique)


@test
def t_unique_channel_quota_uses_source_rank_without_score_boost():
    """独有 dense 的 admission 按 dense 原始 rank，输出仍按 L1 分排序。"""
    lexical = Candidate(Paper(pid="lex", title="Lexical"))
    lexical.channels.add("lexical:pasa:abstract")
    lexical.s_l1 = 0.95
    dense_first = Candidate(Paper(pid="dense_first", title="Dense first"))
    dense_first.channels.add("dense:pasa_local_minilm")
    dense_first.channel_ranks["dense:pasa_local_minilm"] = 0
    dense_first.s_l1 = 0.20
    dense_second = Candidate(Paper(pid="dense_second", title="Dense second"))
    dense_second.channels.add("dense:pasa_local_minilm")
    dense_second.channel_ranks["dense:pasa_local_minilm"] = 1
    dense_second.s_l1 = 0.90
    dual = Candidate(Paper(pid="dual", title="Dual"))
    dual.channels.update({"dense:pasa_local_minilm", "lexical:pasa:abstract"})
    dual.channel_ranks["dense:pasa_local_minilm"] = 0
    dual.s_l1 = 0.99
    ranked = [dual, lexical, dense_second, dense_first]
    kept = CascadeJudge._preserve_channel_quotas(
        ranked, 2, {}, {"dense:pasa_local_minilm": 1})
    assert {c.pid for c in kept} == {"dual", "dense_first"}, [c.pid for c in kept]
    assert [c.pid for c in kept] == ["dual", "dense_first"], [c.pid for c in kept]


@test
def t_ppr_and_cocite():
    g = CitationGraph()
    for a, b in [("c1", "s1"), ("c1", "x1"), ("c2", "s1"), ("c2", "x1"),
                 ("c3", "s1"), ("s1", "old"), ("y1", "unrelated")]:
        g.add_edge(a, b)
    pr = graph_prior(g, {"s1": 1.0})
    assert pr.get("x1", 0) > pr.get("y1", 0), "共被引论文的图先验应更高"


@test
def t_cocite_ties_have_a_stable_pid_order():
    """Equal graph prior must never let set/hash iteration alter RRF ranks."""
    def run(order):
        out = ProbeResult(candidates={
            pid: Candidate(Paper(pid=pid, title=f"Candidate {pid}"))
            for pid in order
        })
        for cand in out.candidates.values():
            cand.s_constraint = 1.0
        # Symmetric one-hop neighbours of the same seed have equal graph
        # priors; reverse dictionary insertion must still yield the same list.
        out.graph.add_edge("seed", "a")
        out.graph.add_edge("seed", "z")
        MultiProbe(SourceRegistry()).apply_graph_signal(
            out, {"seed": 1.0}, min_constraint=0.0)
        return out.rank_lists["cocite"]
    assert run(["z", "a"]) == run(["a", "z"]) == ["a", "z"]


@test
def t_reranker_ranks_sensibly():
    r = LexicalReranker()
    items = [RerankItem("a", "Graph neural networks for molecules"),
             RerankItem("b", "Long context retrieval with dense retrievers"),
             RerankItem("c", "Cooking recipes for pasta")]
    top = r.rerank("dense retrieval for long context", items)[0][0]
    assert top.pid == "b", top.pid


@test
def t_local_embedding_reranker_missing_model_falls_back():
    """本地 embedding 权重不可用时，检索必须退回可用的词法 L2。"""
    reranker = build_reranker({"backend": "local_embedding",
                               "model_path": "__missing_model__", "device": "cpu"})
    items = [RerankItem("good", "Graph neural network retrieval", "neural retrieval"),
             RerankItem("bad", "Protein folding", "structure biology")]
    scores = reranker.score("neural graph retrieval", items)
    assert scores.shape == (2,) and np.all(np.isfinite(scores)), scores
    assert scores[0] > scores[1], scores


@test
def t_dedup_merges_versions():
    """同一篇论文的 arXiv 版与期刊版必须合并，且通道集合要并起来 ——
    否则捕获–再捕获会把一篇算成两个个体。"""
    p1 = Paper(pid="arxiv:1", title="Deep residual learning for image recognition",
               doi="10.1/x", abstract="short")
    p2 = Paper(pid="s2:1", title="Deep residual learning for image recognition",
               doi="10.1/x", abstract="a much longer abstract with more detail")
    out = ProbeResult(candidates={})
    mp = MultiProbe(SourceRegistry())
    mp._absorb(out, [p1], "lexical:arxiv", 0)
    mp._absorb(out, [p2], "dense:s2", 0)
    mp._dedupe_fuzzy(out)
    assert len(out.candidates) == 1, f"未合并: {list(out.candidates)}"
    c = next(iter(out.candidates.values()))
    assert len(c.channels) == 2, f"通道未并集: {c.channels}"
    assert "longer abstract" in c.paper.abstract, "未保留信息量更大的摘要"


@test
def t_graph_signal_requires_constraint_match():
    """图中心性不能替代查询匹配，低约束候选不得因共引而被抬高。"""
    good = Candidate(Paper(pid="good", title="matching paper"))
    bad = Candidate(Paper(pid="bad", title="generic highly cited paper"))
    good.s_constraint, bad.s_constraint = 0.8, 0.1
    out = ProbeResult(candidates={"good": good, "bad": bad})
    # 两个候选都与种子在图上相邻，确保测试的是一致性门槛而不是图缺失。
    out.graph.add_edge("seed", "good")
    out.graph.add_edge("seed", "bad")
    MultiProbe(SourceRegistry()).apply_graph_signal(
        out, {"seed": 1.0}, min_constraint=0.42)
    assert good.s_graph > 0.0
    assert bad.s_graph == 0.0


@test
def t_pasa_fts_source_returns_arxiv_id(tmp_path=None):
    """PaSa 本地源必须返回可直接和公开集 answer_arxiv_id 对齐的 ID。"""
    import sqlite3
    import tempfile
    from pathlib import Path
    from scholarnexus.sources.pasa_corpus import PaSaCorpusSource
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "papers.sqlite"
        con = sqlite3.connect(db)
        con.execute("CREATE VIRTUAL TABLE papers USING fts5(arxiv_id UNINDEXED, title, abstract)")
        con.execute("INSERT INTO papers VALUES (?, ?, ?)",
                    ("2009.02040", "Multivariate Time-series Anomaly Detection",
                     "Graph attention network reconstruction based anomaly detection"))
        con.commit()
        con.close()
        rows = PaSaCorpusSource(index_path=str(db)).search(
            "reconstruction based graph attention", limit=5)
    assert rows and rows[0].arxiv_id == "2009.02040"
    assert rows[0].pid == "arxiv:2009.02040"


@test
def t_pasa_section_expansion_is_query_controlled():
    """PaSa reference expansion must read selected sections, not every reference."""
    import sqlite3
    import tempfile
    import zipfile
    from pathlib import Path
    from scholarnexus.sources.pasa_corpus import PaSaCorpusSource, _title_key

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        db = root / "papers.sqlite"
        con = sqlite3.connect(db)
        con.execute("CREATE VIRTUAL TABLE papers USING fts5(arxiv_id UNINDEXED, title, abstract)")
        con.execute("INSERT INTO papers VALUES (?, ?, ?)", ("1", "Seed Paper", "seed"))
        con.commit()
        con.close()
        ids = {"1": "Seed Paper", "2": "Related Target", "3": "Method Noise"}
        id_map = root / "id2paper.json"
        id_map.write_text(json.dumps(ids), encoding="utf-8")
        archive = root / "papers.zip"
        rows = {
            "Seed Paper": {
                "title": "Seed Paper", "abstract": "seed",
                "sections": {
                    "1 Introduction": ["Method Noise"],
                    "2 Related Work": ["Related Target"],
                    "3 Optimization Details": ["Method Noise"],
                }, "source": "fixture",
            },
            "Related Target": {"title": "Related Target", "abstract": "target",
                               "sections": {}, "source": "fixture"},
            "Method Noise": {"title": "Method Noise", "abstract": "noise",
                             "sections": {}, "source": "fixture"},
        }
        with zipfile.ZipFile(archive, "w") as z:
            for title, row in rows.items():
                z.writestr(_title_key(title), json.dumps(row))
        source = PaSaCorpusSource(index_path=str(db), paper_zip=str(archive),
                                  id_map=str(id_map), reference_hydrate_limit=5)
        papers = source.references_for_query(
            "arxiv:1", "find prior related literature", limit=10, max_sections=1)
        source.close()
    assert [p.arxiv_id for p in papers] == ["2"], [p.arxiv_id for p in papers]


@test
def t_pasa_crawler_section_feature_schema():
    """Crawler-SFT section features stay row-aligned in batched inference."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from scholarnexus.section_selector import FEATURE_NAMES, make_features

    word = TfidfVectorizer().fit([
        "graph neural networks", "related work", "method introduction",
        "anchor paper abstract graph learning",
    ])
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 4)).fit([
        "graph neural networks", "related work", "method introduction",
    ])
    x = make_features(
        word, char,
        ["graph neural networks", "graph neural networks"],
        ["Anchor paper", "Anchor paper"],
        ["A graph learning abstract", "A graph learning abstract"],
        ["Related Work", "Graph Neural Network Method"], [0, 1], [2, 2],
    )
    assert x.shape == (2, len(FEATURE_NAMES))
    assert x[1, 0] > x[0, 0], x[:, 0]
    assert 0.0 <= x[0, 9] <= 1.0 and 0.0 <= x[1, 9] <= 1.0


@test
def t_pasa_cited_title_set_prefers_query_evidence():
    """Section citation-title MaxSim must favor direct query evidence."""
    from sklearn.feature_extraction.text import HashingVectorizer
    from scholarnexus.sources.pasa_corpus import PaSaCorpusSource

    source = object.__new__(PaSaCorpusSource)
    source.section_cited_title_top_k = 8
    vectorizer = HashingVectorizer(stop_words="english", ngram_range=(1, 2),
                                   n_features=2 ** 12, alternate_sign=False, norm="l2")
    scores = source._cited_title_set_scores(
        vectorizer, "graph neural network explanation",
        ["Related Work", "Implementation"],
        {"Related Work": ["Explaining Graph Neural Networks with Subgraph Methods"],
         "Implementation": ["Image classification experiments"]},
    )
    assert scores[0] > scores[1], scores


@test
def t_pasa_dynamic_second_section_is_narrow_and_label_blind():
    """低分、明显落后的第二节应被删；接近并列时应保留。"""
    from scholarnexus.sources.pasa_corpus import PaSaCorpusSource

    source = object.__new__(PaSaCorpusSource)
    source.section_dynamic_second_margin = 0.08
    source.section_dynamic_second_min_score = 0.70
    assert source._choose_sections([("A", .80), ("B", .60)], 2) == [("A", .80)]
    assert source._choose_sections([("A", .80), ("B", .75)], 2) == [("A", .80), ("B", .75)]
    assert source._choose_sections([("A", .90), ("B", .71)], 2) == [("A", .90), ("B", .71)]


# ========================================================================= #
# 6. 指标与端到端
# ========================================================================= #
@test
def t_set_prf():
    m = set_prf(["a", "b", "c"], ["b", "c", "d"])
    assert m.tp == 2 and abs(m.f1 - 2 / 3) < 1e-9


@test
def t_set_prf_dedups():
    m = set_prf(["a", "a", "b"], ["a", "b"])
    assert m.n_pred == 2 and abs(m.f1 - 1.0) < 1e-9


@test
def t_structure_score_intent_aware():
    """给定位型查询硬塞关系图不该得分 —— 结构分要求视图与意图匹配。"""
    base = {"query_type": "locate",
            "matrix": {"columns": ["a", "b", "c"],
                       "rows": [{"cells": [{"status": "yes", "evidence": "e"}]}]}}
    with_view = dict(base, disambiguation={"rows": [1]})
    assert structure_score(with_view) > structure_score(base)


@test
def t_end_to_end_offline():
    reg = SourceRegistry().register(
        LocalCorpusSource(path="data/fixture/corpus.jsonl"))
    eng = ScholarNexus(Config.load(profile="offline"), registry=reg)
    res = eng.search("把 contrastive learning 用于 medical image segmentation 的工作有哪些")
    assert len(res.core) > 0, "无结果"
    assert res.views.get("matrix", {}).get("rows"), "缺约束满足矩阵"
    assert res.ledger["total"]["wall_seconds"] < 60
    from scholarnexus.present.insightboard import render_markdown
    assert "约束满足矩阵" in render_markdown(res)


@test
def t_tiers_are_prefix_of_ranking():
    """core 必须是排序前缀，partial 紧随其后 —— 否则 Oracle 对比不成立。"""
    reg = SourceRegistry().register(
        LocalCorpusSource(path="data/fixture/corpus.jsonl"))
    eng = ScholarNexus(Config.load(profile="offline"), registry=reg)
    res = eng.search("retrieval augmented generation 代表工作")
    ids = [c.pid for c in res.all_candidates]
    n_core = len(res.core)
    assert [c.pid for c in res.core] == ids[:n_core]
    assert [c.pid for c in res.partial] == ids[n_core:n_core + len(res.partial)]


@test
def t_seed_l2_empty_eligible_set_skips_expansion_not_search():
    """A strict seed gate may yield no anchor; L2 strategy must still rank."""
    cfg = Config.load(profile="offline")
    cfg.pipeline["citation_seed_rerank"] = "l2"
    cfg.pipeline["citation_seed_min_constraint"] = 1.1  # constraint scores are bounded by 1
    reg = SourceRegistry().register(
        LocalCorpusSource(path="data/fixture/corpus.jsonl"))
    res = ScholarNexus(cfg, registry=reg).search(
        "retrieval augmented generation representative work")
    assert res.all_candidates, "empty anchor set must not abort final ranking"


@test
def t_seed_rerank_unknown_strategy_is_explicit_error():
    """Typos must not silently degrade to a different citation policy."""
    cfg = Config.load(profile="offline")
    cfg.pipeline["citation_seed_rerank"] = "definitely-unknown"
    reg = SourceRegistry().register(
        LocalCorpusSource(path="data/fixture/corpus.jsonl"))
    try:
        ScholarNexus(cfg, registry=reg).search(
            "retrieval augmented generation representative work")
    except ValueError as exc:
        assert "unknown citation_seed_rerank" in str(exc)
    else:
        raise AssertionError("unknown citation seed strategy must fail explicitly")


# ========================================================================= #
# 7. 融合版新增能力
# ========================================================================= #
@test
def t_constraint_graph_or_and_not_semantics():
    cons = [
        Constraint(ConstraintKind.TOPIC, ConstraintRole.ANCHOR,
                   "retrieval augmented generation", aliases=["RAG"]),
        Constraint(ConstraintKind.DOC_TYPE, ConstraintRole.NEGATIVE,
                   "排除综述", value="review", aliases=["survey"]),
    ]
    graph = compile_constraint_graph(cons)
    article = Paper(pid="a", title="RAG for grounded question answering",
                    abstract="retrieval augmented generation with citations")
    review = Paper(pid="b", title="A survey of RAG",
                   abstract="review of retrieval augmented generation")
    good, bad = match_paper(graph, article), match_paper(graph, review)
    assert good.score > bad.score
    assert good.negative_penalty == 0 and bad.negative_penalty > 0
    assert graph["semantics"].startswith("AND")


@test
def t_constraint_subsumption_merges_aliases():
    cons = [
        Constraint(ConstraintKind.METHOD, ConstraintRole.VERIFY,
                   "graph neural network", aliases=["GNN"]),
        Constraint(ConstraintKind.METHOD, ConstraintRole.VERIFY,
                   "graph neural networks", aliases=["message passing network"]),
    ]
    out = prune_constraints(cons)
    assert len(out) == 1
    joined = " ".join(out[0].aliases).lower()
    assert "gnn" in joined or "message passing" in joined


@test
def t_public_benchmark_matches_title_and_arxiv():
    case = PublicCase("q", "x", ["A Great Paper"], ["2401.00001"])
    papers = [Paper(pid="x", title="A different version", arxiv_id="2401.00001v2")]
    m = public_match(papers, case)
    assert m["hits"] == 1 and abs(m["f1"] - 1.0) < 1e-9


@test
def t_pasa_strict_id_scoring_rejects_title_only_match():
    """PaSa 有 answer_arxiv_id，公开分数不得被同名/缺 ID 的结果虚增。"""
    case = PublicCase("q", "x", ["A Great Paper"], ["2401.00001"])
    papers = [Paper(pid="x", title="A Great Paper", arxiv_id="")]
    m = public_match(papers, case, strict_arxiv_ids=True)
    assert m["hits"] == 0 and m["f1"] == 0.0


@test
def t_openalex_extracts_nonprimary_arxiv_location():
    """OpenAlex 的 DOI 主页面不能遮蔽同记录的 arXiv 身份。"""
    from scholarnexus.sources.openalex import _arxiv_id
    work = {
        "ids": {"openalex": "https://openalex.org/W1"},
        "primary_location": {"landing_page_url": "https://doi.org/10.1/example"},
        "locations": [{"landing_page_url": "https://arxiv.org/abs/2401.00001v2"}],
    }
    assert _arxiv_id(work) == "2401.00001v2"


@test
def t_supervised_calibrator_is_bounded():
    cal = FeatureCalibrator(coef=np.ones(len(FEATURES)), intercept=-1.0,
                            mean=np.zeros(len(FEATURES)),
                            scale=np.ones(len(FEATURES)), blend=0.5)
    cand = Candidate(Paper(pid="p", title="Relevant paper", year=2025))
    cand.s_l1 = cand.s_constraint = 0.8
    pred = cal.predict([cand])
    assert pred.shape == (1,) and 0.0 < pred[0] < 1.0


@test
def t_default_strategy_is_low_cost():
    reg = SourceRegistry().register(
        LocalCorpusSource(path="data/fixture/corpus.jsonl"))
    eng = ScholarNexus(Config.load(profile="offline"), registry=reg)
    res = eng.search("retrieval augmented generation 代表工作")
    assert res.rounds == 1
    assert res.ledger["total"]["llm_calls"] <= 2
    assert eng.cfg.pipeline["l3_policy"] == "disabled"


@test
def t_qwen_rerank_endpoint_mapping():
    url = qwen_rerank_url("https://dashscope.aliyuncs.com/compatible-mode/v1")
    assert url.endswith("/compatible-api/v1/reranks")


@test
def t_pasa_dense_exact_ranking_without_gold_insertion():
    """Dense source ranks the stored corpus only and preserves strict arXiv IDs."""
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        np.save(root / "vectors.npy", np.asarray(
            [[0.0, 1.0], [1.0, 0.0], [0.8, 0.6]], dtype=np.float32))
        (root / "manifest.json").write_text(json.dumps({
            "model": "fixture", "records": 3, "dimension": 2,
            "normalized": True}), encoding="utf-8")
        with (root / "papers.jsonl").open("w", encoding="utf-8") as stream:
            for aid, title in (("1", "orthogonal"), ("2", "exact"),
                               ("3", "near")):
                stream.write(json.dumps({"arxiv_id": aid, "title": title}) + "\n")
        source = PaSaDenseSource(str(root), block_size=256)
        source._embed_query = lambda _query: np.asarray([1.0, 0.0], dtype=np.float32)
        papers = source._search("label-blind query", 2, {})
        assert [paper.arxiv_id for paper in papers] == ["2", "3"]
        assert [paper.pid for paper in papers] == ["arxiv:2", "arxiv:3"]
        source.close()


@test
def t_zero_llm_budget_uses_rule_plan():
    reg = SourceRegistry().register(
        LocalCorpusSource(path="data/fixture/corpus.jsonl"))
    eng = ScholarNexus(Config.load(profile="offline"), registry=reg)
    res = eng.search("retrieval augmented generation", budget=Budget(
        max_llm_calls=0, max_api_calls=10, max_rounds=1))
    assert res.plan.degraded and res.ledger["total"]["llm_calls"] == 0


@test
def t_specter_archive_member_guard_rejects_path_escape():
    """The offline model installer must never extract an unsafe tar member."""
    spec = importlib.util.spec_from_file_location(
        "extract_specter2_test",
        Path(__file__).resolve().parents[1] / "scripts" / "extract_specter2.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as raw:
        safe = Path(raw) / "safe.tar.gz"
        with tarfile.open(safe, "w:gz") as archive:
            info = tarfile.TarInfo("base/config.json")
            payload = b"{}"
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        with tarfile.open(safe, "r:gz") as archive:
            assert len(module._safe_members(archive)) == 1
        unsafe = Path(raw) / "unsafe.tar.gz"
        with tarfile.open(unsafe, "w:gz") as archive:
            info = tarfile.TarInfo("../../outside")
            payload = b"x"
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        with tarfile.open(unsafe, "r:gz") as archive:
            try:
                module._safe_members(archive)
            except ValueError as exc:
                assert "unsafe archive member" in str(exc)
            else:
                raise AssertionError("path-traversal tar member must be rejected")


@test
def t_specter2_full_index_cpu_search_is_exact_and_label_blind():
    """The future full-corpus audit must rank only its stored document matrix."""
    spec = importlib.util.spec_from_file_location(
        "audit_specter2_full_test",
        Path(__file__).resolve().parents[1] / "scripts" / "audit_pasa_local_dense_full.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        np.save(root / "vectors.f16.npy", np.asarray(
            [[0.0, 1.0], [1.0, 0.0], [0.8, 0.6]], dtype=np.float16))
        (root / "manifest.json").write_text(json.dumps({
            "normalized": True, "document_adapter": "proximity",
            "model_root": str(root), "runtime_site": str(root), "max_length": 512,
            "fp16_encoder": True,
        }), encoding="utf-8")
        with (root / "papers.jsonl").open("w", encoding="utf-8") as stream:
            for position, aid in enumerate(("1", "2", "3")):
                stream.write(json.dumps({"position": position, "rowid": position + 1,
                                         "arxiv_id": aid, "title": aid}) + "\n")
        source = module.Specter2FullDenseIndex(
            str(root), device="cpu", search_device="cpu", block_size=256,
            model_root="", runtime_site="")
        assert source._top_positions(np.asarray([1.0, 0.0], dtype=np.float32), 2) == [1, 2]
        assert [row["arxiv_id"] for row in source.records] == ["1", "2", "3"]
        source.close()


@test
def t_local_dense_search_preserves_native_cosine_score():
    """Dense retrieval must expose its source score to fusion features."""
    from scholarnexus.sources.pasa_local_dense import PaSaLocalDenseSource
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        np.save(root / "vectors.f16.npy", np.asarray(
            [[1.0, 0.0], [0.0, 1.0]], dtype=np.float16))
        (root / "manifest.json").write_text(json.dumps({
            "normalized": True, "model_path": str(root), "max_seq_length": 32,
        }), encoding="utf-8")
        (root / "papers.jsonl").write_text(
            "{\"rowid\": 1, \"arxiv_id\": \"1\", \"title\": \"one\"}\n"
            "{\"rowid\": 2, \"arxiv_id\": \"2\", \"title\": \"two\"}\n",
            encoding="utf-8")
        source = PaSaLocalDenseSource(str(root), search_device="cpu")
        source._embed_query = lambda _query: np.asarray([1.0, 0.0], dtype=np.float32)
        papers = source._search("query", 2, {})
        assert [paper.arxiv_id for paper in papers] == ["1", "2"]
        assert papers[0].retrieval_score > papers[1].retrieval_score
        source.close()


@test
def t_final_rank_l2_blend_preserves_probability_mass():
    """The optional L2 order arm must keep F1-Gate's probability multiset."""
    from types import SimpleNamespace
    dummy = SimpleNamespace(cfg=SimpleNamespace(
        pipeline={"final_rank_l2_weight": 0.5}))
    cands = [Candidate(Paper(pid=f"p{index}", title=str(index)),
                       s_l2=value)
             for index, value in enumerate((0.1, 0.9, 0.4))]
    scores = np.asarray((0.2, 0.8, 0.3), dtype=np.float64)
    blended = ScholarNexus._apply_final_rank_l2_blend(dummy, cands, scores)
    assert np.allclose(np.sort(blended), np.sort(scores))
    assert int(np.argmax(blended)) == 1
    disabled = SimpleNamespace(cfg=SimpleNamespace(
        pipeline={"final_rank_l2_weight": 0.0}))
    assert np.array_equal(ScholarNexus._apply_final_rank_l2_blend(
        disabled, cands, scores), scores)


@test
def t_registry_records_optional_source_initialization_errors():
    """A missing configured source must expose its constructor failure."""
    from scholarnexus.sources.base import build_registry
    registry = build_registry({"pasa_local_dense": {
        "enabled": True, "index_dir": "definitely-not-a-dense-index",
    }})
    assert "pasa_local_dense" in registry.initialization_errors
    assert "FileNotFoundError" in registry.initialization_errors["pasa_local_dense"]


@test
def t_cross_encoder_frozen_pool_diagnostic_is_dev_only_and_local_only():
    """A future reranker probe must not silently become a test/API runner."""
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location(
        "cross_encoder_pool_test",
        Path(__file__).resolve().parents[1] / "scripts" / "evaluate_cross_encoder_pasa_pool.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    args = SimpleNamespace(limit=1, fts_k=1, preselect_k=20, batch_size=1,
                           max_length=32, abstract_chars=1,
                           data="AutoScholarQuery/test.jsonl")
    try:
        module._validate_args(args)
    except SystemExit as exc:
        assert "refusing" in str(exc).casefold()
    else:
        raise AssertionError("cross-encoder frozen-pool probe must reject test data")
    try:
        module.LocalCrossEncoder(Path("definitely-not-a-local-model"), "cpu", 32,
                                  False, False)
    except FileNotFoundError as exc:
        assert "never downloads" in str(exc)
    else:
        raise AssertionError("cross-encoder probe must require an on-disk model")
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        data = root / "dev.jsonl"
        data.write_text("{}\n", encoding="utf-8")
        pool = root / "pool" / "papers.jsonl"
        pool.parent.mkdir()
        (pool.parent / "manifest.json").write_text(json.dumps({
            "data": str(data), "offset": 100, "queries": 20,
            "gold_insertion": False,
        }), encoding="utf-8")
        module._assert_pool_alignment(pool, data, 100, 20)
        try:
            module._assert_pool_alignment(pool, data, 160, 20)
        except ValueError as exc:
            assert "offset" in str(exc)
        else:
            raise AssertionError("slice-mismatched frozen pool must be rejected")


@test
def t_openalex_candidate_audit_is_dev_only_and_preserves_arxiv_rank_dedup():
    """The API coverage audit must remain label-safe and strict-ID based."""
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location(
        "openalex_candidate_audit_test",
        Path(__file__).resolve().parents[1] / "scripts" / "audit_openalex_pasa_candidates.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    args = SimpleNamespace(limit=1, fts_k=1, api_k=1, timeout=1,
                           data="AutoScholarQuery/test.jsonl")
    try:
        module._validate(args)
    except SystemExit as exc:
        assert "refusing" in str(exc).casefold()
    else:
        raise AssertionError("OpenAlex candidate audit must reject test data")
    ids, missing = module._openalex_ids([
        {"ids": {"arxiv": "https://arxiv.org/abs/2401.00001v2"}},
        {"locations": [{"landing_page_url": "https://arxiv.org/abs/2401.00001"}]},
        {"title": "no arxiv location"},
    ])
    assert ids == ["2401.00001"] and missing == 1
    assert module._sanitize_openalex_query("works? with * wildcard") == "works with wildcard"
    try:
        module._sanitize_openalex_query("? *")
    except ValueError:
        pass
    else:
        raise AssertionError("punctuation-only OpenAlex query must not be sent")


@test
def t_frozen_bge_selector_head_rejects_autoscholar_and_preserves_pair_text():
    """Selector adaptation may use only official SFT training pairs."""
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location(
        "frozen_bge_selector_head_test",
        Path(__file__).resolve().parents[1] / "scripts" / "train_pasa_bge_selector_head.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    args = SimpleNamespace(train="AutoScholarQuery/dev.jsonl", batch_size=1,
                           max_length=32, abstract_chars=1, holdout=0.2)
    try:
        module._validate_args(args)
    except SystemExit as exc:
        assert "never AutoScholarQuery" in str(exc)
    else:
        raise AssertionError("BGE selector adaptation must reject AutoScholarQuery")
    assert module._pair_texts(["Title"], ["abcdef"], 3) == ["Title\n\nabc"]


@test
def t_pasa_label_blind_freezer_and_posthoc_scorer_reject_test_split():
    """冻结排序与后验计分必须都硬拒绝官方 test 文件。"""
    from types import SimpleNamespace
    root = Path(__file__).resolve().parents[1]
    freeze_spec = importlib.util.spec_from_file_location(
        "pasa_label_blind_freezer_test", root / "scripts" / "run_pasa_label_blind.py")
    freeze = importlib.util.module_from_spec(freeze_spec)
    assert freeze_spec.loader is not None
    freeze_spec.loader.exec_module(freeze)
    args = SimpleNamespace(data="AutoScholarQuery/test.jsonl", offset=0, limit=1,
                           rank_limit=100, out="never-created.json")
    try:
        freeze._validate_args(args)
    except SystemExit as exc:
        assert "refusing" in str(exc).casefold()
    else:
        raise AssertionError("label-blind freezer must reject test data")

    score_spec = importlib.util.spec_from_file_location(
        "pasa_frozen_score_test", root / "scripts" / "score_pasa_frozen_ranking.py")
    scorer = importlib.util.module_from_spec(score_spec)
    assert score_spec.loader is not None
    score_spec.loader.exec_module(scorer)
    try:
        scorer._validate({"kind": scorer.RANKING_KIND, "test_split_read": False,
                          "rows": [{"qid": "q"}]}, Path("test.jsonl"), Path("fresh.json"))
    except SystemExit as exc:
        assert "refusing" in str(exc).casefold()
    else:
        raise AssertionError("post-hoc scorer must reject test data")


@test
def t_pasa_biencoder_training_rejects_autoscholar_and_selector_test():
    """Dense adaptation has exactly one legal training source: Selector-SFT train."""
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location(
        "pasa_biencoder_train_test",
        Path(__file__).resolve().parents[1] / "scripts" / "train_pasa_minilm_biencoder.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    base = Path(__file__).resolve().parents[1]
    common = {"base_model": str(base), "epochs": 1, "batch_size": 1,
              "max_seq_length": 32, "abstract_chars": 64, "holdout": 0.2,
              "margin": 0.1, "lr": 2e-5}
    for illegal in ("AutoScholarQuery/dev.jsonl", "sft_selector/test.jsonl"):
        try:
            module._validate_args(SimpleNamespace(train=illegal, **common))
        except SystemExit as exc:
            assert "only official" in str(exc).casefold()
        else:
            raise AssertionError(f"bi-encoder trainer accepted forbidden source: {illegal}")


@test
def t_pasa_biencoder_group_split_has_no_query_leakage():
    """Triplet health check must separate groups, not merely individual pairs."""
    spec = importlib.util.spec_from_file_location(
        "pasa_biencoder_split_test",
        Path(__file__).resolve().parents[1] / "scripts" / "train_pasa_minilm_biencoder.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    triples, report = module.build_triples(
        ["q one", "q one", "q two", "q two"],
        ["p1", "n1", "p2", "n2"], ["", "", "", ""],
        np.asarray([1, 0, 1, 0]), 20)
    train, heldout = module._split_triples(triples, holdout=0.5, seed=7)
    assert report["triples"] == 2
    assert {row[3] for row in train}.isdisjoint({row[3] for row in heldout})


@test
def t_pasa_expand_gate_rejects_non_crawler_supervision():
    """The action policy must never accept benchmark labels as SFT input."""
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location(
        "pasa_expand_gate_train_test",
        Path(__file__).resolve().parents[1] / "scripts" / "train_pasa_crawler_expand_gate.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    common = {"out": "artifact.joblib", "holdout": 0.2, "target_positive_recall": 0.98}
    for illegal in ("AutoScholarQuery/train.jsonl", "sft_crawler/test.jsonl", "sft_selector/train.jsonl"):
        try:
            module._validate_args(SimpleNamespace(train=illegal, **common))
        except SystemExit as exc:
            assert "only the complete official" in str(exc).casefold()
        else:
            raise AssertionError(f"expand gate accepted forbidden input: {illegal}")


@test
def t_pasa_offline_action_builder_rejects_incomplete_train():
    """A policy learner may not silently train on a truncated benchmark prefix."""
    spec = importlib.util.spec_from_file_location(
        "pasa_offline_action_builder_test",
        Path(__file__).resolve().parents[1] / "scripts" / "build_pasa_offline_action_dataset.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as d:
        train_dir = Path(d) / "AutoScholarQuery"
        train_dir.mkdir()
        train = train_dir / "train.jsonl"
        train.write_text('{"qid":"q","answer_arxiv_id":["1"]}\n{"qid":"broken"', encoding="utf-8")
        try:
            module._validate_train(train, expected_records=2)
        except SystemExit as exc:
            assert "refusing incomplete" in str(exc).casefold()
        else:
            raise AssertionError("offline action builder accepted a truncated train file")


# ========================================================================= #
# 10. PaSa metric-first adaptation guards
# ========================================================================= #
@test
def t_pasa_recovery_validation_rejects_missing_qids():
    """A downloaded prefix or qid gap must never be promoted as train data."""
    from scripts.recover_pasa_autoscholar_train import validate_rows
    rows = [{"qid": f"AutoScholarQuery_train_{index}", "question": f"q {index}",
             "answer_arxiv_id": [f"24{index:03d}.00001"]} for index in range(3)]
    assert validate_rows(rows, 3)["records"] == 3
    rows[2] = dict(rows[2], qid="AutoScholarQuery_train_4")
    try:
        validate_rows(rows, 3)
    except ValueError as exc:
        assert "contiguous" in str(exc)
    else:
        raise AssertionError("recovery validation accepted a qid gap")


@test
def t_pasa_l2_feature_schema_is_stable():
    """Artifact features cannot silently change order between training and inference."""
    from scholarnexus.schema import QueryPlan
    plan = QueryPlan("query", QueryType.METHOD_CROSS, [], [], ["query"], 5.0)
    candidate = Candidate(Paper(pid="p", title="paper"), channels={"dense:pasa", "lexical:pasa"},
                          channel_ranks={"dense:pasa": 2, "lexical:pasa": 3})
    candidate.s_l2, candidate.s_l1, candidate.s_rrf = 0.7, 0.4, 0.2
    expected = (
        "base_l2", "l1", "rrf", "lexical", "dense", "graph", "reference", "title",
        "constraint", "channel_count", "best_channel_rank", "has_dense", "has_citation",
        "has_lexical", "query_type_locate", "query_type_survey", "query_type_method_cross",
        "query_type_benchmark", "query_type_lineage",
    )
    assert tuple(l2_feature_row(plan, candidate)) == expected


@test
def t_pasa_unpromoted_artifact_is_rejected():
    """A failed offline gate must be impossible to activate at runtime."""
    import joblib
    with tempfile.TemporaryDirectory() as directory:
        artifact = Path(directory) / "unpromoted.joblib"
        joblib.dump({"kind": "pasa_l2_fusion_v1", "promoted": False}, artifact)
        try:
            L2FusionModel(str(artifact))
        except ValueError as exc:
            assert "promotion gate" in str(exc)
        else:
            raise AssertionError("runtime accepted an unpromoted L2 artifact")


@test
def t_pasa_l2_fusion_residual_weight_preserves_base_signal():
    """Fusion interpolation is bounded and keeps base ordering at weight zero."""
    from scholarnexus.core.pasa_adaptation import L2FusionModel
    from scholarnexus.schema import QueryPlan

    class _ProbabilityModel:
        def predict_proba(self, matrix):
            values = np.asarray(matrix[:, 0], dtype=np.float64)
            return np.column_stack((1.0 - values, values))

    model = L2FusionModel.__new__(L2FusionModel)
    model.model = _ProbabilityModel()
    model.feature_names = ("base_l2",)
    plan = QueryPlan("query", QueryType.METHOD_CROSS, [], [], ["query"], 5.0)
    candidates = [Candidate(Paper(pid=pid, title="paper"), s_l2=score)
                  for pid, score in (("a", 0.2), ("b", 0.8), ("c", 0.5))]
    zero = model.rerank(plan, candidates, blend_weight=0.0)
    assert [candidate.pid for candidate in zero] == ["b", "c", "a"]
    geometric = model.rerank(plan, candidates, blend_weight=0.5, blend_mode="geometric")
    assert [candidate.pid for candidate in geometric] == ["b", "c", "a"]


@test
def t_pasa_profile_tie_falls_back_to_p2():
    """Exact policy ties retain the known-safe P2 wide-admission baseline."""
    from scholarnexus.schema import QueryPlan
    plan = QueryPlan("query", QueryType.METHOD_CROSS, [], [], ["query"], 5.0)
    policy = ProfilePolicy.__new__(ProfilePolicy)
    policy.model = _EqualProfilePredictor()
    policy.feature_names = ("log_candidate_count", "profile_P0", "profile_P1", "profile_P2", "profile_P3")
    policy.profile_names = ("P0", "P1", "P2", "P3")
    assert policy.choose(plan, [Candidate(Paper(pid="p", title="paper"))]).profile == "P2"


@test
def t_pasa_p0_forces_citation_skip_and_budget():
    """P0 is a real action: citation off and L1 fixed at 700."""
    cfg = Config.load(profile="offline")
    cfg.pipeline.update({"pasa_profile_override": "P0", "max_rounds": 1,
                         "candidate_audit": True})
    reg = SourceRegistry().register(LocalCorpusSource(path="data/fixture/corpus.jsonl"))
    engine = ScholarNexus(cfg, registry=reg)
    try:
        result = engine.search("retrieval augmented generation representative work")
    finally:
        engine.close()
    citation = [event for event in result.trace if event.get("action") == "skip_citation"]
    admission = [event for event in result.trace if event.get("action") == "fixed_profile_admission"]
    assert citation and citation[0].get("reason") == "profile_P0_citation_disabled"
    assert admission and admission[0].get("features", {}).get("l1_keep") == 700


@test
def t_pasa_cardinality_keeps_f1_output_as_ranked_prefix():
    """Learned n-hat may change k but cannot choose a non-prefix set."""
    import joblib
    with tempfile.TemporaryDirectory() as directory:
        artifact = Path(directory) / "cardinality.joblib"
        joblib.dump({"kind": "pasa_cardinality_predictor_v1", "model": _FixedPredictor(2.0),
                     "feature_names": ["log_candidate_count"], "min_value": 1.0,
                     "max_value": 20.0, "promoted": True}, artifact)
        cfg = Config.load(profile="offline")
        cfg.pipeline.update({"pasa_cardinality_path": str(artifact), "max_rounds": 1})
        reg = SourceRegistry().register(LocalCorpusSource(path="data/fixture/corpus.jsonl"))
        engine = ScholarNexus(cfg, registry=reg)
        try:
            result = engine.search("retrieval augmented generation representative work")
        finally:
            engine.close()
    selected = [candidate.pid for candidate in [*result.core, *result.partial]]
    assert selected == [candidate.pid for candidate in result.all_candidates[:len(selected)]]
    assert any(event.get("stage") == "cardinality" for event in result.trace)


@test
def t_pasa_profile_dataset_rejects_divergent_initial_pool():
    """Counterfactual feedback is invalid when profile arms start differently."""
    from scripts.build_pasa_profile_dataset import assert_shared_initial_observation
    def row(profile, members):
        return {"trace": [{"stage": "agent", "action": "profile", "profile": profile,
                           "features": {"log_candidate_count": 2.0}}],
                "candidate_audit": {"stage_members": {"post_probe_r1": members}}}
    rows = {"P0": row("P0", ["a", "b"]), "P1": row("P1", ["a", "b"]),
            "P2": row("P2", ["a", "b"]), "P3": row("P3", ["a", "c"])}
    try:
        assert_shared_initial_observation("AutoScholarQuery_train_0", rows)
    except SystemExit as exc:
        assert "did not share" in str(exc)
    else:
        raise AssertionError("profile builder accepted divergent initial pools")


@test
def t_pasa_profile_loader_requires_two_explicit_cohorts():
    """Policy feedback cannot replace its held-out cohort with a hash reshuffle."""
    from scripts.build_pasa_profile_dataset import _load

    def report(train, profile, cohort, qid):
        return {"kind": "PaSa qid/question-only frozen ranking report v1", "test_split_read": False,
                "data": str(train), "fixed_profile": profile, "cohort": cohort,
                "rows": [{"qid": qid,
                          "trace": [{"stage": "agent", "action": "profile", "profile": profile}],
                          "candidate_audit": {"stage_members": {"post_probe_r1": ["arxiv:1"]}}}]}

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        train = root / "train.jsonl"
        train.write_text("{}\n", encoding="utf-8")
        train_only = root / "train_only.json"
        train_only.write_text(json.dumps(report(train, "P2", "policy_train", "AutoScholarQuery_train_1")),
                              encoding="utf-8")
        try:
            _load([train_only], train, "P2")
        except SystemExit as exc:
            assert "both policy_train and policy_validation" in str(exc)
        else:
            raise AssertionError("profile loader accepted missing validation cohort")
        validation = root / "validation.json"
        validation.write_text(json.dumps(report(train, "P2", "policy_validation", "AutoScholarQuery_train_2")),
                              encoding="utf-8")
        rows, cohorts, _sources = _load([train_only, validation], train, "P2")
        assert set(rows) == {"AutoScholarQuery_train_1", "AutoScholarQuery_train_2"}
        assert cohorts["AutoScholarQuery_train_1"] == "policy_train"
        assert cohorts["AutoScholarQuery_train_2"] == "policy_validation"


@test
def t_pasa_compact_rollout_audit_retains_only_trainable_evidence():
    """Compact rollout artifacts remain sufficient for all train-only gates."""
    from scripts.run_pasa_profile_rollouts import _compact_audit
    audit = {
        "version": "candidate_audit_v1", "label_policy": "label blind", "rounds": 1,
        "stage_sizes": {"post_probe_r1": 2, "l2_input_final": 1},
        "stage_members": {"post_probe_r1": ["arxiv:a", "arxiv:b"], "l2_input_final": ["arxiv:a"]},
        "candidates": {
            "arxiv:a": {"arxiv_id": "a", "channels": ["dense:test"],
                        "channel_ranks": {"dense:test": 3},
                        "stages": {"l2_input": True, "l2": True, "selected": True},
                        "scores": {"l2": 0.8, "p_gold": 0.7, "l1": 0.6, "rrf": 0.1}},
            "arxiv:b": {"arxiv_id": "b", "channels": ["lexical:test"],
                        "stages": {"l2_input": False}, "scores": {"l2": None}},
        },
    }
    compact = _compact_audit(audit)
    assert compact["stage_members"]["post_probe_r1"] == ["arxiv:a", "arxiv:b"]
    assert set(compact["candidates"]) == {"arxiv:a"}
    assert compact["candidates"]["arxiv:a"]["scores"]["l2"] == 0.8
    assert compact["candidates"]["arxiv:a"]["scores"]["p_gold"] == 0.7


@test
def t_pasa_rollout_shards_are_stable_and_nonoverlapping():
    """Long label-blind rollouts can be resumed as immutable hash slices."""
    from scripts.run_pasa_profile_rollouts import _select
    records = [{"qid": f"AutoScholarQuery_train_{index}", "question": f"question {index}"}
               for index in range(20)]
    first = _select(records, "all", 7, 0, 20260825)
    second = _select(records, "all", 7, 7, 20260825)
    assert len(first) == len(second) == 7
    assert {row["qid"] for row in first}.isdisjoint({row["qid"] for row in second})
    assert first == _select(records, "all", 7, 0, 20260825)


@test
def t_pasa_rollout_and_trainers_share_the_same_stable_cohort_hash():
    """Explicit 1024/256 cohorts and downstream train gates cannot drift."""
    from scripts.run_pasa_profile_rollouts import _query_hash
    from scripts.train_pasa_l2_fusion import is_train_query
    for index in range(50):
        query = f"  Query {index} with   normalized spacing  "
        assert (_query_hash(query, 20260825) % 10_000 < 8_000) == is_train_query(query, 20260825)


@test
def t_pasa_paired_compare_scores_explicit_selected_prefixes():
    """The paired evaluator supports label-blind reports written by current runners."""
    from scripts.compare_pasa_reports import adaptive_metric_by_qid
    report = {"rows": [{"qid": "q", "selection": {"mode": "f1_gate_prefix", "count": 2},
                          "selected_arxiv_ids": ["arxiv:1", "2"]}]}
    gold = {"q": {"1", "3"}}
    assert adaptive_metric_by_qid(report, gold, "precision")["q"] == 0.5
    assert adaptive_metric_by_qid(report, gold, "recall")["q"] == 0.5
    assert adaptive_metric_by_qid(report, gold, "f1")["q"] == 0.5


# ========================================================================= #
def main():
    passed, failed = 0, []
    for fn in TESTS:
        name = fn.__name__.replace("t_", "")
        try:
            fn()
            passed += 1
            print(f"  \033[32m✓\033[0m {name}")
        except Exception as e:                                   # noqa: BLE001
            failed.append((name, e, traceback.format_exc()))
            print(f"  \033[31m✗\033[0m {name}: {e}")
    print(f"\n{passed}/{len(TESTS)} 通过")
    if failed:
        print("\n失败详情：")
        for name, _e, tb in failed:
            print(f"\n--- {name} ---\n{tb}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
