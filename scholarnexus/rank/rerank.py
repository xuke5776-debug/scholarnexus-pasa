"""L2 精排：本地 cross-encoder reranker。

设计来源与致谢
--------------
本层的技术选型借鉴了自研项目 Ray-Source（多模态 RAG 产品支持系统）的检索栈：
BM25(稀疏) + 向量(稠密) → RRF 融合 → cross-encoder reranker 精排。
Ray-Source 使用 BAAI/bge-m3 做 embedding、BAAI/bge-reranker-v2-m3 做 query-doc
打分。该组合在闭域手册问答中经过验证，此处迁移到开放域学术检索。

为什么这一层对本赛题特别值钱
----------------------------
评测里 F1 占 70%、运行效率占 20%。cross-encoder 是**本地推理、零 token 消耗**
的强判别器，判别力远高于双塔余弦，接近小参数量 LLM 的 listwise 打分。
把它插进级联后：

    v1: L1 哈希向量粗排 → L2 小模型 listwise(耗 token) → L3 大模型精判
    v2: L1 BM25+dense+RRF → L2 cross-encoder(零 token) → L3 大模型仅判不确定带

L2 整层的 token 成本从"每 100 篇候选约 8k tokens"降到 0，同时精度不降反升。
大模型调用量因此可以压到 ≤ 12 次/查询。

三级回退
--------
1. `APIReranker`      —— vLLM / TEI / 硅基流动等 OpenAI 兼容 /rerank 端点
2. `LocalReranker`    —— sentence-transformers CrossEncoder 本地权重
3. `LexicalReranker`  —— 零依赖词法回退（BM25 + 覆盖率 + 字段加权），
                         保证无网络、无权重时整条流水线仍可端到端跑通
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = set("""a an the of for on in to and or with without via using use used by
from at as is are be been that this these those we our their its it can may new
novel approach approaches method methods model models framework paper study""".split())


def _tok(s: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall((s or "").lower())
            if t not in _STOP and len(t) > 1]


# --------------------------------------------------------------------------- #
@dataclass
class RerankItem:
    pid: str
    title: str
    abstract: str = ""
    venue: str = ""
    year: Optional[int] = None

    def pair_text(self, max_abs_chars: int = 900) -> str:
        return f"{self.title}\n{self.abstract[:max_abs_chars]}"


class BaseReranker:
    name = "base"
    # 该 reranker 输出分数的典型不确定度，供 F1-Gate 的 VoI 计算使用
    sigma = 0.20

    def score(self, query: str, items: Sequence[RerankItem]) -> np.ndarray:
        raise NotImplementedError

    def rerank(self, query: str, items: Sequence[RerankItem],
               top_k: Optional[int] = None) -> List[Tuple[RerankItem, float]]:
        s = self.score(query, items)
        order = np.argsort(-s)
        if top_k:
            order = order[:top_k]
        return [(items[i], float(s[i])) for i in order]


class LexicalReranker(BaseReranker):
    """零依赖回退。不是玩具：字段加权 + 查询词覆盖率 + IDF 加权重叠，
    在学术标题/摘要这类术语驱动的文本上是一个相当结实的基线，
    同时充当消融实验里的"无神经精排"对照组。
    """
    name = "lexical"
    sigma = 0.28

    def __init__(self, title_weight: float = 2.2, k1: float = 1.2, b: float = 0.7):
        self.title_weight, self.k1, self.b = title_weight, k1, b

    def score(self, query: str, items: Sequence[RerankItem]) -> np.ndarray:
        q = _tok(query)
        if not q or not items:
            return np.zeros(len(items))
        docs = [Counter(_tok(it.title)) for it in items]
        abss = [Counter(_tok(it.abstract)) for it in items]
        N = len(items)
        df = Counter()
        for d, a in zip(docs, abss):
            df.update(set(d) | set(a))
        idf = {t: math.log(1 + (N - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
               for t in set(q)}
        avgdl = max(1.0, float(np.mean([sum(a.values()) + 1 for a in abss])))

        out = np.zeros(N)
        for i, (d, a) in enumerate(zip(docs, abss)):
            dl = sum(a.values()) + sum(d.values())
            s, covered = 0.0, 0
            for t in set(q):
                f = self.title_weight * d.get(t, 0) + a.get(t, 0)
                if f <= 0:
                    continue
                covered += 1
                denom = f + self.k1 * (1 - self.b + self.b * dl / avgdl)
                s += idf[t] * f * (self.k1 + 1) / denom
            # 覆盖率因子：命中查询词种类越多越可信，抑制"单词高频"的假阳性
            cov = covered / len(set(q))
            out[i] = s * (0.35 + 0.65 * cov)
        # 归一到 [0,1]，方便与其他 reranker 互换
        if out.max() > out.min():
            out = (out - out.min()) / (out.max() - out.min())
        return out


class APIReranker(BaseReranker):
    """OpenAI/Cohere 兼容的 /rerank 端点（vLLM、TEI、硅基流动均支持）。

    默认模型 BAAI/bge-reranker-v2-m3 —— 与 Ray-Source 一致，中英双语，
    对"中文查询 + 英文论文"的跨语言场景友好，这一点在本赛题很关键
    （用户查询多为中文，论文库为英文）。
    """
    name = "api"
    sigma = 0.12

    def __init__(self, base_url: str, model: str = "BAAI/bge-reranker-v2-m3",
                 api_key_env: str = "RERANK_API_KEY", batch: int = 32,
                 timeout: int = 60, ledger=None):
        import requests
        self.requests = requests
        self.base_url = base_url.rstrip("/")
        self.model, self.batch, self.timeout = model, batch, timeout
        self.api_key = os.environ.get(api_key_env, "")
        self.ledger = ledger
        self.session = requests.Session()
        self._fallback = LexicalReranker()

    def score(self, query: str, items: Sequence[RerankItem]) -> np.ndarray:
        if not items:
            return np.zeros(0)
        out = np.zeros(len(items))
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            for i in range(0, len(items), self.batch):
                chunk = items[i:i + self.batch]
                r = self.session.post(
                    f"{self.base_url}/rerank", headers=headers, timeout=self.timeout,
                    json={"model": self.model, "query": query,
                          "documents": [c.pair_text() for c in chunk],
                          "top_n": len(chunk)})
                r.raise_for_status()
                for row in r.json().get("results", []):
                    out[i + int(row["index"])] = float(row["relevance_score"])
                if self.ledger:
                    self.ledger.add_api("rerank")
        except Exception:                                     # noqa: BLE001
            # 精排端点不可用绝不能让整条流水线挂掉 —— 静默降级到词法回退
            if self.ledger:
                self.ledger.mark("errors::rerank")
            return self._fallback.score(query, items)
        return out


def qwen_rerank_url(base_url: str) -> str:
    """把 DashScope OpenAI 兼容地址转换为 qwen3-rerank 专用端点。"""
    clean = base_url.rstrip("/")
    for suffix in ("/compatible-mode/v1", "/api/v1"):
        if clean.endswith(suffix):
            return clean[:-len(suffix)] + "/compatible-api/v1/reranks"
    return clean + "/reranks"


class QwenReranker(BaseReranker):
    """千问 qwen3-rerank，一次批量语义精排；失败退回词法。"""
    name = "qwen"
    sigma = 0.10

    def __init__(self, base_url: str, model: str = "qwen3-rerank",
                 api_key_env: str = "DASHSCOPE_API_KEY", batch: int = 64,
                 timeout: int = 60, ledger=None):
        import requests
        self.endpoint = qwen_rerank_url(base_url)
        self.model, self.batch, self.timeout = model, batch, timeout
        self.api_key = os.environ.get(api_key_env, "")
        self.ledger = ledger
        self.session = requests.Session()
        self._fallback = LexicalReranker()

    def score(self, query: str, items: Sequence[RerankItem]) -> np.ndarray:
        if not items or not self.api_key:
            return self._fallback.score(query, items)
        out = np.zeros(len(items))
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {self.api_key}"}
        try:
            for offset in range(0, len(items), self.batch):
                chunk = items[offset:offset + self.batch]
                response = self.session.post(
                    self.endpoint, headers=headers, timeout=self.timeout,
                    json={"model": self.model, "query": query[:12000],
                          "documents": [c.pair_text(2400) for c in chunk],
                          "top_n": len(chunk),
                          "instruct": "Rank papers that satisfy every stated research constraint."})
                response.raise_for_status()
                for row in response.json().get("results", []):
                    idx = offset + int(row["index"])
                    if 0 <= idx < len(out):
                        out[idx] = min(1.0, max(0.0, float(row["relevance_score"])))
                if self.ledger:
                    self.ledger.add_api("rerank::qwen")
        except Exception:  # noqa: BLE001
            if self.ledger:
                self.ledger.mark("errors::rerank_qwen")
                self.ledger.note("rerank", "千问重排不可用，降级到词法重排")
            return self._fallback.score(query, items)
        return out


class SiliconFlowEmbeddingReranker(BaseReranker):
    """Use SiliconFlow embeddings as a bounded online semantic reranker.

    It embeds the query and current candidate pool only; unlike a full corpus
    vector database this is inexpensive enough for dev ablation, and it never
    changes the retrieval candidate set.  Thus a measured gain is a genuine
    reranking gain, not gold-aware retrieval.
    """
    name = "siliconflow_embedding"
    sigma = 0.16

    def __init__(self, model: str = "BAAI/bge-m3", api_key_env: str = "SILICONFLOW_API_KEY",
                 batch: int = 64, timeout: int = 60, ledger=None):
        import requests
        self.model, self.batch, self.timeout, self.ledger = model, batch, timeout, ledger
        self.key = os.environ.get(api_key_env, "")
        self.session = requests.Session()
        self._fallback = LexicalReranker()

    def _embed(self, texts: Sequence[str]) -> np.ndarray:
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        vectors = []
        for start in range(0, len(texts), self.batch):
            response = self.session.post("https://api.siliconflow.cn/v1/embeddings",
                headers=headers, timeout=self.timeout,
                json={"model": self.model, "input": list(texts[start:start + self.batch])})
            response.raise_for_status()
            data = sorted(response.json().get("data", []), key=lambda x: int(x.get("index", 0)))
            vectors.extend(row["embedding"] for row in data)
            if self.ledger:
                self.ledger.add_api("embed::siliconflow")
        a = np.asarray(vectors, dtype=np.float64)
        return a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-12)

    def score(self, query: str, items: Sequence[RerankItem]) -> np.ndarray:
        if not items or not self.key:
            return self._fallback.score(query, items)
        try:
            q = self._embed([query])[0]
            docs = self._embed([x.pair_text(4000) for x in items])
            return np.clip((docs @ q + 1.0) / 2.0, 0.0, 1.0)
        except Exception:
            if self.ledger:
                self.ledger.mark("errors::embed_siliconflow")
            return self._fallback.score(query, items)


class LocalEmbeddingReranker(BaseReranker):
    """Offline SentenceTransformer cosine reranker for an admitted pool.

    This is deliberately a candidate-pool reranker, never a corpus retriever:
    it only encodes papers which already survived L1 admission.  It can thus
    test an independent scientific semantic *ordering* signal without making
    a gold-aware candidate-recall claim.

    Large models such as BGE-M3 need special handling on a 4GB CUDA device.
    Loading fp32 weights directly to GPU and only then calling ``half()`` can
    OOM even though final fp16 inference fits.  We therefore load on CPU,
    convert to fp16, and then migrate to CUDA.
    """
    name = "local_embedding"
    sigma = 0.19

    def __init__(self, model_path: str, device: str = "cuda", batch: int = 1,
                 max_seq_length: int = 128, abstract_chars: int = 1800,
                 fp16: bool = True, ledger=None):
        self.model_path = str(model_path or "")
        self.device = str(device or "cpu").lower()
        self.batch = max(1, int(batch))
        self.max_seq_length = max(8, int(max_seq_length))
        self.abstract_chars = max(64, int(abstract_chars))
        self.fp16 = bool(fp16)
        self.ledger = ledger
        self._model = None
        self._fallback = LexicalReranker()

    def _load_model(self):
        if self._model is not None:
            return self._model
        if not self.model_path or not os.path.isdir(self.model_path):
            raise FileNotFoundError(f"local embedding reranker model not found: {self.model_path}")
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer

        target = self.device
        if target == "cuda":
            try:
                import torch
                if not torch.cuda.is_available():
                    target = "cpu"
            except Exception:
                target = "cpu"
        model = SentenceTransformer(
            self.model_path, device="cpu" if target == "cuda" else target,
            local_files_only=True)
        model.max_seq_length = self.max_seq_length
        if self.fp16:
            model.half()
        if target == "cuda":
            model.to("cuda")
        self._model = model
        return model

    def close(self) -> None:
        """Release optional GPU model memory at the end of an evaluation."""
        self._model = None
        if self.device == "cuda":
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

    def score(self, query: str, items: Sequence[RerankItem]) -> np.ndarray:
        if not items:
            return np.zeros(0)
        try:
            model = self._load_model()
            q = model.encode([query], batch_size=1, normalize_embeddings=True,
                             show_progress_bar=False, convert_to_numpy=True)
            docs = model.encode([item.pair_text(self.abstract_chars) for item in items],
                                batch_size=self.batch, normalize_embeddings=True,
                                show_progress_bar=False, convert_to_numpy=True)
            q = np.asarray(q[0], dtype=np.float32)
            docs = np.asarray(docs, dtype=np.float32)
            if docs.ndim != 2 or docs.shape != (len(items), len(q)):
                raise RuntimeError(f"unexpected local embedding shapes: {docs.shape}, {q.shape}")
            return np.clip((docs @ q + 1.0) / 2.0, 0.0, 1.0)
        except Exception:
            if self.ledger:
                self.ledger.mark("errors::local_embedding_rerank")
                self.ledger.note("rerank", "本地 embedding 重排不可用，降级到词法重排")
            return self._fallback.score(query, items)


class PaSaSelectorReranker(BaseReranker):
    """Official PaSa Selector-SFT distilled, lightweight query--paper scorer.

    ``sft_selector/train.jsonl`` supplies balanced True/False query--paper
    judgments.  The companion training script fits a compact TF-IDF pair model
    on that data only.  It is intentionally an L2 *reranker*: it never creates
    candidates, and can therefore not leak labels into retrieval.
    """
    name = "pasa_selector"
    sigma = 0.18

    def __init__(self, model_path: str, ledger=None):
        self._fallback = LexicalReranker()
        self.model = None
        self.vectorizer = None
        self.ledger = ledger
        try:
            import joblib
            bundle = joblib.load(model_path)
            self.model = bundle["model"]
            self.vectorizer = bundle["vectorizer"]
        except Exception:  # model absent/corrupt must preserve offline fallback
            if self.ledger:
                self.ledger.mark("errors::pasa_selector")

    def score(self, query: str, items: Sequence[RerankItem]) -> np.ndarray:
        if not items or self.model is None or self.vectorizer is None:
            return self._fallback.score(query, items)
        try:
            from sklearn.preprocessing import normalize
            q = normalize(self.vectorizer.transform([query] * len(items)))
            t = normalize(self.vectorizer.transform([x.title for x in items]))
            a = normalize(self.vectorizer.transform([x.abstract for x in items]))
            x = np.hstack([np.asarray(q.multiply(t).sum(axis=1)),
                           np.asarray(q.multiply(a).sum(axis=1)),
                           np.asarray(q.multiply(normalize(t + a)).sum(axis=1))])
            return np.asarray(self.model.predict_proba(x)[:, 1], dtype=np.float64)
        except Exception:
            if self.ledger:
                self.ledger.mark("errors::pasa_selector_score")
            return self._fallback.score(query, items)


class PaSaBGESelectorHeadReranker(BaseReranker):
    """Frozen BGE pair encoder plus the official PaSa Selector-SFT calibration head.

    The transformer is never updated at runtime.  Its pair-aware ``[CLS]``
    embedding is passed through the frozen StandardScaler + LogisticRegression
    bundle fitted exclusively from ``PaSa/sft_selector/train.jsonl``.  This is
    deliberately distinct from ``LocalReranker`` (base BGE classifier logit)
    and from the legacy TF-IDF ``PaSaSelectorReranker``.

    A configured supervised artifact must load *exactly*.  Falling back to a
    lexical scorer, a raw BGE logit, or a different head would turn a claimed
    end-to-end ablation into an unknowable mixture, so load/model mismatches
    fail explicitly instead.
    """
    name = "pasa_bge_selector_head"
    sigma = 0.10

    def __init__(self, model_path: str, selector_head_path: str,
                 device: str = "cuda", batch: int = 2, max_length: int = 384,
                 abstract_chars: int = 2500, fp16: bool = True,
                 trust_remote_code: bool = False, ledger=None):
        self.model_path = Path(str(model_path or "")).resolve()
        self.selector_head_path = Path(str(selector_head_path or "")).resolve()
        self.device = str(device or "cpu").lower()
        self.batch = max(1, int(batch))
        self.max_length = max(32, int(max_length))
        self.abstract_chars = max(64, int(abstract_chars))
        self.fp16 = bool(fp16)
        self.trust_remote_code = bool(trust_remote_code)
        self.ledger = ledger
        self.tokenizer = None
        self.model = None
        self.scaler = None
        self.classifier = None

    def _load_model(self):
        if self.model is not None:
            return
        if not self.model_path.is_dir():
            raise FileNotFoundError(
                f"PaSa BGE selector model directory is missing: {self.model_path}")
        if not self.selector_head_path.is_file():
            raise FileNotFoundError(
                f"PaSa BGE selector-head bundle is missing: {self.selector_head_path}")
        try:
            import joblib
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except Exception as exc:  # pragma: no cover - dependency-dependent
            raise RuntimeError("PaSa BGE selector head requires torch, transformers and joblib") from exc
        if self.device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError("PaSa BGE selector head requested CUDA, but CUDA is unavailable")
        if self.fp16 and not self.device.startswith("cuda"):
            raise ValueError("PaSa BGE selector head fp16 requires CUDA")

        try:
            bundle = joblib.load(self.selector_head_path)
            if bundle.get("kind") != "frozen_bge_selector_head_v1":
                raise ValueError("bundle kind is not frozen_bge_selector_head_v1")
            trained_model = Path(str(bundle.get("model_path") or "")).resolve()
            if trained_model != self.model_path:
                raise ValueError(
                    "selector-head model mismatch: "
                    f"bundle={trained_model}, requested={self.model_path}")
            if int(bundle.get("max_length") or 0) != self.max_length:
                raise ValueError(
                    "selector-head max_length mismatch: "
                    f"bundle={bundle.get('max_length')}, requested={self.max_length}")
            if int(bundle.get("abstract_chars") or 0) != self.abstract_chars:
                raise ValueError(
                    "selector-head abstract_chars mismatch: "
                    f"bundle={bundle.get('abstract_chars')}, requested={self.abstract_chars}")
            scaler, classifier = bundle["scaler"], bundle["classifier"]
            if not hasattr(scaler, "transform") or not hasattr(classifier, "predict_proba"):
                raise ValueError("selector-head bundle does not expose scaler/predict_proba")
        except Exception as exc:
            raise RuntimeError(
                f"cannot load PaSa BGE selector head: {self.selector_head_path}") from exc

        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        tokenizer = AutoTokenizer.from_pretrained(
            str(self.model_path), local_files_only=True,
            trust_remote_code=self.trust_remote_code)
        # Loading the 2.27 GB checkpoint in fp32 and only then calling
        # ``half()`` creates a short but fatal host-memory peak on a 4 GB
        # competition GPU / 16 GB laptop.  Ask Transformers to materialize
        # fp16 weights from the local safetensors shards up front instead.
        # This preserves the eventual CUDA dtype while avoiding the transient
        # fp32 copy; ``low_cpu_mem_usage`` is available through Accelerate.
        model_kwargs = {
            "local_files_only": True,
            "trust_remote_code": self.trust_remote_code,
            "low_cpu_mem_usage": True,
        }
        if self.fp16:
            model_kwargs["dtype"] = torch.float16
        model = AutoModelForSequenceClassification.from_pretrained(
            str(self.model_path), **model_kwargs)
        if not hasattr(model, "roberta"):
            raise RuntimeError(
                "PaSa BGE selector head expects the BGE XLM-R/roberta encoder architecture")
        if self.fp16 and next(model.parameters()).dtype != torch.float16:
            model.half()
        model.to(self.device)
        model.eval()
        self.tokenizer, self.model = tokenizer, model
        self.scaler, self.classifier = scaler, classifier

    def close(self) -> None:
        self.model = None
        self.tokenizer = None
        if self.device.startswith("cuda"):
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

    def score(self, query: str, items: Sequence[RerankItem]) -> np.ndarray:
        if not items:
            return np.zeros(0, dtype=np.float64)
        self._load_model()
        assert self.tokenizer is not None and self.model is not None
        assert self.scaler is not None and self.classifier is not None
        try:
            import torch
            values: list[np.ndarray] = []
            # Exact Selector-SFT / frozen-pool pair representation.  Do not
            # reuse ``RerankItem.pair_text`` here: that generic helper uses a
            # single newline, while this calibrated head was trained and
            # validated with the double-newline separator below.
            documents = [f"{item.title}\n\n{item.abstract[:self.abstract_chars]}"
                         for item in items]
            with torch.inference_mode():
                for start in range(0, len(documents), self.batch):
                    docs = documents[start:start + self.batch]
                    encoded = self.tokenizer(
                        [query] * len(docs), docs, padding=True, truncation=True,
                        max_length=self.max_length, return_tensors="pt",
                    ).to(self.device)
                    hidden = self.model.roberta(**encoded, return_dict=True).last_hidden_state
                    cls = hidden[:, 0, :].float().cpu().numpy()
                    probability = self.classifier.predict_proba(
                        self.scaler.transform(np.asarray(cls, dtype=np.float32)))[:, 1]
                    values.append(np.asarray(probability, dtype=np.float64))
            scores = np.concatenate(values) if values else np.zeros(0, dtype=np.float64)
            if len(scores) != len(items) or not np.all(np.isfinite(scores)):
                raise RuntimeError("PaSa BGE selector head produced invalid score output")
            return np.clip(scores, 0.0, 1.0)
        except Exception:
            if self.ledger:
                self.ledger.mark("errors::pasa_bge_selector_head")
            raise


class LocalReranker(BaseReranker):
    """sentence-transformers CrossEncoder 本地权重（离线部署首选）。"""
    name = "local"
    sigma = 0.12

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3",
                 device: Optional[str] = None, batch: int = 32):
        self.batch = batch
        self._fallback = LexicalReranker()
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(model_name, device=device, max_length=512)
        except Exception:                                     # noqa: BLE001
            self.model = None

    def score(self, query: str, items: Sequence[RerankItem]) -> np.ndarray:
        if self.model is None:
            return self._fallback.score(query, items)
        pairs = [(query, it.pair_text()) for it in items]
        raw = np.asarray(self.model.predict(pairs, batch_size=self.batch),
                         dtype=np.float64)
        return 1.0 / (1.0 + np.exp(-raw))          # logit → 概率域


def build_reranker(cfg: Optional[dict] = None, ledger=None) -> BaseReranker:
    cfg = cfg or {}
    backend = (cfg.get("backend") or "lexical").lower()
    if backend == "api":
        return APIReranker(cfg["base_url"], cfg.get("model", "BAAI/bge-reranker-v2-m3"),
                           cfg.get("api_key_env", "RERANK_API_KEY"),
                           batch=int(cfg.get("batch", 32)),
                           timeout=int(cfg.get("timeout", 60)), ledger=ledger)
    if backend == "qwen":
        return QwenReranker(cfg.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                            cfg.get("model", "qwen3-rerank"),
                            cfg.get("api_key_env", "DASHSCOPE_API_KEY"),
                            batch=int(cfg.get("batch", 64)),
                            timeout=int(cfg.get("timeout", 60)), ledger=ledger)
    if backend in ("siliconflow_embedding", "siliconflow_embed"):
        return SiliconFlowEmbeddingReranker(cfg.get("model", "BAAI/bge-m3"),
            cfg.get("api_key_env", "SILICONFLOW_API_KEY"), int(cfg.get("batch", 64)),
            int(cfg.get("timeout", 60)), ledger=ledger)
    if backend in ("local_embedding", "local_embed", "sentence_embedding"):
        return LocalEmbeddingReranker(
            cfg.get("model_path", cfg.get("model", "")),
            cfg.get("device", "cuda"), int(cfg.get("batch", 1)),
            int(cfg.get("max_seq_length", 128)),
            int(cfg.get("abstract_chars", 1800)),
            bool(cfg.get("fp16", True)), ledger=ledger)
    if backend in ("pasa_selector", "selector"):
        return PaSaSelectorReranker(cfg.get("model_path", ""), ledger=ledger)
    if backend in ("pasa_bge_selector_head", "bge_selector_head"):
        return PaSaBGESelectorHeadReranker(
            cfg.get("model_path", cfg.get("model", "")),
            cfg.get("selector_head_path", cfg.get("selector_head", "")),
            cfg.get("device", "cuda"), int(cfg.get("batch", 2)),
            int(cfg.get("max_length", 384)), int(cfg.get("abstract_chars", 2500)),
            bool(cfg.get("fp16", True)), bool(cfg.get("trust_remote_code", False)), ledger=ledger)
    if backend == "local":
        return LocalReranker(cfg.get("model", "BAAI/bge-reranker-v2-m3"),
                             cfg.get("device"))
    return LexicalReranker()


# --------------------------------------------------------------------------- #
def rrf_fuse(rank_lists: Dict[str, List[str]], k: int = 60,
             weights: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """Reciprocal Rank Fusion：融合异构通道，无需分数标定。

    同样来自 Ray-Source 的检索栈（BM25 + FAISS → RRF）。在我们的场景里
    融合的通道更多：lexical / dense / citation-forward / citation-backward /
    author-lineage / venue-scan。
    """
    weights = weights or {}
    scores: Dict[str, float] = {}
    for ch, lst in rank_lists.items():
        w = weights.get(ch, 1.0)
        for r, pid in enumerate(lst):
            scores[pid] = scores.get(pid, 0.0) + w / (k + r + 1)
    return scores
