---
name: systematic-review
version: 2.2
target_artifacts:
  - STATUS.md
  - UNITS.csv
  - CHECKPOINTS.md
  - DECISIONS.md
  - GOAL.md
  - queries.md
  - output/PROTOCOL.md
  - papers/papers_raw.jsonl
  - papers/retrieval_report.md
  - papers/papers_dedup.jsonl
  - papers/core_set.csv
  - papers/screening_log.csv
  - papers/extraction_table.csv
  - output/SYNTHESIS.md
  - output/QUALITY_GATE.md
  - output/RUN_ERRORS.md
  - output/CONTRACT_REPORT.md
default_checkpoints: [C0,C1,C2,C3,C4,C5]
units_template: templates/UNITS.systematic-review.csv
---

# Pipeline: systematic review (PRISMA-style)

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

## Stage 1 - Protocol (C1)
required_skills:
- protocol-writer
produces:
- output/PROTOCOL.md
human_checkpoint:
- approve: protocol locked (query, inclusion/exclusion, databases, time window)
- write_to: DECISIONS.md

## Stage 2 - Retrieval & candidate pool (C2)
required_skills:
- literature-engineer
- dedupe-rank
optional_skills:
- keyword-expansion
- arxiv-search
produces:
- papers/papers_raw.jsonl
- papers/retrieval_report.md
- papers/papers_dedup.jsonl
- papers/core_set.csv

Notes:
- Systematic-review contract: keep the candidate pool auditable. Prefer dedupe (good) over aggressive ranking/filtering (dangerous).
- `dedupe-rank` default: for this pipeline, it keeps the full deduped pool in `papers/core_set.csv` unless you explicitly set `queries.md:core_size` (screening should not silently drop papers).

## Stage 3 - Screening (C3)
required_skills:
- screening-manager
produces:
- papers/screening_log.csv

Notes:
- Use `papers/papers_dedup.jsonl` (or `papers/core_set.csv`) as the candidate list; `papers/screening_log.csv` must include protocol-grounded reasons for every decision.

## Stage 4 - Extraction (C4)
required_skills:
- extraction-form
- bias-assessor
produces:
- papers/extraction_table.csv

Notes:
- Extraction is schema-driven: do not write narrative synthesis here; keep all fields consistent and fill bias fields (low/unclear/high + notes).

## Stage 5 - Synthesis (C5) [PROSE ALLOWED]
required_skills:
- synthesis-writer
- artifact-contract-auditor
produces:
- output/SYNTHESIS.md
- output/CONTRACT_REPORT.md
