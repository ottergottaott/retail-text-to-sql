# Automatic learning and report tone

## Personal preferences

Format/depth are stored per authenticated user and survive chats. Current-turn
instructions override saved settings; personal preferences layer over org tone.
Repeated supported English presentation directives are learned after two signals;
“from now on” saves immediately. My preferences allows inspection, override and
reset. These settings cannot change access, PII rules or admin-owned defaults.

## Feedback → Golden Trios

Use **Give feedback** under an answer. Feedback is bound to that response and an
immutable snapshot of its completed query evidence, not the conversation's latest
analysis. The page shows whether automatic checks published or retained it.

The API worker polls durable SQL-backed jobs every five seconds by default:

1. Recheck the user's current access against the original response scope.
2. Require one complete, nonempty query result. Missing/truncated/multi-query
   evidence stays out of automatic publication.
3. For **Helpful**, check SQL and evaluate report grounding and question relevance
   against the response's evidence. A positive rating alone is not a quality pass.
4. For **Needs correction**, require an exact question match to an existing
   approved, accessible definition. Generate a candidate, require its normalized
   SQL to match that independent reference, execute candidate/reference under the
   same access policy and compare complete results. A model gate additionally
   checks the report and correction. Unsupported corrections are retained with a
   reason; user comments never become the truth oracle.
5. Publish passing examples automatically in their original brand/product scope,
   with evaluation provenance and content deduplication. No manual approval step.
   Retrieval can use them on the next query. They are methodology, not fresh facts.

**Incomplete** feedback is retained without publishing an example. Gate failures
also retain feedback. Dependency failures retry after 60 seconds, up to three
attempts. Pending jobs survive restarts; expired claims are recovered. Originals
stay in storage; copies sent to models are locally sanitized. The fixture path
uses completed synthetic response checks and is labeled as such, not LLM judging.

New examples are immediately available to lexical retrieval. Document embeddings
remain a separate explicit indexing operation (`retail-admin index`), keeping
embedding-provider calls outside the analysis request path.

## CEO report tone

Open **My preferences** while signed in as the configured CEO. The organization
section accepts a presentation-style request and shows tone history and rollback.
Managers cannot submit or roll back organization tone; WebUI administrator status
alone does not grant CEO access.

Submitting a tone queues an automatic gate on two fixed synthetic reports. Live
mode makes at most four configured-model calls: render/judge for each case. Local
checks require preserved numeric literals and no detected PII; the model rubric
checks factual/metric/limitation preservation and requested tone adherence.
Instructions to change policy are rejected. These bounded checks are safeguards,
not a calibrated proof of general report quality.

Passing requests activate a new version automatically. Failed or incomplete gates
keep the previous tone. Newer requests supersede older ones; crash recovery does
not reactivate a completed job. Rollback appends a version of a previously stored
tone without editing code or redeploying. Existing reports remain snapshots.
Fixture mode supports a small deterministic set of concise/plain/professional
styles; arbitrary style evaluation requires the configured live model.

## Runtime and boundaries

No extra service or broker is required. The existing API process owns one worker.
`AUTOMATION_ENABLED=true` and `AUTOMATION_POLL_SECONDS=5` are defaults; disabling
it retains feedback jobs and prevents new tone submissions. Live evaluation uses
the same configured provider/model and credentials as analysis. Helpful feedback
uses one model call; a validated correction uses at most two model calls and two
bounded SQL executions. Each job has an 85-second orchestration budget, at most
two jobs per polling batch, context bounds and safe error messages.

The implementation is for a single API process. Replica-wide scheduling, retention,
held-out rollout gates, calibrated independent judges and broad correction coverage
remain production work. Persisted compare-and-set claims prevent two workers from
claiming the same revision, but do not make all publication side effects a single
transaction. Avoid running multiple schedulers in this prototype.

Local tests cover automatic execution without an operator, restart recovery,
access shrinkage, response binding, deduplication, rejected corrections, successful
reference-checked corrections, tone failures, permissions and rollback. [Scoped browser checks](../evaluation/automatic-learning-browser-2026-11-23.json)
cover feedback application, tone activation/rejection and rollback using fixture
data and a local test proxy. Live Hydrogen smoke results are recorded separately;
fresh client Gemini/BigQuery and native WebUI acceptance remain pending.

## Optional operator tools

`retail-admin candidate`, `review` and `index` remain available for independently
authored expected-row cases and explicit corpus maintenance. The historical
`retail-admin persona` command is a privileged local database tool; the CEO-facing
WebUI/API uses the automatic gate. The old reviewed before/after demonstration in
`retail/learning_demo.py` is historical evidence of that operator path, not proof
of this new worker or general accuracy improvements.
