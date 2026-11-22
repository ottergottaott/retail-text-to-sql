# Provider verification implementation plan

Continue the approved `retail-mvp` design; do not rebuild completed features.
The five unchecked OpenSpec tasks are live verification gates, not missing core
application scaffolding. User has deferred Gemini credentials. No gcloud command
or local ADC file was found during the initial check on 2026-11-21.

## Deliverables

1. DeepSeek: standalone BigQuery verifier using the existing Analytics executor,
   independent of Gemini startup validation. Explicit live opt-in, bounded SQL
   over all four approved logical tables, metadata-only output, safe missing
   configuration outcome, no credentials or returned customer data in evidence.
   Unit checks must exercise the verifier using controlled adapters; they must
   never be represented as successful live BigQuery verification.
2. Kimi: executable lexical/vector/hybrid retrieval comparison against a separate
   held-out paraphrase and negative set. Use existing Knowledge and embeddings
   contracts; report ranking/relevance and no-result behavior, model/index
   versions and mode. Live embeddings require explicit opt-in. Offline controlled
   vectors verify metrics/mechanics only, never real semantic quality. Use an
   isolated temporary store and preserve existing application state.
3. GLM: read-only review of these two deliverables for policy bypass, misleading
   evidence, budget/config failures, test validity and reproducibility.
4. Orchestrator: inspect artifacts and review, resolve material findings, run the
   combined tests and strict OpenSpec validation. Keep live gates unchecked until
   actual service evidence exists.

## Ownership and acceptance

DeepSeek owns `scripts/verify_bigquery.py`, `tests/test_verify_bigquery.py`, and
`docs/bigquery-verification.md`. Kimi owns `retail/retrieval_evaluation.py`,
`scripts/evaluate_retrieval.py`, `tests/test_retrieval_evaluation.py`,
`evaluation/heldout-retrieval-cases.json`, and `docs/retrieval-verification.md`.
Neither changes core runtime, shared docs, dependencies or OpenSpec artifacts.
Tests must demonstrate failures before implementation. No live provider calls,
secret access, public publishing, Git initialization or Docker volume changes.
The orchestrator integrates documentation after both tasks complete.

Initial role allocation reflects the user's observed speed: DeepSeek for the
bounded executor task, Kimi for the cross-component evaluation task, GLM for
review. Actual call timing and retries are available in BB workflow history.

## Initial integration snapshot — superseded by current verification

BigQuery verifier files are implemented and reviewed. The orchestrator reproduced
seven failing regression cases, then fixed live use of the fixture/empty label
secret, settings loading without live opt-in, local deadline classification and
silently ignored scope flags. The focused verifier suite has 15 passing cases;
the complete pytest suite now has 62 passing cases after retrieval integration.
Strict OpenSpec validation passes.
Default CLI output is retained at
`/Users/user/.bb/thread-storage/thr_jx74y5r9jy/bigquery-default.json`; it records no
queries. Test evidence is at
`/Users/user/.bb/thread-storage/thr_jx74y5r9jy/provider-tests.xml`.

No live provider was called. OpenSpec's five live gates remain unchecked.
Kimi's native mode was changed from Default to Auto while preserving BB
accept-edits; a single-file diagnostic write succeeded. The resumed task
implemented the five owned evaluator files. The orchestrator inspected their
contracts and ran the full suite and default evaluation independently. The
offline report is retained at
`/Users/user/.bb/thread-storage/thr_jx74y5r9jy/retrieval-lexical.json`.
On six synthetic positive cases and three negatives, lexical Recall@2 is 1.0,
MRR is 0.8333, negative false-match rate is 0.6667, and irrelevant-example rate
is 0.5. Marketing conversion and churn negatives return examples; weather does
not. This is a measured baseline, not a relevance quality pass. Vector/hybrid
remain untested without a real embedding provider. The exact cause of the
earlier automatic permission denials was not established.
The initial durable workflow failed because OpenCode did not support inherited
permission mode `auto`; subsequent deliverables used individual BB threads.

Remaining review limitations: injected test callables have no enforced timeout;
direct verifier API callers must supply valid entitlement JSON. These do not
affect CLI configuration, which constructs the entitlement map from product IDs.

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
