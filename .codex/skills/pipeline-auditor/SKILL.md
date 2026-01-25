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

Purpose: a deterministic “regression test” for the writing stage.

It answers:
- did we leak placeholders or planner talk?
- did citation scope drift?
- did the draft fall back to generator voice (navigation/narration templates)?
- is citation density/health sufficient for a survey-like draft?

This skill is analysis-only. It does not edit content.

## Inputs

- `output/DRAFT.md`
- `outline/outline.yml`
- Optional (recommended):
  - `outline/evidence_bindings.jsonl`
  - `citations/ref.bib`

## Outputs

- `output/AUDIT_REPORT.md`

## What it checks (deterministic)

- Placeholder leakage: ellipsis (`...`, `…`), TODO markers, scaffold tags.
- Outline alignment: section/subsection order vs `outline/outline.yml`.
- Survey tables (survey deliverable): require >=2 Markdown tables in the merged draft (index tables live in `outline/tables_index.md`) (inserted by `section-merger` from `outline/tables_appendix.md`).
- Paper voice anti-patterns:
  - narration templates (`This subsection ...`, `In this subsection ...`)
  - slide navigation (`Next, we move ...`, `We now turn to ...`)
  - pipeline voice (`this run`, “pipeline/stage/workspace” in prose)
- Evidence-policy disclaimer spam: repeated “abstract-only/title-only/provisional” boilerplate inside H3 bodies.
- Meta survey-guidance phrasing: `survey synthesis/comparisons should ...`.
- Synthesis stem repetition: repeated `Taken together, ...` and similar high-signal generator stems.
- Numeric claim context: numbers without minimal evaluation context tokens (benchmark/dataset/metric/budget/cost).
- Citation health (if `citations/ref.bib` exists): undefined keys, duplicates, basic formatting red flags.
- Citation scope (if `outline/evidence_bindings.jsonl` exists): citations used per H3 should stay within the bound evidence set.

## How to use the report (routing table)

Treat `output/AUDIT_REPORT.md` as a “what to fix next” router.

Common FAIL families -> responsible stage/skill:

- Placeholders / leaked scaffolds
  - Fix: C2–C4 artifacts are not clean. Route to `subsection-briefs` / `evidence-draft` / `writer-context-pack`, then rewrite affected sections.

- Missing overview tables (draft has <2 tables)
  - Fix: ensure `table-schema` + `appendix-table-writer` produced `outline/tables_appendix.md` (>=2 tables, citation-backed, no placeholders), then rerun `section-merger` (tables insert as an Appendix block by default).

- Planner talk in transitions / narrator bridges
  - Fix: rerun `transition-weaver` (and ensure briefs include `bridge_terms` / `contrast_hook`), then re-merge.

- Narration templates / slide navigation inside H3
  - Fix: rewrite the failing `sections/S*.md` via `writer-selfloop` (local, section-level) or `subsection-polisher`.

- Evidence-policy disclaimer spam
  - Fix: keep evidence policy once in Intro/Related Work (front matter), delete repeats in H3 (use `draft-polisher` or local section rewrites).

- Citation scope drift (out-of-scope bibkeys)
  - Fix: either (a) rewrite the subsection to stay in-scope, or (b) fix mapping/bindings (`section-mapper` → `evidence-binder`) and regenerate packs.

- Global unique citations too low
  - Fix: `citation-diversifier` → `citation-injector` (NO NEW FACTS), then `draft-polisher`.

- Intro/Related Work too thin / too few cites
  - Fix: rewrite the corresponding `sections/S<sec_id>.md` front-matter file via `writer-selfloop` (front-matter path) using dense positioning + method paragraph.

## Prevention guidance (what upstream writers should do)

If you want the auditor to PASS *without* a heavy polish loop:
- Start each H3 with a content claim + thesis (avoid narration templates).
- Use explicit contrasts and at least one evaluation anchor paragraph.
- Embed citations per claim (avoid trailing cite dumps).
- Put evidence-policy limitations once in the front matter, not in every H3.

## Script

### Quick Start

- `python .codex/skills/pipeline-auditor/scripts/run.py --help`
- `python .codex/skills/pipeline-auditor/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>` (optional; for logs)
- `--inputs <semicolon-separated>` (rare override; prefer defaults)
- `--outputs <semicolon-separated>` (rare override; default writes `output/AUDIT_REPORT.md`)
- `--checkpoint <C#>` (optional)

### Examples

- Run audit after `global-reviewer` and before LaTeX/PDF:
  - `python .codex/skills/pipeline-auditor/scripts/run.py --workspace workspaces/<ws>`

## Troubleshooting

### Issue: audit fails due to undefined citations

Fix:
- Regenerate citations with `citation-verifier` and ensure `citations/ref.bib` contains every cited key.

### Issue: audit fails due to narration-style navigation phrases

Fix:
- Rewrite as argument bridges (content-bearing handoffs, no navigation commentary) in the failing `sections/*` files, then re-merge.

### Issue: audit fails due to "unique citations too low"

Fix:
- Run `citation-diversifier` to produce `output/CITATION_BUDGET_REPORT.md`.
- Apply it via `citation-injector` (edits `output/DRAFT.md`, writes `output/CITATION_INJECTION_REPORT.md`).
- Then run `draft-polisher` → `global-reviewer` → auditor.
