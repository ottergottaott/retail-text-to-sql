# Report library and Action

User selected both native message Action and persistent Reports navigation.

- A native model-specific Action opens the library without calling an LLM.
- A small, version-pinned frontend overlay adds Reports to WebUI's sidebar. A
  derived Docker image adds one script reference; upstream source remains intact.
- A same-origin standalone library page uses the existing WebUI session. It has
  search, newest-first dates, refresh, empty/error/loading states, and an embedded
  read-only report viewer. It never puts credentials in URLs.
- An Event function registers authenticated GET list/HTML proxy routes before
  WebUI's SPA fallback. It resolves verified users with native WebUI dependencies
  and forwards only that user's server-derived ID to the existing retail API.
  Backend owner/product authorization remains authoritative. No mutation routes.
- HTML is shown in an iframe sandbox without scripts or same-origin permission.
  Report text is never inserted as executable library markup. Downloads are snapshots.
- Installer preserves existing Pipe valves, users, reports and configuration.
  Reproducible Compose overlay and image build make the UI extension durable.
- Alternatives: pinned static chat lacks a current library; a full upstream fork
  adds maintenance cost. The overlay is deliberately limited to sidebar insertion;
  selectors require a browser check when upgrading the pinned WebUI image.

Acceptance: native Action + persistent sidebar item; live list/search/open; 401
without session; identity cannot be forged; cross-user denial; errors sanitized;
restart persistence. No claim of human acceptance or new SQL/provider validation.
