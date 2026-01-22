---
name: anchor-sheet
description: |
  Extract per-subsection “anchor facts” (NO PROSE) from evidence packs so the writer is forced to include concrete numbers/benchmarks/limitations instead of generic summaries.
  **Trigger**: anchor sheet, anchor facts, numeric anchors, evidence hooks, 写作锚点, 数字锚点, 证据钩子.
  **Use when**: `outline/evidence_drafts.jsonl` exists and you want stronger, evidence-anchored writing in `sections/*.md`.
  **Skip if**: evidence packs are incomplete (fix `evidence-draft` first).
  **Network**: none.
  **Guardrail**: NO PROSE; do not invent facts; only select from existing evidence snippets/highlights.
---

# Anchor Sheet (evidence → write hooks) [NO PROSE]

Purpose: make “what to actually say” explicit:
- select quantitative snippets (numbers/percentages)
- select evaluation anchors (benchmarks/datasets/metrics)
- select limitations/failure hooks

This prevents the writer from producing paragraph-shaped but **content-poor** prose.

## Inputs

- `outline/evidence_drafts.jsonl`
- `citations/ref.bib`

## Outputs

- `outline/anchor_sheet.jsonl`

## Output format (`outline/anchor_sheet.jsonl`)

JSONL (one object per H3 subsection).

Required fields:
- `sub_id`, `title`
- `anchors` (list; each anchor has `hook_type`, `text`, `citations`, and optional `paper_id/evidence_id/pointer`)

## Workflow

1. Read `outline/evidence_drafts.jsonl`.
2. Prefer anchors that contain:
   - a number (%, counts, scores)
   - an explicit benchmark/dataset/metric token
   - an explicit limitation/failure statement
3. Filter anchors to only citation keys present in `citations/ref.bib`.
4. Write `outline/anchor_sheet.jsonl`.

## Quality checklist

- [ ] Every H3 has >=4 anchors (if evidence packs are rich).
- [ ] At least 1 anchor contains digits when the evidence pack contains digits.
- [ ] No placeholders (`TODO`/`…`/`(placeholder)`).

## Consumption policy (for C5 writers)

Anchors are intended to prevent “long but empty” prose. Treat them as **must-use hooks**, not optional ideas.

Recommended minimums per H3 (adjust for `queries.md:draft_profile`):
- >=1 evaluation anchor (benchmark/dataset/metric/protocol)
- >=1 limitation/failure hook (concrete, not generic “future work”)
- If digits exist in the evidence pack: include >=1 cited numeric anchor (digit + citation in the same paragraph)

Note:
- Anchor text is trimmed for readability and **does not** include ellipsis markers (to reduce accidental leakage into prose).

## Script

### Quick Start

- `python .codex/skills/anchor-sheet/scripts/run.py --help`
- `python .codex/skills/anchor-sheet/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Default IO:
  - `python .codex/skills/anchor-sheet/scripts/run.py --workspace workspaces/<ws>`
- Explicit IO:
  - `python .codex/skills/anchor-sheet/scripts/run.py --workspace workspaces/<ws> --inputs "outline/evidence_drafts.jsonl;citations/ref.bib" --outputs "outline/anchor_sheet.jsonl"`

### Refinement marker (recommended; prevents churn)

When you are satisfied with anchor facts (and they are actually subsection-specific), create:
- `outline/anchor_sheet.refined.ok`

This is an explicit "I reviewed/refined this" signal:
- prevents scripts from regenerating and undoing your work
- (in strict runs) can be used as a completion signal before writing
