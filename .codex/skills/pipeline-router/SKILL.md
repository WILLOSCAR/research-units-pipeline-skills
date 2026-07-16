---
name: pipeline-router
description: Route an unbound research Goal to one Workflow and materialize its Pipeline lock and checkpoint questions; use when no valid `PIPELINE.lock.md` exists or the active checkpoint lacks a Decision block.
---

# Pipeline Router

Routing is a **commitment**: select one Workflow from the desired Artifact and
evidence method, record that choice, and expose the next human Decision.

## Inputs

- `GOAL.md`, or the current user request when the Workspace is new.
- Existing `PIPELINE.lock.md`, `UNITS.csv`, `STATUS.md`, and `DECISIONS.md` when
  present.
- `docs/PIPELINE_TAXONOMY.md` and candidate Pipeline front matter during
  selection.

## Outputs

- `PIPELINE.lock.md` for a newly bound Goal.
- A checkpoint block in `DECISIONS.md`.
- `queries.md` when the selected retrieval Workflow starts at C0.
- A synchronized current Pipeline/checkpoint projection in `STATUS.md`.

## Steps

### 1. Establish the requested Artifact

Read the Goal and identify:

- the reader-facing deliverable;
- the evidence method it requires;
- the requested format or delivery profile;
- the decisions that materially change Workflow selection.

When a routing discriminator is missing, write the smallest grouped question
set to `DECISIONS.md` and stop at that Decision.

Completion criterion: every fact that can change the Workflow choice is known
or explicitly bounded in `DECISIONS.md`.

### 2. Select one Workflow

Load `docs/PIPELINE_TAXONOMY.md`, then inspect only the candidate Pipeline
contracts. Choose from target Artifact and evidence method rather than keyword
matching alone. Treat delivery profiles and course-report use cases as overlays
inside their existing Workflow family.

Completion criterion: exactly one executable Pipeline is selected and its
target Artifacts match the Goal.

### 3. Materialize the commitment

Write `PIPELINE.lock.md` with:

```text
pipeline: <pipeline path>
units_template: <template path from Pipeline front matter>
locked_at: <YYYY-MM-DD>
```

Initialize `UNITS.csv` from that template when the Workspace is new. Preserve a
valid existing lock; a route change is an explicit operator Decision followed
by reinitialization or migration, never a silent rewrite.

Completion criterion: the lock, Unit template, and Workspace projection refer
to the same Pipeline.

### 4. Expose the next checkpoint

Materialize the active checkpoint block and approval checkbox in
`DECISIONS.md`. At C0, seed `queries.md` from the Goal when retrieval is part of
the selected Workflow.

The deterministic helper may be used after selection:

```bash
uv run python .codex/skills/pipeline-router/scripts/run.py \
  --workspace workspaces/<name> \
  --checkpoint <C0|C1|C2>
```

Completion criterion: `DECISIONS.md` contains the active checkpoint and one
clear approval or answer surface; retrieval Workflows have a non-empty C0 query
seed.

### 5. Verify the route

Check that the locked Pipeline exists, its Unit template exists, and the active
checkpoint is represented in both `STATUS.md` and `DECISIONS.md`.

Completion criterion: the Pipeline Runner can continue from Workspace files
without making another routing inference.

## Context Pointers

- Read `docs/PIPELINE_TAXONOMY.md` only while selecting or deliberately changing
  a Workflow.
- After selection, the locked `pipelines/*.pipeline.md` is the execution
  contract and the taxonomy leaves context.
- Use `assets/pipeline-selection-form.md` only when missing routing facts require
  a human answer.
- Run the helper with `--help` when checkpoint materialization needs debugging;
  the helper records a route but does not choose one.
