# Prompt and tool decision contract

## Actual protocol

The current providers use **structured JSON decisions**, not native provider
`tools`/`tool_calls` messages. Both use the same `SYSTEM` string from
`retail/model.py` and the Pydantic `Decision` contract. The backend, not the
model provider, dispatches the validated action in the LangGraph Tool node.

- Google: `system_instruction=SYSTEM`, JSON response MIME type, `response_schema=Decision`.
- DeepInfra: system message `SYSTEM`, user message containing JSON context,
  `response_format.type=json_schema`; the schema also requires nonempty answer text.
- Temperature 0, up to 6000 output tokens per call. Provider attempts and the
  graph have bounded time/call/query budgets. Temperature 0 is not deterministic execution.

Exact exported snapshots: [system prompt](prompts/system.txt),
[base decision schema](prompts/decision.schema.json),
[DeepInfra schema](prompts/deepinfra-decision.schema.json).
Runtime source remains authoritative. Snapshot hashes are in [manifest](prompts/manifest.json).

## What the model receives

`Agent.context` constructs a JSON object with the current question, scoped recent
history, provenance-backed prior analysis, safe logical schema, allowed SQL
capabilities, authorized products, trusted execution-scope description, per-user
preferences, versioned presentation persona and relevant permitted Golden Trios.
Each later planning call includes accumulated tool results. Credentials and raw
source-table access are never supplied. Query results can contain pseudonymous
customer keys; those are linkable labels, not anonymous data.

## Available actions

| Action | Arguments / meaning | Backend boundary |
| --- | --- | --- |
| `query` | `sql` over the logical schema | AST validation, source binding, time/byte/row budgets |
| `schema` | Return approved schema | Static safe contract; no raw sample rows |
| `answer` | `text` grounded in query evidence | Evidence required; live analytical drafts undergo review |
| `clarify` | `text` asking for a definition | Stops without inventing analysis |
| `save_report` | `title` for current/latest analysis | Save confirmed by actual persistence, not model text |
| `list_reports` | List current user's reports | Owner and current product scope |
| `open_report` | `report_id` | Owner and scope checked again |
| `delete_reports` | `phrase` or `current_conversation` | Preview only; separate explicit confirmation |
| `preference` | Both `format` and `depth` | Enumerated explicit choices, per-user persistence |

The prompt defines Complete-item revenue, consistent populations and grain,
ambiguity handling, evidence citations, limits on causal claims, and correct
save/delete behavior. These instructions guide the model; access control and SQL
safety are enforced independently in code.

## Final grounding review

The live answer path adds `report_review.draft` to the same original context and
tool evidence. The prompt then requires `action=answer`, forbids further tools,
and asks the reviewer to remove unsupported factual premises. The draft is not
evidence. A stronger review model can be configured independently. A failed review
does not save an unreviewed draft. This is a quality layer, not proof of correctness.

## Separate embedding instruction

Qwen query embeddings currently prepend the versioned baseline instruction in
`retail/deepinfra.py` (`instruct-v1`). It mentions a web search query and relevant
passages; **it does not trigger web search**. It only formats the embedding input.
The actual retrieved documents are local permitted Question → SQL → Analyst Report
records. A retail-specific alternative was measured, but the baseline remained
the default. See [retrieval results](retrieval-relevance-results.md).

## Current prompt revision

`retail-v8` changes only deferred-save semantics following a complete paired experiment and independent DeepSeek critique. A pending save is not a persistence receipt; backend appends confirmation after successful review and storage. Missing confirmation is not proof that saving never happened. See [prompt improvement evidence](prompt-improvement.md).
