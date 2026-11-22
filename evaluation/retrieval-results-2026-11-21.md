# Measured retrieval results — 2026-11-21

Generated from saved JSON reports; aggregates are preserved in [machine-readable results](retrieval-results-2026-11-21.json). No release-quality verdict is assigned.

## Retail expanded set

23 synthetic trios,80 positive paraphrases (40EN/40RU),18 negatives. Exact-version binary labels. Lexical and BM25 are local; vector and hybrid use actual Qwen3-Embedding-8B through DeepInfra (1024 dimensions). Runtime threshold0.65 is unchanged. BM25 comes from a separate offline run: corpus digest and exact ordered questions/labels were matched before combining; it did not reuse live vector calls.

| Method | Recall@2 | Precision@2 | MRR@2 | nDCG@2 | Negative false-match rate | p95 ms |
|---|---:|---:|---:|---:|---:|---:|
| lexical | 0.5000 | 0.2500 | 0.4500 | 0.4631 | 0.4444 | 2.7948 |
| vector | 0.7750 | 0.3875 | 0.7625 | 0.7658 | 0.0000 | 2430.4241 |
| hybrid | 0.8375 | 0.4188 | 0.8000 | 0.8098 | 0.4444 | 2482.8650 |
| bm25 | 0.5125 | 0.2562 | 0.4813 | 0.4894 | 0.5556 | 0.1536 |

Negative false-match and irrelevant-example rates use the full retrieved depth5. They must not be read as Precision@2. Language slices and metrics at1/2/5 are in JSON. Hybrid improves positive recall but inherits lexical negative matches; vector abstains on all18 negatives. These are small synthetic samples, not a population guarantee.

## Close retail challenge set

12 positive questions,4 negatives; EN/RU; grades2 directly applicable and1 useful adjacent methodology. All methods use the same corpus. Labels are synthetic and unreviewed.

| Method | Recall@2 | Precision@2 | MRR@2 | nDCG@2 | Negative false-match rate |
|---|---:|---:|---:|---:|---:|
| lexical | 0.2917 | 0.2917 | 0.4167 | 0.3598 | 0.5000 |
| bm25 | 0.3750 | 0.3750 | 0.4583 | 0.4142 | 0.5000 |
| vector | 0.5000 | 0.5000 | 0.7917 | 0.6921 | 0.0000 |
| hybrid | 0.5833 | 0.5833 | 0.8750 | 0.7585 | 0.5000 |

## External WikiSQL diagnostic

Pinned mteb/WikiSQLRetrieval revision `add6c3faf0d972ebb139b30fa6c4f955d99635c5`. Full2048 SQL documents;100 sampled judged queries, seed42. **Subset diagnostic, not an official full benchmark score.** Queries preserve upstream question+table context. SQL is opaque text; no SQL executed and no application state used.

| Method | Recall@10 | Precision@10 | MRR@10 | nDCG@10 | p95 ms |
|---|---:|---:|---:|---:|---:|
| bm25 | 0.8900 | 0.0890 | 0.3958 | 0.5154 | 3.6238 |
| vector | 0.9600 | 0.0960 | 0.7667 | 0.8136 | 2333.3089 |
| bm25_vector_rrf | 0.9500 | 0.0950 | 0.6161 | 0.6987 | 2334.1524 |

Vector wins this sample; adding BM25 via RRF reduced ranking quality. External vector has no threshold; RRF fuses top10 with constant60. This differs from runtime lexical+vector fusion. Do not compare absolute scores across the retail and WikiSQL tasks.

Measured164 embedding attempts:64 full-corpus document batches and100 query embeddings. Indexing took 122.96 seconds; retrieval latency includes query embedding but excludes indexing. Provider cost is unavailable (`null`), not zero. Timing is sequential and sensitive to network/provider load.

## Boundaries and next evaluation

The held-out sets were used for measurement without changing threshold or fusion parameters. Freeze a separate development split before tuning, review labels with an analyst and add independent questions. Controlled tests are separate from these live-embedding reports. Ranking does not establish SQL correctness, useful report actions, safety or production readiness. BigQuery and Langfuse remain unverified. BIRD/Spider are future generation diagnostics, not silently substituted acceptance tests.

## Evidence sources

- expanded_live: `/Users/user/.bb/thread-storage/thr_jx74y5r9jy/retrieval-expanded-live-v2.json`; SHA256 `867694aca5dc073516adaa575690242990b518a8c6f79d216c67ea1a9f3dff28`.
- expanded_offline: `/Users/user/.bb/thread-storage/thr_jx74y5r9jy/retrieval-expanded-offline-v2.json`; SHA256 `0a6704373a36c7fbf1b55408985d407b6d903f969b974d13a38e501e75fbc148`.
- challenge: `/Users/user/.bb/thread-storage/thr_jx74y5r9jy/retrieval-challenge-live.json`; SHA256 `87bdcf30f4503469753fdefbd499573c08efdcb769f1529216e8f05111f44dc0`.
- wikisql: `/Users/user/.bb/thread-storage/thr_jx74y5r9jy/wikisql-live-sample.json`; SHA256 `b930f42cc35f9caa57591b7268e2794b0609b3cf3ee224a5742595c02117dcd8`.

## Agent SQL ablation

Real `google/gemini-3.5-flash` via DeepInfra; DuckDB fixture data, never live
BigQuery. The no-retrieval, lexical and hybrid modes each matched all3 result
oracles (monthly revenue, finalized-item return share, cost-proxy margin) and
finished successfully. Hybrid telemetry confirmed actual hybrid retrieval.
Fresh conversations, equal budgets, same model; one repetition only. These
three cases show basic compatibility, not a measured accuracy benefit from RAG.
Report faithfulness/action quality and broader follow-ups await human review.

The initial run is preserved at `/Users/user/.bb/thread-storage/thr_jx74y5r9jy/agent-retrieval-live-fixture.json`.
It exposed unsupported SQL functions and a validator bug treating SQLGlot's
boolean AND as a forbidden function. Regression tests reproduced the failures
before fixes: AND/OR/NOT are now validated predicate structure, and the model
receives the approved function capabilities. Unknown functions stay forbidden.
The rerun also requests a start-of-month date instead of SQL-formatted YYYY-MM;
month values follow existing fixture serialization. Monthly query wording
therefore differs between initial and rerun; these runs are not a controlled
before/after prompt comparison. The monthly revenue values remain100 and110.

Final raw report: `/Users/user/.bb/thread-storage/thr_jx74y5r9jy/agent-retrieval-live-fixture-v2.json`.
Measured tokens are retained; provider spend is unavailable, not estimated.
All query results are synthetic fixture evidence even though the model is real.
