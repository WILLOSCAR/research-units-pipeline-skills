---
name: tutorial-selfloop
description: |
  Run a tutorial-specific quality gate and write a PASS/FAIL report for the final tutorial deliverable.
  **Trigger**: tutorial self-loop, tutorial quality gate, tutorial pass/fail, 教程自循环, 教程质量门.
  **Use when**: `source-tutorial` 的 C3，已经有 `output/TUTORIAL.md`，想在交付前确认它满足教程合同而不是普通长文。
  **Skip if**: 还没有 tutorial 正文。
  **Network**: none.
  **Guardrail**: 报告缺口时不要发明内容；把失败清楚地路由回 tutorial 写作阶段。
---

# Tutorial Self-Loop

Goal: converge the tutorial deliverable to a stable teaching-quality bar.

The gate should compare `output/TUTORIAL.md` against the intended module shape from `outline/module_plan.yml`, rather than acting like a generic prose checker.

## Inputs

- `output/TUTORIAL.md`
- `outline/module_plan.yml`

## Outputs

- `output/TUTORIAL_SELFLOOP_TODO.md`

## Checks

- reader orientation section exists
- at least one real module exists
- each module has teaching components, not just a block of prose
- source notes are visible but lightweight

## Script

### Quick Start

- `uv run python .codex/skills/tutorial-selfloop/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>` (required)
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Run the tutorial gate:
  - `uv run python .codex/skills/tutorial-selfloop/scripts/run.py --workspace <workspace>`
