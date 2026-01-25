---
name: table-schema
description: |
  Define evidence-first table schemas for a survey: what each table must answer, row unit, columns, and which evidence-pack fields are required to fill it.
  **Trigger**: table schema, schema-first tables, table design, 表格 schema, 先 schema 后填充.
  **Use when**: you want survey tables that are verifiable and fillable before LaTeX (typically Stage C4, after evidence packs exist).
  **Skip if**: `outline/table_schema.md` already exists and is refined (covers both index tables and Appendix tables; no placeholders; evidence mapping is explicit).
  **Network**: none.
  **Guardrail**: no invented facts; schema must be checkable and map each column to an evidence source.
---

# Table Schema (two layers: index vs Appendix)

Tables are not decorations; they are compression.

A common failure mode in this pipeline: the first table that gets generated looks like an internal index.
So we separate tables into two layers:

1) `outline/tables_index.md` (internal)
- purpose: coverage/debugging + fast evidence scan
- allowed to be more exhaustive
- should NOT be inserted into the paper

2) `outline/tables_appendix.md` (reader-facing)
- purpose: publishable survey tables (clean layout + high information density)
- can be inserted into the final PDF as Appendix

This skill designs both layers before filling.

## Default mode: semantic (LLM-first)

Treat this as a design task, not running a script.

If a column cannot be filled from existing evidence packs without guessing, the schema is wrong.

## Roles (use explicitly)

### Table Designer (reader lens)

Mission: choose tables that answer reader questions, not pipeline questions.

Do:
- make each table answer one question
- keep tables small enough to fill (two good tables beat one impossible mega-table)

Avoid:
- internal/log-style tables inside the paper
- column labels that only make sense inside this repo

### Evidence Steward (fillability)

Mission: refuse schemas that require invented facts.

Do:
- map every column to concrete upstream fields
- reject columns that would force long paragraph cells

Avoid:
- TODO columns
- placeholders ("TBD", "...", "(placeholder)")

## Workflow (explicit inputs)

- Use `GOAL.md` to keep the reader question and scope stable.
- Use `outline/outline.yml` to align table row units with the paper structure.
- Use `outline/subsection_briefs.jsonl` to ground table dimensions/axes in the approved structure.
- Use `outline/evidence_drafts.jsonl` to ensure every planned column is fillable without guessing.

## Inputs

- `outline/outline.yml`
- `outline/subsection_briefs.jsonl`
- `outline/evidence_drafts.jsonl`
- Optional: `GOAL.md`

## Output

- `outline/table_schema.md`

## Non-negotiables (schema contract)

- Minimum definitions:
  - Index tables: >=2
  - Appendix tables: >=2
- Every table definition must include:
  - the question it answers
  - the row unit (H3 / benchmark / work / failure mode)
  - columns (with cell style constraints)
  - evidence mapping (which upstream fields fill which columns)
- Cell style: short phrases; avoid paragraph cells.
- Paper voice: Appendix table captions/columns must be publishable (no pipeline jargon).

## Recommended defaults (arxiv-survey family)

### Index tables (for `table-filler` -> `outline/tables_index.md`)

I1) Subsection map (axes + representative works)
- Row unit: H3
- Columns: subsection; axes; representative works
- Evidence sources: `subsection_briefs.axes` + citations from `evidence_drafts`

I2) Concrete anchors (benchmarks / numbers / caveats)
- Row unit: H3
- Columns: subsection; anchor facts; representative works
- Evidence sources: `anchor_sheet.anchors`

### Appendix tables (for `appendix-table-writer` -> `outline/tables_appendix.md`)

A1) Method/architecture map (representative works)
- Row unit: work/system line
- Columns: work; core idea; loop + interface assumptions; key refs
- Evidence sources: `evidence_drafts` (comparisons + definitions) + `anchor_sheet`

A2) Evaluation protocol / benchmark map
- Row unit: benchmark or evaluation setting (fallback: protocol dimension)
- Columns: benchmark/setting; task+metric; key protocol constraints; key refs
- Evidence sources: `anchor_sheet` + `evidence_drafts.evaluation_protocol`

## Positive / negative examples

Good (publishable question + fillable columns):
- Question: "Which benchmarks anchor evaluation in this area, and what task/metric/constraints do they imply?"
- Columns: Benchmark; Task+metric; Protocol constraints; Key refs
- Evidence mapping: `evidence_drafts.evaluation_protocol` + `anchor_sheet`

Bad (internal/pipeline voice):
- Question: "What is evidence readiness + verification needs?"
- Columns: evidence levels, missing fields, TODO checklist

If you want internal diagnostics, put them in an audit report, not in reader-facing tables.

## Script (optional bootstrap)

### Quick Start

- `python .codex/skills/table-schema/scripts/run.py --help`
- `python .codex/skills/table-schema/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <workspace_dir>` (required)
- `--unit-id <id>` (optional; used only for runner bookkeeping)
- `--inputs <outline;briefs;packs;goal>` (optional; override inputs)
- `--outputs <relpath>` (optional; defaults to `outline/table_schema.md`)
- `--checkpoint <C#>` (optional; ignored by the bootstrapper)

### Examples

- Bootstrap a two-layer schema (index + Appendix):

  `python .codex/skills/table-schema/scripts/run.py --workspace workspaces/<ws>`

- Write to a custom schema path (rare):

  `python .codex/skills/table-schema/scripts/run.py --workspace workspaces/<ws> --outputs outline/table_schema.md`

Notes:
- Use the script as a starting point, then refine the schema as a paper artifact.
- If a column cannot be filled from evidence packs without guessing, the schema is wrong.
