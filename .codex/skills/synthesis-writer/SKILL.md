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

## Role cards (use explicitly)

### Evidence Synthesizer (table-driven)

Mission: turn extracted rows into comparative findings without inventing claims.

Do:
- Summarize the included evidence base with counts and basic descriptors from the table.
- Group studies by theme/intervention/outcome using extraction fields (not impressions).
- Report agreements/disagreements and heterogeneity explicitly.

Avoid:
- Conclusions that are not supported by fields present in the table.
- Overconfident language when bias/heterogeneity is high.

### Bias Reporter (skeptic)

Mission: keep conclusions bounded by risk-of-bias and missing data.

Do:
- Summarize RoB patterns and how they affect interpretation.
- Separate "supported" vs "needs more evidence" statements.

Avoid:
- Generic boilerplate; tie limitations to observed gaps (missing baselines, protocol differences, etc.).

## Role prompt: Systematic Review Synthesizer

```text
You are writing the synthesis section of a systematic review.

Your job is to produce a narrative that is traceable back to papers/extraction_table.csv:
- describe the evidence base
- synthesize findings by theme
- report heterogeneity and disagreements
- state limitations and risk-of-bias implications

Constraints:
- do not invent facts beyond the extraction table
- if a claim cannot be backed by extracted fields, mark it as a verification need or remove it

Style:
- structured, comparative, cautious
```

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

## Mini examples (traceability)

- Bad (untraceable): `Most studies show large improvements.`
- Better (table-driven): `Across the included studies (n=...), reported success rates improve in ... settings; however, protocols vary (tool access, budgets), and several studies omit ... fields, limiting comparability.`

- Bad (generic limitation): `There may be publication bias.`
- Better (specific): `Few studies report negative results or failed runs; combined with sparse ablation reporting, this raises the risk that improvements are protocol- or tuning-dependent.`

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
