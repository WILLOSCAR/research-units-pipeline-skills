# Issue tracker: Local Markdown

Issues and specs (also called PRDs) for this repository live privately as markdown files under `.scratch/`. The repository has a GitHub remote for source control, but GitHub Issues is not the tracker: do not create, update, or publish remote issues unless the user explicitly changes this configuration.

This checkout excludes `.scratch/` through `.git/info/exclude`, so tracker artifacts remain local by default.

## Conventions

- One feature or planning effort per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`; never combine all tickets into one file
- Ticket numbers follow dependency order, with blockers first
- Triage state is recorded as a `Status:` line near the top of each issue file; see `triage-labels.md`
- Comments and conversation history append under a `## Comments` heading

## When a skill says "publish to the issue tracker"

Create a new local file under `.scratch/<feature-slug>/`, creating the directory if necessary. Do not call a remote issue API.

## When a skill says "fetch the relevant ticket"

Read the referenced local markdown file. The user will normally provide its path or ticket number.

## Wayfinding operations

When `/wayfinder` is used, keep one map plus one child file per decision ticket:

- **Map:** `.scratch/<effort>/map.md`
- **Child ticket:** `.scratch/<effort>/issues/NN-<slug>.md`
- **Blocking:** record `Blocked by: NN, NN`; a ticket unblocks when every listed ticket is resolved
- **Frontier:** choose the first open, unblocked, unclaimed ticket by number
- **Claim:** set `Status: claimed` before work
- **Resolve:** append the answer under `## Answer`, set `Status: resolved`, and add a concise pointer to the map

Implementation tickets produced by `to-tickets` use the default `ready-for-agent` status and are not triage inputs.
