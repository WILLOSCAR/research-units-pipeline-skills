---
name: bias-assessor
description: |
  Add bias/risk-of-bias assessment fields to an extraction table and populate them consistently.
  **Trigger**: bias, risk-of-bias, RoB, evidence quality, 偏倚评估, 证据质量.
  **Use when**: systematic review 已生成 `papers/extraction_table.csv`，需要在 synthesis 前补齐偏倚/质量字段。
  **Skip if**: 不是 systematic review，或还没有 `papers/extraction_table.csv`。
  **Network**: none.
  **Guardrail**: 使用简单可复核刻度（low/unclear/high）+ 简短 notes；保持字段一致性。
---

# Bias Assessor (risk-of-bias, lightweight)

Goal: make evidence quality explicit in a way that is quick, consistent, and auditable.

## Inputs

- `papers/extraction_table.csv`

## Outputs

- Updated `papers/extraction_table.csv`

## Recommended fields

Use a simple 3-level scale (all lowercase): `low | unclear | high`.

Suggested columns to add (if missing):
- `rob_selection`
- `rob_measurement`
- `rob_confounding`
- `rob_reporting`
- `rob_overall`
- `rob_notes`

## Workflow

1. Read `papers/extraction_table.csv` and identify the set of included studies.
2. If RoB columns are missing, add them (keep names stable once introduced).
3. For each study, fill each RoB domain:
   - `low`: design/reporting plausibly controls the bias
   - `unclear`: not enough information to judge
   - `high`: clear risk (e.g., missing controls, ambiguous measurement, selective reporting)
4. Set `rob_overall` conservatively:
   - `high` if any domain is `high`
   - `unclear` if no `high` but at least one `unclear`
   - `low` only if all domains are `low`
5. Add 1–3 short notes in `rob_notes` that justify the rating.

## Definition of Done

- [ ] Every included paper row has all RoB columns filled.
- [ ] Values are strictly from `low|unclear|high` (no free-form scale drift).
- [ ] Notes are short and specific (what was missing / what was strong).

## Troubleshooting

### Issue: the table has mixed or inconsistent RoB column names

**Fix**:
- Normalize to the recommended column names and keep a single set across all rows.

### Issue: the paper lacks enough methodological detail

**Fix**:
- Prefer `unclear` with a concrete note (“no details on X”) rather than guessing.
