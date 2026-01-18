---
name: subsection-polisher
description: |
  Polish a single H3 unit file under `sections/` into survey-grade prose (de-template + contrast/eval/limitation), without changing citation keys.
  **Trigger**: subsection polisher, per-subsection polish, polish section file, 小节润色, 去模板, 结构化段落.
  **Use when**: `sections/S*.md` exists but reads rigid/template-y; you want to fix quality locally before `section-merger`.
  **Skip if**: subsection files are missing, evidence packs are incomplete, or `Approve C2` is not recorded.
  **Network**: none.
  **Guardrail**: do not invent facts/citations; do not add/remove citation keys; keep citations within the same H3; keep citations subsection-scoped.
---

# Subsection Polisher (local, pre-merge)

Purpose: upgrade one `sections/S<sub_id>.md` (H3 body-only) so it reads like survey prose **before** you merge into `output/DRAFT.md`.

This is intentionally local: fix one unit at a time, then rerun gates so you converge without rewriting the whole draft.

## Inputs

- One target file under `sections/`: `sections/S<sub_id>.md` (H3 body-only)
- Preferred context: `outline/writer_context_packs.jsonl`
- Fallback context: `outline/subsection_briefs.jsonl` + `outline/evidence_drafts.jsonl`
- `citations/ref.bib`

## Output

- Updated `sections/S<sub_id>.md` (same path; citation keys unchanged)

## Paper voice constraints (soft, not robotic)

- Delete outline narration: `This subsection ...`, `In this subsection, we ...`, `Next, we ...`, `We now turn to ...`.
- Keep signposting light: avoid repeating the same opener stem across many subsections (including literal `Key takeaway:` labels).
- Keep evidence-policy disclaimers out of H3 prose; keep them once in front matter, unless the caveat is truly subsection-specific.
- Use calm academic tone; avoid hype (`clearly`, `obviously`, `breakthrough`) and avoid “PPT speaker notes”.

## Workflow (one subsection)

1) **Load the plan + evidence**
- Read the subsection’s record in `outline/writer_context_packs.jsonl` (preferred) or the matching brief in `outline/subsection_briefs.jsonl` + evidence pack in `outline/evidence_drafts.jsonl`.
- From that pack/brief, list: 2–3 concrete contrasts, 1 evaluation anchor (benchmark/dataset/metric/protocol), and 1 limitation you will explicitly mention.

2) **Opener pass (paragraph 1)**
- Remove any narration opener.
- Write a short, content-bearing setup and end paragraph 1 with the brief’s `thesis` (or a faithful paraphrase with the same commitment level).

3) **Paragraph pass (argument > listing)**
- Rewrite paragraph-by-paragraph using `grad-paragraph` micro-structure (tension → contrast → evaluation anchor → limitation).
- Ensure at least one cross-paper synthesis paragraph with >=2 citations in the same paragraph.
- Keep citations embedded inside the sentences they support; avoid trailing citation dumps.
- Keep citation keys unchanged and valid in `citations/ref.bib`.

4) **Rhythm pass (make it feel written)**
- Vary paragraph openings; don’t start every paragraph with `However/Moreover/Taken together`.
- Prefer mid-sentence ties (`...; however, ...`) and concrete nouns (systems/benchmarks/protocols) over generic glue.

5) **Recheck**
- Run `section-logic-polisher` and fix FAILs (no new citations; keep keys stable).
- Run `subsection-writer` gates; if the file still fails, fix only what the report flags.

## Troubleshooting

### Issue: you can’t write a concrete contrast without guessing

**Cause**: evidence packs are title-only / abstract-only without concrete comparison snippets.

**Fix**: strengthen upstream evidence (`paper-notes` → `evidence-draft`) rather than writing filler prose.

### Issue: the subsection passes gates but still feels “generated”

**Fix**:
- Remove repeated opener stems and slide-like navigation phrases.
- Replace generic summary sentences with subsection-specific contrasts (A vs B) and one explicit evaluation anchor.
