---
name: extraction-form
description: |
  Extract study data into a structured table (`papers/extraction_table.csv`) using the protocol’s extraction schema.
  **Trigger**: extraction form, extraction table, data extraction, 信息提取, 提取表.
  **Use when**: systematic review 在 screening 后进入 extraction（C3），需要把纳入论文按字段落到 CSV 以支持后续 synthesis。
  **Skip if**: 还没有 `papers/screening_log.csv` 或 protocol 未锁定。
  **Network**: none.
  **Guardrail**: 严格按 schema 填字段；不要在此阶段写 narrative synthesis（那是 `synthesis-writer`）。
---

# Extraction Form (systematic review)

Goal: create a consistent, analysis-ready extraction table that is directly grounded in the protocol.

## Inputs

Required:
- `papers/screening_log.csv`
- `output/PROTOCOL.md`

Optional:
- `papers/paper_notes.jsonl` (if you already have structured notes)

## Outputs

- `papers/extraction_table.csv`

## Workflow

1. Determine the included set
   - From `papers/screening_log.csv`, collect all rows with `decision=include`.

2. Build/confirm the schema
   - Use the extraction schema defined in `output/PROTOCOL.md`.
   - If the protocol does not define fields yet, stop and update `output/PROTOCOL.md` first.

3. Populate `papers/extraction_table.csv`
   - One row per included paper.
   - If `papers/paper_notes.jsonl` exists, use it as a structured source for values/provenance (but keep the table schema governed by `output/PROTOCOL.md`).
   - Always include provenance columns:
     - `paper_id`, `title`, `year`, `url`
   - For each protocol-defined field:
     - fill concrete values (units explicit)
     - use an explicit sentinel for unknowns (recommended: empty cell + `notes`)

4. Keep it auditable
   - If a value is inferred (not directly stated), mark it in a notes column.
   - Do not write synthesis; only extraction.

5. Quick QA
   - Ensure 1:1 coverage: included papers == extraction rows.
   - Spot-check a few rows against the paper text/notes.

## Definition of Done

- [ ] `papers/extraction_table.csv` exists.
- [ ] Every included paper from `papers/screening_log.csv` has exactly one extraction row.
- [ ] Column meanings match `output/PROTOCOL.md` (no ad-hoc columns without updating the protocol).

## Troubleshooting

### Issue: the protocol does not specify extraction fields

**Fix**:
- Update `output/PROTOCOL.md` (extraction schema section) and re-run extraction.

### Issue: extraction table mixes narrative text with fields

**Fix**:
- Move narrative into a `notes` column and keep the rest as atomic values (numbers/enums/short strings).
