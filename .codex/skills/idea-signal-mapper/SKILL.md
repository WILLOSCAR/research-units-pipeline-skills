---
name: idea-signal-mapper
description: "Map paper notes + taxonomy into a signal table of tensions, missing pieces, and promising academic axes for brainstorm discussion. Writes `output/trace/IDEA_SIGNAL_TABLE.md`."
---

# Idea Signal Mapper

## Triggers & routing

- **Trigger**: idea signal table, brainstorm signals, research tensions, signal map, 研究信号表, tension map.
- **Use when**: you have a core set, a taxonomy, and paper notes, and need a table-first bridge from literature evidence to possible directions.


Goal: create a reusable, table-first artifact that answers:
- where the literature tension is concrete rather than generic,
- which missing control or missing comparison actually keeps the question open,
- what the literature already suggests,
- where the tension lies,
- what is still missing,
- which academically meaningful axis might be worth deeper discussion.

## Script

### Quick Start

- `uv run python .codex/skills/idea-signal-mapper/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>` (required)
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Map signals for a brainstorm workspace:
  - `uv run python .codex/skills/idea-signal-mapper/scripts/run.py --workspace workspaces/brainstorm-llm-agents`
