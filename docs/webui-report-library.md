# Reports library and native Action

## What is installed

- **Reports** link in expanded and compact WebUI sidebar, surviving restarts.
- **My reports** native Action, attached only to Retail Intelligence messages.
- `/static/retail-reports.html`: searchable newest-first library, dates and refresh,
  read-only report viewer, HTML download and separate browser-tab viewing.
- `/api/retail-reports` and `/api/retail-reports/{id}/html`: same-origin read-only
  proxy registered by the Retail Reports API Event function.

Opening or refreshing the library does not call a model, retrieve trios or execute
SQL. Existing reports remain stored in the retail backend independently of chats.

## Installation

Build and start the pinned frontend overlay:

```sh
docker compose --env-file .env.fixture -f compose.yaml -f compose.webui-reports.yaml build webui
docker compose --env-file .env.fixture -f compose.yaml -f compose.webui-reports.yaml up -d --no-deps webui
```

For a fresh fixture bootstrap, add `--reports` to `scripts/bootstrap_webui.py`.
For an existing local installation, run `scripts/install_webui_reports.py` with
`WEBUI_ADMIN_TOKEN` supplied through the process environment, then restart WebUI.
Do not put the token into a CLI argument, URL, committed file or copied terminal
output. Installer copies the existing Pipe's backend URL/adapter secret server-side
and preserves its valves and existing workspace model settings/access grants.
If it creates a workspace model entry, configure its access grants for intended
reviewers in the admin UI; the current demo admin has access. No report data is
copied into WebUI Notes, Knowledge or chats by this library.

The live setup uses the existing `retail-assessment` Compose project and the same
WebUI secret/volume. Its retail API remains the host process on port 8001. Do not
start the fixture API in place of the live backend or overwrite its private valves.

## Access and privacy

The static page is an empty shell. Its JavaScript uses the existing WebUI session
Bearer token only for same-origin requests. Tokens are not included in report
links or exported HTML. The proxy uses `get_verified_user`, ignores browser-supplied
identity headers, and forwards the verified user's ID using the private retail
adapter secret. The retail backend applies current owner and product-scope checks.

Reports render from a temporary Blob URL in an iframe without scripts or
same-origin permission. The report has its own URL so section links such as
`#evidence` scroll within the report rather than loading the library inside it.
Blob URLs are released when the viewer is cleared or the page is left. Titles and
IDs use DOM textContent, not innerHTML. Parent code never executes report HTML.
The report's no-script CSP remains effective, with no remote assets. Read responses
are no-store, failures are sanitized, redirects are disabled and upstream calls
have a 20-second timeout. Disabling the API Event function blocks subsequent
proxy reads; changing its valves takes effect on the next request.

Already displayed HTML and downloads remain snapshots, as with the existing chat
Artifacts. Refresh clears the current viewer before rechecking access. A deleted
or inaccessible report cannot be fetched anew; delivered copies cannot be revoked.

## Maintenance boundary

Action and API registration use native Functions. Persistent sidebar insertion is
a small custom JavaScript overlay, **not an upstream sidebar extension API**. The
derived image adds one script reference to the original index and assets to the
upstream build/static directory; WebUI copies static assets on startup. Branding
and upstream application bundles remain intact. Test sidebar selectors and Action
execution when changing the pinned `v0.13.4-slim` image. The standalone library has
its own narrow sidebar, rather than duplicating the entire WebUI navigation.

Rollback: switch back to the base image/Compose file and disable both Reports
Functions. Keep the existing volume. No database migration or report deletion is
needed. Native Actions are message-toolbar buttons, not global header controls.
