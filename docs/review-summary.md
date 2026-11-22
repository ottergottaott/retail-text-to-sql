# Retail Intelligence: review summary

[Start the demo](../START_HERE.md) · [Architecture](architecture.md) · [Acceptance spec](acceptance-spec.md)

A retail analysis assistant with Open WebUI and CLI interfaces sharing a
FastAPI/LangGraph backend. Gemini plans queries and reviews reports; BigQuery
execution is read-only and scoped to the manager's brands. The CEO sees all
brands. Privacy checks also apply to the CEO.

Reports include tables, SQL evidence, an HTML view and a saved-report library.
Personal format/depth preferences persist across chats. Automatic preference
learning, Golden Bucket updates and tone quality gates are documented designs;
the prototype's shared-knowledge publication uses operator review.

## Run it

With Docker and Compose v2 installed:

```sh
./start.sh
```

Open http://localhost:3000. Use the generated WebUI login in
`.env.docker-retail-demo`. This mode uses synthetic fixtures and requires no
cloud credentials. [Walkthrough](../START_HERE.md#five-minute-walkthrough).

For real queries, supply your own model-provider key, BigQuery execution project
and Google credential JSON. Both direct Gemini and Gemini via DeepInfra are
supported. [Credential and endpoint instructions](setup.md#credentials-checklist).

Default local endpoints: WebUI `http://localhost:3000`, backend
`http://localhost:8000`, API reference `http://localhost:8000/docs`.
These are local services; this repository does not include a hosted public API.

## Recorded checks

| Check | Result | Scope |
| --- | --- | --- |
| Regression suite | 252 passed | Controlled tests; brand access, stored artifacts and demographic privacy. [Evidence](../evaluation/client-alignment-2026-11-22.json) |
| Current Docker/CLI | 10 HTTP/CLI checks + 4 rerun checks passed | Fresh fixture deployment, retained login/report, installed-source match. [Evidence](../evaluation/client-runtime-2026-11-22.json) |
| Current browser smoke | Report library, embedded report, separate tab and SQL highlighting checked | Fixture data; screenshots linked in [runtime evidence](../evaluation/client-runtime-2026-11-22.json). |
| Historical live SQL/save/structure | 12 selected reports | 11/12 initial passes plus 1/1 recheck; 13 requests, retail-v7. [Evidence](../evaluation/live-business-pro-final-2026-11-21.json) |
| Historical live faithfulness | Ragas 0.534; custom SQL-aware 0.843 | Different judge contracts, 12 reports each. Neither is overall accuracy. [Evidence](../evaluation/faithfulness-pro-live-results-2026-11-21.json) |
| Historical retrieval | Recall@2 1.00 on 40 positive cases | Synthetic English cases with cached live embeddings. [Evidence](../evaluation/retrieval-gate-2026-11-21/english-results.json) |
| Historical browser acceptance | 17/21 passed; 4 untested | Local headless Chrome; [scope and limits](../evaluation/browser-acceptance-2026-11-22.json). |

## Remaining checks

The current `retail-v9-client-policy` changes await live Gemini/BigQuery
acceptance. Historical live results do not validate the new brand/privacy
policy, and no faithfulness improvement is claimed for this release.

Human report review, installation on another machine and optional live Langfuse
delivery remain unverified. Browser smoke does not establish downloaded-file
persistence, native fullscreen or live browser fault handling. Cross-question
privacy inference protection is a documented production extension.

The [HTML review page](review-summary.html) is available for local viewing.
