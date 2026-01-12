---
name: novelty-matrix
description: |
  Create a novelty/prior-work matrix comparing the submission’s contributions against related work (overlaps vs deltas).
  **Trigger**: novelty matrix, prior-work matrix, overlap/delta, 相关工作对比, 新颖性矩阵.
  **Use when**: peer review 中评估 novelty/positioning，需要把贡献与相关工作逐项对齐并写出差异点证据。
  **Skip if**: 缺少 claims（先跑 `claims-extractor`）或你不打算做新颖性定位分析。
  **Network**: none (retrieval of additional related work is out-of-scope unless provided).
  **Guardrail**: 明确 overlap 与 delta；尽量给出可追溯证据来源（来自稿件/引用/作者陈述）。
---

# Novelty Matrix (overlap vs delta)

Goal: make novelty/positioning concrete by aligning each contribution against the closest prior work.

## Inputs

Required:
- `output/CLAIMS.md`

Optional:
- A provided list of related work (titles/URLs/DOIs) or the submission’s reference list

## Outputs

- `output/NOVELTY_MATRIX.md`

## Output format (recommended)

- Rows: contributions/claims (from `output/CLAIMS.md`)
- Columns: closest related works (provided or cited by the paper)
- For each row/column, record:
  - `overlap`: what is the same
  - `delta`: what is different/new
  - `evidence`: where this is supported (paper statement / citation / method difference)

## Workflow

1. Extract the contribution list from `output/CLAIMS.md`.
2. Pick ≥5 closest related works (or state explicitly why you cannot).
3. For each contribution, compare to each related work:
   - identify overlap
   - identify delta
   - attach evidence (quote/section/citation pointer)
4. Summarize:
   - which contributions look clearly novel
   - which ones look like incremental variants

## Definition of Done

- [ ] Matrix includes ≥5 related works or explains why unavailable.
- [ ] Every “delta” entry has a short evidence pointer (not just opinion).

## Troubleshooting

### Issue: no related works list is available

**Fix**:
- Use the paper’s own citations as the initial related set; if even that is missing, mark `needs_related_work_list` and stop.

### Issue: overlap/delta becomes vague

**Fix**:
- Force each cell to reference a concrete axis (problem setting, method component, training data, evaluation protocol, result).
