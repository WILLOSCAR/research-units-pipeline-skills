---
name: research-brief
version: 1.0
profile: research-brief
routing_hints: [research brief, rapid review, topic overview, briefing, newcomer memo, snapshot, literature snapshot, 速览, 快速理解, 研究速览]
routing_priority: 32
routing_default: false
target_artifacts:
  - STATUS.md
  - UNITS.csv
  - CHECKPOINTS.md
  - DECISIONS.md
  - GOAL.md
  - PIPELINE.lock.md
  - queries.md
  - papers/papers_raw.jsonl
  - papers/papers_dedup.jsonl
  - papers/core_set.csv
  - outline/taxonomy.yml
  - outline/outline.yml
  - output/SNAPSHOT.md
  - output/BRIEF_SCORECARD.md
  - output/BRIEF_SCORECARD.json
  - output/DELIVERABLE_SELFLOOP_TODO.md
  - output/QUALITY_GATE.md
  - output/RUN_ERRORS.md
  - output/CONTRACT_REPORT.md
default_checkpoints: [C0,C1,C2,C3]
units_template: templates/UNITS.research-brief.csv
contract_model: pipeline.frontmatter/v1
query_defaults:
  max_results: 80
  core_size: 12
  brief_style: newcomer_memo
overridable_query_fields:
  - keywords
  - exclude
  - max_results
  - core_size
  - brief_style
  - time_window.from
  - time_window.to
quality_contract:
  deliverable_kind: brief
  evidence_mode: light
  candidate_pool_policy:
    keep_full_deduped_pool: false
  brief_policy:
    primary_deliverable: output/SNAPSHOT.md
    style: bullets_first
    target_length: one_page
    pointer_density: explicit
  semantic_rubric:
    schema: research-brief-scorecard.v1
    pass_score: 80
    critical_dimensions: [deliverable_structure, brief_specificity, source_traceability]
stages:
  C0:
    title: Init
    checkpoint: C0
    mode: no_prose
    required_skills: [workspace-init, pipeline-router]
    optional_skills: []
    produces: [STATUS.md, UNITS.csv, CHECKPOINTS.md, DECISIONS.md, GOAL.md, PIPELINE.lock.md, queries.md, output/QUALITY_GATE.md, output/RUN_ERRORS.md]
  C1:
    title: Retrieval & core set
    checkpoint: C1
    mode: no_prose
    required_skills: [arxiv-search, dedupe-rank]
    optional_skills: [keyword-expansion]
    produces: [papers/papers_raw.jsonl, papers/papers_dedup.jsonl, papers/core_set.csv]
  C2:
    title: Structure
    checkpoint: C2
    mode: no_prose
    required_skills: [taxonomy-builder, outline-builder, pipeline-router]
    optional_skills: [outline-budgeter]
    produces: [outline/taxonomy.yml, outline/outline.yml, DECISIONS.md]
    human_checkpoint:
      approve: scope + outline
      write_to: DECISIONS.md
  C3:
    title: Brief delivery
    checkpoint: C3
    mode: short_prose_ok
    required_skills: [snapshot-writer, deliverable-selfloop, artifact-contract-auditor]
    optional_skills: [prose-writer]
    produces: [output/SNAPSHOT.md, output/BRIEF_SCORECARD.md, output/BRIEF_SCORECARD.json, output/DELIVERABLE_SELFLOOP_TODO.md, output/CONTRACT_REPORT.md]
---

# Pipeline: research-brief

Goal: produce a compact, high-signal research briefing that helps a reader understand a topic boundary, key themes, and a useful reading path in 24-48 hours.
