# PaSa Implementation Fixes (2026-08-29)

## Scope

This note records implementation fixes made while the frozen P2 development
evaluation was already running. The running process loaded the previous code
before these edits and is not affected. The fixes therefore require a new
train-only smoke run before they can be treated as a measured improvement.

## Findings

1. The local MiniLM and API dense sources computed exact cosine scores but
   returned only hydrated `Paper` objects. `Candidate.s_dense` consequently
   stayed at zero. Dense retrieval still contributed through channel membership
   and RRF rank, but the L2 fusion feature named `dense` was dead.
2. The pipeline constructed a new source registry for every query. The full
   local dense index reads metadata for roughly 568k papers. On a 4GB GPU this
   also increased model and memory churn and was consistent with intermittent
   `pasa_local_dense` registration failures in the long run.
3. Optional source construction errors were swallowed. A later required-source
   check could report only `not registered`, without the constructor exception.
4. The lexical P2 reranker does not need the dense GPU allocation. Releasing
   MiniLM before every lexical L2 pass forced the next query to reload the
   encoder and dense matrix.

## Changes

- `Paper.retrieval_score` is an optional, backwards-compatible field.
- Both PaSa dense sources preserve `(position, cosine)` through hydration and
  cache serialization.
- Dense search cache keys use a new `native_score_v2` namespace, so an old
  score-less cache entry cannot silently defeat the fix.
- `MultiProbe` copies native dense scores into `Candidate.s_dense`, falls back
  to a deterministic rank signal for synthetic/legacy sources, preserves
  citation rank evidence in `s_reference`, and carries these features through
  `ProbeResult.merge()`.
- `ScholarNexus` reuses one registry per engine, rebinds each source to the
  current query ledger, closes owned sources at engine shutdown, and includes
  recorded initialization exceptions in required-source errors.
- Dense accelerators are released before L2 only when a dense admission model
  or GPU L2 reranker actually needs that memory.
- `l1_dense_weight` is an explicit, default-zero ablation knob so native dense
  cosine can be tested in L1 admission without changing the frozen baseline.
- The full-evaluation PowerShell wrapper now rejects dev error rows before
  strict-ID scoring, matching its existing test-stage guard.

## Verification

- Python compile check: passed.
- Regression suite: `97/97` passed.
- New unit coverage verifies that a local dense search preserves native cosine
  order and that the value reaches `Candidate.s_dense`.

## Evaluation boundary

The active artifact remains the old-code, label-blind P2 dev checkpoint:

- checkpoint: `F:/pasa_compare_20260828/pasa_p2_dev_full_20260829_label_blind.checkpoint.jsonl`
- data: `dev.jsonl`, first 1,000 rows
- latest observed progress at note creation: approximately `520/1000`
- observed errors: `AutoScholarQuery_dev_220` and `AutoScholarQuery_dev_221`
- test split: not started

No strict-ID or official score should be reported until this frozen ranking is
complete and its error rows are explicitly counted. Afterward, the repaired
code must be evaluated on disjoint train queries with strict arXiv-ID metrics;
only a validated gain can promote the dense score and registry changes.

## CPU candidate diagnostic

Two label-joined, train-only diagnostics were completed without changing the
running evaluation. On 100 train queries with FTS channel top-500, the RRF
candidate-pool recall was `0.4489`. On a separate 32-query slice with channel
top-2000, it rose to `0.5813` as a pool oracle. This supports testing a wider
FTS window only after the repaired dense path is measured; it is not itself a
final ranking or F1 result.
