# SKILL_DEPENDENCIES

- Regenerate: `python scripts/generate_skill_graph.py`

## Global skill ⇄ artifact graph (from SKILL.md Inputs/Outputs)

```mermaid
flowchart LR
  classDef skill fill:#e3f2fd,stroke:#1e88e5,color:#0d47a1;
  classDef file fill:#f1f8e9,stroke:#7cb342,color:#1b5e20;

  S_agent_survey_corpus["`agent-survey-corpus`"]:::skill
  F_ref_agent_surveys_arxiv_ids_txt["`ref/agent-surveys/arxiv_ids.txt`"]:::file
  F_ref_agent_surveys_arxiv_ids_txt --> S_agent_survey_corpus
  F_ref_agent_surveys_STYLE_REPORT_md["`ref/agent-surveys/STYLE_REPORT.md`"]:::file
  S_agent_survey_corpus --> F_ref_agent_surveys_STYLE_REPORT_md
  F_ref_agent_surveys_pdfs["`ref/agent-surveys/pdfs/`"]:::file
  S_agent_survey_corpus --> F_ref_agent_surveys_pdfs
  F_ref_agent_surveys_text["`ref/agent-surveys/text/`"]:::file
  S_agent_survey_corpus --> F_ref_agent_surveys_text
  S_anchor_sheet["`anchor-sheet`"]:::skill
  F_citations_ref_bib["`citations/ref.bib`"]:::file
  F_citations_ref_bib --> S_anchor_sheet
  F_outline_evidence_drafts_jsonl["`outline/evidence_drafts.jsonl`"]:::file
  F_outline_evidence_drafts_jsonl --> S_anchor_sheet
  F_outline_anchor_sheet_jsonl["`outline/anchor_sheet.jsonl`"]:::file
  S_anchor_sheet --> F_outline_anchor_sheet_jsonl
  S_appendix_table_writer["`appendix-table-writer`"]:::skill
  F_GOAL_md["`GOAL.md`"]:::file
  F_GOAL_md --> S_appendix_table_writer
  F_citations_ref_bib --> S_appendix_table_writer
  F_outline_anchor_sheet_jsonl --> S_appendix_table_writer
  F_outline_evidence_drafts_jsonl --> S_appendix_table_writer
  F_outline_subsection_briefs_jsonl["`outline/subsection_briefs.jsonl`"]:::file
  F_outline_subsection_briefs_jsonl --> S_appendix_table_writer
  F_outline_table_schema_md["`outline/table_schema.md`"]:::file
  F_outline_table_schema_md --> S_appendix_table_writer
  F_outline_tables_index_md["`outline/tables_index.md`"]:::file
  F_outline_tables_index_md --> S_appendix_table_writer
  F_outline_tables_appendix_md["`outline/tables_appendix.md`"]:::file
  S_appendix_table_writer --> F_outline_tables_appendix_md
  S_artifact_contract_auditor["`artifact-contract-auditor`"]:::skill
  F_PIPELINE_lock_md["`PIPELINE.lock.md`"]:::file
  F_PIPELINE_lock_md --> S_artifact_contract_auditor
  F_UNITS_csv["`UNITS.csv`"]:::file
  F_UNITS_csv --> S_artifact_contract_auditor
  F_pipelines_pipeline_md["`pipelines/*.pipeline.md`"]:::file
  F_pipelines_pipeline_md --> S_artifact_contract_auditor
  F_output_CONTRACT_REPORT_md["`output/CONTRACT_REPORT.md`"]:::file
  S_artifact_contract_auditor --> F_output_CONTRACT_REPORT_md
  S_arxiv_search["`arxiv-search`"]:::skill
  F_queries_md["`queries.md`"]:::file
  F_queries_md --> S_arxiv_search
  F_papers_papers_raw_csv["`papers/papers_raw.csv`"]:::file
  S_arxiv_search --> F_papers_papers_raw_csv
  F_papers_papers_raw_jsonl["`papers/papers_raw.jsonl`"]:::file
  S_arxiv_search --> F_papers_papers_raw_jsonl
  S_bias_assessor["`bias-assessor`"]:::skill
  F_papers_extraction_table_csv["`papers/extraction_table.csv`"]:::file
  F_papers_extraction_table_csv --> S_bias_assessor
  S_bias_assessor --> F_papers_extraction_table_csv
  S_chapter_briefs["`chapter-briefs`"]:::skill
  F_GOAL_md --> S_chapter_briefs
  F_outline_outline_yml["`outline/outline.yml`"]:::file
  F_outline_outline_yml --> S_chapter_briefs
  F_outline_subsection_briefs_jsonl --> S_chapter_briefs
  F_outline_chapter_briefs_jsonl["`outline/chapter_briefs.jsonl`"]:::file
  S_chapter_briefs --> F_outline_chapter_briefs_jsonl
  S_chapter_lead_writer["`chapter-lead-writer`"]:::skill
  F_citations_ref_bib --> S_chapter_lead_writer
  F_outline_chapter_briefs_jsonl --> S_chapter_lead_writer
  F_outline_outline_yml --> S_chapter_lead_writer
  F_outline_writer_context_packs_jsonl["`outline/writer_context_packs.jsonl`"]:::file
  F_outline_writer_context_packs_jsonl --> S_chapter_lead_writer
  F_sections_S_sec_id__lead_md["`sections/S<sec_id>_lead.md`"]:::file
  S_chapter_lead_writer --> F_sections_S_sec_id__lead_md
  S_citation_anchoring["`citation-anchoring`"]:::skill
  F_output_DRAFT_md["`output/DRAFT.md`"]:::file
  F_output_DRAFT_md --> S_citation_anchoring
  F_output_citation_anchors_prepolish_jsonl["`output/citation_anchors.prepolish.jsonl`"]:::file
  F_output_citation_anchors_prepolish_jsonl --> S_citation_anchoring
  F_output_CITATION_ANCHORING_REPORT_md["`output/CITATION_ANCHORING_REPORT.md`"]:::file
  S_citation_anchoring --> F_output_CITATION_ANCHORING_REPORT_md
  S_citation_diversifier["`citation-diversifier`"]:::skill
  F_citations_ref_bib --> S_citation_diversifier
  F_outline_outline_yml --> S_citation_diversifier
  F_outline_writer_context_packs_jsonl --> S_citation_diversifier
  F_output_DRAFT_md --> S_citation_diversifier
  F_output_CITATION_BUDGET_REPORT_md["`output/CITATION_BUDGET_REPORT.md`"]:::file
  S_citation_diversifier --> F_output_CITATION_BUDGET_REPORT_md
  S_citation_injector["`citation-injector`"]:::skill
  F_citations_ref_bib --> S_citation_injector
  F_outline_outline_yml --> S_citation_injector
  F_output_CITATION_BUDGET_REPORT_md --> S_citation_injector
  F_output_DRAFT_md --> S_citation_injector
  F_output_CITATION_INJECTION_REPORT_md["`output/CITATION_INJECTION_REPORT.md`"]:::file
  S_citation_injector --> F_output_CITATION_INJECTION_REPORT_md
  S_citation_injector --> F_output_DRAFT_md
  S_citation_verifier["`citation-verifier`"]:::skill
  F_papers_paper_notes_jsonl["`papers/paper_notes.jsonl`"]:::file
  F_papers_paper_notes_jsonl --> S_citation_verifier
  S_citation_verifier --> F_citations_ref_bib
  F_citations_verified_jsonl["`citations/verified.jsonl`"]:::file
  S_citation_verifier --> F_citations_verified_jsonl
  S_claim_evidence_matrix["`claim-evidence-matrix`"]:::skill
  F_outline_mapping_tsv["`outline/mapping.tsv`"]:::file
  F_outline_mapping_tsv --> S_claim_evidence_matrix
  F_outline_outline_yml --> S_claim_evidence_matrix
  F_papers_paper_notes_jsonl --> S_claim_evidence_matrix
  F_outline_claim_evidence_matrix_md["`outline/claim_evidence_matrix.md`"]:::file
  S_claim_evidence_matrix --> F_outline_claim_evidence_matrix_md
  S_claim_matrix_rewriter["`claim-matrix-rewriter`"]:::skill
  F_citations_ref_bib --> S_claim_matrix_rewriter
  F_outline_evidence_drafts_jsonl --> S_claim_matrix_rewriter
  F_outline_subsection_briefs_jsonl --> S_claim_matrix_rewriter
  S_claim_matrix_rewriter --> F_outline_claim_evidence_matrix_md
  S_claims_extractor["`claims-extractor`"]:::skill
  F_DECISIONS_md["`DECISIONS.md`"]:::file
  F_DECISIONS_md --> S_claims_extractor
  F_output_PAPER_md["`output/PAPER.md`"]:::file
  F_output_PAPER_md --> S_claims_extractor
  F_output_CLAIMS_md["`output/CLAIMS.md`"]:::file
  S_claims_extractor --> F_output_CLAIMS_md
  S_concept_graph["`concept-graph`"]:::skill
  F_output_TUTORIAL_SPEC_md["`output/TUTORIAL_SPEC.md`"]:::file
  F_output_TUTORIAL_SPEC_md --> S_concept_graph
  F_outline_concept_graph_yml["`outline/concept_graph.yml`"]:::file
  S_concept_graph --> F_outline_concept_graph_yml
  S_dedupe_rank["`dedupe-rank`"]:::skill
  F_papers_papers_raw_jsonl --> S_dedupe_rank
  F_papers_core_set_csv["`papers/core_set.csv`"]:::file
  S_dedupe_rank --> F_papers_core_set_csv
  F_papers_papers_dedup_jsonl["`papers/papers_dedup.jsonl`"]:::file
  S_dedupe_rank --> F_papers_papers_dedup_jsonl
  S_draft_polisher["`draft-polisher`"]:::skill
  F_citations_ref_bib --> S_draft_polisher
  F_outline_evidence_drafts_jsonl --> S_draft_polisher
  F_outline_outline_yml --> S_draft_polisher
  F_outline_subsection_briefs_jsonl --> S_draft_polisher
  F_output_DRAFT_md --> S_draft_polisher
  S_draft_polisher --> F_output_DRAFT_md
  S_draft_polisher --> F_output_citation_anchors_prepolish_jsonl
  S_evaluation_anchor_checker["`evaluation-anchor-checker`"]:::skill
  F_citations_ref_bib --> S_evaluation_anchor_checker
  F_outline_anchor_sheet_jsonl --> S_evaluation_anchor_checker
  F_outline_evidence_drafts_jsonl --> S_evaluation_anchor_checker
  F_outline_writer_context_packs_jsonl --> S_evaluation_anchor_checker
  F_sections_md["`sections/*.md`"]:::file
  F_sections_md --> S_evaluation_anchor_checker
  S_evaluation_anchor_checker --> F_output_DRAFT_md
  F_output_eval_anchors_checked_refined_ok["`output/eval_anchors_checked.refined.ok`"]:::file
  S_evaluation_anchor_checker --> F_output_eval_anchors_checked_refined_ok
  S_evaluation_anchor_checker --> F_sections_md
  S_evidence_auditor["`evidence-auditor`"]:::skill
  F_output_CLAIMS_md --> S_evidence_auditor
  F_output_MISSING_EVIDENCE_md["`output/MISSING_EVIDENCE.md`"]:::file
  S_evidence_auditor --> F_output_MISSING_EVIDENCE_md
  S_evidence_binder["`evidence-binder`"]:::skill
  F_citations_ref_bib --> S_evidence_binder
  F_outline_mapping_tsv --> S_evidence_binder
  F_outline_subsection_briefs_jsonl --> S_evidence_binder
  F_papers_evidence_bank_jsonl["`papers/evidence_bank.jsonl`"]:::file
  F_papers_evidence_bank_jsonl --> S_evidence_binder
  F_outline_evidence_binding_report_md["`outline/evidence_binding_report.md`"]:::file
  S_evidence_binder --> F_outline_evidence_binding_report_md
  F_outline_evidence_bindings_jsonl["`outline/evidence_bindings.jsonl`"]:::file
  S_evidence_binder --> F_outline_evidence_bindings_jsonl
  S_evidence_draft["`evidence-draft`"]:::skill
  F_citations_ref_bib --> S_evidence_draft
  F_outline_evidence_bindings_jsonl --> S_evidence_draft
  F_outline_subsection_briefs_jsonl --> S_evidence_draft
  F_papers_evidence_bank_jsonl --> S_evidence_draft
  F_papers_paper_notes_jsonl --> S_evidence_draft
  S_evidence_draft --> F_outline_evidence_drafts_jsonl
  F_outline_evidence_drafts["`outline/evidence_drafts/`"]:::file
  S_evidence_draft --> F_outline_evidence_drafts
  S_evidence_selfloop["`evidence-selfloop`"]:::skill
  F_outline_anchor_sheet_jsonl --> S_evidence_selfloop
  F_outline_evidence_binding_report_md --> S_evidence_selfloop
  F_outline_evidence_bindings_jsonl --> S_evidence_selfloop
  F_outline_evidence_drafts_jsonl --> S_evidence_selfloop
  F_outline_subsection_briefs_jsonl --> S_evidence_selfloop
  F_papers_fulltext_index_jsonl["`papers/fulltext_index.jsonl`"]:::file
  F_papers_fulltext_index_jsonl --> S_evidence_selfloop
  F_papers_paper_notes_jsonl --> S_evidence_selfloop
  F_queries_md --> S_evidence_selfloop
  F_output_EVIDENCE_SELFLOOP_TODO_md["`output/EVIDENCE_SELFLOOP_TODO.md`"]:::file
  S_evidence_selfloop --> F_output_EVIDENCE_SELFLOOP_TODO_md
  S_exercise_builder["`exercise-builder`"]:::skill
  F_outline_module_plan_yml["`outline/module_plan.yml`"]:::file
  F_outline_module_plan_yml --> S_exercise_builder
  S_exercise_builder --> F_outline_module_plan_yml
  S_extraction_form["`extraction-form`"]:::skill
  F_output_PROTOCOL_md["`output/PROTOCOL.md`"]:::file
  F_output_PROTOCOL_md --> S_extraction_form
  F_papers_paper_notes_jsonl --> S_extraction_form
  F_papers_screening_log_csv["`papers/screening_log.csv`"]:::file
  F_papers_screening_log_csv --> S_extraction_form
  S_extraction_form --> F_papers_extraction_table_csv
  S_front_matter_writer["`front-matter-writer`"]:::skill
  F_DECISIONS_md --> S_front_matter_writer
  F_GOAL_md --> S_front_matter_writer
  F_citations_ref_bib --> S_front_matter_writer
  F_outline_coverage_report_md["`outline/coverage_report.md`"]:::file
  F_outline_coverage_report_md --> S_front_matter_writer
  F_outline_mapping_tsv --> S_front_matter_writer
  F_outline_outline_yml --> S_front_matter_writer
  F_outline_writer_context_packs_jsonl --> S_front_matter_writer
  F_papers_core_set_csv --> S_front_matter_writer
  F_papers_retrieval_report_md["`papers/retrieval_report.md`"]:::file
  F_papers_retrieval_report_md --> S_front_matter_writer
  F_queries_md --> S_front_matter_writer
  S_global_reviewer["`global-reviewer`"]:::skill
  F_citations_ref_bib --> S_global_reviewer
  F_outline_claim_evidence_matrix_md --> S_global_reviewer
  F_outline_mapping_tsv --> S_global_reviewer
  F_outline_outline_yml --> S_global_reviewer
  F_outline_taxonomy_yml["`outline/taxonomy.yml`"]:::file
  F_outline_taxonomy_yml --> S_global_reviewer
  F_output_DRAFT_md --> S_global_reviewer
  S_global_reviewer --> F_output_DRAFT_md
  F_output_GLOBAL_REVIEW_md["`output/GLOBAL_REVIEW.md`"]:::file
  S_global_reviewer --> F_output_GLOBAL_REVIEW_md
  S_grad_paragraph["`grad-paragraph`"]:::skill
  F_sections_S_sub_id_md["`sections/S<sub_id>.md`"]:::file
  S_grad_paragraph --> F_sections_S_sub_id_md
  S_keyword_expansion["`keyword-expansion`"]:::skill
  F_DECISIONS_md --> S_keyword_expansion
  F_queries_md --> S_keyword_expansion
  S_keyword_expansion --> F_queries_md
  S_latex_compile_qa["`latex-compile-qa`"]:::skill
  F_citations_ref_bib --> S_latex_compile_qa
  F_latex_main_tex["`latex/main.tex`"]:::file
  F_latex_main_tex --> S_latex_compile_qa
  F_latex_main_pdf["`latex/main.pdf`"]:::file
  S_latex_compile_qa --> F_latex_main_pdf
  F_output_LATEX_BUILD_REPORT_md["`output/LATEX_BUILD_REPORT.md`"]:::file
  S_latex_compile_qa --> F_output_LATEX_BUILD_REPORT_md
  S_latex_scaffold["`latex-scaffold`"]:::skill
  F_citations_ref_bib --> S_latex_scaffold
  F_output_DRAFT_md --> S_latex_scaffold
  S_latex_scaffold --> F_latex_main_tex
  S_limitation_weaver["`limitation-weaver`"]:::skill
  F_outline_writer_context_packs_jsonl --> S_limitation_weaver
  F_output_WRITER_SELFLOOP_TODO_md["`output/WRITER_SELFLOOP_TODO.md`"]:::file
  F_output_WRITER_SELFLOOP_TODO_md --> S_limitation_weaver
  F_sections_S_sub_id_md --> S_limitation_weaver
  S_limitation_weaver --> F_sections_S_sub_id_md
  S_literature_engineer["`literature-engineer`"]:::skill
  F_papers_arxiv_export_csv_json_jsonl_bib["`papers/arxiv_export.(csv|json|jsonl|bib)`"]:::file
  F_papers_arxiv_export_csv_json_jsonl_bib --> S_literature_engineer
  F_papers_import_csv_json_jsonl_bib["`papers/import.(csv|json|jsonl|bib)`"]:::file
  F_papers_import_csv_json_jsonl_bib --> S_literature_engineer
  F_papers_imports_csv_json_jsonl_bib["`papers/imports/*.(csv|json|jsonl|bib)`"]:::file
  F_papers_imports_csv_json_jsonl_bib --> S_literature_engineer
  F_papers_snowball_csv_json_jsonl_bib["`papers/snowball/*.(csv|json|jsonl|bib)`"]:::file
  F_papers_snowball_csv_json_jsonl_bib --> S_literature_engineer
  F_queries_md --> S_literature_engineer
  S_literature_engineer --> F_papers_papers_raw_csv
  S_literature_engineer --> F_papers_papers_raw_jsonl
  S_literature_engineer --> F_papers_retrieval_report_md
  S_module_planner["`module-planner`"]:::skill
  F_outline_concept_graph_yml --> S_module_planner
  S_module_planner --> F_outline_module_plan_yml
  S_novelty_matrix["`novelty-matrix`"]:::skill
  F_output_CLAIMS_md --> S_novelty_matrix
  F_output_NOVELTY_MATRIX_md["`output/NOVELTY_MATRIX.md`"]:::file
  S_novelty_matrix --> F_output_NOVELTY_MATRIX_md
  S_opener_variator["`opener-variator`"]:::skill
  F_outline_writer_context_packs_jsonl --> S_opener_variator
  F_output_WRITER_SELFLOOP_TODO_md --> S_opener_variator
  F_sections_S_sub_id_md --> S_opener_variator
  S_opener_variator --> F_sections_S_sub_id_md
  S_outline_budgeter["`outline-budgeter`"]:::skill
  F_GOAL_md --> S_outline_budgeter
  F_outline_coverage_report_md --> S_outline_budgeter
  F_outline_mapping_tsv --> S_outline_budgeter
  F_outline_outline_yml --> S_outline_budgeter
  F_queries_md --> S_outline_budgeter
  F_outline_OUTLINE_BUDGET_REPORT_md["`outline/OUTLINE_BUDGET_REPORT.md`"]:::file
  S_outline_budgeter --> F_outline_OUTLINE_BUDGET_REPORT_md
  S_outline_budgeter --> F_outline_outline_yml
  S_outline_builder["`outline-builder`"]:::skill
  F_outline_taxonomy_yml --> S_outline_builder
  F_ref_agent_surveys_STYLE_REPORT_md --> S_outline_builder
  F_ref_agent_surveys_text --> S_outline_builder
  S_outline_builder --> F_outline_outline_yml
  S_outline_refiner["`outline-refiner`"]:::skill
  F_GOAL_md --> S_outline_refiner
  F_outline_OUTLINE_BUDGET_REPORT_md --> S_outline_refiner
  F_outline_mapping_tsv --> S_outline_refiner
  F_outline_outline_yml --> S_outline_refiner
  F_outline_subsection_briefs_jsonl --> S_outline_refiner
  F_papers_paper_notes_jsonl --> S_outline_refiner
  S_outline_refiner --> F_outline_coverage_report_md
  F_outline_outline_state_jsonl["`outline/outline_state.jsonl`"]:::file
  S_outline_refiner --> F_outline_outline_state_jsonl
  S_paper_notes["`paper-notes`"]:::skill
  F_outline_mapping_tsv --> S_paper_notes
  F_papers_core_set_csv --> S_paper_notes
  F_papers_fulltext_txt["`papers/fulltext/*.txt`"]:::file
  F_papers_fulltext_txt --> S_paper_notes
  F_papers_fulltext_index_jsonl --> S_paper_notes
  S_paper_notes --> F_papers_paper_notes_jsonl
  S_pdf_text_extractor["`pdf-text-extractor`"]:::skill
  F_outline_mapping_tsv --> S_pdf_text_extractor
  F_papers_core_set_csv --> S_pdf_text_extractor
  F_papers_fulltext_paper_id_txt["`papers/fulltext/<paper_id>.txt`"]:::file
  S_pdf_text_extractor --> F_papers_fulltext_paper_id_txt
  S_pdf_text_extractor --> F_papers_fulltext_index_jsonl
  F_papers_pdfs_paper_id_pdf["`papers/pdfs/<paper_id>.pdf`"]:::file
  S_pdf_text_extractor --> F_papers_pdfs_paper_id_pdf
  S_pipeline_auditor["`pipeline-auditor`"]:::skill
  F_citations_ref_bib --> S_pipeline_auditor
  F_outline_evidence_bindings_jsonl --> S_pipeline_auditor
  F_outline_outline_yml --> S_pipeline_auditor
  F_output_DRAFT_md --> S_pipeline_auditor
  F_output_AUDIT_REPORT_md["`output/AUDIT_REPORT.md`"]:::file
  S_pipeline_auditor --> F_output_AUDIT_REPORT_md
  S_pipeline_router["`pipeline-router`"]:::skill
  F_DECISIONS_md --> S_pipeline_router
  F_GOAL_md --> S_pipeline_router
  F_PIPELINE_lock_md --> S_pipeline_router
  F_STATUS_md["`STATUS.md`"]:::file
  F_STATUS_md --> S_pipeline_router
  F_assets_pipeline_selection_form_md["`assets/pipeline-selection-form.md`"]:::file
  F_assets_pipeline_selection_form_md --> S_pipeline_router
  S_pipeline_router --> F_DECISIONS_md
  S_pipeline_router --> F_GOAL_md
  S_pipeline_router --> F_PIPELINE_lock_md
  S_pipeline_router --> F_STATUS_md
  S_pipeline_router --> F_queries_md
  S_post_merge_voice_gate["`post-merge-voice-gate`"]:::skill
  F_outline_transitions_md["`outline/transitions.md`"]:::file
  F_outline_transitions_md --> S_post_merge_voice_gate
  F_output_DRAFT_md --> S_post_merge_voice_gate
  F_output_POST_MERGE_VOICE_REPORT_md["`output/POST_MERGE_VOICE_REPORT.md`"]:::file
  S_post_merge_voice_gate --> F_output_POST_MERGE_VOICE_REPORT_md
  S_prose_writer["`prose-writer`"]:::skill
  F_DECISIONS_md --> S_prose_writer
  F_citations_ref_bib --> S_prose_writer
  F_outline_claim_evidence_matrix_md --> S_prose_writer
  F_outline_evidence_drafts_jsonl --> S_prose_writer
  F_outline_figures_md["`outline/figures.md`"]:::file
  F_outline_figures_md --> S_prose_writer
  F_outline_outline_yml --> S_prose_writer
  F_outline_subsection_briefs_jsonl --> S_prose_writer
  F_outline_tables_appendix_md --> S_prose_writer
  F_outline_tables_index_md --> S_prose_writer
  F_outline_timeline_md["`outline/timeline.md`"]:::file
  F_outline_timeline_md --> S_prose_writer
  F_outline_transitions_md --> S_prose_writer
  S_prose_writer --> F_output_DRAFT_md
  F_output_SNAPSHOT_md["`output/SNAPSHOT.md`"]:::file
  S_prose_writer --> F_output_SNAPSHOT_md
  S_protocol_writer["`protocol-writer`"]:::skill
  F_DECISIONS_md --> S_protocol_writer
  F_GOAL_md --> S_protocol_writer
  F_STATUS_md --> S_protocol_writer
  S_protocol_writer --> F_output_PROTOCOL_md
  S_redundancy_pruner["`redundancy-pruner`"]:::skill
  F_outline_outline_yml --> S_redundancy_pruner
  F_output_DRAFT_md --> S_redundancy_pruner
  F_output_citation_anchors_prepolish_jsonl --> S_redundancy_pruner
  S_redundancy_pruner --> F_output_DRAFT_md
  S_research_pipeline_runner["`research-pipeline-runner`"]:::skill
  F_pipelines_arxiv_survey_latex_pipeline_md["`pipelines/arxiv-survey-latex.pipeline.md`"]:::file
  F_pipelines_arxiv_survey_latex_pipeline_md --> S_research_pipeline_runner
  F_CHECKPOINTS_md["`CHECKPOINTS.md`"]:::file
  S_research_pipeline_runner --> F_CHECKPOINTS_md
  S_research_pipeline_runner --> F_DECISIONS_md
  S_research_pipeline_runner --> F_GOAL_md
  S_research_pipeline_runner --> F_PIPELINE_lock_md
  S_research_pipeline_runner --> F_STATUS_md
  S_research_pipeline_runner --> F_UNITS_csv
  F_workspaces_name["`workspaces/<name>/`"]:::file
  S_research_pipeline_runner --> F_workspaces_name
  S_rubric_writer["`rubric-writer`"]:::skill
  F_DECISIONS_md --> S_rubric_writer
  F_output_CLAIMS_md --> S_rubric_writer
  F_output_MISSING_EVIDENCE_md --> S_rubric_writer
  F_output_NOVELTY_MATRIX_md --> S_rubric_writer
  F_output_REVIEW_md["`output/REVIEW.md`"]:::file
  S_rubric_writer --> F_output_REVIEW_md
  S_schema_normalizer["`schema-normalizer`"]:::skill
  F_citations_ref_bib --> S_schema_normalizer
  F_outline_anchor_sheet_jsonl --> S_schema_normalizer
  F_outline_chapter_briefs_jsonl --> S_schema_normalizer
  F_outline_evidence_bindings_jsonl --> S_schema_normalizer
  F_outline_evidence_drafts_jsonl --> S_schema_normalizer
  F_outline_outline_yml --> S_schema_normalizer
  F_outline_subsection_briefs_jsonl --> S_schema_normalizer
  F_outline_writer_context_packs_jsonl --> S_schema_normalizer
  F_output_SCHEMA_NORMALIZATION_REPORT_md["`output/SCHEMA_NORMALIZATION_REPORT.md`"]:::file
  S_schema_normalizer --> F_output_SCHEMA_NORMALIZATION_REPORT_md
  S_screening_manager["`screening-manager`"]:::skill
  F_output_PROTOCOL_md --> S_screening_manager
  F_papers_core_set_csv --> S_screening_manager
  F_papers_papers_dedup_jsonl --> S_screening_manager
  F_papers_papers_raw_jsonl --> S_screening_manager
  S_screening_manager --> F_papers_screening_log_csv
  S_section_logic_polisher["`section-logic-polisher`"]:::skill
  F_outline_subsection_briefs_jsonl --> S_section_logic_polisher
  F_outline_writer_context_packs_jsonl --> S_section_logic_polisher
  F_sections["`sections/`"]:::file
  F_sections --> S_section_logic_polisher
  F_output_SECTION_LOGIC_REPORT_md["`output/SECTION_LOGIC_REPORT.md`"]:::file
  S_section_logic_polisher --> F_output_SECTION_LOGIC_REPORT_md
  S_section_logic_polisher --> F_sections
  S_section_mapper["`section-mapper`"]:::skill
  F_outline_outline_yml --> S_section_mapper
  F_papers_core_set_csv --> S_section_mapper
  S_section_mapper --> F_outline_mapping_tsv
  F_outline_mapping_report_md["`outline/mapping_report.md`"]:::file
  S_section_mapper --> F_outline_mapping_report_md
  S_section_merger["`section-merger`"]:::skill
  F_GOAL_md --> S_section_merger
  F_outline_outline_yml --> S_section_merger
  F_outline_tables_appendix_md --> S_section_merger
  F_outline_transitions_md --> S_section_merger
  F_sections_sections_manifest_jsonl["`sections/sections_manifest.jsonl`"]:::file
  F_sections_sections_manifest_jsonl --> S_section_merger
  S_section_merger --> F_output_DRAFT_md
  F_output_MERGE_REPORT_md["`output/MERGE_REPORT.md`"]:::file
  S_section_merger --> F_output_MERGE_REPORT_md
  S_snapshot_writer["`snapshot-writer`"]:::skill
  F_outline_outline_yml --> S_snapshot_writer
  F_papers_core_set_csv --> S_snapshot_writer
  F_papers_papers_dedup_jsonl --> S_snapshot_writer
  F_queries_md --> S_snapshot_writer
  S_snapshot_writer --> F_output_SNAPSHOT_md
  S_style_harmonizer["`style-harmonizer`"]:::skill
  F_outline_writer_context_packs_jsonl --> S_style_harmonizer
  F_output_WRITER_SELFLOOP_TODO_md --> S_style_harmonizer
  F_sections_md --> S_style_harmonizer
  S_style_harmonizer --> F_sections_md
  F_sections_style_harmonized_refined_ok["`sections/style_harmonized.refined.ok`"]:::file
  S_style_harmonizer --> F_sections_style_harmonized_refined_ok
  S_subsection_briefs["`subsection-briefs`"]:::skill
  F_GOAL_md --> S_subsection_briefs
  F_outline_claim_evidence_matrix_md --> S_subsection_briefs
  F_outline_mapping_tsv --> S_subsection_briefs
  F_outline_outline_yml --> S_subsection_briefs
  F_papers_paper_notes_jsonl --> S_subsection_briefs
  S_subsection_briefs --> F_outline_subsection_briefs_jsonl
  S_subsection_polisher["`subsection-polisher`"]:::skill
  F_citations_ref_bib --> S_subsection_polisher
  F_outline_evidence_drafts_jsonl --> S_subsection_polisher
  F_outline_subsection_briefs_jsonl --> S_subsection_polisher
  F_outline_writer_context_packs_jsonl --> S_subsection_polisher
  F_sections_S_sub_id_md --> S_subsection_polisher
  S_subsection_polisher --> F_sections_S_sub_id_md
  S_subsection_writer["`subsection-writer`"]:::skill
  F_DECISIONS_md --> S_subsection_writer
  F_citations_ref_bib --> S_subsection_writer
  F_outline_anchor_sheet_jsonl --> S_subsection_writer
  F_outline_chapter_briefs_jsonl --> S_subsection_writer
  F_outline_evidence_bindings_jsonl --> S_subsection_writer
  F_outline_evidence_drafts_jsonl --> S_subsection_writer
  F_outline_outline_yml --> S_subsection_writer
  F_outline_subsection_briefs_jsonl --> S_subsection_writer
  F_outline_writer_context_packs_jsonl --> S_subsection_writer
  S_survey_seed_harvest["`survey-seed-harvest`"]:::skill
  F_papers_papers_dedup_jsonl --> S_survey_seed_harvest
  S_survey_seed_harvest --> F_outline_taxonomy_yml
  S_survey_visuals["`survey-visuals`"]:::skill
  F_citations_ref_bib --> S_survey_visuals
  F_outline_claim_evidence_matrix_md --> S_survey_visuals
  F_outline_outline_yml --> S_survey_visuals
  F_papers_paper_notes_jsonl --> S_survey_visuals
  S_survey_visuals --> F_outline_figures_md
  S_survey_visuals --> F_outline_timeline_md
  S_synthesis_writer["`synthesis-writer`"]:::skill
  F_DECISIONS_md --> S_synthesis_writer
  F_output_PROTOCOL_md --> S_synthesis_writer
  F_papers_extraction_table_csv --> S_synthesis_writer
  F_output_SYNTHESIS_md["`output/SYNTHESIS.md`"]:::file
  S_synthesis_writer --> F_output_SYNTHESIS_md
  S_table_filler["`table-filler`"]:::skill
  F_citations_ref_bib --> S_table_filler
  F_outline_anchor_sheet_jsonl --> S_table_filler
  F_outline_evidence_drafts_jsonl --> S_table_filler
  F_outline_subsection_briefs_jsonl --> S_table_filler
  F_outline_table_schema_md --> S_table_filler
  S_table_filler --> F_outline_tables_index_md
  S_table_schema["`table-schema`"]:::skill
  F_GOAL_md --> S_table_schema
  F_outline_evidence_drafts_jsonl --> S_table_schema
  F_outline_outline_yml --> S_table_schema
  F_outline_subsection_briefs_jsonl --> S_table_schema
  S_table_schema --> F_outline_table_schema_md
  S_taxonomy_builder["`taxonomy-builder`"]:::skill
  F_DECISIONS_md --> S_taxonomy_builder
  F_papers_core_set_csv --> S_taxonomy_builder
  F_papers_papers_dedup_jsonl --> S_taxonomy_builder
  S_taxonomy_builder --> F_outline_taxonomy_yml
  S_terminology_normalizer["`terminology-normalizer`"]:::skill
  F_outline_outline_yml --> S_terminology_normalizer
  F_outline_taxonomy_yml --> S_terminology_normalizer
  F_output_DRAFT_md --> S_terminology_normalizer
  S_terminology_normalizer --> F_output_DRAFT_md
  F_output_GLOSSARY_md["`output/GLOSSARY.md`"]:::file
  S_terminology_normalizer --> F_output_GLOSSARY_md
  S_transition_weaver["`transition-weaver`"]:::skill
  F_outline_outline_yml --> S_transition_weaver
  F_outline_subsection_briefs_jsonl --> S_transition_weaver
  S_transition_weaver --> F_outline_transitions_md
  S_tutorial_module_writer["`tutorial-module-writer`"]:::skill
  F_DECISIONS_md --> S_tutorial_module_writer
  F_outline_module_plan_yml --> S_tutorial_module_writer
  F_output_TUTORIAL_md["`output/TUTORIAL.md`"]:::file
  S_tutorial_module_writer --> F_output_TUTORIAL_md
  S_tutorial_spec["`tutorial-spec`"]:::skill
  F_DECISIONS_md --> S_tutorial_spec
  F_GOAL_md --> S_tutorial_spec
  F_STATUS_md --> S_tutorial_spec
  S_tutorial_spec --> F_output_TUTORIAL_SPEC_md
  S_unit_executor["`unit-executor`"]:::skill
  F_UNITS_csv --> S_unit_executor
  S_unit_executor --> F_STATUS_md
  S_unit_executor --> F_UNITS_csv
  S_unit_planner["`unit-planner`"]:::skill
  F_PIPELINE_lock_md --> S_unit_planner
  F_pipelines_pipeline_md --> S_unit_planner
  F_templates_UNITS_csv["`templates/UNITS.*.csv`"]:::file
  F_templates_UNITS_csv --> S_unit_planner
  S_unit_planner --> F_STATUS_md
  S_unit_planner --> F_UNITS_csv
  S_workspace_init["`workspace-init`"]:::skill
  S_workspace_init --> F_CHECKPOINTS_md
  S_workspace_init --> F_DECISIONS_md
  S_workspace_init --> F_GOAL_md
  S_workspace_init --> F_STATUS_md
  S_workspace_init --> F_UNITS_csv
  F_citations["`citations/`"]:::file
  S_workspace_init --> F_citations
  F_outline["`outline/`"]:::file
  S_workspace_init --> F_outline
  F_output["`output/`"]:::file
  S_workspace_init --> F_output
  F_papers["`papers/`"]:::file
  S_workspace_init --> F_papers
  S_workspace_init --> F_queries_md
  S_writer_context_pack["`writer-context-pack`"]:::skill
  F_citations_ref_bib --> S_writer_context_pack
  F_outline_anchor_sheet_jsonl --> S_writer_context_pack
  F_outline_chapter_briefs_jsonl --> S_writer_context_pack
  F_outline_evidence_bindings_jsonl --> S_writer_context_pack
  F_outline_evidence_drafts_jsonl --> S_writer_context_pack
  F_outline_outline_yml --> S_writer_context_pack
  F_outline_subsection_briefs_jsonl --> S_writer_context_pack
  S_writer_context_pack --> F_outline_writer_context_packs_jsonl
  S_writer_selfloop["`writer-selfloop`"]:::skill
  F_citations_ref_bib --> S_writer_selfloop
  F_outline_chapter_briefs_jsonl --> S_writer_selfloop
  F_outline_evidence_bindings_jsonl --> S_writer_selfloop
  F_outline_subsection_briefs_jsonl --> S_writer_selfloop
  F_outline_writer_context_packs_jsonl --> S_writer_selfloop
  F_output_EVIDENCE_SELFLOOP_TODO_md --> S_writer_selfloop
  F_sections_md --> S_writer_selfloop
  F_sections_sections_manifest_jsonl --> S_writer_selfloop
  S_writer_selfloop --> F_output_WRITER_SELFLOOP_TODO_md
```

## Pipeline execution graphs (from templates/UNITS.*.csv)

### arxiv-survey-latex

```mermaid
flowchart LR
  classDef unit fill:#fff3e0,stroke:#fb8c00,color:#e65100;
  classDef human fill:#ffebee,stroke:#e53935,color:#b71c1c,stroke-width:2px;

  subgraph "C0 - Init"
    U_U001["`U001`\n`workspace-init`"]:::unit
    U_U002["`U002`\n`pipeline-router`"]:::unit
  end

  subgraph "C1 - Retrieval & core set"
    U_U010["`U010`\n`literature-engineer`"]:::unit
    U_U020["`U020`\n`dedupe-rank`"]:::unit
  end

  subgraph "C2 - Structure"
    U_U030["`U030`\n`taxonomy-builder`"]:::unit
    U_U040["`U040`\n`outline-builder`"]:::unit
    U_U050["`U050`\n`section-mapper`"]:::unit
    U_U051["`U051`\n`outline-refiner`"]:::unit
    U_U052["`U052`\n`pipeline-router`"]:::unit
    U_U055["`U055`\n`pipeline-router`"]:::unit
    class U_U055 human
  end

  subgraph "C3 - Evidence pack"
    U_U058["`U058`\n`pdf-text-extractor`"]:::unit
    U_U060["`U060`\n`paper-notes`"]:::unit
    U_U075["`U075`\n`subsection-briefs`"]:::unit
    U_U076["`U076`\n`chapter-briefs`"]:::unit
  end

  subgraph "C4 - Citations + evidence packs"
    U_U090["`U090`\n`citation-verifier`"]:::unit
    U_U091["`U091`\n`evidence-binder`"]:::unit
    U_U092["`U092`\n`evidence-draft`"]:::unit
    U_U0925["`U0925`\n`table-schema`"]:::unit
    U_U0926["`U0926`\n`table-filler`"]:::unit
    U_U0927["`U0927`\n`appendix-table-writer`"]:::unit
    U_U093["`U093`\n`anchor-sheet`"]:::unit
    U_U0935["`U0935`\n`schema-normalizer`"]:::unit
    U_U099["`U099`\n`writer-context-pack`"]:::unit
    U_U0995["`U0995`\n`evidence-selfloop`"]:::unit
    U_U094["`U094`\n`claim-matrix-rewriter`"]:::unit
  end

  subgraph "C5 - Draft + PDF"
    U_U095["`U095`\n`front-matter-writer`"]:::unit
    U_U096["`U096`\n`chapter-lead-writer`"]:::unit
    U_U100["`U100`\n`subsection-writer`"]:::unit
    U_U1005["`U1005`\n`writer-selfloop`"]:::unit
    U_U1006["`U1006`\n`style-harmonizer`"]:::unit
    U_U102["`U102`\n`section-logic-polisher`"]:::unit
    U_U098["`U098`\n`transition-weaver`"]:::unit
    U_U101["`U101`\n`section-merger`"]:::unit
    U_U103["`U103`\n`post-merge-voice-gate`"]:::unit
    U_U104["`U104`\n`citation-diversifier`"]:::unit
    U_U1045["`U1045`\n`citation-injector`"]:::unit
    U_U105["`U105`\n`draft-polisher`"]:::unit
    U_U108["`U108`\n`global-reviewer`"]:::unit
    U_U109["`U109`\n`pipeline-auditor`"]:::unit
    U_U110["`U110`\n`latex-scaffold`"]:::unit
    U_U120["`U120`\n`latex-compile-qa`"]:::unit
    U_U130["`U130`\n`artifact-contract-auditor`"]:::unit
  end

  U_U001 --> U_U002
  U_U002 --> U_U010
  U_U010 --> U_U020
  U_U020 --> U_U030
  U_U030 --> U_U040
  U_U040 --> U_U050
  U_U050 --> U_U051
  U_U051 --> U_U052
  U_U052 --> U_U055
  U_U055 --> U_U058
  U_U058 --> U_U060
  U_U060 --> U_U075
  U_U075 --> U_U076
  U_U060 --> U_U090
  U_U090 --> U_U091
  U_U075 --> U_U091
  U_U060 --> U_U091
  U_U091 --> U_U092
  U_U092 --> U_U0925
  U_U0925 --> U_U0926
  U_U093 --> U_U0926
  U_U0926 --> U_U0927
  U_U093 --> U_U0927
  U_U092 --> U_U093
  U_U093 --> U_U0935
  U_U0935 --> U_U099
  U_U076 --> U_U099
  U_U099 --> U_U0995
  U_U092 --> U_U094
  U_U0995 --> U_U095
  U_U0995 --> U_U096
  U_U0995 --> U_U100
  U_U099 --> U_U100
  U_U076 --> U_U100
  U_U095 --> U_U1005
  U_U096 --> U_U1005
  U_U100 --> U_U1005
  U_U1005 --> U_U1006
  U_U1006 --> U_U102
  U_U102 --> U_U098
  U_U100 --> U_U101
  U_U098 --> U_U101
  U_U0927 --> U_U101
  U_U101 --> U_U103
  U_U103 --> U_U104
  U_U104 --> U_U1045
  U_U1045 --> U_U105
  U_U105 --> U_U108
  U_U108 --> U_U109
  U_U109 --> U_U110
  U_U110 --> U_U120
  U_U120 --> U_U130
```

### arxiv-survey

```mermaid
flowchart LR
  classDef unit fill:#fff3e0,stroke:#fb8c00,color:#e65100;
  classDef human fill:#ffebee,stroke:#e53935,color:#b71c1c,stroke-width:2px;

  subgraph "C0 - Init"
    U_U001["`U001`\n`workspace-init`"]:::unit
    U_U002["`U002`\n`pipeline-router`"]:::unit
  end

  subgraph "C1 - Retrieval & core set"
    U_U010["`U010`\n`literature-engineer`"]:::unit
    U_U020["`U020`\n`dedupe-rank`"]:::unit
  end

  subgraph "C2 - Structure"
    U_U030["`U030`\n`taxonomy-builder`"]:::unit
    U_U040["`U040`\n`outline-builder`"]:::unit
    U_U050["`U050`\n`section-mapper`"]:::unit
    U_U051["`U051`\n`outline-refiner`"]:::unit
    U_U052["`U052`\n`pipeline-router`"]:::unit
    U_U055["`U055`\n`pipeline-router`"]:::unit
    class U_U055 human
  end

  subgraph "C3 - Evidence"
    U_U058["`U058`\n`pdf-text-extractor`"]:::unit
    U_U060["`U060`\n`paper-notes`"]:::unit
    U_U075["`U075`\n`subsection-briefs`"]:::unit
    U_U076["`U076`\n`chapter-briefs`"]:::unit
  end

  subgraph "C4 - Citations + evidence packs"
    U_U090["`U090`\n`citation-verifier`"]:::unit
    U_U091["`U091`\n`evidence-binder`"]:::unit
    U_U092["`U092`\n`evidence-draft`"]:::unit
    U_U0925["`U0925`\n`table-schema`"]:::unit
    U_U0926["`U0926`\n`table-filler`"]:::unit
    U_U0927["`U0927`\n`appendix-table-writer`"]:::unit
    U_U093["`U093`\n`anchor-sheet`"]:::unit
    U_U0935["`U0935`\n`schema-normalizer`"]:::unit
    U_U099["`U099`\n`writer-context-pack`"]:::unit
    U_U0995["`U0995`\n`evidence-selfloop`"]:::unit
    U_U094["`U094`\n`claim-matrix-rewriter`"]:::unit
  end

  subgraph "C5 - Draft"
    U_U095["`U095`\n`front-matter-writer`"]:::unit
    U_U096["`U096`\n`chapter-lead-writer`"]:::unit
    U_U100["`U100`\n`subsection-writer`"]:::unit
    U_U1005["`U1005`\n`writer-selfloop`"]:::unit
    U_U1006["`U1006`\n`style-harmonizer`"]:::unit
    U_U102["`U102`\n`section-logic-polisher`"]:::unit
    U_U098["`U098`\n`transition-weaver`"]:::unit
    U_U101["`U101`\n`section-merger`"]:::unit
    U_U103["`U103`\n`post-merge-voice-gate`"]:::unit
    U_U104["`U104`\n`citation-diversifier`"]:::unit
    U_U1045["`U1045`\n`citation-injector`"]:::unit
    U_U105["`U105`\n`draft-polisher`"]:::unit
    U_U108["`U108`\n`global-reviewer`"]:::unit
    U_U109["`U109`\n`pipeline-auditor`"]:::unit
    U_U130["`U130`\n`artifact-contract-auditor`"]:::unit
  end

  U_U001 --> U_U002
  U_U002 --> U_U010
  U_U010 --> U_U020
  U_U020 --> U_U030
  U_U030 --> U_U040
  U_U040 --> U_U050
  U_U050 --> U_U051
  U_U051 --> U_U052
  U_U052 --> U_U055
  U_U055 --> U_U058
  U_U058 --> U_U060
  U_U060 --> U_U075
  U_U075 --> U_U076
  U_U060 --> U_U090
  U_U090 --> U_U091
  U_U075 --> U_U091
  U_U060 --> U_U091
  U_U091 --> U_U092
  U_U092 --> U_U0925
  U_U0925 --> U_U0926
  U_U093 --> U_U0926
  U_U0926 --> U_U0927
  U_U093 --> U_U0927
  U_U092 --> U_U093
  U_U093 --> U_U0935
  U_U0935 --> U_U099
  U_U076 --> U_U099
  U_U099 --> U_U0995
  U_U092 --> U_U094
  U_U0995 --> U_U095
  U_U0995 --> U_U096
  U_U0995 --> U_U100
  U_U099 --> U_U100
  U_U076 --> U_U100
  U_U095 --> U_U1005
  U_U096 --> U_U1005
  U_U100 --> U_U1005
  U_U1005 --> U_U1006
  U_U1006 --> U_U102
  U_U102 --> U_U098
  U_U100 --> U_U101
  U_U098 --> U_U101
  U_U0927 --> U_U101
  U_U101 --> U_U103
  U_U103 --> U_U104
  U_U104 --> U_U1045
  U_U1045 --> U_U105
  U_U105 --> U_U108
  U_U108 --> U_U109
  U_U109 --> U_U130
```

### lit-snapshot

```mermaid
flowchart LR
  classDef unit fill:#fff3e0,stroke:#fb8c00,color:#e65100;
  classDef human fill:#ffebee,stroke:#e53935,color:#b71c1c,stroke-width:2px;

  subgraph "C0 - Init"
    U_U001["`U001`\n`workspace-init`"]:::unit
    U_U002["`U002`\n`pipeline-router`"]:::unit
  end

  subgraph "C1 - Retrieval & core set"
    U_U010["`U010`\n`arxiv-search`"]:::unit
    U_U020["`U020`\n`dedupe-rank`"]:::unit
  end

  subgraph "C2 - Structure"
    U_U030["`U030`\n`taxonomy-builder`"]:::unit
    U_U040["`U040`\n`outline-builder`"]:::unit
    U_U042["`U042`\n`pipeline-router`"]:::unit
    U_U045["`U045`\n`pipeline-router`"]:::unit
    class U_U045 human
  end

  subgraph "C3 - Snapshot"
    U_U050["`U050`\n`snapshot-writer`"]:::unit
    U_U060["`U060`\n`artifact-contract-auditor`"]:::unit
  end

  U_U001 --> U_U002
  U_U002 --> U_U010
  U_U010 --> U_U020
  U_U020 --> U_U030
  U_U030 --> U_U040
  U_U040 --> U_U042
  U_U042 --> U_U045
  U_U045 --> U_U050
  U_U050 --> U_U060
```

### peer-review

```mermaid
flowchart LR
  classDef unit fill:#fff3e0,stroke:#fb8c00,color:#e65100;
  classDef human fill:#ffebee,stroke:#e53935,color:#b71c1c,stroke-width:2px;

  subgraph "C0 - Init"
    U_U001["`U001`\n`workspace-init`"]:::unit
    U_U002["`U002`\n`pipeline-router`"]:::unit
  end

  subgraph "C1 - Claims"
    U_U010["`U010`\n`claims-extractor`"]:::unit
  end

  subgraph "C2 - Evidence audit"
    U_U020["`U020`\n`evidence-auditor`"]:::unit
    U_U025["`U025`\n`novelty-matrix`"]:::unit
  end

  subgraph "C3 - Rubric write-up"
    U_U030["`U030`\n`rubric-writer`"]:::unit
    U_U040["`U040`\n`artifact-contract-auditor`"]:::unit
  end

  U_U001 --> U_U002
  U_U002 --> U_U010
  U_U010 --> U_U020
  U_U010 --> U_U025
  U_U020 --> U_U030
  U_U025 --> U_U030
  U_U030 --> U_U040
```

### systematic-review

```mermaid
flowchart LR
  classDef unit fill:#fff3e0,stroke:#fb8c00,color:#e65100;
  classDef human fill:#ffebee,stroke:#e53935,color:#b71c1c,stroke-width:2px;

  subgraph "C0 - Init"
    U_U001["`U001`\n`workspace-init`"]:::unit
    U_U002["`U002`\n`pipeline-router`"]:::unit
  end

  subgraph "C1 - Protocol"
    U_U010["`U010`\n`protocol-writer`"]:::unit
    U_U020["`U020`\n`pipeline-router`"]:::unit
    class U_U020 human
  end

  subgraph "C2 - Retrieval & candidate pool"
    U_U025["`U025`\n`literature-engineer`"]:::unit
    U_U026["`U026`\n`dedupe-rank`"]:::unit
  end

  subgraph "C3 - Screening"
    U_U030["`U030`\n`screening-manager`"]:::unit
  end

  subgraph "C4 - Extraction"
    U_U040["`U040`\n`extraction-form`"]:::unit
    U_U045["`U045`\n`bias-assessor`"]:::unit
  end

  subgraph "C5 - Synthesis"
    U_U050["`U050`\n`synthesis-writer`"]:::unit
    U_U060["`U060`\n`artifact-contract-auditor`"]:::unit
  end

  U_U001 --> U_U002
  U_U002 --> U_U010
  U_U010 --> U_U020
  U_U020 --> U_U025
  U_U025 --> U_U026
  U_U026 --> U_U030
  U_U030 --> U_U040
  U_U040 --> U_U045
  U_U045 --> U_U050
  U_U050 --> U_U060
```

### tutorial

```mermaid
flowchart LR
  classDef unit fill:#fff3e0,stroke:#fb8c00,color:#e65100;
  classDef human fill:#ffebee,stroke:#e53935,color:#b71c1c,stroke-width:2px;

  subgraph "C0 - Init"
    U_U001["`U001`\n`workspace-init`"]:::unit
    U_U002["`U002`\n`pipeline-router`"]:::unit
  end

  subgraph "C1 - Spec"
    U_U010["`U010`\n`tutorial-spec`"]:::unit
  end

  subgraph "C2 - Structure"
    U_U020["`U020`\n`concept-graph`"]:::unit
    U_U030["`U030`\n`module-planner`"]:::unit
    U_U035["`U035`\n`exercise-builder`"]:::unit
    U_U040["`U040`\n`pipeline-router`"]:::unit
    class U_U040 human
  end

  subgraph "C3 - Writing"
    U_U050["`U050`\n`tutorial-module-writer`"]:::unit
    U_U060["`U060`\n`artifact-contract-auditor`"]:::unit
  end

  U_U001 --> U_U002
  U_U002 --> U_U010
  U_U010 --> U_U020
  U_U020 --> U_U030
  U_U030 --> U_U035
  U_U035 --> U_U040
  U_U040 --> U_U050
  U_U050 --> U_U060
```
