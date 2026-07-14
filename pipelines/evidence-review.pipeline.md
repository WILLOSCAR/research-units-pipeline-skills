---
name: evidence-review
version: 1.2
profile: evidence-review
routing_hints: [evidence review, evidence synthesis, systematic review, prisma, 系统综述, 证据综述]
routing_priority: 34
routing_default: false
target_artifacts:
  - STATUS.md
  - UNITS.csv
  - CHECKPOINTS.md
  - DECISIONS.md
  - GOAL.md
  - PIPELINE.lock.md
  - queries.md
  - output/PROTOCOL.md
  - papers/papers_raw.jsonl
  - papers/retrieval_report.md
  - papers/papers_dedup.jsonl
  - papers/core_set.csv
  - papers/screening_log.csv
  - papers/extraction_table.csv
  - output/SYNTHESIS.md
  - output/EVIDENCE_SCORECARD.md
  - output/EVIDENCE_SCORECARD.json
  - output/DELIVERABLE_SELFLOOP_TODO.md
  - output/QUALITY_GATE.md
  - output/RUN_ERRORS.md
  - output/CONTRACT_REPORT.md
default_checkpoints: [C0,C1,C2,C3,C4,C5]
units_template: templates/UNITS.evidence-review.csv
contract_model: pipeline.frontmatter/v1
overridable_query_fields:
  - keywords
  - exclude
  - time_window.from
  - time_window.to
quality_contract:
  deliverable_kind: evidence_review
  evidence_mode: protocol_driven
  candidate_pool_policy:
    keep_full_deduped_pool: true
  evidence_policy:
    primary_deliverable: output/SYNTHESIS.md
    rigor: systematic
    protocol_required: true
    screening_log_required: true
    extraction_table_required: true
  semantic_rubric:
    schema: evidence-review-scorecard.v1
    pass_score: 80
    critical_dimensions: [protocol_operability, screening_traceability, extraction_coverage, synthesis_traceability]
stages:
  C0:
    title: Init
    checkpoint: C0
    mode: no_prose
    required_skills: [workspace-init, pipeline-router]
    optional_skills: []
    produces: [STATUS.md, UNITS.csv, CHECKPOINTS.md, DECISIONS.md, GOAL.md, PIPELINE.lock.md, queries.md, output/QUALITY_GATE.md, output/RUN_ERRORS.md]
  C1:
    title: Protocol
    checkpoint: C1
    mode: no_prose
    required_skills: [protocol-writer, human-checkpoint]
    optional_skills: []
    produces: [output/PROTOCOL.md, DECISIONS.md]
    human_checkpoint:
      approve: protocol locked
      write_to: DECISIONS.md
  C2:
    title: Retrieval & candidate pool
    checkpoint: C2
    mode: no_prose
    required_skills: [literature-engineer, dedupe-rank]
    optional_skills: [keyword-expansion, arxiv-search]
    produces: [papers/papers_raw.jsonl, papers/retrieval_report.md, papers/papers_dedup.jsonl, papers/core_set.csv]
  C3:
    title: Screening
    checkpoint: C3
    mode: no_prose
    required_skills: [screening-manager]
    optional_skills: []
    produces: [papers/screening_log.csv]
  C4:
    title: Extraction
    checkpoint: C4
    mode: no_prose
    required_skills: [extraction-form, bias-assessor]
    optional_skills: []
    produces: [papers/extraction_table.csv]
  C5:
    title: Synthesis
    checkpoint: C5
    mode: prose_allowed
    required_skills: [synthesis-writer, deliverable-selfloop, artifact-contract-auditor]
    optional_skills: []
    produces: [output/SYNTHESIS.md, output/EVIDENCE_SCORECARD.md, output/EVIDENCE_SCORECARD.json, output/DELIVERABLE_SELFLOOP_TODO.md, output/CONTRACT_REPORT.md]
---

# Pipeline: evidence-review

Goal: produce an auditable evidence synthesis from a defined review question, with protocol, screening, extraction, and bounded narrative conclusions.
