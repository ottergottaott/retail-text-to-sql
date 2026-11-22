# DeepInfra provider adapters

`retail/deepinfra.py` provides two narrow, OpenAI-compatible adapters selected
through `retail/providers.py`. `LLM_PROVIDER` selects chat independently from
`EMBEDDING_PROVIDER`; both default to the existing direct Google path.
`LLM_PROVIDER=deepinfra` and `EMBEDDING_PROVIDER=deepinfra` select these adapters
in live agent mode. Fixture mode retains its deterministic model. The admin
index command and live retrieval evaluator also use the selected encoder.

## Configuration and endpoint

The adapters read three fields supplied by the parent-owned `Settings`:

- `deepinfra_api_key`
- `deepinfra_model` (for example `google/gemini-3.5-flash`)
- `deepinfra_embedding_model` (for example `Qwen/Qwen3-Embedding-8B`)

The origin is fixed at `https://api.deepinfra.com/v1/openai`. There is no
configurable endpoint or base URL, so a compromised configuration value cannot
redirect requests to an untrusted host. The key is sent only as an
`Authorization: Bearer` header and is never logged, returned or embedded in
error text.

## `DeepInfraModel.decide(context, remaining_seconds)`

Returns `(Decision, usage)` and reuses the existing `SYSTEM` prompt and
`Decision` schema from `retail/model.py`.

- `POST /chat/completions` with the configured model.
- System message is the shared `SYSTEM` text; the user message is the serialized
  context (JSON, `default=str`).
- `temperature=0`, `max_tokens=6000`.
- `response_format` requests a JSON schema named `decision` built from
  `Decision.model_json_schema()`; the returned content is validated with the
  same Pydantic model.
- No automatic retries and no provider SDK. One request per call.
- Timeout is `min(30, remaining_seconds)` seconds and must be finite and
  positive. An expired, zero, negative, NaN or infinite budget refuses the call
  before any request.
- Any HTTP status error, transport error, malformed JSON, missing choice or
  invalid `Decision` raises `ModelError` with a generic message. Response bodies,
  request content and secrets are not included.

Usage is provider-measured metadata mapped to the existing telemetry shape:

```json
{
  "input_tokens": 11,
  "output_tokens": 7,
  "total_tokens": 18,
  "thought_tokens": 3,
  "usage_source": "provider_measured",
  "cost": null
}
```

`thought_tokens` comes from `usage.completion_tokens_details.reasoning_tokens`
when present. Missing or non-integer token fields become `null`. `cost` is always
`null`; this adapter does not estimate price.

## `DeepInfraEmbeddings.embed(texts, task, timeout=10)`

Returns one vector per input text, in input order.

- `POST /embeddings` with the configured embedding model and an explicit
  `dimensions=1024` request.
- For `task == "RETRIEVAL_QUERY"` only, each text is prefixed with the
  evaluated baseline retrieval instruction (this does not perform web search):

  ```text
  Instruct: Given a web search query, retrieve relevant passages that answer the query
  Query: <text>
  ```

  Documents and other tasks are sent unchanged.
- `version` binds provider, model, dimensions and query-instruction revision:

  ```text
  deepinfra:<model>:dim=1024:instruction=instruct-v1
  ```

  A provider/model/dimension/instruction change therefore produces a different
  index identity and requires reindexing.
  The retail-specific `retail-trios-v2` wording was evaluated on 98 synthetic
  cases and rejected: hybrid Recall@2 fell from 0.8375 to 0.75 at the same 0.65
  similarity threshold. See `evaluation/retrieval-instruction-ab-2026-11-21/`.
- Timeout must be finite and positive; it is capped at 15 seconds. Invalid
  timeouts and empty batches are handled without a request (empty input returns
  `[]`).
- The response batch must contain exactly one item per input. Every item must
  have an integer, non-boolean `index` that is unique and within
  `0..len(inputs)-1`. Items may arrive out of order; vectors are re-sorted by
  index before being returned so callers can pair them with the original texts.
- Each vector must be a non-empty list of exactly 1024 finite numeric values.
  Booleans, strings, NaN and infinities are rejected.
- All failures raise `EmbeddingUnavailable` with
  `"Semantic retrieval unavailable; using lexical search."`; provider response
  bodies and secrets never appear in the message. The caller keeps its existing
  lexical fallback.

## Testing

`tests/test_deepinfra.py` uses `httpx.MockTransport` through a factory that
retains the real `httpx.Client`. The tests make no live calls, read no secrets
and do not load environment configuration. They cover request shape and schema,
usage mapping, expired/non-finite budgets, timeout bounds, sanitized HTTP and
transport failures, invalid decisions, query-instruction scoping, out-of-order
embedding indices, malformed vectors, index cardinality/range/uniqueness and
invalid embedding timeouts.

```sh
.venv/bin/python -m pytest tests/test_deepinfra.py -q
```

Passing these tests proves adapter mechanics only. Separately, on2026-11-21
real calls verified structured Gemini chat (`google/gemini-3.5-flash`) and
1024-dimensional Qwen embeddings (`Qwen/Qwen3-Embedding-8B`) through DeepInfra.
The retail and pinned WikiSQL evaluations measured actual embedding relevance;
see [results](../evaluation/retrieval-results-2026-11-21.md). The protected key
was used privately. Direct Google API and BigQuery remain unverified.

The agent passes approved SQL functions and supported aggregation/date examples
in `sql_capabilities`, shared by both model adapters. Unsupported functions
remain terminal policy errors; SQLGlot boolean operators AND/OR/NOT are accepted
as predicate structure, with all descendants still validated.
## Optional final reviewer

`DEEPINFRA_REVIEW_MODEL` selects a separate model for the single final grounding
revision of live analytical drafts. Empty uses the planning model. The configured
host verification uses `google/gemini-3.5-flash` for planning and
`google/gemini-3.1-pro` for review; both remain Gemini through DeepInfra. This is
not fallback: reviewer failure returns an error and saves no completed draft.
Review shares the existing turn call/time/context limits and runs no tools.
Telemetry records the actual review model and `phase=report_review`.

A two-record fixed-evidence experiment showed Pro removing an unsupported
no-discounts conclusion, with measured review calls about 14 and 18 seconds.
That small experiment does not establish general model superiority. Full live
results and advisory judge scores are linked from `docs/final-acceptance.md`.
Google's SDK `response_schema` cannot represent conditional `allOf`; the common
Decision schema requires text, while DeepInfra alone adds the nonempty-answer
condition. Application checks reject blank answers for both providers.
