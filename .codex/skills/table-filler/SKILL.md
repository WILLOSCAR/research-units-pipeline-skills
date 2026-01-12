---
name: table-filler
description: |
  Fill `outline/tables.md` from `outline/table_schema.md` + evidence packs (NO PROSE in cells; citation-backed rows).
  **Trigger**: table filler, fill tables, evidence-first tables, 表格填充, 从证据包填表.
  **Use when**: table schema exists and evidence packs are ready; you want tables that never copy outline placeholders.
  **Skip if**: `outline/tables.md` already exists and is refined (>=2 tables; citations in rows; no placeholders).
  **Network**: none.
  **Guardrail**: do not invent facts; every row must include citations; do not write paragraph cells.
---

# Table Filler (Evidence-first)

Purpose: generate readable, citation-backed tables from evidence packs, with strict anti-placeholder rules.

## Inputs

- `outline/table_schema.md`
- `outline/subsection_briefs.jsonl`
- `outline/evidence_drafts.jsonl`
- `citations/ref.bib`

## Outputs

- `outline/tables.md`

## Non-negotiables

- No placeholders: no `TODO`, `<!-- SCAFFOLD -->`, ellipsis (`…`), or instruction text.
- No invented facts: tables only restate what is present in evidence packs.
- Every row must contain citations (`[@BibKey]`).

## Helper script

- `python .codex/skills/table-filler/scripts/run.py --help`
- `python .codex/skills/table-filler/scripts/run.py --workspace <ws>`

## Script

### Quick Start

- `python .codex/skills/table-filler/scripts/run.py --help`
- `python .codex/skills/table-filler/scripts/run.py --workspace <ws>`

### All Options

- See `--help`.
- Requires: `outline/table_schema.md`, `outline/subsection_briefs.jsonl`, `outline/evidence_drafts.jsonl`, `citations/ref.bib`.

### Examples

- Fill tables from schema + evidence packs:
  - Ensure `outline/table_schema.md` defines >=2 tables.
  - Ensure `outline/evidence_drafts.jsonl` has empty `blocking_missing`.
  - Ensure `citations/ref.bib` contains all cited keys.
  - Run: `python .codex/skills/table-filler/scripts/run.py --workspace workspaces/<ws>`

## Troubleshooting

### Issue: table cells become long prose

**Fix**:
- Convert cells into atomic facts/comparisons and keep prose out of table cells; move narrative into a draft section.

### Issue: rows cannot be filled from evidence packs

**Fix**:
- Treat this as an evidence gap: enrich `outline/evidence_drafts.jsonl` or adjust the schema in `outline/table_schema.md`.
