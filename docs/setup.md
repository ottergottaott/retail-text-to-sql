# Setup and operational boundaries

## Docker fixture demonstration

Only Docker with Compose v2 is needed on the host (macOS, Linux or WSL).
From the repository root:

```sh
./start.sh
```

The script builds the images, creates a private `.env.docker-retail-demo`, waits
for services, installs the Pipe/Reports/feedback/preferences integrations and
reloads them. No host Python or uv is needed. Open http://localhost:3000 and sign
in with `WEBUI_ADMIN_EMAIL` / `WEBUI_ADMIN_PASSWORD` from the generated file.
Select **Retail Intelligence**. This dedicated local installation assumes the
created account is its first administrator. Never point it at an unrelated WebUI.

For occupied ports, use `./start.sh --project another-demo --api-port 8010 --webui-port 3010`.
Rerun the same command to resume; local secrets and volumes are preserved. Stop
with `./start.sh --stop` (include the custom `--project` when used). Do not use
`docker compose down -v` unless you intend to erase stored data.

PostgreSQL is only reachable on the Compose network. API/WebUI ports bind to
loopback. Generated configuration files contain secrets; do not share or commit
them. A fixture launch makes no model/BigQuery calls and demonstrates mechanics,
not live answer quality. See [the walkthrough](../START_HERE.md).

The launcher transfers only the generated configuration and, in live mode,
the selected provider env/Google JSON files through `docker cp`. It never mounts
the host repository or Docker socket into a container and does not modify
Docker Desktop File Sharing. Temporary setup containers are removed on exit.

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

### Credentials checklist

Two independent credentials are required: a Gemini API key does not authenticate
BigQuery. Create the model key in [Google AI Studio](https://aistudio.google.com/apikey).
For BigQuery, use a Google Cloud execution project with the BigQuery API enabled
and an identity allowed to create query jobs (`roles/bigquery.jobUser`); source
tables must be readable. The source dataset is public, but jobs run in your project.
No write access to the source tables is required.

For local user credentials, install the Google Cloud CLI and run
`gcloud auth application-default login`. Pass the resulting ADC JSON file to
`--google-credentials` (on macOS/Linux it is normally
`~/.config/gcloud/application_default_credentials.json`). `gcloud auth login`
alone is not the application-default credential setup. Alternatively supply an
existing approved service-account/external-account credential JSON. Do not
commit credential files or create a broad administrator key for this demo.
See Google's [BigQuery authentication](https://cloud.google.com/bigquery/docs/authentication)
and [IAM role reference](https://cloud.google.com/bigquery/docs/access-control).

Fill `GOOGLE_CLOUD_PROJECT`, `GEMINI_API_KEY`, and an enabled `GEMINI_MODEL` in
`.env.providers`. Keep `EMBEDDING_PROVIDER=none` for the first launch. If the model
is unavailable or lacks quota, chat returns a dependency error rather than
inventing a result. Valid JSON and successful startup do not prove usable cloud
permissions/quota; verify one live question before review.

### Gemini through DeepInfra

If your model key is from DeepInfra, copy
[`deployment/deepinfra.env.example`](../deployment/deepinfra.env.example) to
`.env.providers` instead of the direct-Google template. Fill
`DEEPINFRA_API_KEY`, `DEEPINFRA_MODEL` and `GOOGLE_CLOUD_PROJECT` locally.
Keep `LLM_PROVIDER=deepinfra`; a direct `GEMINI_API_KEY` is not required for this
configuration. BigQuery still requires a separate Google credential JSON.
Model availability/quota must be checked with your provider account.

The adapter uses the fixed OpenAI-compatible base URL
`https://api.deepinfra.com/v1/openai`, with `/chat/completions` for model calls.
There is no provider URL setting to fill in. This also prevents arbitrary
endpoint selection. This configuration is for Gemini serving, not development
reviews through OpenCode China.

```sh
cp deployment/deepinfra.env.example .env.providers
# Edit .env.providers locally, then:
./start.sh --live --project retail-live --env-file .env.providers --google-credentials /absolute/path/google-credentials.json
```

Open WebUI at `http://localhost:3000`. The backend API is at
`http://localhost:8000`, with its route reference at `/docs`; API calls require
an application bearer token from `.env.docker-retail-live`, not your provider
key. If those ports are occupied, add `--webui-port 3010 --api-port 8010` and use
those ports in browser/CLI URLs. No public hosted URL is provided.

Keep provider keys in the ignored local env file and Google credentials outside
the repository. Do not send keys in chat or commit populated env files.

### Launch and verification

BigQuery can be checked independently before Gemini is configured: see
[standalone BigQuery verification](bigquery-verification.md). The default
verifier invocation loads no environment settings and makes no provider calls.

Copy `deployment/live.env.example` to `.env.providers` (ignored by Git), fill in
the execution project, provider key and model ID, and set intended brand access.
The supplied example uses lexical retrieval to avoid embedding calls during setup.
Then run:

```sh
./start.sh --live --project retail-live --env-file .env.providers --google-credentials /absolute/path/google-credentials.json
```

Use your own ADC or service-account credential file. The launcher copies it
through the Docker API into the project-specific `retail-live-google-credentials`
volume. Its directory is `0700`, its file is `0600`, and both belong to the
non-root API identity. The API mounts the volume read-only at `/run/secrets`
and uses `GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/google.json`.
The original file and its permissions are unchanged. Secrets are never added
to the image; no host directory sharing is needed. Temporary setup containers
containing config inputs are removed, including after a failed setup.
The launcher generates stable application tokens, label/adapter secrets and
local login credentials in `.env.docker-retail-live`. The input env file supplies provider
settings, budgets and entitlements; it does not replace the generated database,
login, label or adapter secrets. On rerun, supplied provider settings update;
local identities and stored reports remain. Fixture/live modes need separate
project names and available ports. The private credential volume persists across
restarts and is external to Compose; removing application containers does not
delete it. Stop with `./start.sh --project retail-live --stop`.

Langfuse export is disabled by default (`LANGFUSE_ENABLED=false`). Local metadata events remain in `LOG_PATH`; enable export only when the Langfuse stack is running and you need it.

No evaluation or corpus indexing is run by the launcher. Live questions and
explicit embedding indexing can incur charges. Startup configuration validation
does not prove credentials have working provider/BigQuery permissions. Prefer
managed workload identity for cloud deployment.

For manual host setup, the equivalent settings are described below.

Set RETAIL_MODE=live and GOOGLE_CLOUD_PROJECT, a random LABEL_SECRET, and
replace local demo API tokens. For direct Google use LLM_PROVIDER=gemini,
GEMINI_MODEL and GEMINI_API_KEY. Alternatively use LLM_PROVIDER=deepinfra,
DEEPINFRA_MODEL=google/gemini-3.7-flash and DEEPINFRA_API_KEY. Choose embeddings
independently with EMBEDDING_PROVIDER=gemini|deepinfra|none; Qwen on DeepInfra
uses DEEPINFRA_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B. The backend validates these
requirements before startup. Set BRAND_ACCESS_JSON deliberately; the legacy ENTITLEMENTS_JSON product-ID path is for old tests/deployments. The GCP
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

## Historical integration status — 2026-11-21

These measurements predate the latest brand/cohort policy and do not establish
its live acceptance. See the consolidated acceptance spec for current requirements.

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
