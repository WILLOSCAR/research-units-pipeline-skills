---
name: evidence-draft
description: |
  Create per-subsection evidence packs (NO PROSE): claim candidates, concrete comparisons, evaluation protocol, limitations, plus citation-backed evidence snippets with provenance.
  **Trigger**: evidence draft, evidence pack, claim candidates, concrete comparisons, evidence snippets, provenance, 证据草稿, 证据包, 可引用事实.
  **Use when**: `outline/subsection_briefs.jsonl` exists and you want evidence-first section drafting where every paragraph can be backed by traceable citations/snippets.
  **Skip if**: `outline/evidence_drafts.jsonl` already exists and is refined (no placeholders; >=4 comparisons per subsection; `blocking_missing` empty).
  **Network**: none (richer evidence improves with abstracts/fulltext).
  **Guardrail**: NO PROSE; do not invent facts; only use citation keys that exist in `citations/ref.bib`.
---

# Evidence Draft (NO PROSE)

Purpose: turn `papers/paper_notes.jsonl` + subsection mapping into **writeable evidence packs** so the writer never has to guess (and never copies outline placeholders).

Key design: every pack should contain **evidence snippets** (1–2 sentences) with **provenance** (abstract/fulltext/notes pointer). Even abstract-level snippets are better than template prose.

Why this matters for writing quality:
- Packs are the writer substrate; if packs are thin, C5 will either pad prose or guess.
- Treat `blocking_missing` as a stop signal: route upstream (notes/bindings) instead of writing around gaps.

## Role cards (prompt-level guidance)

- **Evidence Curator**
  - Mission: turn paper notes into contrastable, citeable evidence (not summaries).
  - Do: extract snippet-backed comparisons; surface protocol details and failure modes.
  - Avoid: axis-driven "hypotheses" that are not supported by snippets.

- **Provenance Accountant**
  - Mission: keep every snippet auditable.
  - Do: attach provenance pointers (abstract/fulltext/notes location) and keep excerpts sentence-level.
  - Avoid: untraceable paraphrases that cannot be verified.

- **Skeptic**
  - Mission: prevent evidence inflation.
  - Do: downgrade claims when evidence is abstract/title-only; convert unknowns into `verify_fields` (not repeated boilerplate in prose).
  - Avoid: strong conclusions without protocol/metric context.


## Non-negotiables

- NO PROSE: packs are bullets-only evidence, not narrative paragraphs.
- No fabrication: do not invent datasets/metrics/numbers.
- Citation hygiene: every cite key must exist in `citations/ref.bib`.
- Claim candidates must be snippet-derived (no axis-driven “Hypothesis: …” items); put questions into `verify_fields` instead.
- Avoid silent truncation: keep `claim_candidates[].claim` long enough to carry concrete detail (<= ~400 chars) and keep highlight `excerpt` sentence-level (<= ~280 chars).
- Numeric-claim hygiene (evidence substrate):
  - If a snippet/claim includes digits or `%`, also include minimal context in the same bullet (at least 2 of: task/setting, metric definition, constraint/budget/tool access).
  - If the context is not present in notes/fulltext, do not keep the number; downgrade to qualitative wording and add a `verify_fields` item instead.
- Evidence-aware language:
  - fulltext-backed → can summarize comparisons
  - abstract-only/title-only → must be provisional + list verify-fields (no strong “dominant trade-offs” language)

## Inputs

Required:
- `outline/subsection_briefs.jsonl`
- `papers/paper_notes.jsonl`
- `citations/ref.bib`

Optional (recommended for addressable evidence):
- `papers/evidence_bank.jsonl`
- `outline/evidence_bindings.jsonl`

## Outputs

- `outline/evidence_drafts.jsonl`

Optional (human-readable):
- `outline/evidence_drafts/` (folder of per-subsection Markdown packs)

## Output format (`outline/evidence_drafts.jsonl`)

JSONL (one JSON object per line). Required fields per record:

- `sub_id`, `title`
- `evidence_ids` (list[str]; if `outline/evidence_bindings.jsonl` exists, this should match the binding for the subsection)
- `evidence_level_summary` (counts: `fulltext|abstract|title`)
- `evidence_snippets` (list; each has `text`, `paper_id`, `citations`, `provenance`)
- `definitions_setup` (list of cited bullets)
- `claim_candidates` (3–5 items; each has `claim`, `citations`, `evidence_field`)
- `concrete_comparisons` (>=4 items; each has `axis`, `A_papers`, `B_papers`, `citations`, `evidence_field`; may also include `A_highlights`/`B_highlights` with snippet-backed contrast anchors)
- `evaluation_protocol` (list of concrete protocol bullets + citations)
- `failures_limitations` (2–4 cited bullets)
- `blocking_missing` (list[str]; if non-empty, drafting must stop)
- `verify_fields` (list[str]; non-blocking: fields to verify before making strong claims)

### Provenance schema (per snippet)

Example:

```json
{"source":"abstract","pointer":"papers/paper_notes.jsonl:paper_id=P0012#abstract","evidence_level":"abstract"}
```

Allowed `source`: `fulltext|abstract|paper_notes|title`.

## Workflow

1. Load `outline/subsection_briefs.jsonl` and read each subsection’s `rq`, `axes`, `clusters`, and evidence-level policy.
2. Load `papers/paper_notes.jsonl` and build a per-paper evidence index (`bibkey`, `evidence_level`, `abstract`, `fulltext_path`, `limitations`).
3. For each subsection:
   - Build **evidence_snippets** from mapped papers (prefer fulltext, else abstract), and record provenance.
   - Definitions/setup: 1–2 bullets that define setup + scope boundary (with citations).
   - Claim candidates: 3–5 **checkable** candidates (prefer snippet-derived; tag with `evidence_field`).
   - Concrete comparisons: >=4 A-vs-B comparisons (cluster-vs-cluster) along explicit axes.
   - Evaluation protocol: list concrete benchmark/metric tokens if extractable; otherwise treat as a blocking gap.
   - Failures/limitations: 2–4 concrete limitations/failure modes with citations.
   - Set `blocking_missing` for hard blockers (e.g., no usable citations; title-only evidence; no eval tokens for an eval-heavy subsection).
4. Write `outline/evidence_drafts.jsonl` and per-subsection Markdown copies.

## Quality checklist

- [ ] Every subsection has >=4 concrete comparisons.
- [ ] `evidence_snippets` is non-empty and includes provenance.
- [ ] Any bullet containing numbers/% also carries minimal protocol context (task/metric/constraint), or the number is removed and moved to `verify_fields`.
- [ ] `claim_candidates` has >=3 snippet-derived items (no axis-driven hypotheses).
- [ ] `blocking_missing` is empty.
- [ ] No `TODO` / `(placeholder)` / `<!-- SCAFFOLD -->` / unicode ellipsis (`…`) remains.

## Script

### Refinement marker (recommended; prevents churn)

When you are satisfied with evidence packs (and `blocking_missing` is empty), create:
- `outline/evidence_drafts.refined.ok`

This is an explicit "I reviewed/refined this" signal:
- prevents scripts from regenerating and undoing your work
- (in strict runs) can be used as a completion signal before writing

### Quick Start

- `python .codex/skills/evidence-draft/scripts/run.py --help`
- `python .codex/skills/evidence-draft/scripts/run.py --workspace <ws>`

### All Options

- See `--help`.
- Inputs (required): `outline/subsection_briefs.jsonl`, `papers/paper_notes.jsonl`, `citations/ref.bib`.
- Inputs (optional): `papers/evidence_bank.jsonl`, `outline/evidence_bindings.jsonl`.

### Examples

- Generate evidence packs after citations:
  - Ensure `citations/ref.bib` exists.
  - Ensure `outline/subsection_briefs.jsonl` exists (axes/clusters/plan filled).
  - Ensure `papers/paper_notes.jsonl` has usable evidence (abstract/fulltext/limitations).
  - Run: `python .codex/skills/evidence-draft/scripts/run.py --workspace workspaces/<ws>`

## Troubleshooting

### Issue: evidence packs have `blocking_missing` entries

**Fix**:
- Treat `blocking_missing` as a stop signal: enrich `papers/paper_notes.jsonl` / `papers/evidence_bank.jsonl` (or adjust scope) before drafting prose.

### Issue: evidence snippets are empty or untraceable

**Fix**:
- Ensure each snippet includes provenance (paper id + location) and that `outline/evidence_bindings.jsonl` is non-empty for the subsection.
