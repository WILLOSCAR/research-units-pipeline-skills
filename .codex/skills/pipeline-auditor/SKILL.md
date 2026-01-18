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
- **Narration-style template phrases**: flags slide-like navigation (“Next, we move from…”, “We now turn to…”) and repeated opener labels (e.g., `Key takeaway:`) that should be rewritten as content claims / argument bridges.
- **Evidence-policy disclaimer spam**: flags repeated “abstract-only/title-only evidence” disclaimers; keep evidence policy once in front matter.
- **Pipeline voice leakage**: flags phrases like `this run` that read like execution logs; rewrite as survey methodology (no pipeline/jargon).
- **Synthesis stem repetition**: flags repeated paragraph openers like `Taken together, ...`; vary synthesis phrasing and keep it content-bearing.
- **Meta survey-guidance phrasing**: flags `survey synthesis/comparisons should ...` sentences that read like process advice; rewrite as literature-facing observations (no new facts).
- **Numeric claim context**: flags metric-like numeric paragraphs that cite papers but omit minimal evaluation context tokens (benchmark/dataset/metric/budget/cost).
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

### Issue: audit fails due to evidence-policy disclaimer spam

**Fix** (skills-first):
- Keep evidence-policy limitations **once** in front matter (Introduction or Related Work).
- Remove repeated “abstract-only/title-only evidence” boilerplate from H3 sections (use `draft-polisher` to de-template without changing citation keys).

Note:
- In the default auditor behavior, these style findings may be reported as **warnings** (non-blocking) with examples; treat them as polish tasks if you want ref-like “paper voice”.

### Issue: audit fails due to narration-style navigation phrases

**Fix**:
- Replace slide-like narration (“Next, we move from…”, “We now turn to…”) with argument bridges that restate the lens/contrast (no new facts).
- Apply the edits in place (typically via `draft-polisher`), then rerun auditor.

### Issue: audit fails due to suspicious model naming (e.g., “GPT-5”)

**Fix**:
- Replace ambiguous names with the cited paper’s naming, or a neutral phrase (“a proprietary frontier model”), and add minimal evaluation context if a number is kept (task + metric + constraint/budget/cost).

### Issue: audit fails due to "unique citations too low" (survey/deep profiles)

**Fix** (skills-first; avoid ad-hoc retrieval at this stage):
- Run `citation-diversifier` to generate a per-H3 plan of *unused, in-scope* citation keys (writes `output/CITATION_BUDGET_REPORT.md`).
- Apply the plan:
  - Preferred: run `citation-injector` (edits `output/DRAFT.md` and writes `output/CITATION_INJECTION_REPORT.md`).
  - Manual fallback: add 3–6 citations per H3, preferring keys in `outline/writer_context_packs.jsonl:allowed_bibkeys_selected` that are **not already used elsewhere** in the draft.
- Keep all added citation keys within the subsection’s allowed scope (`outline/evidence_bindings.jsonl` / `allowed_bibkeys_mapped`); avoid cross-chapter “free cites”.
- Add citations via evidence-neutral phrasing (so you don't invent claims), and embed cites per-work (avoid trailing dumps), e.g.:
  - `In <topic>, systems such as X [@A] and Y [@B] illustrate distinct design points; Z [@C] explores a contrasting point under a different protocol.`
- Then rerun `draft-polisher` → `global-reviewer` → auditor.
  - If `draft-polisher` blocks due to anchoring drift after you intentionally added citations, delete `output/citation_anchors.prepolish.jsonl` and rerun to reset the baseline.
