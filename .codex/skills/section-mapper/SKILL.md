---
name: section-mapper
description: |
  Map papers from the core set to each outline subsection and write `outline/mapping.tsv` with coverage tracking.
  **Trigger**: section mapper, mapping.tsv, coverage, paper-to-section mapping, 论文映射, 覆盖率.
  **Use when**: structure 阶段（C2），已有 `papers/core_set.csv` + `outline/outline.yml`，需要确保每小节有足够支持论文再进入 evidence/writing。
---

# Section Mapper

Create a paper→subsection map that supports evidence building and later synthesis.

Good mapping is **relevant**, **diverse**, and **explainable**. Corpus-wide topic words and repeated outline boilerplate are not evidence of subsection relevance.

## When to use

- You have `outline/outline.yml` and a `papers/core_set.csv` and need coverage per subsection.
- You want to identify weak-signal subsections early (so you can adjust scope or add papers).

## Inputs

- `papers/core_set.csv`
- `outline/outline.yml`

## Outputs

- `outline/mapping.tsv`
- `outline/mapping_report.md` (diagnostics: reuse hotspots, weak-signal subsections)
- `outline/mapping_gap_candidates.tsv` (read-only repair candidates from the deduplicated pool when the core set cannot meet a subsection target)

## Freeze marker (explicit)

To prevent accidental overwrites after you refine mapping rationales:

- Create `outline/mapping.refined.ok`.

The marker is valid only while it is newer than the mapping, core set, outline, query contract, and mapper implementation. Any upstream change invalidates it.

If you rerun the script without this marker, it will back up the previous mapping to a timestamped file:

- `outline/mapping.tsv.bak.<timestamp>`

## Workflow (heuristic)

1. Start from the outline subsections (each subsection should be “mappable”).
2. For each subsection, pick enough papers to support evidence-first writing (A150++ default: 28; smaller runs: ~12–20; lightweight: ~3–6) that are:
   - representative (canonical / frequently-cited)
   - complementary (different design choices, different eval setups)
   - not overly reused elsewhere unless truly foundational
   - supported by section-specific concepts, not only corpus-wide words such as the overall topic name
3. Fill `why` with a short semantic rationale (one line is enough), e.g.:
   - mechanism: “decouples planner/executor; tool calling API”
   - evaluation: “interactive web tasks; strong tool error analysis”
   - safety: “agentic jailbreak surface; mitigation study”
4. After initial mapping, scan for:
   - subsections with <3 papers → either broaden, merge, or expand retrieval
   - a few papers mapped everywhere → diversify; reserve “foundational” papers for only the truly relevant parts
   - unfilled targets → treat them as evidence gaps; do not fill them with unrelated papers merely to satisfy a row count

## Quality checklist

- [ ] `outline/mapping.tsv` exists and is non-empty.
- [ ] Most subsections have ≥3 mapped papers (or a clear exception noted in `why`).
- [ ] `why` is semantic (not just `matched_terms=...`).
- [ ] No single paper dominates unrelated subsections.
- [ ] No low-confidence filler row is used to hide an evidence gap.

## Helper script (optional)

### Quick Start

- `uv run python .codex/skills/section-mapper/scripts/run.py --help`
- `uv run python .codex/skills/section-mapper/scripts/run.py --workspace <workspace> --per-subsection 28`

### All Options

- `--per-subsection <n>`: target mapped papers per subsection
- `--diversity-penalty <int>`: penalize repeated reuse of the same paper across many subsections
- `--soft-limit <n>` / `--hard-limit <n>`: caps for per-paper reuse (0 = auto)
- `--minimum-score <n>`: automatic relevance floor (default: 3); lower only when the resulting mappings will be reviewed manually

### Examples

- Higher diversity (reduce over-reuse):
  - `uv run python .codex/skills/section-mapper/scripts/run.py --workspace <workspace> --per-subsection 4 --diversity-penalty 5`
- Tighter reuse caps:
  - `uv run python .codex/skills/section-mapper/scripts/run.py --workspace <workspace> --per-subsection 3 --soft-limit 6 --hard-limit 10`

### Notes

- Writes `outline/mapping_report.md` diagnostics.
- Writes `outline/mapping_gap_candidates.tsv` instead of silently mutating `papers/core_set.csv`; a human or curation step remains responsible for changing the frozen core set.
- Removes corpus-common and outline-common terms before scoring, weights subsection-title alignment, and refuses candidates without enough section-specific evidence.
- Optional `assets/domain_packs/*.json` rules can tighten ambiguous subsection labels for an explicitly detected domain; these rules constrain mapping rather than changing the core set.
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
