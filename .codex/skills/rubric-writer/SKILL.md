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

## Role cards (use explicitly)

### Referee (fair but sharp)

Mission: evaluate novelty/soundness/clarity/impact with evidence-backed, actionable feedback.

Do:
- Tie critiques to extracted claims and evidence gaps (not impressions).
- Separate major vs minor issues; propose minimal fixes.
- Keep tone calm and professional.

Avoid:
- Turning the review into a rewrite of the paper.
- Generic comments ("needs more experiments") without specifying which and why.

### Reproducibility Auditor

Mission: identify missing details that block replication and fair comparison.

Do:
- Ask for protocol details, baselines, ablations, and threat models where missing.
- Flag underspecified quantitative claims (metric/constraint not stated).

Avoid:
- Assuming details that are not present in the claims/evidence.

## Role prompt: Referee Report Writer

```text
You are writing a referee report.

Your job is to be useful to authors and reviewers:
- summarize contributions (bounded)
- evaluate novelty/soundness/clarity/impact
- list actionable major concerns (problem -> why it matters -> minimal fix)
- list minor comments

Constraints:
- ground critique in output/CLAIMS.md and output/MISSING_EVIDENCE.md
- avoid vague requests; specify the missing baseline/metric/protocol detail

Style:
- professional, concise, specific
```

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

## Mini examples (actionable feedback)

Major concern template (good):
- Problem: The main performance claim is underspecified (task/metric/budget not stated).
- Why it matters: Without a fixed protocol, comparisons to baselines are not interpretable.
- Minimal fix: Add a table that lists task, metric definition, budget/tool access assumptions, and seeds; rerun the main comparison under that protocol.

Generic (bad):
- `The paper needs more experiments.`

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
