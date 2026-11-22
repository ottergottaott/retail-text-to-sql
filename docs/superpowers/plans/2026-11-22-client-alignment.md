# Client acceptance alignment implementation plan

**Goal:** Finish the existing prototype against the consolidated client spec and
prepare the public GitHub submission, retaining truthful evaluation boundaries.
**Spec:** `docs/acceptance-spec.md` v1.1.
**Architecture:** Preserve the LangGraph/FastAPI/SQLGlot backend. Add trusted brand
scope snapshots and conservative demographic SQL policy before any query result
is delivered to a model. Preserve legacy product snapshots as a fail-closed
compatibility path, not the reviewer entitlement model.
**Tech stack:** Python, SQLGlot, DuckDB fixtures, BigQuery, PostgreSQL, Docker.

## Constraints and review focus

- No DeepInfra calls. OpenCode China DeepSeek/GLM reviews are authorized.
- Live Gemini gate waits for user-provided key; do not assert live acceptance.
- Preserve stored reports/volumes and existing unrelated uncommitted packaging.
- Review alias/CTE privacy bypass, join fan-out, revoked scope, empty groups,
  external credentials and repeatable startup. No raw PII in model payloads.

## Task 1 — Brand authorization and retained artifacts

Files: security/config/analytics/store/agent/api/learning/knowledge and new
`tests/test_brand_access.py`. Interfaces: `scope_snapshot(principal)` and
`scope_allowed(snapshot, principal)` govern stored records; principal includes
brands/CEO role. Query binding uses brand predicates with parameterized values.
- [x] Write failing tests for manager/CEO, brand inheritance, cross-brand spend,
  report access revocation and parameter-bound BigQuery relations.
- [x] Run `.venv/bin/python -m pytest tests/test_brand_access.py -q` (red).
- [x] Implement policy and scope propagation, keep legacy product tests valid.
- [x] Run targeted and full suite; record output; commit.

## Task 2 — Demographic release policy

Files: new `retail/privacy.py`, analytics/config/model and
`tests/test_demographic_privacy.py`. Conservative policy rejects unsupported
demographic query shapes; valid flat grouped queries receive a distinct-customer
cohort HAVING guard before row limiting. No per-customer demographic selection
or demographic-filtered individual ranking. Privacy policy fails closed.
- [x] Write and observe failures for raw rows, aliases/nested bypasses, cohorts
  4/5, join duplicates, configurable threshold and CEO parity.
- [x] Implement guard and execute real fixture tests, then full suite; commit.

## Task 3 — Definitions, boundaries and design reconciliation

Files: agent/model/config, deployment examples, architecture/OpenSpec/setup docs,
submission summary and tests for model-boundary context and overrides.
- [x] Verify query/history/retrieval/log payload privacy; reproduce/fix gaps.
- [x] Supply explicit analytical defaults and override instructions; preserve
  disclosure in report review and demonstrate with controlled model tests.
- [x] Reconcile automatic learning/tone design, brand configuration and README.
- [x] Run full suite and record requirement-to-evidence matrix; commit.

## Task 4 — Packaging, end-to-end and publication

- [x] Verify fresh/repeated isolated Docker startup, persistence, CLI/WebUI and
  unavailable/invalid credentials without modifying unrelated deployments.
- [ ] Obtain independent OpenCode review on bounded code changes; resolve issues.
  Blocked: automatic approval rejected source transfer to Alibaba China; explicit
  source-transfer consent requested. No model review completed.
- [x] Inspect tracked history for credentials/private data before public push.
- [x] Set remote `git@github.com:ottergottaott/retail-text-to-sql.git`; publish
  reviewed clean commits only. Record remaining live Gemini gate explicitly.
- [ ] After user supplies key, run live Gemini/BigQuery independent SQL checks,
  update final evidence and publication. Goal remains incomplete until then.
