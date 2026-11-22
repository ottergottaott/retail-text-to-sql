# Retail analysis MVP

## Why
Deliver the supplied retail assessment as a runnable, reviewable application.
The assignment PDF is authoritative; this change records agreed implementation
decisions and acceptance scenarios. Earlier `retail-ai-*` documents are discovery
notes and may describe superseded UI choices.

## Scope
- Required core: CLI, Gemini, real BigQuery, dynamic read-only analysis,
  conversational context, reports, product access, PII protection, confirmed
  report deletion, graceful errors and observable execution.
- Chosen additions: Docker Compose, Python API, LangGraph, Open WebUI thin Pipe,
  curated retrieval, persistent preferences, reviewed improvement demonstration,
  versioned persona and focused executable evaluation.
- Production design: all eight original requirements, including learning,
  evaluation and future chart/email/web-search extensions.
- Publication is a separate user-authorized action.

## Delivery boundary
Fixture demonstrations never count as live Gemini, BigQuery or Docker evidence.
Passing local tests is insufficient to declare the full MVP complete.

OpenSpec CLI 2.1.1 initializes this project with the spec-driven schema and
Codex skills. The change passes strict CLI validation. Validation checks document
structure; implementation and live-provider completion require their own evidence.
See [tooling setup](../../../docs/development-tooling.md).
