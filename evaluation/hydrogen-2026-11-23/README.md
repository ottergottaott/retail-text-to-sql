# Hydrogen checks — 23 November 2026

Provider: WikiVibe (`https://api.wikivibe.dev/v1`). Model and judge:
`gemini-4-hydrogen`. Prompt: `retail-v10-auto-improvement`.

## Faithfulness: incomplete

| Measurement | Result | Coverage |
| --- | ---: | --- |
| Standard Ragas faithfulness | 0.5882 | 4/20 cases |
| Custom SQL-aware faithfulness | 0.9555 | 4/20 cases |
| Both metrics measured | 3/20 | Different missing cases for each metric |
| Deterministic answer checks | 12/12 generated | 8 cases not generated before deadline |

The planned 20-case validation did not complete. Metric calls had a 60-second
budget; the invocation stopped at its 1,000-second deadline. Judge timeouts are
retained, not assigned zero or excluded without disclosure. Means describe only
the measured cases and must not be presented as a complete validation score.
No retries were run for this validation invocation. No quality gain is claimed.

[Raw results](validation/results.json), [identity and hashes](validation/identity.json),
[generated samples](validation/samples.json) and per-batch judge diagnostics are retained.
At least 32 judge HTTP attempts were recorded; the final batch was interrupted,
so the total call count is incomplete. Recorded judge tokens: 117,444;
these likewise exclude any unrecorded interrupted batch usage. Generation attempts: 12.
Monetary cost was not measured for the whole run.

This is live model inference over frozen synthetic SQL evidence at the report-review
stage. It does not execute BigQuery, test tool routing or measure overall accuracy.
Generation and judging use the same model, so correlated bias is possible. Standard
Ragas and the custom SQL-aware contract are separate metrics. Historical Flash and
live BigQuery runs use different prompts/models/evidence; no paired improvement or
regression follows from comparing their means. Human review remains pending.

Diagnostics include rejections of proposed next checks and small-count/causal
limitations as unsupported by SQL evidence. These are specific judge findings,
not proof that every low-scored statement is harmless.

## Reproduce or resume explicitly

Requires the development environment and your own ignored `.env.providers` file
configured for WikiVibe. This command makes paid calls. A fresh invocation may
retry incomplete cases; original attempts are retained by the runner. To reproduce
from scratch, choose a new output directory.

```sh
OPENAI_COMPATIBLE_MODEL=gemini-4-hydrogen RAGAS_JUDGE_TIMEOUT=60 \
.venv/bin/python scripts/run_faithfulness_experiment.py --live \
  --env-file .env.providers --cases evaluation/faithfulness-v2/validation.json \
  --prompt docs/prompts/system.txt --limit 20 --batch-size 4 \
  --max-calls-per-batch 16 --max-seconds 1000 \
  --output-dir evaluation/hydrogen-2026-11-23/validation
```

## Automation smoke: two configurations

- [Initial session](automation-smoke.json): CEO tone activated through four live
  render/judge calls; policy-changing tone was rejected and the active version
  retained. Helpful feedback was rejected because the fixture brand-scoped query
  returned no rows. This session did not pass all three checks.
- [Fixture setup recheck](automation-smoke-recheck.json): product-scoped Helpful
  feedback passed one live grounding judge call and was published. CEO was not
  configured in this recheck, so its tone checks do not establish CEO behavior.

These are separate bounded observations, not a single 3/3 passing session.
SQL was deterministic fixture execution in isolated temporary databases; no live
BigQuery was used. The complete local regression suite passed 303 tests; five
[fixture-browser checks](../automatic-learning-browser-2026-11-23.json) covered
feedback application, tone activation/rejection and rollback.

## Connection and review attempts

The first 30-second structured probe failed; the 60-second structured probe returned
a valid answer. Plain HTTP 200 returned empty content and is not an answer-quality
pass. Probe artifacts preserve these outcomes.

OpenCode `alibaba-cn/deepseek-v4.1-flash` failed to connect before returning a code
review. No DeepSeek review acceptance is claimed; DeepInfra was not used.
