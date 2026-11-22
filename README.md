# Retail Intelligence

A retail analysis assistant built with Python, LangGraph, Gemini and BigQuery.
Ask a business question, inspect the SQL and results, and save an HTML report.
The CLI and Open WebUI use the same backend.

## Start here

- [Reviewer guide and Docker/WebUI walkthrough](START_HERE.md)
- [Architecture overview](docs/technical-overview.html) and [technical design](docs/architecture.md)
- [Evaluation evidence and limitations](docs/submission-evidence.md)

## Quick start: no credentials required

Requires Docker with Compose v2 (macOS, Linux or WSL). From the repository root:

```sh
./start.sh
```

Open **http://localhost:3000** and select **Retail Intelligence**. The script
creates a private `.env.docker-retail-demo`; use its `WEBUI_ADMIN_EMAIL` and
`WEBUI_ADMIN_PASSWORD` to sign in. It installs the Pipe, Reports library,
feedback and preference pages. Python and uv run inside Docker.

CLI against the same demo:

```sh
docker compose -p retail-demo --env-file .env.docker-retail-demo exec -e RETAIL_API_TOKEN=alice-local-token api retail --once 'monthly revenue' --json
```

This is **fixture mode**: synthetic data and a small rule-based planner. It
shows workflows and safety mechanics, not live model reasoning. Try
`monthly revenue`, `compare products`, `save report` and `list reports`.
The interactive CLI retains the conversation. Deletion requires an explicit
application confirmation command after a preview.

Docker volumes persist PostgreSQL, reports and WebUI data. Alice can analyze products 1/2; Bob
(`bob-local-token`) can analyze product 3. These are demo identities and tokens.
Stop with `./start.sh --stop`; rerun `./start.sh` to resume. For alternate ports
and the walkthrough, see [the reviewer guide](START_HERE.md#credential-free-docker-demo).

## Live Gemini and BigQuery

Follow [live setup](docs/setup.md#live-gemini-and-bigquery) and use
[.env.example](.env.example) as a configuration reference. You need:

- Google application-default credentials and a BigQuery execution project.
- A Gemini API key and model name. Gemini via DeepInfra is also supported.
- Replacement API tokens, a dedicated label secret and explicit product entitlements.

The dataset is `bigquery-public-data.thelook_ecommerce`. Live model, embedding
and BigQuery calls may incur charges. No credentials are included. The default
configuration remains fixture mode; API health does not establish provider readiness.

Copy [deployment/live.env.example](deployment/live.env.example) to `.env.providers`,
fill in your project/model/key, then run:

```sh
./start.sh --live --project retail-live --env-file .env.providers --google-credentials /absolute/path/google-credentials.json
```

A runtime copy of the Google JSON is kept under a private `.local/docker-retail-live/`
directory and mounted read-only; the source file is unchanged. The private generated
`.env.docker-retail-live` keeps local application/login secrets across restarts.
Use different ports if the demo is still running. Startup does not run model
evaluations or embed the corpus; live chat and explicit indexing may incur charges.

## Shared report tone

Edit [deployment/tone.txt](deployment/tone.txt), then publish it:

```sh
./start.sh --tone deployment/tone.txt --reviewer owner
```

For a live deployment, add `--live --project retail-live`. The next turn uses
the new shared tone without a restart. Versions are recorded; publish an older
text again to roll back. Personal format/depth preferences remain per user.
This is an operator command; a tone editor in WebUI is not implemented.
The fixture planner does not demonstrate arbitrary tone changes; live generation
receives the versioned tone in its context.

## How it works

The agent makes typed decisions inside a bounded LangGraph workflow. SQLGlot
validates generated SQL against four approved logical tables. The executor binds
those tables to product-scoped BigQuery sources, dry-runs queries and enforces
query, time, byte and result limits. One repair is allowed for repairable SQL errors.

Golden Trio retrieval supplies question/SQL/report examples using lexical and
vector rankings with RRF fusion. Examples are versioned and filtered by access;
they provide methodology, not current facts. Embedding indexing is explicit.

Reports include evidence, limitations and proposed actions. Grounding review
precedes persistence in live mode. Reports are owner-scoped and checked against
current product permissions. Feedback enters an operator-reviewed publication
workflow; it never publishes itself automatically.

## Tests and evaluations

```sh
uv run pytest -q
uv run python -m retail.evaluate --output /tmp/retail-evaluation.json
uv run python scripts/verify_offline.py --output /tmp/retail-workflow.json
```

The latest local regression run passed 221 tests. Evaluators separately measure
SQL results, retrieval ranking, workflow safety and report faithfulness. Live
checks and synthetic tests have different evidence boundaries. There is no single
overall accuracy score or automated GitHub Actions gate yet.

See [recorded evidence](docs/submission-evidence.md),
[retrieval evaluation](docs/retrieval-verification.md) and
[Ragas/Langfuse experiments](docs/faithfulness-experiments.md). Paid evals require
explicit opt-in. The latest 80-case synthetic study is incomplete after provider
balance exhaustion; its candidate was not promoted. Serving remains retail-v8.

## Privacy and prototype limits

Direct customer identifiers are excluded from the analytical schema. Customer
keys are pseudonyms, not anonymity. Input/output pattern checks supplement source
restrictions; they are not a complete PII detector. WebUI stores original messages
before backend sanitization: do not enter real PII into this demonstration.

Production requires governed database access, approved small-group disclosure
rules, retention policies and organizational identity integration. Schema metadata
is a static four-table contract. Automated preference inference, a full persona
editor and durable mid-turn recovery remain design work. Human report acceptance
and installation on another machine remain open.

## Project layout

- `retail/`: agent, SQL boundary, providers, retrieval, storage and presentation.
- `integrations/`: Open WebUI Pipe, Actions and authenticated report pages.
- `tests/`: controlled regression and local integration tests.
- `scripts/`: setup, verification and opt-in evaluation tools.
- `evaluation/`: datasets and dated evidence, including unsuccessful attempts.
- `docs/`: setup, architecture and operations. Dated plans and acceptance documents
  are historical records; start with this README and START_HERE.
