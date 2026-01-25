---
name: survey-visuals
description: |
  Draft non-prose visuals artifacts (timeline, figure specs) for a survey, grounded in evidence and using citation keys from `citations/ref.bib`.
  **Trigger**: survey visuals, timeline, figures, visuals, 图表, 时间线, figure spec.
  **Use when**: survey 的 C4（NO PROSE），已有 outline + claim/evidence + citations，需要先把时间线/图规格落盘。
  **Skip if**: 你只关心正文（可跳过）；或缺少 `citations/ref.bib`。
  **Network**: none.
  **Guardrail**: NO PROSE；产物必须具体且可核对（含 citations），禁止遗留 TODO/SCAFFOLD。
---

# Survey Visuals (timeline + figure specs; NO PROSE)

This skill creates non-prose artifacts that make the writing stage less template-y:
- timeline / evolution bullets
- figure specs (what to draw, why it matters, what papers support it)

Tables are handled by dedicated table skills:
- `table-schema` -> `outline/table_schema.md`
- `table-filler` -> `outline/tables_index.md` (internal index)
- `appendix-table-writer` -> `outline/tables_appendix.md` (reader-facing Appendix tables)

## Inputs

- `outline/outline.yml`
- `outline/claim_evidence_matrix.md`
- `papers/paper_notes.jsonl`
- `citations/ref.bib`

## Outputs

- `outline/timeline.md`
- `outline/figures.md`

## Workflow inputs (explicit)

- Use `outline/outline.yml` + `outline/claim_evidence_matrix.md` to decide what to visualize.
- Use `papers/paper_notes.jsonl` for year/milestone candidates.
- Use only citation keys from `citations/ref.bib`.

## Workflow (heuristic)

1) Read the outline + claim-evidence matrix and pick recurring comparison axes.
2) Timeline (`outline/timeline.md`):
   - Write year -> key milestone bullets (aim for breadth and citations).
3) Figures (`outline/figures.md`):
   - Write 2-4 figure specs that a human could draw:
     - purpose (what insight this figure communicates)
     - required elements (boxes/arrows/axes)
     - what papers support each element (cite keys)
4) Use only citation keys present in `citations/ref.bib`.

## Quality checklist

- [ ] No `TODO` and no `<!-- SCAFFOLD ... -->` markers remain in the outputs.
- [ ] `outline/timeline.md` contains >=8 year bullets and each bullet has >=1 citation marker `[@...]`.
- [ ] `outline/figures.md` contains >=2 figure specs and each mentions at least one supporting citation.

## Helper script (optional)

### Quick Start

- `python .codex/skills/survey-visuals/scripts/run.py --help`
- `python .codex/skills/survey-visuals/scripts/run.py --workspace <workspace_dir>`

### All Options

- `--workspace <workspace_dir>` (required)
- `--unit-id <id>` (optional; used only for runner bookkeeping)
- `--inputs <a;b;c>` (optional; defaults to the four Inputs listed above)
- `--outputs <timeline_rel;figures_rel>` (optional; defaults to `outline/timeline.md;outline/figures.md`)
- `--checkpoint <C#>` (optional; ignored by the helper)

### Examples

- Generate timeline + figures with defaults:

  `python .codex/skills/survey-visuals/scripts/run.py --workspace workspaces/<ws>`

- Generate to custom output paths:

  `python .codex/skills/survey-visuals/scripts/run.py --workspace workspaces/<ws> --outputs outline/timeline.md;outline/figures.md`

### Notes

- The helper is intentionally minimal and never overwrites non-placeholder artifacts.
- In strict mode it blocks only if placeholder markers remain (and if minimum timeline/figure requirements are not met).

## Troubleshooting

### Issue: timeline is thin or citation-free

Fix:
- Prefer fewer, higher-signal milestones, but ensure each bullet has >=1 `[@...]`.
- Route upstream if notes are thin: strengthen `paper-notes` / `evidence-draft` rather than padding.

### Issue: figure specs read like prose

Fix:
- Keep specs as draw-instructions: purpose + elements + what each element is supported by (cite keys).
- Move narrative explanation into the main text; this file should stay non-prose.
