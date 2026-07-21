---
name: idea-brainstorm
version: 4.1
profile: idea-brainstorm
routing_hints: [idea, ideation, brainstorm, 点子, 选题, 找方向, 找 idea]
routing_priority: 30
target_artifacts:
  - STATUS.md
  - UNITS.csv
  - CHECKPOINTS.md
  - DECISIONS.md
  - GOAL.md
  - PIPELINE.lock.md
  - queries.md
  - output/trace/IDEA_BRIEF.md
  - papers/papers_raw.jsonl
  - papers/papers_dedup.jsonl
  - papers/core_set.csv
  - papers/retrieval_report.md
  - outline/taxonomy.yml
  - papers/paper_notes.jsonl
  - papers/evidence_bank.jsonl
  - output/trace/IDEA_SIGNAL_TABLE.md
  - output/trace/IDEA_SIGNAL_TABLE.jsonl
  - output/trace/IDEA_DIRECTION_POOL.md
  - output/trace/IDEA_DIRECTION_POOL.jsonl
  - output/trace/IDEA_SCREENING_TABLE.md
  - output/trace/IDEA_SCREENING_TABLE.jsonl
  - output/trace/IDEA_SHORTLIST.md
  - output/trace/IDEA_SHORTLIST.jsonl
  - output/REPORT.md
  - output/APPENDIX.md
  - output/REPORT.json
  - output/IDEA_SCORECARD.md
  - output/IDEA_SCORECARD.json
  - output/DELIVERABLE_SELFLOOP_TODO.md
  - output/QUALITY_GATE.md
  - output/RUN_ERRORS.md
  - output/CONTRACT_REPORT.md
default_checkpoints: [C0,C1,C2,C3,C4,C5]
units_template: templates/UNITS.idea-brainstorm.csv
contract_model: pipeline.frontmatter/v1
query_defaults:
  draft_profile: idea_brainstorm
  max_results: 240
  core_size: 36
  evidence_mode: abstract
  direction_pool_min: 12
  direction_pool_max: 24
  idea_screen_top_n: 10
  idea_shortlist_size: 5
  report_top_n: 3
overridable_query_fields:
  - keywords
  - exclude
  - max_results
  - core_size
  - evidence_mode
  - direction_pool_min
  - direction_pool_max
  - idea_screen_top_n
  - idea_shortlist_size
  - report_top_n
  - time_window.from
  - time_window.to
quality_contract:
  completion_policy:
    required_checks: [idea-brief, literature-engineer, dedupe-rank, taxonomy-builder, paper-notes, idea-signal-mapper, idea-direction-generator, idea-screener, idea-shortlist-curator, idea-memo-writer, deliverable-selfloop, artifact-contract-auditor]
  retrieval_policy:
    minimum_records: 15
  candidate_pool_policy:
    core_size_min: 12
    core_size_max: 36
  memo_bundle:
    required_outputs: [output/REPORT.md, output/APPENDIX.md, output/REPORT.json]
  signal_policy:
    min_rows: 10
  direction_policy:
    shortlist_min: 3
    shortlist_max: 5
    keep_min: 3
    cluster_diversity_min: 2
    lead_diversity_target: 3
    lead_diversity_axes: [cluster, direction_type, program_kind]
  screening_policy:
    keep_rank_max: 7
    maybe_rank_max: 12
    score_weights:
      discussion_worthiness: 0.24
      academic_value: 0.22
      evidence_grounding: 0.18
      direction_distinctness: 0.16
      first_probe_clarity: 0.10
      thesis_potential: 0.10
  semantic_rubric:
    schema: idea-brainstorm-scorecard.v1
    pass_score: 80
    critical_dimensions: [deliverable_structure, evidence_traceability, direction_actionability]
loop_policy:
  stage_retry_budget:
    C1: 2
    C3: 1
    C4: 1
  max_reroutes: 4
  require_human_on_retry_after_approval: true
stages:
  C0:
    title: Init + idea brief
    mode: no_prose
    required_skills: [workspace-init, pipeline-router, idea-brief, human-checkpoint]
    optional_skills: []
    produces: [STATUS.md, UNITS.csv, CHECKPOINTS.md, DECISIONS.md, GOAL.md, PIPELINE.lock.md, queries.md, output/trace/IDEA_BRIEF.md, output/QUALITY_GATE.md, output/RUN_ERRORS.md]
    human_checkpoint:
      approve: brainstorm brief
      write_to: DECISIONS.md
  C1:
    title: Retrieval + core set
    mode: no_prose
    required_skills: [literature-engineer, dedupe-rank]
    optional_skills: []
    produces: [papers/papers_raw.jsonl, papers/papers_dedup.jsonl, papers/core_set.csv, papers/retrieval_report.md]
  C2:
    title: Idea landscape / focus
    mode: no_prose
    required_skills: [taxonomy-builder, checkpoint-brief, human-checkpoint]
    optional_skills: []
    produces: [outline/taxonomy.yml, DECISIONS.md]
    human_checkpoint:
      approve: focus clusters / lenses + exclusions
      write_to: DECISIONS.md
  C3:
    title: Evidence signals
    mode: no_prose
    required_skills: [paper-notes, idea-signal-mapper]
    optional_skills: []
    produces: [papers/paper_notes.jsonl, papers/evidence_bank.jsonl, output/trace/IDEA_SIGNAL_TABLE.md, output/trace/IDEA_SIGNAL_TABLE.jsonl]
  C4:
    title: Direction pool + screening
    mode: short_prose_ok
    required_skills: [idea-direction-generator, idea-screener]
    optional_skills: []
    produces: [output/trace/IDEA_DIRECTION_POOL.md, output/trace/IDEA_DIRECTION_POOL.jsonl, output/trace/IDEA_SCREENING_TABLE.md, output/trace/IDEA_SCREENING_TABLE.jsonl]
  C5:
    title: Shortlist + memo synthesis + evaluation
    mode: prose_allowed
    required_skills: [idea-shortlist-curator, idea-memo-writer, deliverable-selfloop, artifact-contract-auditor]
    optional_skills: []
    produces: [output/trace/IDEA_SHORTLIST.md, output/trace/IDEA_SHORTLIST.jsonl, output/REPORT.md, output/APPENDIX.md, output/REPORT.json, output/IDEA_SCORECARD.md, output/IDEA_SCORECARD.json, output/DELIVERABLE_SELFLOOP_TODO.md, output/CONTRACT_REPORT.md]
---

# Pipeline: Research Idea Brainstorm

Produce a literature-grounded, discussion-ready research-idea memo for a PI,
PhD researcher, or research team. This Workflow is for finding and comparing
promising directions; it is not a survey-writing path and does not pretend that
an early idea is already an execution-ready project plan.

The machine-readable contract above is canonical. This section explains the
research logic without duplicating stage metadata.

```text
scope the search
  -> retrieve a bounded literature set
  -> organize the idea landscape
  -> extract tensions and opportunities
  -> expand and screen directions
  -> deliver a traceable shortlist and memo
```

Two human decisions keep the Run aligned. C0 approves the research brief before
retrieval. C2 reviews the evidence-informed landscape and selects focus lenses
before direction generation. `checkpoint-brief` prepares the C2 review surface;
`human-checkpoint` alone records approval.

The reader opens `output/REPORT.md`. `output/APPENDIX.md` and
`output/REPORT.json` provide supporting detail and a machine-readable view.
Trace Artifacts under `output/trace/` preserve the chain from core papers to
signals, directions, screening decisions, and the final shortlist.

Completion requires more than file existence. The Workflow-declared checks run
at the shared Completion boundary, including retrieval coverage, taxonomy and
trace integrity, shortlist diversity, scorecard acceptance, and final Artifact
coverage. The scorecard establishes contract observability and repair
localization; it does not establish scientific novelty or replace expert
judgment.
