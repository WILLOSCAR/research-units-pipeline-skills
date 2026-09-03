---
name: chapter-skeleton
description: "Build a retrieval-informed chapter skeleton (`outline/chapter_skeleton.yml`) from taxonomy/core scope before stable H3 decomposition."
---

# Chapter Skeleton

## Triggers & routing

- **Trigger**: chapter skeleton, chapter-level outline, H2 skeleton, section-first survey, 章节骨架, 章级骨架.
- **Use when**: survey structure should stabilize chapter-level intent before subsection mapping and writing cards.


## Explicit refinement marker

Create `outline/chapter_skeleton.refined.ok` only after reviewing a manually refined skeleton. A changed taxonomy, goal, or generator invalidates the marker; reruns then back up and rebuild the skeleton.

## Load Order

Always read:
- `references/overview.md`

Use `scripts/run.py` only for deterministic materialization:
- read `outline/taxonomy.yml` for retrieval-informed topic structure
- read `GOAL.md` when present for scope hints
- emit `outline/chapter_skeleton.yml`
- preserve reviewed user work only through the current explicit refinement marker

## Inputs

- `outline/taxonomy.yml`
- Optional: `GOAL.md`

## Outputs

- `outline/chapter_skeleton.yml`

## Asset contract

- `assets/output_contract.json`

## Script

### Quick Start

- `uv run python .codex/skills/chapter-skeleton/scripts/run.py --workspace <workspace>`

### All Options

- `--workspace <dir>`: workspace containing `outline/taxonomy.yml`
- `--unit-id <id>`: optional harness metadata
- `--inputs <semicolon-separated>`: optional override from `UNITS.csv`
- `--outputs <semicolon-separated>`: optional output override; default is `outline/chapter_skeleton.yml`
- `--checkpoint <C*>`: optional harness metadata

### Examples

- Generate the chapter skeleton after taxonomy:
  - `uv run python .codex/skills/chapter-skeleton/scripts/run.py --workspace <workspace> --inputs 'outline/taxonomy.yml;GOAL.md' --outputs 'outline/chapter_skeleton.yml'`
