# CLI verification — 22 November 2026

The application CLI was checked as a separate executable, rather than inferred
from API/WebUI tests. No CLI runtime implementation changed in this verification.

## Controlled integration

`tests/test_cli_workflow.py`: five tests pass against an actual HTTP/SSE API,
isolated SQLite state and local SQL fixtures. Actual CLI subprocesses cover:

- JSON-only stdout and progress/conversation metadata on stderr.
- Analysis → save → new-chat listing → reopen with explicit conversation ID.
- Another user cannot read the saved report.
- Interactive stdin processes multiple turns with one conversation.
- Missing/invalid tokens and unavailable API fail without a traceback.

This demonstrates local integration and error behavior, not model quality.

## Live executable

`evaluation/cli-live-2026-11-22.json` records two successful calls to the installed
`.venv/bin/retail` executable through real HTTP/SSE with Gemini and BigQuery.
The first counted authorized catalogue products. The second used the explicit
`--conversation` ID and answered from prior analysis without another SQL query.
Both returned valid JSON, progress appeared on stderr, and neither requested
or saved a report. Credentials remained in the child environment, not arguments.
The verification started/stopped its own API process when necessary; it is not
evidence of a permanently running deployment or browser visual acceptance.

Human usefulness review remains pending. The fixed client timeout is 150 seconds;
a server configured with a larger maximum turn budget can outlive the client.
The supported default server budget is 90 seconds; arbitrary extended-budget
configuration is not covered by this smoke test.
