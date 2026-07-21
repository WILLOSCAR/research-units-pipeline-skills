---
name: checkpoint-brief
description: Project completed stage Artifacts into a concise human-review block in `DECISIONS.md`; use before a Workflow checkpoint, not for Workflow routing or approval.
---

# Checkpoint Brief

Prepare the review surface between machine-produced Artifacts and a human
checkpoint. This Skill summarizes; it does not choose a Workflow, approve a
checkpoint, or modify semantic Artifacts.

## Inputs

- the active `PIPELINE.lock.md`
- the stage Artifacts named by the current Unit
- the existing `DECISIONS.md`

## Output

- one current checkpoint block in `DECISIONS.md`

## Steps

1. Read the locked Workflow and current checkpoint.
2. Inspect only the declared stage Artifacts.
3. Summarize scope, structure, coverage, and unresolved choices without adding
   new research claims.
4. Upsert the checkpoint block while preserving the approval checklist and
   prior Decision history.
5. Stop before approval. `human-checkpoint` owns the approval Decision.

## Acceptance

- `DECISIONS.md` names the current checkpoint and the Artifacts reviewed.
- unresolved choices are explicit and bounded.
- no approval is inferred or written.
- no Pipeline lock, Unit state, or semantic Artifact is changed.

## Script

```bash
uv run python .codex/skills/checkpoint-brief/scripts/run.py \
  --workspace workspaces/<name> \
  --checkpoint C2 \
  --inputs 'outline/taxonomy.yml;outline/outline.yml'
```

The Pipeline adapter supplies the current Unit's declared `inputs`. Manual
invocations must do the same; an empty input list is reported as unreviewable
rather than inferred from unrelated Workspace files.
