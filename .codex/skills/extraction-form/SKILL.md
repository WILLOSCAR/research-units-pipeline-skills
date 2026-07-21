---
name: extraction-form
description: |
  Use when `evidence-review` has screened includes and needs a schema-aligned extraction table.
  **Trigger**: extraction form, extraction table, data extraction, 信息提取, 提取表.
  **Use when**: `evidence-review` 在 screening 后进入 extraction（C4），需要把纳入论文按字段落到 CSV 以支持后续 synthesis。
---

# Extraction Form

Transforms screened include rows plus protocol schema into the analysis table used by `evidence-review`.

## Inputs

Required:
- `papers/screening_log.csv`
- `output/PROTOCOL.md`

Optional:
- `papers/paper_notes.jsonl`

## Output

- `papers/extraction_table.csv`

## Contract

The table must:
- contain one row per included paper
- preserve provenance columns (`paper_id`, `title`, `year`, `url`)
- include protocol-defined extraction fields
- keep narrative residue in `notes`, not in schema columns

## Script boundary

`scripts/run.py` should:
- parse the extraction schema from the protocol
- filter `include` rows
- materialize a normalized CSV

## Acceptance

- output exists
- include rows map 1:1 to extraction rows
- schema matches `output/PROTOCOL.md`

## Non-goals

- synthesis writing
- bias scoring
