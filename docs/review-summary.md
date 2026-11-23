# Retail Intelligence: review summary

[Launch with your credentials](../README.md#run-with-your-credentials) · [Screenshots and walkthrough](../START_HERE.md) · [Architecture](architecture.md)

Open WebUI and CLI share a Python/FastAPI and LangGraph backend. Gemini plans
analysis and reviews reports. SQLGlot validates read-only SQL before scoped,
budgeted BigQuery execution. PostgreSQL stores reports, preferences and Golden
Trios. Langfuse is optional and off by default.

Brand managers analyze their assigned brands; the CEO sees all brands. Privacy
rules still apply to the CEO. Reports retain SQL evidence. Personal preferences
persist across sessions; feedback and CEO tone changes use automatic quality
gates with scoped publication, version history and rollback.

## Run it

Supply a Gemini key/model, BigQuery project and separate Google credential JSON
using [the README setup](../README.md#run-with-your-credentials), then launch:

```sh
./start.sh --live --project retail-live --env-file .env.providers --google-credentials /absolute/path/google-credentials.json
```

Open `http://localhost:3000`, sign in using `.env.docker-retail-live` and select
**Retail Intelligence**. Ask **Create and save a monthly revenue report**.
Open **Reports → Query evidence → Open tab**. The API reference is at
`http://localhost:8000/docs`.

## Latest evidence

| Check | Result | Coverage |
| --- | ---: | --- |
| Local regression suite | **308 passed** | [Safety, retrieval, preferences, learning and evaluator checks](../evaluation/faithfulness-debug-2026-11-23/regression.xml) |
| Standard Ragas, validation | **0.683 → 0.718** | 20/20 baseline; 20/20 candidate |
| Standard Ragas, reserved test | **0.752** | 20/20 candidate; not used for tuning |
| Custom SQL-aware, validation / test | **0.988 / 1.000** | 20/20 each; separate metric contract |
| Answer tables and structure | **20/20 validation; 20/20 test** | Exact frozen-row checks |
| Automatic learning browser smoke | **5 checks passed** | [Fixture feedback, tone and rollback](../evaluation/automatic-learning-browser-2026-11-23.json) |

Generation and judging used WikiVibe's `gemini-3.8-flash` gateway alias. These
scores cover report review over frozen synthetic SQL results and supplied schema,
not live SQL execution or overall accuracy. The two metrics have different
contracts. One repetition; same-model judging can introduce bias. The paired family-bootstrap
interval includes zero, so a reliable improvement is not established. Validation was
previously exposed; reserved test cases were not used for tuning.
[Protocols, retained failures and complete results](../evaluation/faithfulness-debug-2026-11-23/README.md).

## Other recorded checks

- [Clean Docker startup](../evaluation/client-startup-2026-11-23.json): fixture workflow and intercepted direct-Gemini transport; synthetic credentials.
- [Docker/CLI workflow](../evaluation/client-runtime-2026-11-22.json): 10 checks plus 4 rerun checks with fixture data.
- [Historical live BigQuery reports](../evaluation/live-business-pro-final-2026-11-21.json): 11/12 initial passes plus 1/1 recheck; 13 requests, retail-v7.
- [Historical browser acceptance](../evaluation/browser-acceptance-2026-11-22.json): 17/21 passed; 4 untested.
- [Historical live faithfulness](../evaluation/faithfulness-pro-live-results-2026-11-21.json): standard 0.534 and custom SQL-aware 0.843 on 12 reports; different prompts/evidence from the latest experiment.

## Limits

Fresh direct-Gemini/client-BigQuery acceptance, another-machine installation,
human report acceptance and optional live Langfuse delivery remain unverified.
Historical live results do not validate the current brand/privacy policy.
Browser checks do not establish native fullscreen, downloaded-file persistence
or live fault handling. Cross-question privacy inference protection is a
[documented production extension](architecture.md).
