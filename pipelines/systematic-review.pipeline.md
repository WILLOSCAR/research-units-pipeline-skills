---
name: systematic-review
version: 1.0
target_artifacts:
  - output/PROTOCOL.md
  - papers/screening_log.csv
  - papers/extraction_table.csv
  - output/SYNTHESIS.md
default_checkpoints: [C0,C1,C2,C3,C4]
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

## Stage 2 - Screening (C2)
required_skills:
- screening-manager
produces:
- papers/screening_log.csv

## Stage 3 - Extraction (C3)
required_skills:
- extraction-form
- bias-assessor
produces:
- papers/extraction_table.csv

## Stage 4 - Synthesis (C4) [PROSE ALLOWED]
required_skills:
- synthesis-writer
produces:
- output/SYNTHESIS.md
