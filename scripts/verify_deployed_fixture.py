"""Exercise report deletion against a running fixture API, including concurrent confirmation.

Only deletes the new report created by this run. Existing reports are preserved.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    checks = []

    def check(name, passed):
        checks.append({"name": name, "status": "passed" if passed else "failed"})
        if not passed:
            raise AssertionError(name)

    headers = {"Authorization": "Bearer " + os.getenv("RETAIL_API_TOKEN", "alice-local-token")}
    other = {"Authorization": "Bearer " + os.getenv("RETAIL_OTHER_API_TOKEN", "bob-local-token")}
    try:
        with httpx.Client(base_url=args.url, headers=headers, timeout=120) as client:
            check("Running API explicitly uses fixture mode", client.get("/health").json()["mode"] == "fixture")
            before = {r["id"] for r in client.get("/reports").json()}
            initial = client.post("/chat", json={"message": "Create and save a monthly revenue report"})
            initial.raise_for_status()
            data = initial.json()
            rid, con = data["management"]["report_id"], data["conversation_id"]
            check("New report created by this verification", rid not in before)
            check("Other owner cannot open report", client.get("/reports/" + rid, headers=other).status_code == 403)
            proposal_body = {"conversation_id": con, "report_ids": [rid]}

            def preview():
                response = client.post("/reports/deletion-proposals", json=proposal_body)
                response.raise_for_status()
                p = response.json()
                check("Preview targets only this run's report", [r["id"] for r in p["reports"]] == [rid])
                return "/reports/deletion-proposals/" + p["proposal_id"] + "/confirmation"

            path = preview()
            body = {"conversation_id": con, "confirm": True}
            check("Other owner cannot confirm proposal", client.post(path, json=body, headers=other).status_code == 403)
            check("String confirmation rejected", client.post(path, json={**body, "confirm": "true"}).status_code == 422)
            check("Wrong conversation rejected", client.post(path, json={**body, "conversation_id": "wrong"}).status_code == 403)
            cancelled = client.post(path, json={**body, "confirm": False})
            check("Cancellation deletes nothing", cancelled.json() == {"status": "cancelled", "deleted": 0})
            check("Report remains after cancellation", client.get("/reports/" + rid).status_code == 200)
            path = preview()

            def confirm(_):
                return httpx.post(args.url + path, headers=headers, json=body, timeout=30)

            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = list(executor.map(confirm, range(2)))
            check("Concurrent confirmation returns handled results", all(r.status_code == 200 for r in responses))
            check("Concurrent confirmations delete exactly once", sorted(r.json()["deleted"] for r in responses) == [0, 1])
            check("Replay deletes nothing", client.post(path, json=body).json() == {"status": "deleted", "deleted": 0})
            check("Deleted report is inaccessible", client.get("/reports/" + rid).status_code == 403)
            after = {r["id"] for r in client.get("/reports").json()}
            check("Existing reports preserved", before == after)
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"mode": "fixture", "target": args.url, "checks": checks}, indent=2))
    print(json.dumps({"passed": len(checks), "output": str(args.output)}))


if __name__ == "__main__":
    main()
