# Prompt iteration protocol

Prompts are hypotheses. A well-written instruction and a passing mechanics test
do not establish model behavior. Change serving instructions only after a paired
comparison and regressions, preserving unsuccessful runs.

## Separate contracts

1. **Planner/action dispatch:** correct action, valid arguments, clarification,
   evidence before answer, save ordering, one bounded SQL repair and preference preservation.
2. **SQL generation:** correct rows against independently authored reference SQL,
   population/grain/window consistency and executor rejection of unsafe queries.
3. **Final report review:** numeric fidelity, supported factual premises, requested
   tables, scope, limitations, proposals and truthful save status.
4. **Retrieval instruction:** Recall/MRR/nDCG, negative matches and index coverage.
   Changing it requires a new version/reindex; it is not a report-writing prompt.
5. **Evaluation judges:** frozen during candidate comparisons. Calibrate them
   independently; never improve an agent score by loosening the judge contract.

## Iteration 1 — final report review (22 November 2026)

At the time of iteration 1, the serving prompt was `retail-v7`. That experiment is isolated and does not
change the running API, shared knowledge or report records. Exact inputs and both
prompt variants are frozen in `evaluation/prompt-iteration-2026-11-22/`.

Eight synthetic adversarial drafts are reviewed using identical questions, SQL
results, preferences and trusted scope. Four calibration and four validation
cases are selected before calls. Both variants use the same configured review
model, with one generation per condition and temperature zero (not deterministic).
No SQL is executed and no BigQuery freshness difference can confound the comparison.

The candidate clarifies depth precedence and adds an evidence-checking procedure:
population/unit checks, measurement-boundary limitations, grounded next steps,
truthful save confirmation and retained exact table aliases/values. The existing
security and SQL-execution controls are unchanged.

The untouched standard Ragas faithfulness and custom SQL-aware factual metric
score both arms against original tool evidence. They are distinct contracts.
Record metric coverage, generation failures, elapsed time and measured tokens;
monetary cost is unavailable unless returned by the provider. Human inspection
of remaining claims and utility stays pending.

### Promotion gate

Do not promote from a mean score alone. Require complete evaluation coverage,
no unacceptable validation regression, inspection of exact generated claims and
preserved requested values/format. Then run planner, save/delete, preferences,
safety and representative live end-to-end regressions. A review-only experiment
does not measure SQL generation, tool selection, RAG or whole-product accuracy.

If results are mixed, retain the serving prompt and keep the candidate as an
experiment. Further tuning uses calibration cases; validate a final candidate
on additional untouched cases before declaring general improvement.

### Recorded outcome

All 16 generated answers were evaluated on both metrics (64 judge HTTP calls).
Generation used Gemini 3.1 Pro; the fixed judge used Gemini 3.5 Flash. On all eight
cases, standard faithfulness changed 0.5417 → 0.5528 and custom SQL-aware factual
faithfulness changed 0.9479 → 0.9226. On the four validation cases, both fell:
0.5446 → 0.5345 and 0.9583 → 0.9167 respectively. These are separate contracts,
not an overall accuracy score. One repetition does not estimate statistical significance.

**Candidate rejected; serving prompt unchanged.** The candidate removed an
invented currency in one case, but inspection still found reference-price vs.
historical-discount ambiguity, an unqualified order-key count proposal, and
unsupported negative claims about whether saving had occurred. The SQL-aware
judge did not expose every qualitative issue; score improvements alone would
not establish acceptance. The reviewer-depth change was not independently tested.

See exact [results](../evaluation/prompt-iteration-2026-11-22/results.json),
[assistant inspection](../evaluation/prompt-iteration-2026-11-22/assistant-inspection.json)
and original outputs. Next iteration should target these issues on calibration
cases, then use additional untouched validation and the actual deferred-save
workflow before any promotion. RAG and planner prompts were not changed by this experiment.

## Reproduce

Without `--live`, the CLI writes an untested report without loading inputs or
settings. Live runs preserve prior evidence by requiring a new output directory:

```sh
uv sync --frozen --extra dev --extra evaluation
uv run python scripts/evaluate_review_prompts.py --live --env-file .env.live --output-dir /tmp/retail-review-prompt-repeat
```

This explicitly permits up to 16 generation calls and 96 judge HTTP attempts.
The same configured DeepInfra review model is used for both arms; the judge is
fixed to Gemini Flash. No SQL, BigQuery jobs or application database writes occur.
Inspect per-case outputs and coverage, not just top-line means. Use a new case
file and new output directory for future validation, preserving the original.

## Iteration 2 — targeted semantics and workflow checks

DeepSeek V4.1 Flash (`acp-opencode`, `alibaba-cn/deepseek-v4.1-flash`, low)
independently inspected the serving prompt, orchestration and first experiment.
Its read-only critique is retained in
`evaluation/prompt-iteration-2-2026-11-22/deepseek-design-review.txt`.
It did not execute SQL, recompute metrics or provide human acceptance.

The second candidate replaces specific instructions instead of appending a broad
review checklist: catalogue reference gaps are not historical discounts; order
counts require distinct order keys; pending persistence belongs to the backend;
missing save evidence is not evidence of failure; prose depth follows the explicit
request/preferences. Original safety and query rules remain present.

The four exposed calibration cases are retained. Four new validation cases were
frozen before calls: pending reviewed save, detailed explicit table despite bullet
preferences, current-reference price gap and distinct orders versus items. Exact
inputs, prompts, protocol and digests are persisted in the iteration directory.
New validation here means new to this experiment; it is still a small synthetic
set designed by the implementing assistant, not an independent customer benchmark.

The paired evaluator now requires every expected answer to be generated and scored
on both judge metrics before reporting complete coverage. Failed generation,
unexpected action or missing judge records makes the experiment `incomplete`.
It reports expected/generated/scored counts and missing IDs, and derives split
counts from the input rather than assuming four per split. Controlled regressions
exercise all three missing-evidence paths.

A separate actual LangGraph experiment uses live configured Gemini decisions and
local fixture SQL in temporary stores. It checks query/review/deferred save,
new-chat report listing, opening an owned report, deletion preview without deletion,
undefined-metric clarification and persisted presentation preferences. This is
live-model workflow evidence, not live BigQuery correctness or browser acceptance.
The existing deterministic suite also tests review failure/budget exhaustion and
prevents unreviewed draft persistence.

### Iteration 2 outcome

Rejected. Baseline generated 7/8 answers and candidate 8/8; the experiment correctly
reported `incomplete`. The aggregate means have different denominators and cannot
establish a paired improvement. DeepSeek and implementing-assistant inspection
both caught invented dollar currency in the candidate's catalogue-price answer,
even though the SQL-aware judge assigned the candidate a mean of 1.0. This is a
concrete example of why judge scores do not replace exact-output inspection.
DeepSeek's customer-grain table finding was adjudicated separately: its actual
question did not explicitly request a table, so evaluator-only metadata is not a
user-facing requirement the model can be expected to see.

## Iteration 3 — promoted narrow save-state change

The candidate changes **only** the deferred-save paragraph. Other depth, price
and grain proposals from iteration 2 are not promoted. Exact evidence is retained
in `evaluation/prompt-iteration-3-2026-11-22/`.

Six paired synthetic cases include two exposed calibration cases and four new
validation cases. Both arms generated all six answers; both unchanged Ragas
metrics scored every answer (48 judge HTTP calls). Same Gemini 3.1 Pro review
model in both arms; fixed Gemini 3.5 Flash judge, one repetition.

On the four new validation cases, standard faithfulness changed
**0.6917 → 0.8036** and custom SQL-aware factual faithfulness changed
**0.7708 → 1.0000**. On all six cases the respective changes were
0.6648 → 0.7649 and 0.7639 → 1.0000. These are distinct metric contracts on a
small targeted set, not an overall product accuracy estimate or significance test.

DeepSeek V4.1 Flash independently inspected the exact answers and found no blocking
candidate regressions. The implementing assistant separately identified three
baseline unsupported assertions (two claims that saving did not occur and one
claim of successful saving while pending); none remained in these candidate
answers. Two additional baseline statements described a pending workflow; they
violate the deliberate backend-only status policy but are not counted as proven
false success claims. Requested table aliases/values were retained in all six
candidate answers.

The existing-receipt case is explicitly synthetic robustness evidence: runtime
`open_report` normally stops before review. Actual routing was checked separately
in the six-scenario live-model/local-fixture LangGraph run, which passed. A seventh
ordinary unsaved request completed with correct fixture rows, no saved report and
no unrequested save-status disclaimer. Temporary stores prevented application data
mutation. No live BigQuery correctness or browser acceptance is inferred from this.

**Promoted as `retail-v8`.** The shared prompt now says that pending saves persist
only after successful completed review, suppresses premature save-status assertions,
and leaves the confirmed receipt to the backend. Missing receipts support only
"not confirmed", not proof of failure. Prompt snapshots and trace version match.
Human review remains pending, and pre-existing report-grounding risks remain.

### Running API verification

After restarting the API with `retail-v8`, one authenticated live request executed
BigQuery, reviewed its catalogue-count answer and saved a real report. The saved
HTML returned successfully with a table, and the same trace recorded `retail-v8`.
See `live-api-smoke.json` in the iteration 3 directory. One real test report was
created; existing reports/chats were preserved. The first smoke invocation sent
`question` instead of the API's required `message` field and was rejected with
HTTP 422 before model/SQL work; this harness mistake is retained separately.
API and WebUI health checks passed. Browser visual acceptance was not repeated.
The full post-change controlled suite passed: 200 tests.
