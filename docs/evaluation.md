# Evaluation and release evidence

## Offline commands

```sh
uv sync --extra dev
uv run pytest -q
uv run python -m retail.evaluate --output /tmp/retail-evaluation.json
uv run python scripts/verify_offline.py --output /tmp/retail-offline-workflow.json
```

The standalone evaluator ignores `.env` and explicitly uses fixture mode. SQL
cases are independently written expected results in `evaluation/sql-cases.json`.
They cover product/status grain, monthly revenue, customer-state joins, orders
and two-user scope. It also checks a small lexical retrieval set, unsafe-query
denial and a persisted report preview/confirmation/replay scenario. It exits
nonzero for a failed oracle. The JSON report states what was not evaluated.

The HTTP/CLI verification script starts a real local API process with explicit
fixture configuration, creates and saves a report in one turn, restarts the API,
opens the report in a fresh chat, checks cross-user denial and exercises preview,
cancellation, confirmation and replay. It stores responses and metadata events
without using external credentials. This is process/transport/persistence
evidence, not Gemini, BigQuery or Open WebUI browser evidence.

The lexical examples are a smoke set, not a held-out benchmark. A high score on
these few seed-related questions is not proof of broad retrieval relevance.
Controlled-vector tests check fusion, indexing/versioning and scope mechanics;
they do not assess Gemini embeddings. The fixture planner is rule based and
does not evaluate natural-language understanding or generated report quality.

The pytest suite additionally exercises sanitized SQL errors, source binding
through CTEs, ownership/revocation, changed/expired/cancelled/replayed proposals,
model failure/budgets, follow-up context, preference isolation, reviewed knowledge
publication, persona refresh, API identity and SSE, and the Pipe's controlled
transport. BigQuery SDK mocks verify contract fields and disabled implicit
retries; they are explicitly not live service evidence.

## Live evaluation protocol

For an already running local fixture stack, verify transactional deletion using:

```sh
.venv/bin/python scripts/verify_deployed_fixture.py --output /tmp/retail-postgres-lifecycle.json
```

This script refuses live mode and deletes only the report it creates. It checks
owner/conversation isolation, strict booleans, cancellation, two concurrent
confirmations, replay and preservation of existing reports. All 15 checks passed
against the Compose PostgreSQL backend. Docker/WebUI runtime evidence is recorded
separately in [container-runtime.md](../evaluation/container-runtime.md).

Prepare disjoint development and held-out questions with analyst-reviewed intent,
definitions, permitted scope, reference SQL/results and acceptable report claims.
Record dataset date/freshness, model/config/prompt/persona/index versions and
trace IDs. Run customer, product and time queries across all four physical tables;
inspect BigQuery job IDs, source binding and processed bytes. Re-run equivalent
reference SQL under the same entitlement scope; compare ordered sets or tolerant
numeric results rather than exact SQL strings. Public dataset changes require
fresh reference evidence, not fixture expectations.

Score final answers on intent coverage, correct grain/status/window/denominator,
grounded numeric claims, explicit empty/truncated/freshness limits, absence of
unsupported causal claims, and actions tied to findings. Have a human analyst
review failures and a sample of passes. Any LLM judge must be calibrated and
cannot override deterministic safety checks. A successful query alone does not
prove that the report answers the executive's question.

For retrieval, label relevant trio IDs/versions for paraphrases, exact business
terms, misleading similar questions, no-match requests, changed schemas and
restricted scopes. Compare lexical-only, vector-only and hybrid Recall@2, MRR,
irrelevant-example rate and latency. Tune similarity threshold on development
cases, then freeze it before held-out evaluation. Run end-to-end report cases
with and without retrieval to check whether better retrieval helps generation.

Reliability cases include malformed SQL, empty filters, BigQuery/Gemini failure,
rate limit, exhausted time/call/byte budgets, interrupted SSE, failed persistence,
and unavailable observability. Validate real outcomes and storage after a
mutation interruption; do not assume an absent HTTP response means no commit.

## UX validation

Run real CLI and browser tasks with nontechnical reviewers: ask a regional spend
comparison; clarify churn definition; request a report and Q2 action items; save
and retrieve it from a new chat; cancel a deletion; confirm a different deletion;
recover from a dependency error. Observe task completion without help, time to
useful answer, clarification burden, progress/error comprehension and accidental
destructive actions. Record comments and participant context. No human study or
usability score is currently claimed.

## Release gate

Security invariants must all pass. Analyst-reviewed correctness, retrieval and
UX thresholds must be agreed before release and applied to held-out cases.
Docker/PostgreSQL start and pinned WebUI fixture browser workflow are verified.
Real Gemini/BigQuery business acceptance now has 12 passing independent SQL
oracles. Keep fixture and live reports separate. Final live browser, human UX/report
acceptance and clean-machine installation remain open; Langfuse export is unverified.


## Recorded final acceptance — 2026-11-21

See [final acceptance](final-acceptance.md) and the [review page](../evaluation/morning-review-2026-11-21.html).
The 12 business cases matched independently written physical BigQuery reference
queries and saved their reports in the persistent live application store. Real
follow-up, clarification, report ownership, PII refusal, deletion confirmation,
SSE progress, hybrid retrieval and process-restart persistence were checked.
Earlier preference failures remain recorded; the final required-schema regression
passed with bullets/concise. Full pytest: 159 passed.

### Optional Ragas 0.4.4

```sh
uv sync --locked --extra dev --extra evaluation
uv run python scripts/evaluate_ragas.py --live --env-file .env.live --samples evaluation/ragas-samples.json --output /tmp/retail-ragas.json --max-calls 96
```

Omit `--live` for an untested report without reading inputs/settings or calling a
provider. Live calls are billed, bounded at the HTTP transport, with no SDK or
transport retries. Metric timeouts are bounded individually; there is no global
wall-clock deadline. Faithfulness may require multiple judge calls per sample.
Ragas is optional evaluation tooling and is not imported into the serving path.
The pinned extra is required only for a live Ragas run.

Recorded [Ragas results](../evaluation/ragas-results-2026-11-21.json) cover four
report samples (one live, three fixture) and eight EN/RU retrieval examples.
`means` includes only Ragas-computed scores; `combined_means` explicitly adds
empty-context rule values. Coverage reports Ragas/rule/applicable counts. The
recorded result is incomplete: one empty-context precision score is undefined.
Faithfulness mean 0.50 is not a quality pass; inspect [statement diagnostics](../evaluation/ragas-faithfulness-diagnostics-2026-11-21.json).
Calibration supported a correct numeric statement (1.0) and rejected a contradicted
one (0.0), but this does not calibrate all report categories. The judge is the
same Gemini model family as the application, introducing self-judge bias.
Faithfulness uses SQL facts; context precision/recall use Golden reference logic,
not independent live numerical correctness. Deterministic Recall/Precision/MRR/nDCG
remain separate retrieval measurements. The original aggregation is archived;
v2 reaggregation made no new paid calls and preserved measured token provenance.

## Faithfulness repair (21 November 2026)

Live analytical drafts now pass through one LangGraph `review` node before
last-analysis/report persistence. It receives the original SQL/results and
trusted executor scope, shares the turn's existing budgets, and cannot run tools.
An error, blank answer or exhausted review budget leaves no completed draft.
Provider JSON schema requires `text` and a nonempty value for `action=answer`;
the application still checks blanks independently. Fixture mode remains explicit
and skips the additional live model call.

Keep two separate judge metrics. `faithfulness` is unmodified Ragas whole-answer
entailment. `factual_faithfulness` uses a versioned factual-extraction instruction
with the original full answer, including empirical premises in hypotheses,
limitations and recommendations. Only pure proposals without factual assertions
are excluded. It is not directly comparable to the whole-answer metric, does
not filter sections locally and does not change the NLI judge. Neither metric
proves correct SQL or adequate answers. Numeric oracles and completeness/save
checks remain separate; a faithful answer to the wrong SQL question can fail them.

The six-case calibration includes supported facts plus numeric contradictions,
unsupported causes, hidden recommendation premises, invented sample size and a
no-discounts overclaim. All five negative traps must lose factual entailment;
a mean across these intentionally wrong answers is not a product quality score.
The fixed-evidence replay preserves all four original contexts (one live, three
fixture) and compares baseline/reviewed text under the same judge. Fresh live
reports are evaluated separately because the public source data can change.

Reproduce fresh inputs from recorded verifier output; report metadata must be an
independent export of persisted report IDs/titles, never extracted from prose:

```sh
uv run python scripts/build_faithfulness_samples.py --input evaluation/live-business-grounded-v7-2026-11-21.json --report-metadata evaluation/faithfulness-report-metadata-2026-11-21.json --output /tmp/fresh-faithfulness-samples.json
uv run python scripts/evaluate_ragas.py --live --env-file .env.live --samples /tmp/fresh-faithfulness-samples.json --output /tmp/fresh-faithfulness-results.json --metrics faithfulness factual_faithfulness --max-calls 112
```

Actual evaluation scores and coverage are in
[the source-linked summary](../evaluation/faithfulness-summary-2026-11-21.json).
The same Gemini model family serves as application and judge; self-judge bias,
small sample size and pending human review remain explicit. Failed intermediate
runs are retained and do not become passing evidence when a later run succeeds.

### SQL/provenance-aware diagnostic variant

`sql_factual_faithfulness` is a third, explicitly custom metric. It keeps factual
extraction and adds an NLI contract for interpreting SQL plus trusted executor
metadata: scoped physical binding need not appear as a logical WHERE clause;
untruncated unsampled GROUP BY groups describe the queried population; SQL can
establish which dimensions this analysis did not measure. It must still reject
claims about unqueried global data, discounts, causal effects or transaction
counts inferred from distinct customers. This is not unmodified Ragas and its
scores must not be presented as an improvement to the standard metric.

Statement diagnostics exposed these NLI mistakes in the standard/v1 metrics.
The new twelve-case calibration contains both positive SQL/scope examples and
nine negative traps, including truncated-population and company-global scope
overclaims. Do not add answer-derived facts to contexts to make them pass.
All three metric contracts/results remain separately available. Focused Flash
rechecks and the bounded Pro-review experiment are distinct from a full live run.
