---
name: writer-selfloop
description: |
  Writing self-loop for surveys: run the strict section-quality gate, then rewrite only the failing `sections/*.md` files until the report is PASS.
  **Trigger**: writer self-loop, writing loop, quality gate loop, rewrite failing sections, 自循环, 反复改到 PASS.
  **Use when**: per-section files exist but C5 is FAIL/BLOCKED (thin sections, missing leads/front matter, citation-scope violations, generator voice).
  **Skip if**: you are still pre-C2 (NO PROSE), or evidence packs are incomplete (fix C3/C4 first).
  **Network**: none.
  **Guardrail**: do not invent facts; only use citation keys present in `citations/ref.bib`; keep citations in-scope per `outline/evidence_bindings.jsonl`; do not add/remove citation keys during rewrites.
---

# Writer Self-loop (fix only what fails)

Purpose: make writing converge **without rewriting the whole paper**.

This is the writing self-healing loop:

## Default mode: semantic triage (LLM-first)

Treat the gate as a router, not as a reason to rewrite everything.

- First, classify each failure as: evidence substrate vs writing execution vs voice contamination vs citation hygiene.
- Then, fix the earliest responsible artifact (often not the merged draft).
- Rewrite only the failing files; do not churn working sections.

If you do not run the helper script, you can still execute this skill by reading `sections/*.md` + packs and writing `output/WRITER_SELFLOOP_TODO.md` manually in the same PASS/FAIL style.

## Role cards (use explicitly)

### Writing Manager (triage + convergence)

Mission: make the draft converge by fixing only failing units and routing issues upstream when needed.

Do:
- Rewrite only files flagged by the gate (one at a time).
- If evidence is thin, route upstream instead of padding prose.
- Keep citation keys and scope stable during rewrites.

Avoid:
- Global rewrites that churn working sections.
- Rewriting around evidence gaps with generic filler.

### Router (earliest responsible artifact)

Mission: connect a visible writing failure to the earliest upstream fix.

Do:
- Template voice -> local rewrite (subsection-polisher / front-matter-writer / chapter-lead-writer).
- Thin evidence -> evidence-selfloop (notes/bindings/packs).

Avoid:
- Repeatedly rewriting the same section when the pack cannot support it.


## Role prompt: Writing Manager (triage + convergence)

```text
You are the writing manager for a survey draft.

Your job is to make the draft converge by fixing only what fails, and by routing issues to the earliest responsible artifact.

Rules:
- If a section fails because the evidence is thin or out-of-scope pressure is high, do NOT pad prose.
  Route upstream to evidence-selfloop (notes/bindings/packs) and unblock the substrate.
- If a section fails because the prose is templated (narration openers, slide navigation, repeated disclaimer spam), rewrite locally.
- Never change citation keys during rewrites; keep scope local.

Working style:
- small, auditable edits
- one failing file at a time
- every fix either (a) improves argument moves, or (b) restores paper voice
```
- the gate is deterministic (it inspects `sections/` + `sections/sections_manifest.jsonl`)
- the fixes are semantic (rewrite prose to execute argument moves and restore paper voice)

## Inputs

- `sections/sections_manifest.jsonl` (expected files + allowed citations)
- `sections/*.md` (the actual prose units)
- `outline/writer_context_packs.jsonl` (preferred per-H3 pack)
- `outline/evidence_bindings.jsonl`
- `citations/ref.bib`

Optional routing context:
- `output/EVIDENCE_SELFLOOP_TODO.md` (if evidence gaps are already known)
- `outline/subsection_briefs.jsonl`, `outline/chapter_briefs.jsonl`

## Output

- `output/WRITER_SELFLOOP_TODO.md` (report-class; always written)

## Workflow

1) Run the gate
- Run the writer self-loop script (see Script section below). It reads `sections/sections_manifest.jsonl` and the actual `sections/*.md` files.

2) Read the TODO report
- Open `output/WRITER_SELFLOOP_TODO.md` and identify the failing file paths.
- For each failing H3, load its pack from `outline/writer_context_packs.jsonl`.
- If a pack is missing or you need scope reminders, consult `outline/subsection_briefs.jsonl`; for chapter-level context (leads/throughlines), consult `outline/chapter_briefs.jsonl`.

3) Triage (writing vs evidence)

Route upstream (run `evidence-selfloop`) when:
- `output/EVIDENCE_SELFLOOP_TODO.md` already indicates missing anchors/comparisons for the same subsection
- the pack in `outline/writer_context_packs.jsonl` is too thin to satisfy argument moves without guessing
- you keep wanting out-of-scope citations outside `outline/evidence_bindings.jsonl`

Rewrite locally when:
- the pack is rich enough, but prose is template-y (narration openers, slide navigation, repeated discourse stems)
- the section has content but lacks a thesis, contrasts, evaluation anchoring, or limitations

4) Use the right playbook for the failing file type

- Front matter (`sections/abstract.md`, `sections/S<sec_id>.md` for Intro/Related Work, `sections/discussion.md`, `sections/conclusion.md`): use `front-matter-writer`.
- Chapter leads (`sections/S<sec_id>_lead.md`): use `chapter-lead-writer`.
- H3 bodies (`sections/S<sub_id>.md`): use `subsection-writer` (draft) or `subsection-polisher` (local fix).

5) Keep scope + citations stable
- Keep citation keys unchanged and validate them against `citations/ref.bib`.
- Stay in scope per `outline/evidence_bindings.jsonl` (prefer subsection-first).

6) Rerun the gate until PASS

After PASS (merge-aware voice safety):
- Proceed to `section-logic-polisher` -> `transition-weaver` -> `section-merger` -> `post-merge-voice-gate`.
- If `post-merge-voice-gate` FAILs with `source: transitions`, fix `outline/transitions.md` via `transition-weaver` and re-merge (do not patch the merged draft).

After PASS (non-blocking style hygiene):
- Open `output/WRITER_SELFLOOP_TODO.md` and read `## Style Smells (non-blocking)`.
- If it flags opener cadence / `overview` narration, run `opener-variator` on the listed files.
- If it flags count-based limitation slots (e.g., `Two limitations ...`), run `limitation-weaver` on the listed files.
- Otherwise (or after micro-fixes), run `style-harmonizer` on the listed `sections/*.md` files.
- Keep meaning + citations fixed; treat this as surface-level rewrite, not new content.

## How to fix a failing H3 (semantic recipe)

- Use `tension_statement` + `thesis` from the pack to rewrite paragraph 1 (end with the thesis).
- Use `comparison_cards` to write explicit A-vs-B contrast sentences.
- Use `evaluation_anchor_minimal` / protocol snippets to add task/metric/constraint context.
- Use limitation hooks to add a real caveat (not boilerplate).

## Paper voice repairs (high-impact, low-risk)

Narration opener -> content claim:
- Bad: `This subsection surveys ...`
- Better: start with a tension/decision/lens sentence, then end paragraph 1 with the thesis.

Slide navigation -> argument bridge:
- Bad: `Next, we move from X to Y.`
- Better: `Having established X, we can now examine how Y changes the trade-offs under comparable protocols.`

Meta \"survey should\" -> literature-facing observation:
- Bad: `Therefore, survey comparisons should ...`
- Better: `Across reported protocols, ... varies, which makes ... fragile unless ...`

Disclaimer spam -> one policy paragraph + local caveat only when needed:
- Keep evidence policy once in front matter; delete repeated \"abstract-only\" boilerplate inside H3.

## Stop conditions (when rewriting is the wrong move)

Stop and route upstream if:
- you cannot write a contrast or evaluation anchor without guessing
- the pack lacks benchmarks/metrics/protocol details needed for the subsection\x27s core claim
- fixing one H3 keeps forcing out-of-scope citations

## Failure codes -> routing (how to read the gate)

The writer gate emits short issue codes. Treat them as routers and stop trying to pad prose around missing evidence.

First classify failures:
- Evidence substrate: packs/anchors/comparisons are too thin to execute argument moves without guessing. Route upstream (`evidence-selfloop`).
- Writing execution: packs are rich enough, but the section did not execute moves (thesis/contrast/eval/limitation). Rewrite locally.
- Voice contamination: narration/slide/pipeline voice. Rewrite locally (opener + bridges), do not touch citations.
- Citation hygiene: undefined keys / out-of-scope pressure. Fix citations/bindings or rewrite to in-scope; do not add new keys.

Quick map (common codes):
- `missing_sections_manifest`, `empty_sections_manifest`, `sections_missing_files`: run `subsection-writer` (create missing files + refresh manifest).
- `sections_h3_has_headings`: remove headings; H3 bodies are body-only.
- `sections_intro_*`, `sections_related_work_*`: rewrite front matter via `front-matter-writer` (dense positioning + one methodology note).
- `sections_h3_too_few_paragraphs`, `sections_h3_too_short`: if the pack is rich, expand by executing contrasts + eval anchor + limitation; if the pack is thin, route to `evidence-selfloop`.
- `sections_h3_missing_contrast`: add explicit A-vs-B using `comparison_cards`; if cards are missing, route to `evidence-selfloop` (briefs/packs).
- `sections_h3_missing_eval_anchor`, `sections_h3_missing_cited_numeric`: add minimal protocol context (task/metric/constraint) in the same paragraph; if unknown, route upstream or weaken the claim.
- `sections_h3_missing_limitation`: add a subsection-specific limitation; if none exists in the pack, route upstream.
- `sections_h3_narration_template_opener`, `sections_h3_slide_narration`, `sections_contains_pipeline_voice`: rewrite openers/bridges to paper voice (no navigation commentary).
- `sections_h3_evidence_policy_disclaimer_spam`: delete repeats; keep evidence policy once in front matter.
- `sections_cites_missing_in_bib`: rerun `citation-verifier` (do not invent keys).
- `sections_cites_outside_mapping`: rewrite to in-scope OR fix mapping/bindings (C2/C4) and rebuild packs; do not patch in the merged draft.
- `sections_h3_sparse_citations`: if scope allows, plan adds via `citation-diversifier` then apply via `citation-injector`; if scope is too tight, expand mapping/bindings upstream.

## Script (optional; deterministic gate)

### Quick Start

- `python .codex/skills/writer-selfloop/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Generate an actionable TODO list for failing `sections/*.md`:
  - `python .codex/skills/writer-selfloop/scripts/run.py --workspace workspaces/<ws>`
