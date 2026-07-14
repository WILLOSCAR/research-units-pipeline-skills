---
name: idea-direction-generator
description: |
  Generate a compact pool of discussion-worthy research directions from the signal table, writing `output/trace/IDEA_DIRECTION_POOL.md`.
  **Trigger**: idea direction pool, brainstorm directions, research directions, 研究方向池, brainstorm pool.
  **Use when**: you already have a signal table and want a small, non-isomorphic set of candidate directions.
  **Skip if**: `output/trace/IDEA_DIRECTION_POOL.md` already exists and is refined.
  **Network**: none.
  **Guardrail**: no invented papers; directions must stay anchored to the current signal table and core set.
---

# Idea Direction Generator

Goal: turn a signal table into a modest pool of discussion-worthy research directions.

This skill should favor:
- distinct thesis programs rather than same-shape confound cards,
- short scan-friendly titles,
- explicit contribution shapes and quick falsifiers,
- distinct research lenses,
- academically meaningful tensions,
- low-template cards,
- and lightweight first probes.

## Script

### Quick Start

- `uv run python .codex/skills/idea-direction-generator/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>` (required)
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Generate a direction pool for a brainstorm workspace:
  - `uv run python .codex/skills/idea-direction-generator/scripts/run.py --workspace workspaces/brainstorm-llm-agents`
