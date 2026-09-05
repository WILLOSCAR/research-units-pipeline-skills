# ADR 0021: Introduce V2 Deep Modules Without Reinterpreting V2 Runs

- Status: accepted
- Date: 2026-08-11

## Context

The current Harness preserves strong Run Evidence, Completion, Checkpoint, and
Pipeline-snapshot semantics, but those behaviors are distributed across large
procedural modules, repository-relative subprocess calls, and Skill scripts
that import internal helpers. A direct rewrite of those files would trigger the
existing Kernel-drift guard and could make active `harness-lock.v2` Runs appear
compatible with an implementation they never pinned.

## Decision

Introduce the next implementation as deep modules under
`src/research_harness/` before replacing the legacy `tooling` mutation path:

- `application` owns the small command-oriented Harness interface;
- `domain` owns Run state and transition invariants without filesystem I/O;
- `workflows` compiles Pipeline frontmatter and UNITS data into one validated
  `WorkflowDefinition`;
- `skills` owns the `SkillContext -> SkillResult` execution seam and its
  subprocess and in-memory adapters.

The legacy `tooling` package remains the interpreter for existing
`harness-lock.v2` Runs. V2 modules must not mutate or reinterpret those Runs
through an implicit fallback. Promoting V2 to the default mutation path
requires an explicit versioned lock and Completion compatibility decision,
characterization evidence for existing Workflows, and a retained legacy
runner or an audited migration operation.

Tests should cross the new module interfaces. Existing implementation-level
tests remain only while they protect behavior that has not yet moved behind a
V2 interface.

The V2 `workflow parity` command compares declarative Pipeline and UNITS reader
projections only. Behavioral Audit and Artifact projection parity remains a
required, separate migration gate before any V2 mutation cutover.

## Consequences

The repository temporarily carries legacy and V2 implementations side by
side. This duplication is intentional migration scaffolding, not a permanent
second product surface. New modules can be packaged and tested without
changing the meaning of historical evidence, while each migrated Workflow's
declarative contract can be compared with the legacy readers before cutover.

V2 code is not part of the v2 Kernel hash inventory and must not be advertised
as a protected mutation engine until its own lock contract lands. Once every
supported Workflow has crossed the new interfaces, shallow compatibility
facades and their implementation-level tests should be deleted rather than
layered indefinitely.

## Related Files

- `src/research_harness/`
- `tests/v2/`
- `tooling/run_state.py`
- `tooling/executor.py`
- `tooling/harness_contracts.py`
- `pyproject.toml`
