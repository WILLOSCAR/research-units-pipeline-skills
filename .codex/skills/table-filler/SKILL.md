---
name: table-filler
description: |
  Fill `outline/tables_index.md` from `outline/table_schema.md` + evidence packs (NO PROSE in cells; citation-backed rows).
  **Trigger**: table filler, fill tables, evidence-first tables, index tables, 表格填充, 索引表.
  **Use when**: table schema exists and evidence packs are ready; you want a compact, citation-backed index table to support later writing and Appendix table curation.
  **Skip if**: `outline/tables_index.md` already exists and is refined (>=2 tables; citations in rows; no placeholders).
  **Network**: none.
  **Guardrail**: do not invent facts; every row must include citations; do not write paragraph cells.
---

# Table Filler (index tables, evidence-first)

Goal: produce `outline/tables_index.md` as an internal, citation-backed index.

This file is a *planning/traceability artifact*:
- it is useful for debugging coverage and for quickly seeing what evidence exists
- it should NOT be pasted into the paper verbatim

Reader-facing tables belong in `outline/tables_appendix.md` and are curated by `appendix-table-writer`.

## Default mode: semantic (LLM-first)

Treat this as filling a table artifact from evidence packs:
- restate evidence pack content in compact cells
- attach citations in the row (avoid cite-dump paragraphs)

## Workflow (explicit inputs)

- Read `outline/table_schema.md` first (it defines what each table must answer).
- Use `outline/subsection_briefs.jsonl` + `outline/evidence_drafts.jsonl` to fill the subsection map and pick in-scope citations.
- Use `outline/anchor_sheet.jsonl` to fill the anchor-fact table (prefer quant/eval hooks).
- Validate cite keys against `citations/ref.bib`.

## Inputs

- `outline/table_schema.md`
- `outline/subsection_briefs.jsonl`
- `outline/evidence_drafts.jsonl`
- `outline/anchor_sheet.jsonl`
- `citations/ref.bib`

## Output

- `outline/tables_index.md`

## Output format contract

`outline/tables_index.md` must:
- contain >=2 Markdown tables
- use a caption line before each table, e.g. `**Index Table 1. ...**`
- contain no Markdown headings (`#`, `##`, `###`) unless you explicitly want them for internal readability
- include citations in rows using `[@BibKey]`
- avoid placeholders (`TODO`, `...`, `…`, scaffold comments)
- avoid paragraph cells (short phrases; use `<br>` sparingly)

## What to fill (recommended defaults)

1) Subsection map (axes + representative works)
- Axes come from `subsection_briefs.axes`.
- Representative works come from citations in the evidence pack.

2) Concrete anchors (benchmarks / numbers / caveats)
- Anchor facts come from `outline/anchor_sheet.jsonl` (curated, citation-backed).
- Representative works come from citations in the anchor sheet (or the evidence pack as fallback).

## Common failure modes

- Cells become long prose
  - Fix: compress into short phrases; move narrative explanation into prose sections.

- Rows cannot be filled without guessing
  - Fix: treat as an evidence gap (route to `evidence-selfloop` / `evidence-draft`) OR narrow the schema.

## Script (optional bootstrap)

### Quick Start

- `python .codex/skills/table-filler/scripts/run.py --help`
- `python .codex/skills/table-filler/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <workspace_dir>` (required)
- `--unit-id <id>` (optional; used only for runner bookkeeping)
- `--inputs <schema;briefs;packs;anchors;bib>` (optional; override inputs)
- `--outputs <relpath>` (optional; defaults to `outline/tables_index.md`)
- `--checkpoint <C#>` (optional; ignored by the bootstrapper)

### Examples

- Bootstrap index tables (default output path):

  `python .codex/skills/table-filler/scripts/run.py --workspace workspaces/<ws>`

- Write to a custom index file (rare):

  `python .codex/skills/table-filler/scripts/run.py --workspace workspaces/<ws> --outputs outline/tables_index.md`

Notes:
- The script is deterministic bootstrap; treat the result as an internal index artifact.
- Curate reader-facing Appendix tables separately via `appendix-table-writer`.
