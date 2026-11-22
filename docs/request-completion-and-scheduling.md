# Repeatable analytics and request completion: current state and next work

## Two different jobs

**Knowledge indexing (implemented):** `retail-admin index` embeds published Golden
Knowledge through the configured provider. Its document IDs bind content, trio
version, model and embedding dimensions/instruction; it can be rerun. Call after
reviewed publication, from CI or an operator cron job. Avoid embedding every record
on every user turn. A standalone indexing microservice is not currently necessary.
Before scheduling unattended indexing, add an explicit wall-time/call budget,
summary/alert, concurrency lock and retry policy with bounded attempts.

**Repeatable business analysis (not implemented):** persist an AnalysisDefinition,
not a raw unvalidated SQL string or chat snapshot. Proposed fields:

- owner, title, original question and structured metric/dimensions/filters;
- period policy: fixed dates or relative period, timezone, closed vs incomplete;
- presentation preference snapshot and schema/logic version;
- schedule/timezone, enabled state and execution budgets;
- explicit execution mode: replan from intent or rerun reviewed query template.

Each scheduled Run stores definition/version, resolved period, current principal
scope, status, trace/evidence/job IDs and immutable report ID. Recheck the owner's
current account and product permissions at execution and before persistence. A
scheduler enqueues the same application workflow, using a dedupe key such as
(definition_id, version, scheduled_at). No credentials in job payloads. Start with
a CLI/job runner invoked by cron; add queue workers only when concurrency/retries
justify them. Handle DST, overlapping runs, downtime catch-up, cancellation,
provider budget, schema changes and data freshness explicitly. Scheduling or
notifications are not being added by the report-library change.

## Current completion path (verified from retail/agent.py)

- Empty answers and answers without query evidence/prior authorized analysis fail.
- Live drafts go through one bounded model review against original tool evidence.
- Review must return a nonempty answer, within call/time/context budgets.
- Generated decision and final answer pass `safe_output` PII checks.
- Only completed analyses become last_analysis or auto-saved reports.
- Saved report provenance, product scope and owner survive independently of chat.
- Final response has outcome, trace_id, evidence and management/save ID.

These are mechanics, not proof that every analytical claim is factually grounded.
The current review is free-text revision; it has no structured claim-level verdict.

## Missing completion gates (proposed, not implemented)

1. **Request coverage:** structured requested metric, grain, period, comparison,
   output and save intent; compare with executed evidence and final response.
   A clarification is not a completed analysis; disclose unfulfilled save/export.
2. **Numerical grounding:** claims cite query_id + row/column or explicit computed
   formula; deterministic checks for values, percentages, totals and denominators.
   Allow rounding tolerance and supported derived values; never equate every
   number in text with a raw cell (dates/count limits are different kinds).
3. **Analytical validity:** empty/truncated results, tiny sample, incomplete period,
   timezone, duplicate grain, missing baseline/denominator and freshness. Some can
   be derived from structured query/evidence metadata; others need domain review.
4. **Recommendation grounding:** label unsupported causal explanations as hypotheses;
   separate measured findings, limitations and proposed action items.
5. **Structured review outcome:** accepted/revised/unsupported with issue categories,
   claim evidence references and coverage. A review that merely returned text is
   insufficient. Review cannot invent query results or expand access.
6. **Commit integrity:** recheck scope before save, idempotency keys for retried saves,
   transactionally associate report + run + outcome where possible. A rendering or
   client disconnect must not imply a save failed or trigger a second mutation.
7. **Completion telemetry:** requested/performed actions, validation verdicts,
   latency/usage and persistence outcome; available measured usage separate from
   estimates. Do not log raw PII or secrets.

Priority before assessment: request coverage + structured review + deterministic
checks on numbers for the supported business scenarios. Keep Ragas faithfulness
and retrieval metrics as offline regression evidence; they are not guaranteed
per-request correctness or substitutes for authorization.
