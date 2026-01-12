---
name: synthesis-writer
description: |
  Synthesize evidence into a structured narrative (`output/SYNTHESIS.md`) grounded in `papers/extraction_table.csv`, including limitations and bias considerations.
  **Trigger**: synthesis, evidence synthesis, systematic review writing, 综合写作, SYNTHESIS.md.
  **Use when**: systematic review 完成 screening+extraction（含 bias 评估）后进入写作阶段（C4）。
  **Skip if**: 还没有 `papers/extraction_table.csv`（或 protocol/screening 尚未完成）。
  **Network**: none.
  **Guardrail**: 以 extraction table 为证据底座；明确局限性与偏倚；不要在无数据支撑时扩写结论。
---

# Synthesis Writer (systematic review)

Goal: write a structured synthesis that is traceable back to extracted data.

## Inputs

Required:
- `papers/extraction_table.csv`

Optional:
- `DECISIONS.md` (approval to write prose, if your process requires it)
- `output/PROTOCOL.md` (to restate scope and methods consistently)

## Outputs

- `output/SYNTHESIS.md`

## Workflow

1. Check writing approval (if applicable)
   - If your pipeline requires it, confirm `DECISIONS.md` indicates approval before writing prose.

2. Describe the evidence base (methods snapshot)
   - Summarize the included set using `papers/extraction_table.csv` (counts, time window, study types).
   - Keep this strictly descriptive.

3. Theme-based synthesis
   - Group studies by theme/intervention/outcome (based on extraction fields).
   - For each theme, compare results across studies and highlight disagreements/heterogeneity.

4. Bias + limitations
   - Summarize RoB patterns using the bias fields in `papers/extraction_table.csv`.
   - Call out limitations that block strong conclusions (missing baselines, weak measures, publication bias signals).

5. Conclusions (bounded)
   - State only what the extracted evidence supports.
   - Separate “supported conclusions” vs “needs more evidence”.

## Suggested outline for `output/SYNTHESIS.md`

- Research questions + scope (from `output/PROTOCOL.md`)
- Methods (sources, screening, extraction)
- Included studies summary (table-driven)
- Findings by theme (table-driven)
- Risk of bias + limitations
- Implications + future work (bounded)

## Definition of Done

- [ ] Every major claim in `output/SYNTHESIS.md` is traceable to specific fields/rows in `papers/extraction_table.csv`.
- [ ] Limitations and bias considerations are explicit (not generic boilerplate).

## Troubleshooting

### Issue: the synthesis starts inventing facts not in the table

**Fix**:
- Restrict claims to what is explicitly present in `papers/extraction_table.csv`; move speculation to “needs more evidence”.

### Issue: extraction table is too sparse to synthesize

**Fix**:
- Add missing extraction fields/values first (re-run `extraction-form` / `bias-assessor`), then write.
