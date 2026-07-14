from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from tooling import quality_reporting
from tooling.quality_checks import evidence_review as evidence_review_checks
from tooling.quality_checks import delivery as delivery_checks
from tooling.quality_checks import research_idea as research_idea_checks
from tooling.quality_checks import source_tutorial as source_tutorial_checks
from tooling.quality_checks import survey_retrieval
from tooling.quality_checks import survey_planning
from tooling.quality_checks import survey_writing
from tooling.quality_checks import survey_policy
from tooling.quality_checks import survey_structure
from tooling.quality_checks.common import QualityIssue


def _pipeline_profile(workspace: Path) -> str:
    return survey_policy.pipeline_profile_name(workspace)


def _draft_profile(workspace: Path) -> str:
    return survey_policy.draft_profile(workspace)


def _citation_target(workspace: Path) -> str:
    return survey_policy.citation_target(workspace)


def _global_citation_min_subsections(workspace: Path) -> int:
    return survey_policy.global_citation_min_subsections(workspace)


def survey_citation_policy(workspace: Path, *, bibliography_size: int, h3_count: int) -> dict[str, int | float | str]:
    return survey_policy.survey_citation_policy(
        workspace,
        bibliography_size=bibliography_size,
        h3_count=h3_count,
    )


def check_unit_outputs(*, skill: str, workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    checker = _QUALITY_CHECKS.get(skill)
    return checker(workspace, outputs) if checker is not None else []


def registered_quality_skills() -> frozenset[str]:
    """Return Skills with semantic checks beyond output existence."""

    return frozenset(_QUALITY_CHECKS)


def _check_pdf_text_extractor(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return survey_retrieval.check_pdf_text_extractor(workspace, outputs)


def write_quality_report(*, workspace: Path, unit_id: str, skill: str, issues: list[QualityIssue]) -> Path:
    return quality_reporting.write_quality_report(
        workspace=workspace,
        unit_id=unit_id,
        skill=skill,
        issues=issues,
    )


def _check_taxonomy(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return survey_planning.check_taxonomy(workspace, outputs)


def _check_mapping(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return survey_planning.check_mapping(workspace, outputs)


def _check_evidence_bindings(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return survey_planning.check_evidence_bindings(workspace, outputs)


def _check_table_schema(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return survey_planning.check_table_schema(workspace, outputs)


def _check_tables_index_md(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return survey_planning.check_tables_index(workspace, outputs)


def _check_tables_appendix_md(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return survey_planning.check_tables_appendix(workspace, outputs)


def _check_argument_snapshot(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return survey_writing.check_argument_snapshot(workspace, outputs)


def _check_sections_manifest(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return survey_writing.check_sections_manifest(workspace, outputs)


def _check_draft(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return survey_writing.check_draft(workspace, outputs)


def _check_latex_compile_qa(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return delivery_checks.check_latex_compile_qa(
        workspace,
        outputs,
        which=shutil.which,
    )


def _check_draft_polisher(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    issues = survey_writing.check_draft(workspace, outputs)
    issues.extend(survey_writing.check_citation_anchoring(workspace, outputs))
    return issues


def _check_extraction_form(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return evidence_review_checks.check_extraction(workspace, outputs, require_bias=False)


def _check_bias_assessor(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return evidence_review_checks.check_extraction(workspace, outputs, require_bias=True)


QualityCheck = Callable[[Path, list[str]], list[QualityIssue]]


# This registry is the semantic validation boundary between executable Skills
# and the Harness. Skills absent here still receive the Executor's declared
# output-existence checks, but no Skill-specific semantic gate.
_QUALITY_CHECKS: dict[str, QualityCheck] = {
    "anchor-sheet": survey_planning.check_anchor_sheet,
    "appendix-table-writer": survey_planning.check_tables_appendix,
    "argument-selfloop": _check_argument_snapshot,
    "artifact-contract-auditor": delivery_checks.check_contract_report,
    "arxiv-search": survey_retrieval.check_arxiv_search,
    "beamer-compile-qa": delivery_checks.check_beamer_compile_qa,
    "beamer-scaffold": delivery_checks.check_beamer_scaffold,
    "bias-assessor": _check_bias_assessor,
    "chapter-briefs": survey_planning.check_chapter_briefs,
    "chapter-skeleton": survey_structure.check_chapter_skeleton,
    "citation-injector": survey_retrieval.check_citation_injection,
    "citation-verifier": survey_retrieval.check_citations,
    "claim-evidence-matrix": survey_planning.check_claim_evidence_matrix,
    "claim-matrix-rewriter": survey_planning.check_claim_evidence_matrix,
    "dedupe-rank": survey_retrieval.check_dedupe_rank,
    "deliverable-selfloop": delivery_checks.check_deliverable_selfloop_report,
    "draft-polisher": _check_draft_polisher,
    "evaluation-anchor-checker": survey_writing.check_eval_anchor_report,
    "evidence-binder": _check_evidence_bindings,
    "evidence-draft": survey_planning.check_evidence_drafts,
    "extraction-form": _check_extraction_form,
    "global-reviewer": survey_writing.check_global_review,
    "idea-brief": research_idea_checks.check_idea_brief,
    "idea-direction-generator": research_idea_checks.check_direction_pool,
    "idea-memo-writer": research_idea_checks.check_report_bundle,
    "idea-screener": research_idea_checks.check_screening_table,
    "idea-shortlist-curator": research_idea_checks.check_shortlist,
    "idea-signal-mapper": research_idea_checks.check_signal_table,
    "latex-compile-qa": _check_latex_compile_qa,
    "latex-scaffold": delivery_checks.check_latex_scaffold,
    "literature-engineer": survey_retrieval.check_literature_engineer,
    "module-source-coverage": source_tutorial_checks.check_module_source_coverage,
    "outline-builder": survey_planning.check_outline,
    "outline-refiner": survey_planning.check_coverage_report,
    "paper-notes": survey_planning.check_paper_notes,
    "paragraph-curator": survey_writing.check_paragraph_curator,
    "pdf-text-extractor": _check_pdf_text_extractor,
    "pipeline-auditor": survey_writing.check_audit_report,
    "prose-writer": _check_draft,
    "protocol-writer": evidence_review_checks.check_protocol,
    "schema-normalizer": survey_planning.check_schema_normalization_report,
    "screening-manager": evidence_review_checks.check_screening,
    "section-bindings": survey_structure.check_section_bindings,
    "section-briefs": survey_structure.check_section_briefs,
    "section-logic-polisher": survey_writing.check_section_logic_polisher,
    "section-mapper": _check_mapping,
    "section-merger": survey_writing.check_merge_report,
    "source-ingest": source_tutorial_checks.check_source_ingest,
    "source-manifest": source_tutorial_checks.check_source_manifest,
    "source-tutorial-spec": source_tutorial_checks.check_source_tutorial_spec,
    "subsection-briefs": survey_planning.check_subsection_briefs,
    "subsection-writer": survey_writing.check_sections_manifest_index,
    "survey-visuals": survey_planning.check_survey_visuals,
    "synthesis-writer": evidence_review_checks.check_synthesis,
    "table-filler": _check_tables_index_md,
    "table-schema": _check_table_schema,
    "taxonomy-builder": _check_taxonomy,
    "transition-weaver": survey_planning.check_transitions,
    "tutorial-context-pack": source_tutorial_checks.check_tutorial_context_packs,
    "tutorial-selfloop": source_tutorial_checks.check_tutorial_selfloop_report,
    "tutorial-spec": source_tutorial_checks.check_tutorial_spec,
    "writer-context-pack": survey_planning.check_writer_context_packs,
    "writer-selfloop": survey_writing.check_writer_selfloop,
}
