"""Standalone, read-only BigQuery verifier for the four approved logical tables.

Default invocation performs no network calls. Actual BigQuery access requires
``--live``, a configured execution project and an explicit product scope. The
verifier reuses the existing Analytics executor, so it does not depend on Gemini
startup validation and never sends generated SQL directly to BigQuery.

Output is metadata only: status, per-table row counts, column names, job ID,
processed bytes and timing. Aggregate values, credentials and configuration
secrets are never written to the report.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from retail.analytics import Analytics, QueryError, QueryUnavailable
from retail.config import Settings
from retail.security import PolicyError, principal_for

TABLES = ("products", "order_items", "orders", "users")
QUERIES = (
    ("products", "SELECT COUNT(*) AS row_count FROM products"),
    ("order_items", "SELECT COUNT(*) AS row_count FROM order_items"),
    ("orders", "SELECT COUNT(*) AS row_count FROM orders"),
    ("users", "SELECT COUNT(*) AS row_count FROM users"),
)
EXIT_OK = 0
EXIT_UNCONFIGURED = 2
EXIT_INCOMPLETE = 3


def build_config(live, project=None, products=None):
    """Load settings without the Gemini-dependent live validation."""
    config = Settings()
    config.retail_mode = "live" if live else "fixture"
    if project is not None:
        config.google_cloud_project = project
    if products is not None:
        config.entitlements_json = json.dumps({"alice": sorted(set(products))})
    return config


def _empty_report(live, status, note):
    return {
        "verifier": "bigquery",
        "live_requested": bool(live),
        "queried": False,
        "tables": list(TABLES),
        "results": [],
        "status": status,
        "evidence": {"kind": "none", "note": note},
    }


def _metadata(outcome):
    """Reduce an executor result to metadata; never copy row values."""
    rows = outcome.get("rows") or []
    return {
        "mode": outcome.get("mode"),
        "rows_returned": len(rows),
        "columns": sorted(rows[0]) if rows else [],
        "job_id": outcome.get("job_id"),
        "bytes_processed": outcome.get("bytes_processed"),
        "estimated_bytes": outcome.get("estimated_bytes"),
        "truncated": bool(outcome.get("truncated")),
        "seconds": outcome.get("seconds"),
    }


def verify(live, config=None, executor=None):
    """Return (report, exit_code) without ever being called from tests as live proof."""
    if not live:
        return _empty_report(
            False,
            "live_not_requested",
            "No BigQuery call was made. Pass --live to request a bounded read-only check.",
        ), EXIT_OK
    config = config or build_config(live)
    if not config.google_cloud_project:
        return _empty_report(
            True,
            "unconfigured",
            "No execution project is configured. Set --project or GOOGLE_CLOUD_PROJECT; no query was attempted.",
        ), EXIT_UNCONFIGURED

    controlled = executor is not None
    if controlled:
        call = executor
        kind = "controlled_adapter"
    else:
        if not config.label_secret.strip() or config.label_secret == "local-fixture-label-secret":
            return _empty_report(
                True,
                "unconfigured",
                "A dedicated nonempty LABEL_SECRET is required; no query was attempted.",
            ), EXIT_UNCONFIGURED
        analytics = Analytics(config)
        try:
            principal = principal_for("alice", config)
        except PolicyError:
            return _empty_report(
                True,
                "unconfigured",
                "No usable product scope is configured for the verifier identity; no query was attempted.",
            ), EXIT_UNCONFIGURED
        deadline = time.monotonic() + config.max_seconds

        def call(sql):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise QueryUnavailable("Query time budget exhausted")
            return analytics.execute(sql, principal, remaining_seconds=remaining)

        kind = "bigquery"

    report = {
        "verifier": "bigquery",
        "live_requested": True,
        "queried": True,
        "tables": list(TABLES),
        "results": [],
        "evidence": {"kind": kind},
    }
    code = EXIT_OK
    for table, sql in QUERIES:
        entry = {"table": table, "sql": sql, "status": "ok"}
        try:
            outcome = call(sql)
        except QueryUnavailable as error:
            if str(error) == "Query time budget exhausted":
                entry["status"] = "budget_exhausted"
                entry["reason"] = "The local verification time budget was exhausted."
            else:
                entry["status"] = "unavailable"
                entry["reason"] = "BigQuery unavailable, timed out, or access not configured."
            code = max(code, EXIT_INCOMPLETE)
        except QueryError:
            entry["status"] = "query_error"
            entry["reason"] = "BigQuery rejected the query. Check supported types and SQL syntax."
            code = max(code, EXIT_INCOMPLETE)
        except PolicyError:
            entry["status"] = "policy_denied"
            entry["reason"] = "The verification query failed a local policy check."
            code = max(code, EXIT_INCOMPLETE)
        else:
            entry["result"] = _metadata(outcome)
            if outcome.get("mode") != "live":
                entry["status"] = "not_live"
                entry["reason"] = "The executor did not report live mode."
                code = max(code, EXIT_INCOMPLETE)
        report["results"].append(entry)

    complete = all(entry["status"] == "ok" for entry in report["results"])
    if controlled:
        # Controlled adapters validate mechanics only and can never be presented
        # as successful live BigQuery verification.
        report["status"] = "unit_controlled" if complete else "incomplete_controlled"
        report["evidence"]["note"] = "Controlled adapter result; not live BigQuery evidence."
    else:
        report["status"] = "verified" if complete else "incomplete"
        report["evidence"]["note"] = "Live executor result; retain job IDs and bytes as provider metadata."
    return report, code


def _write(report, output):
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute bounded read-only metadata queries. Without this flag no query is made.",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="GCP execution/billing project. Falls back to GOOGLE_CLOUD_PROJECT.",
    )
    parser.add_argument(
        "--products",
        type=int,
        nargs="+",
        default=None,
        metavar="ID",
        help="Explicit product IDs defining the verification scope. Required with --live.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Also write the JSON report here.")
    args = parser.parse_args(argv)

    if not args.live:
        if args.project is not None or args.products is not None:
            parser.error("--project and --products require --live")
        report, code = verify(False)
    elif args.products is None:
        report, code = _empty_report(
            True,
            "unconfigured",
            "--products is required with --live so the verification scope is explicit; no query was attempted.",
        ), EXIT_UNCONFIGURED
    elif any(product <= 0 for product in args.products):
        parser.error("--products values must be positive integers")
    else:
        config = build_config(True, project=args.project, products=args.products)
        report, code = verify(True, config=config)

    _write(report, args.output)
    return code


if __name__ == "__main__":
    sys.exit(main())
