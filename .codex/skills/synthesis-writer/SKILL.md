---
name: synthesis-writer
description: "Use when `evidence-review` has completed extraction and needs a bounded narrative synthesis."
---

# Synthesis Writer

## Triggers & routing

- **Trigger**: synthesis, evidence synthesis, systematic review writing, 综合写作, SYNTHESIS.md.
- **Use when**: `evidence-review` 完成 screening+extraction（含 bias 评估）后进入写作阶段（C5）。
- **Skip if**: 还没有 `papers/extraction_table.csv`（或 protocol/screening 尚未完成）。
- **Network**: none.
- **Guardrail**: 以 extraction table 为证据底座；明确局限性与偏倚；不要在无数据支撑时扩写结论。


Transforms the extraction table into the final `evidence-review` narrative.

## Input

- `papers/extraction_table.csv`

Optional:
- `output/PROTOCOL.md`
- `DECISIONS.md`

## Output

- `output/SYNTHESIS.md`

## Contract

The synthesis must include stable sections:
- `## Included studies summary`
- `## Findings by theme`
- `## Risk of bias`
- `## Supported conclusions`
- `## Needs more evidence`

## Script boundary

`scripts/run.py` should:
- summarize extracted evidence conservatively
- keep conclusions bounded by table contents
- render the stable section structure

It should not invent findings not grounded in the extraction table.

## Acceptance

- output exists
- includes all stable sections
- stays table-grounded and bounded

## Non-goals

- upstream extraction repair
- free-form speculative discussion
