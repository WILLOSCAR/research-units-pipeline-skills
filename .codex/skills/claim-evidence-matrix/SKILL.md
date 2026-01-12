---
name: claim-evidence-matrix
description: |
  Build a section-by-section claim–evidence matrix (`outline/claim_evidence_matrix.md`) from the outline and paper notes.
  **Trigger**: claim–evidence matrix, evidence mapping, 证据矩阵, 主张-证据对齐.
  **Use when**: 写 prose 之前需要把每个小节的可检验主张与证据来源显式化（outline + paper notes 已就绪）。
  **Skip if**: 缺少 `outline/outline.yml` 或 `papers/paper_notes.jsonl`。
  **Network**: none.
  **Guardrail**: bullets-only（NO PROSE）；每个 claim 至少 2 个证据来源（或显式说明例外）。
---

# Claim–Evidence Matrix

Make the survey’s claims explicit and auditable **before** writing prose.

This should stay **bullets-only** (NO PROSE). The goal is to make later writing *easy* and to prevent “template prose” from sneaking in.

## Inputs

- `outline/outline.yml`
- `papers/paper_notes.jsonl`
- Optional: `outline/mapping.tsv`

## Output

- `outline/claim_evidence_matrix.md`

## Workflow (heuristic)
Uses: `outline/outline.yml`, `outline/mapping.tsv`.


1. For each subsection, write 1–3 claims that are:
   - specific (mechanism / assumption / empirical finding)
   - falsifiable (“X reduces tool errors under Y evaluation”, not “X is important”)
2. For each claim, list ≥2 evidence sources:
   - prefer different styles of evidence (method paper + eval/benchmark paper, or two competing approaches)
3. Keep it tight: claim → evidence → (optional) caveat/limitations.
4. If evidence is weak or only abstract-level, say so explicitly (don’t overclaim).
5. If `bibkey` exists in `papers/paper_notes.jsonl`, include `[@BibKey]` next to evidence items to make later prose/LaTeX conversion smoother.

## Quality checklist

- [ ] Every subsection has ≥1 claim.
- [ ] Each claim lists ≥2 evidence sources (or an explicit exception).
- [ ] Claims are not copy-pasted templates (avoid “围绕…总结…” boilerplate).

## Helper script (optional)

### Quick Start

- `python .codex/skills/claim-evidence-matrix/scripts/run.py --help`
- `python .codex/skills/claim-evidence-matrix/scripts/run.py --workspace <workspace_dir>`

### All Options

- See `--help` (this helper is intentionally minimal)

### Examples

- Generate a first-pass matrix, then refine manually:
  - Run the helper once, then refine `outline/claim_evidence_matrix.md` by tightening claims and adding caveats when evidence is abstract-level.

### Notes

- The helper generates a baseline matrix (claims + evidence) and never overwrites non-placeholder work; in `pipeline.py --strict` it will be blocked only if placeholder markers remain.

## Troubleshooting

### Issue: claims are generic or read like outline boilerplate

**Fix**:
- Tighten each claim to a falsifiable statement and add an explicit caveat if evidence is abstract-only.

### Issue: you cannot add `[@BibKey]` because keys are missing

**Fix**:
- Run `citation-verifier` to generate `citations/ref.bib`, then use the produced keys in the matrix.
