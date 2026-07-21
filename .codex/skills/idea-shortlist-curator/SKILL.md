---
name: idea-shortlist-curator
description: |
  Converge the screened direction pool into a small, discussion-ready shortlist, writing `output/trace/IDEA_SHORTLIST.md`.
  **Trigger**: idea shortlist, shortlist directions, brainstorm shortlist, 方向 shortlist.
  **Use when**: you already have a direction pool and screening table and want the strongest 3-5 directions for the final memo.
---

# Idea Shortlist Curator

## Load Order

Always read:
- `references/overview.md`

Read by task:
- `references/ranking_rubric.md` when customizing risk notes or deferral reasons
- `assets/rationale_templates.json` when changing deterministic shortlist rationale wording or rule order

## Script Boundary

Use `scripts/run.py` only for:
- diversity-aware greedy selection from screened rows
- deterministic ranking record assembly and JSONL/Markdown output

Do not treat `run.py` as the place for:
- domain-specific risk narratives that should be inspectable from references
- reader-facing prose templates for the final memo (those belong in `idea-memo-writer`)

Goal: turn a direction pool into a small shortlist that is:
- explicitly ranked with a real why-#1>#2>#3 argument,
- diverse in program shape rather than just cluster labels,
- specific about why deferred directions are not in the lead set,

and remains:
- academically interesting,
- distinct enough to compare,
- grounded enough to discuss,
- and not yet overfrozen into project plans.

## Script

### Quick Start

- `uv run python .codex/skills/idea-shortlist-curator/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>` (required)
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Curate a shortlist for a brainstorm workspace:
  - `uv run python .codex/skills/idea-shortlist-curator/scripts/run.py --workspace workspaces/brainstorm-llm-agents`
