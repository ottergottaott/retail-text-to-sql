# Setup and operational boundaries

## Docker fixture demonstration

No Gemini or Google Cloud secrets are needed for fixture mode. Generate an
isolated ignored `.env.fixture` with local demo credentials; existing files are
preserved. Run from the project directory after installing dependencies.

```sh
.venv/bin/python scripts/setup_fixture.py
BUILDX_CONFIG=/tmp/retail-buildx docker compose --env-file .env.fixture --project-name retail-assessment up --build -d
.venv/bin/python scripts/bootstrap_webui.py
docker compose --env-file .env.fixture --project-name retail-assessment up -d --force-recreate api
docker compose --env-file .env.fixture --project-name retail-assessment exec -e RETAIL_API_TOKEN=alice-local-token api retail --url http://localhost:8000
```

API: http://localhost:8000. WebUI: http://localhost:3000. Ports bind to loopback.
PostgreSQL is reachable only on the Compose network. Named volumes persist state
across container recreation. `docker compose down` preserves volumes; the `-v`
flag removes them and must not be used for routine shutdown.

The bootstrap creates the local WebUI account, enables the Pipe and configures
the server identity mapping. Local admin login details are in `.env.fixture`;
keep that file private. API recreation loads the updated mapping.

**Earlier fixture verification (not repeated in the current session):** image build, healthy API/PostgreSQL/WebUI, container CLI report
creation, report persistence after API recreation, and actual WebUI chat with
progress history, rendered evidence table and saved report. Data/model mode is
fixture; this does not verify Gemini or BigQuery.

## Open WebUI Pipe

1. Create the first local WebUI account as administrator.
2. In Workspace → Functions, create/import `integrations/openwebui_pipe.py` and
   enable it. This is administrator-installed server code.
3. Set its API_URL valve to `http://api:8000` and ADAPTER_SECRET to the backend
   secret. This secret stays on the WebUI server, never in browser requests.
4. Obtain the authenticated WebUI account ID from its account/admin data and add
   it to WEBUI_USERS_JSON in the backend, e.g. `{"actual-webui-id":"alice"}`.
   Recreate the API container to load environment changes.
5. Select Retail Analyst in a chat. Observe progress statuses followed by a
   persisted final answer with tables. Reports are listed/opened from chat and
   the optional authenticated Reports library. Deletion requires the exact command from
   the preview. Deleting the WebUI chat does not delete saved reports.

Pipe transports only the latest text question plus server-injected user/chat/message
identity. It contains no agent, SQL rules, entitlement logic or tool execution.
Backend conversation association is persisted and owner scoped; Pipe restart
does not lose it. Regeneration/branching currently appends to the same backend
history; separate branch mapping is a known UX limitation. WebUI stores original
messages before backend sanitization: do not use real PII in this demonstration.
Production needs ingress privacy controls and coordinated retention policy.

### Reports, feedback and preference pages

Build `integrations/webui/Dockerfile` and use `compose.webui-reports.yaml` with
the base Compose file. Install the updated Pipe, then run
`scripts/install_webui_reports.py` with `WEBUI_ADMIN_TOKEN` in the environment
and the local `--webui-url`. The installer preserves Pipe valves and model grants,
enables the Reports/Learning Events and attaches **My reports**, **Give feedback**,
and **My preferences** to Retail Intelligence. Restart WebUI after installation.
Assets are served at `/static/retail-reports.html` and `/static/retail-learning.html`.
Feedback must be opened from an answer generated with the updated Pipe/backend;
old answers have no trusted message mapping. Both pages use the current signed-in
account; the adapter secret remains server-side. See [learning workflow](improvement.md).

Open WebUI API transport and event behavior follow the official
[Pipe documentation](https://docs.openwebui.com/features/extensibility/plugin/functions/pipe/)
and [status events](https://docs.openwebui.com/features/extensibility/plugin/development/events/).
The pinned slim image follows the documented
[release tag format](https://docs.openwebui.com/getting-started/quick-start/).
No local models or Ollama are required. The pinned v0.13.4-slim release was
verified in a local browser with the fixture backend.

## Live Gemini and BigQuery

BigQuery can be checked independently before Gemini is configured: see
[standalone BigQuery verification](bigquery-verification.md). The default
verifier invocation loads no environment settings and makes no provider calls.

Supply credentials via the secure form or local ignored environment file. Never
copy credentials into the image. Google credentials on the host do not magically
exist inside containers. Add a local Compose override mounting the credential file
read-only at `/run/secrets/google.json` and set GOOGLE_APPLICATION_CREDENTIALS to
that container path. Prefer workload identity for a cloud deployment.

Set RETAIL_MODE=live and GOOGLE_CLOUD_PROJECT, a random LABEL_SECRET, and
replace local demo API tokens. For direct Google use LLM_PROVIDER=gemini,
GEMINI_MODEL and GEMINI_API_KEY. Alternatively use LLM_PROVIDER=deepinfra,
DEEPINFRA_MODEL=google/gemini-3.5-flash and DEEPINFRA_API_KEY. Choose embeddings
independently with EMBEDDING_PROVIDER=gemini|deepinfra|none; Qwen on DeepInfra
uses DEEPINFRA_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B. The backend validates these
requirements before startup. Restrict product entitlements deliberately. The GCP
identity needs BigQuery job creation in the billing/execution project and public
dataset read access. Queries dry-run and enforce maximum bytes billed, timeout,
query count and returned-row budgets. Public data freshness is outside this app's
control. Neither fixture SQL nor tests prove actual BigQuery service behavior.

Document embeddings use `gemini-embedding-001` with retrieval document/query task
types, following [Google's embeddings documentation](https://ai.google.dev/gemini-api/docs/embeddings).
The embedding model and source content/version identify each index record.
Index explicitly through the administrator command once available. Missing index
or provider failure uses lexical retrieval and records that fact in telemetry.
The default cosine threshold is a starting assumption requiring calibration;
controlled-vector tests verify mechanics, not semantic quality.

## Expanded demo knowledge

The bundled `retail/data/golden-trios.json` contains 20 additional synthetic
methodology examples. From the configured application environment, import
explicitly with `retail-admin load-demo`, then `retail-admin index` with the
chosen embedding provider. Existing trio IDs/publications are preserved.
Changing provider/model/dimensions/instruction requires reindexing. The importer
validates the entire file before writing. Evaluation CLI imports into an
isolated store and does not change the running application's knowledge.

## Current integration status — 2026-11-21

See [START_HERE](../START_HERE.md) for the reviewer installation flow and
[WebUI integration](webui-integration.md) for component responsibilities and
same-database knowledge import/index commands. Real DeepInfra chat/embeddings and retrieval evaluations passed;
BigQuery project/host ADC are now configured and live aggregate queries passed;
see [connection evidence](bigquery-verification.md). Docker recovered and live
browser report/feedback/preferences checks passed. See
[learning acceptance](../evaluation/learning-loop-acceptance-2026-11-21.json) and
[measured retrieval results](../evaluation/retrieval-results-2026-11-21.md).


## Persistent host live backend used for final acceptance

The protected `.env.live` contains provider and application credentials, the
existing WebUI mapping, `RETAIL_MODE=live`, product entitlements, and
`DATABASE_URL=sqlite:////Users/user/Documents/w/cv/retail-assistant/.local/live/retail.db`.
Do not print, commit or serve that file. Host ADC supplies BigQuery credentials.
From the project directory, with `.env.live` configured:

```sh
uv sync --locked --extra dev
uv run python -c 'from retail.config import Settings; from retail.api import create_app; import uvicorn; uvicorn.run(create_app(Settings(_env_file=".env.live")), host="127.0.0.1", port=8001)'
```

Choose a database path appropriate to your checkout when reproducing elsewhere.
Do not replace an existing database or overwrite reports. The above launch does
not need the private `.local/live/server.py` helper used during acceptance.
To import/index against this exact environment (explicitly invokes billed
embeddings), use the same protected config and database:

```sh
uv run python -c 'from retail.config import Settings; from retail.store import Store; from retail.golden import load_demo_corpus; from retail.knowledge import Knowledge; from retail.providers import embeddings_for; c=Settings(_env_file=".env.live"); c.validate_live(); c.validate_embeddings(); s=Store(c.database_url); print(load_demo_corpus(s)); print(Knowledge(s, embeddings_for(c), c.retrieval_min_similarity).index())'
```

Do not index a fixture or evaluation store and expect it to affect the live process.

For containerized Open WebUI with this host backend, set the server-side Pipe
API_URL to `http://host.docker.internal:8001`; use the matching protected
ADAPTER_SECRET and WebUI-user mapping from `.env.live`. The backend handles ADC
on the host, so this arrangement needs no credential mount into WebUI. This
connection reached host health successfully, but the final browser run is blocked:
Docker VM logs showed disk I/O errors and the daemon stopped responding. No
volume deletion or factory reset was performed. See final-acceptance.md.

The separate static review page requires no credentials and serves only recorded
evaluation artifacts, not the project directory:

```sh
uv run python scripts/build_acceptance_review.py
uv run python -m http.server 8002 --bind 127.0.0.1 --directory evaluation
```

Open http://127.0.0.1:8002/morning-review-2026-11-21.html. Verdicts stay in browser
storage until exported. This page is not a live chat or an Open WebUI replacement.


### Docker recovery during final acceptance

Docker Desktop was restarted without factory reset/prune or volume deletion.
Thirteen unrelated containers were stopped; only `retail-assessment-webui-1`
remains running. The live API and SQLite application database are on the host
using the launch above; do not start the fixture API container on top of it.
WebUI is http://127.0.0.1:3000 and forwards to host port 8001.
See `evaluation/webui-live-grounded-2026-11-21.json` for the verified browser path.
