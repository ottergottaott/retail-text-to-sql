# Interactive reports in Open WebUI

## Client experience

Select **Retail Intelligence** and use a retail starter prompt, or ask for an
analysis and save it. A completed analysis produces:

- An embedded report card. **Read report & explore evidence** expands the analysis
  inside the chat, with exact query rows and collapsible SQL.
- A full HTML **Artifact**, automatically discovered by Open WebUI. Use **Preview**
  if its panel is closed. Native controls offer download and full-screen viewing.
  The HTML file contains its own styles and data, without remote assets.
- A short chat receipt explaining whether the report is saved, with its ID.

Reports include live/fixture labels, original limitations and proposed action items,
scope at creation, saved timestamp, and measured query metadata when available.
A descriptive SVG revenue chart is included only for 2–16 nonnegative finite
revenue rows with a supported unambiguous dimension. It never infers totals,
causality or business population counts. Unknown shapes retain tables. Large
tables scroll; layout adapts to narrow panels and printing.

Ask **List my saved reports**, then **Open saved report REPORT_ID** from a new chat.
The API renders persisted data without repeating SQL or report-writing model calls.
The conversational router/retrieval can still make provider calls to select the
open-report action.

## Setup

Reimport `integrations/openwebui_pipe.py` as administrator, preserving its existing
`API_URL`, `ADAPTER_SECRET` valves and identity mapping. `REPORT_DISPLAY` defaults
to `both`; alternatives are `artifact`, `embedded`, and `text`. Plain API/CLI
clients keep the original answer and receive HTML only if they request
`include_report_view: true`.

In **Settings → Interface**, enable **Always Collapse Code Blocks** for concise
chat. This user preference was enabled for the demo through
`/api/v1/users/user/settings/update` with `ui.collapseCodeBlocks=true`.
Four retail starters were installed through `/api/v1/configs/suggestions` from
`integrations/webui_report_experience.json`. The local fixture bootstrap applies
the same configuration.

## API and access

`GET /reports/{report_id}/html` requires the same Bearer identity as the JSON API,
checks ownership and current product scope, and sends `no-store`, `nosniff` and
a restrictive CSP. It is not a public share link. No access token appears in
HTML or a URL. The Pipe obtains HTML server-side; adapter credentials stay private.

Only successful completed analyses with evidence, or accessible saved reports,
receive a `report_view`. Clarifications, denials, list operations, deletion previews
and errors do not. Presentation or embed-delivery failures never retry analysis
or invalidate a committed save. The original API answer remains available.

The renderer uses an allowlisted Markdown subset and escapes model text, rows,
SQL and metadata. Full Artifacts have no JavaScript. The preview has one fixed
hash-authorized script posting only its pixel height to the parent; it cannot
fetch data or read WebUI session state. Same-origin permission is not required.
WebUI's own iframe CSP can further restrict the preview.

Chat messages and downloaded HTML are **snapshots**. Deleting a backend report
blocks subsequent API reads but does not erase previously delivered snapshots
or downloads, just as with the original Markdown answers. This is not a revocable
share-document system. Existing privacy and retention caveats still apply.

## Verification

`evaluation/webui-report-experience-2026-11-21.json` records installed version,
live report IDs, browser checks and evidence paths. Tests cover escaping, fence
injection, CSP hash, chart values, owner/scope access, confirmed deletion and
nonfatal presentation failures. Wheel verification confirms the template is
packaged. Human UX acceptance remains separate from automated checks.

## SQL colors and report navigation

SQL evidence uses a server-rendered, lossless display lexer: keywords, strings,
numbers, comments and quoted identifiers have distinct colors. Token text is
escaped; no CDN, JavaScript highlighter or query rewriting is involved. Reopen
an existing report to get the updated rendering; earlier chat snapshots retain
old styling.

The saved-report list now contains same-origin links that prepare an **Open saved
report ID** command in a new WebUI chat with Retail Intelligence selected. In the installed v0.13.4 build, clicking the link opens a native WebUI chat
tab and submits the opening command automatically. Current upstream documentation
describes prefill only; on those versions review and send the command. Links contain only the report
identifier, never credentials. The backend checks current owner/product access
again. Plain-text display mode retains the original backend response. The list
is a snapshot, not a continuously refreshing library.

Artifacts is the native right-hand WebUI tab, available from the tab bar's + menu.
A dedicated persistent **Reports** navigation page or a standalone authenticated
browser-tab viewer has not been implemented. Direct backend HTML URLs require
Bearer authentication and cannot be used as ordinary unauthenticated links.
Downloaded HTML can be opened in its own browser tab as an offline snapshot.

## Persistent library extension

See [Reports library and native Action](webui-report-library.md) for the installed
sidebar **Reports** entry, message **My reports** Action, search/refresh, and
separate browser-tab viewer. These are additions to the original chat/Artifacts
experience. The library obtains saved reports directly from the authenticated API
without conversational routing, retrieval or SQL execution.
