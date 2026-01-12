---
name: subsection-writer
description: |
  Write section/subsection prose into per-unit files under `sections/`, so each unit can be QA’d independently before merging into `output/DRAFT.md`.
  **Trigger**: subsection writer, per-section writing, split sections, sections/, 分小节写, 按章节拆分写作.
  **Use when**: `Approve C2` is recorded and evidence packs exist; you want evidence-first drafting without a monolithic one-shot draft.
  **Skip if**: `DECISIONS.md` approval is missing, or `outline/evidence_drafts.jsonl` is incomplete/scaffolded.
  **Network**: none.
  **Guardrail**: do not invent facts/citations; no ellipsis/TODO/placeholder leakage; H3 body files must not contain headings.
---

# Subsection Writer (Per-section drafting)

Goal: write prose in **small, independently verifiable units** so we can catch:
- placeholder leakage (…/TODO)
- template boilerplate
- subsection→citation drift

This skill produces multiple files under `sections/`, plus a machine-readable manifest consumed by `section-merger`.

## Inputs

- `DECISIONS.md` (must include `Approve C2` before writing)
- `outline/outline.yml` (drives ordering + subsection ids)
- `outline/subsection_briefs.jsonl` (rq/axes/clusters/paragraph_plan)
- `outline/evidence_drafts.jsonl` (evidence packs: snippets + comparisons + limitations)
- `outline/evidence_bindings.jsonl` (allowed evidence ids / citation scope per H3)
- `citations/ref.bib` (defines valid citation keys)

## Outputs

Required:
- `sections/sections_manifest.jsonl`
- `sections/`

Optional (pipeline-dependent):
- `sections/abstract.md`
- `sections/open_problems.md`
- `sections/conclusion.md`
- `sections/evidence_note.md`

## Workflow (recommended two-pass)

0. Gate check: confirm `DECISIONS.md` has `Approve C2` (scope+outline approval).
1. Use `outline/outline.yml` to enumerate H2/H3 units and determine write order.
2. For each H3, plan paragraphs from `outline/subsection_briefs.jsonl` + `outline/evidence_drafts.jsonl`:
   - pick 3–5 contrasts from `concrete_comparisons` (use >=2 in the prose)
   - pick 2–3 evidence snippets with **concrete nouns** (benchmarks/datasets/tools/numbers)
   - pick an evaluation anchor from `evaluation_protocol` (dataset/metric/protocol when available)
   - pick failures/limitations from `failures_limitations` (use >=1 in the subsection)
3. Write the H3 body file under `sections/` (see contract below).
4. Enforce citation scope:
   - every cited key must exist in `citations/ref.bib`
   - every citation used in a subsection must be allowed by `outline/evidence_bindings.jsonl`
5. Write/update `sections/sections_manifest.jsonl` so downstream merge is deterministic.

## File contract (H3 body files)

For each H3 file (e.g., `sections/S2_1.md`):

- **Body only**: MUST NOT contain headings (`#`, `##`, `###`).
- **Evidence-first**: MUST include citations `[@BibKey]` (survey default: `>=3` unique citations per H3).
- **Grad-paragraph shape** (avoid “summary-only”): across the file, include:
  - explicit **contrast** phrasing (e.g., whereas / in contrast / 相比 / 不同于)
  - an **evaluation anchor** (benchmark/dataset/metric/protocol/评测)
  - at least one explicit **limitation / provisional** sentence (limited/unclear/受限/待验证)
- **Depth target (survey-quality)**:
  - Aim for **6–10 paragraphs** per H3 (not 1–2).
  - Aim for **~800–1400 words** per H3 (shorter only if the evidence pack is explicitly thin and you mark it as provisional).
- **No pipeline voice**: do not leak scaffold phrases like “working claim”, “axes we track”, “verification targets”.

## Roles (optional but effective)

### Role A: Argument Planner

For each H3 subsection, extract from `outline/evidence_drafts.jsonl`:
- 1 subsection thesis (subsection-specific)
- 3 snippet-derived insight candidates (pick from `claim_candidates` / `evidence_snippets`; each should name at least one concrete artifact like a benchmark/dataset/tool)
- 2 contrasts (A vs B) grounded in mapped citations
- 1 evaluation anchor sentence
- 1 limitation / verification sentence

If you can’t do this without guessing, stop and push the gap upstream (`paper-notes` / `evidence-draft`).

### Role B: Writer

Write **6–10 paragraphs** that realize the plan (survey-quality default):
- paragraph 1: scope/tension + define the comparison axis
- paragraph 2: approach family / cluster A (mechanism + assumptions) + citations
- paragraph 3: cluster A evaluation/trade-offs (benchmarks/metrics/latency/compute) + citations
- paragraph 4: approach family / cluster B (contrast with A) + citations
- paragraph 5: cluster B evaluation/trade-offs + citations
- paragraph 6: cross-paper synthesis paragraph (>=2 citations in the same paragraph)
- paragraph 7: limitations/failure modes + what needs verification (especially under abstract-only evidence)
- paragraph 8 (optional): practical implication / design guideline grounded in the contrasts
- paragraph 9 (optional): bridge to next subsection (use transition map if available)

Do not reuse framing across subsections; sentences must be anchored in the subsection’s specific evidence snippets.

### Role C: Skeptic (quick pass)

Delete or rewrite any sentence that is:
- copy-pastable into other subsections
- purely generic without concrete nouns

## Script

### Quick Start

- `python .codex/skills/subsection-writer/scripts/run.py --help`
- `python .codex/skills/subsection-writer/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`: workspace root
- `--unit-id <U###>`: unit id (optional; for logs)
- `--inputs <semicolon-separated>`: override inputs (rare; prefer defaults)
- `--outputs <semicolon-separated>`: override outputs (rare; prefer defaults)
- `--checkpoint <C#>`: checkpoint id (optional; for logs)

### Examples

- Draft all section files after evidence packs are ready:
  - Ensure `outline/evidence_drafts.jsonl` is complete (no placeholders).
  - Ensure `DECISIONS.md` has `Approve C2`.
  - Run: `python .codex/skills/subsection-writer/scripts/run.py --workspace workspaces/<ws>`

## Troubleshooting

### Issue: blocked by section-file quality gates

**Symptom**:
- `output/QUALITY_GATE.md` reports missing eval anchor / missing contrast / too few paragraphs.

**Cause**:
- The subsection reads like a title/abstract summary, not a survey comparison.

**Fix**:
- Rebuild the subsection using `grad-paragraph` (tension → contrast → eval anchor → limitation).
- If evidence packs don’t contain concrete comparison snippets, strengthen upstream evidence.

### Issue: citations outside allowed binding set

**Symptom**:
- “cites keys not mapped/bound to subsection …”

**Fix**:
- Either (a) replace with bound citations, or (b) fix `outline/mapping.tsv` + rerun `evidence-binder`.
