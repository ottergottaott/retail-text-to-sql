# Development tooling

## OpenSpec

Installed OpenSpec CLI **2.1.1** at `~/.local/bin/openspec` using the official npm
package `@fission-ai/openspec`. Node 24.2.0 satisfies its Node >=22.20.0 requirement.

The project was initialized with:

```sh
openspec init --tools codex --scope project --no-animation
```

This created `openspec/config.yaml` and six project skills in `.agents/skills/`.
The existing `openspec/changes/retail-mvp/` documents were preserved. Context and
artifact rules distinguish assignment requirements, additions, runtime evidence
and remaining work.

Run from `retail-assistant/`:

```sh
OPENSPEC_TELEMETRY=0 openspec list --json
OPENSPEC_TELEMETRY=0 openspec status --change retail-mvp --json
OPENSPEC_TELEMETRY=0 openspec instructions apply --change retail-mvp --json
OPENSPEC_TELEMETRY=0 openspec validate retail-mvp --strict --json
OPENSPEC_TELEMETRY=0 openspec validate --all --strict --no-interactive --json
```

The strict change validation passed with no issues. `status` reports planning
artifacts complete because proposal/specs/design/tasks exist; it does not mean
the MVP is finished. `instructions apply` reads individual task checkboxes and
still shows pending live-provider verification. The change remains unarchived.

## Superpowers

Installed all **15 skills** from `obra/superpowers`, version **7.0.2**, revision
`22f0b463e7a5e579904dd6211a520321035526f7`, into `~/.codex/skills/` using Codex's
skill-installer helper. Existing skills were preserved. This is a skills
installation, not a marketplace-plugin installation or a runtime dependency of
the retail application.

Skills cover brainstorming, planning, TDD, systematic debugging, code review,
verification and development workflows. They become available to Codex's skill
discovery on the next turn. `using-superpowers` and its Codex reference were read
during setup; `verification-before-completion` was applied to verify installation.
Earlier application work was not retroactively performed under these workflows.
The subsequent [review and regression fixes](superpowers-review.md) applied
Superpowers review/debugging/TDD to the current implementation and updated the
OpenSpec scenarios and task evidence.

OpenSpec holds the agreed change and acceptance scenarios. Superpowers guides
how implementation and review are performed. User instructions and the host's
tool/permission rules continue to apply. Live service and evaluation evidence
remain separate from both tools' installation checks.

## Verification evidence

Thread storage contains `retail-openspec-install.log`, `retail-openspec-init.log`,
`retail-openspec-validation.json`, `retail-openspec-status.json`,
`retail-openspec-apply.json`, `retail-openspec-validation-all.json`,
`retail-superpowers-install.log` and `retail-development-tooling-checks.json`.

Upstream references: [OpenSpec CLI](https://openspec.dev/docs/cli) and
[Superpowers](https://github.com/obra/superpowers).
