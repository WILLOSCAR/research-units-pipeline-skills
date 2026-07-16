# ADR 0014: Commit Unit Completion As A Recoverable Provenance Transaction

- Status: accepted
- Date: 2026-07-15

## Context

The executable paths previously finalized a Unit in different ways. Scripted
execution, human approval, automatic approval, and `pipeline.py mark` could
update `UNITS.csv` before or without producing the same Attempt, Manifest,
Artifact, Evaluation, and Failure evidence. A visible `DONE` value could
therefore mean either verified completion or an operator assertion.

Ordering also matters. Writing the mutable `DONE` projection before durable
evidence makes a process interruption ambiguous. Writing a final DONE Manifest
before the Attempt is durable creates the opposite inconsistency if the process
stops between those operations.

## Decision

All executable completion paths use `tooling.completion.commit_unit_completion`.
A Unit is committed through one recoverable protocol:

1. validate required outputs and Workflow-mandatory completion invariants;
2. validate and record a declared scorecard when one exists;
3. write a per-Attempt Manifest with `PREPARED` status;
4. record `unit.completion.prepared`;
5. finish the Attempt as `SUCCEEDED` and register its Artifacts;
6. finalize the Manifest as `DONE`;
7. project the Unit as `DONE` in `UNITS.csv` and record
   `unit.completion.committed`.

Run reconciliation may finish a valid prepared transaction or restore a Unit
whose successful Attempt and DONE Manifest were durable before the mutable
projection changed. It does not infer success from `UNITS.csv` alone. Failure
resolution is limited to failure types the successful path explicitly
reverified.

Run Audit checks referential integrity across Run identity, Events, Attempts,
Manifests, Artifacts, Decisions, Failures, Evaluations, and DONE Units. Current
hash equality is required for immutable outputs. Compatibility projections and
diagnostic sinks that are intentionally rewritten across Units retain
historical Artifact records but are excluded from that current-hash rule.

## Consequences

`DONE` is now a derived compatibility projection backed by durable evidence,
not an independent source of truth. Manual and automated completion have the
same provenance and scorecard behavior. The two-phase Manifest makes the
recovery boundary explicit without adding another ledger: completion stages
remain append-only Run Events.

The protocol is still single-process and file-based. It does not provide
distributed transactions or worker leases. Reconciliation can reconstruct a
missing prepared Event from a valid PREPARED Manifest, matching latest started Attempt,
declared outputs, and current hashes; it does not accept an orphaned or
inconsistent Manifest as completion evidence.

## Related Files

- `tooling/completion.py`
- `tooling/run_state.py`
- `tooling/executor.py`
- `tooling/harness.py`
- `scripts/pipeline.py`
- `tests/test_run_state.py`
