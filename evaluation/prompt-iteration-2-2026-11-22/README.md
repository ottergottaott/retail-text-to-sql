# Prompt iteration 2 evidence

- `baseline.txt`, `candidate.txt`, `cases.json`, `protocol.json`, `input-digests.json`: frozen before generation.
- `deepseek-design-review.txt`: actual read-only DeepSeek V4.1 Flash critique from the named BB thread, with its limited evidence boundary.
- `results.json`: paired review-only generation/score report; inspect coverage before comparing means.
- `judge-results.json`: unchanged standard and SQL-aware Ragas judge results.
- `workflow-results.json`: live-model LangGraph actions with actual local fixture SQL, temporary stores and deterministic checks. Not live BigQuery or browser evidence.

Reproduce the review-only experiment from the project root, using a NEW output directory:

```sh
uv run python scripts/evaluate_review_prompts.py --live --env-file .env.live \
  --cases evaluation/prompt-iteration-2-2026-11-22/cases.json \
  --baseline evaluation/prompt-iteration-2-2026-11-22/baseline.txt \
  --candidate evaluation/prompt-iteration-2-2026-11-22/candidate.txt \
  --output-dir /tmp/retail-prompt-iteration2-repeat
```

`--live` permits billed calls; without it inputs/settings are not loaded. This replay is no longer untouched validation. Human review remains pending.
