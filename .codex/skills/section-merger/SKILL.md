---
name: section-merger
description: |
  Deterministically merge per-section files under `sections/` into `output/DRAFT.md`, preserving outline order and weaving transitions from `outline/transitions.md`.
  **Trigger**: merge sections, merge draft, combine section files, sections/ -> output/DRAFT.md, 合并小节, 拼接草稿.
  **Use when**: you have per-unit prose files under `sections/` and want a single `output/DRAFT.md` for polishing/review/LaTeX.
  **Skip if**: section files are missing or still contain scaffolding markers (fix `subsection-writer` first).
  **Network**: none.
  **Guardrail**: deterministic merge only (no new facts/citations); preserve section order from `outline/outline.yml`.
---

# Section Merger

Goal: assemble a paper-like `output/DRAFT.md` from:
- `sections/` (per-section/per-subsection prose)
- `outline/transitions.md` (inserted as short hand-offs between adjacent units)

Evidence-first visuals (`outline/tables.md`, `outline/timeline.md`, `outline/figures.md`) are **intermediate artifacts by default**. If you want them in the final PDF, weave them into the relevant prose sections intentionally (instead of auto-injecting them as top-level ToC chapters).

This skill is **deterministic**: it does not rewrite content or invent prose; it only merges already-generated content.

## Inputs

- `outline/outline.yml` (drives section/subsection order)
- `outline/transitions.md` (optional but recommended)
- Optional (diagnostics): `sections/sections_manifest.jsonl`
- Optional context: `GOAL.md`

## Outputs

- `output/DRAFT.md`
- `output/MERGE_REPORT.md`

## Workflow (deterministic)

1. Read `GOAL.md` (if present) and use its first non-heading line as the draft title.
2. Read `outline/outline.yml` to determine the expected section/subsection order.
3. Merge the per-unit files under `sections/`.
4. Insert transitions from `outline/transitions.md` when present.
5. Write `output/DRAFT.md` and a deterministic `output/MERGE_REPORT.md` (missing files, ordering).

## Script

### Quick Start

- `python .codex/skills/section-merger/scripts/run.py --help`
- `python .codex/skills/section-merger/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`: workspace root
- `--unit-id <U###>`: unit id (optional; for logs)
- `--inputs <semicolon-separated>`: override inputs (rare; prefer defaults)
- `--outputs <semicolon-separated>`: override outputs (rare; prefer defaults)
- `--checkpoint <C#>`: checkpoint id (optional; for logs)

### Examples

- Standard merge (outline + transitions + section files):
  - `python .codex/skills/section-merger/scripts/run.py --workspace workspaces/<ws>`

## Troubleshooting

### Issue: merge report says a subsection file is missing

**Likely cause**:
- A required `sections/*.md` file has not been written yet (check `sections/sections_manifest.jsonl` if present to see which units exist).

**Fix**:
- Write the missing units under `sections/` (typically via `subsection-writer`) and rerun merge.
