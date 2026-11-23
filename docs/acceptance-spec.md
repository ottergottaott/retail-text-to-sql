# Consolidated acceptance specification

Version: 1.1, 2026-11-22. Status: client clarifications complete; implementation alignment pending.

## Sources and precedence

- A: original **AI Technical Assignment — Retail Company**, requirements 1–8,
  Deliverables and Expected Agent Capabilities, supplied PDF.
- C1: client response at 18:17 in the supplied Slack transcript, 2026-11-22.
- C2: client response at 18:26 in the same transcript.
- C3: Roi's direct follow-up supplied in chat: learning takes effect automatically;
  no specific tone gate criteria; cohort assumptions are at developer discretion.
- The supplied transcript is `Pasted-text.txt`; it is private source material,
  not a submission artifact. Client clarifications refine A. C2 explicitly
  preserves A's distinction between working prototype and design-only features.
- Existing code, old OpenSpec requirements and prior demos do not override these
  sources. This document is the consolidated requirements baseline; its existence
  does not establish implementation acceptance.
- Project defaults below are engineering decisions, not confirmed client answers.
  Future client answers require an explicit versioned change to this baseline.

## Delivery scope

The submission must contain a public GitHub repository with source, architecture
diagram, detailed technical explanation, setup instructions and example run.
The HLD must describe services, compute, storage, communication, data flow,
framework/model choices and experience, extensibility, and every requirement A1–A8.

The working prototype must provide CLI chat, real dynamic BigQuery execution
against `bigquery-public-data.thelook_ecommerce` (`orders`, `order_items`,
`products`, `users`), conversational follow-ups, multi-step analysis and reports
with supported insights/action items. It must support customer, product and time
analysis, and explain available data/schema. Google Gemini with reviewer-supplied
credentials must work. Open WebUI is an existing additional interface.

Mandatory implemented requirements: safety/PII/access, destructive-operation
confirmation, resilience and observability. Continuous improvement, Golden Bucket
updates and persona quality gates are design scope; additional implementations
are welcome but are not prerequisites for acceptance. A bounded automatic worker
and CEO tone editor are now implemented; see [workflow](improvement.md). [A Deliverables 3; C2.1]

## Mandatory runtime acceptance

### SEC-01 — Brand authorization [A2; C1.1, C1.3]

- Identity, role and entitlements are resolved in trusted code, outside the LLM.
- A static config or access table maps managers to one or more brands.
- Managers can analyze only their brands; CEO can analyze all brands.
- Products, items, orders, customer populations, spend, churn and rankings must
  consistently use the authorized brand scope. A customer's purchases at other
  brands must not influence a manager's calculations.
- New products in an authorized brand must inherit access without editing a
  manually enumerated product-ID list. Missing/invalid permissions fail closed.
- CEO access does not bypass privacy controls. [C2.2]
- Tests: two managers, overlapping brands, cross-brand customers, denied brand,
  CEO, newly added product and invalid identity/config.

### SEC-02 — PII excluded before model calls [A2; C1.2; C2.2]

- Never expose first/last names, email, street address, postal code, exact
  coordinates or IP addresses in results or model context.
- Trusted SQL projections/masking must remove restricted raw fields before query
  results reach any model. Output redaction alone is insufficient.
- Stable opaque/pseudonymous customer keys are permitted. Raw customer IDs are
  not a substitute for pseudonyms. Secrets/salts remain outside model context.
- Cover query results, history, retrieval examples, reports, diagnostics and
  telemetry. Test model-boundary payloads, not only rendered answers.
- Project default: sanitize user-supplied PII before forwarding prompts/history;
  block inputs that cannot be safely transformed. This extends the dataset rule.
- Document IP addresses explicitly as PII in the HLD.

### SEC-03 — Demographics only in safe aggregates [C1.2; C2.2]

- City, state, country, age, gender and traffic source are permitted only in
  aggregate analysis; do not expose individual demographic rows.
- Block individual-customer listings filtered by age; apply the same conservative
  rule to other demographic predicates, or offer a safe aggregate alternative.
- Enforce a configurable minimum demographic cohort in trusted code, default 5.
- SQL policy must cover joins, CTEs, subqueries, aliases and window functions;
  an aggregate in SQL alone does not establish privacy safety.
- Project default under C3's delegated discretion: count distinct underlying customers per released
  group, not item/order rows. Joining five items from one customer does not pass.
- Project default under C3's delegated discretion: omit totals/comparisons in the same answer when
  they directly reconstruct a suppressed group; otherwise refuse that shape.
- Cross-question inference protection is explicitly outside prototype scope;
  describe the risk and production mitigation in the HLD. [C2.2]
- Tests: cohorts 4/5, duplicates/fan-out, customer-key grouping, demographic
  filtering in nested queries, aggregate fallback and CEO privacy.

### SEC-04 — Read-only bounded SQL and analytical-only agent [A2, A5]

- Parse/validate SQL and bind approved logical relations to trusted scoped
  sources. Reject writes, scripts and unauthorized physical-source access.
- Use documented least-privilege GCP access; bound rows, bytes, query/model calls
  and execution time. A LIMIT alone is not a BigQuery scan-cost control.
- Reject malicious/non-analytical instructions; retrieved material cannot
  override security. Failed policy checks do not trigger access-bypass repairs.

### ANA-01 — Explicit, overridable definitions [C1.3; C2.3]

- State analytical definitions and relevant time boundaries in the answer.
- Users may override analytical definitions per question (e.g. churn window).
- Org defaults, including privacy thresholds, belong to data/admin operators;
  configuration is sufficient. Ordinary users cannot lower privacy thresholds.
- Project defaults: revenue = sum of sale_price for Complete items, excluding
  cancelled/returned and other non-completed statuses; churn = previously
  purchasing customers with no qualifying purchase in the last 90 days, using
  an explicit as-of date and eligible-population denominator. Spend denominators
  and order/item/customer grain must be explicit.
- These defaults are engineering choices within the client's examples, not
  company-wide definitions. All manager calculations remain brand-scoped.
- No claims about causality, historical discounts or net profit without evidence.

### REP-01 — Owned durable reports and confirmed deletion [A3]

- Save/list/open reports with owner and current-scope enforcement.
- Support deletion by matching report content (e.g. Client X) and conversation.
- Preview exact owned targets; require explicit confirmation bound to user,
  target set and conversation. Cancel/expiry/replay/changed targets cannot delete.
- Users can delete only their own reports; CEO all-brand access does not grant
  other users' report ownership. This is the conservative reading of A3.
- Save/delete success claims require actual persistence receipts.

### RES-01 — Bounded repair and understandable failure [A5]

- Detect syntax/schema errors and empty returns; attempt bounded safe correction
  or diagnostic refinement before giving up. An empty result may be genuine;
  never silently broaden authorization or change the user's analytical intent.
- Handle timeouts, provider/BigQuery outages and budget exhaustion without UI
  crashes or fabricated answers. Report incomplete work truthfully.
- Tests: syntax repair, genuine empty result, policy denial, dependency failure,
  budget timeout and save failures across CLI/API; exercise WebUI integration.

### OBS-01 — Privacy-safe debugging [A7]

- Correlate request, conversation, turn, model/tool calls, query jobs and outcomes.
- Track latency, success/failure categories, bounded-call usage, repair/fallback,
  retrieval behavior, BigQuery bytes and token/cost availability.
- Do not export PII/secrets; document what operators can inspect to diagnose a
  failure. Langfuse is an implementation option, not a named client requirement.
- Local telemetry must work without an external observability account.

### RUN-01 — Reproducible external-credential setup [A Deliverables 4–6; C1.6]

- CLI and documented setup work on another machine with externally supplied
  Gemini key, Google credentials and execution project. No client credentials
  will be provided to the developer; no developer secrets enter Git or images.
- Provide .env.example, credential instructions and example conversation.
- Distinguish fixture runs from live Gemini/BigQuery evidence. Docker is optional
  in A; retain the existing one-command launcher as delivery convenience.

## Required design coverage

### DES-01 — Golden Knowledge and scalable system improvement [A1, A4b; C1.4–5]

- Define a versioned synthetic Question → SQL → Analyst Report format and seed
  a small clearly labelled set. Explain query-time relevant-example retrieval.
- Describe ingestion, privacy/access tagging, validation, deduplication,
  evaluation, publication, rollback and stale-example handling.
- Human approval must not be the only scalable path. Proposed default:
  automated deterministic/security/evaluation gates publish low-risk validated
  examples; ambiguous/high-risk candidates go to an exception queue.
- Retrieval supplies methodology, not current factual evidence. Enforce current
  brand/access scope before examples reach the model.

### DES-02 — Personal preference learning [A4a; C1.7]

- Remember format/depth across sessions and learn from interaction over time.
- Personal preferences layer on org defaults and never override privacy or an
  explicit current instruction. Describe persistence, isolation and reset.
- Learned preferences take effect automatically without a confirmation step.
  Explicit current instructions take precedence over inferred preferences;
  users can inspect, override and reset stored preferences. [C3; controls are
  project design choices]
- Automatic learning does not authorize changes to access, privacy thresholds or
  admin-owned business defaults. Scalable example promotion still passes the
  automated validation/evaluation gates described in DES-01.

### DES-03 — Nondeveloper persona updates [A8; C1.5, C1.7]

- CEO can update shared report tone without code edits or redeployment.
- Version, evaluate and automatically activate a passing candidate with no manual
  approval step; keep the previous version on failure and support rollback.
- Project gate criteria (C3 specifies no additional criteria): factual preservation, privacy, analytical
  instruction compliance and requested tone adherence on a fixed regression set.
- Implemented authorization: configured CEO edits tone; data/admin owns analytical and
  privacy defaults. These are distinct permissions.

### DES-04 — Evaluation, UX and extensibility [A6; A task/deliverables]

- Explain deterministic SQL/result oracles, retrieval metrics, groundedness judge
  contracts, safety regressions, UX checks, dataset provenance and CI gates.
- Never combine unlike metrics into an overall accuracy score. Report coverage,
  failures, retries and live/synthetic boundaries, including human-review status.
- Describe extension points for charts, email, external trends and dashboards;
  those additional integrations are not mandatory working features.
- Explain deployment/service/storage choices, failure modes, safe updates and
  production mitigations for cross-query inference and stronger privacy controls.

## Initial implementation gap register

This is a targeted source inspection, not a complete runtime audit or test run.

- G1, blocking: `Principal`, `principal_for`, Settings and BigQuery bindings use
  static product-ID lists; no manager-brand/CEO model in the inspected path.
- G2, blocking: the logical users relation exposes customer_key alongside state,
  country and age_band; SQL validation lacks an aggregate-only demographic rule
  and a minimum-cohort policy. Pseudonymization does not resolve this gap.
- G3, investigate: verify every prompt/history/retrieval/log boundary for PII.
  Regex redaction is not proof that names/addresses can never reach a model.
- G4, investigate: trace analytical overrides and explicit definition disclosure;
  no churn/cohort configuration is present in inspected Settings.
- G5, documentation conflict: older OpenSpec requires human reviewer approval
  for every knowledge publication. Revise design for scalable automatic gates;
  existing optional manual tooling may remain, but must not define the only path.
- G6, verify: preserve existing confirmation, SQL guardrails, repair, telemetry,
  report UI, CLI and Docker work; rerun relevant gates after authorization changes.

## Completion evidence and order

1. Use this baseline, keeping delegated engineering defaults distinct from
   explicit client requirements. No remaining client clarification blocks work.
2. Trace each mandatory ID to code and meaningful tests; implement G1/G2 first,
   then complete boundary/definition checks and reconcile design documents.
3. Run deterministic suite and fixture end-to-end acceptance. Do not treat old
   product-scoped evidence as proof of new brand/cohort behavior.
4. Live Gemini acceptance waits for the user-provided key. DeepInfra calls are
   disabled for this finishing phase; independent development-model review is
   separate from the client application's Gemini/BigQuery acceptance.
5. Update HLD, setup and submission summary with measured results and explicit
   untested limits. Acceptance requires evidence, not this document's existence.
