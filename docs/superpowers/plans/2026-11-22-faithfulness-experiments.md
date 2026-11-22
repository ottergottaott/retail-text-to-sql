# Faithfulness Experiments Implementation Plan

> Execute inline using executing-plans and test-driven-development. Existing authorization covers execution; do not reopen the design approval.

**Goal:** Make faithfulness improvement measurable and reproducible with local Langfuse and a larger English set.
**Architecture:** Offline bounded experiments feed scores and provenance to isolated Langfuse; JSON remains authoritative. Serving behavior changes only after comparison gates.
**Tech Stack:** Existing Python, Ragas 0.4.4, DeepInfra, Langfuse, Docker Compose.
**Spec:** `docs/superpowers/specs/2026-11-22-faithfulness-experiments-design.md`

## Global constraints
English cases; unchanged standard Ragas; no secret values in output; preserve existing data/containers and historical evidence. No Git repository exists here, so save files and hashes rather than fabricate commits. Never claim statistical certainty from the chosen sample count.

## Review focus
Partial scoring, case/split leakage, metric contract drift, invented context/provenance, unbounded paid execution, telemetry that accepts but never persists data.

### Task 1: Local Langfuse and scored ingestion
- [ ] Create `compose.langfuse.yaml`, local credential bootstrap and concise operations instructions. Validate Compose, then launch an isolated project.
- [ ] Add tests first for `retail/experiment_tracking.py`: invalid/missing scores excluded, stable case/run identifiers, metadata export omits answer/rows, synthetic capture explicit.
- [ ] Implement dataset/run/trace/score export; test on controlled transport, then verify a real local scored trace by API readback. Save sanitized evidence.

### Task 2: Dataset and bounded experiment execution
- [ ] Add `evaluation/faithfulness-v2` dataset/manifests with family-separated splits, expected result contracts and provenance.
- [ ] Add failing tests for split validation, bounds, incomplete coverage and paired comparison; implement `retail/faithfulness_experiments.py` and CLI.
- [ ] Preserve standard metric diagnostics, immutable results, prompt/data hashes, per-case checks and resumable bounded batches.
- [ ] Validate all 80 cases offline; freeze v8 baseline and run development batches with real generation/judging.

### Task 3: Measured iterations and acceptance
- [ ] Diagnose unsupported statements; save candidate prompt separately before calls.
- [ ] Compare baseline/candidate, validate the chosen change on untouched validation; if robust, evaluate sealed test once.
- [ ] Retain all failures; promote only when defined gates pass. Otherwise document the failed attempt and continue a justified iteration.
- [ ] Run full pytest and fresh end-to-end smoke; export actual runs to Langfuse and verify stored scores.
- [ ] Ask existing authorized DeepSeek reviewer for bounded evidence audit. Save a concise comparison and remaining limitations.
