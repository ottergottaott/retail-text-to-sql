# Architecture

One Python backend serves Open WebUI and the CLI. The backend owns authorization,
SQL execution and report persistence; clients send requests and display progress.

## Analysis request

```mermaid
flowchart LR
  UI[WebUI / CLI] --> API[Identity and brand access]
  API --> Agent[LangGraph agent]
  Retrieval[Authorized Trio retrieval] -->|selected examples| Agent
  Agent -->|copy of complete model context| Privacy[Local PII sanitization]
  Privacy -->|sanitized payload only| Model[Gemini]
  Model -->|typed decision| Agent
  Agent --> SQL[SQL validation and scoped execution]
  SQL --> BQ[BigQuery]
  BQ -->|approved columns, hashed IDs, cohort checks| SQL
  SQL -->|query evidence| Agent
  Agent -->|reviewed answer| Reports[Saved reports and response]
```

## 1. Indexing — explicit administrator operation

```mermaid
flowchart LR
  Originals[(Published Golden Trios: originals)] -->|copy: question, tags, report| Privacy[Local PII sanitization]
  Privacy --> Embeddings[Embedding provider]
  Embeddings --> Vectors[(Stored document vectors)]
```

Run indexing when published examples or the embedding/privacy version change.
It prepares document vectors; it does not run on each question. Originals remain
unchanged. Index records identify the Trio, version and embedding model. PostgreSQL currently stores
original Trios and embedding JSON records; similarity is computed in Python.
pgvector is a possible scaling extension, not a current dependency. Publication
SQL, scope, schema and evaluation checks are separate from retrieval.

## 2. Search — on each question

```mermaid
flowchart LR
  Store[(Golden Trios and stored vectors)] --> Filter[Latest version, schema and access filter]
  Filter --> Rank[Rank permitted examples: lexical + vector]
  Question[Analysis question] --> Rank
  Question -->|copy| Privacy[Local PII sanitization]
  Privacy --> Embeddings[Embedding provider]
  Embeddings -->|query vector| Rank
  Rank -->|top-k example copies| Agent[Agent context]
```

Access is checked **before either ranking**. First resolve the latest published
version and compatible schema, then keep only examples permitted for this user.
Lexical and vector scores are computed within that permitted set. Only then are
top-k examples selected. The current implementation applies these filters in
Python before scoring; it does not perform an unrestricted top-k search followed
by access filtering. The full model context is sanitized at the Gemini boundary
shown above.

These diagrams show the implemented data flow. Local operations stay inside the
application. PII sanitization transforms copies sent to generation/embedding
providers; it does not delete Trio fields or overwrite stored originals.
SQL validation separately prevents queries from accessing restricted columns.

## 3. Automatic improvement — outside the analysis request

```mermaid
flowchart LR
  Feedback[Answer feedback + evidence snapshot] --> Jobs[(Durable jobs)]
  CEO[CEO tone request] --> Jobs
  Jobs --> Worker[API background worker]
  Worker --> Local[Access, SQL, evidence and privacy checks]
  Local --> Privacy[Sanitized evaluation context]
  Privacy --> Model[Configured model quality gate]
  Model --> Pass{Pass?}
  Pass -->|knowledge| Trios[(Versioned scoped Trios)]
  Pass -->|tone| Tone[(Active tone version)]
  Pass -->|no| Retained[Retain feedback / keep previous tone]
  Trios --> Retrieval[Next-query retrieval]
  Tone --> Agent[Next-turn presentation]
```

Helpful responses require evidence-grounding checks. Corrections additionally
require an exact matching approved definition and equivalent SQL/results; arbitrary
user corrections are not truth labels. CEO tone uses fixed synthetic render/judge
cases, numeric/privacy checks and version rollback. Worker retries are bounded;
no separate queue service is required. [Flow and limits](improvement.md).

## Current request path

1. Resolve identity and brand scope; use the original question for local retrieval
   and load permitted context.
2. Retrieve relevant Question → SQL → Report examples as methodology. Scan outgoing
   embedding text and retrieved copies locally; keep stored Trios unchanged.
3. Scan the complete planning/review payload locally, then ask the model for a
   typed decision; validate and dispatch it in trusted code.
4. Validate SQL, bind authorized sources, dry-run BigQuery and execute within budgets.
   Allow one repair for a repairable SQL error.
5. Review the draft against query evidence, then return the answer and save if requested.

## Safety boundaries

- Managers analyze their brands; the CEO sees all brands. Source binding enforces scope.
- Database identifiers such as names, email, street address, postal code, exact coordinates
  and IP address are excluded from approved analytical sources before model context.
  Customer keys are hashed pseudonyms;
  demographics are aggregate-only with a configurable minimum cohort (default 5).
- SQLGlot validates the AST, approved tables and functions. Execution is read-only,
  with query, byte, row, time and model-call limits.
- Saved reports are owner-scoped and checked against current access. Deletion requires
  an explicit user confirmation command after a preview.
- Golden Trio publication checks SQL, declared scope, schema and evaluation evidence.
  Retrieval filters latest published examples by schema and access, then sanitizes
  copies, including question, SQL and report. The same local scan protects document
  and query embeddings, planning, history, tool results and grounding review.
  Stored fields and original values are retained; they are not sent unchanged.
- The outbound scan combines local English PERSON NER with field/pattern rules
  for names, contacts, street addresses, postal codes, exact coordinates, IPv4/IPv6
  and raw customer IDs. Customer pseudonyms use keyed HMAC. Aggregate geography
  is retained; SQL cohort/privacy rules remain a separate enforcement boundary.
  Detector failure blocks the call. Embedding keys include the privacy policy
  version and sanitized document, preventing reuse of the previous raw-text index.

## State and deployment

Docker Compose runs the API, PostgreSQL and Open WebUI. Gemini and BigQuery are
external; reviewers provide their endpoint, model key and Google credentials.
Conversations, saved reports, preferences and versioned knowledge persist in SQL.
The synthetic offline mode uses SQLite/DuckDB. Langfuse is optional and off by default.

## Current limits

Schema metadata is a static four-table contract. Bounded personal preference
learning and automatic feedback/tone gates have local test coverage; live
acceptance of the new workflows remains pending. Broad arbitrary-correction
learning and multi-replica scheduling remain extensions.
Conversations persist, but mid-turn recovery does not.
Local NER and pattern rules can miss PII or mask non-sensitive text; this is not
a complete detector for arbitrary prose, languages or address formats.
WebUI stores original messages before backend sanitization: do not submit real PII.
Current brand/privacy changes still require live acceptance with client credentials.

[Visual overview](architecture.html) · [Full technical design](architecture-design.md) ·
[Detailed diagrams](architecture-details.html) · [Requirements](acceptance-spec.md) ·
[Measured results](review-summary.md)

### Privacy coverage and remaining gap

Trusted database projections exclude first/last names, email, street address,
postal code, exact coordinates and IP addresses before query results reach an
LLM. Pseudonymous customer keys are permitted. Demographic results require grouped
aggregates and at least `MINIMUM_COHORT_SIZE` distinct customers (default 5);
individual demographic listings and demographic-filtered customer rankings are
blocked. City, gender and traffic source are currently unavailable in the logical
schema, so they cannot be queried; state, country and age bands are supported.

Outbound protection now scans local copies using the packaged English spaCy
PERSON model and explicit field/pattern recognizers. It runs before embeddings
and generation, including after retrieval of legacy Trios. The model is installed
at build time; there is no runtime download or external detection call. Detector
failure prevents egress. Stored originals and Trio structure remain unchanged.

NER is probabilistic. Unlabelled postal codes, unusual addresses, obfuscated PII
and unsupported languages may evade recognition; names can also be overmasked.
Individual demographic narratives in imported free text do not have the same
provable cohort enforcement as executable SQL. WebUI and the database retain
original text, so access and retention controls still matter. These local checks
do **not** prove that arbitrary user-supplied PII can never reach a model. Do not
submit real PII; production requires broader labelled detection/recall acceptance.

[Detector package and model installation](https://spacy.io/usage/models)
