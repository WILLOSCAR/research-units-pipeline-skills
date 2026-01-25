---
name: appendix-table-writer
description: |
  Curate reader-facing survey tables for the Appendix (clean layout + high information density), using only in-scope evidence and existing citation keys.
  **Trigger**: appendix tables, publishable tables, survey tables, reader tables, 附录表格, 可发表表格, 综述表格.
  **Use when**: you have C4 artifacts (evidence packs + anchor sheet + citations) and want tables that look like a real survey (not internal logs).
  **Skip if**: `outline/tables_appendix.md` already exists and is refined (>=2 tables; citation-backed; no placeholders; not index-y).
  **Network**: none.
  **Guardrail**: no invented facts; no pipeline jargon; no paragraph cells; use only keys present in `citations/ref.bib`.
---

# Appendix Table Writer (publishable survey tables)

## Why this exists

The pipeline can produce index tables that are useful for planning/debugging, but read like internal artifacts.

This skill writes publishable, reader-facing tables that can live in an Appendix:
- cleaner layout
- higher information density
- survey-style organization (methods/benchmarks/risks), not intermediate state

Index tables remain in `outline/tables_index.md` and should not be copied verbatim into the paper.

## Inputs

- `outline/table_schema.md` (table intent + evidence mapping)
- `outline/tables_index.md` (internal index; optional but recommended)
- `outline/subsection_briefs.jsonl`
- `outline/evidence_drafts.jsonl`
- `outline/anchor_sheet.jsonl`
- `citations/ref.bib`
- Optional: `GOAL.md`

## Output

- `outline/tables_appendix.md`

## Roles (use explicitly)

### Survey Table Curator (reader lens)

Mission: choose tables a reader actually wants in a survey Appendix.

Do:
- prefer 2-3 tables that answer big questions (methods, evaluation, risks)
- make rows comparable (same row unit across the table)
- make the table legible without reading the whole paper

Avoid:
- one-row-per-H3 index dumps
- columns named like internal axes ("axes", "blocking_missing", "evidence readiness")

### Production Editor (layout)

Mission: make the table look publishable in LaTeX.

Do:
- keep columns <= 4
- keep cells short (phrases, not sentences)
- use `<br>` sparingly (0-1 per cell; never a list dump)

Avoid:
- 6-8 columns with tiny unreadable text
- cells that look like notes (semicolon chains + slash lists + long parentheticals)
- slash-separated axis markers (A/B/C) in captions/headers/cells (post-merge voice gate will flag them); use commas or 'and' instead
- internal axis jargon that reads like an intermediate artifact once printed (e.g., calling table columns "tokens"); prefer "protocol details/metadata/assumptions"

### Evidence Steward (verifiability)

Mission: prevent hallucinations.

Do:
- every row must include citations in a dedicated column (e.g., "Key refs")
- only restate what appears in evidence packs / anchor sheet
- when evidence is thin, prefer fewer rows with stronger grounding

Avoid:
- "representative works" with no supporting claim in packs/anchors
- adding benchmark/method details not present upstream

## Table contract (publishable, Appendix-ready)

`outline/tables_appendix.md` must:
- contain >=2 Markdown tables
- use a caption line before each table, e.g. `**Appendix Table A1. ...**`
- contain no headings (`#`, `##`, `###`) inside the file (the merger adds an Appendix heading)
- contain no placeholders (`TODO`, `TBD`, `FIXME`, `...`, unicode ellipsis)
- contain citations in rows using `[@BibKey]` (keys must exist in `citations/ref.bib`)
- avoid pipeline jargon and index-like column names

## Workflow (explicit inputs)

- Start from `GOAL.md` (scope) and `outline/table_schema.md` (what each table must answer).
- Use `outline/tables_index.md` as a shortlist source, but do not paste it verbatim.
- Fill rows/cells using `outline/subsection_briefs.jsonl`, `outline/evidence_drafts.jsonl`, and `outline/anchor_sheet.jsonl` (no guessing).
- Validate every cited key against `citations/ref.bib`.

## Recommended Appendix tables (default set)

If you are unsure what to build, start with these two:

1) Method/architecture map (representative works)
- Row unit: work/system line (not H3 id)
- Columns (example):
  - Work (short name)
  - Core idea (1 short phrase)
  - Loop + interface assumptions (1 short phrase; reader-facing)
  - Key refs (2-4 cite keys)

2) Evaluation protocol / benchmark map
- Row unit: benchmark / evaluation setting (or a canonical protocol dimension if benchmarks are thin)
- Columns (example):
  - Benchmark / setting
  - Task + metric (phrases, not definitions)
  - Key protocol constraints (budget/cost/latency/steps/tool access/threat model)
  - Key refs (2-4 cite keys)

Optional third (only if it stays clean):
3) Risk / threat-surface map
- Row unit: threat/failure mode category
- Columns: surface; why it matters; mitigation pattern; key refs

## Positive / negative examples (style)

Bad (index table / internal notes):
- Column: "Axes"
- Cell: `planning / memory / tools / eval / safety` (slash dump)
- Rows: every H3 id with 5+ `<br>` lines

Good (survey table):
- Column labels are reader-facing ("Core idea", "Task + metric", "Constraint")
- Cells are short phrases (no narration)
- A reader can scan and compare rows quickly

Also good (avoid intermediate-artifact tells):
- Don't label columns as "token(s)". If you need the idea, rewrite as "protocol details/metadata/assumptions".
- Avoid ASCII arrows like `->` inside cells; prefer natural phrasing (e.g., "interleaves reasoning traces with tool actions").

## When to stop / route upstream

If you cannot fill a row without guessing:
- remove the row (prefer fewer, solid rows), and
- route upstream: strengthen `evidence-draft` / `anchor-sheet` for that area.

## Script (validator-only)

### Quick Start

- `python .codex/skills/appendix-table-writer/scripts/run.py --help`
- `python .codex/skills/appendix-table-writer/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <workspace_dir>` (required)
- `--unit-id <id>` (optional; used only for runner bookkeeping)
- `--inputs <a;b;c>` (optional; ignored by the validator; kept for runner compatibility)
- `--outputs <relpath>` (optional; defaults to `outline/tables_appendix.md`)
- `--checkpoint <C#>` (optional; ignored by the validator)

### Examples

- Validate the default appendix tables file:

  `python .codex/skills/appendix-table-writer/scripts/run.py --workspace workspaces/e2e-agent-survey-latex-verify-YYYYMMDD-HHMMSS`

- Validate a workspace that writes appendix tables to a non-standard path:

  `python .codex/skills/appendix-table-writer/scripts/run.py --workspace workspaces/<ws> --outputs outline/tables_appendix.md`

Notes:
- This script does not write table content. It only validates that `outline/tables_appendix.md` is Appendix-ready.
- It always writes a short report to `output/TABLES_APPENDIX_REPORT.md`.
