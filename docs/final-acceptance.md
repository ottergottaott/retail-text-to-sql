# Final acceptance — 21 November 2026

Historical run. For the 22 November regression/browser follow-up and current
submission status, see [review summary](review-summary.html).

## Interactive report update

Open WebUI now offers embedded report cards plus HTML Artifacts, supported
revenue charts, expandable SQL/results, and a downloadable standalone HTML
snapshot. [Usage and boundaries](report-experience.md).

Live report `rep_3c595b29bfd416bd` was created through WebUI and reopened from
new chats after API restarts. Reload persistence and the native download Blob
were checked. Owner HTML access passed and Bob received 403. The current suite
has **177 passing tests**, strict OpenSpec passed, and the built wheel includes
the HTML template. [Detailed evidence](../evaluation/webui-report-experience-2026-11-21.json).

Human UX acceptance, OS download persistence, and native fullscreen behavior
remain unverified. HTML presentation does not change the faithfulness findings
or the remaining acceptance gates below. Chat/download snapshots are not revoked
when the source report is deleted.

## Open for review

- [Morning review page](../evaluation/morning-review-2026-11-21.html), also served at http://127.0.0.1:8002/morning-review-2026-11-21.html.
- Live Open WebUI: http://127.0.0.1:3000. Live API: http://127.0.0.1:8001.
- [Source-linked faithfulness summary](../evaluation/faithfulness-summary-2026-11-21.json).

The page contains exact recorded answers, actual SQL rows, independently authored
physical BigQuery reference SQL/results, saved IDs and local human verdict/notes
controls. Export verdicts to JSON; browser notes do not modify application reports.
Credentials and application tokens remain private in `.env.live`.

## What changed for faithfulness

Live analysis follows Context → Plan/Tool loop → Draft → Review → Answer/save.
One grounding revision receives original SQL/results and trusted execution scope;
the draft is not evidence. It runs before completed-analysis/report persistence,
shares existing call/time/context budgets and cannot call tools. A failed/blank
review leaves no completed draft saved. The provider schema requires text;
DeepInfra additionally requires a nonempty answer. Application guards remain.
Google SDK schema compatibility has a regression test.

The configured host uses Gemini 3.5 Flash for planning and Gemini 3.1 Pro for
final review through DeepInfra. `DEEPINFRA_REVIEW_MODEL` is optional; empty uses
the planning model. Reviewer failure does not fall back to an unreviewed draft.
A bounded two-record experiment measured Pro review calls at about 14/18 seconds
and removed an unsupported no-discounts inference. This is not a general model
benchmark. Actual model/token metadata is recorded per stage; cost is not invented.

SQL instructions now filter Complete populations before grouping so counts,
prices and time buckets use consistent populations. Trusted source binding is
explicit in context: missing product predicates in logical SQL do not mean access
control was omitted. Customer, item and order counts remain distinct metrics.

## Verification evidence

The final configured run is [Pro-reviewed live business verification](../evaluation/live-business-pro-final-2026-11-21.json).
See its status and each case's query oracle, report structure and save fields;
these are not report-text semantic acceptance. Eleven initial turns passed; one
Pro review failed and saved nothing. An explicit recheck passed, giving twelve
selected reports from thirteen requests. The original failure is retained in
[the initial Pro run](../evaluation/live-business-pro-reviewed-v9-2026-11-21.json). The prior full Flash run passed
12/12 independent physical BigQuery oracles and saved all twelve reports.
Intermediate v5/v6 failures and focused v8 no-discounts regression remain archived.
No saved historical report was silently rewritten after a prompt/model change.

[Live browser evidence](../evaluation/webui-live-grounded-2026-11-21.json)
verified visible progress, rendered table, saving and opening the same report from
a new WebUI chat. A separate final Pro-reviewed price-analysis browser turn is
recorded in the thread artifacts. Chat deletion itself was not exercised.
Docker recovered without prune/reset or volume removal. Thirteen unrelated
containers were stopped; only retail WebUI remains running. API/SQLite run on host.

The current controlled regression suite passed **167 tests**; strict OpenSpec
validation passed. Earlier [dialogue/security/restart evidence](../evaluation/live-dialogue-security-2026-11-21.json)
covers previous-month follow-up, ambiguity, preferences, owner isolation, PII
refusal, confirmed/cancelled/replayed deletion, persisted reports and hybrid SSE.
[Fault/observability checks](../evaluation/fault-observability-checks-2026-11-21.json)
cover controlled model/query failures and metadata privacy. These are distinct
from real provider fault injection or Langfuse ingestion.

## Three different judge contracts

1. `faithfulness`: unmodified Ragas whole-response entailment.
2. `factual_faithfulness`: factual extraction v1, retaining assertions inside recommendations and limitations; pure proposals excluded.
3. `sql_factual_faithfulness`: a custom SQL/provenance-aware NLI contract, handling trusted binding, untruncated groups and query measurement boundaries.

Do not compare the three as though they were one metric. All receive the original
full answer; SQL contexts contain tool evidence and independently persisted report
metadata, never facts inferred from answer text. Scores, coverage, call budgets,
measured tokens and unavailable monetary cost are in their linked JSON reports.

The controlled four-record comparison uses identical contexts (one live, three
fixture) for baseline/reviewed text. Fresh reports are measured separately: the
public data changed between historical and current runs. The SQL-aware variant
was introduced after statement diagnostics showed standard NLI rejecting valid
executor scope and inventing truncation despite `truncated=false`. Standard
scores remain visible; they were not replaced with the custom score.

The [twelve-case SQL-aware calibration](../evaluation/faithfulness-sql-calibration-results-2026-11-21.json)
checks three supported cases and nine traps: wrong numbers, unsupported causes,
hidden premises, invented sample size, discounts, customer/transaction confusion,
truncated populations, unauthorized global scope and invented system absence.
All supported cases scored fully entailed; each negative case lost entailment.
This small calibration does not prove a judge is reliable on every report.

The [earlier fresh Flash results](../evaluation/faithfulness-live-results-2026-11-21.json),
[SQL-aware scores](../evaluation/faithfulness-sql-live-results-2026-11-21.json),
[statement diagnostics](../evaluation/faithfulness-live-diagnostics-2026-11-21.json)
and [focused stronger-review experiment](../evaluation/faithfulness-pro-review-experiment-2026-11-21.json)
remain available. The v8 Flash recheck reintroduced the incorrect no-discounts
claim despite matching its SQL oracle; it is explicitly a report-quality failure.
High aggregate scores do not erase that failure. Final Pro-reviewed reports and
scores are shown separately on the review page.

## Final measured report scores

The twelve selected Pro-reviewed reports were scored in two disjoint batches;
no successful report was omitted or rescored. Unmodified Ragas whole-response
faithfulness: **0.534**; custom SQL-aware factual faithfulness: **0.843**,
with all twelve scored for each metric. These are distinct contracts, not two
measurements on one scale. See [full results](../evaluation/faithfulness-pro-live-results-2026-11-21.json).
This does not establish general aggregate superiority of Pro over Flash; the
reviewer remains configurable and adds latency. Human quality acceptance is open.

## Remaining acceptance

Human report/UX acceptance is pending. Inspect definitions, narrow scope, sample
sizes, causal claims and useful actions; neither numeric equality nor an LLM
judge grants human acceptance. The Gemini family is used for application and
judge, so self-judge bias applies even with different model variants.

Optional Langfuse actual ingestion/read-back remains unverified: local metadata
privacy/correlation is separate evidence. Clean-machine setup remains untested.
An earlier fresh virtual environment installed the locked dependencies and a wheel,
passed 159 tests plus 21 installed-wheel fixture cases; that was this same host,
not a clean machine. No public repository/submission was published.

[Architecture](architecture.md), [evaluation contracts](evaluation.md),
[reproducible setup](setup.md) and [all-eight requirement audit](completion-audit.md)
cover the assignment and additions. The [previous acceptance snapshot](final-acceptance-before-faithfulness.md)
is retained as historical context, not current runtime status.

## Reproduce

```sh
uv sync --locked --extra dev --extra evaluation
uv run python scripts/verify_live_business.py --live --env-file .env.live --output /tmp/retail-business-recheck.json
uv run python scripts/evaluate_ragas.py --live --env-file .env.live --samples evaluation/faithfulness-live-samples-2026-11-21.json --output /tmp/retail-judge-recheck.json --metrics faithfulness sql_factual_faithfulness --max-calls 112
uv run pytest -q
OPENSPEC_TELEMETRY=0 openspec validate retail-mvp --strict
```

Live verification creates reports and incurs bounded model/BigQuery usage.
The Ragas command above rejudges recorded Flash reports; build inputs from a new
business run plus independent persisted report metadata to judge fresh reports.
See evaluation.md for the sample builder. Preserve original evidence on reruns.
