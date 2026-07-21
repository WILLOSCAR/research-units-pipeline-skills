# ADR 0017: Bind Completion Acceptance To Recovery And Audit

- Status: accepted
- Date: 2026-07-22

## Context

Completion previously ran mandatory Workflow checks before DONE, but their
result was not part of the durable transaction. A PREPARED Manifest could be
recovered without proving that acceptance had passed, and Run Audit could show
PASS for an unfinished or acceptance-incomplete Run. Adding new top-level Audit
verdicts under the v1 schema would also break consumers that only know
PASS/ATTENTION.

## Decision

New Runs use `recoverable-provenance.v2`. Mandatory acceptance is copied into
the PREPARED/DONE Manifest and prepared/committed Completion Events. Recovery
requires matching PASS evidence and reruns the current checker. A recognized v1
PREPARED transaction may be migrated only after that checker passes; otherwise
the Unit becomes BLOCKED with an `acceptance_recovery_failed` Failure.

New reports use `run-audit.v2`. They require a Workflow-acceptance projection
and distinguish PASS, IN_PROGRESS, INCOMPLETE, and ATTENTION. Only PASS exits
zero. Improvement and Artifact Pack therefore cannot upgrade an unfinished Run
to PASS. The validator remains read-compatible with historical v1 reports.

Scorecard validation recomputes derived score, critical failures, failure
records, and verdict. Human Checkpoint Completion requires both the readable
checkbox and an append-only Decision record.

## Consequences

The active success signal is stronger and more explicit, but historical v1
proof bundles remain historical evidence rather than current-protocol proofs.
One public completed Run must be refreshed under v2. Migration is intentionally
limited to PREPARED transactions whose current acceptance can be reproduced;
historical DONE results are reported as unverified rather than inferred.

## Related Files

- `tooling/completion.py`
- `tooling/run_state.py`
- `tooling/harness.py`
- `tooling/scorecards.py`
- `tooling/executor.py`
- `docs/SCHEMAS.md`
- `tests/test_run_state.py`
- `tests/test_pipeline_harness_doctor.py`
