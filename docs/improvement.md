# Reviewed improvement and persona workflow

Client scope and defaults: [consolidated specification](acceptance-spec.md). Shared-knowledge automation
and persona quality gates remain design-only; optional commands below describe
the existing operator-driven demonstration.

## What the assignment actually requires

Requirement 4 is titled “Continuous Improvement (The Learning Loop)”. It asks
for remembered and learned user preferences, and system improvement from past
interactions. It does not prescribe a background job, scheduler, separate
service, automatic training, or an external learning API. Background evaluation
and indexing jobs are optional implementation proposals, not assignment
requirements or a claim that such jobs are running. The current controlled
feedback/review/publication/indexing path below is operator-triggered.

## User preferences

Use **My preferences** under a Retail Intelligence answer, the preferences API,
or ask the live agent to remember an explicit format
and depth. Preferences are keyed to authenticated backend identity, loaded into
each turn's model context, and applied to query evidence rendering. Supported
formats are tables, bullets and prose. No learning can change product scope or
PII policy. Fixture planning is intentionally limited; use the API to exercise
preference changes without Gemini.

### Presentation preference application

The current English-only deterministic implementation uses this order:
current question → saved personal format/depth → application defaults.
Shared persona controls tone; presentation preferences layer on top of it without
changing safety or analytical definitions. The same effective format reaches the
model and the backend Query evidence renderer. Explicit table requests override
saved bullets/prose. Existing saved reports remain snapshots.

- “Use bullets. Keep it concise.” applies to this response immediately.
- Repeating the same directive on two turns stores that field automatically,
  without a confirmation step. Counters persist across sessions per user.
- “From now on, use bullets.” saves immediately and preserves unspecified depth.
- “Use prose for this answer only.” neither changes the profile nor trains it.
- My preferences shows saved format/depth and source; save overrides learning,
  and reset restores tables/standard and clears pending learning signals.

This is bounded learning from presentation directives, not general inference from
ratings, demographics or user behavior. Quoted examples and negated directive
clauses are ignored. Supported formats are tables, bullets and prose; depths are
concise, standard and detailed. Chart preference is not implemented. Natural
language beyond the supported patterns still depends on model interpretation.

**Verification:** these latest preference edits and prepared regression cases
have not been executed; the user paused tests/evals. The earlier passing suite
predates them. No new paid calls are required for preference learning.

## Feedback from Open WebUI

Use **Give feedback** under a newly generated Retail Intelligence response.
The page previews the selected question/answer and accepts Helpful, Incomplete,
or Needs correction plus an optional comment. Feedback remains **unreviewed**.
Native Open WebUI thumbs are separate and are not bridged to this workflow.

The Pipe forwards trusted WebUI chat/message IDs. The backend records an owned,
scope-bound snapshot of the actual completed response and resolves it server-side
to a conversation/trace. A revision check rejects a stale form after regeneration.
Snapshots survive the bounded conversation history; ownership and current product
scope are rechecked. Older answers created before this integration have no mapping.
Comments are sanitized; they are never treated as instructions or publication approval.

## System learning demonstration

1. Submit authenticated `POST /feedback` with conversation_id, trace_id, rating
   (`helpful`, `unhelpful`, `correction`) and comment. The referenced turn must
   belong to that user. Comments are sanitized and remain untrusted.
2. An operator reviews feedback, writes a sanitized trio JSON file with id,
   question, sql, report, tags, scope, schema_version=`safe-v1` and origin, and
   runs `retail-admin candidate --source-user alice --feedback-id ID --file FILE`.
   Use origin=`synthetic reviewed demonstration` for fabricated examples.
3. Write a JSON array of independently reviewed cases, each containing name,
   user and expected_rows. For the fixture query `SELECT COUNT(*) AS products
   FROM products`, Alice's expected_rows is `[{"products":2}]`; Bob's is
   `[{"products":1}]`. These are fixture facts, not public BigQuery expectations.
4. Run `retail-admin review --candidate ID --reviewer REVIEWER_ID --cases FILE`.
   It executes the candidate SQL for each user's trusted entitlement context,
   records actual/expected rows and job/mode provenance, and publishes a version
   only after all cases pass. Failed cases do not publish the example.
5. Run `retail-admin index` with the configured embedding provider to embed approved published trios.
   Document embeddings are not created during user questions. Retrieval filters
   scope/schema/latest version before vector matching and fuses ranks with text
   search. The model and source version/content hash identify an index record.

`tests/test_governance.py` demonstrates failed review, successful two-user review,
publication and changed retrieval results. It does not prove that a new SQL
method generalizes or that Gemini's generated reports become better. Production
publication additionally requires held-out intent, safety, retrieval and report
regressions, automated publication gates, a staged rollout and monitored rollback criteria.
Human review handles high-risk exceptions instead of approving every update.
There is no automatic fine-tuning or autonomous prompt mutation.

For rollback, create a new reviewed candidate containing a prior published
version and run the evaluation gate again; publish it as a new monotonically
increasing version. This retains history and avoids reviving old index records.
Publication commands require local database access and are operator-only; there
is no public trusted-publication endpoint. Separate admin identity/RBAC and a
signed release artifact are production extensions.

## Persona without redeployment

Write a tone file and run `retail-admin persona --file tone.txt --reviewer ID`.
The next turn reads the newly published version from the database; no application
restart is needed. To roll back, republish the previous tone as a new version.
Persona is bounded presentation data, subordinate to fixed safety instructions
and executor policy. The version is included in traces.

**Current UX limitation:** an operator CLI is implemented, not the final
nondeveloper editor. The production editor should allow a CEO/editor to preview
a tone on fixed sample reports, compare it with the current version, publish or
roll back under editor RBAC, and inspect audit history. It must expose tone and
style controls, not system policy or arbitrary executable configuration.


## Assignment reread: current gaps (21 November)

The original PDF requirement 4 explicitly includes both user preference learning
over time and system improvement from past interactions. Deliverable 3 makes the
learning loop design scope rather than a mandatory prototype feature; our MVP
already contains a bounded implementation, but it must not be described as a
finished autonomous learning system.

### Demonstrable today

- Explicit per-user format/depth survives chats and reaches model context.
- Feedback API requires an owned conversation/trace and stores unreviewed input.
- Operator can create a candidate, test independently authored SQL expected rows,
  publish a new knowledge version and explicitly index it.
- Failed SQL evaluation does not publish. Published knowledge affects retrieval.
- Persona publication takes effect next turn without deployment.

### Implemented and remaining extensions

1. **Implemented:** Give feedback Action, trusted response mapping, revision guard,
   authenticated feedback/preferences proxy and page. Feedback never publishes knowledge.
2. **Implemented, latest edits unverified:** explicit preferences UI/reset,
   current-turn overrides and automatic learning from repeated format/depth
   directives. No inferred-preference confirmation is required. Chart/text
   preference remains unimplemented.
3. Operator review queue: feedback → sanitized draft candidate → evaluate → compare
   current/candidate versions → approve/reject → index → monitor/rollback.
4. Strengthen the publication gate beyond exact SQL rows: held-out intent/report
   faithfulness, retrieval nDCG/Recall/MRR, safety and cross-user cases. Require no
   meaningful regression and record dataset/model/prompt/index versions.
5. Treat current ratings as noisy signals, not labels of objective correctness.
   Track before/after measurements and retain human review for shared changes.

The operator-driven shared-knowledge demonstration remains separate from the
bounded personal presentation learner. Repeated analysis jobs
are an independent extension described in request-completion-and-scheduling.md.

## Reproducible before/after evidence

Run `.venv/bin/python scripts/demonstrate_learning.py --live --env-file .env.live
--output /tmp/learning-demo.json` as one command. This explicitly permits bounded
billed model/embedding calls, uses a temporary database and fixture SQL, and never
modifies live shared knowledge. Without `--live`, it loads no settings/providers
and reports untested. The test `tests/test_learning_demo.py` uses a controlled planner.

The live v2 result is `evaluation/learning-loop-live-v2-2026-11-21.json`:
the Gemini model via DeepInfra first asks for an undefined synthetic Lantern KPI;
an operator submits its catalogue-count definition, a deliberately wrong SQL
oracle blocks publication, then Alice/Bob fixture oracles pass. One new Trio is
indexed with live Qwen embeddings. In a new conversation, hybrid retrieval supplies
the definition and the model returns the expected count, `products=2`.
This demonstrates one learned business definition, not a general accuracy gain,
autonomous learning, live BigQuery validation or human acceptance of the report.

The first run is retained as `evaluation/learning-loop-live-2026-11-21.json`:
the ambiguous instruction “Show products” produced the correct catalogue list,
but did not match the count-row oracle. V2 explicitly requests one count row;
the prompt change means the runs are not an unchanged repeated benchmark.
