---
name: subsection-writer
description: |
  Write section/subsection prose into per-unit files under `sections/`, so each unit can be QA’d independently before merging into `output/DRAFT.md`.
  **Trigger**: subsection writer, per-section writing, split sections, sections/, 分小节写, 按章节拆分写作.
  **Use when**: `Approve C2` is recorded and evidence packs exist; you want evidence-first drafting without a monolithic one-shot draft.
  **Skip if**: `DECISIONS.md` approval is missing, or `outline/evidence_drafts.jsonl` is incomplete/scaffolded.
  **Network**: none.
  **Guardrail**: do not invent facts/citations; no ellipsis/TODO/placeholder leakage; keep citations subsection- or chapter-scoped (prefer subsection); H3 body files must not contain headings.
---

# Subsection Writer (Per-section drafting)

Goal: produce survey-quality prose in **small, independently verifiable units** under `sections/`, so we can catch:
- placeholder leakage (`…`/`TODO`)
- template boilerplate
- citation drift across subsections
- “content-poor” prose that ignores evidence packs

This skill is LLM-first. The helper script only writes `sections/sections_manifest.jsonl` and runs quality gates.

## Decision Tree (what to write)

```
Need better overall flow?  → write chapter leads (H2)
Need deeper subsection content? → use writer context packs (H3)
Missing concrete numbers/benchmarks? → go upstream (evidence-draft / paper-notes)
```

## Inputs

- `DECISIONS.md` (must include `Approve C2` before writing)
- `outline/outline.yml` (ordering + subsection ids)
- `outline/chapter_briefs.jsonl` (H2 chapter lead plans)
- `outline/subsection_briefs.jsonl` (rq/axes/clusters/paragraph_plan)
- `outline/evidence_drafts.jsonl` (evidence packs: snippets + comparisons + eval + limitations)
- `outline/anchor_sheet.jsonl` (selected anchor facts to prevent generic prose)
- `outline/writer_context_packs.jsonl` (preferred: merged per-H3 drafting pack)
- `outline/evidence_bindings.jsonl` (allowed citation scope per H3)
- `citations/ref.bib` (valid citation keys)

## Outputs

Required:
- `sections/sections_manifest.jsonl` (includes per-H3 `allowed_bibkeys_*` + `anchor_facts` to prevent citation drift and generic prose)
- `sections/`

Required global sections:
- `sections/abstract.md`
- `sections/discussion.md`
- `sections/conclusion.md`

Required chapter-lead blocks (one per H2 chapter that has H3 subsections):
- `sections/S<sec_id>_lead.md`

Required H3 body files (one per H3 subsection):
- `sections/S<sub_id>.md`

## Workflow (planner → writer → skeptic)

### 0) Gate check (policy)

Confirm `DECISIONS.md` has `Approve C2` (scope+outline). If not, stop and request approval.

### 1) Planner pass (don’t write yet)

- Use `outline/outline.yml` to enumerate H2/H3 units and determine write order.

For each H2 chapter **with H3 subsections**:
- read `outline/chapter_briefs.jsonl`
- extract `throughline` + `key_contrasts`

For each H3 subsection:
- Prefer the matching record in `outline/writer_context_packs.jsonl` (rq/axes/paragraph_plan + comparison cards + eval + limitations + anchors + allowed cites).
- If missing, fall back to:
  - `outline/subsection_briefs.jsonl` (rq/axes/clusters/paragraph_plan)
  - `outline/evidence_drafts.jsonl` (comparisons, eval, limitations)
  - `outline/anchor_sheet.jsonl` (numeric/eval/limitation anchors)
- When drafting, pick:
  - >=1 quantitative anchor (digits) if available
  - >=1 evaluation anchor (benchmark/dataset/metric)
  - >=1 limitation/failure hook

If you cannot find anchors without guessing, stop and fix upstream evidence.

### 2) Write chapter leads (H2 coherence)

For each H2 chapter with H3 subsections, create `sections/S<sec_id>_lead.md`:
- Body-only: MUST NOT contain headings (`#`, `##`, `###`).
- 2–3 paragraphs (tight, high-signal).
- Must preview the chapter’s comparison axes and how the H3s connect.
- Must include >=2 citations (prefer surveys/benchmarks already in `ref.bib`).
- No new facts: don’t introduce new claims that are not later supported in H3.

### 2b) Write front matter H2 sections (Introduction + Related Work)

These are H2 sections without H3 subsections, so write body-only files (no headings; they are injected under the H2 title by `section-merger`):
- `sections/S1.md` (Introduction)
- `sections/S2.md` (Related Work)

Requirements (strict mode; thresholds depend on `queries.md:draft_profile`):
- Depth: >=6 substantive paragraphs (paragraphs with >=~200 chars after removing citations; avoid bullet-only structure).
- Cite density (unique cites; min depends on `draft_profile`): `lite` Intro>=8 / Related>=10; `survey` Intro>=12 / Related>=15; `deep` Intro>=18 / Related>=22 (mix foundations + representative systems + eval/benchmark/security).
- Paper-like structure: motivation → scope/definitions → why the taxonomy/axes → contributions → organization paragraph.

Related Work policy:
- Avoid a dedicated “Prior Surveys” mini-section; integrate survey citations as part of positioning vs adjacent lines of work.

Optional style reference:
- Skim `ref/agent-surveys/text/` to imitate typical front-matter structure and citation density.

### 2c) Write Discussion (global)

Write `sections/discussion.md` (MUST include a `## Discussion` heading).

Targets:
- 3–6 paragraphs that synthesize cross-cutting themes across chapters (not per-paper summaries).
- Each paragraph should cite multiple works when making factual claims (prefer >=2 citations in synthesis paragraphs).
- Include limitations/assumptions explicitly (benchmark dependence, abstract-only evidence, reproducibility gaps).
- End with concrete, actionable future directions (avoid generic template bullets).

### 3) Write H3 body files (depth + evidence)

For each H3 file `sections/S<sub_id>.md`:
- Body-only: MUST NOT contain headings.
- Evidence-first: cite density depends on `draft_profile` (`lite`>=7, `survey`>=10, `deep`>=12 unique citations), all present in `citations/ref.bib`.
- Citation scope: citations must be allowed by `outline/evidence_bindings.jsonl` for that `sub_id` (or, if needed, within the same H2 chapter’s mapped union); keep >=2 subsection-specific citations.
- Depth target (depends on `draft_profile`; all sans cites): `lite`>=6 paragraphs & >=~5000 chars; `survey`>=9 & >=~9000; `deep`>=10 & >=~11000.
- Must include:
  - >=2 explicit contrasts (whereas / in contrast / 相比 / 不同于)
  - >=1 evaluation anchor (benchmark/dataset/metric/protocol)
  - >=1 limitation/provisional sentence (limited/unclear/受限/待验证)
  - >=1 cross-paper synthesis paragraph with >=2 citations in the same paragraph
  - if evidence packs contain quantitative snippets: >=1 **cited numeric anchor** (digit + citation in same paragraph)

### 4) Skeptic pass (delete generic sentences)

Delete or rewrite any sentence that is:
- copy-pastable into other subsections
- missing concrete nouns (benchmarks/datasets/tools/numbers)
- not grounded by citations when it contains a factual claim
- meta/process language that should not appear in a paper (e.g., “drafting policy”, “template-y”, “pipeline”, “quality gate”)

## Common failure modes (and fixes)

- **Generic prose despite long paragraphs** → you skipped `outline/anchor_sheet.jsonl`; rewrite with >=1 cited numeric anchor + >=2 concrete comparisons.
- **Citations missing in bib** → go upstream: ensure classics/surveys are in `papers/core_set.csv` and regenerate `citations/ref.bib`.
- **Citations outside binding set** → rewrite to stay within subsection/ chapter mapping; if still impossible, fix `outline/mapping.tsv` then rerun `evidence-binder` (avoid cross-chapter “free cite”).
- **Quality gate fails after partial writing** → use `writer-selfloop` to rewrite only failing `sections/*.md` based on `output/QUALITY_GATE.md` (don’t rewrite the whole draft).

## Script

### Quick Start

- `python .codex/skills/subsection-writer/scripts/run.py --help`
- `python .codex/skills/subsection-writer/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`
- `--unit-id <U###>`
- `--inputs <semicolon-separated>`
- `--outputs <semicolon-separated>`
- `--checkpoint <C#>`

### Examples

- Run after writing `sections/*.md`:
  - `python .codex/skills/subsection-writer/scripts/run.py --workspace workspaces/<ws>`

Notes:
- The script does not write prose; it writes `sections/sections_manifest.jsonl` and runs strict quality gates.
