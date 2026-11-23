# Retail Intelligence

A retail analysis assistant with Gemini, BigQuery, Open WebUI and a CLI.
Ask a business question, inspect the SQL and save an HTML report.

![Open WebUI chat with a saved report, Artifacts panel and visible feedback link](evaluation/screenshots/webui-chat-artifacts-fixture-2026-11-23.jpg)

Synthetic demo · [Quick walkthrough and feedback form](START_HERE.md)

## Run with your credentials

Requires Docker with Compose v2. Python and uv run inside the containers.

```sh
git clone https://github.com/ottergottaott/retail-text-to-sql.git
cd retail-text-to-sql
cp deployment/live.env.example .env.providers
```

Edit `.env.providers`: set `GOOGLE_CLOUD_PROJECT` and choose your model API:

- **Direct Gemini:** `LLM_PROVIDER=gemini`, `GEMINI_API_KEY`, `GEMINI_MODEL`
  and `GEMINI_BASE_URL` (default: `https://generativelanguage.googleapis.com`).
- **OpenAI-compatible gateway:** `LLM_PROVIDER=openai_compatible`,
  `OPENAI_COMPATIBLE_BASE_URL` (your provider's API base URL, usually ending in
  `/v1`), `OPENAI_COMPATIBLE_API_KEY` and `OPENAI_COMPATIBLE_MODEL`.
  Google model-key settings are unused on this path.

Use a model ID enabled by your provider. The URL must match the selected API
protocol. Keep `EMBEDDING_PROVIDER=none` for the first launch.

Supply a Google application-default credential JSON with BigQuery query-job
permissions. Gemini and BigQuery use separate credentials.
[How to obtain credentials](docs/setup.md#credentials-checklist).

```sh
./start.sh --live --project retail-live --env-file .env.providers --google-credentials /absolute/path/google-credentials.json
```

Open **http://localhost:3000**. Sign in with `WEBUI_ADMIN_EMAIL` and
`WEBUI_ADMIN_PASSWORD` from the generated `.env.docker-retail-live`, then select
**Retail Intelligence**. Ask **Create and save a monthly revenue report.**
Open **Reports**, select the report and expand **Query evidence**.

The backend is at `http://localhost:8000`; its API reference is at `/docs`.
The source dataset is `bigquery-public-data.thelook_ecommerce`. You supply your
own keys and GCP project; model and BigQuery calls may incur charges. Credentials
are excluded from Git and container images. Startup readiness does not verify
cloud permissions or quota: submit a live question to check both integrations.

Rerun the same launch command to resume. Stop with
`./start.sh --stop --project retail-live`; Docker volumes retain data.

[CLI and reviewer walkthrough](START_HERE.md) ·
[Alternative model endpoints and troubleshooting](docs/setup.md)

## Optional fixture preview

`./start.sh` starts a separate synthetic demo without cloud keys. Its rule-based
planner supports examples such as `monthly revenue` and `save report`; this mode
does not test Gemini or BigQuery. Login details are in `.env.docker-retail-demo`.
Stop it before live startup, or choose different ports.

## How it works

The agent makes typed decisions inside a bounded LangGraph workflow. SQLGlot
validates generated SQL against four approved logical tables. The executor binds
those tables to product-scoped BigQuery sources, dry-runs queries and enforces
query, time, byte and result limits. One repair is allowed for repairable SQL errors.
Local PII scanning sanitizes copies before generation and embedding calls,
including retrieved examples; stored Golden Trios remain unchanged.

Golden Trio retrieval supplies question/SQL/report examples using lexical and
vector rankings with RRF fusion. Examples are versioned and filtered by access;
they provide methodology, not current facts. Embedding indexing is explicit.

Reports include evidence, limitations and proposed actions. Grounding review
precedes persistence in live mode. Reports are owner-scoped and checked against
current product permissions. Feedback enters an operator-reviewed publication
workflow; it never publishes itself automatically.

## Verification and limits

The last completed local suite passed **262 tests**, before the latest preference edits. The [review summary](docs/review-summary.md)
separates regression tests, historical live checks and current synthetic prompt
experiments. **Standard Ragas faithfulness: 0.756** on 19/20 synthetic
validation cases using WikiVibe Flash. One generation failed; evaluation is paused.
This evaluates report grounding against frozen SQL evidence, not end-to-end
accuracy or fresh BigQuery execution. The candidate has not been promoted.

The subsequent [focused privacy/workflow run](evaluation/model-payload-privacy-2026-11-23.json)
passed **109 local tests**, including outbound payload checks and preference application.
Providers were mocked; this does not replace a fresh live acceptance run.

Current schema metadata covers four approved logical tables. Personal format/depth
learning has a bounded, locally tested deterministic implementation.
Shared knowledge/tone promotion still uses operator review. Current brand/privacy changes still need live acceptance
with client credentials. Do not enter real PII into WebUI: it stores original
messages before backend sanitization.

## Further reading

- [Architecture and diagram](docs/architecture.md)
- [Requirements and implementation status](docs/acceptance-spec.md)
- [Evaluation evidence](docs/submission-evidence.md)
- [Shared tone and learning workflow](docs/improvement.md)
- [Developer setup](docs/setup.md#host-python-development)
