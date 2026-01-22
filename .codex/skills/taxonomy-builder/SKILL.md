---
name: taxonomy-builder
description: |
  Build a 2+ level taxonomy (`outline/taxonomy.yml`) from a core paper set and scope constraints, with short descriptions per node.
  **Trigger**: taxonomy, taxonomy builder, 分类, 主题树, taxonomy.yml.
  **Use when**: survey/snapshot 的结构阶段（NO PROSE），已有 `papers/core_set.csv`，需要生成可映射且读者友好的主题结构。
  **Skip if**: 已经有批准过且可映射的 taxonomy（不要无意义重构）。
  **Network**: none.
  **Guardrail**: 避免泛化占位桶；保持 2+ 层且每节点有具体描述。
---

# Taxonomy Builder

Turn a core paper set into a **2+ level, mappable taxonomy** that will drive the outline and paper-to-section mapping.

This is *structure*, not writing: avoid prose paragraphs and avoid “generic placeholder” buckets.

## Role cards (prompt-level guidance)

- **Taxonomy Architect**
  - Mission: create a taxonomy that reads like a survey’s core chapters (few, thick buckets).
  - Do: choose 3–4 top-level chapters by reader questions and decision-relevant axes.
  - Avoid: keyword-only clusters, “Misc/Other”, and too many top-level buckets that would bloat the final ToC.

- **Mapping Sponsor**
  - Mission: keep the taxonomy mappable to real papers.
  - Do: ensure each leaf can plausibly map to multiple papers (ideally ≥3); keep node names discriminative.
  - Avoid: overlapping buckets whose boundaries are not explainable.

- **Scope Guardian**
  - Mission: encode what counts as in-scope at the taxonomy level.
  - Do: bake boundary cues into descriptions (what belongs here, what does not).
  - Avoid: relying on later prose to resolve scope drift.


## When to use

- You have a `papers/core_set.csv` and need a stable structure for a survey/snapshot.
- You want categories that are meaningful to readers (not just keyword clusters).

## When not to use

- You already have an approved taxonomy that maps well to your target narrative (don’t churn it).

## Inputs

- `papers/core_set.csv` (required)
- Optional: `papers/papers_dedup.jsonl` (to peek at abstracts/metadata)
- Optional: `DECISIONS.md` (scope constraints)

## Output

- `outline/taxonomy.yml`

## Workflow (heuristic)
Uses: `papers/papers_dedup.jsonl`, `DECISIONS.md`.


1. Skim the core set and cluster by **reader-relevant axes**, not by surface keywords.
   - For LLM agents, common axes: control loop/architecture, tool use, planning & reasoning, memory/RAG, multi-agent coordination, evaluation/benchmarks, safety/security, applications.
2. Choose top-level nodes that feel like “chapters in a survey”, and keep a **paper-like section budget**:
   - If you want a paper-like PDF with ~6–8 H2 sections total (see `ref/agent-surveys/STYLE_REPORT.md`), remember the pipeline also adds fixed H2 sections (Introduction / Related Work / Discussion / Conclusion).
   - In that case, aim for **~3–4 taxonomy-driven chapters** (top-level nodes), not 8–12 tiny buckets.
   - Deep surveys can go wider (e.g., 5–6 taxonomy chapters), but expect thinner writing unless you also expand evidence and writing budgets.
3. For each top-level node, create 2–6 subtopics with **clear inclusion cues** (what belongs here, what doesn’t).
4. Write a short description for every node:
   - define what the bucket covers
   - name 2–5 representative paper IDs (or recognizable lines of work) that belong here
5. Sanity check:
   - leaves aren’t too tiny (ideally ≥3 papers per leaf)
   - names are mutually exclusive *enough* (some overlap is OK, confusion is not)

## Quality checklist

- [ ] `outline/taxonomy.yml` has ≥2 levels.
- [ ] Every node has a `description` with concrete meaning (not “Papers and ideas centered on …” boilerplate).
- [ ] Leaf nodes look mappable (not overly broad like “Misc/Other”).
- [ ] Top-level nodes feel like chapters (avoid too many tiny buckets if you target a paper-like 6–8 H2 structure).

## Common failure modes (and fixes)

- **Generic buckets** (“Overview/Benchmarks/Open Problems”) → rename to content-based subtopics.
- **Keyword clustering** → reframe as design/evaluation questions a reader would ask.
- **Too much overlap** → tighten inclusion cues; split a bucket by mechanism vs evaluation vs safety.
- **Too many top-level buckets** → merge into fewer, thicker chapters; push fine-grained points into subsection bullets/axes instead of new H2 sections.

## Helper script (optional)

### Quick Start

- `python .codex/skills/taxonomy-builder/scripts/run.py --help`
- `python .codex/skills/taxonomy-builder/scripts/run.py --workspace <workspace_dir>`

### All Options

- `--top-k <n>`: number of candidate terms to consider
- `--min-freq <n>`: minimum frequency threshold

### Examples

- Generate a baseline taxonomy (then optionally refine):
  - `python .codex/skills/taxonomy-builder/scripts/run.py --workspace <ws> --top-k 100 --min-freq 2`

### Notes

- The script generates a baseline 2-level taxonomy (topic-aware) and never overwrites non-placeholder work.
- In `pipeline.py --strict` it will be blocked only if placeholder markers (TODO/TBD/FIXME/(placeholder)) remain.

### Refinement marker (recommended; completion signal)

When you are satisfied with the taxonomy (and after C2 approval if applicable), create:
- `outline/taxonomy.refined.ok`

This is an explicit "I reviewed/refined this" signal:
- makes it harder for a scaffold-y taxonomy to silently pass in strict runs
- documents that buckets were edited into reader-meaningful, mappable nodes

## Troubleshooting

### Common Issues

#### Issue: Quality gate blocks `taxonomy_scaffold`

**Symptom**:
- `output/QUALITY_GATE.md` reports taxonomy contains `TODO`/placeholder text.

**Causes**:
- Helper script generated a scaffold, but taxonomy was not rewritten.

**Solutions**:
- Rewrite every node name + description to be domain-meaningful.
- Ensure ≥2 levels via `children`.
- Remove generic buckets like “Overview/Benchmarks/Open Problems”.

#### Issue: Taxonomy has no depth (`children` missing)

**Symptom**:
- Quality gate reports “needs ≥2 levels”.

**Causes**:
- Only top-level nodes were created.

**Solutions**:
- Add 2–6 child nodes per top-level node, each with clear inclusion cues.

### Recovery Checklist

- [ ] `outline/taxonomy.yml` is valid YAML list.
- [ ] At least one node has a non-empty `children` list.
- [ ] No `TODO`/`(placeholder)` remains.
