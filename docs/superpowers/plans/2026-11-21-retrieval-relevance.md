# Retrieval relevance implementation plan

Goal: improve English no-match handling with existing embeddings.
Spec: ../specs/2026-11-21-retrieval-relevance-design.md
Execution: inline, using regression tests before production changes.

- [x] Collect bounded live embeddings and calibrate on deterministic development cases.
- [x] Add failing tests for lexical false matches, partial indexes, fallback,
      semantic-only matches, scope and gate telemetry in tests/test_knowledge.py.
- [x] Implement cosine eligibility for lexical additions in retail/knowledge.py.
- [x] Persist a reproducible English comparison, policy/version/split metadata,
      and explain any recall/precision tradeoff; run the complete pytest suite.
- [x] Verify live API rollout if the candidate passes the measured gate.

Verification: 187 pytest cases passed; independent reviewer found no runtime
blocking issues. Clarified supplied-cache provenance and added input digests.
API restarted on 8001 and health returned live. Direct live-config retriever
checked existing 23-document index with real embeddings: positive returned a
method, weather query returned none, both reported an applied gate.
This is not a new end-to-end chat/report or BigQuery acceptance run.

Constraints: no new dependency; no report deletion; no secret output; no
BigQuery calls needed for retrieval evaluation. Never tune the acceptance
threshold against final validation outcomes. Provider failure must not masquerade
as a measured semantic no-match. English is the product evaluation scope.
