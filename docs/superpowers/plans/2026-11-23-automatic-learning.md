# Automatic learning implementation plan

Goal: automatically process feedback and activate gated CEO tone updates without manual approval.

Approved scope: existing PostgreSQL/SQLite records hold durable feedback jobs; one API-process worker polls them. No new queue service. Personal learning stays unchanged.

- Preserve an immutable response-specific evidence snapshot for feedback, distinct from mutable conversation last_analysis.
- Worker claims jobs transactionally, uses bounded execution and persists safe failure states. Helpful evidence-backed responses can become scoped examples. Corrections require independent known regression evidence; unsupported corrections remain rejected, not trusted as ground truth. Deduplicate examples by content and scope.
- Tone requests require CEO access, run fixed synthetic render/judge checks and deterministic number/privacy checks, activate only passing candidates; retain previous version on failure and support rollback.
- One bounded worker in the single API process polls on startup; pending work survives restart. No cloud calls for fixture learning. Live gates use the configured model and sanitized contexts. Paid gate call limits and errors are explicit.
- API/WebUI expose owned feedback status and CEO tone controls; managers cannot update tone. Update architecture, setup and acceptance boundaries.
- TDD regressions cover rejected/missing evidence, scope shrinkage, duplicate requests, corrected results against independent fixtures, judge failure, tone permissions, rollback and persistence. Run full suite once after integration.

Boundary: automated evaluators provide safeguards, not proof of arbitrary corrections or production accuracy. Prototype remains single-worker; production scheduling across replicas requires distributed coordination.
