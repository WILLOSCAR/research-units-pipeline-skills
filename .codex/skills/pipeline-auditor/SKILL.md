---
name: pipeline-auditor
description: |
  Audit/regression checks for the evidence-first survey pipeline: citation health, per-section coverage, placeholder leakage, and template repetition.
  **Trigger**: auditor, audit, regression test, quality report, 审计, 回归测试.
  **Use when**: `output/DRAFT.md` exists and you want a deterministic PASS/FAIL report before LaTeX/PDF.
  **Skip if**: you are still changing retrieval/outline/evidence packs heavily (audit later).
  **Network**: none.
  **Guardrail**: do not change content; only analyze and report.
---

# Pipeline Auditor (draft audit + regression)

Goal: catch the failures your writer/polisher can accidentally produce:
- placeholder leakage (`...`, `…`, TODO)
- repeated boilerplate sentences
- missing/undefined/duplicate citations
- outline drift (H3 headings not matching `outline/outline.yml`)

Outputs are deterministic and auditable.

## Inputs

- `output/DRAFT.md`
- `outline/outline.yml`
- Optional (recommended):
  - `outline/evidence_bindings.jsonl`
  - `citations/ref.bib`

## Outputs

- `output/AUDIT_REPORT.md`

## What it checks (deterministic)

- **Placeholder leakage** in `output/DRAFT.md`: ellipsis, TODO markers, scaffold tags.
- **Outline alignment**: section/subsection order and presence compared to `outline/outline.yml`.
- **Citation health** (if `citations/ref.bib` exists): undefined keys, duplicate keys, basic formatting red flags.
- **Evidence binding hygiene** (if `outline/evidence_bindings.jsonl` exists): citations used per H3 should stay within the bound evidence set.
- **H3 parsing boundary**: treat new `##` headings as boundaries so tables/figures/open-problems sections are not accidentally attributed to the last H3.
- **Paragraph-level cite coverage**: only counts substantive paragraphs (ignores headings/tables/short transitions) when computing uncited paragraph rates, to avoid false FAILs.

## Script

### Quick Start

- `python .codex/skills/pipeline-auditor/scripts/run.py --help`
- `python .codex/skills/pipeline-auditor/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`: workspace root
- `--unit-id <U###>`: unit id (optional; for logs)
- `--inputs <semicolon-separated>`: override inputs (rare; prefer defaults)
- `--outputs <semicolon-separated>`: override outputs (rare; prefer defaults)
- `--checkpoint <C#>`: checkpoint id (optional; for logs)

### Examples

- Run audit after `global-reviewer` and before LaTeX:
  - `python .codex/skills/pipeline-auditor/scripts/run.py --workspace workspaces/<ws>`

## Troubleshooting

### Issue: audit fails due to undefined citations

**Fix**:
- Regenerate citations with `citation-verifier` (ensure `citations/ref.bib` includes every cited key), then rerun.
