---
name: chapter-briefs
description: |
  Build per-chapter (H2) writing briefs (NO PROSE) so the final survey reads like a paper (chapter leads + cross-H3 coherence) without inflating the ToC.
  **Trigger**: chapter briefs, H2 briefs, chapter lead plan, section intent, 章节意图, 章节导读, H2 卡片.
  **Use when**: `outline/outline.yml` + `outline/subsection_briefs.jsonl` exist and you want thicker chapters (fewer headings, more logic).
  **Skip if**: the outline is still changing heavily (fix outline/mapping first).
  **Network**: none.
  **Guardrail**: NO PROSE; do not invent papers; only reference subsection ids and already-mapped papers.
---

# Chapter Briefs (H2 writing cards) [NO PROSE]

Purpose: turn each **H2 chapter that contains H3 subsections** into a chapter-level writing card so the writer can:
- add a chapter lead paragraph block (coherence)
- keep a consistent comparison axis across the chapter
- avoid “8 small islands” where every H3 restarts from scratch

This artifact is **internal intent**, not reader-facing prose.

Why this matters for writing quality:
- Chapter briefs prevent the "paragraph island" failure mode: without a throughline, each H3 restarts and repeats openers.
- Treat `throughline` and `lead_paragraph_plan` as decision constraints, not copyable sentences.

## Inputs

- `outline/outline.yml`
- `outline/subsection_briefs.jsonl`
- Optional: `GOAL.md`

## Outputs

- `outline/chapter_briefs.jsonl`

## Output format (`outline/chapter_briefs.jsonl`)

JSONL (one object per H2 chapter that has H3 subsections).

Required fields:
- `section_id`, `section_title`
- `subsections` (list of `{sub_id,title}` in outline order)
- `synthesis_mode` (one of: `clusters`, `timeline`, `tradeoff_matrix`, `case_study`, `tension_resolution`)
- `synthesis_preview` (1–2 bullets; how the chapter will synthesize across H3 without template-y “Taken together…”)
- `throughline` (3–6 bullets)
- `key_contrasts` (2–6 bullets; pull from each H3 `contrast_hook` when available)
- `lead_paragraph_plan` (2–3 bullets; plan only, not prose)
  - Each bullet should be chapter-specific and mention concrete handles (axes / contrast hooks / evaluation lens).
  - Avoid generic glue like "Para 1: introduce the chapter" without naming what is being compared.
- `bridge_terms` (5–12 tokens; union of H3 bridge terms)

## How C5 uses this (chapter lead contract)

The writer uses `outline/chapter_briefs.jsonl` to draft `sections/S<sec_id>_lead.md` (body-only; no headings).

Contract (paper-like, no new facts):
- Preview the chapter’s comparison axes (2–3) and how the H3s connect; do not restate the table of contents.
- Reuse `key_contrasts` / `bridge_terms` as *handles* (not templates) so the chapter reads coherent without repeating "Taken together" everywhere.
- Keep it grounded (>=2 citations later in C5; do not invent new papers here).

## Workflow

0. (Optional) Read `GOAL.md` to pin scope/audience, and inject that constraint into the chapter throughline.
1. Read `outline/outline.yml` and list H2 chapters that have H3 subsections.
2. Read `outline/subsection_briefs.jsonl` and group briefs by `section_id`.
3. For each chapter, produce:
   - a **throughline**: what the whole chapter is trying to compare/explain
   - **key contrasts**: 2–6 contrasts that span multiple H3s
   - a **synthesis_mode**: enforce synthesis diversity across chapters (avoid repeating the same closing paragraph shape)
   - a **lead paragraph plan**: 2–3 paragraph objectives (what the chapter lead must do)
   - a **bridge_terms** set to keep terminology stable across H3s
4. Write `outline/chapter_briefs.jsonl`.

## Quality checklist

- [ ] One record per H2-with-H3 chapter.
- [ ] No placeholders (`TODO`/`…`/`(placeholder)`/template instructions).
- [ ] `throughline` and `key_contrasts` are chapter-specific (not copy/paste generic).
- [ ] `lead_paragraph_plan` bullets explicitly preview 2–3 comparison axes and how the H3 subsections partition them (no generic chapter-intro boilerplate).

## Script

### Quick Start

- `python .codex/skills/chapter-briefs/scripts/run.py --help`
- `python .codex/skills/chapter-briefs/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Default IO:
  - `python .codex/skills/chapter-briefs/scripts/run.py --workspace workspaces/<ws>`
- Explicit IO:
  - `python .codex/skills/chapter-briefs/scripts/run.py --workspace workspaces/<ws> --inputs "outline/outline.yml;outline/subsection_briefs.jsonl;GOAL.md" --outputs "outline/chapter_briefs.jsonl"`

### Refinement marker (recommended; prevents churn)

When you are satisfied with chapter briefs, create:
- `outline/chapter_briefs.refined.ok`

This is an explicit "I reviewed/refined this" signal:
- prevents scripts from regenerating and undoing your work
- (in strict runs) can be used as a completion signal to avoid silently accepting a bootstrap scaffold

### Notes

- This helper is a bootstrap; refine manually if needed.
