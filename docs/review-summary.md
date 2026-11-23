# Retail Intelligence: review summary

[Start the demo](../START_HERE.md) · [Architecture](architecture.md) · [Acceptance spec](acceptance-spec.md)

A retail analysis assistant with Open WebUI and CLI interfaces sharing a
FastAPI/LangGraph backend. Gemini plans queries and reviews reports; BigQuery
execution is read-only and scoped to the manager's brands. The CEO sees all
brands. Privacy checks also apply to the CEO.

Reports include tables, SQL evidence, an HTML view and a saved-report library.
Personal format/depth preferences persist across chats. Current-turn overrides
and bounded learning from repeated presentation directives passed focused local
checks. Automatic Golden Bucket updates and tone
quality gates remain designs; shared-knowledge publication uses operator review.

## Run it

Start with [the README credential setup](../README.md#run-with-your-credentials).
Supply your Gemini API key/model, a BigQuery execution project and Google
credential JSON, then launch:

```sh
./start.sh --live --project retail-live --env-file .env.providers --google-credentials /absolute/path/google-credentials.json
```

Open `http://localhost:3000` and sign in using `.env.docker-retail-live`.
Select **Retail Intelligence**, ask **Create and save a monthly revenue report**,
then inspect **Reports → Query evidence → Open tab**.
The backend is at `http://localhost:8000`, with its API reference at `/docs`.

An optional `./start.sh` fixture preview uses synthetic data without cloud keys;
it does not test either provider. [Walkthrough](../START_HERE.md).

## Recorded checks

| Check | Result | Scope |
| --- | --- | --- |
| Clean client startup | Fixture workflow and direct-Gemini startup passed; 24 local tests passed | Clean git archive and new Docker volumes. Direct startup used synthetic credentials; Google SDK HTTP transport was intercepted. No real Google/BigQuery calls. [Evidence](../evaluation/client-startup-2026-11-23.json) |
| Outbound privacy / workflow follow-up | 109 passed | Local synthetic PII, mocked model/embedding boundaries, retrieval, brand/cohort guards and preference application. No new live calls or full-suite rerun. [Evidence](../evaluation/model-payload-privacy-2026-11-23.json) |
| Latest regression suite | 262 passed | Predates the latest preference edits. Controlled tests, including custom-gateway evaluation routing and empty-result oracle wording. [Evidence](../evaluation/wikivibe-flash-iteration-2026-11-23/regression-empty-wording.xml) |
| Latest Flash validation candidate | Standard Ragas: **0.756** | 19/20 synthetic cases scored; one generation failed. WikiVibe / gemini-3.8-flash, same generator/judge. Evaluation paused; no promotion. [Evidence](../evaluation/wikivibe-flash-iteration-2026-11-23/candidate-v2-validation/results.json) |
| Latest Flash development pilot | Standard Ragas: baseline 0.755; candidate v2 0.787 | 8 synthetic cases / 4 families per variant; same generator/judge. Difference interval includes zero; no promotion. Validation on 20 cases is incomplete and paused. [Protocol and results](../evaluation/wikivibe-flash-iteration-2026-11-23/README.md) |
| Regression suite | 253 passed | Controlled tests; brand access, stored artifacts and demographic privacy. [Evidence](../evaluation/client-alignment-2026-11-22.json) |
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
