---
name: workspace-init
description: |
  Initialize a new workspace by copying the standard artifact template (STATUS.md, CHECKPOINTS.md, UNITS.csv, DECISIONS.md + folders).
  **Trigger**: workspace init, initialize workspace, workspace template, 初始化 workspace.
  **Use when**: 启动任何 pipeline run（必须先有 workspace 工件与目录骨架）。
  **Skip if**: workspace 已初始化且不希望覆盖既有文件（除非显式 `--overwrite`）。
  **Network**: none.
  **Guardrail**: 不要修改 `.codex/skills/workspace-init/assets/` 模板；默认不覆盖已有文件。
---

# Workspace Init

Create an artifact-first workspace using the standard template under `assets/workspace-template/`.

This skill is intentionally simple and deterministic.

## Input

- Target workspace directory (usually the current working directory for the run).

## Outputs

- `STATUS.md`, `CHECKPOINTS.md`, `UNITS.csv`, `DECISIONS.md`
- `GOAL.md`
- `queries.md`
- `papers/`, `outline/`, `citations/`, `output/` (with placeholder files)

## Workflow

1. Create the target workspace directory if it does not exist.
2. Copy the contents of `assets/workspace-template/` into the workspace.
3. Do not overwrite existing files unless explicitly requested; prefer merge/append when safe.
4. Ensure the four core files exist: `STATUS.md`, `UNITS.csv`, `CHECKPOINTS.md`, `DECISIONS.md`.

## Quality checklist

- [ ] Workspace contains the template files and folders.
- [ ] `UNITS.csv` is valid CSV with the required header.

## Side effects

- Allowed: create missing workspace files/directories.
- Not allowed: modify the template under `.codex/skills/workspace-init/assets/`.

## Script

### Quick Start

- `python .codex/skills/workspace-init/scripts/run.py --help`
- `python .codex/skills/workspace-init/scripts/run.py --workspace <workspace_dir>`

### All Options

- `--overwrite`: allow overwriting existing files in the target workspace

### Examples

- Create a new workspace:
  - `python .codex/skills/workspace-init/scripts/run.py --workspace workspaces/my-run`
- Re-init and overwrite template files (be careful):
  - `python .codex/skills/workspace-init/scripts/run.py --workspace workspaces/my-run --overwrite`

## Troubleshooting

### Issue: workspace already exists and files were not overwritten

**Fix**:
- This is the default behavior. Re-run with `--overwrite` only if you want to replace template files.

### Issue: you accidentally tried to use the repo root as a workspace

**Fix**:
- Always use `workspaces/<name>/` (the runner refuses to use the repo root).
