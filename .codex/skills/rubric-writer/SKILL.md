---
name: rubric-writer
description: |
  Use when `paper-review` has claims plus evidence gaps and needs the final referee-style report.
  **Trigger**: rubric review, referee report, peer review write-up, 审稿报告, REVIEW.md.
  **Use when**: `paper-review` pipeline 的最后阶段（C3），已有 `output/CLAIMS.md` + `output/MISSING_EVIDENCE.md`（以及可选 novelty matrix）。
---

# Rubric Writer

Transforms review evidence artifacts into the final `paper-review` deliverable.

## Inputs

Required:
- `output/CLAIMS.md`
- `output/MISSING_EVIDENCE.md`

Optional:
- `output/NOVELTY_MATRIX.md`
- `DECISIONS.md`

## Output

- `output/REVIEW.md`

## Contract

The review must expose stable sections:
- `### Summary`
- `### Novelty`
- `### Soundness`
- `### Clarity`
- `### Impact`
- `### Major Concerns`
- `### Minor Comments`
- `### Recommendation`

Every major concern must cite its `claim_id` or `gap_id`. This is the
traceability interface consumed by the paper-review scorecard.

## Script boundary

`scripts/run.py` should:
- read prior review artifacts
- render the stable rubric sections
- keep the review bounded and traceable

It should not re-parse the manuscript from scratch or perform retrieval.

## Acceptance

- `output/REVIEW.md` exists
- includes all stable rubric sections
- recommendation is explicit

## Non-goals

- deep manuscript parsing
- novelty retrieval
- writing an author rebuttal
