# PaSa 学术论文检索系统优化咨询材料

> 目的：请外部 AI/研究助手帮助诊断 ScholarNexus 在 **PaSa / AutoScholarQuery**
> 赛题上的真实瓶颈，并给出可复现、可在官方评测上验证的提升方案。
>
> 本文只陈述已经核验过的数据、代码和实验；不包含任何 API Key、个人隐私或
> 需要联网账号才能访问的凭据。请不要建议使用评测 gold、test 标签或人工答案
> 来进行候选生成、排序、训练或引用扩展。

---

## 1. 想请你解决的核心问题

我们正在做一个“用户自然语言问题 → 相关学术论文集合”的检索系统，目标是
提高 PaSa 官方 `AutoScholarQuery` 数据集上的召回和最终集合质量。

当前系统已有一个真实、可复现的改进：按 query 选择锚点论文的相关 section，
只展开这些 section 的引用（而不是展开整篇论文所有参考文献）。在官方 dev
前 20 题上，它将严格 arXiv-ID Recall@20 从 `0.125` 提升至 `0.225`；进一步
叠加一个由官方 Selector SFT 数据训练的轻量相关性分类器后达到 `0.260`。

但结果仍然不够好，且 20 条 query 的样本太小，统计置信度不足。我们希望获得
高质量建议，重点回答：

1. **真正最大瓶颈是什么？** 是全库候选召回、anchor paper 选择、section 选择、
   citation expansion 噪声，还是 final reranker/selector？
2. 在没有论文全文正文、只有 `section heading -> cited paper titles` 的 PaSa
   archive 条件下，怎样做更强、更可靠的 section-aware citation retrieval？
3. 如何最有效利用官方 `sft_selector/train.jsonl` 的 19,826 条平衡 query-paper
   标注，训练/蒸馏一个真正有赛题增益的 Selector？
4. 是否应优先建设全库 dense retrieval（以及什么 embedding / multi-vector /
   hybrid 方法），而不是继续调 BM25、RRF 或规则？
5. 在仅有一张 RTX 3050 Laptop 4GB GPU、可选商业 rerank API、但希望方案也能
   离线复现的约束下，最有性价比的实现路径是什么？

我们希望的是带明确实验设计的建议，例如：

```text
改动 X
→ 为什么它适合 PaSa 的 gold 构造机制
→ 怎样确保不泄漏标签
→ 应做哪几个 dev 消融
→ 应报告哪些指标与显著性检验
→ 预期改善的是 candidate recall，还是 reranking precision
```

不希望得到泛泛的“用更大模型 / 用 RAG / 多试几个 embedding”建议。

---

## 2. PaSa 赛题与官方资源：已核验事实

### 2.1 官方代码与数据

使用的是 PaSa 官方 GitHub 实现及其公开数据。官方 README 对系统的描述是：

```text
Crawler: 根据用户 query 生成检索式，并为论文选择要展开的 section。
Selector: 根据 user query + paper title + abstract 判断论文相关性。
```

官方评测脚本：`metrics.py`。

它读取一组 `PaperNode` JSON，按论文标题（只保留字母后）做匹配，并报告：

```text
crawler recall / selected precision / selected recall / Recall@100 / Recall@50 / Recall@20
```

**重要注意**：官方 `metrics.py` 是标题匹配，可能被近似标题或同名论文虚高。
因此我们的实验同时用：

1. 官方原版 `metrics.py`；
2. 自己实现的 strict arXiv-ID matching（预测和 gold 必须 ID 完全匹配）。

对外报告时，请优先相信 strict-ID，官方脚本作为赛方口径的补充。

### 2.2 官方 paper archive 的真实结构

官方资源中的：

```text
paper_database/cs_paper_2nd.zip
```

包含约 **555,262** 篇 CS 论文。单条数据结构的关键字段为：

```json
{
  "title": "...",
  "abstract": "...",
  "sections": {
    "section heading": ["cited paper title 1", "cited paper title 2"]
  },
  "source": "..."
}
```

这件事非常关键：`sections` **不是正文 chunk**；它只保存“章节标题 → 该章节的
被引论文标题”。因此不能假装系统拿到了论文完整正文，也不能直接做正文 passage
embedding。当前我们能做的真实任务是：

```text
query
→ 给 anchor paper 的 section heading 打分
→ 选择少数 section
→ 取这些 section 的 cited-paper titles
→ 用 id2paper.json 将 title 映射到 arXiv ID
→ 这些论文只是候选，必须再次被 rank/selector 判断
```

### 2.3 官方 Selector SFT 数据

官方文件：

```text
sft_selector/train.jsonl
```

已核验数量：**19,826** 条 query-paper 对，正负样本严格平衡：

```text
True:  9,913
False: 9,913
```

每条输入的形式近似：

```text
User Query: <query>
Searched Paper:
  Title: <title>
  Abstract: <abstract>
Output: Decision: True / False + rationale
```

这是一份很有价值的、与赛题语义直接对齐的 relevance supervision。它可以用来
训练 pairwise Selector，但不应与 AutoScholarQuery dev/test gold 混用。

### 2.4 PaSa 查询的机制性难点

PaSa `AutoScholarQuery` 的 query 通常来自论文 Related Work 的语义改写，而不是
论文标题/摘要的原句。因此典型 query 与答案论文之间会出现：

```text
用户问题：描述任务、机制、对比或改进目标
论文标题：方法名、缩写、具体模型名
论文摘要：可能只间接提到 query 所描述的关系
```

这导致纯关键词 FTS/BM25 很容易召回不到正确论文，或者只召回到领域相近但不是
回答该问题的论文。

---

## 3. 当前系统架构

项目名：`ScholarNexus`。

当前端到端管线：

```text
自然语言 query
  │
  ├─ QueryLens：规则/LLM 解析 query、约束、类型、检索式
  │
  ├─ MultiProbe：多源/多通道候选召回
  │     ├─ PaSa 本地 SQLite FTS5：abstract
  │     ├─ PaSa 本地 SQLite FTS5：title + abstract
  │     └─ PaSa 本地 SQLite FTS5：all fields
  │
  ├─ RRF + L0/L1：去重、约束过滤、粗排
  │
  ├─ 可选：从高置信 anchor candidates 做 citation expansion
  │     └─ PaSa archive 的 sections / cited paper titles
  │
  ├─ L2 reranker：词法 / API cross-encoder / 当前轻量 PaSa Selector
  │
  ├─ 概率校准、coverage estimate、F1 gate
  │
  └─ 返回 Top-K / core / partial
```

### 3.1 当前 PaSa FTS 设计

为官方 archive 建了只读 SQLite FTS5 索引。每条 query 有 3 个独立词法视图：

```text
lexical:pasa:abstract
lexical:pasa:title_abstract
lexical:pasa:all_fields
```

每个通道分别有自己的 rank list；之后通过 RRF 融合，而不是先混为一个检索结果。

理由：abstract、title、all-fields 的发现机制并不完全相同，保留 channel identity
既能提高 RRF 的稳定性，也有助于 candidate coverage 分析。

### 3.2 当前 L1 通道配额保护

我们发现单靠 RRF/L1 全局截断会过早删除“只被一个通道发现”的候选。为此新增：

```json
"l1_channel_quotas": {
  "lexical:pasa:abstract": 180,
  "lexical:pasa:title_abstract": 180,
  "lexical:pasa:all_fields": 180,
  "cite_bwd_section": 120
}
```

逻辑：

```text
先按每个独立 channel 的 L1 分取 Top-N
→ 候选去重
→ 再用全局 L1 分补齐到 keep
→ 最终输出仍按 L1 分排序
```

它只保护候选“存活”，不把 channel 身份作为最终相关性加分。

单独开启配额，在当前三条高度相关的词法通道上尚未改变 Top-20 指标；因此我们把
它视为工程防护与 dense/citation future-proofing，不把它声称为有效增益。

### 3.3 当前 section-aware citation expansion

原先系统行为：

```text
seed paper
→ 展开所有 section 的所有 references
→ 大量图噪声
```

当前行为：

```text
seed paper + raw user query
→ section score(section heading, query)
→ 选择 top-2 sections
→ 只展开这些 section 的 references
→ 每个 reference 仅作为 candidate
→ 重新经过 L1 / L2 / Selector
```

现有 section score 是保守启发式：

```text
2 × heading-query token overlap
+ Related Work / Prior Work / Literature Review 的弱先验
+ Background / Introduction 的更弱先验
```

重要限制：它只能读 section heading，不能读 section 正文，所以其语义选择能力还很
有限。我们希望咨询更好的处理方式。

当前 expansion safety gate：

```text
先把初始候选做 L0/L1
→ 只选择 s_constraint >= 0.42 的候选作 citation seed
→ 每 query 最多 4 个 seeds
→ 每 seed 最多 40 篇 cited papers
→ 每篇扩展论文之后仍需 L1/L2 过滤
```

没有把 citation neighbor 自动当作正例，也没有使用 gold 选择 seed、section 或
reference。

### 3.4 当前轻量 PaSa Selector

为了先验证“官方 SFT relevance supervision 是否有用”，我们实现了一个零 API
成本的轻量 Selector：

```text
官方 sft_selector/train.jsonl
→ TF-IDF(query), TF-IDF(title), TF-IDF(abstract)
→ 3 个 pairwise cosine features：
   - query-title cosine
   - query-abstract cosine
   - query-(title+abstract) cosine
→ LogisticRegression
→ p(relevant | query, paper)
```

它只在已有候选上执行 L2 reranking，绝不创建候选。

训练时只使用官方 Selector SFT train：

```text
样本数：19,826
80/20 stratified held-out split
ROC-AUC：0.7566
Average Precision：0.7380
```

这些只是 selector-train 的内部 sanity check，**不是 PaSa dev 比赛结果**。

---

## 4. 已做实验及可信结果

### 4.1 历史候选召回诊断

这些数值全部按 arXiv ID 严格匹配；gold 只在每个 label-blind rank list 完成后用于
离线打分：

| 设置 | 样本 | 指标 | 结果 |
|---|---:|---|---:|
| abstract-only FTS | dev 前 100 | candidate Recall@20 | 0.1966 |
| all-fields FTS | dev 前 100 | candidate Recall@20 | 0.2182 |
| 三通道 Top-500 并集 | dev 前 100 | candidate Recall | 0.4343 |
| 三通道 Top-2000 并集 | dev 前 50 | candidate Recall | 0.5268 |
| RRF Top-1000 | dev 前 50 | candidate Recall | 0.4299 |
| RRF Top-1500 | dev 前 50 | candidate Recall | 0.4666 |

解读：

1. 纯 abstract 索引不足；
2. 多视图词法召回确实有价值；
3. 但即便 union Top-2000，仍有约一半 gold 根本不在候选池中；
4. RRF / L1 的压缩会继续丢失部分本可获得的 gold；
5. 所以 **candidate recall 是首要瓶颈**，而 final reranker 不是唯一问题。

### 4.2 API cross-encoder 的已有小实验

之前在小规模真实实验中，通用 `BAAI/bge-reranker-v2-m3` 显示出排序能力：

```text
词法端到端 Recall@20：约 0.125
通用 cross-encoder 端到端 Recall@20：约 0.185
```

这说明 semantic reranking 能提升排序；但它不能找回词法 candidate pool 中根本没有
的正确论文。因此目前不能仅依赖 reranker。

注：当前运行会话中没有注入商业 API 凭据，后续所有本轮实验都使用本地资源；本文
不包含任何历史密钥。

### 4.3 当前 P0 的严格对照：官方 dev 前 20 题

所有配置：

```text
- 官方 AutoScholarQuery dev 的第 0–19 条
- 不使用 test
- 不使用 dev gold 参与检索、排序、训练、seed、section selection 或扩展
- 每个结果都保存前 100 的 title/arXiv ID
- 同时跑 strict arXiv-ID scorer 与官方 metrics.py
```

结果：

| 配置 | strict Recall@20 | 官方 Recall@20 | 官方 Recall@50 | 官方 Recall@100 |
|---|---:|---:|---:|---:|
| Baseline：3-channel lexical | 0.125 | 0.125 | 0.185 | 0.235 |
| Baseline + L1 channel quotas | 0.125 | 0.125 | 0.185 | 0.235 |
| Quota + query-aware section citation expansion | 0.225 | 0.225 | 0.235 | 0.260 |
| 上述 + light PaSa Selector | **0.260** | **0.260** | **0.260** | **0.285** |

官方 `metrics.py` 的完整列含义为：

```text
crawler recall & selected precision & selected recall & Recall@100 & Recall@50 & Recall@20
```

三行原始输出：

```text
Baseline:
0.235 & 0.006 & 0.185 & 0.235 & 0.185 & 0.125

Section-only:
0.260 & 0.007 & 0.235 & 0.260 & 0.235 & 0.225

Section + light Selector:
0.285 & 0.007 & 0.260 & 0.285 & 0.260 & 0.260
```

### 4.4 query-level paired bootstrap：不要把小样本提升夸大

对每个 query 的 strict-ID recall 做 paired bootstrap，20,000 samples，固定随机种子。

#### section-only vs baseline

| 指标 | baseline | section-only | delta | 95% CI | improved / worse / tie |
|---|---:|---:|---:|---|---|
| Recall@20 | 0.125 | 0.225 | +0.100 | [0.000, 0.250] | 2 / 0 / 18 |
| Recall@50 | 0.185 | 0.235 | +0.050 | [-0.050, 0.175] | 2 / 1 / 17 |
| Recall@100 | 0.235 | 0.260 | +0.025 | [-0.075, 0.150] | 1 / 1 / 18 |

#### section + light Selector vs section-only

| 指标 | section-only | selector | delta | 95% CI | improved / worse / tie |
|---|---:|---:|---:|---|---|
| Recall@20 | 0.225 | 0.260 | +0.035 | [-0.065, 0.160] | 2 / 1 / 17 |
| Recall@50 | 0.235 | 0.260 | +0.025 | [-0.075, 0.150] | 1 / 1 / 18 |
| Recall@100 | 0.260 | 0.285 | +0.025 | [-0.075, 0.150] | 1 / 1 / 18 |

**当前严谨结论**：

- section-aware expansion 是一个值得继续验证的真实正向信号；
- 轻量 Selector 在 dev20 上有正向迹象，但统计上不稳定；
- 不应声称已经统计显著，也不应依据 dev20 冻结最终方案；
- 下一步必须扩大到至少 dev100 做完全相同的 paired comparison。

### 4.5 citation expansion 的运行审计

在 section-only dev0–19 实验中：

```text
20 queries 中，19 条实际触发 citation expansion
平均每 query：4 个 citation seeds
触发的 query 平均：约 31.7 条 section citation edges
```

所以 section gain 不是“配置设置了但没有运行”造成的假象。它实际读取官方 archive
并按 section 取回了不同于词法召回的论文候选。

### 4.6 当前最优实验配置：精确参数

为避免外部建议基于错误假设，以下是当前 `section + light Selector` 运行的关键参数：

```json
{
  "retrieval": {
    "sources": ["PaSa local FTS only"],
    "lexical_views": ["abstract", "title_abstract", "all_fields"],
    "per_query_limit": 500,
    "max_search_limit": 2000
  },
  "candidate_control": {
    "l1_keep": 700,
    "l1_channel_quotas": {
      "lexical:pasa:abstract": 180,
      "lexical:pasa:title_abstract": 180,
      "lexical:pasa:all_fields": 180,
      "cite_bwd_section": 120
    },
    "l2_keep": 150
  },
  "citation": {
    "citation_expand_seeds": 4,
    "citation_expand_limit": 40,
    "citation_section_max_sections": 2,
    "citation_seed_min_constraint": 0.42,
    "citation_graph_min_constraint": 0.42
  },
  "decision": {
    "max_rounds": 1,
    "l3_policy": "disabled",
    "use_propensity": false,
    "calibrator": "rank_decay",
    "n_hat_prior_override": 5
  }
}
```

其中：

```text
per_query_limit = 每个 FTS view 的候选数
l1_keep         = 进入 L2 的最多候选数
l2_keep         = 进入 final calibration / top output 的最多候选数
section max=2   = 每个 citation seed 最多选两个 section
seed=4          = 每个 query 最多扩展四篇 anchor paper
expand=40       = 每个 seed 最多从选中 section 带入 40 篇 references
```

当前没有启用：

```text
- 多轮 query evolution
- L3 LLM 逐篇核验
- OpenAlex / Semantic Scholar / arXiv 在线检索源
- 全库 dense vector index
- test 集结果驱动的任何调参
```

原因不是这些方向一定无效，而是它们尚未在当前严格 dev 协议下证明正收益，或者缺少
稳定、可复现的本地数据支撑。

### 4.7 已尝试、但目前没有证实有效或不应作为主路线的内容

请将这部分也纳入诊断，避免重复建议已经失败的低收益路线。

#### (a) 仅增加/调整词法检索字段

尝试过 abstract-only、title+abstract、all-fields、不同词权重、停用词/词干变体和
RRF 参数。结论：多视图保留有价值，但仅靠这些微调无法解决 query 与答案论文的
语义改写错配。它们最多改善 lexical candidate recall 的局部表现。

#### (b) 只用 RRF 融合多通道

问题：RRF 奖励多通道一致性，但 PaSa 的正确答案可能只在一个独立通道出现，例如
title-only、dense 或 section citations。因此 RRF 被错误用作“淘汰器”时，会压掉
唯一发现者。L1 quotas 修复的是这一结构风险；但在目前 3 个互相高度重叠的 lexical
views 中，没有直接带来 dev20 的最终增益。

#### (c) 展开 anchor 的全部 references

这是早期实现。问题非常明显：一篇论文整篇的 references 跨越背景、方法、实验、
实现细节和无关领域，带入了大量图噪声；候选池变大不等于 relevant candidates 增加。
因此已改成 section-aware expansion。请不要建议恢复全量 reference expansion，除非
可以给出强过滤/强 selector 的依据和实验设计。

#### (d) 仅靠 citation graph / PPR / co-citation 分数

当前实现会计算受约束的 graph prior，但明确要求候选先通过 query constraint 初筛，
才允许 graph score 加分。原因：引文邻近、共同引用或高中心性不是 query relevance 的
替代。早期弱约束图扩展会让宽泛、高被引论文获得虚高的图分。

请讨论图方法时，重点说明怎样让 graph traversal 始终受 query semantics 约束。

#### (e) query evolution / LLM 生成更多检索式

系统保留了 query evolution 接口，但当前默认关闭。已有尝试没有稳定增益，主要风险是
模型生成宽泛近义词或无关 subquery，使有限候选预算被噪声消耗。若建议重新开启，请给
出受控 query expansion 的形式，例如 entity/method extraction、反向引用词、检索式
质量过滤或 budget allocation，而不是泛泛的 LLM rewrite。

#### (f) L3 通用 LLM judge

系统曾有对少量候选做 LLM 约束核验的 L3 层，并要求模型输出可在 title/abstract 中
验证的证据片段；无法验证的证据会被拒绝。当前默认关闭，因为小规模实验未显示稳定
净收益，而且它不能弥补 candidate missing，成本和延迟较高。

如果建议 LLM judge，请说明：

```text
- 应判哪些候选（如 only boundary candidates / citation candidates）？
- 如何在 PaSa 的短 title+abstract 条件下避免 hallucinated relevance？
- 如何用 final F1 / recall 的真实收益证明值得付费？
```

#### (g) 通用 embedding / reranker 的局部实验

曾完成过小规模 SiliconFlow BGE embedding / reranker 实验。得到的合理结论是：通用
semantic reranker 有排序能力，但当前最大问题仍是 candidate recall。这里要区分两件
事：

```text
候选池内 embedding rerank：只能改变现有候选的顺序。
全库 dense retrieval：可以找回 lexical FTS 根本遗漏的论文。
```

此前只做过局部 pool / 10k 级别实验，并未建立 55 万论文的可用 full-corpus dense
index。因此不能把“已尝试 embedding rerank”误解为“dense retrieval 已经失败”。

#### (h) 轻量 TF-IDF Selector

它训练集内 holdout AUC 合格，但 dev20 的增益不稳定，说明它更像一个便宜的 lexical
feature calibrator，而不是语义理解模型。它可以保留为 fallback 或 ablation，不应仅凭
当前结果成为最终主模型。

### 4.8 当前最终选择/F1 的明显短板

官方 `metrics.py` 的 selected precision / selected recall 也值得注意：

```text
Baseline selected precision:      0.006
Section-only selected precision:  0.007
Section+Selector precision:       0.007

Baseline selected recall:         0.185
Section-only selected recall:     0.235
Section+Selector selected recall: 0.260
```

这些 precision 很低的直接原因是我们的官方格式 adapter 为了忠实表达 ranked list，
按 `select_score = 1 - rank/100` 导出，官方脚本会将前 50 项视为 selected。它并不是
一个已经针对 PaSa F1 学好的最终集合选择器。因此：

```text
- 当前最可靠的比较是 strict Recall@20/50/100；
- official selected F1/precision 不能被包装成系统最终质量；
- F1-Gate / cardinality estimate 的最终集决策需要在更大 dev 上单独评估；
- 若外部 AI 对赛方真正的“提交格式和选择规则”有更准确理解，请指出。
```

### 4.9 官方指标与 strict-ID 指标的潜在不一致

官方 `metrics.py` 只使用 `keep_letters(title)` 进行匹配。因此以下情况可能造成官方
指标虚高或差异：

```text
- 同一 arXiv 论文的 title 版本、标点、LaTeX 清理差异；
- 不同论文存在高度相近甚至同名 title；
- archive / id2paper 的 title 版本和 gold title 版本不同；
- official script 不读取预测 arXiv ID。
```

我们的导出 JSON 同时写入 title 和 arXiv ID，但官方脚本仍只看 title。因此请建议：

```text
最终比赛是否必须完全遵循 title scoring？
为了诚信和可复核，是否应同时提交/保留 strict-ID audit？
怎样检查 title-version mismatch 是否导致 false negative / false positive？
```

---

## 5. 当前问题：为什么提升仍不够明显？

这是最需要外部 AI 深入诊断的部分。

### 问题 A：candidate recall 上限低

即便三通道词法 union Top-2000，strict candidate recall 也约只有 0.53。大量 query
与答案论文在标题/摘要层面词面错配；这些 gold 没有进入候选池，任何 reranker 都无法
补救。

需要回答：

```text
PaSa 上全库 dense retrieval / hybrid retrieval 最合适的实现是什么？
是否应该 index title、abstract、title+abstract、query-generated concepts 等多个向量？
是否有已经在 PaSa / AutoScholarQuery / scientific paper retrieval 中证实有效的模型？
```

特别希望获得关于以下方案取舍的建议：

```text
1. 单向量 title+abstract dense index
2. title vector + abstract vector 的 late interaction / MaxSim
3. BM25 + dense reciprocal fusion
4. query expansion / HyDE / pseudo-document
5. knowledge-concept / topic augmented retrieval
6. sparse learned retrieval（如 SPLADE 类）
```

### 问题 B：anchor paper 选择仍然受词法约束

section expansion 只有在“初始候选中找到了足够相关的 seed paper”时才能起作用。
当前 seed 由 L1 分和 `s_constraint >= 0.42` 选出。问题是：

```text
如果 query 的语义改写太强，正确 anchor 根本不在 lexical pool 中；
如果 seed 为领域相近但错误的论文，citation expansion 只会扩散噪声；
如果降低 seed threshold，图候选数量和噪声会爆炸。
```

希望获得的建议：

```text
如何单独训练/构造一个“query -> anchor paper” selector？
是否应该用 title/abstract semantic retrieval 选 anchors，再用 citation expansion？
是否应把 anchor relevance 和 final paper relevance 作为两个不同任务？
是否有 random walk / PPR / constrained graph retrieval 的更好做法？
```

### 问题 C：section selector 没有正文，只能看 heading

目前仅按 section heading 的 token overlap + prior 选择 section。即使得到增益，这仍
远弱于真正阅读 section 内容。

限制不可回避：官方 ZIP 里没有 section body。

希望讨论可行替代方案：

```text
- 可否仅用“section heading + 该 section 引用论文 title 集合”构造 section representation？
- 比如对引用标题做 embedding / centroid，使 section 的语义由 references 代理？
- 是否能在 offline preprocessing 阶段，为每个 section 建 citation-title embedding？
- 如何避免对 55 万论文全部 section 做昂贵 embedding？
- 是否应仅对 top anchors on-demand 处理？
- 在没有正文下，怎样把 query、section title、cited-paper titles 做三方匹配？
```

### 问题 D：当前轻量 Selector 太弱

官方 Selector SFT 是丰富的 query-title-abstract relevance supervision，但当前的
TF-IDF + LogisticRegression 只能使用表面词项相似度。它确实有内部 AUC，却没有表现
出稳定的 PaSa dev 增益。

希望获得具体训练建议：

```text
1. 最适合 SFT 数据的开源 cross-encoder base model 是什么？
   - BGE reranker 系列？
   - GTE / jina / e5 reranker？
   - 小型 Qwen / Llama 的 sequence classification 或 generative classifier？

2. 4GB VRAM 下是否可做 QLoRA？建议的模型规模、量化、batch、max length、LoRA target？

3. 是否应使用 distillation：强 API reranker / LLM 为硬 negatives 重新打分，
   再蒸馏到小模型？

4. 训练 target 应为 binary classification、pairwise ranking，还是 listwise ranking？

5. 如何防止官方 SFT 的 query 分布与 AutoScholarQuery dev 产生数据泄漏或近重复？

6. 如何让 selector 重视“完整满足所有约束”而非主题相近？
```

### 问题 E：运行成本与实验效率

当前本地机器：

```text
GPU: NVIDIA GeForce RTX 3050 Laptop GPU, 4GB VRAM
数据: 本地 PaSa ZIP + SQLite FTS
```

运行 20 条 dev 的端到端 section+selector 实验约数分钟；如果逐配置跑 1000 条会很慢。

希望获得科学而不浪费预算的实验策略：

```text
- dev0–19 预检后，下一阶段该用 dev100、dev200 还是全 dev1000？
- 怎样做 sequential testing / early stopping，避免在 dev 上反复调过拟合？
- 以 query-level bootstrap / randomization test 为准，最小需要多少题才有判断力？
- 如何固定一份 dev-tuning split 和 dev-validation split？
- 何时冻结配置、再跑公开 test？
```

---

## 6. 已读论文及当前理解

以下不是要求你重复检索，而是提供已读结论，欢迎纠错或补充：

### PaSa（官方论文/仓库）

已确认：Crawler 负责查询与 section expansion，Selector 以 query + title + abstract
判断相关性。官方方法的核心确实是“有控制的 section-level citation expansion”，
而不是无差别引用图爬取。

### SPAR / RefChain 类工作

已确认：受控 reference chaining 可以提升 raw recall，但容易损害 precision；简洁的
relevance prompt 通常比复杂 prompt 稳定。说明 citation expansion 必须和强 Selector
配合，不能把扩展邻居默认视为相关。

### PaperRegister / PaperScout / PaperPilot

已确认：抽象级索引会错过细粒度 scientific query；chunk / aspect-aware retrieval 有
价值。但当前 PaSa archive 没有正文，因此不能直接照搬 chunk retrieval。PaperScout
效果与 PaSa 强相关，但依赖重训练官方 selector，官方级训练成本较高。

### SemRank / LitSearch / Chain-of-Retrieval

已确认：

```text
- corpus-grounded concept/keyphrase index 可以补强 BM25/dense；
- 直接把全文塞成一个 embedding 往往不理想；
- 多视图 / aspect-aware representation 常优于 abstract-only；
- stronger reranker 对学术检索很关键；
- 但论文到论文引用预测任务不能完全等价用户 query 到论文检索。
```

请重点指出：哪些结论可以安全迁移到 PaSa，哪些不能。

---

## 7. 不可违反的实验与诚信约束

请在建议方案中遵守以下约束：

1. **不能使用 dev/test gold 做检索、排序、seed 选择、section 选择、训练样本生成、
   citation expansion 或 query rewrite。**
2. dev 可用于调参；冻结配置后再测 test。不能反复按 test 结果改参数。
3. 所有核心指标同时报告：
   - strict arXiv-ID Recall@20 / @50 / @100；
   - 官方 `metrics.py` 输出；
   - query-level paired bootstrap CI；
   - candidate recall 和 final recall 分开报告。
4. 不要只按标题相似度报告“命中”。
5. 不要把 citation neighbor、同领域论文或 paper title match 自动视为正例。
6. 对增强模型请给出关闭/回退策略，保证无 API、模型下载失败或 GPU 不足时系统仍可运行。
7. 不建议用任何未授权私有数据、付费数据或不可复现的人工标注作为主要结果来源。

---

## 8. 已实现代码与可复现产物

项目根目录中与本咨询最相关的文件：

```text
scholarnexus/sources/pasa_corpus.py
  - PaSa FTS source
  - official ZIP reading
  - references_for_query(): query-aware section citation expansion

scholarnexus/retrieval/multiprobe.py
  - multi-channel retrieval
  - citation expansion integration

scholarnexus/core/judge.py
  - L0/L1/L2
  - L1 channel quota protection

scholarnexus/rank/rerank.py
  - LexicalReranker
  - API/local reranker fallback
  - PaSaSelectorReranker (light TF-IDF distilled selector)

scripts/train_pasa_selector.py
  - train-only official Selector SFT parser/trainer

scripts/run_public.py
  - strict arXiv-ID evaluation
  - saves top-100 IDs/titles and label-blind trace

scripts/export_pasa_official_from_run_public.py
  - exports ranking to official PaperNode JSON

scripts/compare_pasa_reports.py
  - strict ID paired bootstrap comparison
```

重要配置：

```text
configs/pasa_multichannel_lexical_dev.json
configs/pasa_p0_quota_dev.json
configs/pasa_p0_quota_section_dev.json
configs/pasa_p0_quota_section_selector_dev.json
```

本轮的主要报告：

```text
docs/eval/pasa-p0-baseline-dev0-19-strict.json
docs/eval/pasa-p0-quota-section-dev0-19-strict.json
docs/eval/pasa-p0-quota-section-selector-dev0-19-strict.json
docs/eval/pasa-p0-section-vs-baseline-dev0-19-paired.json
docs/eval/pasa-p0-selector-vs-section-dev0-19-paired.json
```

所有本轮代码回归测试状态：

```text
51 / 51 passed
```

---

## 9. 希望外部 AI 最终输出的格式

请尽量按下面格式回答，而不是泛泛建议：

```markdown
## 诊断结论
- 主要瓶颈排序：1) ... 2) ... 3) ...
- 为什么当前 section gain 小但可信 / 或为什么可能是偶然

## 推荐路线（按预期收益 / 实现成本排序）
### R1：<方案名>
- 改什么：
- 为什么符合 PaSa：
- 需要的数据：
- 不泄漏保证：
- 训练/索引/推理细节：
- 4GB GPU / CPU 可行性：
- 风险与 fallback：
- 最小消融实验：
- 成功判据：

### R2：...

## 不建议做的事情
- ...

## dev 评测协议
- train/dev-tune/dev-validation/test 切法：
- 每项要报告的指标：
- bootstrap / 显著性方案：

## 可直接给工程师的伪代码或模块接口
```

如果认为某条当前方向有根本性问题，请明确说出，并基于 PaSa 数据实际可获得字段
给替代方案；不要假设可以访问并不存在的 paper full text。

---

## 10. 关键实现逻辑（伪代码级细节）

本节给出足够接近代码的说明，方便外部 AI 审查算法逻辑、指出错误假设或直接替换
模块。变量名与当前工程大体一致。

### 10.1 PaSa 多视图 FTS

```python
def query_terms(query):
    # 英文 token；移除常见礼貌词和泛化词，例如 paper/work/about/the/and
    # 最多保留 18 个 term，避免 FTS query 过宽
    return normalized_terms

def fts_queries(query):
    terms = query_terms(query)
    return {
        "abstract":       ' OR '.join(f'abstract:"{t}"' for t in terms),
        "title_abstract": ' OR '.join(f'(title:"{t}" OR abstract:"{t}")' for t in terms),
        "all_fields":     ' OR '.join(f'"{t}"' for t in terms),
    }

for view, match in fts_queries(query).items():
    rows = sqlite.execute(
        "SELECT arxiv_id,title,abstract FROM papers "
        "WHERE papers MATCH ? "
        "ORDER BY bm25(papers, 0.0, 3.0, 1.0) LIMIT ?",
        (match, per_query_limit),
    )
    absorb(rows, channel=f"lexical:pasa:{view}")
```

解释与隐患：

```text
- abstract 在 BM25 中权重 3.0，title 权重 0.0 或由 FTS query 结构间接发挥作用；
- `all_fields` 可能命中元数据/其他字段，因此召回更广、噪声也更高；
- query 词项是 OR，不是 AND，目的是避免细粒度 query 出现零召回；
- 这也使泛化词、错误词义和 query 中的冗余动词带来很多噪声；
- 当前英文 tokenizer 对缩写、连字符、方法名、公式/希腊字母和中文 query 的处理并不理想；
- 需要外部建议：PaSa 是否应使用更好的 scientific tokenization / entity normalization /
  acronym expansion / query term weighting。
```

### 10.2 RRF 与 L1 分数

```python
def rrf(rank_lists, k=60):
    score = defaultdict(float)
    for channel, ranked_pids in rank_lists.items():
        for rank, pid in enumerate(ranked_pids):
            score[pid] += channel_weight[channel] / (k + rank + 1)
    return score

def l1_score(candidate, query_plan):
    lexical_coverage = |query_tokens ∩ paper_tokens| / |query_tokens|
    n_channel_types = number_of_distinct(channel.split(':')[0])
    diversity = 1 - exp(-0.8 * n_channel_types)
    position = 1 / (1 + 0.08 * best_channel_rank)

    return (
        0.29 * normalized_rrf(candidate) +
        0.19 * graph_score(candidate) +
        0.16 * lexical_coverage +
        0.12 * diversity +
        0.08 * position +
        0.11 * quoted_title_similarity(candidate) +
        0.05 * constraint_match(candidate)
    )
```

潜在问题：

```text
- 权重是工程启发式，并不是在足够大的独立 dev 上学习的；
- `graph_score` 有机会通过 citation topology 放大错误 seed；
- `diversity` 以 channel 类型而不是真正独立概率建模，三条 lexical view 并不独立；
- query token overlap 与 FTS/BM25 信号高度相关，L1 可能重复奖励 lexical matching；
- 对纯语义改写 query，正确答案可能 lexical coverage 很低，L1 有误杀风险；
- quoted_title_similarity 对 method name/title locate query 有用，但对 broad related-work
  query 未必有用。
```

我们希望外部 AI 明确评价：

```text
1. 该 L1 是否应该被更简单的 union/top-per-channel 保留策略替代？
2. 是否应用 query-dependent learned fusion，而不是固定权重？
3. 如果训练一个 ranker，怎么在不使用 AutoScholarQuery dev/test gold 的前提下构造训练？
4. 官方 Selector SFT 是否可监督 L1 / L2 fusion，而不仅是 L2 binary classifier？
```

### 10.3 当前 citation seed 与 section expansion 伪代码

```python
# 初始候选完成多通道融合后：
initial_l1 = l1_rank(initial_candidates, keep=l1_keep, quotas=quotas)

seeds = [c for c in initial_l1 if c.constraint_score >= 0.42]
seeds = sorted(seeds, key=lambda c: c.l1_score, reverse=True)[:4]

for seed in seeds:
    archive_row = zip.read(title_key(id2paper[seed.arxiv_id]))
    sections = archive_row["sections"]  # heading -> list[cited_title]

    chosen_sections = topk(
        sections.keys(),
        key=lambda heading:
            2.0 * token_overlap(heading, raw_query)
            + prior_if_related_work_background_introduction(heading),
        k=2,
    )

    for heading in chosen_sections:
        for cited_title in sections[heading]:
            cited_arxiv_ids = title_to_ids[title_key(cited_title)]
            add_as_candidate(cited_arxiv_ids, channel="cite_bwd_section")
            graph.add_edge(seed, cited_id)

# 所有新论文再次经过 L0/L1/L2；没有 citation neighbor 直接晋级的规则。
```

这里有若干可能的根本问题，请逐条给判断：

```text
1. 将 `s_constraint >= 0.42` 作为 seed gate 是否合理？
   当前 constraint 是规则解析出来的，可能和真实 semantic relevance 不一致。

2. section heading token overlap 是否过弱？
   该 heading 可能是“3.2 Existing Methods”，不含目标领域词，却有正确 citations。

3. “Related Work”先验是否会导致系统性偏向？
   PaSa gold 的构造与 related-work 有关，这个先验可能合理，但也可能在 dev 上过拟合。

4. title_key 为“只保留字母、小写”的 title-to-ID mapping：
   同名/近同名标题可能有冲突；一些引用标题可能无法解析到 id2paper。

5. references 的 abstract 默认不 hydration（`reference_hydrate_limit=0`）：
   citation candidates 在 L2 时可能只有 title、没有 abstract。该选择减少 ZIP I/O，
   但可能明显伤害 Selector。是否应对少量 section references on-demand hydrate？

6. 当前只有 backward references，没有 forward citations：
   PaSa archive 数据形态是否允许离线建立 reverse index？值得吗？

7. 一跳扩展是否足够？二跳很可能噪声爆炸，是否有语义约束下的二跳策略？
```

### 10.4 当前轻量 Selector 的训练和推理

```python
# training -- only official sft_selector/train.jsonl
train, heldout = stratified_split(official_selector_sft, test_size=0.2, seed=20260823)
tfidf.fit(train.query + train.title + train.abstract)

def pair_features(query, title, abstract):
    q = l2_normalize(tfidf(query))
    t = l2_normalize(tfidf(title))
    a = l2_normalize(tfidf(abstract))
    return [cos(q, t), cos(q, a), cos(q, normalize(t + a))]

model = LogisticRegression(class_weight="balanced").fit(features(train), train.label)
score = model.predict_proba(features(query, candidate.title, candidate.abstract))[:, 1]
```

它的真实局限：

```text
- feature 只有 3 维；它基本只能表示表面术语相似；
- 没有 query/candidate 的 token interaction attention；
- 没有 hard negative mining；
- 没有 listwise “候选集合内谁更相关”的训练；
- citation candidate 缺 abstract 时，两个特征直接退化；
- SFT rationale 当前完全没有使用；
- 对同义改写、方法关系、否定约束、多条件 conjunction 的理解很弱。
```

这正是我们想让外部 AI 提供“强但可运行的 Selector 训练方案”的原因。

### 10.5 当前 final calibration / F1-Gate（不是当前主提升来源）

系统还包含相关概率校准、coverage estimate、cardinality prior 与 F1-Gate。简化后：

```text
L2 scores
→ adaptive score fusion
→ rank-decay / mixture calibrator producing p(relevant)
→ estimate target set size N-hat
→ choose prefix k approximately maximizing expected F1
→ output core / partial candidate set
```

当前 PaSa dev 实验为了隔离检索/排序改动，设置：

```text
use_propensity = false
calibrator = rank_decay
n_hat_prior_override = 5
L3 disabled
```

这意味着：当前优化结果主要应解释为 retrieval/ranking 的变化，而不是借由元数据
propensity 或复杂 final gate“调高”评测分数。另一方面，这也说明最终集合选择还没有
充分优化；请外部 AI 讨论它是否值得在获得强 Selector 后重新系统评测。

---

## 11. 数据、索引、环境与性能限制

### 11.1 本地文件和规模

```text
PaSa official paper ZIP: approximately 2.5 GB
Paper entries:            approximately 555,262
Local FTS database:        SQLite FTS5 built from the official archive
AutoScholarQuery dev:      1,000 queries
Selector SFT train:        19,826 labeled pairs
```

当前 FTS 记录至少含：

```text
arxiv_id, title, abstract
```

但 citation reference 的内容要从 ZIP 解压/读取。为了避免每 query 多次解析 archive
central directory，source 在一次 engine 生命周期中复用 ZipFile 句柄；Windows 上这个
过程仍然产生显著的磁盘 I/O、内存波动和总体延迟。

### 11.2 硬件/软件

```text
OS: Windows / PowerShell
GPU: NVIDIA GeForce RTX 3050 Laptop GPU, 4GB VRAM
Python: 3.12
CPU/RAM: 未作为可假设的充裕服务器资源
```

已安装并使用的本地 Python 包包括：

```text
numpy, requests, PyYAML, scikit-learn, scipy, joblib,
tqdm, beautifulsoup4, arxiv
```

当前没有将大型 Transformer reranker 常驻在 GPU；4GB 显存是实际约束。若建议模型微调，
请给出：

```text
- 是否能在 4GB 上运行；
- 量化方式（4-bit / 8-bit）、序列长度、batch/gradient accumulation；
- CPU offload 是否现实；
- 预期训练时长；
- 若不现实，推荐哪一种 API / 蒸馏替代；
- 模型权重和索引的磁盘规模。
```

### 11.3 当前运行时间

在当前机器上，section citation 路径的端到端实际耗时大致为：

```text
dev 前 20 条：数分钟（约 15–16 秒/条 ledger time，另外有 archive/进程开销）
```

因此全 dev1000 的多配置搜索成本很高，不能盲目网格搜索。希望建议一个分层评测计划：

```text
small pilot -> tuning split -> held-out dev validation -> frozen public test
```

### 11.4 商业 API 状态

工程具备 OpenAI-compatible rerank / embedding 接口，也曾做过真实 API 小实验。但当前
会话环境中没有注入可用云端 API key，因此本轮实验没有调用商业 API。

请不要要求提供或复述密钥。可以把“若具备合规 API 凭据”作为一个可选实验分支，并
说明调用量估算、缓存、重试和本地 fallback。

---

## 12. 当前已知 bug 风险、实现风险和待审查点

我们希望外部 AI 像审阅一个研究工程一样指出这些问题是否会污染结果。

### 12.1 标题到 arXiv ID 映射

当前 `_title_key(title)` 近似为：

```python
"".join(ch.lower() for ch in title if ch.isalpha())
```

它用于将 archive `sections` 中的 cited title 对齐到 `id2paper.json`。风险：

```text
- 版本标题、缩写、冒号/破折号、LaTeX、数字差异；
- 不同论文清理后 title 相同；
- cite title 可能不在 id2paper；
- 一个 title key 可能对应多个 arXiv IDs。
```

当前实现会保留匹配到的所有 IDs 并在后续去重。请建议更好的高 precision/high recall
reference resolution，不要使用 benchmark gold。

### 12.2 Citation candidate metadata 不完整

为了避免对大量 references 读取 ZIP，当前配置下 section expansion 的新候选常常是：

```text
title: present
abstract: empty
arxiv_id: present
source: pasa
```

这会使：

```text
- lexical L1 使用的 paper.text() 变弱；
- generic/learned reranker 缺少最关键 abstract；
- Selector 退化成 query-title matching；
- 但完整 hydration 可能使 ZIP I/O 变得很慢。
```

这可能是“section expansion 增加了候选，但增益有限”的最具体工程原因之一。请建议
可控的 hydration 方案，如只 hydration：

```text
- selected sections 的前 N 个 references；
- title/section score 较高的 references；
- L1 quotas 保留下来的 section candidates；
- Selector 不确定带附近的 candidates；
- 或预构建 compact arXiv-ID -> title+abstract KV store。
```

### 12.3 L1 channel quota 的顺序偏差

quota 配置按 dictionary insertion order 依次取候选。如果 channel 间候选重叠很多，前
一个 channel 可能先占用更多名额，后一个 channel 的“独特候选”只保留剩余位置。虽然
最终按 L1 分排序，但 admission 过程仍可能有顺序效应。

请判断是否应改为：

```text
- 先为每 channel 计算独特候选；
- round-robin / diversity-constrained selection；
- max coverage selection；
- per-channel quota after dedup; or
- learned candidate admission。
```

### 12.4 Query parser / constraints 的误解析

QueryLens 包含规则解析，可能把普通词错误识别为 venue/year/hard filter。系统有
“hard filter 后候选少于最小阈值则放宽为 verify constraint”的回退，但这仍可能改变
候选排序与 seed selection。

已知原则：metadata missing 不应被当作不满足；hard filter 不能静默导致全部 gold
被过滤。请建议如何审计 query parsing error 对 PaSa 结果的影响。

### 12.5 实验样本选择偏差

当前真实端到端对照主要是 dev index 0–19，不是随机抽样，也不是按 query 类型分层。
可能存在顺序偏差。后续必须：

```text
- 固定一个不参与开发的 dev-validation slice；
- 按 gold count / query length / topic / lexical difficulty 分层报告；
- 至少扩展到 100 条，最好全 1000 dev；
- 使用 paired tests 而不是只比较 macro mean。
```

请提出一套正式、竞争赛可接受的 split/评测协议。

### 12.6 当前报告没有“oracle rerank upper bound”

我们已有 candidate union recall，但没有系统地测：

```text
如果当前候选池中的 gold 能被完美排到最前，Recall@20 的理论上限是多少？
如果只改变 L1 admission，不改变 candidates，能提升多少？
section expansion 带进来的 gold 数量是多少？它们在 L1 / L2 / top20 各阶段如何流失？
```

这是下一步必须补的 diagnostic。请建议最有信息量的 per-query trace schema 与统计表。

---

## 13. 我们希望优先验证的具体技术假设

请按“最值得先做 / 预期收益 / 证据基础 / 实现成本 / 失败风险”排序评价以下假设。

### H1：全库 hybrid dense retrieval 会比继续强化 citation path 更先带来大幅提升

理由：strict candidate recall 的上限目前很低；citation expansion 依赖 lexical seed。

待回答：

```text
- 什么 embedding model 对 scientific query-paper retrieval 最适合？
- 应 embed title、abstract，还是 title+abstract？
- 文档长度截断策略？
- 用 FAISS/HNSW/SQLite vector extension，索引预计大小与构建时间？
- top-K dense 应取多少，再怎样和 FTS 融合？
- 如何避免 dense channel 在近邻噪声中冲掉精准 title hit？
```

### H2：用官方 Selector SFT 微调真正的 cross-encoder 能显著超过当前 TF-IDF Selector

理由：官方数据的 input/output 与本任务完全同构，当前模型仅使用了非常弱的特征。

待回答：

```text
- 推荐 base model、loss、negative strategy、max_length、training protocol；
- 是否用 rationale 做 auxiliary supervision；
- 用 pairwise/listwise contrastive 的可靠做法；
- 如何选 model without overfitting AutoScholarQuery dev；
- 如何评估 selector 本身：SFT heldout AUC/AP + end-to-end dev recall 是否足够？
```

### H3：section 的“引用标题集合语义”可以替代缺失的正文

建议构想：

```text
section representation = heading embedding + aggregate(embedding(cited paper titles))
query -> retrieve/select section by semantic similarity
```

可能实现层级：

```text
Level 0: on-demand 对 top anchors 的 cited titles 做 embedding/centroid
Level 1: 缓存常见 anchor 的 section centroids
Level 2: 全库预计算 section centroids / inverted index
```

待回答：这个假设是否学术上合理、如何避免 data leakage、如何可扩展到 55 万论文、
centroid 是否会被大量泛化引用稀释、是否有 set-to-query / late interaction 的替代？

### H4：citation reference hydration 是当前低成本、高收益缺口

理由：section 扩展得到的 candidate 经常缺 abstract，正好让当前 reranker 最弱。

待回答：是否应先做一个 bounded experiment：

```text
section-only, hydration=0 vs 8 vs 20 vs adaptive
```

在相同 seeds/sections 下报告：

```text
candidate recall, L1 survival, L2 recall@20, latency, ZIP reads, memory
```

这是否比先训练大模型更值得优先验证？

### H5：anchor selection 与 final relevance 应分开训练

当前同一个 L1 分既用于 seed admission 又用于 final candidate sorting；但两种任务不同：

```text
anchor relevance: “这篇论文的某个 section 是否可能通向 query 的相关文献？”
final relevance:  “这篇论文本身是否回答用户问题？”
```

待回答：是否应该针对 anchor 建独立 scorer（例如 query-to-survey/related-work affinity），
如何基于现有公开数据构建训练而不使用 benchmark gold？

### H6：多跳 citation expansion 是否值得

直觉上，二跳可能找回更多间接相关论文；但大概率产生图漂移。待回答：是否有下列受控
方式值得做：

```text
- 只从 selector 高分的一跳 papers 再扩展；
- 每跳必须重新 query-score；
- beam search with semantic reward；
- query-conditioned PPR；
- stop when marginal unique high-score candidates < threshold。
```

请依据 PaSa 任务机制说明是否值得，而不是只给一般图检索建议。

---

## 14. 推荐外部 AI 进行的“第一轮答复”范围

为了让咨询能立刻转化为工程任务，请优先回答以下 10 个问题：

1. 在 PaSa archive 没有正文的条件下，`section heading + cited-title set` 的最佳
   section selection 建模方法是什么？
2. 对 55 万 title+abstract 做 dense index，推荐哪些模型、索引和具体 K 值？
3. 官方 Selector SFT 最适合微调哪个可在 4GB / CPU fallback 环境实践的模型？
4. 不微调大模型时，能否用 stronger off-the-shelf cross-encoder + calibrated fusion
   达到可信增益？具体怎么做？
5. 当前 reference candidates 缺 abstract 应如何 hydration，如何做最小消融？
6. seed threshold、section count、citation fanout 怎样系统调参而不在 dev 过拟合？
7. 如何建立 candidate-stage oracle diagnostic，找出 gold 在哪个阶段丢失？
8. 当前官方 metrics.py title matching 与 strict ID mismatch 应怎样处理和报告？
9. 是否应该完全放弃当前 L1 fixed-weight fusion，改成什么？
10. 给出未来 1–2 周最优先的 3 个实验，按预期收益和成本排序。

---

## 15. 对外部 AI 的最终提醒

请把这里当作真实比赛/研究工程的审查，而不是概念设计题。

我们尤其需要你：

```text
✓ 指出当前方法真正错在哪里，即使结论不舒服；
✓ 区分“能提高训练/离线分类 AUC”和“能提高 PaSa end-to-end Recall@20”；
✓ 区分“candidate recall improvement”和“reranking improvement”；
✓ 所有建议都尊重本数据实际没有全文的事实；
✓ 给出能跑、能消融、能拒绝无效方案的实验；
✓ 优先提供有论文/公开实现/PaSa机制依据的技术路线；
✓ 指出潜在 leakage、metric gaming、test overfit 风险。
```

不需要你：

```text
✗ 重复常识性的“使用 RAG / 用大模型 / 多试模型”；
✗ 假定可以访问不存在的 section body/full paper PDF；
✗ 建议用 AutoScholarQuery dev/test answer 来选 seed、选章节或训练；
✗ 把当前 dev20 的小提升宣传成已显著；
✗ 只给论文名字而没有与本任务的落地映射。
```
