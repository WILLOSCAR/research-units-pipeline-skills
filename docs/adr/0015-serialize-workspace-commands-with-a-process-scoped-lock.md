# ADR 0015: Serialize Workspace Commands With A Process-Scoped Lock

- Status: accepted
- Date: 2026-07-16

## Context

One local Workspace stores mutable projections and append-only Run ledgers in
ordinary files. Two commands could otherwise select the same Unit, append
conflicting Attempt or Event records, reconcile the same interruption twice, or
write incompatible report snapshots. Commands such as Doctor and Status also
reconcile state before reading it, so they are not strictly read-only.

## Decision

Every Workspace command acquires one non-blocking POSIX `flock` at its outermost
entrypoint before creating, reconciling, executing, approving, marking, or
inspecting that Workspace. The diagnostic file is
`.harness/invocation.lock`; it records the operation, PID, host, and acquisition
time, but file existence alone does not indicate an active lock.

The Pipeline adapter uses an explicit fail-closed command registry. All current
Workspace commands are locked; `audit-diff` is the only exception because it
compares two already materialized report files without mutating a Run.
Product-level commands that delegate to `scripts/pipeline.py` rely on that
single lock. Product inspection commands acquire it directly. Internal Python
helpers assume the outer operation already owns the boundary and must not shell
back into another command for the same Workspace.

Command arguments and Workspace location are validated before creating lock
metadata. A missing Workspace, invalid Pipeline, or repo-root target therefore
fails without creating a partial `.harness/` directory.

Process-owned Attempts record their owner PID and host. Reconciliation may
interrupt one only after a later command owns the Workspace lock and confirms
that local process no longer exists. Manually owned Attempts intentionally span
commands and are never inferred stale from the absence of a long-lived lock.

## Consequences

Overlapping commands for one Workspace fail immediately with owner metadata;
different Workspaces can still run in parallel. The operating system releases
the lock when the owner exits, including abnormal termination, so no stale lease
cleanup protocol is required.

The owner fields improve local crash detection but are not a distributed lease:
unknown-host, legacy, and manual Attempts are handled conservatively instead of
being interrupted automatically. A `DOING` projection with no unique open
Attempt is reported as an integrity error rather than rewritten from inference.

This is local command serialization, not a distributed worker lease, database
transaction, or multi-host coordination protocol. The current implementation
requires a POSIX runtime with `fcntl` support.

## Related Files

- `tooling/run_state.py`
- `scripts/pipeline.py`
- `tooling/product_cli.py`
- `tests/test_run_state.py`
