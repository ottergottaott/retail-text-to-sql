# OpenSpec and Superpowers review

## Scope and process

Reviewed the current MVP against `openspec/changes/retail-mvp/` using OpenSpec CLI
and Superpowers `requesting-code-review`. A separate reviewer examined current
source for product/PII policy, confirmation, deadlines and error handling. There
is no Git repository here, so the review used file paths and current source
rather than a commit range. No credentials or live providers were used.

Reviewer findings were reproduced before edits. `receiving-code-review`,
`systematic-debugging` and `test-driven-development` guided the corrections.
`verification-before-completion` was used for the final evidence. This is the
first application review under these skills, not a claim that earlier work used
TDD or Superpowers retroactively.

## Findings and corrections

| Finding | Root cause and correction | Regression evidence |
| --- | --- | --- |
| P1: fixture query could occupy a worker indefinitely | DuckDB ignored the remaining query deadline. Propagate the remaining budget, refuse expired execution, interrupt a running query on expiry and classify interruption as terminal QueryUnavailable. | Both expired-budget and infinite-recursive-query tests failed first; both passed after the fix. The same two behaviors were verified inside the rebuilt container. |
| P2: source-less model answer was returned as successful analysis | Plan accepted action=answer without any query or prior analysis. Require current query evidence or a scoped persisted prior analysis; withhold unsupported completion and emit MissingQueryEvidence metadata. | Fresh analytical answer test failed first, then passed. Additional cases preserve authorized follow-ups and reject prior analysis after access shrinks. Container check passed. |
| P2: sensitive SQL field entered repair | Generic schema qualification turned email into repairable QueryError. Recognize known sensitive/raw customer fields before qualification and deny them as policy violations. | A scripted email query followed by a safe query previously succeeded; after correction it terminates after the first model call with denied outcome. Container check passed. |

No demonstrated confirmation bypass was found. Production OIDC/IAM, distributed
locking, ingress privacy, migrations and production operations remain explicit
design scope. No new production claim is made from this review.

The answer guard establishes presence and authorization of evidence. It does
not verify every numeric claim or prove that Gemini used the correct analytical
method. Real-model and analyst-reviewed evaluation remain necessary.

## OpenSpec reconciliation

The CLI recognized change `retail-mvp` and its `spec-driven` artifacts. Added
explicit scenarios for unsupported analytical completion, fixture deadline
expiry and terminal sensitive-field denial. Fixed the stale design statement
that vector retrieval was absent. Added a review-corrections task and marked it
complete only after local and container verification. Strict validation was
rerun. Provider tasks remain unchecked and the change is not archived.

## Verification record

- Baseline: 33 tests passed.
- RED: four defect-reproduction tests failed before production edits, including
  a subprocess timeout that kept the nonterminating-query test itself bounded.
- GREEN: 39 total tests passed after corrections, including six review cases.
- Offline evaluation: 21 checks passed.
- Actual local HTTP/CLI workflow: 22 checks passed.
- Rebuilt Docker API: four in-container regression checks passed.
- Running API with PostgreSQL: 15 lifecycle checks passed again; existing reports
  were preserved.

Thread evidence includes `retail-review-baseline.xml`, `retail-review-red.xml`,
`retail-tests.xml`, `retail-review-fixture-green.xml`,
`retail-review-evidence-green.xml`, `retail-review-policy-green.xml`,
`retail-evaluation.json`, `retail-offline-workflow.json`,
`retail-review-deploy.log`, `retail-review-container-checks.json`,
`retail-postgres-lifecycle.json`, `retail-openspec-validation.json` and
`retail-review-findings.json`.
