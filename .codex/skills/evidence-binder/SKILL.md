---
name: evidence-binder
description: |
  Bind addressable evidence IDs from `papers/evidence_bank.jsonl` to each subsection (H3), producing `outline/evidence_bindings.jsonl`.
  **Trigger**: evidence binder, evidence plan, section->evidence mapping, 证据绑定, evidence_id.
  **Use when**: `papers/evidence_bank.jsonl` exists and you want writer/auditor to use section-scoped evidence items (WebWeaver-style memory bank).
  **Skip if**: you are not doing evidence-first section-by-section writing.
  **Network**: none.
  **Guardrail**: NO PROSE; do not invent evidence; only select from the existing evidence bank.
---

# Evidence Binder (NO PROSE)

Goal: convert a paper-level pool into a **subsection-addressable evidence plan**.

This skill is the bridge from “Evidence Bank” → “Writer”: the writer should only use evidence IDs bound to the current subsection.

Why this matters for writing quality:
- Weak/undifferentiated bindings force the writer to either pad prose or cite out-of-scope.
- Treat `binding_gaps` as a routing signal: fix upstream evidence/mapping instead of "writing around" missing evidence.

## Inputs

- `outline/subsection_briefs.jsonl`
- `outline/mapping.tsv`
- `papers/evidence_bank.jsonl`
- Optional:
  - `citations/ref.bib` (to validate cite keys when evidence items carry citations)

## Outputs

- `outline/evidence_bindings.jsonl` (1 JSONL record per subsection)
- `outline/evidence_binding_report.md` (summary; bullets + small tables)
  - Includes `gaps` (missing required evidence fields) and `tag mix` (selected evidence tags) so subsection-specific evidence needs are visible.

## Output format (`outline/evidence_bindings.jsonl`)

JSONL (one object per H3 subsection). Best-effort fields (keep deterministic):

- `sub_id`, `title`
- `paper_ids` (papers in-scope for this subsection, from `mapping.tsv`)
- `mapped_bibkeys` (bibkeys mapped to this subsection)
- `bibkeys` (a selected subset to encourage subsection-first citations)
- `evidence_ids` (selected evidence items from `papers/evidence_bank.jsonl`)
- `evidence_counts` (small summary by claim_type / tag / evidence_level)
- `binding_rationale` (short bullets; why the selected evidence covers this subsection’s axes / desired tags)
- `binding_gaps` (list[str]; required evidence fields not covered by selected evidence; drives the evidence self-loop upstream)

## Binding policy (how strict to be)

- Subsection-first by default: the writer should primarily cite `bibkeys` and use `evidence_ids` bound to this `sub_id`.
- Allow limited within-chapter reuse: citations from sibling H3s within the same H2 chapter may be reused for background/evaluation framing, but:
  - keep >=2 subsection-specific citations per H3 (avoid “free cite drift”)
  - avoid cross-chapter reuse unless the outline explicitly calls for it

## Workflow (NO PROSE)

1. Read `outline/subsection_briefs.jsonl` to understand each H3’s scope/rq/axes.
2. Read `outline/mapping.tsv` to know which papers belong to each subsection.
3. Read `papers/evidence_bank.jsonl` and select a subsection-scoped set of `evidence_id` items per H3.
4. If `citations/ref.bib` exists, sanity-check that any cite keys referenced by selected evidence items are defined.
5. Write `outline/evidence_bindings.jsonl` and `outline/evidence_binding_report.md`.

## Freeze policy

- If `outline/evidence_bindings.refined.ok` exists, the script will not overwrite `outline/evidence_bindings.jsonl`.
- Treat this marker as an explicit refinement/completion signal (especially in strict runs): only create it after you have checked `binding_gaps` and `tag mix` look subsection-specific.

## Heterogeneity sanity check (avoid recipe-like bindings)

A common hidden failure mode is *mechanical uniformity*: every H3 ends up with the same `claim_type`/`tag mix`, which hides what each subsection is actually missing and pushes the writer toward generic prose.

Before you mark bindings as refined:
- Scan `outline/evidence_binding_report.md`: different H3 should show meaningfully different `tag mix` / `claim_type` balance.
- If most H3 look identical, treat it as a binder smell: tighten `required_evidence_fields`, adjust selection rationale, or enrich the evidence bank, then rerun.

## Script

### Quick Start

- `python .codex/skills/evidence-binder/scripts/run.py --help`
- `python .codex/skills/evidence-binder/scripts/run.py --workspace workspaces/<ws>`

### All Options

- `--workspace <dir>`: workspace root
- `--unit-id <U###>`: unit id (optional; for logs)
- `--inputs <semicolon-separated>`: override inputs (rare; prefer defaults)
- `--outputs <semicolon-separated>`: override outputs (rare; prefer defaults)
- `--checkpoint <C#>`: checkpoint id (optional; for logs)

### Examples

- Bind evidence IDs after building the evidence bank:
  - Ensure `papers/evidence_bank.jsonl` exists.
  - Run: `python .codex/skills/evidence-binder/scripts/run.py --workspace workspaces/<ws>`

## Troubleshooting

### Issue: some subsections have too few evidence IDs

**Fix**:
- Strengthen `papers/evidence_bank.jsonl` via `paper-notes` (more extractable evidence items).
- Or broaden the mapped paper set for the subsection via `section-mapper`, then rerun binder.

### Issue: `binding_gaps` is non-empty (missing evidence types)

**What it means**:
- The subsection brief requires certain evidence fields (e.g., benchmarks/metrics/security/tooling), but the bound evidence items do not cover them.

**Fix (self-loop upstream)**:
- Prefer enriching `papers/evidence_bank.jsonl` / `papers/paper_notes.jsonl` for mapped papers (extract benchmark/metric/failure-mode details).
- If the mapping is weak for that evidence type, expand `outline/mapping.tsv` for the subsection and rerun binder.
- If the requirement is unrealistic for the subsection’s scope, revise `outline/subsection_briefs.jsonl:required_evidence_fields` and rerun binder.
