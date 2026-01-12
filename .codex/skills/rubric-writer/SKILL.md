---
name: rubric-writer
description: |
  Write a rubric-based peer review report (`output/REVIEW.md`) using extracted claims and evidence gaps (novelty/soundness/clarity/impact).
  **Trigger**: rubric review, referee report, peer review write-up, 审稿报告, REVIEW.md.
  **Use when**: peer-review pipeline 的最后阶段（C3），已有 `output/CLAIMS.md` + `output/MISSING_EVIDENCE.md`（以及可选 novelty matrix）。
  **Skip if**: 上游产物未就绪（claims/evidence gaps 缺失）或你不打算输出完整审稿报告。
  **Network**: none.
  **Guardrail**: 给可执行建议（actionable feedback），并覆盖 novelty/soundness/clarity/impact；避免泛泛而谈。
---

# Rubric Writer (referee report)

Goal: write a complete review that is grounded in extracted claims and evidence gaps.

## Inputs

Required:
- `output/CLAIMS.md`
- `output/MISSING_EVIDENCE.md`

Optional:
- `output/NOVELTY_MATRIX.md`
- `DECISIONS.md` (if you have reviewer constraints/format)

## Outputs

- `output/REVIEW.md`

## Workflow

0. If `DECISIONS.md` exists, follow any required reviewer format/constraints.

1. One-paragraph summary (bounded)
   - Summarize the paper’s goal + main contributions using `output/CLAIMS.md`.

2. Rubric sections
   - Novelty: reference `output/NOVELTY_MATRIX.md` (if present) and/or the related work discussion.
   - Soundness: reference the concrete gaps from `output/MISSING_EVIDENCE.md`.
   - Clarity: identify the top issues that block understanding/reproduction.
   - Impact: discuss likely relevance if the issues were fixed.

3. Actionable feedback
   - Major concerns: each with “problem → why it matters → minimal fix”.
   - Minor comments: clarity, presentation, missing details.

4. Final recommendation
   - Choose a decision label and justify it primarily via soundness + evidence quality.

## Definition of Done

- [ ] `output/REVIEW.md` covers novelty/soundness/clarity/impact.
- [ ] Major concerns are actionable (each has a minimal fix).
- [ ] Critiques are traceable to `output/CLAIMS.md` / `output/MISSING_EVIDENCE.md` (not free-floating).

## Troubleshooting

### Issue: review turns into a rewrite of the paper

**Fix**:
- Cut; keep to critique + actionable fixes and avoid adding new content.

### Issue: review is generic (“needs more experiments”)

**Fix**:
- Replace with concrete gaps from `output/MISSING_EVIDENCE.md` (which baseline, which dataset, which ablation).
