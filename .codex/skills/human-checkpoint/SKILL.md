---
name: human-checkpoint
description: Review and record one pending human checkpoint in a research Workspace; use when a HUMAN Unit is blocked on an `Approve C*` decision, and never treat silence or artifact existence as approval.
---

# Human Checkpoint

A checkpoint is **consent**, not a formatting step. It binds a named human
Decision to the exact Artifacts and constraints reviewed before execution may
continue.

## Inputs

- `DECISIONS.md`.
- `UNITS.csv` and `STATUS.md` for the active checkpoint.
- Artifacts declared by the locked Pipeline for that checkpoint.

## Outputs

- Updated `DECISIONS.md`.
- A checkpoint Decision in the Run ledger.

## Steps

### 1. Identify the pending checkpoint

Inspect `STATUS.md`, `UNITS.csv`, and the active runner message. Select the
first blocked HUMAN Unit and its `C*` identifier. If multiple checkpoints
appear active or the checklist is missing, stop and repair the projection
before approving anything.

Completion criterion: exactly one pending checkpoint and its owning HUMAN Unit
are identified.

### 2. Review the declared Artifacts

Read the locked Pipeline's checkpoint contract and inspect every named Artifact.
Record requested constraints or scope changes in the checkpoint block before
approval; do not silently modify reader-facing content as part of sign-off.

Completion criterion: the reviewer can name the Artifacts inspected and any
constraints attached to the Decision.

### 3. Record approval through the adapter

Use the Pipeline adapter so the Markdown checkbox and machine Decision ledger
remain synchronized:

```bash
uv run python scripts/pipeline.py approve \
  --workspace workspaces/<name> \
  --checkpoint <C*>
```

Do not infer approval from chat silence, a completed Artifact, or an existing
but unchecked checklist item.

Completion criterion: `DECISIONS.md` contains `[x] Approve C*` and the Run
ledger records `checkpoint.approved` for the same checkpoint.

### 4. Hand execution back to the Runner

Resume through the Pipeline adapter. The Harness may complete the HUMAN Unit
and expose the next eligible Unit; this Skill does not execute downstream
semantic work itself.

Completion criterion: the checkpoint is no longer the active blocker, or one
new specific blocker is visible in durable Workspace state.

## Context Pointers

- The locked `pipelines/*.pipeline.md` owns checkpoint purpose and required
  review Artifacts.
- `DECISIONS.md` is the human-readable Decision surface.
- `.harness/decisions.jsonl` is the machine-readable history; update it
  through the adapter rather than by hand.
- Use `checkpoint-brief` to recreate a post-route checkpoint review block.
- `scripts/run.py` is a runner-compatibility helper that only toggles the
  Markdown checkbox. Prefer `scripts/pipeline.py approve`, which also records
  the machine Decision.

## Troubleshooting

- If the approvals checklist is missing after C0, materialize the review block
  with `checkpoint-brief` before approval. Use `pipeline-router` only for the
  initial C0 route.
- If reviewed upstream Artifacts later change, expect the Harness to revoke the
  stale approval and request a new Decision.
