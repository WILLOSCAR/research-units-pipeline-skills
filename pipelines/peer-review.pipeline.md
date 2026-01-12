---
name: peer-review
version: 1.0
target_artifacts:
  - output/CLAIMS.md
  - output/MISSING_EVIDENCE.md
  - output/NOVELTY_MATRIX.md
  - output/REVIEW.md
default_checkpoints: [C0,C1,C2,C3]
units_template: templates/UNITS.peer-review.csv
---

# Pipeline: peer review / referee report

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

## Stage 1 - Claims (C1)
required_skills:
- claims-extractor
produces:
- output/CLAIMS.md

## Stage 2 - Evidence audit (C2)
required_skills:
- evidence-auditor
- novelty-matrix
produces:
- output/MISSING_EVIDENCE.md
- output/NOVELTY_MATRIX.md

## Stage 3 - Rubric write-up (C3)
required_skills:
- rubric-writer
produces:
- output/REVIEW.md
