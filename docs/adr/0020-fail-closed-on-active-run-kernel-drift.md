# ADR 0020: Fail Closed On Active Run Kernel Drift

- Status: accepted
- Date: 2026-08-02

## Context

`harness-lock.v2` records hashes for the files in `HARNESS_KERNEL_PATHS`, but a
recorded hash is not an execution boundary by itself. An active Run could be
resumed after scheduling, Completion, quality dispatch, or ledger semantics had
changed in the checkout. Its later Attempts would then appear under one Run ID
even though two Harness implementations had governed them.

Audit must remain available after drift so maintainers can inspect old Runs.
Completed historical Runs must also remain interpretable under the contract
that governed them rather than being retroactively converted into failures.

## Decision

Before an existing Run executes or accepts a mutation, require a readable,
recognized lock. For `harness-lock.v2`, compare its complete Kernel manifest
with the executing checkout. An absent or unreadable lock, an unknown schema,
or a missing, unexpected, malformed, or hash-mismatched Kernel entry is
`DRIFT`.

- `run-one`, `run`, `approve`, and `mark` fail before creating an Attempt or
  changing a Decision when drift is present.
- `init` and `kickoff` refuse any Workspace that already contains durable Run
  evidence, before template files, Pipeline projections, or Units can be
  overwritten. Their `--overwrite` flags are not Run-reset or migration flags.
- The direct Unit executor applies the same guard so callers cannot bypass the
  CLI boundary.
- Inspection-only Doctor and Audit remain available. A valid current Run may
  reconcile recoverable projections before inspection; a drifted Run is read
  in place and is not reconciled under the executing implementation.
- Audit reports Kernel-lock status. Drift is an integrity error for an active
  Run, but a completed Run remains historical evidence under its pinned
  contract.
- Recognized `harness-lock.v1` locks remain available to Doctor and Audit at
  their legacy compatibility boundary, but current mutation commands
  do not auto-authenticate or upgrade them. Relabeling a v2 lock as v1 is drift,
  not a compatibility escape hatch.

A changed Kernel therefore requires a new Run. The old lock and ledger are not
rewritten in place.

## Consequences

One Run can no longer silently cross Harness implementations, and a failed
mutation leaves no new Attempt evidence. Maintainers can still inspect and
publish bounded historical evidence after the repository evolves.

The current rule is a local integrity guard, not a filesystem sandbox or a
distributed lease. It also makes the Kernel inventory a compatibility surface:
adding a protected path intentionally prevents active older v2 Runs from
continuing under the expanded implementation.

## Related Files

- `tooling/run_state.py`
- `tooling/executor.py`
- `scripts/pipeline.py`
- `tooling/harness.py`
- `tooling/harness_contracts.py`
- `docs/SCHEMAS.md`
- `tests/test_run_state.py`
