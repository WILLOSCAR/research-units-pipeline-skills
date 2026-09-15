# Architecture Decision Records

This directory records repo-level architecture decisions for Research Harness.
ADRs are for choices that affect project structure, contracts, validation,
harness behavior, or long-term maintenance.

Use `DECISIONS.md` inside a workspace for run-local choices. Use ADRs here when
the decision should guide future contributors and agents across runs.

## Decision classes

[ADR 0026](0026-redesign-the-product-from-the-story-and-freeze-the-implementation.md)
froze the implementation at tag `snapshot/pre-refactor-2026-09-12` and
redesigned the product from the story. Every earlier ADR is classified by how it
constrains the rebuilt product:

- **story** — part of the story itself; the refactor must satisfy it as written.
- **behavior** — the behavior it decided carries forward as a conformance
  requirement; the specific mechanism does not.
- **snapshot** — records the frozen implementation; the refactor re-decides it
  or carries it forward in a new ADR.

## Accepted Decisions

| ADR | Decision | Status | Class |
|---|---|---|---|
| [0001](0001-separate-semantic-skills-from-deterministic-harness.md) | Separate semantic skills from the deterministic harness | accepted | story |
| [0002](0002-keep-run-audit-as-markdown-plus-json.md) | Keep run audit as Markdown plus JSON sidecar | accepted | snapshot |
| [0003](0003-keep-doctor-report-as-markdown-plus-json.md) | Keep doctor report as Markdown plus JSON sidecar | accepted | snapshot |
| [0004](0004-keep-skill-audit-as-repo-local-json-before-sarif.md) | Keep skill audit as repo-local JSON before SARIF | accepted | snapshot |
| [0005](0005-keep-run-audit-diff-as-json-backed-comparison.md) | Keep run audit diff as JSON-backed comparison | accepted | snapshot |
| [0006](0006-keep-showcase-audit-as-repo-local-json-contract.md) | Deprecate showcase audit as active harness contract | deprecated | — |
| [0007](0007-keep-improvement-report-as-a-local-repair-map.md) | Keep improvement report as a local repair map | accepted | snapshot |
| [0008](0008-keep-artifact-pack-as-manifest-before-archive.md) | Keep artifact pack as manifest before archive | accepted | snapshot |
| [0009](0009-add-a-pinned-append-only-run-ledger.md) | Add a pinned append-only Run ledger | accepted | behavior |
| [0010](0010-pair-review-markdown-with-structured-evidence.md) | Pair review Markdown with structured Evidence | accepted | snapshot |
| [0011](0011-keep-semantic-scorecards-workflow-local.md) | Keep semantic scorecards Workflow-local | accepted | snapshot |
| [0012](0012-publish-curated-run-evidence-not-full-workspaces.md) | Publish curated Run evidence, not full Workspaces | accepted | behavior |
| [0013](0013-route-quality-checks-through-workflow-domains.md) | Route quality checks through Workflow domains | accepted | snapshot |
| [0014](0014-commit-unit-completion-as-a-recoverable-provenance-transaction.md) | Commit Unit completion as a recoverable provenance transaction | accepted | behavior |
| [0015](0015-serialize-workspace-commands-with-a-process-scoped-lock.md) | Serialize Workspace commands with a process-scoped lock | accepted | behavior |
| [0016](0016-author-skills-for-predictability-and-bounded-context-load.md) | Author Skills for predictability and bounded context load | accepted | snapshot |
| [0017](0017-bind-completion-acceptance-to-recovery-and-audit.md) | Bind Completion acceptance to recovery and Audit | accepted | behavior |
| [0018](0018-snapshot-pipeline-contracts-inside-each-run.md) | Snapshot Pipeline contracts inside each Run | accepted | behavior |
| [0019](0019-bind-checkpoint-approval-to-reviewed-artifacts.md) | Bind Checkpoint approval to reviewed Artifacts | accepted | behavior |
| [0020](0020-fail-closed-on-active-run-kernel-drift.md) | Fail closed on active Run Kernel drift | accepted | behavior |
| [0021](0021-introduce-v2-deep-modules-without-reinterpreting-v2-runs.md) | Introduce V2 deep modules without reinterpreting v2 Runs | accepted | snapshot |
| [0022](0022-own-v3-local-run-execution-behind-one-engine.md) | Own V3 local Run execution behind one engine | accepted | snapshot |
| [0023](0023-expose-one-versionless-research-harness-interface.md) | Expose one versionless Research Harness interface | accepted | snapshot |
| [0024](0024-make-the-case-the-product-object.md) | Make the Case the product object | superseded | — |
| [0025](0025-make-the-self-correcting-run-the-product-object.md) | Make the self-correcting Run the product object | accepted | story |
| [0026](0026-redesign-the-product-from-the-story-and-freeze-the-implementation.md) | Redesign the product from the story and freeze the implementation | accepted | story |
| [0027](0027-enrich-the-story-with-grounds-faults-lessons-and-the-outer-loop.md) | Enrich the story with grounds, Faults, Lessons, and the outer loop | accepted | story |
| [0028](0028-rebuild-design-for-horizon-0.md) | Rebuild design for Horizon 0: new package, referee protocol, kind YAML, D0 gate binding, removal order | accepted | behavior |

## ADR Format Contract

Each ADR file should use this minimal shape:

- title line: `# ADR NNNN: Short Decision`
- metadata: `Status` and `Date`
- sections: `## Context`, `## Decision`, `## Consequences`, and
  `## Related Files`

Allowed statuses are `accepted`, `deprecated`, and `superseded`.

The repository's document gate (`scripts/check_docs.py`) checks that every link
in this index resolves; index drift and the ADR contract are kept by review.
Keep ADRs short, but make the decision, tradeoff, and related files explicit
enough that future agents do not need to recover the rationale from chat logs.
