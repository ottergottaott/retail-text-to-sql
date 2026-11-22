# Narrow save-state prompt promotion: retail-v8

The only serving change is the deferred-save instruction paragraph. See
`promotion.json`, exact frozen inputs/digests, `results.json`, original samples,
unchanged `judge-results.json`, DeepSeek review and implementing-assistant
inspection. Human acceptance remains pending.

`workflow-results.json`: six real Gemini/LangGraph turns with actual fixture SQL
and temporary stores. `ordinary-unsaved-workflow.json`: ordinary analytical turn
creates no report or unrequested disclaimer. `live-api-smoke.json`: actual running
API, live BigQuery, reviewed count answer, one saved test report and accessible HTML.
The initial HTTP-422 smoke harness error is retained separately.

Review-only reproduction (billed calls require --live; use a NEW output directory):

```sh
uv run python scripts/evaluate_review_prompts.py --live --env-file .env.live \
  --cases evaluation/prompt-iteration-3-2026-11-22/cases.json \
  --baseline evaluation/prompt-iteration-3-2026-11-22/baseline.txt \
  --candidate evaluation/prompt-iteration-3-2026-11-22/candidate.txt \
  --output-dir /tmp/retail-prompt-iteration3-repeat
```

The four validation cases were new before the first calls; replays are exposed.
The existing-report-receipt case is a synthetic robustness context, not a real
review routing path: runtime open_report terminates before review.
