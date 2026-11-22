# Retail Intelligence — reviewer guide

A retail analysis assistant with Gemini, BigQuery and curated analytical knowledge.
One Python/LangGraph backend serves a CLI and Open WebUI. Reports include tables,
limitations, proposed actions and inspectable SQL evidence.

## Suggested review order

Open the [one-page review summary](docs/review-summary.html) for measured results
and remaining checks.

1. Read the [architecture overview](docs/technical-overview.html) (about 5 minutes).
2. Start the credential-free demo below and try the walkthrough.
3. Inspect the [tool decision prompt](docs/prompts/system.txt) and
   [decision schema](docs/prompts/decision.schema.json).
4. Review [test and evaluation evidence](docs/submission-evidence.md).
5. For real model/data execution, follow [live setup](docs/setup.md#live-gemini-and-bigquery).

## Credential-free Docker demo

Prerequisites: Docker Compose v2, Python 3.11+ and uv. Run from the extracted
project directory on a machine with ports 3000 and 8000 available. Initial
dependency/image installation requires internet access.

```sh
uv sync --frozen --extra dev
uv run python scripts/setup_fixture.py
docker compose -p retail-assessment --env-file .env.fixture -f compose.yaml -f compose.webui-reports.yaml up --build -d
uv run python scripts/bootstrap_webui.py --reports
docker compose -p retail-assessment --env-file .env.fixture -f compose.yaml -f compose.webui-reports.yaml up -d --force-recreate api webui
```

Open **http://localhost:3000**. Sign in with `WEBUI_ADMIN_EMAIL` and
`WEBUI_ADMIN_PASSWORD` from your locally generated `.env.fixture`; the installer
does not print them. Select **Retail Intelligence**. Bootstrap expects the demo
account to be the first administrator on a fresh WebUI volume. If you already
have a WebUI deployment on this port, use a separate environment instead of
reconfiguring that installation.

**This is fixture mode:** deterministic synthetic data and a small rule-based
planner, clearly labeled. It demonstrates integration and safety mechanics;
it does not demonstrate Gemini reasoning, live BigQuery or semantic RAG quality.
No API keys are included. Live calls require your own credentials and may incur charges.

### Five-minute walkthrough

1. Ask **“Create and save a monthly revenue report.”** Inspect progress, the
   evidence table and saved report ID. Open the HTML Artifact/embedded preview.
2. Use **My reports**, or the **Reports** sidebar link. Open the saved report,
   expand SQL evidence and download the standalone HTML snapshot.
3. Start a new chat and ask **“List my saved reports.”** The earlier report
   remains available independently of its originating chat.
4. Under a newly generated answer, use **Give feedback**. Inspect the selected
   response and submit a rating/comment. It remains unreviewed; it cannot publish knowledge.
5. Use **My preferences** to save bullets/concise, then start a new chat and
   ask for monthly revenue. Explicit requests for tables override presentation defaults.
6. Ask **“Delete reports.”** Inspect the proposed targets. Use the displayed
   `/cancel ID` to keep them. Actual deletion requires the explicit `/confirm ID`
   application command; the model cannot confirm for you.

Fixture planning supports these examples, not arbitrary business questions.
For dynamic analysis, use live mode. Saved HTML/downloads are snapshots and cannot
be remotely revoked when a database report is deleted.

### CLI and automated checks

With the Docker API running:

```sh
export RETAIL_API_TOKEN=alice-local-token
uv run retail --url http://localhost:8000 --once 'monthly revenue' --json
uv run pytest -q
uv run python scripts/verify_offline.py --output /tmp/retail-offline.json
```

Use `bob-local-token` to exercise a separate fixture user. Alice is authorized for
products 1/2; Bob for product 3. These are local demo tokens, not production credentials.
Use the interactive `uv run retail --url http://localhost:8000` to retain a
conversation, or pass `--conversation ID` between invocations.

Stop with the same Compose arguments followed by `stop`. Named volumes preserve
data. Do not use `down -v` unless you intend to erase the demo databases.

## Live model and data

The live backend supports direct Google Gemini or Gemini via DeepInfra;
the embedding provider is independently selectable. BigQuery requires Google
application-default credentials and a project with query-job permission.
See [.env.example](.env.example), [setup](docs/setup.md), and
[BigQuery verification](docs/bigquery-verification.md). For a host live backend,
use the documented public launch command; private development helpers are not required.

Curated examples are explicitly synthetic, not client-supplied analyst history.
Load them with `retail-admin load-demo` and index with `retail-admin index`
against the same configured application database. Indexing uses the selected
provider and can incur charges; it is an operator operation, not a chat-time job.

The [reviewed learning demo](docs/improvement.md#reproducible-beforeafter-evidence)
uses a real model and embeddings with isolated fixture SQL. It leaves live shared
knowledge untouched and records both failed and passing evaluation evidence.

## Scope and limitations

This is a bounded assessment MVP. Current schema metadata is a static, minimized
four-table contract; there is no dynamic BigQuery metadata discovery. There is no
autonomous training, preference inference, dashboard scheduler or durable mid-turn
resume. Human approval governs shared knowledge publication. Local Langfuse experiment ingestion and live metadata delivery have been verified.
See [experiment setup and boundaries](docs/faithfulness-experiments.md).

216 tests passed in the latest local run, including five actual CLI/HTTP/SSE integration tests. Live business checks and judge scores
have separate evidence contracts; tests are not an answer-accuracy percentage.
A fresh installation on another machine and final human report acceptance remain open.
The latest prompt experiment is incomplete after provider balance exhaustion;
retail-v8 remains the serving prompt. Live calls need funded provider credentials;
the credential-free fixture demo remains available.

## Source map

- `retail/agent.py`: graph, budgets, tool dispatch and grounding review.
- `retail/model.py`, `retail/deepinfra.py`: prompts, typed decisions and providers.
- `retail/analytics.py`, `retail/security.py`: SQL and data-access boundaries.
- `retail/knowledge.py`: versioned retrieval and explicit indexing.
- `retail/store.py`, `retail/governance.py`, `retail/learning.py`: persistence and reviewed improvement.
- `integrations/`: thin WebUI Pipe, Actions and authenticated pages.
- `evaluation/`, `tests/`: recorded measurements and regression coverage.

Detailed architecture and all eight requirement areas: [technical design](docs/architecture.md).
