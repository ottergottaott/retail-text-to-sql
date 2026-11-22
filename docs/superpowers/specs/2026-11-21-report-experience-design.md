# Report experience in Open WebUI

## Intent and authorization
The user selected Artifacts plus an embedded presentation and requested a polished,
convenient employer demo. Implement directly on the existing Open WebUI Pipe/API.

## Approach
Use one deterministic backend HTML renderer, with a compact embedded preview and
a complete HTML Artifact. Keep the ordinary final answer available for CLI and
accessibility. A separate frontend or Open WebUI fork adds unnecessary maintenance.
Model-authored HTML would add calls and introduce untrusted active content.

## Experience
Restrained navy/teal report design; responsive layout; clear live/fixture labels;
saved/draft status; readable analysis and tables; navigation; collapsible SQL and
query metadata. Show limitations without suggesting the model is always correct.
No fabricated business metrics or charts. Native Artifact controls provide export
and expanded viewing. Open saved reports from any chat through existing tools.

## Boundaries
Render only successful completed analyses or accessible saved reports. Never turn
clarification, deletion previews, denials, or errors into reports. Escape all
data; no model HTML, remote assets, arbitrary links, tokens, or data-fetching JS.
A fixed hash-authorized preview script sends only iframe height to WebUI so its
sandbox can resize without granting same-origin access. Full Artifact has no JS.
Existing owner and product scope checks apply to HTML just as to JSON.
Deleting a chat does not delete the report. A rendered chat snapshot can survive
deletion of its backend report, like the existing Markdown message; it is not a
live access-controlled document. Ingress/retention caveats remain documented.

## Verification
TDD for escaping, evidence, rendering eligibility, saved access and adapter fallback.
Browser verification on the installed v0.13.4-slim: embedded preview, full Artifact,
reopen/reload, and realistic report layout. Preserve fixture/live evidence labels.
