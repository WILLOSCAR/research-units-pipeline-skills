---
name: draft-polisher
description: |
  Polish `output/DRAFT.md` to remove template-y boilerplate and improve coherence while preserving citations and meaning.
  **Trigger**: polish draft, de-template, coherence pass, 润色, 去套话, 过渡, 统一术语.
  **Use when**: `prose-writer` produced a first-pass draft but it still reads like scaffolding (repetition/ellipsis/template phrases).
  **Skip if**: Draft is already human-grade and passes quality gates; or prose is not approved in `DECISIONS.md`.
  **Network**: none.
  **Guardrail**: Do not add/remove/invent citations; keep all `[@BibKey]` keys valid and attached to the same claims.
---

# Draft Polisher (Markdown)

Goal: turn a first-pass draft into readable survey prose **without changing the evidence contract**.

This skill is Stage D in the evidence-first pipeline: de-template + coherence.

## Inputs

- `output/DRAFT.md`
- Optional context (read-only):
  - `outline/outline.yml`
  - `outline/mapping.tsv`
  - `papers/paper_notes.jsonl`
  - `citations/ref.bib`

## Output

- `output/DRAFT.md` (in-place refinement)

## Non-negotiables

1. Preserve citations exactly
   - Do not add new citation keys.
   - Do not delete citations.
   - Do not move a citation so it supports a different claim.
2. No evidence inflation
   - If a paragraph makes a claim, it must already be supported by citations that exist in the draft (or you must rewrite it into a qualified statement).
3. No template language
   - Remove scaffolding phrases like:
     - “We use the following working claim …”
     - “clusters around recurring themes …”
     - “enumerate 2-4 …”
     - “Scope and definitions / Design space / Evaluation practice …”

## Workflow (section-by-section)

For each `##` section, and each `###` subsection:

1. **Pin citations**
   - Identify all `[@...]` in the subsection.
   - For each citation span, note which sentence/claim it supports.
2. **Fix the paragraph structure**
   - Prefer a repeating micro-structure:
     - Claim (one clear sentence)
     - Evidence (1–3 sentences; cite within the paragraph)
     - Synthesis (contrast + trade-off + limitation)
3. **De-template**
   - Replace generic framing with content-bearing sentences.
   - Eliminate ellipsis (`…`) and any instruction-like fragments.
4. **Improve transitions**
   - Add minimal transitions that connect subsections (avoid “Moreover/However” spam).
   - Ensure each section has an opening paragraph that previews its substructure.
5. **Reduce repetition**
   - If two subsections share similar “takeaways/open problems” wording, rewrite both to be subsection-specific.
6. **Terminology consistency**
   - Pick canonical names for key concepts (e.g., “latent diffusion”, “DiT”, “classifier-free guidance”) and use them consistently.

## Acceptance checklist

- [ ] No `TODO/TBD/FIXME/(placeholder)` remains.
- [ ] No ellipsis placeholders (`…`) remain.
- [ ] No scaffold instruction fragments (“enumerate 2-4 …”) remain.
- [ ] Every subsection has citations and at least one paragraph with ≥2 citations.
- [ ] No obvious copy-paste boilerplate across many subsections.

## Helper script (gate wrapper)

This skill includes a tiny wrapper script so it can be used as a verifiable unit in `UNITS.csv`.

- `python .codex/skills/draft-polisher/scripts/run.py --workspace <ws>`

The wrapper runs the same quality-gate checks and blocks until the draft passes (even without `--strict`).

### Quick Start

- `python .codex/skills/draft-polisher/scripts/run.py --workspace <ws>`

### All Options

- See `python .codex/skills/draft-polisher/scripts/run.py --help`.
- Optional read-only context for better polishing decisions: `outline/outline.yml`, `outline/mapping.tsv`, `papers/paper_notes.jsonl`, `citations/ref.bib`.

### Examples

- Polish a first-pass draft:
  - Ensure `output/DRAFT.md` exists.
  - Optionally consult `outline/outline.yml` + `outline/mapping.tsv` to avoid scope drift, and `papers/paper_notes.jsonl` + `citations/ref.bib` to preserve claim→citation alignment.
