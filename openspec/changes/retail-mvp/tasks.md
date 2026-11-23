# Implementation and evidence

Unchecked means incomplete or not yet verified. Existing source is not proof.

- [x] Record agreed scope, design and acceptance scenarios.
- [x] Initialize OpenSpec for Codex and pass strict CLI validation of retail-mvp.
- [x] Verify safe SQL source binding and scoped fixture results with escape tests.
- [x] Verify representative live queries across all four table families (bounded counts, real job IDs/bytes; broader semantics still need review).
- [x] Implement Gemini structured adapter and LangGraph bounded execution; live provider verification remains separate.
- [x] Verify controlled follow-up context, clarification, schema tools and fixture report workflows.
- [ ] Evaluate real Gemini follow-ups and report quality against analyst-reviewed cases.
- [x] Implement authenticated API and required CLI; verify local CLI-to-API fixture run.
- [x] Verify owner-only persistence and strict deletion including restart/replay.
- [x] Add thin Open WebUI Pipe with progress and identity; verify transport in controlled tests.
- [x] Add semantic retrieval, rank fusion and scope/schema/version filtering; test with controlled vectors.
- [x] Evaluate actual embedding relevance with a held-out paraphrase/negative set (Qwen via DeepInfra; synthetic labels, no release-quality pass).
- [x] Add preferences, feedback/review publication and versioned persona operator command.
- [x] Design the nondeveloper persona editing/preview interface; implement versioned operator publication without redeploy.
- [x] Verify offline metadata correlations, sanitized dependency outcomes and call/query/result/context budgets.
- [ ] Verify real provider usage metadata and optional Langfuse export.
- [x] Add Docker image/Compose with persistent PostgreSQL and WebUI storage; validate Compose syntax.
- [x] Run offline SQL oracles, lexical retrieval smoke, safety and report lifecycle evaluation.
- [x] Document held-out model/retrieval evaluation and executive usability protocol.
- [x] Run real Gemini and BigQuery; record live jobs and sanitized traces (DeepInfra Gemini/Qwen, bounded aggregate/report workflow).
- [x] Run Docker and browser workflow against documented fixture setup.
- [x] Consolidate architecture HTML/diagrams, all-eight explanation and README; mark old alternatives as archived.
- [x] Audit each goal requirement against current authoritative evidence; unresolved gates recorded in `docs/completion-audit.md`.
- [x] Complete Superpowers review corrections for fixture deadlines, evidence-backed answers and terminal PII SQL denial; verify local and container behavior.

## Current verification boundary

Updated2026-11-21:147 pytest cases and22 local HTTP/CLI fixture checks pass.
DeepInfra structured Gemini chat and Qwen embeddings were exercised live.
Actual embedding relevance was measured on98 expanded retail cases,16 graded
challenge cases and a pinned WikiSQL100-query subset over2048 documents.
See `evaluation/retrieval-results-2026-11-21.md` for limitations and provenance.
Three real-model/fixture-SQL result oracles pass in each of no-retrieval, lexical
and hybrid; this is not live BigQuery or report-faithfulness evidence.

Pipe/API/agent/storage integration passed with actual ASGI transport. Earlier
Docker/PostgreSQL/browser fixture checks remain historical; the current Docker
daemon is unavailable. BigQuery project `static-bee-277223` and host ADC were subsequently configured;
all four table aggregates passed and the real hybrid agent executed BigQuery. Direct Google API, Langfuse export and human-reviewed follow-ups/report
quality remain unverified. BigQuery job/byte evidence is now available. The combined provider/Langfuse task remains unchecked
although DeepInfra token metadata was observed. No public submission was made.
OpenSpec CLI validation checks specification structure, not runtime completion.

Live evidence after ADC consent: `evaluation/bigquery-live-verification-2026-11-21.json`
and `evaluation/bigquery-live-workflow-2026-11-21.json`. Combined analysis/save
passed after prompt retail-v3; explicit follow-up save/list/open also passed.
Tests used isolated temporary stores; default application remains fixture.


## Final acceptance addendum — 2026-11-21

- [x] Execute 12 live business cases against independent physical BigQuery SQL,
  match results and save reports in the persistent live backend.
- [x] Verify real follow-up, ambiguity clarification, owned report open, PII denial,
  confirmed/cancelled/replayed deletion, SSE and hybrid retrieval.
- [x] Verify saved reports after a real backend process restart.
- [x] Fix omitted concise preference depth with required provider schema; verify
  final live regression while preserving earlier failures.
- [x] Add opt-in Ragas with bounded paid calls, source-separated aggregation,
  calibration/diagnostics and a real advisory run; obtain bounded DeepSeek review.
- [x] Run 167 tests after faithfulness/schema regressions and persist report review artifacts.
- [x] Complete live Open WebUI progress/table/save/new-chat-open after Docker VM recovery.
- [x] Add bounded report grounding revision before saving; require nonempty answer text in provider schema.
- [x] Support explicit stronger final reviewer with shared budgets and actual-model telemetry; no fallback.
- [x] Calibrate whole-response/factual Ragas metrics and preserve fixed-context comparison and failed live runs.
- [ ] Verify actual optional Langfuse ingestion/read-back when configured.
- [ ] Complete clean-machine setup and human report/UX acceptance.
- [x] Add deterministic HTML Artifacts and expandable embedded reports with
  owner/scope checks, inert model content, SQL evidence and supported revenue charts.
- [x] Verify fresh live report/save, cross-chat reopen after API restart, WebUI
  reload persistence, native HTML download payload, and template wheel packaging.

Current evidence is consolidated in docs/final-acceptance.md. Ragas scores and
DeepSeek review do not close human acceptance. The overall goal remains open.

- [x] Add durable automatic feedback processing, scoped publication and bounded retries.
- [x] Add CEO tone editor, automatic fixed-case gate and version rollback.
