# English retrieval relevance gate — 21 November 2026

## Change

Hybrid RRF previously accepted every positive word-overlap result, even when
the embedding model considered it unrelated. With a compatible index and a
successful query embedding, lexical candidates now need cosine similarity
at least `RETRIEVAL_LEXICAL_MIN_SIMILARITY=0.60` (capped at the semantic
threshold). Strong semantic-only matches still use `RETRIEVAL_MIN_SIMILARITY=0.65`.
There are no extra inference calls. The existing `instruct-v1` query instruction
is unchanged in this experiment. No intent blacklist or case IDs enter runtime.

Missing-current-version vectors cannot enter gated lexical results. Telemetry
records `retrieval_policy`, `relevance_gate`, `lexical_rejected`,
`index_complete` and both thresholds. Unavailable embeddings preserve lexical
fallback, explicitly marked ungated; the improvement below does not apply to it.

## Method

- English product scope: 40 positive paraphrases plus 10 negatives from the
  expanded synthetic corpus evaluation; Russian cases are excluded here.
- Development split: first English paraphrase for each of 20 intents plus
  alternating sorted negative IDs (5). Remaining 25 cases are validation.
- Development grid: floors 0.50, 0.55, 0.60, 0.625, 0.65. Select the conservative
  round floor 0.60 among full-recall, zero-false-match development settings.
  The full expanded dataset had already appeared in previous experiments;
  its validation portion is not a pristine independent test set.
- A new English challenge (12 positives, 8 negatives) was authored before
  selecting the threshold and evaluated after selection, with no retuning.
- Qwen/Qwen3-Embedding-8B via live DeepInfra, 1024 dimensions; the same document
  and query vectors are replayed for legacy and candidate retrieval. Six
  initial embedding requests and two additional challenge requests, no BigQuery.
- 23 Golden Trios, identical access/schema filters and RRF in both variants.
- Cached vectors contain only synthetic corpus/question text. The replay
  command makes no external calls; cache/corpus/case digests identify inputs.

## Results

| Dataset | Metric | Legacy | Gated |
| --- | --- | --- | --- |
| English expanded, 40 positive / 10 negative | Recall@2 | 1.000 | 1.000 |
| English expanded | MRR@2 | 0.950 | 0.950 |
| English expanded | nDCG@2 | 0.9631 | 0.9631 |
| English expanded | Negative false matches | 8/10 | 0/10 |
| Validation portion, 20 positive / 5 negative | Recall@2 | 1.000 | 1.000 |
| Validation portion | Negative false matches | 4/5 | 0/5 |
| New challenge, 12 positive / 8 negative | Recall@2 | 1.000 | 1.000 |
| New challenge | MRR@2 | 0.9583 | 0.9583 |
| New challenge | nDCG@2 | 0.9692 | 0.9692 |
| New challenge | Negative false matches | 8/8 | 0/8 |

False-match rate means any example returned through rank 5, not a security
violation or an incorrect final answer. Ranking metrics average positive cases;
negative cases are reported separately. Precision@2 stays 0.5 because each
positive case labels one relevant trio; fixed-k precision uses denominator 2.

## Reproduction

```sh
.venv/bin/python scripts/evaluate_relevance_gate.py \
  --vectors evaluation/retrieval-gate-2026-11-21/vectors.json \
  --cases evaluation/expanded-retrieval-cases.json \
  --output /tmp/english-gate-results.json

.venv/bin/python scripts/evaluate_relevance_gate.py \
  --vectors evaluation/retrieval-gate-2026-11-21/vectors.json \
  --cases evaluation/english-retrieval-challenge.json \
  --output /tmp/challenge-gate-results.json
```

Full cases, metrics, calibration split and vectors are in
`evaluation/retrieval-gate-2026-11-21/`. Regression tests cover rejection,
moderate-similarity lexical rescue, semantic-only matching, stale/partial
indexes, provider fallback and existing scope isolation.

## Limits

These are small, synthetic, unreviewed relevance judgments. They do not prove
production no-match accuracy, SQL correctness, report faithfulness or user
acceptance. Cached replay timing is not provider or user-perceived latency.
Thresholds need recalibration when model/corpus distributions change. Retrieval
abstention does not prevent the agent from answering schema-supported questions.
