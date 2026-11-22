# Faithfulness experiments

## Local dashboard

Langfuse runs independently from the retail application at **http://127.0.0.1:3001**.
Use the numeric loopback address: on this machine `localhost:3001` can resolve to an unrelated IPv6 listener.

Login: `reviewer@retail.local`. The generated password is `LF_LOGIN_PASSWORD` in the private file `.local/langfuse/.env`; do not include that file in the submission or print its contents in logs.

```sh
.venv/bin/python scripts/bootstrap_langfuse.py
docker compose --env-file .local/langfuse/.env -f compose.langfuse.yaml up -d
```

Langfuse web/worker are pinned to 4.83.0 and ClickHouse to its matching official Compose version, 26.3.62.3. The dashboard uses isolated persistent volumes. Stop it with the same Compose command followed by `stop`; do not use `down -v` if you want to retain experiments. The optional AI Gateway is not deployed. This is a development deployment, without a production backup/availability claim.

## What is measured

- `faithfulness`: unchanged Ragas 0.4.4 whole-response metric. Statement diagnostics observe its existing NLI call without changing prompts, statements or score calculation.
- `sql_factual_faithfulness`: the separately named existing SQL/provenance-aware contract. It is not standard faithfulness and not an accuracy percentage.
- Deterministic table/structure checks: exact expected rows, aliases and rounded numeric values, required limitations/action sections, and a guard against fabricated save receipts. These are coverage checks, not a complete semantic oracle.
- Case coverage, generation failures/rechecks, latency and provider-reported tokens. Cost remains unknown unless the provider reports it.

The historical standard score 0.534 belongs to retail-v7 and a different live evidence set. New synthetic v8/v9 experiments must not be presented as improvement from that number.

## Dataset

`evaluation/faithfulness-v2/manifest.json` pins 80 English synthetic cases: 40 development, 20 validation, 20 reserved test. Forty task groups each have two product-scope variants. This is **not 80 independent observations**. SQL is validated and executed against the existing deterministic DuckDB fixture, not BigQuery. Scope variants remain in the same split; bootstrap comparisons resample task groups. Related SQL skills still occur across splits. The author created all tasks, so the reserved test is not an independent client assessment.

Existing exposed report cases remain regression material. Human relevance and business review are pending. Review-stage experiments do not test retrieval, planner routing, authorization implementation or live SQL execution.

## Run and resume

```sh
.venv/bin/python scripts/run_faithfulness_experiment.py --live \
  --cases evaluation/faithfulness-v2/development.json \
  --prompt evaluation/faithfulness-v2/baseline-v8.txt \
  --output-dir evaluation/faithfulness-v2/runs/baseline-development
```

Without `--live`, the command reads no provider settings or case contents. With it, the command prints its paid-call ceilings. Each batch contains at most eight cases; generation concurrency is two. Model attempts retain the serving adapter's 30-second bound; judge calls are bounded per batch and by the invocation deadline. Resume using identical inputs/output directory. At most one generation recheck per failed case and one judge recheck per batch is allowed; original attempts are retained. Rechecks are not first-attempt successes. A completed score run can still fail deterministic acceptance; exit zero requires both complete scoring and all deterministic checks.

Output identity pins model, judge, prompt and selected dataset hashes. `results.json` holds coverage, checks and diagnostics; per-case and per-batch files retain the evidence. Validation is used only after the candidate is frozen. `--allow-test` is required to score the reserved test; do not use it while tuning.

## Export existing scores

`scripts/export_faithfulness_langfuse.py` imports recorded samples and scores with no model calls. By default only hashes, allowlisted provenance and numeric scores leave the evaluator. `--capture-synthetic` explicitly permits detailed synthetic questions, contexts and answers; live evidence cannot use that option. The exporter associates each score with a trace and dataset experiment using the installed SDK's v4 OTEL experiment attributes. This small SDK-specific adapter requires readback verification when upgrading Langfuse.

Verify through **Observations API v2**, **Scores API v3** and **Experiments API**. Legacy `GET /traces` returns 404 on v4; a successful write or container health alone is not delivery evidence.

## Promotion

Compare identical cases/evidence and unchanged metric contracts. Require complete paired scoring, table/task coverage, no material factual regression, a positive validation delta with family-bootstrap uncertainty, independent review, and reserved-test confirmation. Case bootstrap does not measure judge variability; repeat a fixed subset to check sensitivity. Retain rejected candidates. Do not strip useful requested content merely to improve the score, or manufacture context by copying the model's answer into evidence.
