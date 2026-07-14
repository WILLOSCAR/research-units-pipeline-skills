---
name: novelty-matrix
description: |
  Use when `paper-review` needs overlap/delta positioning against provided related work.
  **Trigger**: novelty matrix, prior-work matrix, overlap/delta, 相关工作对比, 新颖性矩阵.
  **Use when**: `paper-review` 中评估 novelty/positioning，需要把贡献与相关工作逐项对齐并写出差异点证据。
  **Skip if**: 缺少 claims（先跑 `claims-extractor`）或你不打算做新颖性定位分析。
  **Network**: none (retrieval of additional related work is out-of-scope unless provided).
  **Guardrail**: 明确 overlap 与 delta；尽量给出可追溯证据来源（来自稿件/引用/作者陈述）。
---

# Novelty Matrix

Transforms a claim ledger plus related-work surface into a novelty positioning table for `paper-review`.

## Input

Required:
- `output/CLAIMS.md`

Optional:
- manuscript reference list
- user-provided related work list

## Output

- `output/NOVELTY_MATRIX.md`
- `output/NOVELTY_MATRIX.tsv` (`review-novelty-row.v1`)

## Contract

Each matrix row must expose:
- claim
- closest related work
- overlap
- delta
- evidence note

## Script boundary

`scripts/run.py` should:
- extract candidate related works from available sources
- generate stable overlap/delta rows
- write a table-shaped artifact

Keep matching heuristics and markdown rendering in shared tooling.

## Acceptance

- output exists
- includes at least one row per claim
- if related works are unavailable, the artifact says so explicitly
- TSV rows preserve `claim_id`, overlap, delta, and evidence as separate fields

## Non-goals

- final novelty judgment prose
- retrieval of a new literature corpus
