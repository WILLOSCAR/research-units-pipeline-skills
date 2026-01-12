---
name: tutorial
version: 1.0
target_artifacts:
  - output/TUTORIAL_SPEC.md
  - outline/concept_graph.yml
  - outline/module_plan.yml
  - output/TUTORIAL.md
default_checkpoints: [C0,C1,C2,C3]
units_template: templates/UNITS.tutorial.csv
---

# Pipeline: tutorial (teaching loop)

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

## Stage 3 - Writing (C3) [PROSE ALLOWED]
required_skills:
- tutorial-module-writer
produces:
- output/TUTORIAL.md
