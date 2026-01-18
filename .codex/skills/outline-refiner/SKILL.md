---
name: outline-refiner
description: |
  Planner-pass coverage + redundancy report for an outline+mapping, producing `outline/coverage_report.md` and `outline/outline_state.jsonl`.
  **Trigger**: planner, dynamic outline, outline refinement, coverage report, 大纲迭代, 覆盖率报告.
  **Use when**: you have `outline/outline.yml` + `outline/mapping.tsv` and want a verifiable, NO-PROSE planner pass before writing.
  **Skip if**: you don't want any outline/mapping diagnostics (or you have a frozen/approved structure and will not change it).
  **Network**: none.
  **Guardrail**: NO PROSE; do not invent papers; only report coverage/reuse and propose structural actions as bullets.
---

# Outline Refiner (Planner pass, NO PROSE)

Goal: make the outline *auditable* by adding an explicit planner stage that answers:
- Do we have enough mapped evidence per H3?
- Are the same few papers reused everywhere?
- Are subsection axes still generic/scaffold-y?
- Is the outline likely to produce a paper-like structure (final ToC budget: ~6–8 H2; fewer, thicker H3s)?

This is a deterministic “planner” unit: it must not write survey prose.

## Inputs

Required:
- `outline/outline.yml`
- `outline/mapping.tsv`

Optional (best-effort diagnosis; may be missing early in the pipeline):
- `outline/OUTLINE_BUDGET_REPORT.md` (if present: explains recent merges; helps interpret mapping/coverage changes)
- `papers/paper_notes.jsonl` (for evidence levels)
- `outline/subsection_briefs.jsonl` (for axis specificity)
- `GOAL.md` (for scope drift hints)

## Outputs

- `outline/coverage_report.md` (bullets + small tables; NO PROSE)
- `outline/outline_state.jsonl` (append-only JSONL; one record per run)

## Workflow (planner pass, NO PROSE)

1. Parse `outline/outline.yml` to enumerate H2 sections + H3 subsections (section sizing / budget).
   - If `outline/OUTLINE_BUDGET_REPORT.md` exists, use it as the merge/change log so the coverage report can explain *why* structure changed.
2. Read `outline/mapping.tsv` and compute per-H3 coverage and reuse hotspots.
3. If `papers/paper_notes.jsonl` exists, summarize evidence levels (fulltext/abstract/title) for mapped papers.
4. If `outline/subsection_briefs.jsonl` exists, compute axis specificity (generic vs specific axes) per H3.
5. Optionally use `GOAL.md` to flag obvious scope drift (keywords not reflected in outline).
6. Write `outline/coverage_report.md` and append a run record to `outline/outline_state.jsonl`.

## Freeze policy

- If `outline/coverage_report.refined.ok` exists, the script will not overwrite `outline/coverage_report.md`.

## Script

### Quick Start

- `python .codex/skills/outline-refiner/scripts/run.py --help`
- `python .codex/skills/outline-refiner/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`: workspace root
- `--unit-id <U###>`: unit id (optional; for logs)
- `--inputs <semicolon-separated>`: override inputs (rare; prefer defaults)
- `--outputs <semicolon-separated>`: override outputs (rare; prefer defaults)
- `--checkpoint <C#>`: checkpoint id (optional; for logs)

### Examples

- Planner-pass diagnostics after `section-mapper`:
  - `python .codex/skills/outline-refiner/scripts/run.py --workspace workspaces/<ws>`

## Troubleshooting

### Issue: report is missing evidence-level or axis-specificity columns

**Cause**:
- Optional inputs are missing (no `papers/paper_notes.jsonl` and/or no `outline/subsection_briefs.jsonl`).

**Fix**:
- Run `paper-notes` and/or `subsection-briefs`, then rerun `outline-refiner`.
