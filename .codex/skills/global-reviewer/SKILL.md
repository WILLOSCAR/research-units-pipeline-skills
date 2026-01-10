---
name: global-reviewer
description: |
  Global consistency review for survey drafts: terminology, cross-section coherence, and scope/citation hygiene.
  Writes `output/GLOBAL_REVIEW.md` and (optionally) applies safe edits to `output/DRAFT.md`.
  **Trigger**: global review, consistency check, coherence audit, 术语一致性, 全局回看, 章节呼应, 拷打 writer.
  **Use when**: Draft exists and you want a final evidence-first coherence pass before LaTeX/PDF.
  **Skip if**: You are still changing the outline/mapping/notes (do those first), or prose writing is not approved.
  **Network**: none.
  **Guardrail**: Do not invent facts or citations; do not add new citation keys; treat missing evidence as a failure signal.
---

# Global Reviewer (survey draft)

Goal: ensure the draft reads like a coherent survey (not stitched subsections) and that definitions/claims are consistent across sections.

This skill is Stage E in the evidence-first pipeline: global review + consistency fixes.

## Inputs

- `output/DRAFT.md`
- Context (read-only):
  - `outline/outline.yml`
  - `outline/taxonomy.yml`
  - `outline/mapping.tsv`
  - `outline/claim_evidence_matrix.md`
  - `citations/ref.bib`

## Outputs

- `output/GLOBAL_REVIEW.md` (bullet report)
- `output/DRAFT.md` (optional safe edits)

## Non-negotiables

- No invented facts.
- No invented citations.
- Do not add/remove citation keys.
- If evidence is missing, the correct output is **block + TODO evidence fields**, not confident prose.

## Required structure in `output/GLOBAL_REVIEW.md`

Write a bullets-first report with these sections (use these headings verbatim so gates can verify them):

- `## A. Input integrity / placeholder leakage`
- `## B. Narrative and argument chain`
- `## C. Scope and taxonomy consistency`
- `## D. Citations and verifiability (claim -> evidence)`
- `## E. Tables and structural outputs`

Include a top bullet:

- `- Status: PASS` (or `- Status: OK`) **only after** all blocking issues are addressed.

## What to check (hard)

### A. Input integrity / placeholder leakage

- Did the outline or claim-matrix leak prompt scaffolds (ellipsis / enumerate instructions / “scope/design space/evaluation practice”)?
- Did writer copy placeholder bullets into prose?
- Do paper notes contain concrete evidence fields (metrics/datasets/compute/failure modes) or only title-level metadata?

### B. Narrative and argument chain

- For each subsection: write one thesis that is unique to that subsection (would not be true elsewhere).
- Provide 2 contrast sentences (A vs B) with citations.
- Provide 1 failure mode / counterexample with citations.

### C. Scope and taxonomy consistency

- Check scope drift: if goal is T2I but many works are T2V/T2AV, either justify in taxonomy or tighten retrieval filters.
- Check taxonomy boundaries: include/exclude rules per node; no mixed axes (model-family vs capability) without an explicit rule.

### D. Citations and verifiability (claim -> evidence)

- Produce a small claim-evidence table (5–10 rows): `claim | section | papers | evidence_field | evidence_level`.
- Flag paragraphs with weak/irrelevant citations.

### E. Tables and structural outputs

- Are tables answering a real comparison question (schema), or copying outline placeholders?
- Do tables contain citations in rows?
- If tables look ugly: classify root cause (content schema vs LaTeX template) and propose the exact fix.

## Safe edits allowed

- Unify terminology (glossary-driven search/replace).
- Add 1–2 sentence transitions between major sections.
- Tighten scope statements and conclusion RQ closure.

## Helper script

This skill includes a tiny wrapper script that scaffolds `output/GLOBAL_REVIEW.md` (placeholder headings). The actual review is LLM-driven.

- `python .codex/skills/global-reviewer/scripts/run.py --workspace <ws>`

The wrapper runs the same quality-gate checks and blocks until the report is filled and the draft passes (even without `--strict`).

### Quick Start

- `python .codex/skills/global-reviewer/scripts/run.py --workspace <ws>`

### All Options

- See `python .codex/skills/global-reviewer/scripts/run.py --help`.
- Reads context (do not modify unless you are fixing upstream): `outline/outline.yml`, `outline/taxonomy.yml`, `outline/mapping.tsv`, `outline/claim_evidence_matrix.md`, `citations/ref.bib`.

### Examples

- Create and then fill the global review:
  - Run the script once to create the scaffold: `python .codex/skills/global-reviewer/scripts/run.py --workspace workspaces/<ws>`
  - Fill `output/GLOBAL_REVIEW.md` and set `- Status: PASS` only after blocking issues are addressed.
