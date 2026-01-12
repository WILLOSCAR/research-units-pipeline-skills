---
name: claim-matrix-rewriter
description: |
  Rewrite `outline/claim_evidence_matrix.md` as a projection/index of evidence packs (NO PROSE), so claims/axes are driven by `outline/evidence_drafts.jsonl` rather than outline placeholders.
  **Trigger**: claim matrix rewriter, rewrite claim-evidence matrix, evidence-first claim matrix, matrix index, 证据矩阵重写, 从证据包生成矩阵.
  **Use when**: `outline/subsection_briefs.jsonl` + `outline/evidence_drafts.jsonl` are ready and you want a clean claim→evidence index for QA/writing.
  **Skip if**: `outline/claim_evidence_matrix.md` is already refined and consistent with evidence packs.
  **Network**: none.
  **Guardrail**: NO PROSE; do not invent facts; only cite keys present in `citations/ref.bib`; if evidence is abstract/title-only, claims must be provisional.
---

# Claim Matrix Rewriter (Evidence-first, NO PROSE)

Purpose: make `outline/claim_evidence_matrix.md` a **navigation/index layer** that is driven by evidence packs (not by outline bullets).

Key property: keep the **legacy, gate-checked format** so downstream QA can rely on stable markers:

- `- Claim:` (one per subsection)
- `  - Evidence:` (>=2 per subsection)

## Inputs

- `outline/subsection_briefs.jsonl`
- `outline/evidence_drafts.jsonl`
- `citations/ref.bib`

## Outputs

- `outline/claim_evidence_matrix.md`

## Non-negotiables

- NO PROSE: bullets only.
- No placeholders: no `...`, unicode ellipsis (`…`), `TODO`, `(placeholder)`, or `<!-- SCAFFOLD -->`.
- Claims are evidence-aware:
  - fulltext-backed: may summarize comparisons
  - abstract-only/title-only: must be provisional (no strong “dominant trade-offs” language)

## Helper script

- `python .codex/skills/claim-matrix-rewriter/scripts/run.py --help`
- `python .codex/skills/claim-matrix-rewriter/scripts/run.py --workspace <ws>`

## Script

### Quick Start

- `python .codex/skills/claim-matrix-rewriter/scripts/run.py --help`
- `python .codex/skills/claim-matrix-rewriter/scripts/run.py --workspace <ws>`

### All Options

- See `--help`.
- Requires: `outline/subsection_briefs.jsonl`, `outline/evidence_drafts.jsonl`, `citations/ref.bib`.

### Examples

- Rewrite the matrix from evidence packs:
  - Ensure `outline/subsection_briefs.jsonl` and `outline/evidence_drafts.jsonl` exist and `blocking_missing` is empty.
  - Ensure `citations/ref.bib` exists and contains the cited keys.
  - Run: `python .codex/skills/claim-matrix-rewriter/scripts/run.py --workspace workspaces/<ws>`

## Troubleshooting

### Issue: cited keys are missing from `citations/ref.bib`

**Fix**:
- Run `citation-verifier` (or fix the upstream notes) so every referenced key exists before rewriting.

### Issue: evidence packs still have `blocking_missing`

**Fix**:
- Fix upstream evidence (`paper-notes` / `evidence-draft`) first; the matrix should not “paper over” missing evidence.
