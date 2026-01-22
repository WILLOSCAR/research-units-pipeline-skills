---
name: paper-notes
description: |
  Write structured notes for each paper in the core set into `papers/paper_notes.jsonl` (summary/method/results/limitations).
  **Trigger**: paper notes, structured notes, reading notes, 论文笔记, paper_notes.jsonl.
  **Use when**: survey 的 evidence 阶段（C3），已有 `papers/core_set.csv`（以及可选 fulltext），需要为后续 claims/citations/writing 准备可引用证据。
  **Skip if**: 还没有 core set（先跑 `dedupe-rank`），或你只做极轻量 snapshot 不需要细粒度证据。
  **Network**: none.
  **Guardrail**: 具体可核对（method/metrics/limitations），避免大量重复模板；保持结构化字段而非长 prose。
---

# Paper Notes

Produce consistent, searchable paper notes that later steps (claims, visuals, writing) can reliably synthesize.

This is still **NO PROSE**: keep notes as bullets / short fields, not narrative paragraphs.

## Role cards (prompt-level guidance)

- **Close Reader**
  - Mission: extract what is *specific* and *checkable* (setup, method, metrics, limits).
  - Do: name concrete tasks/benchmarks and what the paper actually measures.
  - Avoid: generic summary boilerplate that could fit any paper.

- **Results Recorder**
  - Mission: capture evaluation anchors that later writing needs.
  - Do: record task + metric + constraints (budget/tool access) whenever available.
  - Avoid: copying numbers without the evaluation setting that makes them meaningful.

- **Limitation Logger**
  - Mission: capture the caveats that change interpretation.
  - Do: write paper-specific limitations (protocol mismatch, missing ablations, threat model gaps).
  - Avoid: repeated generic limitations like “may not generalize” without specifics.


## When to use

- After you have a core set (and ideally a mapping) and need evidence-ready notes.
- Before writing a survey draft.

## Inputs

- `papers/core_set.csv`
- Optional: `outline/mapping.tsv` (to prioritize)
- Optional: `papers/fulltext_index.jsonl` + `papers/fulltext/*.txt` (if running in fulltext mode)

## Output

- `papers/paper_notes.jsonl` (JSONL; one record per paper)

## Decision: evidence depth

- If you have extracted text (`papers/fulltext/*.txt`) → enrich key papers using fulltext snippets and set `evidence_level: "fulltext"`.
- If you only have abstracts (default) → keep long-tail notes abstract-level, but still fully enrich **high-priority** papers (see below).

## Workflow (heuristic)
Uses: `outline/mapping.tsv`, `papers/fulltext_index.jsonl`.


1. Ensure **coverage**: every `paper_id` in `papers/core_set.csv` must have one JSONL record.
2. Use mapping to choose **high-priority papers**:
   - heavily reused across subsections
   - pinned classics (ReAct/Toolformer/Reflexion… if in scope)
3. For high-priority papers, capture:
   - 3–6 summary bullets (what’s new, what problem setting, what’s the loop)
   - `method` (mechanism and architecture; what differs from baselines)
   - `key_results` (benchmarks/metrics; include numbers if available)
   - `limitations` (specific assumptions/failure modes; avoid generic boilerplate)
4. For long-tail papers:
   - keep summary bullets short (abstract-derived is OK)
   - still include at least one limitation, but make it specific when possible
5. Assign a stable `bibkey` for each paper for citation generation.

## Quality checklist

- [ ] Coverage: every `paper_id` in `papers/core_set.csv` appears in `papers/paper_notes.jsonl`.
- [ ] High-priority papers have non-`TODO` method/results/limitations.
- [ ] Limitations are not copy-pasted across many papers.
- [ ] `evidence_level` is set correctly (`abstract` vs `fulltext`).

## Helper script (optional)

### Quick Start

- `python .codex/skills/paper-notes/scripts/run.py --help`
- `python .codex/skills/paper-notes/scripts/run.py --workspace <workspace_dir>`

### All Options

- See `--help` (this helper is intentionally minimal)

### Examples

- Generate notes, then optionally enrich `priority=high` papers:
  - Run the helper once, then refine `papers/paper_notes.jsonl` (e.g., add full-text details for key papers and diversify limitations).

### Notes

- The helper writes deterministic metadata/abstract-level notes and marks key papers with `priority=high`.
- In `pipeline.py --strict` it will be blocked if high-priority notes are incomplete (missing method/key_results/limitations) or contain placeholders.

## Troubleshooting

### Common Issues

#### Issue: High-priority notes still look like scaffolds

**Symptom**:
- Quality gate reports missing `method/key_results` or `TODO` placeholders.

**Causes**:
- Notes were generated from abstracts only; key papers weren’t enriched.

**Solutions**:
- Fully enrich `priority=high` papers: `method`, ≥1 `key_results`, ≥3 `summary_bullets`, ≥1 concrete `limitations`.
- If you need full text evidence, run `pdf-text-extractor` in `fulltext` mode for key papers.

#### Issue: Repeated limitations across many papers

**Symptom**:
- Quality gate reports repeated limitation boilerplate.

**Causes**:
- Copy-pasted limitations instead of paper-specific failure modes/assumptions.

**Solutions**:
- Replace boilerplate with paper-specific limitations (setup, data, evaluation gaps, failure cases).

### Recovery Checklist

- [ ] `papers/paper_notes.jsonl` covers all `papers/core_set.csv` paper_ids.
- [ ] ≥80% of `priority=high` notes satisfy method/results/limitations completeness.
- [ ] No `TODO` remains in high-priority notes.
