---
name: paper-review
version: 1.2
profile: paper-review
routing_hints: [paper review, manuscript review, paper critique, critique this paper, review this paper, review this manuscript, assess this paper, assess manuscript, referee report, peer review, 审稿, 论文评估, 评审这篇论文, 审阅这篇论文]
routing_priority: 33
routing_default: false
target_artifacts:
  - STATUS.md
  - UNITS.csv
  - CHECKPOINTS.md
  - DECISIONS.md
  - GOAL.md
  - PIPELINE.lock.md
  - queries.md
  - output/PAPER.md
  - output/CLAIMS.md
  - output/CLAIMS.jsonl
  - output/MISSING_EVIDENCE.md
  - output/EVIDENCE_AUDIT.jsonl
  - output/NOVELTY_MATRIX.md
  - output/NOVELTY_MATRIX.tsv
  - output/REVIEW.md
  - output/REVIEW_SCORECARD.md
  - output/REVIEW_SCORECARD.json
  - output/DELIVERABLE_SELFLOOP_TODO.md
  - output/QUALITY_GATE.md
  - output/RUN_ERRORS.md
  - output/CONTRACT_REPORT.md
default_checkpoints: [C0,C1,C2,C3]
units_template: templates/UNITS.paper-review.csv
contract_model: pipeline.frontmatter/v1
quality_contract:
  deliverable_kind: paper_review
  evidence_mode: manuscript_traceable
  completion_policy:
    required_checks: [deliverable-selfloop, artifact-contract-auditor]
  candidate_pool_policy:
    keep_full_deduped_pool: false
  review_policy:
    primary_deliverable: output/REVIEW.md
    traceability_required: true
    required_axes: [novelty, soundness, clarity, impact]
  semantic_rubric:
    schema: paper-review-scorecard.v1
    pass_score: 80
    critical_dimensions: [claim_traceability, evidence_coverage, review_traceability]
stages:
  C0:
    title: Init
    checkpoint: C0
    mode: no_prose
    required_skills: [workspace-init, pipeline-router]
    optional_skills: []
    produces: [STATUS.md, UNITS.csv, CHECKPOINTS.md, DECISIONS.md, GOAL.md, PIPELINE.lock.md, queries.md, output/QUALITY_GATE.md, output/RUN_ERRORS.md]
  C1:
    title: Manuscript ingest + claims
    checkpoint: C1
    mode: no_prose
    required_skills: [manuscript-ingest, claims-extractor]
    optional_skills: []
    produces: [output/PAPER.md, output/CLAIMS.md, output/CLAIMS.jsonl]
  C2:
    title: Evidence audit
    checkpoint: C2
    mode: no_prose
    required_skills: [evidence-auditor, novelty-matrix]
    optional_skills: []
    produces: [output/MISSING_EVIDENCE.md, output/EVIDENCE_AUDIT.jsonl, output/NOVELTY_MATRIX.md, output/NOVELTY_MATRIX.tsv]
  C3:
    title: Review write-up
    checkpoint: C3
    mode: prose_allowed
    required_skills: [rubric-writer, deliverable-selfloop, artifact-contract-auditor]
    optional_skills: []
    produces: [output/REVIEW.md, output/REVIEW_SCORECARD.md, output/REVIEW_SCORECARD.json, output/DELIVERABLE_SELFLOOP_TODO.md, output/CONTRACT_REPORT.md]
---

# Pipeline: paper-review

Goal: produce a traceable assessment of a single paper or manuscript, grounded in explicit claims, evidence gaps, novelty positioning, and a machine-readable review scorecard.
