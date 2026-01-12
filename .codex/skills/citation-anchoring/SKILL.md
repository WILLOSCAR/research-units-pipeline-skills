---
name: citation-anchoring
description: |
  Regression-check citation anchoring (citations stay in the same subsection) to prevent “polish drift” that breaks claim→evidence alignment.
  **Trigger**: citation anchoring, citation drift, regression, cite stability, 引用锚定, 引用漂移.
  **Use when**: after editing/polishing, you want to confirm citations did not migrate across `###` subsections.
  **Skip if**: you do not have a baseline anchor file yet.
  **Network**: none.
  **Guardrail**: analysis-only; do not edit content.
---

# Citation Anchoring (regression)

Purpose: prevent a common failure mode:
- polishing rewrites text and accidentally moves citation markers into a different subsection, breaking claim→evidence alignment.

## Baseline policy

- `draft-polisher` captures a baseline once per run: `output/citation_anchors.prepolish.jsonl`.
- Subsequent polisher runs block if citation sets per H3 change.

## Role

- **Auditor**: only checks and reports; does not edit.

## Notes

If you intentionally restructure across subsections:
- delete `output/citation_anchors.prepolish.jsonl` and regenerate a new baseline.

## Troubleshooting

### Issue: baseline anchor file is missing

**Fix**:
- Run `draft-polisher` once to generate `output/citation_anchors.prepolish.jsonl`, then rerun the anchoring check.

### Issue: citations intentionally moved across subsections

**Fix**:
- Delete `output/citation_anchors.prepolish.jsonl` and regenerate a new baseline (then treat that as the new regression anchor).
