---
name: beamer-scaffold
description: |
  Generate a Beamer slide deck from the final tutorial and approved module structure.
  **Trigger**: beamer scaffold, slides from tutorial, tutorial slides, 生成 beamer, 教程幻灯片.
  **Use when**: `source-tutorial` 的 C4，需要把 `output/TUTORIAL.md` 转成可编译的 `latex/slides/main.tex`。
  **Skip if**: 还没有 tutorial 正文。
  **Network**: none.
  **Guardrail**: slides 不能只是机械 heading dump；必须保持模块对齐并适合讲授/轻量自学。
---

# Beamer Scaffold

Goal: produce a compile-ready Beamer deck from the final tutorial.

`output/TUTORIAL.md` is the canonical prose input, while `outline/module_plan.yml` keeps the slide deck aligned with the approved module order.

## Inputs

- `output/TUTORIAL.md`
- `outline/module_plan.yml`

## Outputs

- `latex/slides/main.tex`

## Script

### Quick Start

- `uv run python .codex/skills/beamer-scaffold/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>` (required)
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Build `latex/slides/main.tex` from the tutorial:
  - `uv run python .codex/skills/beamer-scaffold/scripts/run.py --workspace <workspace>`
