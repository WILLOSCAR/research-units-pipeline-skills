---
name: lit-snapshot
version: 2.2
target_artifacts:
  - STATUS.md
  - UNITS.csv
  - CHECKPOINTS.md
  - DECISIONS.md
  - GOAL.md
  - queries.md
  - papers/papers_raw.jsonl
  - papers/papers_dedup.jsonl
  - papers/core_set.csv
  - outline/taxonomy.yml
  - outline/outline.yml
  - output/SNAPSHOT.md
  - output/QUALITY_GATE.md
  - output/RUN_ERRORS.md
  - output/CONTRACT_REPORT.md
default_checkpoints: [C0,C1,C2,C3]
units_template: templates/UNITS.lit-snapshot.csv
---

# Pipeline: literature snapshot (24-48h) [bullets-first]

Goal: a compact, reader-facing snapshot (`output/SNAPSHOT.md`) with a small but usable paper set and a paper-like structure. This is intentionally lighter than `arxiv-survey*` (no evidence packs, no BibTeX, no LaTeX).

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

## Stage 1 - Retrieval & core set (C1)
required_skills:
- arxiv-search
- dedupe-rank
optional_skills:
- keyword-expansion
produces:
- papers/papers_raw.jsonl
- papers/papers_dedup.jsonl
- papers/core_set.csv

Notes:
- Snapshot default: aim for a smaller but diverse set (e.g., core_set ~20-40) rather than a survey-scale pool.
- If the snapshot feels generic, the fix is almost always upstream: broaden `queries.md` (more synonyms, fewer excludes, wider time window) and rerun C1.

## Stage 2 - Structure (C2) [NO PROSE]
required_skills:
- taxonomy-builder
- outline-builder
optional_skills:
- outline-budgeter
produces:
- outline/taxonomy.yml
- outline/outline.yml
human_checkpoint:
- approve: scope + outline (snapshot ToC)
- write_to: DECISIONS.md

Notes:
- Paper-like default: prefer fewer, thicker sections. For snapshots, avoid H3 explosion; treat H2 as the main organizing unit.
- If the outline is over-fragmented, use `outline-budgeter` (NO PROSE) to merge adjacent nodes and keep the ToC readable before writing.

## Stage 3 - Snapshot (C3) [SHORT PROSE OK]
required_skills:
- snapshot-writer
- artifact-contract-auditor
optional_skills:
- prose-writer
produces:
- output/SNAPSHOT.md
- output/CONTRACT_REPORT.md

Notes:
- The deliverable is bullets-first and pointer-heavy: every non-trivial claim should attach 1-2 concrete paper pointers from `papers/core_set.csv`.
- Avoid outline narration (e.g., `This section surveys ...`); write content claims + why-it-matters + pointers.
