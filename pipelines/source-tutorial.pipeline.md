---
name: source-tutorial
version: 1.3
profile: source-tutorial
routing_hints: [source tutorial, tutorial, 教程, 教学, lesson, course notes]
routing_priority: 35
target_artifacts:
  - STATUS.md
  - UNITS.csv
  - CHECKPOINTS.md
  - DECISIONS.md
  - GOAL.md
  - PIPELINE.lock.md
  - queries.md
  - sources/manifest.yml
  - sources/index.jsonl
  - sources/provenance.jsonl
  - output/TUTORIAL_SPEC.md
  - outline/concept_graph.yml
  - outline/module_plan.yml
  - outline/source_coverage.jsonl
  - outline/tutorial_context_packs.jsonl
  - output/TUTORIAL.md
  - output/TUTORIAL_SELFLOOP_TODO.md
  - latex/main.tex
  - latex/main.pdf
  - output/LATEX_BUILD_REPORT.md
  - latex/slides/main.tex
  - latex/slides/main.pdf
  - output/SLIDES_BUILD_REPORT.md
  - output/QUALITY_GATE.md
  - output/RUN_ERRORS.md
  - output/CONTRACT_REPORT.md
default_checkpoints: [C0,C1,C2,C3,C4]
units_template: templates/UNITS.source-tutorial.csv
contract_model: pipeline.frontmatter/v1
quality_contract:
  completion_policy:
    required_checks: [source-manifest, source-ingest, source-tutorial-spec, module-source-coverage, tutorial-context-pack, tutorial-selfloop, latex-scaffold, latex-compile-qa, beamer-scaffold, beamer-compile-qa, artifact-contract-auditor]
  tutorial_policy:
    tutorial_form: article_first
    source_grounding: provenance_bound
    running_example_policy: optional_if_supported
  source_policy:
    accepted_source_kinds: [webpage, pdf, markdown, repo, docs_site, video]
    repo_depth: readme_docs_first
  delivery_policy:
    article_pdf_required: true
    slides_pdf_required: true
stages:
  C0:
    title: Init
    mode: no_prose
    required_skills: [workspace-init, pipeline-router]
    optional_skills: []
    produces: [STATUS.md, UNITS.csv, CHECKPOINTS.md, DECISIONS.md, GOAL.md, PIPELINE.lock.md, queries.md, output/QUALITY_GATE.md, output/RUN_ERRORS.md]
  C1:
    title: Source intake
    mode: no_prose
    required_skills: [source-manifest, source-ingest]
    optional_skills: []
    produces: [sources/manifest.yml, sources/index.jsonl, sources/provenance.jsonl]
  C2:
    title: Pedagogical structure
    mode: no_prose
    required_skills: [source-tutorial-spec, concept-graph, module-planner, exercise-builder, module-source-coverage, tutorial-context-pack, checkpoint-brief, human-checkpoint]
    optional_skills: []
    produces: [output/TUTORIAL_SPEC.md, outline/concept_graph.yml, outline/module_plan.yml, outline/source_coverage.jsonl, outline/tutorial_context_packs.jsonl, DECISIONS.md]
    human_checkpoint:
      approve: source scope + learner profile + tutorial structure
      write_to: DECISIONS.md
  C3:
    title: Tutorial writing
    mode: prose_allowed
    required_skills: [source-tutorial-writer, tutorial-selfloop]
    optional_skills: []
    produces: [output/TUTORIAL.md, output/TUTORIAL_SELFLOOP_TODO.md]
  C4:
    title: Delivery
    mode: prose_allowed
    required_skills: [latex-scaffold, latex-compile-qa, beamer-scaffold, beamer-compile-qa, artifact-contract-auditor]
    optional_skills: []
    produces: [latex/main.tex, latex/main.pdf, output/LATEX_BUILD_REPORT.md, latex/slides/main.tex, latex/slides/main.pdf, output/SLIDES_BUILD_REPORT.md, output/CONTRACT_REPORT.md]
---

# Pipeline: source-tutorial

Goal: transform mixed source materials into a reader-first tutorial that is easier to read, easier to learn from, and easier to teach from, then derive article PDF and Beamer slides from the same teaching structure.
