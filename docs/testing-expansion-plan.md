# Golden knowledge and provider testing expansion

## Approved direction

Continue the existing MVP. Expand synthetic demonstration knowledge across
retail analytical intents and start reproducible evaluation. Keep direct Google
Gemini support for assignment reviewers; add DeepInfra as a selectable provider
for Gemini chat and Qwen3-Embedding-8B. Existing security, source binding,
ownership and publication controls remain authoritative.

## Work and ownership

1. Kimi: create `retail/data/golden-trios.json`,
   `evaluation/expanded-retrieval-cases.json`, and `docs/golden-dataset.md`.
   Add about 20 synthetic methodology trios using only the safe schema, plus
   disjoint English/Russian paraphrases and negative/clarification cases.
   No invented measured outcomes or historical-human provenance.
2. DeepSeek: implement `retail/deepinfra.py`, `tests/test_deepinfra.py`, and
   `docs/deepinfra.md`. Existing httpx only, explicit finite timeouts, no retries,
   sanitized failures, Decision schema validation, real provider usage fields,
   robust embedding batch/index/vector validation. No live calls or secrets.
3. Parent: inspect and integrate external adapters with config/agent/admin and
   evaluation CLI; add tests first. Add a bundled synthetic-corpus loader and
   validate new SQL against the approved schema. Preserve original seed IDs,
   publication version behavior and the small baseline evaluation.
4. Parent: run full tests, expanded offline retrieval and scoped fixture SQL
   checks, then live providers only when authentication is available. Record
   measured versus untested evidence explicitly. Do not close live gates from
   fixture tests.

## Acceptance and remaining inputs

Default evaluation remains offline and does not load credentials. Expanded
evaluation uses an isolated store; application data and Docker volumes remain
intact. Changing embedding provider/model changes index identity and requires
reindexing. Existing Google paths continue working. Failed live dependencies
never produce fabricated data or successful fallback quality claims.

Initial state: Google OAuth pending and no ADC/project. DeepInfra was later
configured privately; current verification below supersedes that initial state.
No Git initialization, public publication or infrastructure deletion.

## Current verification — 2026-11-21

Full pytest:147 passed; local HTTP/CLI fixture workflow:22 checks passed.
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

DeepInfra credential is configured and used privately. BigQuery project and ADC
are still absent; direct Google API and Langfuse export are unverified. Model
usage tokens are provider-measured; spend is unavailable (`null`). The overall
live MVP goal remains incomplete. Strict OpenSpec syntax validation is distinct
from passing runtime/provider acceptance.


## Final review disposition

The isolated evaluator now initializes built-in seeds before importing additional
corpus records, so ID collisions cannot replace seed content. A regression test
reproduced the old failure before the ordering fix. The bundled corpus has no
collisions. Parent independently validated all 98 IDs, exact relevance references
and two positive paraphrases per language per intent.

Duplicate relevance labels are now rejected before indexing; missing or
wrong-version references score misses and produce label warnings. The expanded
corpus and labels were structurally audited. CLI missing/invalid input now
produces an argparse error instead of an unhandled input traceback.

The current retail CLI has no aggregate paid-call ceiling. Use the checked
98-case dataset deliberately; do not pass arbitrarily large files with --live.
WikiSQL prints full-corpus+query call estimates before live calls and validates
adapter version first. The chat CLI150-second timeout may still be shorter
than a deliberately increased server budget. Empty Google embedding-model
configuration retains lexical-only behavior; use explicit provider=none for
that choice. These remaining small limitations were not expanded into unrelated
runtime changes in this evaluation task.
