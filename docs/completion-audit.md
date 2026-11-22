# Requirement and evidence audit

Historical audit with dated addenda. The current 22 November submission
entry point is the [review summary](review-summary.html); earlier test counts
and operational limitations below describe their recorded runs.

Audited against the original four-page assignment, local source and saved
evidence. Current results below supersede earlier lexical-only snapshots;
the overall live goal is incomplete.

## Current acceptance addendum — 2026-11-21

The [final acceptance guide](final-acceptance.md) and source-linked faithfulness
summary contain current results. A bounded report-review stage and required
answer text schema were added after live runs exposed unsupported statements and
empty model answers. Failed intermediate runs remain available. Whole-answer and
factual-assertion Ragas metrics are reported separately, calibrated with hidden
premise and numeric traps. Live Open WebUI progress/table/save/new-chat opening
passed after Docker recovery; 13 unrelated containers were stopped without data
removal. Optional Langfuse delivery, clean-machine and human acceptance remain
open. Earlier snapshots below retain their original evidence boundaries.

## Earlier verification — 2026-11-21

Full pytest:159 passed; local HTTP/CLI fixture workflow:22 checks passed.
Real DeepInfra structured Gemini chat and1024-dimensional Qwen embeddings were
verified. Expanded retail comparison (98 cases), graded retail challenge
(16 cases) and pinned WikiSQL diagnostic (full2048 corpus,100 query subset)
completed with real embeddings. See [measured results](../evaluation/retrieval-results-2026-11-21.md)
and [verification commands](retrieval-verification.md). These are measurements
on synthetic/unreviewed retail labels, not a relevance release pass.

A real-Gemini/fixture-SQL ablation matched3/3 result oracles in each of
no-retrieval, lexical and hybrid modes. This does not prove RAG adds accuracy or
report faithfulness. SQL boolean predicates and model capability disclosure were
fixed with regression tests. Unsupported functions remain terminal.

Actual Pipe→API→LangGraph→fixture SQL→storage integration passed, including
progress and cross-user report isolation. Current Docker daemon is unavailable;
no new browser/container check is claimed. Earlier fixture browser evidence
remains historical. See [WebUI integration](webui-integration.md).

DeepInfra credential is configured and used privately. The user subsequently completed ADC for `static-bee-277223`; all four live
BigQuery table aggregates passed. Direct Google API and Langfuse export remain
unverified. See [BigQuery connection evidence](bigquery-verification.md). Model
usage tokens are provider-measured; spend is unavailable (`null`). The overall
live MVP goal remains incomplete. Strict OpenSpec syntax validation is distinct
from passing runtime/provider acceptance.

## Assignment boundary

All eight numbered requirements require production design. The mandatory
prototype implements core conversational analysis and reports plus requirements
2, 3, 5 and 7, a CLI, dynamic BigQuery queries, Gemini compatibility and portable
setup. Theoretical Golden Knowledge, learning, evaluation and persona management
still require detailed design; their small implemented demonstrations are chosen
additions. Docker/Open WebUI are additions. Charts/email/web trends are extension
points. The requested public GitHub submission is not authorized for publication
in this session.

## Eight requirements

| Requirement | Evidence inspected | Current conclusion |
| --- | --- | --- |
| 1. Hybrid knowledge plus fresh SQL | `knowledge.py`, `embeddings.py`, knowledge tests, architecture section 1, improvement guide | Version/scope/schema filtering, lexical retrieval, controlled semantic fusion and reviewed publication implemented. Synthetic seeds labeled. Actual Qwen relevance measured on synthetic held-out sets; Gemini consumes retrieved trios in fixture-data ablation. Human usefulness review remains pending. |
| 2. Safety, PII, user product access | `security.py`, `analytics.py`, revocation/source-binding tests, offline SQL/safety cases, API/runtime owner checks, architecture section 2 | Approved projection and trusted product binding exercised locally; raw sensitive columns excluded. Regex PII checks are incomplete by design. Real BQ source binding/count execution verified for all four families; production privacy/IAM/retention controls are documented. |
| 3. Confirmed owned deletion | `store.py`, `api.py`, report tests, HTTP/CLI restart evidence, deployed PostgreSQL lifecycle run, architecture section 3 | Exact target/version/owner/conversation/expiry confirmation, cancellation and replay verified. Two concurrent PostgreSQL confirmations delete once; existing reports preserved. |
| 4. User and system learning | `governance.py`, `admin.py`, governance tests, architecture section 4 and improvement guide | Explicit per-user preferences reach context/rendering; reviewed SQL evaluation blocks bad publication and approved versions affect retrieval. Inferred-preference confirmation/reset and full production release gating remain design only. |
| 5. Resilience and cost limits | `agent.py`, `model.py`, `analytics.py`, budget/repair tests, BQ SDK contract mocks, architecture section 5 | Local bounded repair, empty-result return to planning, dependency failures, row/byte/context/call/time budgets exercised. Real service timeout/rate-limit behavior and natural-language repair quality unverified. |
| 6. Correctness, intent and UX evaluation | `evaluate.py`, SQL/retrieval cases, offline output, evaluation guide, browser evidence, architecture section 6 | 159 pytest cases and22 local HTTP/CLI checks; offline SQL/safety oracles retained. Browser covers progress/table/save/new-chat listing. Superpowers review regressions cover fixture interruption, source-less analytical completion, scoped prior evidence and sensitive-field denial. Real-embedding retail and external subset scores measured; small real-model fixture-SQL ablation passed. Human executive UX and broader follow-ups remain unreviewed. |
| 7. Observability/debugging | `telemetry.py`, agent events, correlation/privacy tests, HTTP/CLI JSONL, architecture section 7 | Local metadata correlations, safe errors, query/config/version references and terminal outcomes verified. Actual DeepInfra token metadata verified; BigQuery job IDs/processed bytes verified; optional Langfuse export unverified. Alerts and sensitive correspondence access/retention are production design. |
| 8. Nondeveloper persona agility | `admin.py`, governance persona test, architecture section 8 | Versioned operator publication applies next turn without redeploy. Nondeveloper editor, preview, RBAC and rollback are explicitly production design, not a finished CEO UI. |

## Other deliverables and capability gates

| Deliverable or invariant | Evidence and remaining work |
| --- | --- |
| Named architecture components, services, compute, communication and storage | `architecture.md` and interactive `architecture.html` cover local and GCP production deployment, focused agent/storage/retrieval/learning/evaluation/security views. Overview/RAG tabs were browser inspected. |
| Detailed rationale, all-eight explanations, errors and extensions | Architecture sections, setup/evaluation/improvement guides. Candidate's actual framework experience paragraph is intentionally missing until the user supplies facts. |
| Dynamic customer/product/time/schema/multi-step analysis and reports with action items | Dynamic query action and safe four-table schema exist; fixtures verify SQL result oracles and report save/open. Real Gemini-to-BigQuery aggregate analysis and explicit follow-up save/list/open passed. Broader follow-up intent and action quality remain human-review gates. |
| CLI and web share one backend policy/agent | CLI container run and browser Pipe run used the same API/PostgreSQL. Pipe has no tools/second agent; observed progress history and persisted final table. |
| Reports survive chat lifetime/restarts | Independent SQL records, local report-lifetime tests, API recreation persistence, new WebUI chat listing. Actual deletion of a WebUI chat was not exercised. |
| Portable, secret-free local setup | Frozen dependency lock, Docker image/Compose, setup/bootstrap scripts; actual local image build and healthy stack. Another clean machine has not been exercised. |
| Genuine Gemini/BigQuery mode | Implemented adapters and explicit fixture/live distinction; no silent fallback. DeepInfra chat/encoder and BigQuery authenticated execution verified; real-model hybrid analysis completed. Report human review and browser live deployment remain gates. |
| OpenSpec/Superpowers tooling | OpenSpec CLI 2.1.1 initialized the project for Codex; retail-mvp passed strict validation. All 15 Superpowers 7.0.2 skills installed into the user's Codex skills directory. These support development and do not prove application correctness. See development-tooling.md. |
| Submission | Source/docs remain local; no public repository published. |

## Remaining review protocol (credentials are now configured)

1. Configure the chosen Gemini model, GCP job project and authentication privately;
   switch to live mode with non-demo application tokens and appropriate scope.
2. Exercise customer, product, time and schema questions, follow-up clarification
   and multi-query analysis. Inspect actual BQ job IDs/bytes and Gemini usage.
3. Compare scoped result sets with independently reviewed reference queries and
   review report claims, caveats and action items against user intent.
4. Review the measured retail labels with an analyst; add independent cases and
   freeze a development set before tuning. Real embeddings already compared.
5. Recheck the release gate and candidate experience statement before submission.

Do not label BigQuery integration verified from fixture evidence. DeepInfra
credentials were configured privately and were used for the recorded real runs.

## After ADC consent — live workflow evidence

Project static-bee-277223, four-table live verifier and real hybrid
Gemini/Qwen→BigQuery→saved-report workflow passed. Explicit follow-up
save/list/open also passed in new conversations. Initial combined-save intent
was missed; prompt retail-v3 explicitly describes the pending-save lifecycle,
and the same live request then saved successfully. Full pytest147 passed.
Portable metadata: evaluation/bigquery-live-workflow-2026-11-21.json.
Temporary test stores were disposed; no reports were added to application state.
Default application remains fixture. Live browser/container configuration,
Langfuse, broad follow-up/report quality and human review remain open gates.
