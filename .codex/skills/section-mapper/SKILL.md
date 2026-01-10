---
name: section-mapper
description: |
  Map papers from the core set to each outline subsection and write `outline/mapping.tsv` with coverage tracking.
  **Trigger**: section mapper, mapping.tsv, coverage, paper-to-section mapping, 论文映射, 覆盖率.
  **Use when**: structure 阶段（C2），已有 `papers/core_set.csv` + `outline/outline.yml`，需要确保每小节有足够支持论文再进入 evidence/writing。
  **Skip if**: 还没有 outline（先跑 `outline-builder`）或 core set 还没收敛。
  **Network**: none.
  **Guardrail**: 覆盖率可审计（避免所有小节重复用同几篇）；为弱覆盖小节留下明确补救方向（扩 query / 合并小节）。
---

# Section Mapper

Create a paper→subsection map that supports evidence building and later synthesis.

Good mapping is **diverse** (avoids reusing the same paper everywhere) and **explainable** (short semantic “why”, not just keyword overlap).

## When to use

- You have `outline/outline.yml` and a `papers/core_set.csv` and need coverage per subsection.
- You want to identify weak-signal subsections early (so you can adjust scope or add papers).

## Inputs

- `papers/core_set.csv`
- `outline/outline.yml`

## Outputs

- `outline/mapping.tsv`
- `outline/mapping_report.md` (diagnostics: reuse hotspots, weak-signal subsections)

## Freeze marker (explicit)

To prevent accidental overwrites after you refine mapping rationales:

- Create `outline/mapping.refined.ok`.

If you rerun the script without this marker, it will back up the previous mapping to a timestamped file:

- `outline/mapping.tsv.bak.<timestamp>`

## Workflow (heuristic)

1. Start from the outline subsections (each subsection should be “mappable”).
2. For each subsection, pick ~3–6 papers that are:
   - representative (canonical / frequently-cited)
   - complementary (different design choices, different eval setups)
   - not overly reused elsewhere unless truly foundational
3. Fill `why` with a short semantic rationale (one line is enough), e.g.:
   - mechanism: “decouples planner/executor; tool calling API”
   - evaluation: “interactive web tasks; strong tool error analysis”
   - safety: “agentic jailbreak surface; mitigation study”
4. After initial mapping, scan for:
   - subsections with <3 papers → either broaden, merge, or expand retrieval
   - a few papers mapped everywhere → diversify; reserve “foundational” papers for only the truly relevant parts

## Quality checklist

- [ ] `outline/mapping.tsv` exists and is non-empty.
- [ ] Most subsections have ≥3 mapped papers (or a clear exception noted in `why`).
- [ ] `why` is semantic (not just `matched_terms=...`).
- [ ] No single paper dominates unrelated subsections.

## Helper script (optional)

### Quick Start

- `python .codex/skills/section-mapper/scripts/run.py --help`
- `python .codex/skills/section-mapper/scripts/run.py --workspace <workspace_dir> --per-subsection 3`

### All Options

- `--per-subsection <n>`: target mapped papers per subsection
- `--diversity-penalty <float>`: penalize repeated reuse of the same paper across many subsections
- `--soft-limit <n>` / `--hard-limit <n>`: caps for per-paper reuse (0 = auto)

### Examples

- Higher diversity (reduce over-reuse):
  - `python .codex/skills/section-mapper/scripts/run.py --workspace <ws> --per-subsection 4 --diversity-penalty 0.25`
- Tighter reuse caps:
  - `python .codex/skills/section-mapper/scripts/run.py --workspace <ws> --per-subsection 3 --soft-limit 6 --hard-limit 10`

### Notes

- Writes `outline/mapping_report.md` diagnostics.
- In `pipeline.py --strict`, mapping may be blocked until generic `why` rationales are replaced with semantic ones.

## Troubleshooting

### Common Issues

#### Issue: `outline/mapping.tsv` is empty or low-coverage

**Symptom**:
- Mapping has few rows, or many subsections have <3 papers.

**Causes**:
- Core set is too small or outline is too fine-grained.

**Solutions**:
- Increase core set size (rerun `dedupe-rank` with larger `--core-size`).
- Merge weak-signal subsections or broaden the scope/queries.

#### Issue: Mapping over-reuses the same papers

**Symptom**:
- Quality gate reports repeated papers across many unrelated subsections.

**Causes**:
- Diversity penalty too low; limited core set.

**Solutions**:
- Raise `--diversity-penalty` and/or set tighter `--soft-limit/--hard-limit`.
- Manually diversify mappings for unrelated sections.

### Recovery Checklist

- [ ] Each subsection has ≥3 mapped papers (target).
- [ ] `why` column contains semantic rationale (not just token overlap).
