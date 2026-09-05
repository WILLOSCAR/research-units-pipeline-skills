# ADR 0022: Own V3 Local Run Execution Behind One Engine

- Status: accepted
- Date: 2026-08-11

## Context

The V2 deep modules established typed Workflow, Run, Completion, Artifact, and
Skill boundaries, but callers still have to coordinate individual Attempt and
Completion commands. Only in-memory storage adapters exist, so the new model
cannot yet survive a process restart or own a complete local Unit execution.
Exposing storage, subprocess, acceptance, and recovery choreography to every
caller would make those invariants easy to violate and hard to replace with a
future remote runtime.

## Decision

Add an opt-in V3 `LocalRunEngine` bound to one Workspace. Its public mutation
surface is one `execute(command)` method and its read surface is `inspect()`.
The engine owns the full Unit transaction: recovery, scheduling, durable
Attempt creation, Skill invocation, Artifact capture, acceptance, Completion,
and projection. Callers do not coordinate `BeginAttempt` and
`CompleteAttempt` themselves.

Persist exactly one canonical mutable Run aggregate under `.harness-v3` using
an explicit, versioned JSON codec. Advisory lock data controls concurrency but
is not Run state. Immutable identity metadata may pin the Run, Workflow,
Kernel, adapter, and protocol contracts, but human-readable status and
Manifest files remain evidence or projections rather than parallel state
authorities. Writes use optimistic version checks and durable atomic replace;
Artifact and Checkpoint evidence is Workspace-confined and content-addressed.
Create a new Workspace transactionally in a same-parent staging directory and
publish it only after its contracts, execution snapshot, and canonical Run are
durable. Bind subprocess adapters to a read-only, revision-addressed,
manifest-verified repository snapshot so a composed engine never executes
later checkout bytes under an earlier Kernel identity.

Keep filesystem, Skill execution, acceptance, clocks, and identifiers behind
local-substitutable seams. `Advance` may execute one Unit or continue until a
Checkpoint, failure, or completed Run, while preserving the domain model's
single-active-Attempt invariant. Expected workflow or Skill failures become
durable blocked results; integrity, concurrency, unsupported-version, and
adapter-protocol failures stay typed exceptions.

Existing `harness-lock.v2` Workspaces remain owned by the legacy interpreter.
V3 never mutates or silently upgrades them. Migration, if added, must create a
new Run identity and preserve read-only provenance to the source Run. A
declarative Workflow parity result is not a behavioral migration result;
observable state, Completion, Artifact, Checkpoint, failure, and recovery
behavior require their own conformance evidence.

## Consequences

The repository gains a second, explicitly versioned local execution path while
the V2 interpreter is retained. This is additive migration scaffolding: the
V3 engine can be fault-injected and replayed without changing historical Runs,
and its adapters can later be replaced without widening the caller API.

The engine serializes local Unit execution and pays the cost of durable JSON
serialization and filesystem synchronization. That tradeoff is acceptable for
small research Workspaces and provides a clear recovery boundary. Parallel or
remote execution must preserve fencing, idempotency, pinned adapter identity,
and uncertain-outcome handling before it can implement the same seam.

## Related Files

- `src/research_harness/engine/`
- `src/research_harness/storage/`
- `src/research_harness/acceptance/`
- `src/research_harness/application/`
- `tests/v3/`
- `docs/adr/0021-introduce-v2-deep-modules-without-reinterpreting-v2-runs.md`
