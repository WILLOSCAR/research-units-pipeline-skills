---
name: workspace-init
description: Initialize a missing research Workspace from the repository template without overwriting existing Run state; use before Pipeline binding when the target under `workspaces/` has no valid core artifacts.
---

# Workspace Init

Initialization is a **boundary**: it creates Workspace-owned state and leaves
existing state untouched unless overwrite is an explicit operator decision.
It does not select a Workflow or execute a Unit.

## Inputs

- Target directory under `workspaces/<name>/`.
- Optional explicit overwrite decision.

## Outputs

- `STATUS.md`, `CHECKPOINTS.md`, `UNITS.csv`, and `DECISIONS.md`.
- `GOAL.md` and `queries.md`.
- `papers/`, `outline/`, `citations/`, and `output/` directories.

## Steps

### 1. Validate the destination

Resolve the target path and reject the repository root. Inspect existing files
before deciding whether initialization is missing, partial, or already
complete. Never infer overwrite permission from a partial Workspace.

Completion criterion: the destination is a Workspace path and every existing
file that could be replaced is known.

### 2. Materialize the base template

Copy the repository-owned template into the target. Default to create-missing;
use `--overwrite` only after an explicit replacement decision.

Completion criterion: all missing base files and directories are materialized,
and no pre-existing file was replaced without explicit permission.

### 3. Verify the core contract

Confirm that `STATUS.md`, `UNITS.csv`, `CHECKPOINTS.md`, and `DECISIONS.md`
exist. Parse the `UNITS.csv` header and reject malformed CSV rather than
leaving a superficially initialized Workspace.

Completion criterion: the four core files exist and `UNITS.csv` has the
required schema.

### 4. Hand off to Workflow binding

Leave Workflow selection and Pipeline-specific Unit materialization to
`pipeline-router` or the Pipeline adapter. The generic template is not evidence
that a Goal has been routed.

Completion criterion: the Workspace can be passed to the router without
requiring any state from chat history.

## Context Pointers

- Read `assets/workspace-template/` only when inspecting or changing the base
  template contract.
- Read the selected `pipelines/*.pipeline.md` only after Workflow binding.
- Use `research-pipeline-runner` when the user asked to continue beyond
  initialization.

## Script

### Quick Start

```bash
uv run python .codex/skills/workspace-init/scripts/run.py \
  --workspace workspaces/<name>
```

### All Options

- `--workspace <path>`: target Workspace.
- `--overwrite`: replace existing template-owned files after explicit approval.
- `--unit-id`, `--inputs`, `--outputs`, `--checkpoint`: Pipeline-runner
  compatibility arguments.

### Examples

Inspect the interface before use:

```bash
uv run python .codex/skills/workspace-init/scripts/run.py --help
```

Replace template files only after an explicit reset decision:

```bash
uv run python .codex/skills/workspace-init/scripts/run.py \
  --workspace workspaces/<name> \
  --overwrite
```

## Troubleshooting

- Existing files remain unchanged by default. This is the expected idempotent
  behavior, not an initialization failure.
- Never point the script at the repository root; use `workspaces/<name>/`.
