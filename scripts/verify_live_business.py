"""Run explicit live business acceptance with independent physical SQL oracles."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from retail.agent_retrieval_evaluation import matches


def report_checks(answer):
    """Minimum structure for these pinned English cases, not semantic acceptance."""
    narrative = answer.split("### Query evidence", 1)[0].strip().lower()
    return {"summary_present": bool(narrative) and not narrative.startswith("please clarify"),
            "limitations_present": "limit" in narrative or "caveat" in narrative,
            "action_items_present": "action" in narrative}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--env-file", type=Path, default=Path(".env.live"))
    parser.add_argument("--cases", type=Path, default=ROOT / "evaluation/live-business-cases.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {"status": "untested", "cases": [], "human_review": "pending"}
    def persist():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, default=str) + "\n")
    if not args.live:
        persist(); return 0
    if args.url not in {"http://127.0.0.1:8001", "http://localhost:8001"}:
        parser.error("Acceptance mutates saved reports; only the isolated local live backend is supported.")
    from retail.config import Settings
    import httpx
    from google.cloud import bigquery
    config = Settings(_env_file=args.env_file); config.validate_live()
    definition = json.loads(args.cases.read_text())
    if not 1 <= len(definition["cases"]) <= 15 or definition["scope_products"] != [1, 2]:
        parser.error("Expected 1–15 reviewed cases scoped to products 1 and 2.")
    tokens = json.loads(config.api_tokens_json)
    token = next(k for k, v in tokens.items() if v == "alice")
    report.update(status="running", model=config.deepinfra_model if config.llm_provider == "deepinfra" else config.gemini_model,
                  review_model=(config.deepinfra_review_model or config.deepinfra_model) if config.llm_provider == "deepinfra" else config.gemini_model, data_mode="live", reference_sql="physical BigQuery, independent of Analytics.bind", version=definition["version"])
    persist()
    failures = 0
    with bigquery.Client(project=config.google_cloud_project) as bq, httpx.Client(base_url=args.url, headers={"Authorization": "Bearer " + token}, timeout=150) as http:
        health = http.get("/health"); health.raise_for_status()
        if health.json()["mode"] != "live": parser.error("Backend is not live.")
        for case in definition["cases"]:
            result = {"id": case["id"], "question": case["question"], "reference_sql": case["reference_sql"]}
            report["cases"].append(result); persist()
            start = time.monotonic()
            try:
                job = bq.query(case["reference_sql"], job_config=bigquery.QueryJobConfig(
                    query_parameters=[bigquery.ArrayQueryParameter("products", "INT64", [1, 2])],
                    maximum_bytes_billed=config.maximum_bytes_billed, job_timeout_ms=40000), timeout=15, retry=None, job_retry=None)
                expected = json.loads(json.dumps([dict(r) for r in job.result(timeout=45, retry=None, job_retry=None)], default=str))
                result.update(reference_rows=expected, reference_job_id=job.job_id, reference_bytes_processed=job.total_bytes_processed)
                response = http.post("/chat", json={"message": case["question"]}); response.raise_for_status()
                answer = response.json(); result["response"] = answer
                oracle = any(e["mode"] == "live" and not e["truncated"] and matches(e["rows"], expected) for e in answer["evidence"])
                saved = bool((answer.get("management") or {}).get("report_id"))
                completeness = report_checks(answer["answer"])
                result.update(query_oracle_passed=oracle, saved=saved, report_structure_checks=completeness,
                              status="passed" if oracle and saved and all(completeness.values()) and answer["outcome"] == "succeeded" else "failed")
                failures = failures + 1 if answer["outcome"] == "dependency_error" else 0
            except Exception as error:
                result.update(status="untested", error_category=type(error).__name__)
                failures += 1
            result["seconds"] = time.monotonic() - start
            persist()
            print(json.dumps({"case": case["id"], "status": result["status"], "seconds": round(result["seconds"], 1)}), flush=True)
            if failures >= 2:
                report["stop_reason"] = "Two consecutive dependency failures; remaining live work not attempted."
                break
    report["status"] = "passed" if len(report["cases"]) == len(definition["cases"]) and all(c["status"] == "passed" for c in report["cases"]) else "incomplete"
    persist()
    return 0 if report["status"] == "passed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
