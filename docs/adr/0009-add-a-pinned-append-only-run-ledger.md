# ADR 0009: Add A Pinned Append-Only Run Ledger

- Status: accepted
- Date: 2026-07-13

## Context

The original Workspace contract stored plan, current status, recovery hints,
and history across `UNITS.csv`, `STATUS.md`, logs, and per-Unit manifests. Those
files remain useful to people, but retries overwrite current status and cannot
reliably answer which Harness revision or concrete Attempt produced an
Artifact.

The project needs durable Run identity and history without migrating existing
Workflow contracts or replacing readable Workspace files.

## Decision

Add a hidden `.harness/` ledger to each initialized Workspace.

- `goal.json`, `run.json`, and `harness.lock.json` identify the Goal, current Run, and pinned execution revision.
- `events.jsonl`, `attempts.jsonl`, `artifacts.jsonl`, and `failures/ledger.jsonl` preserve append-only history.
- `plan/planned.json` preserves the initial Unit plan; `plan/effective.json` records accepted operator changes.
- `GOAL.md`, `UNITS.csv`, `STATUS.md`, and `DECISIONS.md` remain human-readable views and compatibility surfaces.
- Retries receive new Attempt IDs, and stale `DOING` recovery records an interrupted Attempt.

The current implementation remains local and single-process. Worker leases,
distributed scheduling, external evaluation, and candidate promotion are not
part of this decision.

## Consequences

Runs can now be distinguished from Workspace names, Artifacts can be traced to
Attempts, and failures can be recorded without overwriting earlier history.
The Harness interface stays compatible because existing Pipeline commands and
Workspace files remain in place.

The tradeoff is temporary dual representation: `UNITS.csv` still drives the
synchronous scheduler while `.harness/` preserves machine history. Future work
may derive more human views from the ledger after real completed Runs prove the
contract.

## Related Files

- `tooling/run_state.py`
- `tooling/executor.py`
- `tooling/harness.py`
- `scripts/pipeline.py`
- `tooling/product_cli.py`
- `docs/SCHEMAS.md`
- `tests/test_run_state.py`
