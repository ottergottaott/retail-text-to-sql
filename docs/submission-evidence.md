# Evidence guide

Updated on 22 November 2026. Results are local observations, not production guarantees.

Current entry point: [one-page review summary](review-summary.html),
[source-backed metrics](../evaluation/submission-metrics-2026-11-22.json) and
[browser acceptance](../evaluation/browser-acceptance-2026-11-22.json).
The latest regression suite passed 253/253 tests; see [client-alignment evidence](../evaluation/client-alignment-2026-11-22.json). Earlier dated summaries retain their original counts.
DeepSeek independently audited the metric claims and compared the new live
WebUI report with its embedded SQL evidence; it did not execute SQL or inspect
screenshots. Both critiques are retained in `evaluation/deepseek-*-2026-11-22.json`.

| Area | Evidence | What it establishes |
| --- | --- | --- |
| Regression suite | 253 passing tests, including brand scope, demographic privacy, experiment infrastructure and CLI integration | Controlled safety, workflow, provider-contract and learning mechanics |
| Prompt iteration | `evaluation/prompt-iteration-3-2026-11-22/` | Narrow save-state improvement: complete paired generation/scoring, DeepSeek critique, live-model/fixture-SQL workflow checks; distinct Ragas contracts |
| WebUI feedback/preferences | `evaluation/learning-loop-acceptance-2026-11-21.json` | Actual native Actions, owned response mapping, unreviewed feedback and persisted preferences |
| Reviewed improvement | `evaluation/learning-loop-live-v2-2026-11-21.json` | Real Gemini/Qwen calls; one synthetic new definition, reviewed publication/indexing, correct fixture SQL result |
| Live BigQuery business checks | `evaluation/live-business-pro-final-2026-11-21.json` | Twelve selected reports with query/reference checks; thirteen initial/recheck requests, not twelve consecutive successes |
| Report quality | `evaluation/faithfulness-pro-live-results-2026-11-21.json` | Standard Ragas and custom SQL-aware scores under different documented contracts |
| Retail retrieval | `evaluation/retrieval-gate-2026-11-21/` | Live-embedding cache comparisons; supported retrieval retained while measured negative matches fell |
| External retrieval | `evaluation/retrieval-results-2026-11-21.md` | WikiSQL diagnostic and retail retrieval measurements; not end-to-end SQL execution accuracy |

Read [final acceptance](final-acceptance.md) for the recorded report-quality
failures and limitations. Standard whole-response Ragas faithfulness was 0.534;
custom SQL-aware factual faithfulness was 0.843 on twelve selected reports.
They are different judge contracts and must not be presented as improvement
from 53.4% to 84.3%, or as an overall answer-accuracy score.

The learning demo's initial result is retained alongside v2: “Show products”
returned a correct catalogue list but failed the exact count-row oracle. V2
explicitly requested a count column; this prompt change is disclosed, rather
than presented as an unchanged repeated benchmark. No broad learning gain is claimed.

The latest client-alignment changes have controlled fixture/SDK-contract coverage.
Earlier live SQL, judge and browser evidence predates the new brand/cohort policy
and does not establish live acceptance of retail-v9-client-policy.

## Remaining checks

- Final human review of report usefulness and factual premises.
- Fresh installation on another machine; the provided flow has not been exercised there.
- Completion of the latest paid faithfulness study. Local Langfuse experiment ingestion and live metadata delivery are verified; see [experiments](faithfulness-experiments.md).
- Downloaded-file persistence and native fullscreen in the headless browser.

The final browser pass exercised a new live analysis/save, report navigation,
SQL highlighting, a separate report tab, reload, narrow-screen layout, feedback,
preference persistence, cancellation and confirmation of one disposable report
deletion, and reopening the primary report after deleting its WebUI chat.
Cross-user and provider-failure paths retain controlled API/CLI coverage;
live browser fault injection was not performed. The twelve-report business
suite is retail-v7 evidence; the new retail-v8 browser smoke does not replace it.

Archived documents may contain earlier test counts and operational snapshots.
Use START_HERE and the dated evidence above as the submission entry point.

See [prompt iteration protocol and results](prompt-improvement.md) for rejected candidates, frozen cases, exact metric contracts and the narrow `retail-v8` promotion. These targeted synthetic scores do not replace the twelve-report live business evaluation.

## CLI follow-up verification (22 November)

Five CLI subprocess/HTTP/SSE integration tests passed. The installed `retail` executable also completed a real Gemini/BigQuery count request and a follow-up with the same conversation, no repeated SQL and no report save. See [CLI verification](../evaluation/cli-verification-2026-11-22.md) and [live evidence](../evaluation/cli-live-2026-11-22.json). This does not establish browser visual acceptance.

## Extracted archive check (22 November)

A candidate archive was extracted into a fresh directory and installed with
`uv sync --frozen --extra dev`, a new virtualenv and an isolated empty uv cache.
The installed CLI help and all five subprocess/HTTP/SSE fixture workflow tests
passed (39.65 seconds). Source manifest hashes and exclusion of private state
were checked. Runtime, integration and test files remain identical to that
candidate; subsequent changes concern the handoff and its evidence.
See [installation record](../evaluation/archive-installation-2026-11-22.json).
This is a same-host check; the complete Docker/bootstrap walkthrough and
installation on another machine were not rerun.

[Actual browser captures](browser-screenshots.html) are bundled offline.
