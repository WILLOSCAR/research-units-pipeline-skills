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

Purpose: prevent a common failure mode: polishing rewrites text and accidentally moves citation markers into a different `###` subsection, breaking claim→evidence alignment.

## Inputs

- `output/DRAFT.md`
- `output/citation_anchors.prepolish.jsonl` (baseline; created by `draft-polisher` on first run)

## Outputs

- `output/CITATION_ANCHORING_REPORT.md` (PASS/FAIL + drift examples)

## Baseline policy

- `draft-polisher` captures a baseline once per run: `output/citation_anchors.prepolish.jsonl`.
- Subsequent polish runs should keep per-H3 citation sets stable.

## Workflow (analysis-only)

Role:
- **Auditor**: only checks and reports; does not edit.

Steps:

1) Load the baseline anchors.
2) Parse the current `output/DRAFT.md` into `###` subsections and extract citation keys per subsection.
3) Compare current sets to baseline sets:
- keys added/removed within a subsection
- keys that migrated across subsections
4) Write `output/CITATION_ANCHORING_REPORT.md`:
- `- Status: PASS` only if no drift is detected
- otherwise, `- Status: FAIL` with a short diff table + examples

## Notes

If you intentionally restructure across subsections:
- delete `output/citation_anchors.prepolish.jsonl` and regenerate a new baseline (then treat that as the new regression anchor).

## Troubleshooting

### Issue: baseline anchor file is missing

Fix:
- Run `draft-polisher` once to generate `output/citation_anchors.prepolish.jsonl`, then rerun the anchoring check.

### Issue: citations intentionally moved across subsections

Fix:
- Delete `output/citation_anchors.prepolish.jsonl` and regenerate a new baseline (then treat that as the new regression anchor).
