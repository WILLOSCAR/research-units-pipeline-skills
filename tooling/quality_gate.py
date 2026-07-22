from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable

from tooling import quality_reporting
from tooling.quality_checks import evidence_review as evidence_review_checks
from tooling.quality_checks import paper_review as paper_review_checks
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


def required_completion_checks(workspace: Path) -> frozenset[str]:
    """Return the Workflow-declared Skill checks that must pass before DONE."""

    from tooling.common import load_workspace_pipeline_spec

    spec = load_workspace_pipeline_spec(workspace)
    if spec is None:
        return frozenset()
    completion_policy = spec.quality_contract.get("completion_policy", {})
    if not isinstance(completion_policy, dict):
        return frozenset()
    raw_checks = completion_policy.get("required_checks", [])
    if not isinstance(raw_checks, list):
        return frozenset()
    return frozenset(str(item or "").strip() for item in raw_checks if str(item or "").strip())


def completion_contract_issue(workspace: Path) -> str:
    """Return a fail-closed error when a bound Run loses its Pipeline contract."""

    from tooling.common import load_workspace_pipeline_spec

    if load_workspace_pipeline_spec(workspace) is not None:
        return ""

    run_workflow = ""
    run_path = workspace / ".harness" / "run.json"
    if run_path.exists():
        try:
            payload = json.loads(run_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = {}
        if isinstance(payload, dict):
            run_workflow = str(payload.get("workflow") or "").strip()

    declared_pipeline = ""
    lock_path = workspace / "PIPELINE.lock.md"
    if lock_path.exists():
        try:
            for raw_line in lock_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw_line.strip()
                if line.startswith("pipeline:"):
                    declared_pipeline = line.split(":", 1)[1].strip()
                    break
        except OSError:
            declared_pipeline = ""

    if run_workflow and run_workflow.lower() not in {"unknown", "unbound", "legacy"}:
        return (
            f"The Run is bound to Workflow `{run_workflow}`, but its Pipeline contract "
            "cannot be loaded from `PIPELINE.lock.md`. Restore or migrate the lock before completion."
        )
    if declared_pipeline:
        return (
            f"`PIPELINE.lock.md` declares `{declared_pipeline}`, but that Pipeline contract "
            "cannot be loaded. Repair the lock before completion."
        )
    return ""


def completion_check_required(*, skill: str, workspace: Path) -> bool:
    """Return whether the active Workflow makes this Skill check mandatory."""

    return bool(completion_contract_issue(workspace)) or skill in required_completion_checks(workspace)


def check_completion_acceptance(*, skill: str, workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    """Run a Workflow-declared acceptance check, including configuration errors."""

    contract_issue = completion_contract_issue(workspace)
    if contract_issue:
        return [QualityIssue(code="completion_contract_unavailable", message=contract_issue)]
    if not completion_check_required(skill=skill, workspace=workspace):
        return []
    checker = _QUALITY_CHECKS.get(skill)
    if checker is None:
        return [
            QualityIssue(
                code="missing_completion_check",
                message=(
                    f"The active Workflow requires an acceptance check for `{skill}`, "
                    "but the Harness has no registered checker."
                ),
            )
        ]
    try:
        return checker(workspace, outputs)
    except Exception as exc:  # pragma: no cover - defensive commit boundary
        return [
            QualityIssue(
                code="completion_check_exception",
                message=f"Workflow acceptance check crashed: {type(exc).__name__}: {exc}",
            )
        ]


def check_completion_invariants(*, skill: str, workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    """Run mandatory Workflow-domain invariants that apply even outside strict quality mode."""

    checker = _COMPLETION_INVARIANTS.get(skill)
    return checker(workspace, outputs) if checker is not None else []


def has_completion_invariant(skill: str) -> bool:
    """Return whether Completion executed a registered mandatory invariant for this Skill."""

    return skill in _COMPLETION_INVARIANTS


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


def _check_outline_cutover(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    if "outline/outline_state.jsonl" not in outputs:
        return []
    return survey_structure.section_first_cutover_issues(
        workspace,
        consumer="outline/outline_state.jsonl",
        require_stable_h3=True,
    )


_COMPLETION_INVARIANTS: dict[str, QualityCheck] = {
    "outline-refiner": _check_outline_cutover,
}


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
    "claims-extractor": paper_review_checks.check_claims,
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
    "evidence-selfloop": survey_planning.check_evidence_selfloop,
    "evidence-auditor": paper_review_checks.check_evidence_audit,
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
    "novelty-matrix": paper_review_checks.check_novelty_matrix,
    "outline-builder": survey_planning.check_outline,
    "outline-refiner": survey_planning.check_coverage_report,
    "paper-notes": survey_planning.check_paper_notes,
    "paragraph-curator": survey_writing.check_paragraph_curator,
    "pdf-text-extractor": _check_pdf_text_extractor,
    "pipeline-auditor": survey_writing.check_audit_report,
    "prose-writer": _check_draft,
    "protocol-writer": evidence_review_checks.check_protocol,
    "rubric-writer": paper_review_checks.check_review,
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
