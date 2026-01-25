---
name: peer-review
version: 2.2
target_artifacts:
  - STATUS.md
  - UNITS.csv
  - CHECKPOINTS.md
  - DECISIONS.md
  - GOAL.md
  - queries.md
  - output/CLAIMS.md
  - output/MISSING_EVIDENCE.md
  - output/NOVELTY_MATRIX.md
  - output/REVIEW.md
  - output/QUALITY_GATE.md
  - output/RUN_ERRORS.md
  - output/CONTRACT_REPORT.md
default_checkpoints: [C0,C1,C2,C3]
units_template: templates/UNITS.peer-review.csv
---

# Pipeline: peer review / referee report

Goal: produce an actionable referee report (`output/REVIEW.md`) that is traceable to the submitted paper’s claims and evidence (no free-floating advice, no invented comparisons).

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

Notes:
- Input expectation: you must have the manuscript text available as `output/PAPER.md` (or equivalent extracted text) before running this stage.
- Contract: every claim must include a source pointer (section/page/quote) so later critique is auditable.

## Stage 2 - Evidence audit (C2)
required_skills:
- evidence-auditor
- novelty-matrix
produces:
- output/MISSING_EVIDENCE.md
- output/NOVELTY_MATRIX.md

Notes:
- Evidence-auditor should write gaps/risks/verification steps, not “fix the paper”.
- Novelty-matrix should be conservative: compare against cited/known related work; if you lack sources, record that limitation explicitly.

## Stage 3 - Rubric write-up (C3)
required_skills:
- rubric-writer
- artifact-contract-auditor
produces:
- output/REVIEW.md
- output/CONTRACT_REPORT.md

Notes:
- Prefer concrete, minimal fixes (what experiment/ablation/analysis would resolve the concern) over generic “needs more experiments”.
