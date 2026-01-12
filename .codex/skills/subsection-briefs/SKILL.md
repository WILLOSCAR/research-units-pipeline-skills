---
name: subsection-briefs
description: |
  Build per-subsection writing briefs (NO PROSE) so later drafting is driven by evidence and checkable comparison axes (not outline placeholders).
  **Trigger**: subsection briefs, writing cards, intent cards, H3 briefs, scope_rule, axes, clusters, 写作意图卡, 小节卡片, 段落计划.
  **Use when**: `outline/outline.yml` + `outline/mapping.tsv` + `papers/paper_notes.jsonl` exist and you want section-by-section drafting without template leakage.
  **Skip if**: `outline/subsection_briefs.jsonl` already exists and is refined (no placeholders/ellipsis; axes+clusters+paragraph_plan are filled).
  **Network**: none.
  **Guardrail**: NO PROSE; do not invent papers; only reference `paper_id`/`bibkey` that exist in `papers/paper_notes.jsonl`.
---

# Subsection Briefs (NO PROSE)

Purpose: convert each H3 subsection into a **writeable intent card** that the writer can execute without copying scaffold bullets.

This is the bridge between:
- Stage A (verifiable outline: Intent/RQ/Evidence needs/Expected cites)
- Stage C (section-by-section drafting)

## Non-negotiables

- NO PROSE: output is structured briefs only (no narrative paragraphs).
- No placeholders: do not emit `…`, `TODO`, `TBD`, `(placeholder)`, or instruction-like fragments.
- Evidence-aware: if evidence is abstract-only/title-only, the brief must encode a conservative writing strategy (provisional language / questions-to-answer).
- Scope hygiene: each brief must state include/exclude rules to prevent scope drift.

## Inputs

- `outline/outline.yml`
- `outline/mapping.tsv`
- `papers/paper_notes.jsonl`
- Optional: `outline/claim_evidence_matrix.md`
- Optional: `GOAL.md`

## Outputs

- `outline/subsection_briefs.jsonl`

## Output format (`outline/subsection_briefs.jsonl`)

JSONL (one JSON object per line). Required fields per record:

- `sub_id` (e.g., `"3.2"`)
- `title`
- `section_id`, `section_title`
- `scope_rule` (object with `include`/`exclude`/`notes`)
- `rq` (1–2 sentences)
- `axes` (list of 3–5 checkable comparison dimensions; no ellipsis)
- `clusters` (2–3 clusters; each has `label`, `rationale`, `paper_ids`, and optional `bibkeys`)
- `paragraph_plan` (6–10 paragraphs; each paragraph is a *unit of comparison* with explicit clusters/evidence needs)
- `evidence_level_summary` (counts by `fulltext|abstract|title`)

## Workflow

Optional context (if present): read `GOAL.md` to pin scope and audience, and use `outline/claim_evidence_matrix.md` as an additional evidence index (do not copy placeholders).

1. Read `outline/outline.yml` and extract each subsection’s Stage-A fields (Intent/RQ/Evidence needs/Expected cites/Comparison axes).
2. Read `outline/mapping.tsv` and collect mapped `paper_id`s for each `sub_id`.
3. Read `papers/paper_notes.jsonl` and build per-paper mini-meta: `bibkey`, `year`, `evidence_level`, key bullets/limitations.
4. Write a **scope_rule** per subsection:
   - What is in-scope for this subsection?
   - What is out-of-scope?
   - If cross-scope citations are allowed, what is the justification policy?
5. Propose 3–5 **axes**:
   - Prefer concrete, checkable phrases (e.g., representation, training signal, sampling/solver, compute, evaluation protocol, failure modes).
   - Use the subsection title + mapped-paper tags to specialize axes.
6. Build 2–3 **clusters** of papers (2–5 papers each) and explain why they cluster (which axis/theme).
7. Build a 6–10 paragraph **paragraph_plan** (plan paragraphs, not prose):
   - Para 1: setup + scope boundary + thesis/definitions.
   - Para 2: approach family / cluster A (mechanism + assumptions).
   - Para 3: cluster A evaluation/trade-offs (benchmarks/metrics/latency/compute).
   - Para 4: approach family / cluster B (contrast with A).
   - Para 5: cluster B evaluation/trade-offs (mirror A for comparability).
   - Para 6: cross-paper synthesis (explicit compare A vs B; later prose should include >=2 citations in one paragraph).
   - Para 7: failures/limitations + verification targets + open question (especially under abstract-only evidence).
   - Para 8–10 (optional): design implication / deployment nuance / bridge terms.
8. Write `outline/subsection_briefs.jsonl`.

## Quality checklist

- [ ] Every subsection has `rq` and `scope_rule`.
- [ ] `axes` length is 3–5 and each axis is a concrete noun phrase.
- [ ] `clusters` length is 2–3; each cluster has 2–5 papers.
- [ ] `paragraph_plan` length is 6–10; each plan references clusters (not generic filler).
- [ ] No placeholder markers appear anywhere.

## Helper script (bootstrap)

This skill includes a deterministic bootstrap script that scaffolds briefs from existing artifacts. Treat it as a starting point and refine as needed.

- Clustering note: the script groups papers using lightweight title keyword tags (e.g., agents/tool-use/planning/memory/multi-agent/security) and falls back to recency splits when tags are sparse.

### Quick Start

- `python .codex/skills/subsection-briefs/scripts/run.py --help`
- `python .codex/skills/subsection-briefs/scripts/run.py --workspace <workspace_dir>`

### All Options

- See `--help`.

### Examples

- Use default inputs/outputs:
  - `python .codex/skills/subsection-briefs/scripts/run.py --workspace workspaces/<ws>`
- Explicit IO (for custom pipelines):
  - `python .codex/skills/subsection-briefs/scripts/run.py --workspace workspaces/<ws> --inputs "outline/outline.yml;outline/mapping.tsv;papers/paper_notes.jsonl" --outputs "outline/subsection_briefs.jsonl"`

## Troubleshooting

### Issue: briefs look generic or repeat across subsections

**Symptom**: many briefs share the same axes/clusters.

**Causes**:
- Mapping coverage is weak (too few papers per subsection).
- Paper notes are title-only / missing abstracts.

**Solutions**:
- Fix upstream: expand retrieval + increase `core_size` in `queries.md`; rerun `literature-engineer` + `dedupe-rank`.
- Enrich evidence: set `evidence_mode: "fulltext"` and provide PDFs under `papers/pdfs/` (or enable network for `pdf-text-extractor`).

### Issue: scope drift (e.g., T2I vs T2V) reappears

**Symptom**: clusters include out-of-scope papers.

**Solutions**:
- Tighten `scope_rule` to explicitly allow only “bridge” citations and require justification.
- Fix retrieval filters / exclusions upstream and rerun mapping.
