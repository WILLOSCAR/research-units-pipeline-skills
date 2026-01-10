---
name: prose-writer
description: |
  Write `output/DRAFT.md` (or `output/SNAPSHOT.md`) from an approved outline and evidence packs, using only verified citation keys from `citations/ref.bib`.
  **Trigger**: write draft, prose writer, snapshot, survey writing, 写综述, 生成草稿, section-by-section drafting.
  **Use when**: structure is approved (`DECISIONS.md` has `Approve C2`) and evidence packs exist (`outline/subsection_briefs.jsonl`, `outline/evidence_drafts.jsonl`).
  **Skip if**: approvals are missing, or evidence packs are incomplete / scaffolded (missing-fields, TODO markers).
  **Network**: none.
  **Guardrail**: do not invent facts or citations; only cite keys present in `citations/ref.bib`; avoid pipeline-jargon leakage in final prose.
---

# Prose Writer (Evidence-first)

Goal: produce a survey draft that reads like a real paper because it is driven by **evidence packs**, not by outline placeholders.

This skill should behave like a synthesis engine:
- inputs = subsection briefs + evidence drafts
- output = paragraph-level claim → evidence → synthesis (with citations)

## Non-negotiables

- **No prose without approval**: for surveys, require `Approve C2` in `DECISIONS.md`.
- **No invented citations**: only use keys present in `citations/ref.bib`.
- **No placeholder leakage**: if any upstream artifact still contains scaffold markers/ellipsis/TODO, do not write; block and request evidence fixes.
- **No pipeline voice**: do not leak internal scaffolding terms like “working claim”, “enumerate 2-4”, “scope/design space/evaluation practice”.

## Inputs

- `outline/outline.yml`
- `outline/subsection_briefs.jsonl`
- `outline/transitions.md`
- `outline/evidence_drafts.jsonl`
- Optional: `outline/tables.md`, `outline/timeline.md`, `outline/figures.md`
- Optional: `outline/claim_evidence_matrix.md`
- `citations/ref.bib`
- `DECISIONS.md`

## Outputs

- `output/DRAFT.md` and/or `output/SNAPSHOT.md`

## Decision: snapshot vs draft

- Snapshot: bullets-first, ~1 page; summarize what evidence exists + what is missing.
- Draft: section-by-section prose that follows each subsection’s `paragraph_plan` and uses paragraph-level citations.

## Workflow (v2: briefs + evidence packs)

Before writing, load the structural and coherence inputs: `outline/outline.yml` (section order) and `outline/transitions.md` (transition map). Optionally consult `outline/claim_evidence_matrix.md` as an evidence index.

1. **Gate check (HITL)**
   - Read `DECISIONS.md`.
   - If `Approve C2` is not ticked, write a short request block (what you plan to write + which evidence packs you will rely on), then stop.

2. **Input integrity check (fail fast)**
   - Read `outline/subsection_briefs.jsonl` and confirm:
     - each H3 has a brief,
     - `scope_rule/rq/axes/clusters/paragraph_plan` are filled,
     - no placeholders/ellipsis.
   - Read `outline/evidence_drafts.jsonl` and confirm:
     - each H3 has >=3 concrete comparisons,
     - `blocking_missing` is empty (or explicitly acknowledged and you switch to snapshot mode).

3. **Write per-subsection mini-essays (do NOT draft whole paper in one blob)**
   - For each subsection (`H3`):
     - read its brief (`rq`, `axes`, `clusters`, `paragraph_plan`, evidence-level policy)
     - read its evidence pack (`claim_candidates`, `concrete_comparisons`, `evaluation_protocol`, `failures_limitations`)
     - write 2–3 paragraphs following `paragraph_plan`:
       - Paragraph structure: Claim → Evidence → Synthesis.
       - Each paragraph must include citations that match the claims.
     - The subsection must have a **unique thesis** (would be false in other subsections).

4. **Weave transitions (coherence)**
   - Between adjacent subsections/sections, add 1–2 transition sentences that reflect the taxonomy logic (not generic “Moreover/However”).
   - Keep the scope boundary consistent with `scope_rule` (avoid silent drift like T2I→T2V).

5. **One-pass rewrite (de-template)**
   - Remove repeated phrasing across subsections.
   - Replace generic claims (“trade-offs depend on benchmarks”) with concrete comparisons from evidence packs.
   - If evidence is abstract-only, downgrade to “hypothesis + verification needed” rather than confident conclusions.

6. **Integrate cross-cutting artifacts**
   - Insert `outline/tables.md` (>=2 tables), `outline/timeline.md` (>=8 cited milestones), and `outline/figures.md` (>=2 specs) into the draft.

## Quality checklist

- [ ] No `…`, `TODO`, `(placeholder)`, or `<!-- SCAFFOLD -->` remains in `output/DRAFT.md`.
- [ ] Every subsection has citations and at least one paragraph with >=2 citations (cross-paper synthesis).
- [ ] No undefined citation keys (all keys exist in `citations/ref.bib`).
- [ ] Scope is consistent with `GOAL.md` and `scope_rule`.

## Helper script (bootstrap)

The helper script is a **gate wrapper**: it blocks until approvals + prerequisites are satisfied and a real `output/DRAFT.md` exists (no scaffold markers). Writing itself is LLM-driven.

### Quick Start

- `python .codex/skills/prose-writer/scripts/run.py --help`
- `python .codex/skills/prose-writer/scripts/run.py --workspace <workspace_dir>`

### All Options

- See `--help`.

### Examples

- Run the gate wrapper after approval (it will block until `output/DRAFT.md` is written):
  - Tick `Approve C2` in `DECISIONS.md` then run:
  - `python .codex/skills/prose-writer/scripts/run.py --workspace workspaces/<ws>`

## Troubleshooting

### Issue: writer outputs ellipsis / scaffold text

**Symptom**: `output/DRAFT.md` contains `…`, `enumerate 2-4 ...`, or repeats the same paragraph template.

**Causes**:
- `outline/subsection_briefs.jsonl` is missing or generic.
- `outline/evidence_drafts.jsonl` has `blocking_missing` or scaffold markers.

**Solutions**:
- Fix upstream: regenerate briefs/evidence packs, enrich abstracts/fulltext, and block writing until evidence is concrete.

### Issue: scope drift (e.g., T2I vs T2V)

**Symptom**: subsections cite many out-of-scope papers without justification.

**Solutions**:
- Tighten `scope_rule` in subsection briefs and rerun evidence packs.
- Tighten `queries.md` excludes and rerun retrieval/dedupe/mapping.
