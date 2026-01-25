---
name: tutorial
version: 2.2
target_artifacts:
  - STATUS.md
  - UNITS.csv
  - CHECKPOINTS.md
  - DECISIONS.md
  - GOAL.md
  - queries.md
  - output/TUTORIAL_SPEC.md
  - outline/concept_graph.yml
  - outline/module_plan.yml
  - output/TUTORIAL.md
  - output/QUALITY_GATE.md
  - output/RUN_ERRORS.md
  - output/CONTRACT_REPORT.md
default_checkpoints: [C0,C1,C2,C3]
units_template: templates/UNITS.tutorial.csv
---

# Pipeline: tutorial (teaching loop)

Goal: a tutorial deliverable (`output/TUTORIAL.md`) that has a consistent running example and a real teaching loop (objectives -> steps -> exercises -> verification), not just a blog-style explanation.

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

## Stage 1 - Spec (C1)
required_skills:
- tutorial-spec
produces:
- output/TUTORIAL_SPEC.md

Notes:
- The spec is the scope contract: audience, prerequisites, learning objectives, and a running example (if applicable).

## Stage 2 - Structure (C2) [NO PROSE]
required_skills:
- concept-graph
- module-planner
- exercise-builder
produces:
- outline/concept_graph.yml
- outline/module_plan.yml
human_checkpoint:
- approve: target audience + scope + running example
- write_to: DECISIONS.md

Notes:
- Treat `outline/module_plan.yml` as the execution contract for writing: modules must have concrete outputs and at least one verifiable exercise each.

## Stage 3 - Writing (C3) [PROSE ALLOWED]
required_skills:
- tutorial-module-writer
- artifact-contract-auditor
produces:
- output/TUTORIAL.md
- output/CONTRACT_REPORT.md

Notes:
- Write only within the approved scope; if you discover missing prerequisites, record them as a follow-up instead of expanding scope silently.
