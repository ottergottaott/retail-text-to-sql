# Final acceptance — 21 November 2026

The backend is live and has recorded evidence. The complete delivery is **not yet
accepted**: the live Open WebUI path, clean-machine setup, optional Langfuse and
human report/UX review remain open.

## Morning review

Open [the report review page](../evaluation/morning-review-2026-11-21.html), or
http://127.0.0.1:8002/morning-review-2026-11-21.html while its terminal is running.
It includes all twelve answers, actual rows, executed SQL, independent reference
SQL/results and per-report verdict/notes controls. Export your verdicts to JSON;
browser-local notes do not update the application's saved reports.

The live API is http://127.0.0.1:8001; `/health` verifies process/mode only.
API tokens remain private in `.env.live`. The static review server binds only to
loopback and serves the evaluation directory. It is a recorded review artifact,
not a working chat UI. See [reproducible host launch](setup.md#persistent-host-live-backend-used-for-final-acceptance).

## What passed

| Evidence | Result | Boundary |
| --- | --- | --- |
| [Business acceptance](../evaluation/live-business-results-2026-11-21.json) | 12/12 passed and saved | Live Gemini via DeepInfra; real BigQuery. Independently authored physical reference SQL; matching row sets/numbers. Public data snapshot, product scope 1 and 2. Not all twelve ran with the fully built hybrid index. |
| [Dialogue/security](../evaluation/live-dialogue-security-2026-11-21.json) | Final regressions passed | Previous-month context, undefined churn clarification, new-chat report open, owner isolation, PII refusal, strict deletion/cancel/replay, SSE, hybrid retrieval and real backend restart. Entitlement bypass check verifies no unauthorized evidence, not an explicit natural-language refusal. |
| Preference defect | Fixed and live retested | Model omitted `depth`; default became standard. Prompt alone failed. Required provider schema plus preference validation now persist bullets/concise. Two earlier failed attempts remain recorded. |
| [Faults and telemetry](../evaluation/fault-observability-checks-2026-11-21.json) | Passed | Controlled model/query failure injections and scan of 407 local metadata events. Not induced real provider faults or Langfuse delivery. |
| Full pytest | 159 passed | Controlled regression suite; separate from live-provider evidence. |
| [Retrieval measurements](../evaluation/retrieval-results-2026-11-21.md) | Recorded | Real Qwen embeddings; retail synthetic labels and pinned WikiSQL subset. Not a human-reviewed relevance release pass. |

All 23 current Golden trios were explicitly indexed into the live store with
Qwen3-Embedding-8B/1024 dimensions. A subsequent live SSE turn reported hybrid
retrieval. Reports are independent persisted records; a new chat can open them.
No WebUI chat-deletion scenario was exercised.

## Ragas and reviewer results

[Live Ragas report](../evaluation/ragas-results-2026-11-21.json),
[statement diagnostics/calibration](../evaluation/ragas-faithfulness-diagnostics-2026-11-21.json),
[DeepSeek review](../evaluation/deepseek-report-review-2026-11-21.json).

Ragas 0.4.4 evaluated four reports (one live, three fixture) and eight bilingual
retrieval samples. Faithfulness mean: **0.50**. Retrieval context precision:
approximately **1.0** over seven defined samples; context recall: **0.8571** over
seven Ragas measurements. Including the separately identified empty-context rule
zero gives **0.75** recall over eight samples. Overall status is **incomplete**
because one empty-context precision score is undefined. This is a small advisory
sample, not a release-quality pass or a benchmark against alternative models.

Measured provider use: 26 attempts, 50,863 total tokens; monetary cost unavailable
(`null`). The same Gemini model family served as judge and application model;
self-judge bias applies. Source-separated v2 aggregation reused the original
measurements without extra paid calls; original v1 output is archived.
Faithfulness receives SQL facts, retrieval metrics receive Golden methodology.
Recommended actions and general caveats often fail strict SQL entailment. Inspect
the diagnostics rather than dismissing low scores or treating them as numeric
SQL errors. Supported numeric calibration scored 1.0; a contradicted statement
scored 0.0. This does not prove general judge reliability.

DeepSeek reviewed 11 earlier report variants: nine fixture variants and two live
variants. It found no numeric contradiction against each report's own embedded
rows. It flagged small-sample caveats, speculative causes and missing temporal
limits. It did **not** independently recompute SQL. A subsequent separate
[twelve-case review](../evaluation/deepseek-live-business-review-2026-11-21.json)
covered all new business reports. Independent SQL verification is separate evidence.
Prompt v4 asks for small-sample caveats and labels proposed investigations, but
all twelve saved reports were not regenerated after that prompt change.

## Open gates and blockers

- **Live Open WebUI:** Docker initially started and the Pipe reached host API
  health. Then the daemon became unresponsive; Docker VM logs showed EXT4/buffer
  I/O errors. No factory reset, prune or volume removal was attempted. Existing
  data was preserved. Complete browser question/progress/table/save/new-chat-open
  after Docker recovery. Historical fixture browser evidence is separate.
- **Langfuse:** exporter exists; no configured functioning service/read-back was
  available. Local privacy/correlation checks do not verify ingestion.
- **Clean installation:** frozen lock/setup instructions exist, but another clean
  machine was not exercised. Do not claim this from the existing host.
- **Human acceptance:** review numbers, definitions, caveats and action items;
  assess live UI usability after Docker recovery. No human verdict is implied.
- **Submission:** no public repository was published. Candidate framework
  experience statement still needs the user's factual contribution.

The original assignment requires CLI and production design across eight
requirements; WebUI, Docker and this optional judge suite are additions. Their
current state must still be disclosed if demonstrated. Architecture and all-eight
requirement mapping remain in [architecture](architecture.md) and
[requirement audit](completion-audit.md).

## Reproduce measurements

From the configured project directory, with the host API running on port 8001:

```sh
uv run python scripts/verify_live_business.py --live --env-file .env.live --output /tmp/retail-business-recheck.json
uv sync --locked --extra dev --extra evaluation
uv run python scripts/evaluate_ragas.py --live --env-file .env.live --samples evaluation/ragas-samples.json --output /tmp/retail-ragas-recheck.json --max-calls 96
uv run pytest -q
OPENSPEC_TELEMETRY=0 openspec validate retail-mvp --strict
```

Live business rechecks create new saved reports and incur model/BigQuery usage;
Ragas incurs judge usage. Review the pinned cases before rerunning. Never replace
existing evidence with a new run without preserving its provenance.


## Review corrections and isolated-install evidence

The twelve-case DeepSeek review caught a real false-success defect: realized-price
matched its SQL oracle and saved, but its empty generated narrative fell back to
a clarification message. The original run was incorrectly labeled passing.
The agent now rejects blank final analyses without saving or updating last-analysis
state. The verifier also checks minimum report structure for the pinned English
cases. Both fixes have RED/GREEN regressions. A [new live realized-price run](../evaluation/live-business-realized-price-recheck-2026-11-21.json)
matched the independent SQL, generated limitations/action items and saved a new
report. The consolidated twelve-case result now includes that rerun. Original
mislabeled evidence and the original saved report are retained, not deleted.

The rerun still overstates that identical prices prove no discounting. This is a
human-review flag, not a numeric-oracle failure. Other wording/action caveats
remain visible in the reviewer output and [dispositions](../evaluation/review-disposition-2026-11-21.json).
The reviewer's concern about omitted product predicates in logical SQL is resolved
by the existing executor design: `physical_sources` + `bind` replace every source
with principal-scoped physical subqueries. Model-supplied predicates are not the
access-control boundary. The review page now labels these as logical SQL.

A new isolated virtual environment was installed from the frozen lock on this
host, including a non-editable application wheel. The regression suite passed
159 tests with the isolated dependencies. The installed wheel's standalone
fixture evaluator passed 21/21 cases with explicit repository case-file paths.
Its defaults locate cases beside the package and are not available in a wheel;
pass `--sql-cases` and `--retrieval-cases` when evaluating a non-editable install.
This verifies dependency isolation/packaging on the existing machine, not a new
machine, Docker build or provider credentials on a new host. Installation and
JUnit logs are saved in the thread's storage. Ordinary README `uv sync` uses an
editable checkout where bundled evaluation paths are available.
