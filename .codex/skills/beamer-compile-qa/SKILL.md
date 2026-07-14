---
name: beamer-compile-qa
description: |
  Compile the Beamer tutorial deck and write a build report.
  **Trigger**: beamer compile, slides compile, tutorial slides pdf, 编译幻灯片, beamer pdf.
  **Use when**: `source-tutorial` 的 C4，已有 `latex/slides/main.tex`，需要输出 `latex/slides/main.pdf` 和编译报告。
  **Skip if**: slides scaffold 还没完成。
  **Network**: none.
  **Guardrail**: 编译失败也要落盘可读报告，不能只返回报错。
---

# Beamer Compile QA

Goal: compile the Beamer deck and record success or failure in a stable report.

The compiler should treat `latex/slides/main.tex` as the entrypoint and emit both `latex/slides/main.pdf` and `output/SLIDES_BUILD_REPORT.md`.

## Inputs

- `latex/slides/main.tex`

## Outputs

- `latex/slides/main.pdf`
- `output/SLIDES_BUILD_REPORT.md`

## Script

### Quick Start

- `uv run python .codex/skills/beamer-compile-qa/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>` (required)
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Compile the Beamer deck:
  - `uv run python .codex/skills/beamer-compile-qa/scripts/run.py --workspace <workspace>`
