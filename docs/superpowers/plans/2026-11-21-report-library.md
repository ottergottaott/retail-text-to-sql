# Report Library Implementation Plan

**Goal:** Persistent Reports navigation and native Action with authenticated live data.
**Architecture:** Static same-origin library + Event proxy + Action + pinned image overlay.
**Spec:** docs/superpowers/specs/2026-11-21-report-library-design.md

- [x] Write failing tests for verified-user proxy, bounded calls, safe errors and lifecycle.
- [x] Implement Event proxy and native Action.
- [x] Implement library UI and version-pinned navigation image overlay.
- [x] Install functions and image without changing existing data or valves.
- [x] Verify browser Action/navigation/search/open, RBAC and restart; run full tests.
- [x] Document setup, maintenance boundary and observed evidence.

## Execution ledger

- Completed implementation and native Action browser test; Action is model-specific.
- Fixed sidebar insertion for compact and expanded navigation, with Notes/Workspace/
  New Chat fallback and hard navigation instead of the SPA router.
- Fixed startup-managed asset location: image copies files into `/app/build/static`.
- Fixed viewer inherited CSP for deterministic inline report styles; iframe remains
  scriptless and without same-origin permission.
- Read-only independent review found the CSP and Notes dependency issues; both fixed.
- Repeated query scheduling and completion-gate recommendations are documentation,
  not implemented behavior: see docs/request-completion-and-scheduling.md.
