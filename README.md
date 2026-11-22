# Retail Intelligence

A retail analysis assistant built with Python, LangGraph, Gemini and BigQuery.
Ask a business question, inspect the SQL and results, and save an HTML report.
The CLI and Open WebUI use the same backend.

## Start here

- [Reviewer guide and Docker/WebUI walkthrough](START_HERE.md)
- [Architecture overview](docs/technical-overview.html) and [technical design](docs/architecture.md)
- [Evaluation evidence and limitations](docs/submission-evidence.md)

## Quick start: no credentials required

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). Run from the repository root:

```sh
uv sync --frozen --extra dev
uv run uvicorn retail.api:create_app --factory --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
export RETAIL_API_TOKEN=alice-local-token
uv run retail --once 'monthly revenue' --json
uv run retail
```

This is **fixture mode**: synthetic data and a small rule-based planner. It
shows workflows and safety mechanics, not live model reasoning. Try
`monthly revenue`, `compare products`, `save report` and `list reports`.
The interactive CLI retains the conversation. Deletion requires an explicit
application confirmation command after a preview.

SQLite persists state in `retail.db`. Alice can analyze products 1/2; Bob
(`bob-local-token`) can analyze product 3. These are demo identities and tokens.
For the browser demo, follow [Docker/Open WebUI setup](START_HERE.md#credential-free-docker-demo).

## Live Gemini and BigQuery

Follow [live setup](docs/setup.md#live-gemini-and-bigquery) and use
[.env.example](.env.example) as a configuration reference. You need:

- Google application-default credentials and a BigQuery execution project.
- A Gemini API key and model name. Gemini via DeepInfra is also supported.
- Replacement API tokens, a dedicated label secret and explicit product entitlements.

The dataset is `bigquery-public-data.thelook_ecommerce`. Live model, embedding
and BigQuery calls may incur charges. No credentials are included. The default
configuration remains fixture mode; API health does not establish provider readiness.

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

The latest local regression run passed 216 tests. Evaluators separately measure
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
