# Iterations

- v8: frozen serving baseline.
- v9: exact grain/current-reference/cost-proxy wording and concise schema-supported checks. Full 40-case development run; not promoted.
- v10: make metric formula, grain, population, authorized scope and applied time filter explicit for a self-contained report. Eight-case development pilot only; judge penalized ambiguous “all available history” as an unverified completeness guarantee.
- v11: same as v10, explicitly distinguishes no date filter from audited historical coverage. Frozen before candidate validation. Development cases are tuning material, including the first eight pilot cases. No candidate validation or reserved-test scores inspected during these changes.

All comparisons use original unchanged SQL contexts and Ragas instructions. Proposed checks can still be penalized by standard faithfulness. Synthetic study, not live BigQuery quality or human acceptance.

- Protocol frozen in protocol.json. Runner resume checks dataset/model/judge/prompt/metric/batch hashes; other fixed settings and implementation hashes are recorded separately.
- Baseline reserved-test execution may run while v11 validation finishes: v11 is frozen and no further tuning is permitted after test exposure. Candidate test execution remains conditional on validation acceptance.
