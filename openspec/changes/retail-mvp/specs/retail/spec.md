Consolidated scope authority: `docs/acceptance-spec.md` v1.1. Learning and persona
quality gates are design-only; runtime safety, oversight, resilience and
observability are mandatory. Historical product-scoped evidence remains historical.

## ADDED Requirements

### Requirement: Grounded retail analysis
The application SHALL dynamically query the four approved thelook tables through
a product-scoped safe schema and support customer, product and temporal analysis.

#### Scenario: Follow-up analysis
- **WHEN** a user asks a follow-up about a previous metric or time window
- **THEN** the agent preserves relevant context or asks a clarification and reports
  query provenance, definitions, findings and supported action items.

#### Scenario: Missing evidence
- **WHEN** a query returns no rows or an external dependency fails
- **THEN** the response distinguishes absence from failure and invents no results.

#### Scenario: Unsupported analytical completion
- **WHEN** the model proposes an analytical answer without current query evidence
  or a previous analysis that remains authorized
- **THEN** the application withholds that answer and does not record analytical success.

### Requirement: Policy enforcement
The application SHALL resolve identity and brand/CEO scope outside the model,
exclude disallowed PII before model context, and permit only bounded read queries.

#### Scenario: SQL escape attempt
- **WHEN** SQL uses physical names, sensitive fields, scripts, unsupported table
  functions, or unauthorized relations through nested queries or CTEs
- **THEN** execution is denied and raw SQL diagnostics are withheld.

#### Scenario: Two owners
- **WHEN** two users query data or retrieve reports
- **THEN** each can access only their configured products and owned reports.

### Requirement: Durable reports and explicit deletion
Reports SHALL persist independently of chat lifetime. Deletion SHALL require an
exact owned-target preview and explicit confirmation bound to that preview.

#### Scenario: Confirmation and replay
- **WHEN** the user confirms a valid unexpired proposal in its conversation
- **THEN** only its unchanged authorized targets are deleted transactionally;
  replay cannot delete additional reports.

#### Scenario: Cancelled or invalid confirmation
- **WHEN** confirmation is cancelled, expired, cross-user, cross-conversation or
  refers to changed targets
- **THEN** reports remain intact and the actual outcome is reported.

### Requirement: Curated hybrid knowledge
The agent SHALL retrieve permitted published trios as methodological examples,
and ground current conclusions in actual query results.

#### Scenario: Relevant paraphrase
- **WHEN** a question paraphrases an analyst example without exact keywords
- **THEN** semantic retrieval can contribute candidates, combined with lexical
  ranking; irrelevant questions may return no examples.

#### Scenario: Reviewed update
- **WHEN** feedback suggests a new analytical approach
- **THEN** the production design requires sanitization and recorded passing automatic
  evaluation gates, with human review for exceptions, with version/provenance and rollback available.

#### Scenario: Response-linked WebUI feedback
- **WHEN** a signed-in user submits feedback from an assistant response
- **THEN** the backend SHALL resolve its trusted chat/message snapshot, enforce
  ownership and current scope, reject a stale response revision and store
  sanitized feedback as unreviewed without publishing knowledge.

#### Scenario: Lexical overlap without semantic support
- **WHEN** compatible indexed embeddings are available but a lexical candidate
  fails the configured semantic relevance floor
- **THEN** it SHALL NOT enter hybrid results solely through keyword overlap;
  telemetry SHALL record the relevance gate and index coverage.

#### Scenario: Embedding provider unavailable
- **WHEN** query embedding fails
- **THEN** bounded lexical fallback MAY remain available and telemetry SHALL
  explicitly mark the relevance gate unavailable rather than claim gated retrieval.

### Requirement: Personalization and configurable persona
Presentation preferences SHALL persist per user; the design SHALL apply learned
preferences automatically with user override/reset; persona SHALL be versioned and
editable without application redeployment, subordinate to security policy.

#### Scenario: Preference isolation
- **WHEN** Alice chooses concise tables and Bob chooses detailed bullets
- **THEN** later turns respect each preference without mixing their histories.

#### Scenario: Explicit preference controls
- **WHEN** a signed-in user saves or resets format/depth in My preferences
- **THEN** the new per-user version SHALL persist across new chats and restarts;
  reset SHALL save tables/standard and saved reports SHALL remain snapshots.

### Requirement: Bounded and observable execution
Each turn SHALL have finite model/query/time/byte/row budgets and privacy-safe
correlation between request, conversation, turn, model call and query job.

#### Scenario: Repair budget
- **WHEN** SQL is repairably invalid
- **THEN** the model receives a sanitized diagnostic and may retry within the
  remaining budget; policy denial is never retried as an execution workaround.

#### Scenario: Fixture query exhausts its deadline
- **WHEN** a local fixture query would run beyond its remaining execution budget
- **THEN** the application interrupts it and returns a terminal budget failure
  instead of leaving an API worker occupied indefinitely.

#### Scenario: Sensitive field request
- **WHEN** generated SQL references a known sensitive customer field such as email
- **THEN** the application denies the operation without another model call for SQL repair.

### Requirement: Reproducible delivery and evaluation
CLI and Open WebUI SHALL use the same backend. Docker setup, credentials,
architecture covering all eight requirements, evaluation and limitations SHALL
be documented. Evidence SHALL distinguish fixtures, live services and untested
claims. No external publication occurs without authorization.

#### Scenario: Reviewer setup
- **WHEN** a reviewer follows the documented clean setup with valid credentials
- **THEN** they can ask a question, follow up, save/list/open a report, preview and
  confirm deletion, and inspect a correlated trace.

### Requirement: Interactive report presentation
Open WebUI SHALL offer deterministic HTML Artifacts and embedded report previews
for successful completed analyses and accessible saved reports. HTML SHALL preserve
the original findings, limitations and evidence, with explicit fixture/live labels.
Charts SHALL only describe supported returned data without inventing totals.

#### Scenario: Open a saved report from another chat
- **WHEN** the owner opens an authorized saved report in a new WebUI chat
- **THEN** the report renders from persistent data as an Artifact and embedded
  preview without rerunning its SQL or report-writing model calls.

#### Scenario: HTML access and presentation failure
- **WHEN** HTML is requested by another user or after product access is revoked
- **THEN** the API denies access using the same rules as its JSON report endpoint.
- **WHEN** optional HTML or embed delivery fails after a report has been saved
- **THEN** the successful backend operation is not retried or hidden as a failed save.

#### Scenario: Untrusted report markup
- **WHEN** model text, SQL, rows or metadata contain HTML or code-fence delimiters
- **THEN** these remain inert data; the full report runs no scripts and the preview
  permits only its fixed hash-authorized iframe height bridge.

### Requirement: Authenticated report library navigation
The optional WebUI extension SHALL provide a persistent Reports entry and a native
message Action that opens a searchable saved-report library without invoking an
LLM or executing analytical SQL. The read-only proxy SHALL derive identity from a
verified WebUI session and apply backend owner and current product-scope checks.

#### Scenario: Open a saved report from the library
- **WHEN** an authenticated user selects a report in their library
- **THEN** the backend returns only an owned, currently accessible report
- **AND** the UI displays it in a scriptless sandbox and supports a separate browser tab
- **AND** no credentials are included in report URLs or downloaded HTML

#### Scenario: Refresh after access changes
- **WHEN** the user refreshes the library or opens a report after access is revoked
- **THEN** current backend permissions govern the new read
- **AND** inaccessible content is not fetched anew
- **AND** previously delivered snapshots remain subject to documented retention limits
