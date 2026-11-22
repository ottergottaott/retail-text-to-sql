"""Real local API/CLI smoke with process restart; no external credentials used."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    checks, responses = [], []
    def check(name, passed):
        checks.append({"name": name, "status": "passed" if passed else "failed"})
        if not passed:
            raise AssertionError(name)
    with tempfile.TemporaryDirectory(prefix="retail-offline-") as directory:
        data = Path(directory)
        env = {**os.environ, "RETAIL_MODE": "fixture", "DATABASE_URL": f"sqlite:///{data}/state.db",
            "LOG_PATH": str(data / "events.jsonl"), "API_TOKENS_JSON": '{"alice-local-token":"alice","bob-local-token":"bob"}',
            "ENTITLEMENTS_JSON": '{"alice":[1,2],"bob":[3]}', "ADAPTER_SECRET": "",
            "LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": "", "GEMINI_API_KEY": ""}
        with socket.socket() as socket_handle:
            socket_handle.bind(("127.0.0.1", 0)); port = socket_handle.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        log = (data / "api.log").open("w")
        process = None
        def start():
            process = subprocess.Popen([sys.executable, "-m", "uvicorn", "retail.api:create_app", "--factory",
                "--host", "127.0.0.1", "--port", str(port)], cwd=root, env=env, stdout=log, stderr=log)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Fixture API exited before readiness")
                try:
                    if httpx.get(url + "/health", timeout=1).json().get("mode") == "fixture":
                        return process
                except (httpx.HTTPError, ValueError):
                    pass
                time.sleep(0.1)
            process.terminate(); process.wait(timeout=10)
            raise RuntimeError("Fixture API readiness timed out")
        def stop(process):
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)
        def turn(message, conversation=None):
            command = [sys.executable, "-m", "retail.cli", "--url", url, "--once", message, "--json"]
            if conversation:
                command.extend(["--conversation", conversation])
            result = subprocess.run(command, cwd=root, env={**env, "RETAIL_API_TOKEN": "alice-local-token"},
                capture_output=True, text=True, timeout=30, check=True)
            response = json.loads(result.stdout)
            responses.append(response)
            check("CLI received fixture response and trace", response["mode"] == "fixture" and bool(response["trace_id"]))
            return response
        try:
            process = start()
            initial = turn("Create and save a monthly revenue report")
            con, rid = initial["conversation_id"], initial["management"]["report_id"]
            check("CLI query has known fixture monthly results", initial["evidence"][0]["rows"] == [
                {"month": "2026-01-01 00:00:00", "revenue": 100.0}, {"month": "2026-02-01 00:00:00", "revenue": 110.0}])
            check("Report includes action items", "Action items" in initial["answer"])
            with httpx.Client(base_url=url) as client:
                check("Bob cannot open Alice's report", client.get("/reports/" + rid,
                    headers={"Authorization": "Bearer bob-local-token"}).status_code == 403)
                check("Unauthenticated report access denied", client.get("/reports").status_code == 403)
            stop(process); process = start()
            listed = turn("list reports")
            check("Report survives actual API process restart and fresh chat", rid in listed["answer"] and listed["conversation_id"] != con)
            opened = turn("open report " + rid)
            check("Saved report opens from a new chat", "Action items" in opened["answer"] and "100.0" in opened["answer"])
            preview = turn("delete reports mentioning Analysis report", con)
            proposal = preview["management"]["proposal_id"]
            check("Deletion preview identifies exact saved report", [r["id"] for r in preview["management"]["reports"]] == [rid])
            cancelled = turn("/cancel " + proposal, con)
            check("Cancellation reports zero deletion", cancelled["management"] == {"status": "cancelled", "deleted": 0})
            check("Cancelled report remains available", rid in turn("list reports")["answer"])
            preview = turn("delete reports mentioning Analysis report", con)
            proposal = preview["management"]["proposal_id"]
            deleted = turn("/confirm " + proposal, con)
            check("Confirmation deletes exactly one report", deleted["management"] == {"status": "deleted", "deleted": 1})
            replay = turn("/confirm " + proposal, con)
            check("Confirmation replay deletes nothing further", replay["management"]["deleted"] == 0)
            check("Deleted report no longer listed", rid not in turn("list reports")["answer"])
        finally:
            stop(process); log.close()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            if (data / "events.jsonl").exists():
                args.output.with_suffix(".events.jsonl").write_text((data / "events.jsonl").read_text())
            report = {"mode": "offline_fixture_real_http_cli", "checks": checks, "responses": responses,
                "not_verified": ["Gemini", "BigQuery", "semantic embeddings", "Docker/PostgreSQL", "Open WebUI browser"]}
            args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({"output": str(args.output), "checks_passed": len(checks), "mode": report["mode"]}))


if __name__ == "__main__":
    main()
