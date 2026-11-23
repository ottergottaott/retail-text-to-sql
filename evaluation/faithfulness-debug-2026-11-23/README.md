# Controlled report-grounding evaluation

This experiment compares the serving prompt with a frozen candidate on identical
synthetic SQL evidence. It tests the report-review stage, not SQL generation,
BigQuery execution, access enforcement or overall answer accuracy.

## What changed

- Report statements use queried counts and preserve the requested tables.
- Limitations describe the query, without inferring what the dataset lacks.
- Proposed next checks remain in the report and are phrased without assumed facts.
- Automation, access, privacy, business, tool and save rules are preserved.

The candidate was written through OpenCode `alibaba-cn/deepseek-v4.1-flash`.
[Coding provenance](coding-provenance.json) and [prompt diff checks](prompt-scope-review.json).
The evaluator fixes passed the full local regression suite: **308 tests**.
[JUnit evidence](regression.xml).

## Measurement contract

Both variants use WikiVibe's `gemini-3.8-flash` gateway ID for generation and judging.
These are the endpoint's model aliases. Standard Ragas 0.4.4 Faithfulness is
unchanged; the separately reported SQL-aware metric uses a different contract.
Using the same model for generation and judging can introduce bias.

The `schema-v1` judge evidence contains the original SQL/result/scope plus the
logical schema supplied to generation. It excludes the draft, history, examples
and grading instructions. Both variants are scored with this same evidence;
historical SQL-only/Hydrogen means are not a paired control.

The 10-case development pilot uses five complete families. The full validation
set contains 20 cases and was previously exposed, so it is not a new held-out
test. Each run has one repetition; family bootstrap intervals do not measure
repeat-judge variance. Protocols record call ceilings before execution.

Incomplete runs cannot pass the comparison gate. At most one failed-generation
or incomplete-batch recheck is allowed, with original artifacts retained.
Earlier Hydrogen HTTP 429/503 failures remain in `baseline/` and are excluded
from the paired Flash comparison.

## Reproduce the validation run

Use an ignored `.env.providers` configured for the same OpenAI-compatible endpoint.
The command incurs provider charges; the first-pass ceiling is 20 generation
and 80 judge calls per variant. Rechecks may add calls within the recorded cap.

```sh
OPENAI_COMPATIBLE_MODEL=gemini-3.8-flash RAGAS_JUDGE_TIMEOUT=120 \
.venv/bin/python scripts/run_faithfulness_experiment.py --live \
  --env-file .env.providers --cases evaluation/faithfulness-v2/validation.json \
  --prompt evaluation/faithfulness-debug-2026-11-23/candidate-v2-frozen.txt \
  --limit 20 --batch-size 4 --judge-model gemini-3.8-flash \
  --judge-context schema-v1 --judge-workers 2 --generation-seconds 60 \
  --max-calls-per-batch 16 --max-seconds 1800 --output-dir /tmp/retail-candidate-check
```

Use `baseline.txt` and a different output directory for the control. Run
`scripts/compare_faithfulness_experiments.py --baseline …/results.json
--candidate …/results.json --output …/comparison.json` for paired analysis.
Changing a prompt, model or evidence contract requires a new directory.

## Results

| Set | Standard Ragas | Custom SQL-aware | Coverage |
| --- | ---: | ---: | --- |
| Development baseline / candidate v1 | 0.689 / 0.782 | 0.975 / 0.961 | 10/10 each |
| Validation baseline / candidate v2 | 0.683 / 0.718 | 0.957 / 0.988 | 20/20 baseline; 20/20 candidate |
| Reserved test, candidate v2 | 0.752 | 1.000 | 20/20 |

Candidate v2 passed table/structure checks on all 20 validation and all 20
reserved test cases. Its frozen prompt is the repository default, `retail-v11-grounded-reports`.
No prompt edits were made after reserved-test execution began. The independent
China DeepSeek AI review covered 17 validation answers; the primary coding
assistant checked the remaining three. Neither is human acceptance.

[Machine-readable final metrics](final-metrics.json) ·
[Paired validation analysis](validation-comparison.json) ·
[Release decision](promotion.json).

The development candidate's custom score fell slightly, so v2 additionally fixes
query-versus-dataset limitation wording. Original failures and bounded provider
rechecks are retained. An empty-result checker also missed the phrase
`0 rows returned`; a regression test and minimal regex fix corrected deterministic
checks without changing generated answers or Ragas scores.

The release decision is separate from the strict automatic comparator. The paired
95% family-bootstrap change interval is [-0.012, 0.084], including zero: the
strict automatic statistical gate did not pass. The point estimate increased,
but a statistically reliable improvement is not established. Single-run
bootstrap intervals describe case/family uncertainty, not repeated-judge variance.
Historical 0.534/0.588 means are not paired controls for this `schema-v1` experiment.
