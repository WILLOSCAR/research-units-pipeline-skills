---
name: arxiv-survey
version: 4.1
profile: arxiv-survey
routing_hints: [survey, 综述, 调研, literature review, course paper, term paper, course report, seminar report, topic report, short literature review, technical survey report, research landscape report, end-of-term report, 课程论文, 课程报告, 期末论文, 期末报告, 结课报告, 研讨课报告, 文献综述报告, 短文献综述, 专题报告, 专题调研报告, 技术调研报告, 技术综述报告]
routing_default: true
routing_priority: 10
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
  - papers/retrieval_report.md
  - outline/taxonomy.yml
  - outline/chapter_skeleton.yml
  - outline/section_bindings.jsonl
  - outline/section_binding_report.md
  - outline/section_briefs.jsonl
  - outline/outline.yml
  - outline/mapping.tsv
  - outline/coverage_report.md
  - outline/outline_state.jsonl
  - output/REROUTE_STATE.json
  - outline/subsection_briefs.jsonl
  - outline/chapter_briefs.jsonl
  - outline/transitions.md
  - papers/fulltext_index.jsonl
  - papers/paper_notes.jsonl
  - papers/evidence_bank.jsonl
  - outline/evidence_bindings.jsonl
  - outline/evidence_binding_report.md
  - outline/claim_evidence_matrix.md
  - outline/table_schema.md
  - outline/tables_index.md
  - outline/tables_appendix.md
  - output/TABLES_APPENDIX_REPORT.md
  - outline/evidence_drafts.jsonl
  - outline/anchor_sheet.jsonl
  - outline/writer_context_packs.jsonl
  - citations/ref.bib
  - citations/verified.jsonl
  - sections/sections_manifest.jsonl
  - sections/h3_bodies.refined.ok
  - sections/paragraphs_curated.refined.ok
  - sections/style_harmonized.refined.ok
  - sections/opener_varied.refined.ok
  - sections/abstract.md
  - sections/S1.md
  - sections/S2.md
  - output/FRONT_MATTER_CONTEXT.json
  - sections/discussion.md
  - sections/conclusion.md
  - output/QUALITY_GATE.md
  - output/RUN_ERRORS.md
  - output/SCHEMA_NORMALIZATION_REPORT.md
  - output/EVIDENCE_SELFLOOP_TODO.md
  - output/WRITER_SELFLOOP_TODO.md
  - output/EVAL_ANCHOR_REPORT.md
  - output/ARGUMENT_SELFLOOP_TODO.md
  - output/SECTION_ARGUMENT_SUMMARIES.jsonl
  - output/ARGUMENT_SKELETON.md
  - output/PARAGRAPH_CURATION_REPORT.md
  - output/FRONT_MATTER_REPORT.md
  - output/CHAPTER_LEADS_REPORT.md
  - output/SECTION_LOGIC_REPORT.md
  - output/GLOBAL_REVIEW.md
  - output/DRAFT.md
  - output/MERGE_REPORT.md
  - output/POST_MERGE_VOICE_REPORT.md
  - output/CITATION_BUDGET_REPORT.md
  - output/CITATION_INJECTION_REPORT.md
  - output/AUDIT_REPORT.md
  - output/TEMPLATE_RESIDUE_SCORECARD.json
  - output/CONTRACT_REPORT.md
default_checkpoints: [C0,C1,C2,C3,C4,C5]
units_template: templates/UNITS.arxiv-survey.csv
contract_model: pipeline.frontmatter/v1
structure_mode: section_first
pre_retrieval_shell:
  enabled: true
  approval_surface: false
  allowed_h2: [Introduction, Related Work, Core Chapters, Discussion, Conclusion]
binding_layers: [chapter_skeleton, section_bindings, section_briefs, subsection_mapping]
core_chapter_h3_target: 3
query_defaults:
  max_results: 1800
  core_size: 300
  per_subsection: 28
  global_citation_min_subsections: 4
  draft_profile: survey
  citation_target: recommended
  evidence_mode: abstract
overridable_query_fields:
  - keywords
  - exclude
  - max_results
  - core_size
  - per_subsection
  - global_citation_min_subsections
  - draft_profile
  - citation_target
  - enrich_metadata
  - evidence_mode
  - fulltext_max_papers
  - fulltext_max_pages
  - fulltext_min_chars
  - time_window.from
  - time_window.to
quality_contract:
  completion_policy:
    required_checks:
      - literature-engineer
      - dedupe-rank
      - chapter-skeleton
      - section-bindings
      - outline-refiner
      - taxonomy-builder
      - section-mapper
      - paper-notes
      - claim-matrix-rewriter
      - citation-verifier
      - evidence-binder
      - subsection-briefs
      - evidence-draft
      - evidence-selfloop
      - anchor-sheet
      - writer-context-pack
      - front-matter-writer
      - subsection-writer
      - writer-selfloop
      - evaluation-anchor-checker
      - section-logic-polisher
      - paragraph-curator
      - section-merger
      - citation-injector
      - draft-polisher
      - global-reviewer
      - argument-selfloop
      - pipeline-auditor
      - artifact-contract-auditor
  writing_policy:
    template_residue_max_ratio: 0.10
    template_literal_min_chars: 24
  citation_policy:
    unique_hard_floor: 150
    unique_recommended: 165
    by_profile:
      survey:
        unique_hard_floor: 150
        unique_recommended: 165
        global_budget_per_h3: 14
        base: 35
        bibliography_fraction: 0.50
        recommended_fraction: 0.55
      deep:
        unique_hard_floor: 165
        unique_recommended: 165
        global_budget_per_h3: 16
        base: 40
        bibliography_fraction: 0.60
        recommended_fraction: 0.60
      course_paper:
        unique_hard_floor: 24
        unique_recommended: 32
        global_budget_per_h3: 3
        base: 6
        bibliography_fraction: 0.35
        recommended_fraction: 0.45
  structure_policy:
    max_final_h2_by_profile:
      survey: 8
      deep: 9
      course_paper: 7
    max_h3_by_profile:
      survey: 10
      deep: 12
      course_paper: 6
  front_matter_policy:
    survey:
      introduction:
        min_cites: 35
        min_paras: 5
        min_chars: 2600
      related_work:
        min_cites: 50
        min_paras: 6
        min_chars: 3200
    deep:
      introduction:
        min_cites: 40
        min_paras: 6
        min_chars: 3000
      related_work:
        min_cites: 55
        min_paras: 7
        min_chars: 3600
    course_paper:
      introduction:
        min_cites: 6
        min_paras: 3
        min_chars: 1200
      related_work:
        min_cites: 8
        min_paras: 3
        min_chars: 1400
  subsection_policy:
    survey:
      min_unique_citations: 12
      min_chars: 4200
    deep:
      min_unique_citations: 14
      min_chars: 5200
    course_paper:
      min_unique_citations: 4
      min_chars: 1600
loop_policy:
  stage_retry_budget:
    C1: 2
    C2: 2
    C3: 1
    C4: 1
  max_reroutes: 4
  require_human_on_retry_after_approval: true
stages:
  C0:
    title: Init
    mode: no_prose
    required_skills: [workspace-init, pipeline-router]
    optional_skills: []
    produces: [STATUS.md, UNITS.csv, CHECKPOINTS.md, DECISIONS.md, GOAL.md, PIPELINE.lock.md, queries.md, output/QUALITY_GATE.md, output/RUN_ERRORS.md]
  C1:
    title: Retrieval & core set
    mode: no_prose
    required_skills: [literature-engineer, dedupe-rank]
    optional_skills: [keyword-expansion, survey-seed-harvest]
    produces: [papers/papers_raw.jsonl, papers/retrieval_report.md, papers/papers_dedup.jsonl, papers/core_set.csv]
  C2:
    title: Structure
    mode: no_prose
    required_skills: [taxonomy-builder, chapter-skeleton, section-bindings, section-briefs, outline-builder, section-mapper, outline-refiner, checkpoint-brief, human-checkpoint]
    optional_skills: [outline-budgeter]
    produces: [outline/taxonomy.yml, outline/chapter_skeleton.yml, outline/section_bindings.jsonl, outline/section_binding_report.md, outline/section_briefs.jsonl, outline/outline.yml, outline/mapping.tsv, outline/coverage_report.md, outline/outline_state.jsonl, output/REROUTE_STATE.json, DECISIONS.md]
    human_checkpoint:
      approve: scope + section skeleton + outline
      write_to: DECISIONS.md
  C3:
    title: Evidence
    mode: no_prose
    required_skills: [pdf-text-extractor, paper-notes, subsection-briefs, chapter-briefs]
    optional_skills: []
    produces: [papers/fulltext_index.jsonl, papers/paper_notes.jsonl, papers/evidence_bank.jsonl, outline/subsection_briefs.jsonl, outline/chapter_briefs.jsonl]
  C4:
    title: Citations + evidence packs
    mode: no_prose
    required_skills: [citation-verifier, evidence-binder, evidence-draft, table-schema, anchor-sheet, table-filler, appendix-table-writer, schema-normalizer, writer-context-pack, evidence-selfloop, claim-matrix-rewriter]
    optional_skills: [survey-visuals]
    produces: [citations/ref.bib, citations/verified.jsonl, outline/evidence_bindings.jsonl, outline/evidence_binding_report.md, outline/table_schema.md, outline/tables_index.md, outline/tables_appendix.md, output/TABLES_APPENDIX_REPORT.md, outline/evidence_drafts.jsonl, outline/anchor_sheet.jsonl, output/SCHEMA_NORMALIZATION_REPORT.md, outline/writer_context_packs.jsonl, output/EVIDENCE_SELFLOOP_TODO.md, outline/claim_evidence_matrix.md]
  C5:
    title: Draft
    mode: prose_allowed
    required_skills: [front-matter-writer, chapter-lead-writer, subsection-writer, writer-selfloop, style-harmonizer, opener-variator, section-logic-polisher, paragraph-curator, evaluation-anchor-checker, argument-selfloop, transition-weaver, section-merger, post-merge-voice-gate, citation-diversifier, citation-injector, draft-polisher, global-reviewer, pipeline-auditor, artifact-contract-auditor]
    optional_skills: [prose-writer, subsection-polisher, redundancy-pruner, terminology-normalizer, limitation-weaver, latex-scaffold, latex-compile-qa]
    produces: [outline/transitions.md, sections/sections_manifest.jsonl, sections/h3_bodies.refined.ok, sections/paragraphs_curated.refined.ok, sections/style_harmonized.refined.ok, sections/opener_varied.refined.ok, sections/abstract.md, sections/S1.md, sections/S2.md, sections/discussion.md, sections/conclusion.md, output/WRITER_SELFLOOP_TODO.md, output/EVAL_ANCHOR_REPORT.md, output/ARGUMENT_SELFLOOP_TODO.md, output/SECTION_ARGUMENT_SUMMARIES.jsonl, output/ARGUMENT_SKELETON.md, output/PARAGRAPH_CURATION_REPORT.md, output/FRONT_MATTER_REPORT.md, output/FRONT_MATTER_CONTEXT.json, output/CHAPTER_LEADS_REPORT.md, output/SECTION_LOGIC_REPORT.md, output/MERGE_REPORT.md, output/DRAFT.md, output/POST_MERGE_VOICE_REPORT.md, output/CITATION_BUDGET_REPORT.md, output/CITATION_INJECTION_REPORT.md, output/GLOBAL_REVIEW.md, output/AUDIT_REPORT.md, output/TEMPLATE_RESIDUE_SCORECARD.json, output/CONTRACT_REPORT.md]
---

# Pipeline: Survey And Research Report

Turn a topic into a literature-grounded long-form deliverable. The same
research lifecycle supports a field survey, a focused technical report, or a
bounded course or seminar paper; delivery profiles vary density without
creating parallel Workflows.

The YAML frontmatter and matching `templates/UNITS.arxiv-survey*.csv` are
canonical. This narrative explains why the stages exist without copying their
Skill, Artifact, threshold, or dependency lists.

```text
scope -> retrieve -> structure -> bind evidence -> draft -> audit
```

The default `survey` profile favors broad coverage. Explicit bounded-report
intent selects the compact `course_paper` compatibility profile. `deep` raises
evidence and writing density. `evidence_mode` independently selects abstract-
or full-text-backed evidence, so document length and evidence strength are not
conflated.

## Stage 0 - Init (C0)

C0 materializes the Workspace, locks the Workflow contract, records the Goal,
and asks for approval before retrieval commits the Run to a scope.

## Stage 1 - Retrieval & core set (C1)

Retrieval expands the approved query plan, preserves source provenance, removes
duplicates, and selects a stable core set. Coverage limits come from the active
delivery profile. A weak pool is repaired here instead of being hidden by later
writing.

## Stage 2 - Structure (C2) [NO PROSE]

Structure is derived from the retrieved corpus, not from a generic table of
contents. Chapter saturation is checked before stable subsection IDs are
created. Each subsection becomes a research question plus an evidence need;
C2 then pauses for a human to approve the argument shape before prose exists.

## Stage 3 - Evidence (C3) [NO PROSE]

Evidence Units convert papers into notes, comparison anchors, and verifiable
writing briefs. Full text is optional and more expensive; the active contract
records the evidence mode so a reader can distinguish abstract-backed claims
from deeper paper-level interpretation.

## Stage 4 - Citations + evidence packs (C4) [NO PROSE]

This stage binds each planned section to allowed citations, evidence cards,
numeric or methodological anchors, and table material. Per-section context packs
keep drafting bounded and make a failed paragraph traceable to its upstream
evidence instead of forcing the writer to reload the whole corpus.

## Stage 5 - Draft (C5) [PROSE AFTER C2]

Drafting happens section by section from bounded context packs, then converges
through targeted checks before merge. The system distinguishes three repair
classes:

- writing defects return to the owning section Skill;
- thin or out-of-scope evidence returns to C3 or C4 instead of being padded with
  prose;
- structural defects reopen C2 and require renewed human approval.

The final argument snapshot fingerprints what will be merged. Post-merge checks
inspect the actual deliverable for citation scope, paragraph logic, unsupported
numeric claims, template leakage, voice consistency, and profile-specific
density. Tables are reader-facing Artifacts; planning indexes and optional
visual specifications remain internal unless the contract explicitly promotes
them.

The deterministic writer scripts may create provisional bootstrap prose, but
the CODEX-owned writing Units are responsible for rewriting it before
acceptance. Front matter now receives the same residue check at its owning Unit
boundary, so an unedited bootstrap cannot commit and flow silently into merge.
The final auditor measures the entire draft against the
writer-template assets selected for that Run (four fixed banks plus an optional
front-matter domain overlay), verifies the recorded asset hashes and their
owning Skill implementations against the v2 Run lock, and emits
`output/TEMPLATE_RESIDUE_SCORECARD.json`. The 10% limit remains an initial policy
target. A passing scorecard establishes attainability only for the Artifact set
and immutable contract recorded by that Run; clean from-scratch reproduction
and cross-topic calibration require separate evidence.

The Workflow-declared completion checks are mandatory in normal execution.
`--strict` adds registered diagnostic checks that are not already part of the
mandatory contract. Neither mode upgrades a structural PASS into a claim of
scientific correctness; expert review remains a separate quality layer.

Use `arxiv-survey-latex` when LaTeX and PDF are required. That Workflow inherits
this research lifecycle and adds delivery compilation and PDF quality checks.
