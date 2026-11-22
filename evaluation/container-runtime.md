# Local container verification

Verified on 2026-11-20 without external provider credentials.

- Docker API image built successfully; PostgreSQL 16.6 and Open WebUI
  v0.13.4-slim started with healthy services on loopback ports.
- CLI inside the API container created report `rep_c4eacfe5b7d078dc` using
  PostgreSQL persistence and fixture analytics (monthly values 100 and 110).
- API container was recreated after WebUI identity mapping; a fresh CLI
  conversation still listed the original report.
- Actual headless-browser Open WebUI chat selected Retail Analyst, created and
  saved report `rep_23e0f3675875c7d9`, rendered the evidence table, and exposed
  status history including retrieval, planning, query and completion.
- A fresh WebUI chat listed both reports, including the CLI-created report.
- A separate running-API lifecycle verification passed all 15 checks, including
  PostgreSQL concurrent confirmation: two simultaneous requests returned deletion
  counts 0 and 1; replay returned 0. Cancellation, cross-owner/conversation denial,
  strict booleans and preservation of pre-existing reports also passed.
- Browser screenshot was visually inspected; the browser session was closed
  and the private temporary login helper removed. Containers remain running.
- After Superpowers review corrections, the API image was rebuilt and recreated.
  Four in-container regression checks passed for expired/nonterminating queries,
  unsupported analytical completion and sensitive SQL denial. All 15 PostgreSQL
  lifecycle checks passed again. See `docs/superpowers-review.md`.

Thread evidence: `retail-docker-build.log`, `retail-docker-pull.log`,
`retail-compose-up.log`, `retail-container-cli.json`,
`retail-container-reports.json`, `retail-container-status.jsonl`,
`retail-webui-browser.json`, `retail-webui.jpg`, and
`retail-postgres-lifecycle.json` under the thread storage. The lifecycle JSON is
also copied to `evaluation/latest-postgres-lifecycle.json`.

This is fixture integration evidence. Real Gemini decisions/usage, embedding
relevance, BigQuery jobs and optional Langfuse export remain unverified. Browser
chat deletion is not covered by this run; backend report lifetime is independent
of WebUI chat storage by design and is separately exercised in local tests.
