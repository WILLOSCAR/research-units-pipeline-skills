---
name: idea-screener
description: "Screen the direction pool with a discussion-first scoring pass, writing `output/trace/IDEA_SCREENING_TABLE.md`."
---

# Idea Screener

## Triggers & routing

- **Trigger**: idea screener, screening table, brainstorm screening, 方向筛选表.
- **Use when**: you already have a direction pool and want a table-first comparison before curating the shortlist.


Goal: compress a direction pool into a scored comparison table that helps shortlist the most discussion-worthy directions.

The screener should reward:
- advisor-useful rank separation,
- distinct contribution shapes,
- concrete prior-work grounding,
and penalize same-template directions that only swap nouns.

## Script

### Quick Start

- `uv run python .codex/skills/idea-screener/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>` (required)
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Screen a direction pool for a brainstorm workspace:
  - `uv run python .codex/skills/idea-screener/scripts/run.py --workspace workspaces/brainstorm-llm-agents`
