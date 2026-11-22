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

Prerequisites: Docker with Compose v2 (macOS, Linux or WSL). Run from the extracted
project directory on a machine with ports 3000 and 8000 available. Initial
dependency/image installation requires internet access.

```sh
./start.sh
```

Open **http://localhost:3000**. Sign in with `WEBUI_ADMIN_EMAIL` and
`WEBUI_ADMIN_PASSWORD` from your locally generated `.env.docker-retail-demo`; the installer
does not print them. Select **Retail Intelligence**. Bootstrap expects the demo
account to be the first administrator on a fresh WebUI volume. If you already
have a WebUI deployment on this port, use a separate environment instead of
reconfiguring that installation:

```sh
./start.sh --project another-demo --api-port 8010 --webui-port 3010
```

The script builds the runtime, generates persistent local secrets, waits for
healthy services, installs the WebUI integrations and reloads their configuration.
No Python or uv installation is required on the host. Rerun the same command
after a setup interruption; it preserves the existing local login and data.

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
docker compose -p retail-demo --env-file .env.docker-retail-demo exec -e RETAIL_API_TOKEN=alice-local-token api retail --once 'monthly revenue' --json
```

Use `bob-local-token` to exercise a separate fixture user. Alice manages
North/South; Bob manages West; `ceo-local-token` has all-brand access. These are local demo tokens, not production credentials.
Omit `--once ... --json` for the interactive CLI, or pass `--conversation ID`
between invocations. Developer tests use `uv sync --frozen --extra dev` and
`uv run pytest -q`; uv is optional for reviewer startup.

Stop with `./start.sh --stop` (include `--project NAME` for another deployment). Named volumes preserve
data. Do not use `down -v` unless you intend to erase the demo databases.

## Live model and data

The live backend supports direct Google Gemini or Gemini via DeepInfra;
the embedding provider is independently selectable. BigQuery requires Google
application-default credentials and a project with query-job permission.
See [.env.example](.env.example), [setup](docs/setup.md), and
[BigQuery verification](docs/bigquery-verification.md). For a host live backend,
use the documented public launch command; private development helpers are not required.

For the Docker live launch, fill in `.env.providers` from
[deployment/live.env.example](deployment/live.env.example), then use:

```sh
./start.sh --live --project retail-live --env-file .env.providers --google-credentials /absolute/path/google-credentials.json
```

Supply your own Google ADC/service-account credential file with the required
BigQuery permissions. The script copies the selected env/JSON files through the Docker API. Google
credentials stay in a private Docker volume mounted read-only by the API;
they never enter the image. No repository mount or File Sharing changes are needed.
This creates a new reviewer deployment; it does not import existing developer
reports or WebUI accounts. The example brand permissions are demonstration
settings; replace them deliberately. For production, use managed identities.

## Shared report tone

Edit [deployment/tone.txt](deployment/tone.txt), then run
`./start.sh --tone deployment/tone.txt --reviewer owner`. Add
`--live --project retail-live` for that deployment. The operator command
publishes a new shared version; the next question uses it without a restart.
It controls presentation tone. Personal format/depth preferences are separate.
There is no WebUI editor for this shared setting yet.

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
resume. The optional prototype knowledge publisher is operator-reviewed. The required production design uses automatic evaluation gates and exception review. Local Langfuse experiment ingestion and live metadata delivery have been verified.
See [experiment setup and boundaries](docs/faithfulness-experiments.md).

252 tests passed in the latest local run, including brand/CEO authorization, demographic cohort checks and five CLI/HTTP/SSE integration tests. Live business checks and judge scores
have separate evidence contracts; tests are not an answer-accuracy percentage.
A fresh installation on another machine and final human report acceptance remain open.
The latest prompt experiment is incomplete after provider balance exhaustion;
Historical live evidence uses retail-v7/v8; the retail-v9-client-policy prompt has not yet been evaluated live. Live calls need funded provider credentials;
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
