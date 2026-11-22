# Learning loop implementation plan

Goal: finish and test the bounded learning workflow agreed with the user.
Design: ../specs/2026-11-21-learning-loop-design.md
Execution: inline TDD, followed by one independent final review.

- [x] Test and implement owner/scope-bound WebUI message-to-turn snapshots,
      revision-safe feedback submission and rating-only feedback.
- [x] Test and implement verified WebUI learning proxy and native Actions;
      connect Pipe message IDs and build feedback/preferences page.
- [x] Add reproducible reviewed-publication before/after demonstration with
      explicit fixture/live evidence boundaries.
- [x] Run full tests; install Functions/assets, restart services as needed;
      verify feedback and preference persistence in the browser.
- [x] Review, fix substantive findings, update OpenSpec/README/improvement docs,
      persist evidence and report remaining limits.

## Verification ledger

- Backend and proxy TDD: missing implementation / failing assertions observed, then green.
- Learning demo TDD: missing module observed, then live-model fixture demo executed.
- Browser: actual native Actions, response preview, submitted correction, server-owned
  mapping check, reset/reload and restored bullets/concise version 5 verified.
- Live demo v1 oracle false retained; clarified output contract in v2, no threshold
  or oracle relaxation. V2 before clarification → approved indexed definition →
  products=2 query oracle passed. SQL was fixture-only; one case is not broad accuracy.
- Final independent review found failed regeneration retaining previous feedback.
  Regression RED (200 instead of 403) → tombstone old mapping → GREEN.
- Final full suite: 195 passed; OpenSpec strict validation passed. API restarted
  with fix, WebUI image rebuilt/recreated, health live. Saved reports preserved.
- Evidence: evaluation/learning-loop-acceptance-2026-11-21.json.
- Explicit inference/chart preference and nondeveloper operator review queue remain
  documented extensions, outside the approved bounded loop.
