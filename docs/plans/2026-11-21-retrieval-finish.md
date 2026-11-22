# Retrieval evaluation completion

Continue the approved MVP locally; no Git, publication or destructive operations.
Use executing-plans and TDD. Credentials stay private; fixture and live evidence
remain distinct. Existing Open WebUI Pipe is the UI integration, not a new agent.

## Tasks

1. Add independently checked binary/graded ranking metrics at k=1/2/5, preserving
   legacy @2 fields. Include RR/MRR, precision, recall, nDCG, p50/p95 and language
   slices; no-match cases scored separately. Deduplicate exact references and
   report unknown labels. Write failing tests before code, then run full suite.
2. Add close retail relevance cases and an isolated, bounded WikiSQL diagnostic
   using external corpus/query/qrels files. Reuse metric functions, never import
   external SQL into trusted knowledge. Keep its scores separate. Run offline
   lexical/BM25 diagnostics and live selected embeddings when available.
3. Run real DeepInfra smoke and retail comparison. Test the existing API/Pipe
   contracts and workflow; document UI connection and remaining credentials.
   BigQuery needs ADC/project. Docker must be running for a browser stack check.
4. Review the changed files, run full pytest, offline workflow and strict
   OpenSpec validation; persist machine-readable evidence and a concise status.

## Ledger

- Initial readiness: DeepInfra credential present (value not inspected), ADC and
  project absent, Docker daemon unavailable. Existing adapters/Pipe inspected.
- Ruling: preserve the original @2 metric fields while adding explicit multi-k
  fields and rank depth, so previous scripts remain usable. New comparisons
  use the same expanded rank depth for all evaluated modes.

- Task1 complete: shared binary/graded multi-k metrics, slices, Unicode BM25
  baseline and independently checked tests; old@2 fields preserved.
- Task2 complete: real Qwen runs on expanded/challenge retail and pinned WikiSQL
  subset. No threshold tuning; measurements and source digests saved in
  evaluation/retrieval-results-2026-11-21.json and companion Markdown.
- Ruling: WikiSQL preserves question+table context and SQL text; it is an
  isolated retrieval diagnostic, not production SQL or a full benchmark score.
- Ruling: real-model ablation explicitly injects fixture Analytics; it cannot
  establish BigQuery readiness. Initial failures remain saved. Three query
  oracles pass in each mode after capability disclosure and boolean AST fix.
  Monthly prompt changed to start-of-month date; no causal before/after claim.
- Regression cycle: six new failing cases reproduced boolean/capability and
  external version/call-estimate defects. Predicate expectations corrected from
  mistaken monthly values to hand-derived product totals70/140. All tests green.
- Task3 complete: actual Pipe/API/agent/storage ASGI test and local HTTP/CLI22
  checks. Setup/WebUI docs cover same-DB indexing and container credentials.
  Docker currently unavailable; browser rerun and live BigQuery remain gates.
- Reviewer findings: one final review from GLM received; no repeat requested.
  Parent inspected new ablation. Missing adapter version and pre-call estimate
  fixed; redundant available_queries simplified. Remaining operator caveats
  documented without expanding into unrelated runtime work.
- Task4 verification: full pytest147 passed; local HTTP/CLI22 checks passed.
  Strict OpenSpec validation passed after the final documentation update.
