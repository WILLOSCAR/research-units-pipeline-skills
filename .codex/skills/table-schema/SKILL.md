---
name: table-schema
description: |
  Define evidence-first table schemas for a survey (NO PROSE): what each table must answer, columns, and which evidence-pack fields are required to fill it.
  **Trigger**: table schema, schema-first tables, table design, 表格 schema, 先 schema 后填充.
  **Use when**: you want tables to be verifiable and non-placeholder before LaTeX (typically Stage C4 after evidence packs exist).
  **Skip if**: `outline/table_schema.md` already exists and is refined (no placeholders; >=2 tables defined).
  **Network**: none.
  **Guardrail**: NO PROSE; do not invent facts; schema must be checkable and map each column to an evidence source.
---

# Table Schema (Evidence-first, NO PROSE)

Purpose: prevent “ugly tables” by fixing the **information architecture first** (questions + columns + evidence sources), before any filling.

## Inputs

- `outline/outline.yml`
- `outline/subsection_briefs.jsonl`
- `outline/evidence_drafts.jsonl`
- Optional: `GOAL.md`

## Outputs

- `outline/table_schema.md`

## Non-negotiables

- NO PROSE: schemas are bullets-only.
- No placeholders: no `TODO`, `(placeholder)`, `<!-- SCAFFOLD -->`, or ellipsis (`…`).
- Each table must define:
  - the **question** it answers
  - the **row unit** (subsection / cluster / paper)
  - each **column** + its allowed content style (short phrases; no long prose cells)
  - **evidence mapping**: which evidence-pack fields are required for each column

## Helper script

- `python .codex/skills/table-schema/scripts/run.py --help`
- `python .codex/skills/table-schema/scripts/run.py --workspace <ws>`

## Script

### Quick Start

- `python .codex/skills/table-schema/scripts/run.py --help`
- `python .codex/skills/table-schema/scripts/run.py --workspace <ws>`

### All Options

- See `--help`.
- Reads: `outline/outline.yml`, `outline/subsection_briefs.jsonl`, `outline/evidence_drafts.jsonl`.
- Optional: `GOAL.md` (for scope + table questions).

### Examples

- Create schema-first table specs:
  - Ensure `outline/evidence_drafts.jsonl` exists so columns can be tied to evidence fields.
  - Run: `python .codex/skills/table-schema/scripts/run.py --workspace workspaces/<ws>`
