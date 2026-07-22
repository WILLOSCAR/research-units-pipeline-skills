# ADR 0019: Bind Checkpoint Approval To Reviewed Artifacts

- Status: accepted
- Date: 2026-07-22

## Context

A readable approval checkbox and an append-only Decision prove that an
operator approved a Checkpoint, but they do not prove which Artifact versions
were reviewed. If an outline, protocol, taxonomy, or scope brief changes after
approval, replaying the old Decision would authorize downstream execution
against evidence the operator did not see. Idea Brainstorm also allowed a C2
focus to fall back to the pre-retrieval brief, weakening the intended
post-retrieval choice.

## Decision

Each new Checkpoint approval records a `checkpoint-review-basis.v1` object in
the Decision ledger. The basis names the active HUMAN Unit and fingerprints its
declared inputs plus the inputs and outputs of its direct dependency. Approval
is valid only while those fingerprints still match. When `DECISIONS.md` is a
review input, the fingerprint includes only that Checkpoint's marked review
block and its normalized approval line. Toggling the checkbox does not
invalidate the Decision, edits inside the reviewed block do, and later blocks
for other Checkpoints cannot stale an earlier approval.

Approval commands accept only the currently active HUMAN Unit. Idea Brainstorm
C2 requires an explicit focus selection in `DECISIONS.md`; an earlier Idea
Brief cannot substitute for that Decision.

## Consequences

Stale or premature approvals fail closed and must be recorded again after the
review basis changes. Before downstream execution, a stale completed Checkpoint
is reopened, its readable approval is cleared, and dependent Unit projections
are reset for rerun. Completion and PREPARED recovery also clear the readable
checkbox and append an explicit revocation Decision when they detect stale
authorization; Run Audit applies the same approval test, so a crash boundary
cannot bypass the gate. Existing Decisions without a review basis remain
readable history but do not authorize new Completion. Checkpoint contracts must
keep their review inputs explicit enough for the Harness to fingerprint them.
The binding is intentionally local to direct review evidence rather than every
transitive ancestor, which keeps the approval payload bounded and explainable.

## Related Files

- `tooling/run_state.py`
- `tooling/executor.py`
- `tooling/ideation.py`
- `scripts/pipeline.py`
- `docs/SCHEMAS.md`
- `docs/PROJECT_LANGUAGE.md`
- `tests/test_run_state.py`
