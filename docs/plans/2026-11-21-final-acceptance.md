# Final acceptance and Ragas implementation plan

> Execute with Superpowers executing-plans and TDD. User requested continuous completion and morning review; no further design choices are pending.

## Design

Keep the existing deterministic retrieval metrics and independent SQL oracles.
Add optional Ragas 0.4.4 evaluation, outside the request path, using explicit
DeepInfra judge calls. Faithfulness receives SQL results and metric definitions,
not Golden reports as factual evidence. Context precision/recall receive curated
Golden reference logic. These are distinct evaluations with separate scores.
All judge results are advisory, with errors recorded rather than counted as zero.
Never export raw prompts, reports, SQL results, credentials or customer identifiers
to Langfuse. Verify actual ingestion with metadata and a read-back through its API.

## Tasks

- [x] Add bounded, opt-in Ragas CLI and dependency extra; RED/GREEN tests for
  sample boundaries, empty context, timeout/error reporting and offline default.
- [x] Run 10–15 real Gemini/BigQuery business cases against independently
  written reference SQL, save report/evidence pairs for morning review.
- [ ] Verify browser progress, table, save, fresh-chat opening, dialogue,
  ownership, PII refusal, deletion preview/cancel/confirm and persistence.
- [ ] Start isolated local Langfuse if resources permit; validate ingestion and
  metadata-only export. Record any actual external blocker explicitly.
- [x] Run Ragas on saved reports and a bounded labeled retrieval sample;
  obtain DeepSeek review, fix material defects, run complete tests and OpenSpec.
- [x] Document launch/review steps, artifacts, measured failures and remaining
  human checks. Keep services and saved reports available for morning review.

## Constraints and review focus

Preserve existing volumes and fixture data. Use protected `.env.live` and isolated
live SQLite state with host ADC. No secret values in logs or tool output.
Bound billable calls and judge retries. Public data can change: compare queries
within the same run. Do not count a semantic fallback as tested hybrid retrieval.
No human acceptance or clean-machine installation claim from automated review.

## Execution ledger

- Docker Desktop started; existing fixture stack preserved.
- Host live backend on 8001 and Open WebUI on 3000 configured; browser acceptance
  not yet complete. Golden indexing hit provider read timeout twice; investigate.
- DeepSeek review attempt encountered external-directory/tool approval failures;
  do not claim a completed review until its artifact has been inspected.


## Final execution ledger

12/12 live business oracles passed and reports persisted. Live dialogue/security,
SSE, actual hybrid retrieval and restart persistence passed. Two preference
failures were preserved; required format/depth schema fixed the defect and the
live regression passed. Full test suite: 159 passed.

Ragas ran (26 provider attempts, 50,863 measured tokens); v2 aggregation separates
Ragas scores from empty-context rules. Faithfulness 0.50 is advisory and requires
review. Statement diagnostics/calibration and DeepSeek review are saved. The
DeepSeek set is 11 earlier report variants, not these 12 independent business cases.

Docker initially recovered then became unresponsive; VM console showed disk I/O
errors. Live WebUI and Langfuse ingestion remain blocked/unverified. No volumes
were removed. Backend and read-only review page remain in persistent BB terminals;
see docs/final-acceptance.md. Clean-machine and human review remain open.


Follow-up review of all 12 live reports exposed one empty-narrative false success.
RED/GREEN guard and stricter business harness added; actual realized-price recheck
passed, preserving original failed evidence/report. Residual prose issues are
flagged for human review. Frozen isolated install, 159 regression tests and 21
installed-wheel fixture evaluations passed on the same host. Clean-machine and
Docker/WebUI remain distinct open gates.
