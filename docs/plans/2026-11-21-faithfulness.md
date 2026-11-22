# Faithfulness repair and remeasurement

User goal: make report faithfulness meaningful and improve actual reports, with
Docker restart and unnecessary containers stopped. Existing framework/provider
choices and autonomous execution remain authorized.

## Diagnosis and approach

The pinned statement diagnostics show two causes: unsupported factual inferences
(e.g. identical observed prices imply no discounts; small samples imply demand)
and a strict SQL-entailment metric scoring proposed actions as historical facts.
Missing report-title metadata also penalized a true save statement. Numeric SQL
oracles cannot detect these report-text problems.

First make a bounded prompt-only comparison using the same four recorded evidence
sets; do not change contexts or judge between baseline and candidate. Strengthen
fact/assumption/proposal boundaries and narrow caveats to what the query supports.
If that is insufficient, introduce explicit report sections and evidence links
rather than adding unbounded agent retries. Keep whole-answer Ragas visible.
A separate factual-claim score must identify its scope and include unsupported
assertions even when placed inside recommendations. Never add report-derived
claims to judge context or remove difficult findings to inflate a score.

## Acceptance

- Preserve original reports, contexts, prompt versions and scores.
- New reports preserve the business answer, limitations and useful action items.
- Facts are entailed by query results, SQL/authorized scope or trusted definitions;
  speculation is explicit and does not sneak in an unsupported premise.
- Deterministic numeric/scoping gates still pass.
- Judge calibration includes supported, numeric contradiction, unsupported cause,
  tiny-sample overclaim, and factual assertions embedded in recommendations.
- Re-run fixed-evidence comparison and fresh live business cases. Publish whole
  report faithfulness separately from any scoped metric, sample counts and judge
  limitations. Human acceptance remains separate.
- Full regression suite, optional tools isolated, bounded paid calls, no raw
  content export into observability, no secrets in artifacts.

## Tasks

1. Restore Docker without removing volumes; inventory and stop unused containers.
2. Run fixed-evidence prompt comparison and inspect statement-level failures.
3. Add any needed output/evaluation contract changes with RED/GREEN tests.
4. Run calibrated, bounded judging and fresh live SQL/report oracles.
5. Verify browser progress/report save/open and publish revised review artifacts.

No model swap or arbitrary metric threshold is assumed to fix grounding. A higher
score on rewritten contexts is not comparable with the original score.

## Implementation decisions and evidence

Prompt-only revision still produced unsupported sample-size claims. Added one
bounded live `review` node before persistence; it shares existing time/context/
model-call budgets. Regression cases cover corrected saved content, failed review
and exhausted review budget. No HTTP retry loop or new service was introduced.
Trusted execution scope is explicit in model context so logical SQL lacking a
product predicate is not misreported as missing authorization.

Fresh v5 revealed incorrect Complete-population counts and zero buckets from
other statuses. v6 explicitly filters the requested population before grouping.
v6 also reproduced blank answers: provider output contained action/format/depth/
title but omitted text. Provider schema now requires text and a nonempty answer;
the application blank guard remains. Original v5/v6 failures remain archived.
The v7 artifact denotes this schema correction using the same v6 system prompt.

Docker recovered without pruning volumes. Thirteen unrelated containers were
stopped. Live WebUI verified visible progress, table, saving and opening that
report from a new chat; evidence is `webui-live-grounded-2026-11-21.json`.

Final comparison, calibration, fresh live coverage and input hashes are generated
by `scripts/summarize_faithfulness.py`. Human acceptance remains separate.

## Final recorded state

167 regression tests and strict OpenSpec passed. The final configured browser
path passed with actual Flash/Pro stage telemetry. Twelve selected Pro-reviewed
reports passed SQL/structure/save checks from thirteen requests: eleven initial
successes, one failed Pro review that saved nothing, and one explicit successful
recheck. Both the original failure and report selection provenance remain.

All twelve selected texts were judged with standard whole-response Ragas and
separate custom SQL-aware entailment. Calibration has three supported cases and
nine negative traps. Scores are advisory, not automatic human acceptance or a
claim that a stronger model universally fixes faithfulness. The morning review
page contains the reports, failed historical rechecks, metrics and verdict inputs.
