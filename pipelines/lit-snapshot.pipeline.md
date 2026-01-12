---
name: lit-snapshot
version: 1.0
target_artifacts:
  - papers/core_set.csv
  - outline/taxonomy.yml
  - outline/outline.yml
  - output/SNAPSHOT.md
default_checkpoints: [C0,C1,C2]
units_template: templates/UNITS.lit-snapshot.csv
---

# Pipeline: literature snapshot (48h) [bullets-first]

## Stage 0 - Init (C0)
required_skills:
- workspace-init
- pipeline-router
produces:
- STATUS.md
- UNITS.csv
- CHECKPOINTS.md
- DECISIONS.md
- GOAL.md
- queries.md

## Stage 1 - Retrieval (C1)
required_skills:
- arxiv-search
- dedupe-rank
optional_skills:
- keyword-expansion
produces:
- papers/papers_raw.jsonl
- papers/papers_dedup.jsonl
- papers/core_set.csv

## Stage 2 - Structure + snapshot (C2) [NO LONG PROSE]
required_skills:
- taxonomy-builder
- outline-builder
- prose-writer
produces:
- outline/taxonomy.yml
- outline/outline.yml
- output/SNAPSHOT.md
