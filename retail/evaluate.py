"""Reproducible offline acceptance smoke; never a real-model quality claim."""
import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from .agent import Agent
from .analytics import Analytics, validate, QueryError
from .config import Settings
from .knowledge import Knowledge
from .security import PolicyError, principal_for
from .store import Store


def run(sql_cases, retrieval_cases):
    cases = []
    def record(name, suite, passed, detail=None):
        cases.append({"name": name, "suite": suite, "status": "passed" if passed else "failed", "detail": detail})

    with tempfile.TemporaryDirectory(prefix="retail-eval-") as directory:
        config = Settings(_env_file=None, retail_mode="fixture", database_url=f"sqlite:///{directory}/state.db",
            log_path=f"{directory}/events.jsonl")
        store = Store(config.database_url); analytics = Analytics(config)
        for case in sql_cases:
            try:
                actual = analytics.execute(case["sql"], principal_for(case["user"], config))
                record(case["name"], "fixture_sql", not actual["truncated"] and actual["rows"] == case["expected_rows"],
                    {"actual_rows": actual["rows"], "expected_rows": case["expected_rows"]})
            except (PolicyError, QueryError):
                record(case["name"], "fixture_sql", False, "Query rejected or unresolved")
        for sql in ["SELECT email FROM users", "SELECT first_name FROM users", "SELECT * FROM project.dataset.users",
                    "DELETE FROM products", "SELECT * FROM products; SELECT * FROM users",
                    "WITH q AS (SELECT * FROM secrets) SELECT * FROM q"]:
            try:
                validate(sql)
                record("Deny: " + sql, "safety", False)
            except (PolicyError, QueryError):
                record("Deny: " + sql, "safety", True)
        alice, bob = principal_for("alice", config), principal_for("bob", config)
        knowledge = Knowledge(store)
        recalls, reciprocal_ranks, negative_false_matches = [], [], []
        for case in retrieval_cases:
            found = [t["id"] for t in knowledge.retrieve(case["question"], alice)]
            relevant = set(case["relevant"])
            if relevant:
                recall = len(relevant & set(found)) / len(relevant)
                rr = next((1 / rank for rank, id in enumerate(found, 1) if id in relevant), 0)
                recalls.append(recall); reciprocal_ranks.append(rr)
                passed = recall == 1
            else:
                negative_false_matches.append(bool(found)); passed = not found
            record(case["question"], "lexical_retrieval_smoke", passed, {"found": found, "relevant": case["relevant"]})
        agent = Agent(config, store)
        initial = agent.chat(alice, "monthly revenue")
        con = initial["conversation_id"]
        saved = agent.chat(alice, "save report", con)
        rid = (saved.get("management") or {}).get("report_id")
        record("Fixture agent query and save", "workflow", bool(rid) and bool(initial["evidence"]))
        restarted = Store(config.database_url)
        record("Report persists and is owner scoped", "workflow",
            bool(rid) and any(r["id"] == rid for r in restarted.reports(alice)) and restarted.reports(bob) == [])
        if rid:
            proposal = restarted.propose_delete(alice, con, ids=[rid])
            record("Preview is non-destructive", "workflow", len(restarted.reports(alice)) == 1)
            actual = restarted.confirm_delete(alice, con, proposal["proposal_id"], True)
            replay = restarted.confirm_delete(alice, con, proposal["proposal_id"], True)
            record("Exact confirmation and replay", "workflow", actual["deleted"] == 1 and replay["deleted"] == 0)
        events = [json.loads(line) for line in Path(config.log_path).read_text().splitlines()]
        record("Correlated metadata without raw result rows", "observability",
            all(e.get("trace_id") and e.get("conversation_id") and "rows" not in e if e["stage"] != "query"
                else isinstance(e.get("rows"), int) for e in events))
        summary = {"passed": sum(c["status"] == "passed" for c in cases),
            "failed": sum(c["status"] == "failed" for c in cases), "total": len(cases)}
        return {"mode": "offline_fixture", "dataset_version": "fixture-v1", "planner": "rule_based_fixture",
            "generated_at": datetime.now(timezone.utc).isoformat(), "summary": summary, "cases": cases,
            "retrieval": {"kind": "lexical_smoke_not_held_out", "recall_at_2": sum(recalls)/len(recalls) if recalls else None,
                "mrr": sum(reciprocal_ranks)/len(reciprocal_ranks) if reciprocal_ranks else None,
                "negative_false_match_rate": sum(negative_false_matches)/len(negative_false_matches) if negative_false_matches else None},
            "not_evaluated": ["real Gemini planning/report quality", "real embedding relevance", "live BigQuery",
                "Docker/PostgreSQL runtime", "Open WebUI browser behavior", "human executive usability"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1] / "evaluation"
    parser.add_argument("--sql-cases", type=Path, default=root / "sql-cases.json")
    parser.add_argument("--retrieval-cases", type=Path, default=root / "retrieval-cases.json")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run(json.loads(args.sql_cases.read_text()), json.loads(args.retrieval_cases.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({"output": str(args.output), **report["summary"], "mode": report["mode"]}))
    if report["summary"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
