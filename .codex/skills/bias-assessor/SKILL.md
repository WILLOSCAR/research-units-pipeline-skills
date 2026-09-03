---
name: bias-assessor
description: "Use when `evidence-review` has an extraction table and needs lightweight risk-of-bias fields."
---

# Bias Assessor

## Triggers & routing

- **Trigger**: bias, risk-of-bias, RoB, evidence quality, 偏倚评估, 证据质量.
- **Use when**: `evidence-review` 已生成 `papers/extraction_table.csv`，需要在 synthesis 前补齐偏倚/质量字段。
- **Skip if**: 不是 evidence/systematic review，或还没有 `papers/extraction_table.csv`。
- **Network**: none.
- **Guardrail**: 使用简单可复核刻度（low/unclear/high）+ 简短 notes；保持字段一致性。


Enriches the extraction table with lightweight risk-of-bias fields for `evidence-review`.

## Input

- `papers/extraction_table.csv`

## Output

- updated `papers/extraction_table.csv`

## Contract

The table should expose stable RoB columns:
- `rob_selection`
- `rob_measurement`
- `rob_confounding`
- `rob_reporting`
- `rob_overall`
- `rob_notes`

Allowed values are fixed:
- `low`
- `unclear`
- `high`

## Script boundary

`scripts/run.py` should:
- add missing RoB columns
- assign a conservative overall score
- keep notes brief

## Acceptance

- RoB columns exist
- all included rows have values
- values stay within the fixed scale

## Non-goals

- deep methodological critique
- rewriting extraction contents
