# Design

## Deployment and responsibilities
Open WebUI hosts a thin Pipe. CLI and Pipe call the same Python API. The API
authenticates requests and resolves product entitlements before invoking Agent.
Agent uses LangGraph to retrieve context, plan, execute bounded tools and produce
an answer. Analytics validates logical SQL and substitutes every physical source
with a trusted product-scoped, PII-minimized BigQuery relation. Generated SQL
never directly selects physical tables. Report operations use transactional
ownership checks independently of model instructions.

Use PostgreSQL for shared application persistence in Docker; SQLite is a local
development option. Store conversations, reports, preferences, published persona
versions, trios, feedback, review decisions and deletion proposals. BigQuery
contains transactions; application persistence does not replicate raw logs.
Structured JSONL is the baseline telemetry sink; Langfuse is optional export.

## Agent
Context → Plan → Query → Plan, terminating at Answer or Clarification. Separate
application commands handle saved reports, preferences and deletion confirmation.
The model may propose deletion targets but cannot manufacture confirmation.
Budgets cap model calls, query attempts, returned rows, bytes and elapsed time.
Fixture queries are interrupted at their remaining deadline. Analytical completion
requires current query evidence or a prior analysis still within the user's scope.
SQL resolution errors permit bounded repair; policy denials terminate. Dependency
errors must not become fictitious analysis. Conversation context is user scoped.

## Knowledge
Versioned Question → SQL → Analyst Report records are authoritative curated
content. Filter published versions, compatible schema and authorized scope first.
Target retrieval combines lexical ranking and vector similarity using reciprocal
rank fusion. Embedding model/version and index generation are recorded. Current
code implements lexical/metadata retrieval, persisted vectors and rank fusion.
With healthy indexed embeddings, lexical candidates also require semantic
support (default floor 0.60; strong semantic-only threshold 0.65). Missing current
vectors cannot bypass this gate; provider failure retains explicitly ungated
lexical fallback. English synthetic live-embedding relevance results and limits
are documented in docs/retrieval-relevance-results.md; these do not establish
production semantic quality or report correctness.
Synthetic seeds are explicitly labeled. Retrieved examples guide method; current
BigQuery results ground findings. Retrieval does not grant execution authority.

## Learning and persona
Persist explicit presentation preferences; proposed inferred preferences need
user confirmation. A turn may override presentation without changing entitlement
or privacy policy. Feedback creates candidates, never automatic trusted examples.
Reviewers sanitize a candidate, run regression and retrieval evaluation, publish
a version and retain rollback references. Persona is versioned presentation data,
loaded at turn start; it cannot redefine tools, access policy or PII restrictions.

## Security and operations
API bearer tokens resolve identities server side. WebUI integration uses a
dedicated adapter secret plus an allowlist mapping trusted WebUI identities.
Production replaces demo tokens with OIDC; bind identity at the ingress boundary.
SQLGlot validates syntax/scopes; trusted executor source substitution enforces
product scope. Production should additionally use authorized views and least
privilege IAM. Pseudonymous customer keys are not anonymity. Names, contacts,
precise coordinates and raw customer identifiers are absent from the analytical
schema. Sanitize user text before model/storage, and reject detectable PII in
results and output. Regex checks supplement source restrictions and are not a
complete PII classifier. WebUI stores messages before backend sanitization:
document this boundary and apply ingress filtering/retention in production.

Reports survive chat deletion. Deletion previews exact IDs and versions, binds
owner/conversation/expiry, and rechecks access in the deletion transaction.
Record metadata correlations, configuration versions, stage duration, outcome,
sanitized error category, retries, query jobs, bytes and measured token usage.
Keep cost estimates explicitly separate from measured quantities. Retention,
access controls, TLS, backups, migrations, alert thresholds and incident recovery
are required production documentation, not implied by the local prototype.

## Extension points
Typed tools can add charts, email or external trends. New outbound actions need
permissions and concrete confirmation; external content remains untrusted.
Deployment overview and focused diagrams belong in the final architecture HTML
and README, with Agent represented as one component in the overview.
