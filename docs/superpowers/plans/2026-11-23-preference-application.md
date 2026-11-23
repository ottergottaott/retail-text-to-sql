# Preference application and bounded learning

Scope agreed in the conversation: finish personal format/depth application and
record privacy limitations. Paid evals and test execution are paused by the user.

## Design

Use trusted deterministic English presentation directives, with no model calls.
Current-turn directives override the saved personal profile; the saved profile
layers over application defaults. Explicit persistent requests save immediately.
Two matching presentation corrections per field learn that setting automatically.
A different directive restarts that field's evidence count. Requests explicitly
limited to this answer never contribute learning evidence. Ignore quoted content
and negated directive clauses. No access, privacy, analytical or tone policy is
learned. The existing preferences UI/API remains the inspection/override/reset.

## Implementation

- Add `retail/preferences.py` for directive parsing and effective-profile assembly.
- Keep persistent signal counters separate from profile values in `Store`.
- Resolve effective preferences once in `Agent.context`; pass them to every model
  call and use the same values for backend evidence rendering.
- Preserve user-required tables even when a saved default says bullets/prose.
- Document the supported deterministic learning scope, PII limitations and paused
  evaluation provenance. Add focused regression cases but do not run them while
  the user's testing pause is in force.

Verification pending: new preference behavior has no execution evidence yet.
