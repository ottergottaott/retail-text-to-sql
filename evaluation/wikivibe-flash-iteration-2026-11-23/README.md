# WikiVibe Flash paired pilot — 23 November 2026

Eight English development cases from four whole task families were selected
before calls. Both variants used `gemini-3.8-flash` through
`https://api.wikivibe.dev/v1`. Generation and judging used the same model;
judge scores are advisory and may have correlated bias.

| Check | Baseline | Candidate |
| --- | --- | --- |
| Standard Ragas faithfulness | 0.7552 | 0.7219 |
| Custom SQL-aware faithfulness | 0.9504 | 1.0000 |
| Scored cases | 8/8 | 8/8 |
| Deterministic table/structure/save checks | 8/8 | 8/8 |
| Generation attempts | 8 | 8 |
| Judge HTTP calls | 32 | 32 |

The candidate adds six lines requesting compact, directly supported factual
sentences and query-grounded limitations. It lost 0.0333 on standard Ragas.
The paired family-bootstrap interval was [-0.0696, 0.0003]; only four families
were tested. The comparison gate did not pass. No promotion is justified.
SQL-aware faithfulness is a separate contract, not a replacement for standard
Ragas or an accuracy percentage.

The unchanged standard judge frequently scored proposed future checks as
unsupported statements. It also rejected some query-boundary descriptions.
Per-statement reasons remain in the judge batch files. Useful next checks and
requested tables were retained; the judge contract and SQL evidence were not
changed to raise scores.

## Evidence and reproduction

- [Protocol, implementation hashes and limits](protocol.json)
- [Baseline results](baseline-development/results.json)
- [Candidate results](candidate-development/results.json)
- [Paired comparison](comparison-development.json)
- [261 passing regression tests](regression.xml)
- [40/40 development SQL oracle rechecks](sql-oracle-recheck.json)

From the repository root, with gateway credentials in the ignored local
`.env.providers` file:

```sh
OPENAI_COMPATIBLE_MODEL=gemini-3.8-flash RAGAS_JUDGE_TIMEOUT=60 \
.venv/bin/python scripts/run_faithfulness_experiment.py --live \
  --env-file .env.providers \
  --cases evaluation/faithfulness-v2/development.json \
  --prompt evaluation/wikivibe-flash-iteration-2026-11-23/candidate.txt \
  --limit 8 --batch-size 4 --max-calls-per-batch 16 --max-seconds 1000 \
  --output-dir evaluation/wikivibe-flash-reproduction
```

Use `baseline.txt` and a separate output directory for the baseline. Calls are
billable; each variant permits eight generation requests and up to 32 judge
requests per invocation. The runner permits one disclosed retry on a later
resume. Exact outputs and scores can vary.

These are frozen synthetic SQL results at the review stage. There were no live
BigQuery queries, planner or retrieval tests in this experiment. The 40-query
oracle recheck executed the development reference SQL on the deterministic
DuckDB fixture. It does not verify generated SQL against BigQuery.

The older `prompt-iteration-4-kie-2026-11-23` run used fixture placeholder
answers because application fixture routing bypassed the configured gateway.
It is marked invalid for prompt comparison. Live evaluators now bypass that
routing; a controlled HTTP regression test verifies the actual custom endpoint
and provider-reported token usage. The isolated earlier 0.75 Flash smoke is one
synthetic case and is not the paired pilot result.

Broader validation, repeated-judge sensitivity checks and human review remain
pending. The historical 0.534 live score uses different data and a different
judge/model setup, so no improvement from 0.534 to these pilot values is claimed.

## Candidate v2: development result

The frozen [v2 prompt](candidate-v2.txt) clarifies order/item grain, current-price
reference gaps and query boundaries, and asks for useful next analytical questions.
On the same eight exposed development cases, standard Ragas scored **0.7868**
versus baseline **0.7552**; custom SQL-aware scored **0.9861** versus **0.9504**.
All eight deterministic checks passed. Six standard scores improved and two fell.
The family-bootstrap interval for the standard difference is [-0.0159, 0.0662].
Four task families are insufficient for the five-family comparison gate, and the
interval includes zero. This is a promising development result, not a promotion.

One initial standard-judge response failed schema validation. The bounded resume
re-evaluated that case, retaining the first batch in `judge-00.attempt-1.json`.
The final run scored 8/8 using 36 judge requests across both attempts. Rechecks
are not first-attempt successes.

- [Development protocol](protocol-v2.json)
- [Complete v2 results](candidate-v2-development/results.json)
- [Paired development comparison](comparison-development-v2.json)
- [DeepSeek design critique through OpenCode / Alibaba China](deepseek-v2-design-review.json)
- [262 passing final regression tests](regression-final.xml)
- [20/20 validation SQL oracle rechecks](validation-sql-oracle-recheck.json)

Broader validation is running under a [frozen protocol](protocol-validation-v2.json):
20 synthetic cases / 10 families per variant, with the baseline and v2 prompts
unchanged. Results are pending. No validation or sealed-test improvement is claimed.

The independent [DeepSeek answer review](deepseek-v2-answer-review.json), run via
OpenCode / Alibaba China, found no blocking development sample errors. Its
[evidence-limited schema notes and recheck concerns were checked locally](deepseek-v2-review-adjudication.json).
This is AI critique, not human acceptance or independent SQL verification.
The application [source prompt remains the baseline](source-prompt-decision.json);
the first candidate's unpromoted six-line edit and its exact-text assertion test
were removed. The resulting [regression recheck passed 261 tests](regression-serving-baseline.xml).
The earlier 262-test record includes that now-removed experimental text assertion.

The latest [262-test regression](regression-empty-wording.xml) includes a new
meaningful empty-result oracle test instead. The checker now recognizes
“No records returned” for an empty reference while still rejecting that answer
for a nonempty reference. This fixes two baseline false negatives; it changes
neither generated answers nor the Ragas contract. Both validation variants use
the corrected checker on resume. The [resume protocol](validation-resume-protocol.json)
records a 120-second metric timeout and preserves the original incomplete batches.

## Evaluation paused by the user

Further evaluation and test runs were stopped on 23 November. The original
candidate validation remains incomplete: 19/20 cases, with one generation failing
both permitted 30-second attempts. A separately documented supplemental attempt
used a 60-second generation limit; inspect its artifacts separately and do not
count it as an original-run success. Baseline resume and repeated-judge processes
were interrupted. Partial judge files and failed attempts are retained; no
complete validation comparison, repeatability acceptance or promotion is claimed.
The application prompt remains baseline. The latest completed regression is
262 passing tests, predating subsequent preference-application edits.
