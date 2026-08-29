"""ScholarNexus 核心数据结构。

所有模块之间只通过这里定义的类型通信，便于单元测试与消融替换。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


# --------------------------------------------------------------------------- #
# 查询意图类型（决定 N̂ 先验、通道权重、预算与展示形态）
# --------------------------------------------------------------------------- #
class QueryType(str, Enum):
    LOCATE = "locate"              # 特定论文定位型："提出 XX 方法的那篇论文"
    SURVEY = "survey"              # 综述覆盖型："某方向的全部工作"
    METHOD_CROSS = "method_cross"  # 方法交叉型："A 方法用在 B 任务上的工作"
    BENCHMARK = "benchmark"        # 数据集-基准型："在 XX 数据集上评测的工作"
    LINEAGE = "lineage"            # 作者-脉络型："XX 团队后续工作 / 技术脉络"

    @property
    def zh(self) -> str:
        return {
            "locate": "特定论文定位",
            "survey": "综述覆盖",
            "method_cross": "方法交叉",
            "benchmark": "数据集/基准",
            "lineage": "脉络追踪",
        }[self.value]


class ConstraintRole(str, Enum):
    """约束的执行角色 —— 这是「检索/判定解耦」的落点。"""
    HARD_FILTER = "hard_filter"   # 元数据可直接过滤：年份、venue、语言、类型
    ANCHOR = "anchor"             # 用于生成检索式的锚点语义面（故意欠约束）
    VERIFY = "verify"             # 只在判定阶段核验，绝不进检索式
    NEGATIVE = "negative"         # 排除性约束："不要综述"、"不含强化学习"


class ConstraintKind(str, Enum):
    TOPIC = "topic"
    METHOD = "method"
    TASK = "task"
    DATASET = "dataset"
    MODALITY = "modality"
    METRIC = "metric"
    YEAR = "year"
    VENUE = "venue"
    AUTHOR = "author"
    DOC_TYPE = "doc_type"
    OTHER = "other"


@dataclass
class Constraint:
    kind: ConstraintKind
    role: ConstraintRole
    text: str                       # 人类可读描述，用作约束满足矩阵的列名
    value: Any = None               # 结构化值：{"min":2022} / ["CVPR"] / str
    weight: float = 1.0             # 判定阶段的权重（加权约束满足度）
    aliases: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value if isinstance(self.kind, Enum) else self.kind
        d["role"] = self.role.value if isinstance(self.role, Enum) else self.role
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Constraint":
        return Constraint(
            kind=ConstraintKind(d.get("kind", "other")),
            role=ConstraintRole(d.get("role", "verify")),
            text=d.get("text", ""),
            value=d.get("value"),
            weight=float(d.get("weight", 1.0)),
            aliases=list(d.get("aliases") or []),
        )


@dataclass
class SubQuery:
    """查询分解出的可独立检索的子问题。"""
    text: str
    facet: str = "core"              # 该子查询覆盖的语义面
    weight: float = 1.0
    channel_hint: str = ""           # 建议投递的通道（lexical / dense / ...）


@dataclass
class Budget:
    max_llm_calls: int = 16
    max_tokens: int = 60000
    max_api_calls: int = 60
    max_seconds: float = 45.0
    max_rounds: int = 3
    max_l3_judgments: int = 60       # 大模型逐条精判的上限


@dataclass
class QueryPlan:
    """QueryLens 的输出：一次检索任务的完整执行计划。"""
    raw_query: str
    query_type: QueryType
    constraints: List[Constraint]
    subqueries: List[SubQuery]
    search_strings: List[str]        # 直接投喂给学术 API 的检索式（欠约束）
    n_hat_prior: float               # 目标集合基数的先验均值
    n_hat_prior_sd: float = 8.0
    budget: Budget = field(default_factory=Budget)
    channel_weights: Dict[str, float] = field(default_factory=dict)
    language: str = "en"
    notes: str = ""
    degraded: bool = False           # True = LLM 不可用，走了规则回退
    quoted_spans: List[str] = field(default_factory=list)
    constraint_graph: Dict[str, Any] = field(default_factory=dict)
    """查询中疑似直接引用的文本片段（论文标题、方法名、数据集名）。

    「提出 XX 的那篇论文是哪篇」这类定位型查询里，XX 往往就是标题原文或
    方法专名。把它单独抽出来做精确匹配，比让它混进一般词袋有效得多。
    """

    def hard_filters(self) -> List[Constraint]:
        return [c for c in self.constraints if c.role == ConstraintRole.HARD_FILTER]

    def verify_constraints(self) -> List[Constraint]:
        return [c for c in self.constraints
                if c.role in (ConstraintRole.VERIFY, ConstraintRole.ANCHOR,
                              ConstraintRole.NEGATIVE)]

    def api_filters(self) -> Dict[str, Any]:
        """把硬过滤约束翻译成学术 API 的元数据参数（零 LLM 成本）。"""
        f: Dict[str, Any] = {}
        for c in self.hard_filters():
            v = c.value
            if c.kind == ConstraintKind.YEAR and isinstance(v, dict):
                if v.get("min"):
                    f["year_min"] = int(v["min"])
                if v.get("max"):
                    f["year_max"] = int(v["max"])
            elif c.kind == ConstraintKind.VENUE and v:
                f["venues"] = list(v) if isinstance(v, (list, tuple)) else [str(v)]
            elif c.kind == ConstraintKind.DOC_TYPE and v:
                f["doc_type"] = str(v)
        return f

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_query": self.raw_query,
            "query_type": self.query_type.value,
            "query_type_zh": self.query_type.zh,
            "constraints": [c.to_dict() for c in self.constraints],
            "subqueries": [asdict(s) for s in self.subqueries],
            "search_strings": self.search_strings,
            "n_hat_prior": self.n_hat_prior,
            "n_hat_prior_sd": self.n_hat_prior_sd,
            "channel_weights": self.channel_weights,
            "degraded": self.degraded,
            "quoted_spans": self.quoted_spans,
            "constraint_graph": self.constraint_graph,
            "notes": self.notes,
        }


# --------------------------------------------------------------------------- #
# 论文与候选
# --------------------------------------------------------------------------- #
@dataclass
class Paper:
    pid: str                                   # 归一化后的全局唯一 id
    title: str
    abstract: str = ""
    year: Optional[int] = None
    venue: str = ""
    authors: List[str] = field(default_factory=list)
    doi: str = ""
    arxiv_id: str = ""
    url: str = ""
    citation_count: int = 0
    reference_ids: List[str] = field(default_factory=list)
    citing_ids: List[str] = field(default_factory=list)
    fields: List[str] = field(default_factory=list)
    source: str = ""
    doc_type: str = "article"
    # Optional source-native retrieval score.  Dense sources populate this
    # field so downstream feature extraction can use the actual cosine score,
    # while older cached/source records remain valid via the default ``None``.
    retrieval_score: Optional[float] = None

    def dedup_key(self) -> str:
        """跨源去重 / 版本合并的归一化 key。"""
        if self.doi:
            return "doi:" + self.doi.lower().strip()
        if self.arxiv_id:
            return "arxiv:" + self.arxiv_id.lower().split("v")[0].strip()
        t = "".join(ch for ch in (self.title or "").lower() if ch.isalnum())
        return "title:" + hashlib.md5(t.encode()).hexdigest()[:16]

    def text(self) -> str:
        return f"{self.title}\n{self.abstract}"

    @property
    def is_review(self) -> bool:
        dt = (self.doc_type or "").lower()
        if "review" in dt or "survey" in dt:
            return True
        t = (self.title or "").lower()
        return t.startswith("a survey") or ": a survey" in t or "a review of" in t

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConstraintCheck:
    constraint_text: str
    status: str            # "yes" | "partial" | "no" | "unknown"
    evidence: str = ""

    @property
    def score(self) -> float:
        return {"yes": 1.0, "partial": 0.5, "no": 0.0, "unknown": 0.3}.get(
            self.status, 0.3)


@dataclass
class Candidate:
    paper: Paper
    channels: Set[str] = field(default_factory=set)   # 命中它的检索通道
    channel_ranks: Dict[str, int] = field(default_factory=dict)
    # 可选的、完全 label-blind 的发现记录。默认运行不填充它；只有显式开启
    # candidate_audit 时才用于离线回答“候选从哪里来、在哪一层被截断”。它绝不
    # 参与任何检索、排序、校准或集合选择。
    provenance: List[Dict[str, Any]] = field(default_factory=list)

    # 各层打分
    s_lexical: float = 0.0
    s_dense: float = 0.0
    s_graph: float = 0.0            # 双向 PPR + 共被引闭包先验
    s_reference: float = 0.0        # 通过强种子章节直接引用发现的来源证据
    s_title: float = 0.0            # 查询引用片段与标题的整体相似度
    s_constraint: float = 0.0       # 可执行约束图的零成本匹配分
    s_rrf: float = 0.0              # 多通道 RRF 融合
    s_l1: float = 0.0               # 轻量粗排融合分
    s_l2: Optional[float] = None    # cross-encoder 精排分（零 token）
    s_l3: Optional[float] = None    # 大模型约束清单精判分

    p_rel: float = 0.0              # 校准后的相关概率 P(relevant)
    propensity: float = 1.0         # P(labeled | relevant)，标注生成过程建模
    p_gold: float = 0.0             # F1-Gate 实际使用的概率
    sigma: float = 0.25             # p_rel 的不确定度
    voi: float = 0.0

    checks: List[ConstraintCheck] = field(default_factory=list)
    rationale: str = ""
    tier: str = "excluded"          # "core" | "partial" | "excluded"
    judged_level: int = 1           # 最高走到的判定层级
    seed_round: int = 0             # 在第几轮被发现

    @property
    def pid(self) -> str:
        return self.paper.pid

    def constraint_satisfaction(self) -> float:
        if not self.checks:
            return 0.0
        tot_w = sum(1.0 for _ in self.checks)
        return sum(c.score for c in self.checks) / max(tot_w, 1e-9)

    def to_dict(self) -> Dict[str, Any]:
        p = self.paper
        return {
            "pid": self.pid,
            "title": p.title,
            "abstract": p.abstract[:400],
            "year": p.year,
            "venue": p.venue,
            "authors": p.authors[:6],
            "url": p.url,
            "doi": p.doi,
            "citation_count": p.citation_count,
            "channels": sorted(self.channels),
            "p_rel": round(self.p_rel, 4),
            "propensity": round(self.propensity, 4),
            "p_gold": round(self.p_gold, 4),
            "sigma": round(self.sigma, 4),
            "tier": self.tier,
            "judged_level": self.judged_level,
            "seed_round": self.seed_round,
            "scores": {
                "lexical": round(self.s_lexical, 4),
                "dense": round(self.s_dense, 4),
                "graph": round(self.s_graph, 4),
                "reference": round(self.s_reference, 4),
                "title": round(self.s_title, 4),
                "constraint": round(self.s_constraint, 4),
                "rrf": round(self.s_rrf, 4),
                "l1": round(self.s_l1, 4),
                "l2": None if self.s_l2 is None else round(self.s_l2, 4),
                "l3": None if self.s_l3 is None else round(self.s_l3, 4),
            },
            "checks": [asdict(c) for c in self.checks],
            "constraint_satisfaction": round(self.constraint_satisfaction(), 3),
            "rationale": self.rationale,
        }


@dataclass
class SearchResult:
    query: str
    plan: QueryPlan
    core: List[Candidate]
    partial: List[Candidate]
    all_candidates: List[Candidate]
    n_hat: float
    n_hat_ci: tuple
    coverage: float
    threshold: float
    expected_f1: float
    rounds: int
    ledger: Dict[str, Any]
    views: Dict[str, Any] = field(default_factory=dict)
    trace: List[Dict[str, Any]] = field(default_factory=list)
    # Optional developer-only, label-blind diagnostic artifact.  Kept out of
    # ordinary output unless the pipeline's candidate_audit switch is enabled.
    candidate_audit: Dict[str, Any] = field(default_factory=dict)

    def pids(self) -> List[str]:
        return [c.pid for c in self.core]

    def to_dict(self, include_all: bool = False) -> Dict[str, Any]:
        d = {
            "query": self.query,
            "plan": self.plan.to_dict(),
            "core": [c.to_dict() for c in self.core],
            "partial": [c.to_dict() for c in self.partial],
            "n_hat": round(self.n_hat, 2),
            "n_hat_ci": [round(x, 2) for x in self.n_hat_ci],
            "coverage": round(self.coverage, 4),
            "threshold": round(self.threshold, 4),
            "expected_f1": round(self.expected_f1, 4),
            "rounds": self.rounds,
            "ledger": self.ledger,
            "views": self.views,
            "trace": self.trace,
        }
        if include_all:
            d["all_candidates"] = [c.to_dict() for c in self.all_candidates]
        if self.candidate_audit:
            d["candidate_audit"] = self.candidate_audit
        return d

    def to_json(self, indent: int = 2, include_all: bool = False) -> str:
        return json.dumps(self.to_dict(include_all), ensure_ascii=False,
                          indent=indent)
