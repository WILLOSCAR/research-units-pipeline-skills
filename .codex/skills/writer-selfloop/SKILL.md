---
name: writer-selfloop
description: |
  Self-loop for survey writing: read `output/QUALITY_GATE.md`, then rewrite only the failing per-section files under `sections/` until the gates pass.
  **Trigger**: writer self-loop, quality gate loop, rewrite failing sections, expand thin sections, 自循环, 反复改到 PASS.
  **Use when**: `subsection-writer` is BLOCKED (missing/short/thin H3, citation scope errors, missing chapter leads).
  **Skip if**: you are still pre-C2 (NO PROSE), or evidence packs/anchor sheet are incomplete (fix C3/C4 first).
  **Network**: none.
  **Guardrail**: do not invent facts; only use citation keys present in `citations/ref.bib`; keep citations subsection- or chapter-scoped per `outline/evidence_bindings.jsonl`; H3 body files must not contain headings.
---

# Writer Self-loop (Fix → Recheck → Repeat)

Purpose: make the writing stage converge **without rewriting everything**.

This skill reads `output/QUALITY_GATE.md`, pinpoints which `sections/*.md` files failed, and iterates only on those files until `subsection-writer` passes.

## Inputs

- `output/QUALITY_GATE.md` (must mention `subsection-writer` / `sections/*` issues)
- `sections/sections_manifest.jsonl` (paths + allowed citations + anchor facts)
- `outline/subsection_briefs.jsonl`
- `outline/chapter_briefs.jsonl`
- `outline/writer_context_packs.jsonl` (preferred: merged per-H3 drafting pack)
- `outline/evidence_drafts.jsonl`
- `outline/anchor_sheet.jsonl`
- `outline/evidence_bindings.jsonl`
- `citations/ref.bib`
- failing `sections/*.md`

## Outputs

- Updated `sections/S<sub_id>.md` (H3 body files)
- Updated `sections/S<sec_id>_lead.md` (H2 chapter lead blocks, when required)
- `output/WRITER_SELFLOOP_TODO.md` (optional; helper output)

## Loop contract

Repeat until this passes:

```bash
python .codex/skills/subsection-writer/scripts/run.py --workspace workspaces/<ws>
```

## Workflow

### 0) Parse the failure report

- Open `output/QUALITY_GATE.md`.
- Extract:
  - which files failed (e.g., `sections/S3.2.md`, `sections/S3_lead.md`)
  - which gate codes fired (e.g., `sections_h3_too_short`, `sections_cites_outside_mapping`)

If the report does not mention any `sections/*` paths, you are looping the wrong stage (switch to draft-level fixes).

### 1) For each failing H3 file: rewrite with anchors (not vibes)

For a failing `sections/S<sub_id>.md`:

1. Read the corresponding record in `sections/sections_manifest.jsonl`:
   - `allowed_bibkeys_selected` / `allowed_bibkeys_mapped`
   - `evidence_ids`
   - `anchor_facts`
2. Prefer `outline/writer_context_packs.jsonl` for this `sub_id` (single merged pack: rq/axes/paragraph_plan + comparisons + eval + limitations + anchors + allowed cites).
   - Treat `must_use` as a hard checklist (min anchors / comparisons / limitation hooks); if you cannot satisfy it without guessing, fix upstream evidence.
   - Use `pack_warnings` / `pack_stats` to detect when the pack is thin due to missing notes/fulltext (go back to C3/C4 instead of writing filler).
   - If missing, fall back to:
     - `outline/subsection_briefs.jsonl` (rq/axes/paragraph_plan)
     - `outline/evidence_drafts.jsonl` (comparisons/eval/limitations)
3. Rewrite/expand the section to satisfy the gates, while only using citation keys present in `citations/ref.bib`:
   - Body-only (no headings)
   - Depth target depends on `draft_profile` (all sans cites): `lite`>=6 paragraphs & >=~5000 chars; `survey`>=9 & >=~9000; `deep`>=10 & >=~11000.
   - Cite density depends on `draft_profile` (`lite`>=7, `survey`>=10, `deep`>=12 unique citations), all allowed by `outline/evidence_bindings.jsonl` for this `sub_id`
   - >=2 explicit contrasts (whereas/in contrast/相比/不同于)
   - >=1 evaluation anchor (benchmark/dataset/metric/protocol)
   - >=1 limitation/provisional sentence (limited/unclear/受限/待验证)
   - Paragraph-plan execution: follow `paragraph_plan[].argument_role` and ensure you can point to evaluation / synthesis / limitation / decision paragraphs (do not leave role labels).
   - >=1 cross-paper synthesis paragraph with >=2 citations in the same paragraph
   - If the evidence pack contains digits: include >=1 cited numeric anchor (digit + citation in same paragraph)

Hard rule: if you cannot satisfy the section without “free-citing” outside the binding set, stop and fix upstream (`mapping.tsv` → `evidence-binder` → `evidence-draft`).

### 2) For each failing H2 lead: write the chapter lead block

For a missing/weak `sections/S<sec_id>_lead.md`:

- Use `outline/chapter_briefs.jsonl` to keep the chapter throughline consistent.
- Body-only, 2–3 tight paragraphs.
- Must preview the chapter’s comparison axes and how its H3 subsections connect.
- Include >=2 citations (keys must exist in `citations/ref.bib`; keep it grounded and non-generic).


### 2b) For a failing H2 body file: rewrite the front matter (Introduction / Related Work)

Some H2 sections have **no H3 subsections** (common: Introduction + Related Work), so they are written as body-only files:
- `sections/S<sec_id>.md` (no headings; `section-merger` injects them under the H2 heading)

If `output/QUALITY_GATE.md` reports issues like `sections_intro_*` / `sections_related_work_*` for a `sections/S*.md` file:

1) Identify which H2 it is by reading `outline/outline.yml` (match by `id` or title).
2) Rewrite the file with paper-like front matter shape:
   - Motivation + scope boundary (what counts as an “agent” in this survey, what does not).
   - Evidence policy paragraph **once** (abstract vs fulltext coverage, reproducibility bias); do not repeat the same disclaimer in every H3.
   - Positioning (Related Work): integrate surveys + adjacent lines of work, but avoid a dedicated “Prior Surveys” mini-section by default.
   - Organization paragraph that previews the comparison axes (interface contract → planning/memory → adaptation/multi-agent → evaluation/risks).

Notes:
- H2 files are not subsection-scoped by `outline/evidence_bindings.jsonl`; citations must still exist in `citations/ref.bib`.
- Keep paper voice: avoid narration templates (“This subsection…”, “Next, we move…”); use content claims + why-it-matters + organization.

### 3) Recheck (always)

Rerun:

```bash
python .codex/skills/subsection-writer/scripts/run.py --workspace workspaces/<ws>
```

If it still fails, only touch the remaining failing files and repeat.

## Troubleshooting (by gate code)

- `sections_missing_files`: create the missing `sections/*.md` first (don’t merge yet).
- `sections_h2_no_citations`: add citations (or remove factual claims and keep it purely structural).
- `sections_intro_sparse_citations` / `sections_intro_too_short` / `sections_intro_too_few_paragraphs`: expand the Introduction H2 body file (`sections/S<sec_id>.md`) with scope + positioning + organization, keeping claims citation-grounded.
- `sections_related_work_sparse_citations` / `sections_related_work_too_short` / `sections_related_work_too_few_paragraphs`: expand the Related Work H2 body file (`sections/S<sec_id>.md`) with survey coverage + adjacent lines of work, keeping claims citation-grounded.
- `sections_h3_too_short` / `sections_h3_too_few_paragraphs`: add concrete comparisons + eval protocol details + synthesis + limitation (don’t add fluff).
- `sections_h3_missing_cited_numeric`: pick an anchor fact with digits from `outline/anchor_sheet.jsonl` and integrate it with citations.
- `sections_h3_weak_anchor_density`: ensure multiple paragraphs are both cited and anchored (digit OR evaluation token OR limitation token), not just long descriptions.
- `sections_h3_missing_thesis_statement`: rewrite paragraph 1 so it ends with a conclusion-first takeaway aligned to briefs `thesis` (avoid “This subsection …” meta narration).
- `sections_h3_low_connector_density`: add explicit logical connectors (contrast/causal/extension/implication) and rerun `section-logic-polisher` until PASS.
- `sections_h3_citation_dump_paragraphs`: rewrite paragraphs that end with `[@a; @b; @c]` as the only citations; embed citations inside the sentences they support.
- `sections_citation_dump_line`: remove stand-alone citation-only lines; merge the citation into the claim sentence.
- `sections_cites_outside_mapping`: you used citation keys outside the binding set → fix mapping/bindings or rewrite to stay in-scope.
- `sections_h3_missing_contrast` / `sections_h3_missing_eval_anchor` / `sections_h3_missing_limitation`: add the missing micro-structure signals explicitly.

Non-gated but high-impact polish (paper voice):
- Remove outline narration (`This subsection ...`, `In this subsection, we ...`) and slide navigation (`We now turn to ...`); rewrite into content claims + argument bridges.
- Keep evidence-policy limitations once in front matter; delete repeated “abstract-only/title-only” boilerplate inside H3 unless truly subsection-specific.
- Avoid repeating literal opener labels across many H3s (e.g., `Key takeaway:`); vary opener phrasing and cadence.
- Keep tone calm and academic; delete hype words and “PPT speaker notes”.

## Script (optional)

### Quick Start

- `python .codex/skills/writer-selfloop/scripts/run.py --help`
- `python .codex/skills/writer-selfloop/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Generate an actionable TODO list from an existing quality report:
  - `python .codex/skills/writer-selfloop/scripts/run.py --workspace workspaces/<ws>`

Notes:
- The script is a deterministic helper: it does not rewrite prose; it only writes `output/WRITER_SELFLOOP_TODO.md`.
