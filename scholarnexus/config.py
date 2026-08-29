"""配置层：一套 profile 切换「商业 API」与「本地部署」，不改一行业务代码。

设计约束（来自项目决策）
------------------------
初赛走商业 API（DashScope / 硅基流动 / DeepSeek 等 OpenAI 兼容端点），
但本地部署路径必须始终保留、且随时可切——这既是成本对冲，也是评审关心的
「方案落地可行性」。因此三层能力（LLM / Embedding / Reranker）各自独立配置，
每层都有 `cloud → local → 零依赖回退` 的三级降级链：

    LLM      : cloud(openai_compat) → local(vLLM/Ollama) → mock(规则)
    Embedding: cloud(/embeddings)   → local(vLLM/TEI)    → hashing(TF-IDF)
    Reranker : cloud(/rerank)       → local(CrossEncoder)→ lexical(BM25+覆盖率)

任何一层失效都只降级该层，**绝不让整条流水线挂掉**——这条原则借鉴自
Ray-Source 的「失败不降级、绝不误报上线」工程约定，在本系统里体现为
「失败可降级、但必须在执行账本里如实标注降级事件」。
"""
from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:
    import yaml
except Exception:                                    # noqa: BLE001
    yaml = None


# --------------------------------------------------------------------------- #
# 内置 profile
# --------------------------------------------------------------------------- #
PROFILES: Dict[str, Dict[str, Any]] = {

    # ---- 初赛主用：商业 API ----
    "cloud": {
        "llm_fast": {                     # 查询解析 / 查询扩展：便宜、快
            "backend": "openai_compat",
            "model": "qwen-flash",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key_env": "DASHSCOPE_API_KEY",
            "temperature": 0.0, "max_tokens": 1200, "timeout": 45,
        },
        "llm_judge": {                    # L3 约束精判：强判别力
            "backend": "openai_compat",
            "model": "qwen-plus",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key_env": "DASHSCOPE_API_KEY",
            "temperature": 0.0, "max_tokens": 2000, "timeout": 60,
        },
        "embedding": {
            "backend": "api", "model": "text-embedding-v3", "dim": 1024,
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key_env": "DASHSCOPE_API_KEY",
        },
        "reranker": {
            "backend": "qwen", "model": "qwen3-rerank",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key_env": "DASHSCOPE_API_KEY",
        },
    },

    # ---- 决赛/私有化：本地部署（vLLM + TEI） ----
    "local": {
        "llm_fast": {
            "backend": "openai_compat", "model": "Qwen3-4B-Instruct",
            "base_url": "http://127.0.0.1:8000/v1",
            "api_key_env": "LOCAL_API_KEY",
            "temperature": 0.0, "max_tokens": 1200, "timeout": 60,
        },
        "llm_judge": {
            "backend": "openai_compat", "model": "Qwen3-32B-Instruct",
            "base_url": "http://127.0.0.1:8001/v1",
            "api_key_env": "LOCAL_API_KEY",
            "temperature": 0.0, "max_tokens": 2000, "timeout": 120,
        },
        "embedding": {
            "backend": "api", "model": "Qwen3-Embedding-0.6B", "dim": 1024,
            "base_url": "http://127.0.0.1:8002/v1", "api_key_env": "LOCAL_API_KEY",
        },
        "reranker": {
            "backend": "local", "model": "BAAI/bge-reranker-v2-m3",
            "device": None,
        },
    },

    # ---- 离线自测 / CI：零外部依赖 ----
    "offline": {
        "llm_fast": {"backend": "mock", "model": "mock-fast"},
        "llm_judge": {"backend": "mock", "model": "mock-judge"},
        "embedding": {"backend": "hashing", "dim": 4096},
        "reranker": {"backend": "lexical"},
    },
}

DEFAULT_SOURCES = {
    "openalex": {"enabled": True, "mailto_env": "OPENALEX_MAILTO"},
    "s2": {"enabled": True, "api_key_env": "S2_API_KEY"},
    "arxiv": {"enabled": True},
    "pubmed": {"enabled": False, "email": ""},
}

DEFAULT_PIPELINE = {
    "max_rounds": 2,
    "per_query_limit": 20,          # 每条检索式取回上限
    "l1_keep": 220,                 # 进入 L2 精排的候选上限
    # 在 L1 全局排序前为独立召回通道保留名额。RRF 很适合融合异构排名，
    # 但不能承担“淘汰唯一发现者”的职责：一个只被 dense 或 title 命中的真答案
    # 可能在全局 RRF 中输给多个宽泛词法通道。配置形如
    # {"lexical:pasa:abstract": 80, "dense:pasa": 120}；空字典保持旧行为。
    "l1_channel_quotas": {},
    # 只保护“仅由某一通道首次发现”的候选，按该通道原始检索 rank 取前 N 篇。
    # 典型配置为 {"dense:pasa_local_minilm": 300}。它控制 admission，而非
    # relevance score；第二道 L2 截断须用同样语义的 l2_unique_channel_quotas。
    "l1_unique_channel_quotas": {},
    "l2_keep": 80,                  # 进入 VoI 排队的候选上限
    # ``0`` preserves legacy behavior (L2 receives every L1 survivor).
    # Positive values cap only the L2 input, not L1 candidate admission.
    "l2_input_keep": 0,
    # L2 截断也可为指定检索通道保留成员名额。它与 l1_channel_quotas
    # 语义一致：只控制谁能进入 L2，不改变 L1 分数或后续排序。默认为空，
    # 以保持既有配置与冻结评测的结果完全一致。
    "l2_channel_quotas": {},
    "l2_unique_channel_quotas": {},
    # ``raw_plus_anchor`` preserves historical behavior.  ``raw`` is used by
    # the PaSa BGE Selector-SFT replication so its pair text exactly matches
    # the frozen-pool validation protocol.
    "l2_query_mode": "raw_plus_anchor",
    # Experimental route: keep the lexical retriever on QueryLens' controlled
    # search strings, but send the original complete question to the listed
    # independent dense sources.  Empty preserves the historical all-sources
    # × all-search-strings probe.  A dedicated channel tag records this input
    # representation in candidate provenance and prevents accidental mixing.
    "raw_query_dense_sources": [],
    "raw_query_dense_limit": 0,
    # Optional second dense view made from positive query constraints.  It is
    # off by default because every extra view costs an additional ANN pass;
    # train-only recall gates must approve it before use in a submission.
    "raw_query_dense_constraint_view": False,
    # Optional label-blind admission gate for an independent dense channel.
    # It is intentionally empty by default: the gate must use a separately
    # frozen Selector-SFT scorer and can protect membership only, never alter
    # L1/L2 relevance scores.
    "dense_admission_selector": {},
    # Train-only PaSa adaptation artifacts.  They are opt-in and the runtime
    # refuses bundles that did not pass their recorded internal promotion gate.
    "pasa_l2_fusion_path": "",
    # Train-promoted L2 fusion can retain a residual of the original L2 score
    # when the validation cohort shows that full replacement is too brittle.
    "pasa_l2_fusion_weight": 1.0,
    "pasa_l2_fusion_blend_mode": "linear",
    # Optional head-only application keeps the original L2 tail order intact.
    # Zero preserves the historical full-candidate fusion behavior.
    "pasa_l2_fusion_head_keep": 0,
    "pasa_cardinality_path": "",
    "pasa_profile_policy_path": "",
    # Set only by frozen train rollout arms.  Normal inference uses either an
    # approved policy artifact or the historical baseline behavior.
    "pasa_profile_override": "",
    "max_l3_judgments": 0,          # 默认关闭：当前消融中 L3 无正收益
    "l3_batch_size": 6,             # 每次 L3 调用打包几篇（省 call 数）
    "citation_expand_seeds": 6,     # 引文扩散的种子数
    "citation_expand_limit": 40,    # 每个种子取回的引文数
    # 默认由 L1 选 citation anchor。"l2" 是一个受控实验开关：只把已通过
    # 同一 constraint floor 的候选交给当前 L2 再排序，用于测试“anchor relevance
    # 与 final relevance 是否应分开”；不会增加种子数，也绝不读取 benchmark gold。
    "citation_seed_rerank": "disabled",
    # An optional *separate* scorer for citation anchors.  It is intentionally
    # distinct from final L2 relevance: an excellent related-work anchor need
    # not itself be the best final answer.  Empty keeps historical L1 seeds.
    "citation_anchor_reranker": {},
    # Optional train-only final-order calibration. A positive value blends
    # calibrated probability with normalized L2 score before F1-Gate; zero
    # preserves the frozen baseline exactly.
    "final_rank_l2_weight": 0.0,
    # Bound the number of L1-eligible papers sent to the optional anchor
    # scorer.  Zero retains every eligible candidate (legacy-compatible).
    "citation_anchor_input_keep": 0,
    # PaSa 官方 archive 的 sections 是“section 标题 -> 该节引用论文”。
    # >0 时，仅扩展 query 匹配的前若干 section；0 是旧的全参考文献回退。
    "citation_section_max_sections": 0,
    # 图扩展只能从已经与查询锚点一致的候选出发。否则一个宽泛检索词命中的
    # 高被引论文会把整片无关引文邻域带入候选池，图分数反而淹没文本相关性。
    "citation_seed_min_constraint": 0.42,
    "target_coverage": 0.85,
    "core_ratio": 1.25,             # core / partial 分层门限倍率
    "use_propensity": True,         # 标注倾向性建模（对齐评测金标准构造过程）
    # 校准器："mixture"（默认，对先验不敏感）/ "mixture+temper"（额外压尾）
    # / "rank_decay"。实测在合成语料上 temper 收益不显著（+1.3%）且提高了
    # 对先验的敏感度，故默认关闭；真实数据上需重新验证，见 docs/DESIGN_V2.md。
    "calibrator": "mixture",
    "anchor_prior_weight": 1.0,
    "decay_c": 1.6,
    "constraint_bonus": True,
    "band_width": 0.15,
    "l3_policy": "disabled",       # disabled / adaptive / always
    "l3_min_voi": 0.004,
    "l3_max_papers": 12,
    "enable_query_evolution": False,# 当前消融无收益；真实集证明后再打开
    "supervised_calibrator_path": "",
    "supervised_blend": 0.65,
    # 仅供开发集离线诊断。开启后保留候选的来源、stage membership 和 citation
    # path；它是纯观测开关，不能改变候选、分数、输出或 test 提交。
    "candidate_audit": False,
}


# --------------------------------------------------------------------------- #
@dataclass
class Config:
    profile: str = "cloud"
    llm_fast: Dict[str, Any] = field(default_factory=dict)
    llm_judge: Dict[str, Any] = field(default_factory=dict)
    embedding: Dict[str, Any] = field(default_factory=dict)
    reranker: Dict[str, Any] = field(default_factory=dict)
    sources: Dict[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULT_SOURCES))
    pipeline: Dict[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULT_PIPELINE))
    budget: Dict[str, Any] = field(default_factory=dict)
    cache_path: str = ".sn_cache/cache.sqlite"
    cache_ttl_days: float = 30.0

    # ---------------- 构造 ----------------
    @staticmethod
    def load(path: Optional[str] = None, profile: Optional[str] = None) -> "Config":
        """优先级：显式参数 > 配置文件 > 环境变量 SN_PROFILE > 自动探测。"""
        raw: Dict[str, Any] = {}
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            if path.endswith((".yaml", ".yml")) and yaml is not None:
                raw = yaml.safe_load(text) or {}
            else:
                raw = json.loads(text)

        prof = (profile or raw.get("profile") or os.environ.get("SN_PROFILE")
                or Config.autodetect_profile())
        base = copy.deepcopy(PROFILES.get(prof, PROFILES["offline"]))
        cfg = Config(profile=prof, **base)

        for key in ("llm_fast", "llm_judge", "embedding", "reranker",
                    "sources", "pipeline", "budget"):
            if key in raw and isinstance(raw[key], dict):
                cur = getattr(cfg, key) or {}
                cur.update(raw[key])
                setattr(cfg, key, cur)
        if "cache_path" in raw:
            cfg.cache_path = raw["cache_path"]
        if "cache_ttl_days" in raw:
            cfg.cache_ttl_days = float(raw["cache_ttl_days"])
        return cfg

    @staticmethod
    def autodetect_profile() -> str:
        """没有任何显式配置时：有云端 Key 就走云，否则离线。

        这保证 `git clone && python -m scholarnexus.cli "query"` 在零配置下
        也能跑出结果（降级到规则解析 + 词法精排），而不是抛异常。
        """
        # 内置 cloud 档位统一使用 DashScope；其他供应商需显式配置文件，
        # 避免仅存在无关 Key 时误入 cloud 后再整链降级。
        for env in ("DASHSCOPE_API_KEY",):
            if os.environ.get(env):
                return "cloud"
        return "offline"

    # ---------------- 运行时能力探测 ----------------
    def resolved(self) -> "Config":
        """把「配了但没 Key」的层就地降级，并记录降级原因。

        商业 API profile 下如果没有对应的环境变量，直接降级到零依赖实现，
        比运行到一半 401 再抛异常要好得多。
        """
        cfg = copy.deepcopy(self)
        cfg.degradations = []                                   # type: ignore[attr-defined]

        def _needs_key(d: Dict[str, Any]) -> bool:
            if d.get("backend") in ("mock", "hashing", "lexical", "local",
                                    "local_embedding", "local_embed",
                                    "sentence_embedding", "pasa_selector", "selector",
                                    "pasa_bge_selector_head", "bge_selector_head"):
                return False
            url = d.get("base_url", "")
            if url.startswith(("http://127.0.0.1", "http://localhost")):
                return False        # 本地服务通常不校验 Key
            return not os.environ.get(d.get("api_key_env", ""), "")

        for key, fallback in (("llm_fast", {"backend": "mock", "model": "mock-fast"}),
                              ("llm_judge", {"backend": "mock", "model": "mock-judge"}),
                              ("embedding", {"backend": "hashing", "dim": 4096}),
                              ("reranker", {"backend": "lexical"})):
            d = getattr(cfg, key) or {}
            if _needs_key(d):
                cfg.degradations.append(                        # type: ignore[attr-defined]
                    {"layer": key, "from": d.get("model", d.get("backend")),
                     "to": fallback["backend"],
                     "reason": f"环境变量 {d.get('api_key_env')} 未设置"})
                setattr(cfg, key, fallback)
        return cfg

    def to_dict(self) -> Dict[str, Any]:
        def _scrub(d: Dict[str, Any]) -> Dict[str, Any]:
            return {k: v for k, v in (d or {}).items() if "key" not in k or k.endswith("_env")}
        return {
            "profile": self.profile,
            "llm_fast": _scrub(self.llm_fast),
            "llm_judge": _scrub(self.llm_judge),
            "embedding": _scrub(self.embedding),
            "reranker": _scrub(self.reranker),
            "sources": self.sources,
            "pipeline": self.pipeline,
            "degradations": getattr(self, "degradations", []),
        }
