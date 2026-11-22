# Retrieval verification

Updated 2026-11-21. [Measured results and limitations](../evaluation/retrieval-results-2026-11-21.md)

Latest runtime change: [English relevance gate comparison](retrieval-relevance-results.md).
With healthy indexed embeddings, lexical additions require semantic support;
provider failure still produces explicitly ungated lexical fallback.
are the current evidence; earlier lexical-only results are historical baselines.

## Reproduce locally

The default CLI creates a temporary SQLite store, loads no provider settings
and makes no provider calls. It evaluates lexical and actual BM25; vector and
hybrid have null metrics and empty case lists marked untested.

```sh
.venv/bin/python scripts/evaluate_retrieval.py \
  --cases evaluation/expanded-retrieval-cases.json \
  --corpus retail/data/golden-trios.json --k 1 2 5 \
  --output /tmp/retrieval-offline.json
```

Live Qwen comparison (billed provider calls; credential in protected environment):

```sh
EMBEDDING_PROVIDER=deepinfra .venv/bin/python scripts/evaluate_retrieval.py \
  --live --cases evaluation/expanded-retrieval-cases.json \
  --corpus retail/data/golden-trios.json --output /tmp/retrieval-live.json
```

Replace the cases path with `evaluation/retail-challenge-cases.json` for graded
close-method distractors. The expanded set has80 positives and18 negatives;
the challenge set has12 positives and4 negatives. Both are synthetic, unreviewed.
Evaluation stores are disposable and do not index the running application's DB.

Pinned external English/SQL diagnostic, separate from retail acceptance:

```sh
EMBEDDING_PROVIDER=deepinfra .venv/bin/python scripts/evaluate_wikisql.py \
  --data-dir /tmp/retail-wikisql --download --live --limit 100 \
  --output /tmp/wikisql-live.json
```

Without --live this uses BM25 only. Download is separately explicit. The pinned
revision and all file checksums are in the report. Full corpus2048, sampled100
queries; upstream question+table context preserved. External SQL is not executed.
--limit does not reduce the full corpus indexing cost. Vector and BM25+vector RRF
reuse query embeddings; indexing time is reported separately.

Real-model/synthetic-database ablation (not BigQuery evidence):

```sh
LLM_PROVIDER=deepinfra EMBEDDING_PROVIDER=deepinfra \
  .venv/bin/python scripts/evaluate_agent_retrieval.py --live \
  --output /tmp/agent-ablation.json
```

## Metric and evidence contracts

- Exact trio ID **and version** define relevance. Duplicate labels are refused;
  unknown or unpublished references produce label warnings and score misses.
- Retail k=1,2,5; legacy @2 fields retained. Precision uses fixed denominator k.
  Recall and RR/MRR use positive relevance; nDCG gain is2^grade-1 with logarithmic
  discount. Missing positives score zero; queries with no positives have null
  ranking metrics and are summarized separately by false-match/no-result rate.
- Negative false-match and irrelevant-example rates cover the full retrieved
  depth (default5), not just @2. Language slices are separate.
- Latency records mean/p50/p95, including live query embedding when applicable.
  These small sequential runs are not a concurrency/load benchmark.
- Corpus/model/index versions, labels, ranked references and measured mode are
  saved. No credentials or raw vectors are exported. Provider cost remains null;
  no price estimate is represented as measured spend.
- Hybrid counts only when retrieval telemetry confirms hybrid. Semantic failure
  cannot score lexical fallback as hybrid; incomplete modes remain untested.
- Controlled-vector tests prove mechanics, never semantic quality. Live Qwen
  relevance was measured on the saved sets, not certified as release quality.

Production threshold0.65 is unchanged. Hybrid improves positive recall on our
retail sets while inheriting lexical false positives; pure vector wins this
WikiSQL sample. Do not tune on these held-out results or assume hybrid always
wins. Freeze a separate development set before threshold/fusion changes.

Still required: human relevance/report review, broader agent intent/follow-up
evaluation and real BigQuery execution. A ranking score proves none of these.
