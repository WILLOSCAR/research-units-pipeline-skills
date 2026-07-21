# ADR 0018: Snapshot Pipeline Contracts Inside Each Run

- Status: accepted
- Date: 2026-07-22

## Context

`harness-lock.v1` recorded the selected Pipeline path and SHA-256 hash, but
runtime policy was still loaded from the current repository checkout. After a
Pipeline edit, an old Workspace could therefore execute against a different
contract while retaining the earlier lock metadata. Variant Pipelines also
depend on a local base contract, so copying only the selected file would leave
part of the effective policy mutable.

## Decision

New Runs use `harness-lock.v2`. Initialization copies the repository's local
Pipeline contract bundle into `.harness/contracts/pipelines/`, records the
selected snapshot path and every bundle hash, and loads Workflow policy from
that snapshot. A missing, escaping, or hash-mismatched snapshot fails closed in
contract loading and cross-ledger integrity checks. Historical v1 locks remain
readable through the checkout-resident compatibility path.

## Consequences

Repository upgrades no longer silently redefine new Runs, and inherited
Pipeline variants retain their base contract. Each Workspace stores a small
copy of the Pipeline bundle, and v1 Runs do not gain guarantees that were not
recorded when they started. A future explicit migration command must create a
Decision and a new lock revision rather than rewriting the snapshot in place.

## Related Files

- `tooling/run_state.py`
- `tooling/common.py`
- `tooling/pipeline_spec.py`
- `docs/SCHEMAS.md`
- `tests/test_run_state.py`
