# Architecture Decision Records

This directory records repo-level architecture decisions for the Auto Research
Design System. ADRs are for choices that affect project structure, contracts,
validation, harness behavior, or long-term maintenance.

Use `DECISIONS.md` inside a workspace for run-local choices. Use ADRs here when
the decision should guide future contributors and agents across runs.

## Accepted Decisions

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-separate-semantic-skills-from-deterministic-harness.md) | Separate semantic skills from the deterministic harness | accepted |
| [0002](0002-keep-run-audit-as-markdown-plus-json.md) | Keep run audit as Markdown plus JSON sidecar | accepted |
| [0003](0003-keep-doctor-report-as-markdown-plus-json.md) | Keep doctor report as Markdown plus JSON sidecar | accepted |
| [0004](0004-keep-skill-audit-as-repo-local-json-before-sarif.md) | Keep skill audit as repo-local JSON before SARIF | accepted |
| [0005](0005-keep-run-audit-diff-as-json-backed-comparison.md) | Keep run audit diff as JSON-backed comparison | accepted |
| [0006](0006-keep-showcase-audit-as-repo-local-json-contract.md) | Deprecate showcase audit as active harness contract | deprecated |
| [0007](0007-keep-improvement-report-as-a-local-repair-map.md) | Keep improvement report as a local repair map | accepted |
| [0008](0008-keep-artifact-pack-as-manifest-before-archive.md) | Keep artifact pack as manifest before archive | accepted |
| [0009](0009-add-a-pinned-append-only-run-ledger.md) | Add a pinned append-only Run ledger | accepted |
| [0010](0010-pair-review-markdown-with-structured-evidence.md) | Pair review Markdown with structured Evidence | accepted |
| [0011](0011-keep-semantic-scorecards-workflow-local.md) | Keep semantic scorecards Workflow-local | accepted |
| [0012](0012-publish-curated-run-evidence-not-full-workspaces.md) | Publish curated Run evidence, not full Workspaces | accepted |
| [0013](0013-route-quality-checks-through-workflow-domains.md) | Route quality checks through Workflow domains | accepted |
| [0014](0014-commit-unit-completion-as-a-recoverable-provenance-transaction.md) | Commit Unit completion as a recoverable provenance transaction | accepted |
| [0015](0015-serialize-workspace-commands-with-a-process-scoped-lock.md) | Serialize Workspace commands with a process-scoped lock | accepted |
| [0016](0016-author-skills-for-predictability-and-bounded-context-load.md) | Author Skills for predictability and bounded context load | accepted |

## ADR Format Contract

Each ADR file should use this minimal shape:

- title line: `# ADR NNNN: Short Decision`
- metadata: `Status` and `Date`
- sections: `## Context`, `## Decision`, `## Consequences`, and
  `## Related Files`

Allowed statuses are `accepted`, `deprecated`, and `superseded`.

Strict repo validation checks both index drift and this minimal ADR contract.
Keep ADRs short, but make the decision, tradeoff, and related files explicit
enough that future agents do not need to recover the rationale from chat logs.
