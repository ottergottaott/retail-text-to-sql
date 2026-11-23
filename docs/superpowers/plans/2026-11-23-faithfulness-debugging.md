# Faithfulness debugging implementation plan

> **For agentic workers:** Use executing-plans to implement these tasks sequentially with TDD.

**Goal:** improve report grounding with a complete paired evaluation, preserving safety, exact tables and useful proposed checks.

**Architecture:** keep Ragas statement extraction/NLI unchanged. Add an explicitly versioned judge-evidence option containing the existing SQL/result/scope and supplied logical schema only. Pin generation model and judge independently; bounded concurrent judging creates separate metric instances per case. Keep the serving prompt unchanged until a candidate passes evaluation.

**Tech Stack:** existing Python, pytest, Ragas 0.4.4, OpenAI-compatible gateway.

**Spec:** user-approved five-step improvement approach in this conversation.

## Global constraints

- English artifacts; no secrets or real PII in evidence.
- No answer/draft, retrieval examples or grading instructions may become judge evidence.
- Preserve full-response standard Ragas and separately named SQL-aware metric.
- A context-contract change requires both variants to be scored anew; historical means are not a paired control.
- Do not read reserved test cases during tuning. Existing validation has been exposed; disclose that.
- No incomplete run may pass comparison. Retain failures, timeouts and provider budgets.

## Hypotheses from recorded diagnostics

1. Missing logical schema explains some rejected schema-bound assertions; test by changing evidence only, not answers or metric prompts.
2. Repetitive, interpretive limitations and 3–4 proposed checks introduce unsupported claims; test a concise candidate against frozen v10 with identical judge/evidence.
3. Sequential 60-second metric calls exhaust the run deadline; use isolated concurrent case scoring without hidden retries or increased per-batch HTTP ceilings.

## Review focus

- Evidence includes a poisoned draft/history: exclude it completely.
- Changed judge/evidence on resume: refuse reuse through identity hashes.
- Concurrent case diagnostics/call counts: independent instances and exact aggregate budgets.
- Both runs stop on the same subset: comparison must fail coverage gates.
- Candidate omits tables/limitations/recommendations: deterministic acceptance must fail.

## Task 1: Reproducible evaluation plumbing

- [x] Add failing tests for schema-only evidence, explicit judge selection, isolated concurrent budgets and incomplete comparison refusal.
- [x] Implement `judge_contexts`, runner options and comparison identity/coverage checks.
- [x] Run focused tests, then complete local regression suite: 307 passed; regression.xml retained.

## Task 2: Candidate and controlled live experiment

- [x] Freeze current SYSTEM as baseline; prepare a candidate with exact observed counts, bounded wording and 1–2 useful analytical next-check questions. Candidate authored through OpenCode `alibaba-cn/deepseek-v4.1-flash`; serving unchanged.
- [x] Save protocol, input hashes, model/judge and paid-call ceilings before calls.
- [x] Evaluate development families first. Inspect per-claim differences; never relabel this as held-out validation.
- [x] Freeze the selected candidate, then evaluate the complete validation set with identical generator/judge/context.
- [x] Record coverage, means, paired family uncertainty and deterministic checks. Promote only if evidence supports improvement without factual/task regressions.

## Provider observations

The initial Hydrogen/Flash pilot completed both metrics for only 2/10 cases;
HTTP 429/503 errors prevented a paired comparison. It is retained as incomplete.
A subsequent tiny probe returned Hydrogen HTTP 502 and Flash HTTP 200. A new,
separate Flash/Flash pilot therefore uses identical generation/judge models for
both variants and serial judge calls. This is not comparable to historical
Hydrogen means. No provider errors are excluded from recorded coverage.

## Final result

Candidate v2: standard Ragas 0.718 on all 20 validation cases and 0.752 on all
20 reserved test cases. Tables/structure: 20/20 each. Validation baseline 0.683;
paired 95% family-bootstrap change interval [-0.012, 0.084] includes zero.
Released by explicit user-authorized decision, not the stricter automatic
statistical gate. No statistically reliable improvement or live SQL accuracy
claim. Serving: retail-v11-grounded-reports. See final-metrics.json and promotion.json.
