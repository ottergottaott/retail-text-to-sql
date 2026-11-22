# Retrieval benchmark strategy

Updated 2026-11-21. Retail evaluation and a pinned external WikiSQL diagnostic
are implemented and executed with real Qwen embeddings via DeepInfra. See
[measured results](../evaluation/retrieval-results-2026-11-21.md).

## Separate the tasks

1. **Example retrieval:** find useful Golden methodology trios for a new user
   question. Our current embedded document is question + tags + analyst report;
   SQL is delivered to the agent after retrieval but is not embedded.
2. **Text-to-SQL generation:** produce an executable, correct query against the
   authorized schema. Retrieval ranking alone does not prove query correctness.
3. **Product behavior:** authorization, privacy, clarification, report evidence,
   confirmed deletion and error handling require our application-specific checks.

## External choices

- **MTEB WikiSQLRetrieval:** direct natural-language-question to SQL retrieval.
  This is the closest ready-made external SQL retrieval task found. Its corpus,
  queries and relevance judgments are separate. It tests English/SQL, not our
  complete retail trios or Russian queries. Use a separate evaluation harness;
  do not import its SQL into trusted application knowledge or execute it through
  the production SQL path. Compare at the documented nDCG@10 and additionally
  our working cutoff. A sample run must be labeled a subset, not a full score.
- **MTEB/MMTEB retrieval tasks:** useful for encoder selection and multilingual
  diagnostics. Full aggregate MTEB mixes other tasks; it is not our acceptance
  criterion. Running all tasks is unnecessary for this assessment.
- **BIRD Mini-Dev:** 500 text-to-SQL pairs across 11 databases, with questions,
  reference SQL and external knowledge. Useful for a separate generation harness
  and execution accuracy, not ready-made relevance labels for selecting helpful
  prior trios. Its schemas/dialects do not match our four-table BigQuery contract.
- **Spider 2.0:** enterprise SQL workflows, including BigQuery. Useful as a later
  extension; adapting the full suite would expand this assessment substantially.

## Recommended MVP order

Keep the local retail set as the primary product evaluation. Review synthetic
labels, add independent queries, and add close negatives differing in status,
grain, denominator, time window and metric definition. Keep tuning queries
separate from final evaluation queries. Human review is still pending.

Compare the same corpus and queries using current lexical, vector and hybrid
retrieval. Record Recall@2, MRR, no-match false positives, per-language quality,
latency and provider/model/index identity. The evaluation includes actual Okapi BM25 (Unicode tokenization, k1=1.2, b=0.75).
Production lexical retrieval remains its existing weighted token-overlap method;
BM25 is an evaluation baseline, not an implicit runtime replacement. Evaluate
a reranker only after establishing a measured baseline.

Use WikiSQLRetrieval as an additional external diagnostic. Because it retrieves
SQL text while our product retrieves methodology text, report the representation
and task difference explicitly. Optionally test question/tags/report versus
question/tags/report/SQL on our retail set before changing the product index.

Finally measure whether retrieved examples improve SQL execution correctness
and report faithfulness: no retrieval versus lexical versus hybrid under the
same model, prompts, budgets and scoped data. A high retrieval score alone does
not establish that the agent benefits from examples.

## Metric contract

Implemented metrics share independently checked functions in
`retail/retrieval_metrics.py`. Retail uses k=1,2,5; external WikiSQL also uses10.
Per-case RR and aggregate MRR are explicitly cutoff-bound. Reported metrics:

- Evaluate k = 1, 2 and 5; k = 2 is the current agent context cutoff.
- **Recall@k:** relevant retrieved documents / all labeled relevant documents.
  Macro-average over positive queries. With one relevant document this is a hit
  rate, so labels must include all acceptable methodology matches where possible.
- **Precision@k:** relevant retrieved documents / k. Missing result slots count
  as misses. Macro-average over positive queries; do not silently change the
  denominator to the number returned.
- **RR@k / MRR@k:** per-query reciprocal rank of the first relevant document,
  zero if none occurs within k; MRR averages those values over positive queries.
  These are case-level and aggregate forms of the same measure.
- **nDCG@k:** graded ranking quality, using gain 2^relevance - 1 and log2(rank+1)
  discount, normalized by the ideal ranking. The expanded set has binary labels. The separate challenge set has synthetic
  graded labels: 0 irrelevant, 1 useful adjacent method, 2 directly applicable.
  Neither label set has been reviewed by a human analyst.
- **Negative false-match rate:** fraction of no-match queries returning any
  example. Keep separate from positive-only ranking averages: nDCG's ideal
  denominator is zero when no relevant document exists. Include no-result rate
  to explain abstention. A system returning nothing has perfect negative
  abstention but zero positive recall; interpret jointly.
- **Latency:** end-to-end retrieval p50/p95, including remote query embedding
  and optional reranking. Indexing time and estimated/measured cost are separate.
- **Authorization leakage:** unauthorized examples returned / opportunities,
  with zero violations as a required security invariant, not an averaged quality
  trade-off. Evaluate against separate scoped principals.

Report English and Russian slices separately. Freeze a dev/test query split
before tuning thresholds or fusion weights. Incomplete relevance judgments can
understate precision and nDCG; human label review remains necessary. External
benchmarks retain their official metrics, corpus and cutoff; custom k=2/subset
measurements are additional diagnostics and must be labeled accordingly.

## Primary sources

- MTEB task definition: https://docs.mteb.org/overview/available_tasks/retrieval/#wikisqlretrieval
- WikiSQL retrieval data: https://huggingface.co/datasets/mteb/WikiSQLRetrieval
- MTEB benchmarks: https://docs.mteb.org/overview/available_benchmarks/
- BIRD Mini-Dev: https://github.com/bird-bench/mini_dev
- Spider 2.0: https://spider2-sql.github.io/

## Executed external diagnostic

`scripts/evaluate_wikisql.py` verifies pinned parquet SHA-256 checksums and uses
the full 2,048-document SQL corpus. The measured run sampled 100 judged queries
with seed42; it is not an official full MTEB score. Upstream queries contain
question **and table context**; we preserve them without stripping that context.
SQL remains opaque retrieval text and is never executed or imported into the app.

External vector ranking has no cosine threshold. Its hybrid fuses BM25 top10
and vector top10 with RRF constant60, unlike production lexical+vector fusion.
Compare modes within each report; do not merge their task scores. The measured
run attempted164 embedding calls:64 document batches plus100 query calls. The
CLI now prints that estimate before calls; --limit caps queries, not indexing.

## Agent benefit check

`scripts/evaluate_agent_retrieval.py --live` runs no-retrieval, lexical and hybrid
with the same real model against explicitly injected DuckDB fixture analytics.
It creates isolated stores and never constructs a BigQuery client. Three small
hand-derived query-result oracles check monthly revenue, finalized return share
and product-cost proxy margin. It does not grade report truthfulness or action
quality; those await human review. One repetition cannot establish a causal
retrieval benefit. See the results document for failures and rerun provenance.
