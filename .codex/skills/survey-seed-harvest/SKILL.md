---
name: survey-seed-harvest
description: |
  Identify survey/review papers in a retrieved set and extract taxonomy seeds into `outline/taxonomy.yml` (topics/subtopics/terminology).
  **Trigger**: survey seed harvest, taxonomy seeds, 从 survey 提 taxonomy, bootstrap taxonomy.
  **Use when**: retrieval/dedup 后想快速从已有 survey/review 论文中提取术语与主题结构，用于加速 `taxonomy-builder`。
  **Skip if**: 已经有高质量 taxonomy（或你不想被 survey 既有框架限制）。
  **Network**: none.
  **Guardrail**: 产物是 seed，必须经 `taxonomy-builder` 重写与对齐 scope；避免生成泛化占位节点。
---

# Survey Seed Harvest

Bootstrap taxonomy *seeds* from existing survey/review papers inside your retrieved set.

This is an accelerator for the early structure stage: it should make `taxonomy-builder` easier, not replace it.

## Inputs

- `papers/papers_dedup.jsonl` (deduped paper metadata with titles/abstracts)

## Outputs

- `outline/taxonomy.yml` (seed taxonomy; expected to be refined)

## Workflow (heuristic)
Uses: `papers/papers_dedup.jsonl`.


1. Find likely survey/review papers:
   - title/abstract contains “survey”, “review”, “systematic”, “meta-analysis”
2. Extract candidate topic terms and group them into:
   - ~4–10 top-level nodes (“chapters”)
   - 2–6 children per node (mappable leaves)
3. Write short, *actionable* descriptions:
   - what belongs here / what does not
   - (optional) list 2–5 representative titles as seeds
4. Treat the result as a starting point:
   - pass it to `taxonomy-builder` for domain-meaningful rewriting and scope alignment.

## Quality checklist

- [ ] `outline/taxonomy.yml` exists and is valid YAML.
- [ ] Taxonomy has at least 2 levels (`children` used) and every node has a description.
- [ ] Avoid generic placeholder nodes like “Overview/Benchmarks/Open Problems” unless they are truly content-based for your domain.

## Script (optional helper)

### Quick Start

- `python .codex/skills/survey-seed-harvest/scripts/run.py --help`
- `python .codex/skills/survey-seed-harvest/scripts/run.py --workspace <workspace_dir>`

### All Options

- `--top-k <n>`: number of candidate terms to consider
- `--min-freq <n>`: minimum frequency threshold

### Examples

- More conservative term selection:
  - `python .codex/skills/survey-seed-harvest/scripts/run.py --workspace <ws> --top-k 80 --min-freq 3`

### Notes

- This helper is keyword-based; treat the output as *seeds* and refine with `taxonomy-builder`.

## Troubleshooting

### Issue: no survey/review papers are detected in the set

**Fix**:
- Broaden retrieval (add “survey”, “review”, “benchmark” variants) or manually seed a few known surveys, then rerun.

### Issue: taxonomy seeds look like generic buckets

**Fix**:
- Keep seeds concrete (named methods/benchmarks/tasks) and rely on `taxonomy-builder` to rewrite under the actual scope.
