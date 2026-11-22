# Bounded learning loop

Implement the agreed workflow: response-linked user feedback in Open WebUI,
explicit persistent presentation preferences, operator-reviewed Golden Trio
publication, and reproducible before/after evidence. No autonomous training.

Use native Actions opening one same-origin page. An embedded input dialog is
harder to review and does not provide preference controls; an external learning
service would add identity/data boundaries. Keep state in the retail backend.

Pipe supplies trusted WebUI chat/message identifiers when invoking the backend.
On completion the backend binds these to the authenticated owner, actual
conversation, trace, response snapshot and product scope. Feedback APIs resolve
that stored mapping, never accept an arbitrary browser-selected backend trace.
Check current scope and owned conversation; require the fetched mapping revision
on submission so regenerated responses cannot silently receive stale feedback.
Feedback is untrusted, sanitized and unreviewed. No feedback endpoint publishes.

WebUI proxy verifies native session and uses server-only adapter credentials.
Same-origin feedback page uses session token only in Authorization headers,
textContent for snapshots and no model HTML. User chooses helpful/unhelpful/
correction and optional comment. Store a fixed human-readable default comment
for rating-only feedback. Preferences expose format/depth, explicit save and
reset-to-defaults; show persistence and version. Charts/inference remain design.

Operator CLI continues to create/evaluate/approve/index knowledge. Add a
repeatable isolated fixture demonstration of failure -> user correction ->
review rejection/pass -> publication -> retrieved method -> successful SQL
oracle. Clearly distinguish controlled planning/fixture data from measured
live model quality. Add live retrieval before/after for a demonstration method
if feasible, without claiming an improved report without model evidence.

Preserve reports, chat history, existing Action assignments and user access.
Responses predating the message mapping cannot accept response-linked feedback.
