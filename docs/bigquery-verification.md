# BigQuery verification (DeepSeek deliverable)

## Purpose and boundary

`scripts/verify_bigquery.py` is a standalone, read-only verifier for the four
approved logical tables (`products`, `order_items`, `orders`, `users`). It uses
the existing `retail.analytics.Analytics` executor, so the same SQL policy,
source binding, parameterization, byte budget, timeout and row/result checks
apply. Live runs load application settings but do not call the Gemini-dependent
`Settings.validate_live()`. They separately require a dedicated `LABEL_SECRET`,
so a missing Gemini key never blocks a BigQuery check.

The verifier does not prove report quality. It records metadata from bounded
aggregate queries; it cannot by itself show that a generated report answers a
business question.

## Safe default

Running the script with no flags performs **no** network call and prints a JSON
report with `"queried": false` and `"status": "live_not_requested"`. Credentials
are not read and no query is attempted.

```sh
.venv/bin/python scripts/verify_bigquery.py
```

## Explicit live opt-in

A live run requires all of:

- `--live` — explicit opt-in;
- `--project` (or `GOOGLE_CLOUD_PROJECT` in the environment) for job execution
  and billing;
- `--products ID ...` — an explicit product scope used to bind the trusted
  order-item subquery;
- a private, nonempty `LABEL_SECRET`, different from the shipped fixture value,
  configured through the application's protected environment setup.

`--project` or `--products` without `--live` is a usage error (exit `2`).

```sh
.venv/bin/python scripts/verify_bigquery.py \
  --live --project my-gcp-project --products 1 2 3 \
  --output /tmp/bigquery-verification.json
```

Authentication uses the standard Google Cloud mechanism already required by the
application (for example `GOOGLE_APPLICATION_CREDENTIALS`). The verifier does
not print, copy or persist credential content.

If the project or dedicated label secret is absent, or `--live` is given without `--products`, the script
makes no query and exits `2` with `"status": "unconfigured"`. If BigQuery is
unreachable, unauthorized or times out, `Analytics` raises its sanitized
`QueryUnavailable`; the verifier maps that to `"status": "unavailable"` with a
generic reason and exits `3`. Service diagnostics and SQL literals are not
copied into the report.

The configured `MAX_SECONDS` is shared across the four queries. Once exhausted,
remaining queries are not submitted and receive `budget_exhausted`, with exit
`3`. Provider timeouts remain `unavailable`; the executor sanitizes provider
diagnostics. The injected controlled-adapter API is for synchronous unit tests;
it does not impose a timeout on an arbitrary injected callable. Direct API
callers must provide valid entitlement JSON; the CLI builds it from product IDs.

## Queries and output

Each live run executes one bounded aggregate per approved table:

```sql
SELECT COUNT(*) AS row_count FROM products;
SELECT COUNT(*) AS row_count FROM order_items;
SELECT COUNT(*) AS row_count FROM orders;
SELECT COUNT(*) AS row_count FROM users;
```

`Analytics` validates them against the logical schema, binds physical sources,
passes product IDs and the label salt as query parameters, dry-runs to enforce
`MAXIMUM_BYTES_BILLED`, and wraps results in the configured row limit. No
generated SQL is passed directly to BigQuery.

The JSON report is metadata only. Per table it includes status, the logical SQL,
result mode, number of result rows, column names, job ID, processed and
estimated bytes, truncation flag and timing. It never includes aggregate values,
customer rows, credentials or configuration secrets. Example shape:

```json
{
  "verifier": "bigquery",
  "live_requested": true,
  "queried": true,
  "tables": ["products", "order_items", "orders", "users"],
  "status": "verified",
  "evidence": {"kind": "bigquery", "note": "..."},
  "results": [
    {
      "table": "products",
      "sql": "SELECT COUNT(*) AS row_count FROM products",
      "status": "ok",
      "result": {
        "mode": "live",
        "rows_returned": 1,
        "columns": ["row_count"],
        "job_id": "...",
        "bytes_processed": 0,
        "estimated_bytes": 0,
        "truncated": false,
        "seconds": 0.0
      }
    }
  ]
}
```

Exit codes: `0` when every requested check returned live metadata (or nothing
was requested), `2` for missing configuration, `3` for unavailable, rejected or
non-live outcomes.

## Unit evidence is not live evidence

`tests/test_verify_bigquery.py` loads the script and drives `verify()` with
controlled adapters. Those checks verify: the default makes no call, missing
configuration is safe, all four logical tables are covered, only metadata is
reported, service failures stay categorized and sanitized, and an adapter that
does not report live mode is not treated as success. A controlled run is
reported as `"status": "unit_controlled"` with
`"evidence": {"kind": "controlled_adapter", ...}` and the note that it is
**not live BigQuery evidence**. No test contacts Google Cloud.

```sh
.venv/bin/python -m pytest tests/test_verify_bigquery.py -q
```

## Current status — verified2026-11-21

Google Cloud CLI is installed; the user completed local ADC browser consent.
Execution/quota project: `static-bee-277223`. A dedicated label secret was
generated privately and the application project setting was saved. Credentials
were not printed. The application's default mode has not been switched to live.

An actual --live verifier run with products1,2 succeeded for all four logical
tables, with real job IDs, live mode and processed/estimated byte counts.
[Portable metadata evidence](../evaluation/bigquery-live-verification-2026-11-21.json).
This verifies authentication, source binding and bounded aggregate execution,
not every SQL operation or report quality. Docker still needs a read-only ADC
mount to use host credentials inside its API container.

## Real agent/report workflow

After the table checks, a live DeepInfra Gemini + Qwen hybrid agent indexed
all23 synthetic methodology trios, executed actual BigQuery aggregate SQL and
saved its completed report. A separate live run verified explicit follow-up
save plus listing/opening from fresh conversations and owner-only store access.
[Workflow metadata](../evaluation/bigquery-live-workflow-2026-11-21.json).

The initial combined analysis/save request returned analysis without saving.
The saved failing result reproduced that regression. The shared model prompt
now explicitly requires save_report before the final answer when both are
requested (prompt retail-v3). The identical live request then executed query,
save_report and final persistence successfully. This is a single real-model
regression check, not a guarantee of all future intent handling.

All test stores were temporary and disposed after verification; these sample
reports are not in the application's database. Real report faithfulness still
needs human review. Full pytest147 passed after the prompt change. No browser
live deployment or Langfuse export is claimed. Default application mode remains
fixture; production tokens/provider selection and container ADC mounts are
separate launch configuration.
