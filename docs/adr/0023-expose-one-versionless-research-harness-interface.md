# ADR 0023: Expose One Versionless Research Harness Interface

- Status: accepted
- Date: 2026-08-11

> Amended by [ADR 0025](0025-make-the-self-correcting-run-the-product-object.md).
> The decision to expose exactly one versionless interface stands, but the names
> below were overtaken: the package exports the `Loop*` surface with `Start`,
> `Continue`, and `Decide`, not `ResearchHarness` with `Create`, `Advance`,
> `Approve`, `Recover`, and `RunSnapshot`. Those orchestration commands became
> private implementation language. Read this ADR for why one interface exists;
> read ADR 0025 and `CONTEXT.md` for what it is called.

## Context

The typed Workflow, domain, storage, Skill, acceptance, and local-engine Modules
landed behind strong behavioral tests. Their migration labels then leaked into
three executable names (`rh`, `rh2`, and `rh3`) and two public orchestration
Interfaces. The product story also presented Improve as a normal fourth stage,
although the implemented command only diagnoses a bounded repair surface.

Persistent formats need explicit versions. Callers should not need to select an
implementation generation or coordinate Attempt and Completion transitions.

## Decision

Expose `ResearchHarness.open(workspace, repository=...)`, `execute(intent)`, and
`inspect()` as the versionless public Interface. Export stable Create, Advance,
Approve, Recover, result, inspection, state, outcome, and fault types from the
top-level package. The immutable Domain `RunView` is exported there as
`RunSnapshot` because detailed Run Evidence is part of inspection; mutation
commands and engine transaction types remain implementation details. Treat
application, engine, storage, Skill, acceptance, and migration packages as
implementation or maintainer surfaces.

Keep `rh` as the only installed product executable while it retains ownership
of legacy mutation. Consolidate typed Workflow maintenance and next-engine Run
commands under `python -m research_harness`; remove `rh2`, `rh3`, and the second
CLI implementation. `.harness-v3` remains an internal storage-schema namespace,
not a product version. The retained `rh` and `scripts/pipeline.py` paths reject
that namespace before acquiring their legacy Workspace lock, so one Workspace
cannot acquire two state authorities.

Use the product model:

```text
Goal -> Run -> Deliverable + Evidence
```

Describe `Audit -> Repair -> Resume` as the bounded control loop after a Run
stops. Do not imply that diagnosis applies repairs or promotes Harness changes.

Delete `WorkflowProjection` and the acceptance Catalog-to-Registry double
lookup because neither hides independent variation. A validated Workflow owns
its derived DAG, Skill, and required-check properties; acceptance binds an
exact `(Workflow, Skill)` pair directly to one evaluator Adapter.

## Consequences

Callers get one deep Module and no version-selection problem. CLI rendering,
repository composition, implementation-error translation, and engine outcomes
are localized behind that Interface. Maintainers can still test internal seams
and the retained legacy reader. Workspace paths remain unresolved until the
bootstrap boundary validates symlinks, while legacy inspection reads only a
bounded identity summary and never requires the live repository.

This decision does not authorize default-engine cutover or legacy deletion.
Some quality evaluators still depend on legacy projections, and no fresh
realistic completed next-engine Run yet supports a default-cutover claim.
Behavioral conformance across all seven Workflows remains the deletion gate.

Remote execution, automatic Workflow routing, and new Evaluation-suite seams
remain deferred until real second Adapters or callers exist.

## Related Files

- `src/research_harness/harness.py`
- `src/research_harness/cli.py`
- `docs/PROJECT_LANGUAGE.md`
- `docs/REFACTORING_AUDIT.md`
- `docs/adr/0021-introduce-v2-deep-modules-without-reinterpreting-v2-runs.md`
- `docs/adr/0022-own-v3-local-run-execution-behind-one-engine.md`
