# Report Experience Implementation Plan

> Execute inline with Superpowers executing-plans; user authorized implementation.

**Goal:** Present successful retail analyses as polished embedded previews and HTML Artifacts.
**Architecture:** API attaches deterministic presentation to successful results; Pipe renders
the preview via `embeds` and returns full HTML as an Artifact alongside final text.
**Tech Stack:** Python/FastAPI, standard-library escaping, existing Open WebUI Pipe.
**Spec:** `docs/superpowers/specs/2026-11-21-report-experience-design.md`

## Constraints and review focus
No extra model calls; no arbitrary active content; no weakened report ownership.
Test malicious data, unsaved/empty results, failed presentation transport, scope
changes and reopening persisted reports. Verify both UI modes in the installed build.

## Tasks
- [x] Add renderer contract tests, observe RED; implement responsive HTML and preview.
  Files: `tests/test_report_presentation.py`, `retail/report_presentation.py`,
  `retail/templates/report.html`.
- [x] Add API tests for successful/draft/opened reports and cross-user denial,
  observe RED; attach `report_view` and add authenticated HTML endpoint.
  Files: `retail/api.py`, `tests/test_api.py`.
- [x] Add Pipe tests for two presentations and nonfatal embed failure, observe RED;
  implement return-content and supplementary-embed delivery.
  Files: `integrations/openwebui_pipe.py`, `tests/test_pipe.py`.
- [x] Run regression suite; update installed Pipe and host API without changing
  credentials; verify real saved report, reload and new chat in browser.
- [x] Record screenshots and evidence; update integration documentation and OpenSpec.

## Execution record
Renderer, API and Pipe tests were observed RED before implementation and GREEN
afterward. Browser discovery showed that HTML fences inside details are stripped
from Artifact discovery and that cross-origin previews need explicit height
messages. The implementation uses an external HTML fence and a fixed,
hash-authorized height bridge; it does not grant same-origin iframe access.

177 regression tests passed; strict OpenSpec validation passed; the built wheel
contains `retail/templates/report.html`. A bounded independent code review found
no important findings in access, eligibility, escaping, evidence and saved-state
handling. The review preceded the small product-name chart-label refinement,
covered by renderer tests and the live browser check.

Fresh live report `rep_3c595b29bfd416bd` was generated and saved through WebUI,
then reopened from new chats after API restarts. Final renderer, chart, embedded
expansion, exact SQL disclosure and reload persistence were observed in v0.13.4.
Native Download created a text/html Blob containing the report and chart; OS
download persistence was not independently checked. Native fullscreen button
is available, but headless checks returned no fullscreen element, so fullscreen
success is not asserted. Human acceptance remains pending.
