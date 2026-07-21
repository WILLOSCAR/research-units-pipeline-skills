---
name: section-briefs
description: |
  Build chapter-level briefs (`outline/section_briefs.jsonl`) from chapter skeleton plus section bindings before stable H3 decomposition.
  **Trigger**: section briefs, chapter planning cards, section-first briefs, 章节 brief, 章级 brief.
  **Use when**: section bindings exist and the run needs chapter-level rationale and decomposition guidance before emitting stable H3 ids.
---

# Section Briefs

## Load Order

Always read:
- `references/overview.md`

Use `scripts/run.py` only for deterministic brief assembly:
- read `outline/chapter_skeleton.yml` for chapter IDs and target shape
- read `outline/section_bindings.jsonl` for saturation and gap signals
- read `GOAL.md` when present for run-level scope
- write `outline/section_briefs.jsonl` as planning substrate, not prose

## Inputs

- `outline/chapter_skeleton.yml`
- `outline/section_bindings.jsonl`
- Optional: `GOAL.md`

## Outputs

- `outline/section_briefs.jsonl`

## Asset contract

- `assets/output_contract.json`

## Script

### Quick Start

- `uv run python .codex/skills/section-briefs/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>`: workspace containing chapter skeleton and section bindings
- `--unit-id <id>`: optional harness metadata
- `--inputs <semicolon-separated>`: optional override from `UNITS.csv`
- `--outputs <semicolon-separated>`: optional output override; default is `outline/section_briefs.jsonl`
- `--checkpoint <C*>`: optional harness metadata

### Examples

- Build chapter-level briefs from the section-first layer:
  - `uv run python .codex/skills/section-briefs/scripts/run.py --workspace <workspace> --inputs 'outline/chapter_skeleton.yml;outline/section_bindings.jsonl;GOAL.md' --outputs 'outline/section_briefs.jsonl'`
