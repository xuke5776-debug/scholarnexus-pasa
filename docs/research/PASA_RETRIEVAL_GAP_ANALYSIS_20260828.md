# PaSa Retrieval Gap Analysis

Date: 2026-08-28

## Scope and conclusion

This is an evidence-led diagnosis of the current ScholarNexus PaSa adaptation.
It is not a claim that a paper, an open-source repository, or a new embedding
model will automatically improve the competition score.

The primary failure is **not candidate generation alone and not the choice of
one embedding API**.  The dominant failure is the learned-free path from a
wide candidate pool to the top-100 ranking:

1. the current pipeline retrieves many relevant papers into the pool,
2. L2 admission removes a large part of them before final ranking, and
3. the available lexical and online-BGE ordering signals do not reliably put
   the remaining relevant papers at the top for compositional academic queries.

The second, separate problem is **coverage**.  The local-only system has no
equivalent of the original PaSa Crawler's multi-query, multi-step search.
Consequently, a reranker can never recover papers missing from its candidate
pool.

## Direct measurements from this project

### A. Candidate-stage bottleneck

The frozen, query-only, eight-query train pilot at stable-hash offset 264 used
the current H8, raw-question MiniLM dense, lexical P2 configuration.  Gold
answers were joined only after the ranking artifact was written.

| Stage | Strict candidate recall | Meaning |
| --- | ---: | --- |
| Initial lexical + raw MiniLM pool | 0.6146 | Direct search finds most, not all, gold papers. |
| Citation-only additions | 0.1250 incremental | Section citations add two gold papers. |
| Full candidate pool | 0.7396 | Six of 22 gold IDs are still absent. |
| After L1=1000 | 0.7396 | L1 widening itself does not discard gold in this pilot. |
| L2 input=150 | 0.3229 | The principal observed loss: six gold papers hit `l2_input_cap`. |
| Final ranked top-100 | 0.3229 | Lexical L2 does not recover losses after admission. |
| F1-Gate selected prefix | 0.1250 | Set selection is a second, independent loss. |

Evidence: `docs/eval/pasa_candidate_flow_querylensfix_lexical_train8_offset264_20260828.json`.

This distinguishes two facts that must not be conflated:

- Candidate recall 0.7396 is an oracle ceiling for this exact pool, not system
  Recall@100.
- A stronger final scorer cannot recover the six missing IDs; a wider L2 input
  without a better ordering signal can still make top-100 worse.

### B. Online BGE does not solve the ranking problem

An actual SiliconFlow `BAAI/bge-reranker-v2-m3` run completed all eight pilot
queries with 19 online reranker calls per query and no fallback/error trace.
It is therefore a valid negative result, rather than an API failure.

| Arm | R@20 | R@50 | R@100 | Adaptive F1 |
| --- | ---: | ---: | ---: | ---: |
| Lexical P2, L2 input 150 | 0.2604 | 0.2604 | 0.3229 | 0.1095 |
| Online BGE P2, L2 input 150 | 0.2396 | 0.2813 | 0.3229 | 0.0852 |
| Online BGE P3, L2 input 300 | 0.2604 | 0.2813 | 0.2813 | 0.0852 |

P3 admitted more gold into its L2 input (0.4479 versus 0.3229), but its
ranking still dropped R@100 by 0.0417 against online-BGE P2.  It fails the
non-regression gate.  This rules out the simplistic conclusion that the
current problem is merely `150 is too small`.

Evidence: `docs/eval/pasa_querylensfix_online_bge_p3_vs_p2_train8_offset264_paired_20260828.json` and
`docs/eval/pasa_querylensfix_online_bge_p3_vs_p2_train8_offset264_summary_20260828.md`.

### C. Sealed-dev signal is weak and selection is undertrained

On the previous 20-query sealed `dev800-819` slice, the strict-ID lexical
ranking was R@20=0.1900, R@50=0.2472, R@100=0.2972.  A train-only
effective-cardinality predictor changed only output-prefix length and raised
adaptive F1 from 0.04838 to 0.06326.  The 20,000-draw paired 95% interval for
that F1 delta still crossed zero, and the predictor had only 32 train and 32
validation rollouts.  It is an encouraging but insufficiently reliable
selection experiment, not a replacement for per-paper relevance calibration.

Evidence: `docs/eval/PASA_CARDINALITY_DEV800_819_20260827.md`.

## Why the adaptation differs from the published PaSa system

The competition corpus and the repository name are shared, but the executed
retrieval policy is materially different.

| Published PaSa | Current full-evaluation P2 | Consequence |
| --- | --- | --- |
| Two trained 7B agents: Crawler and Selector | QueryLens/mock planning plus lexical L2 and a small MiniLM dense channel | No learned action policy for query generation, section choice, or relevance. |
| Crawler generates several search queries, searches, reads paper sections, and recursively expands citations | `max_rounds=1`, `enable_query_evolution=false`, 4 citation seeds, at most 2 sections, 40 references per seed | Much lower query and navigation diversity. |
| Default agent surface exposes two expansion layers and separate search/expansion budgets | One fixed candidate-construction pass | No exploration/ensemble opportunity. |
| Google/Serp search plus arXiv paper/section fetching | External sources are disabled for the local controlled evaluation | Papers outside local channel recall cannot enter the pool. |
| Selector scores every crawled paper against the detailed request | F1-Gate has weak rank-decay/cardinality evidence after L2 | The system lacks a reliable criterion-satisfaction probability for each paper. |

The original project documents a Qwen2.5-7B Selector/Crawler SFT path with
eight training processes and a PPO crawler with 16,000 episodes, two agents,
three rounds, and external search.  That exact route is not realistic on the
local RTX 3050 4GB.  Pretending otherwise would spend time on an infeasible
training plan rather than improve the submitted system.

Sources:

- [PaSa paper and reference implementation](https://github.com/bytedance/pasa)
- [Published action loop in `paper_agent.py`](https://github.com/bytedance/pasa/blob/main/paper_agent.py)
- [PaSa arXiv record](https://arxiv.org/abs/2501.10120)

## Related work and what transfers

### 1. Late interaction: ColBERTv2

[ColBERT](https://github.com/stanford-futuredata/ColBERT) stores token-level
document representations and scores a query with MaxSim late interaction.  It
is specifically designed to retain finer query-document interactions than a
single dense vector while remaining scalable.  This matches PaSa's
multi-constraint questions better than a generic single-vector cosine score.

**Transferable idea:** use late interaction as an L2 scorer or a candidate-only
rescoring experiment.  It directly targets the observed loss between the
wide L1 candidate set and top-100.

**Constraint:** full ColBERT indexing and training require GPU resources; the
project README explicitly says a GPU is required for training and indexing.
Do not attempt a full-corpus ColBERT index or fine-tune it first on a 4GB GPU.
First run a 32-query candidate-only feasibility and quality test after the
current full evaluation has released the GPU.

### 2. Learned sparse expansion: SPLADE

[SPLADE](https://github.com/naver/splade) learns sparse query/document
expansion while retaining inverted-index retrieval and lexical
interpretability.  Its maintainers describe hard-negative mining and
distillation as the improvements behind later models, and it includes BEIR
evaluation support.

**Transferable idea:** this is the most practical retrieval alternative to
the current hand-tuned FTS views.  It can add semantic expansion without
discarding exact technical terms, titles, acronyms, or constraint words.
That is particularly relevant because the current QueryLens fix shows that
generic polite wording can otherwise dominate retrieval anchors.

**Constraint:** a pre-trained zero-shot model may still mismatch this
synthetic-AI corpus.  Compare its candidate recall and union-with-FTS recall
on a held-out train cohort before building or shipping a full index.  Use the
33,551 train records and mined hard negatives if a small fine-tune is later
justified.

### 3. Listwise reranking

[RankLLM](https://github.com/castorini/rank_llm) supports pointwise, pairwise,
and listwise rerankers, including RankGPT-style approaches.  Listwise ranking
is conceptually relevant because the competition is judged at top-k and by a
selected prefix, not independent binary decisions.

**Transferable idea:** train a lightweight list-aware or feature-fusion L2
model from frozen PaSa P2 candidates.  Candidate channel/rank/RRF/constraint
features are already auditable in this project.

**Constraint:** the open-source listwise examples center on 7B models and
vLLM.  They are not deployable on the available 4GB GPU.  A hosted LLM
listwise experiment is permissible only as a small, costed ablation; it must
not become the default based on anecdotes.

### 4. Query expansion and pseudo-documents

[HyDE](https://arxiv.org/abs/2212.10496) generates a hypothetical
relevant document and embeds it for zero-shot dense retrieval.  It is useful
evidence that query formulation can matter as much as the encoder.

**Transferable idea:** add a bounded second query representation that expresses
the topic, required method/task, and exclusion constraints, then union its
results with the raw-question channel.

**Constraint:** HyDE is designed for zero-shot dense retrieval.  Here there
is supervised train data and current query rewriting has already shown drift
risk.  Do not deploy generated pseudo-documents globally.  Evaluate raw,
constraint-only, and pseudo-document channels separately with a predeclared
candidate-recall gate.

### 5. Evaluation discipline

[BEIR](https://github.com/beir-cellar/beir) provides a common IR evaluation
framework spanning lexical, dense, sparse, and reranking systems.  The project
already exports standard IR measures via `ir_measures`/`ranx`; retain that
alongside the official PaSa `metrics.py` because PaSa also scores a selected
set rather than only a ranked list.

## Why AgenticArXiv-RL is not a drop-in solution

[AgenticArXiv-RL](https://github.com/Algorineko/AgenticArXiv-RL) is a useful
engineering reference for trajectory logging, format/tool/process/outcome
reward decomposition, reward-variance alarms, and SFT-to-DPO/GRPO/PPO
plumbing.  It is not a trained PaSa retrieval model:

- its README describes a mock arXiv environment and seven benchmark task
  seeds, rather than the AutoScholarQuery corpus and official PaSa outputs;
- its verifiable reward includes tool-sequence and parsing components that do
  not equal strict arXiv-ID R@20/R@50/R@100 plus selected-set F1;
- importing its policy would require retraining actions, observations, tools,
  and reward against PaSa; and
- its RL stack does not remove the 7B/multi-GPU memory problem.

Adopt its observability ideas, not its policy or reward as a shortcut.

## Prioritized execution plan after the current full evaluation

The current full dev/test run must finish unchanged.  Its test results are a
final frozen measurement, not material for later tuning.

### Priority 1: train-only fusion before another model swap

1. Generate 1,024 `policy_train` and 256 disjoint `policy_validation` compact
P2 rollouts after the GPU is free.  Use question-only retrieval and do not
read dev/test labels.
2. Train an L2 feature-fusion ranker on strict train IDs using candidate
channel membership/ranks, FTS scores, MiniLM score/rank, RRF, constraint,
graph/citation and query-type features.  The target is candidate relevance,
not a hard-coded `n_hat=5`.
3. Promote only if the independent train validation improves R@20 by at least
0.01, does not lower R@100 by more than 0.002, and does not lower F1 by more
than 0.002.  Otherwise retain lexical P2.
4. Fit a probability-calibrated prefix selector on the promoted ranking.  It
should optimize expected F1 over rank prefixes, not only predict answer-set
cardinality.  The existing 32-query cardinality artifact remains an audit
control, not the final selector.

Why this is first: the measured P3 result proves that increasing capacity
without a learned ordering signal is not enough, while the candidate audit
shows a large recoverable pool already exists.

### Priority 2: improve first-stage recall without 7B RL

1. Add a train-gated sparse-expansion channel (SPLADE or a smaller sparse
query expander) and union it with FTS + raw MiniLM.  Track channel-unique gold
IDs and candidate recall before reranking.
2. Add two bounded query views: raw question and constraint-normalized topic
form.  Keep each view's candidates/channels auditable.  This is a controlled
approximation of Crawler query diversity, not a claim of agentic RL.
3. Retain section citation expansion because it added 0.125 candidate recall
in the pilot, but choose seeds by train-validated relevance/coverage rather
than a global citation gate.

### Priority 3: only then test late interaction or hosted listwise rankers

1. Run a 32-query frozen candidate-only ColBERT experiment.  It must use the
same candidate IDs and pass ranking gates before building a corpus index.
2. If a hosted listwise reranker is tested, bound it to top 50 or 100
candidates, record exact calls/cost/latency, and compare it against the
feature-fusion arm with a paired test.
3. Do not retry online BGE-M3 as the default: the direct real-API ablation is
already negative.

## Non-negotiable evaluation rules

- Train is the only source for fitting, thresholds, channel weights, or action
  policies.
- Dev rankings must be frozen before labels are read.  Use paired 20,000-draw
  bootstrap/sign-flip for a candidate-versus-baseline decision.
- The already-started test evaluation uses a frozen configuration.  Do not
  select a new model based on its result or run repeated test ablations.
- Every final export must satisfy official PaSa format: local title/ID source,
  at most top-100 ranked papers, strictly decreasing scores, and a selected
  rank prefix represented by `select_score > 0.5`.

## Source notes

All external claims above were read from public project documentation or paper
pages on 2026-08-28.  URLs are included inline.  Browser navigation was
unavailable in this desktop session, so public GitHub raw documentation and
read-only public paper metadata were used instead.  No external account,
credential, upload, or model execution was used for this review.
