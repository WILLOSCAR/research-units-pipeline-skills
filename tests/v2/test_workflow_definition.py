from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from research_harness.workflows import (
    LoopContract,
    StageDefinition,
    UnitDefinition,
    WorkflowSyntaxError,
    WorkflowValidationError,
    load_workflow_definition,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
UNIT_HEADER = "unit_id,title,type,skill,inputs,outputs,acceptance,checkpoint,status,depends_on,owner\n"
EXPECTED_CASE_CONTRACTS = {
    "arxiv-survey": LoopContract(
        kind="survey",
        views=("output/DRAFT.md",),
        claim_sources=("outline/claim_evidence_matrix.md",),
        evidence_sources=(
            "papers/evidence_bank.jsonl",
            "outline/evidence_bindings.jsonl",
        ),
        decision_sources=("DECISIONS.md",),
    ),
    "arxiv-survey-latex": LoopContract(
        kind="survey",
        views=("output/DRAFT.md", "latex/main.tex", "latex/main.pdf"),
        claim_sources=("outline/claim_evidence_matrix.md",),
        evidence_sources=(
            "papers/evidence_bank.jsonl",
            "outline/evidence_bindings.jsonl",
        ),
        decision_sources=("DECISIONS.md",),
    ),
    "evidence-review": LoopContract(
        kind="evidence-synthesis",
        views=("output/SYNTHESIS.md",),
        claim_sources=("output/SYNTHESIS.md",),
        evidence_sources=("papers/screening_log.csv", "papers/extraction_table.csv"),
        decision_sources=("DECISIONS.md",),
    ),
    "idea-brainstorm": LoopContract(
        kind="ideas",
        views=("output/REPORT.md", "output/APPENDIX.md"),
        claim_sources=("output/trace/IDEA_SHORTLIST.jsonl",),
        evidence_sources=(
            "papers/evidence_bank.jsonl",
            "output/trace/IDEA_SIGNAL_TABLE.jsonl",
        ),
        decision_sources=("DECISIONS.md",),
    ),
    "paper-review": LoopContract(
        kind="review",
        views=("output/REVIEW.md",),
        claim_sources=("output/CLAIMS.jsonl",),
        evidence_sources=("output/EVIDENCE_AUDIT.jsonl", "output/NOVELTY_MATRIX.tsv"),
        decision_sources=("DECISIONS.md",),
    ),
    "research-brief": LoopContract(
        kind="brief",
        views=("output/SNAPSHOT.md",),
        claim_sources=("output/SNAPSHOT.md",),
        evidence_sources=("papers/papers_dedup.jsonl",),
        decision_sources=("DECISIONS.md",),
    ),
    "source-tutorial": LoopContract(
        kind="tutorial",
        views=("output/TUTORIAL.md", "latex/main.pdf", "latex/slides/main.pdf"),
        claim_sources=("outline/tutorial_context_packs.jsonl",),
        evidence_sources=("sources/provenance.jsonl", "outline/source_coverage.jsonl"),
        decision_sources=("DECISIONS.md",),
    ),
}


@pytest.mark.parametrize(
    "pipeline_name",
    (
        "arxiv-survey-latex",
        "arxiv-survey",
        "evidence-review",
        "idea-brainstorm",
        "paper-review",
        "research-brief",
        "source-tutorial",
    ),
)
def test_all_executable_workflow_contracts_compile(pipeline_name: str) -> None:
    workflow = load_workflow_definition(
        REPO_ROOT / "pipelines" / f"{pipeline_name}.pipeline.md",
        repo_root=REPO_ROOT,
    )

    assert workflow.name == pipeline_name
    assert workflow.units
    assert tuple(workflow.dag) == tuple(unit.id for unit in workflow.units)
    assert set(workflow.checks).issubset(workflow.skills)
    assert workflow.case_contract == EXPECTED_CASE_CONTRACTS[pipeline_name]
    for paths in (
        workflow.case_contract.views,
        workflow.case_contract.claim_sources,
        workflow.case_contract.evidence_sources,
        workflow.case_contract.decision_sources,
    ):
        assert set(paths).issubset(workflow.target_artifacts)


def test_case_contract_is_frozen() -> None:
    workflow = load_workflow_definition(
        REPO_ROOT / "pipelines" / "paper-review.pipeline.md",
        repo_root=REPO_ROOT,
    )

    with pytest.raises(FrozenInstanceError):
        setattr(workflow.case_contract, "kind", "changed")


def test_latex_variant_appends_only_its_case_views() -> None:
    base = load_workflow_definition(
        REPO_ROOT / "pipelines" / "arxiv-survey.pipeline.md",
        repo_root=REPO_ROOT,
    )
    latex = load_workflow_definition(
        REPO_ROOT / "pipelines" / "arxiv-survey-latex.pipeline.md",
        repo_root=REPO_ROOT,
    )

    assert latex.case_contract.views == (
        *base.case_contract.views,
        "latex/main.tex",
        "latex/main.pdf",
    )
    assert latex.case_contract.kind == base.case_contract.kind
    assert latex.case_contract.claim_sources == base.case_contract.claim_sources
    assert latex.case_contract.evidence_sources == base.case_contract.evidence_sources
    assert latex.case_contract.decision_sources == base.case_contract.decision_sources


def test_paper_review_compiles_one_typed_workflow_projection() -> None:
    workflow = load_workflow_definition(
        REPO_ROOT / "pipelines" / "paper-review.pipeline.md",
        repo_root=REPO_ROOT,
    )

    assert workflow.name == "paper-review"
    assert workflow.version == "1.5"
    assert all(isinstance(stage, StageDefinition) for stage in workflow.stages)
    assert all(isinstance(unit, UnitDefinition) for unit in workflow.units)
    assert tuple(stage.id for stage in workflow.stages) == ("C0", "C1", "C2", "C3")
    assert len(workflow.units) == 9

    assert workflow.dag["U030"] == ("U020", "U025")
    assert workflow.skills == (
        "workspace-init",
        "pipeline-router",
        "manuscript-ingest",
        "claims-extractor",
        "evidence-auditor",
        "novelty-matrix",
        "rubric-writer",
        "deliverable-selfloop",
        "artifact-contract-auditor",
    )
    assert workflow.checks == (
        "claims-extractor",
        "evidence-auditor",
        "novelty-matrix",
        "rubric-writer",
        "deliverable-selfloop",
        "artifact-contract-auditor",
    )


def test_explicit_units_path_supports_snapshot_backed_contract_loading(
    tmp_path: Path,
) -> None:
    copied_units = tmp_path / "UNITS.csv"
    copied_units.write_bytes(
        (REPO_ROOT / "templates" / "UNITS.paper-review.csv").read_bytes()
    )

    workflow = load_workflow_definition(
        REPO_ROOT / "pipelines" / "paper-review.pipeline.md",
        repo_root=REPO_ROOT,
        units_path=copied_units,
    )

    assert workflow.units_source == copied_units.resolve()
    assert workflow.units_template == "templates/UNITS.paper-review.csv"


def test_duplicate_yaml_key_is_never_silently_overwritten(tmp_path: Path) -> None:
    pipeline = tmp_path / "duplicate.pipeline.md"
    pipeline.write_text(
        "---\nname: first\nname: second\n---\n",
        encoding="utf-8",
    )

    with pytest.raises(WorkflowSyntaxError) as caught:
        load_workflow_definition(pipeline, units_path=tmp_path / "UNITS.csv")

    assert caught.value.codes == {"duplicate_yaml_key"}
    assert "`name`" in str(caught.value)


def test_pipeline_and_units_projection_drift_is_reported_together(
    tmp_path: Path,
) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[output/expected.md]",
        target_artifacts="[output/expected.md]",
        unit_rows=(
            "U001,Do work,META,beta,,output/actual.md,check it,C0,TODO,,CODEX\n",
        ),
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, repo_root=tmp_path, units_path=units)

    assert {
        "unit_skill_stage_drift",
        "unit_output_stage_drift",
        "stage_skill_units_drift",
        "stage_output_units_drift",
    }.issubset(caught.value.codes)
    rendered = str(caught.value)
    assert "skill `beta`" in rendered
    assert "output/actual.md" in rendered


def test_duplicate_ids_missing_dependencies_and_cycles_are_explicit(
    tmp_path: Path,
) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        unit_rows=(
            "U001,First,META,alpha,,output/result.md,check,C0,TODO,U002,CODEX\n",
            "U002,Second,META,alpha,,,check,C0,TODO,U001;U999,CODEX\n",
            "U001,Duplicate,META,alpha,,,check,C0,TODO,,CODEX\n",
        ),
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert {
        "duplicate_unit_id",
        "unknown_unit_dependency",
        "unit_dependency_cycle",
    }.issubset(caught.value.codes)


def test_completion_check_must_name_a_required_workflow_skill(tmp_path: Path) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        required_checks="[not-declared]",
        unit_rows=("U001,Do work,META,alpha,,output/result.md,check,C0,TODO,,CODEX\n",),
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert "required_check_skill_drift" in caught.value.codes
    assert "not-declared" in str(caught.value)


def test_unit_inputs_cannot_escape_the_workspace(tmp_path: Path) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        unit_rows=(
            "U001,Do work,META,alpha,../outside.md,output/result.md,check,C0,TODO,,CODEX\n",
        ),
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert "unsafe_artifact_path" in caught.value.codes
    assert "row 2.inputs" in str(caught.value)


def test_unit_inputs_may_name_a_workspace_directory(tmp_path: Path) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        unit_rows=(
            "U001,Do work,META,alpha,sections/,output/result.md,check,C0,TODO,,CODEX\n",
        ),
    )

    workflow = load_workflow_definition(pipeline, units_path=units)

    assert workflow.units[0].inputs == ("sections/",)


def test_repo_root_confines_the_selected_pipeline(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    outside = tmp_path / "outside"
    repo_root.mkdir()
    pipeline, units = _write_contract(
        outside,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        unit_rows=("U001,Do work,META,alpha,,output/result.md,check,C0,TODO,,CODEX\n",),
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(
            pipeline,
            repo_root=repo_root,
            units_path=units,
            skill_catalog={"alpha"},
            quality_check_catalog={"alpha"},
        )

    assert "pipeline_outside_allowed_root" in caught.value.codes


@pytest.mark.parametrize("reference_kind", ("absolute", "relative"))
def test_repo_root_confines_variant_parents(
    tmp_path: Path,
    reference_kind: str,
) -> None:
    repo_root = tmp_path / "repo"
    pipeline_dir = repo_root / "pipelines"
    pipeline_dir.mkdir(parents=True)
    outside = tmp_path / "outside"
    base, _ = _write_contract(
        outside,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        unit_rows=("U001,Do work,META,alpha,,output/result.md,check,C0,TODO,,CODEX\n",),
    )
    reference = (
        str(base)
        if reference_kind == "absolute"
        else "../../outside/example.pipeline.md"
    )
    variant = pipeline_dir / "escaped.pipeline.md"
    variant.write_text(
        "---\n"
        "name: escaped\n"
        "version: 2\n"
        f"variant_of: {reference}\n"
        "variant_overrides:\n"
        "  profile: escaped\n"
        "---\n",
        encoding="utf-8",
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(
            variant,
            repo_root=repo_root,
            skill_catalog={"alpha"},
            quality_check_catalog={"alpha"},
        )

    assert "variant_outside_allowed_root" in caught.value.codes


def test_repo_root_rejects_automatic_units_symlink_escape(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    pipeline, units = _write_contract(
        repo_root,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        unit_rows=("U001,Do work,META,alpha,,output/result.md,check,C0,TODO,,CODEX\n",),
    )
    outside_units = tmp_path / "outside.csv"
    outside_units.write_bytes(units.read_bytes())
    units.unlink()
    units.symlink_to(outside_units)

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(
            pipeline,
            repo_root=repo_root,
            skill_catalog={"alpha"},
            quality_check_catalog={"alpha"},
        )

    assert "units_outside_allowed_root" in caught.value.codes


def test_allowed_root_confines_an_explicit_units_symlink(tmp_path: Path) -> None:
    allowed_root = tmp_path / "allowed"
    pipeline, units = _write_contract(
        allowed_root,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        unit_rows=("U001,Do work,META,alpha,,output/result.md,check,C0,TODO,,CODEX\n",),
    )
    outside_units = tmp_path / "outside.csv"
    outside_units.write_bytes(units.read_bytes())
    units.unlink()
    units.symlink_to(outside_units)

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(
            pipeline,
            units_path=units,
            allowed_root=allowed_root,
        )

    assert "units_outside_allowed_root" in caught.value.codes


def test_repository_catalogs_are_injectable_and_fail_closed(tmp_path: Path) -> None:
    pipeline, _ = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        unit_rows=("U001,Do work,META,alpha,,output/result.md,check,C0,TODO,,CODEX\n",),
    )

    with pytest.raises(WorkflowValidationError) as missing_skill:
        load_workflow_definition(
            pipeline,
            repo_root=tmp_path,
            quality_check_catalog={"alpha"},
        )
    assert "unknown_workflow_skill" in missing_skill.value.codes

    skill_dir = tmp_path / ".codex" / "skills" / "alpha"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Alpha\n", encoding="utf-8")
    workflow = load_workflow_definition(
        pipeline,
        repo_root=tmp_path,
        quality_check_catalog={"alpha"},
    )
    assert workflow.skills == ("alpha",)

    with pytest.raises(WorkflowValidationError) as missing_check:
        load_workflow_definition(
            pipeline,
            repo_root=tmp_path,
            quality_check_catalog=set(),
        )
    assert "unregistered_quality_check" in missing_check.value.codes


def test_capability_validation_modes_make_structural_only_loading_explicit(
    tmp_path: Path,
) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        unit_rows=("U001,Do work,META,alpha,,output/result.md,check,C0,TODO,,CODEX\n",),
    )

    auto = load_workflow_definition(pipeline, units_path=units)
    structural = load_workflow_definition(
        pipeline,
        units_path=units,
        validate_capabilities="structural",
    )
    assert auto.name == "example"
    assert structural.name == "example"
    assert structural.case_contract == auto.case_contract

    with pytest.raises(WorkflowValidationError) as unavailable:
        load_workflow_definition(
            pipeline,
            units_path=units,
            validate_capabilities="required",
        )
    assert {
        "skill_catalog_unavailable",
        "quality_check_catalog_unavailable",
    }.issubset(unavailable.value.codes)

    workflow = load_workflow_definition(
        pipeline,
        units_path=units,
        skill_catalog={"alpha"},
        quality_check_catalog={"alpha"},
        validate_capabilities="required",
    )
    assert workflow.skills == ("alpha",)

    with pytest.raises(WorkflowValidationError) as conflicting:
        load_workflow_definition(
            pipeline,
            units_path=units,
            skill_catalog={"alpha"},
            validate_capabilities="structural",
        )
    assert "structural_capability_mode_conflict" in conflicting.value.codes


def test_required_checks_must_be_nonempty(tmp_path: Path) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        required_checks="[]",
        unit_rows=("U001,Do work,META,alpha,,output/result.md,check,C0,TODO,,CODEX\n",),
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert "empty_pipeline_list" in caught.value.codes


def test_case_contract_mapping_is_required(tmp_path: Path) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        case_contract="",
        unit_rows=("U001,Do work,META,alpha,,output/result.md,check,C0,TODO,,CODEX\n",),
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert "missing_pipeline_field" in caught.value.codes
    assert "case_contract" in str(caught.value)


@pytest.mark.parametrize(
    "missing_field",
    ("kind", "views", "claim_sources", "evidence_sources", "decision_sources"),
)
def test_case_contract_requires_all_five_fields(
    tmp_path: Path,
    missing_field: str,
) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        case_contract=_case_contract_yaml(omit=frozenset({missing_field})),
        unit_rows=("U001,Do work,META,alpha,,output/result.md,check,C0,TODO,,CODEX\n",),
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert "missing_pipeline_field" in caught.value.codes
    assert f"case_contract.{missing_field}" in str(caught.value)


@pytest.mark.parametrize(
    "field",
    ("views", "claim_sources", "evidence_sources", "decision_sources"),
)
def test_case_contract_path_lists_must_be_nonempty(
    tmp_path: Path,
    field: str,
) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        case_contract=_case_contract_yaml(**{field: "[]"}),
        unit_rows=("U001,Do work,META,alpha,,output/result.md,check,C0,TODO,,CODEX\n",),
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert "empty_pipeline_list" in caught.value.codes
    assert f"case_contract.{field}" in str(caught.value)


@pytest.mark.parametrize("kind", ("x" * 65, "123", "''", "unknown"))
def test_case_contract_kind_must_be_stable_short_text(
    tmp_path: Path, kind: str
) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        case_contract=_case_contract_yaml(kind=kind),
        unit_rows=("U001,Do work,META,alpha,,output/result.md,check,C0,TODO,,CODEX\n",),
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert "invalid_case_kind" in caught.value.codes


def test_builtin_workflow_case_kind_cannot_drift(tmp_path: Path) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        case_contract=_case_contract_yaml(kind="tutorial"),
        unit_rows=("U001,Do work,META,alpha,,output/result.md,check,C0,TODO,,CODEX\n",),
    )
    pipeline.write_text(
        pipeline.read_text(encoding="utf-8").replace(
            "name: example\n", "name: paper-review\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert "case_kind_workflow_drift" in caught.value.codes


def test_case_contract_paths_are_unique_safe_targets(tmp_path: Path) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        case_contract=_case_contract_yaml(
            views="[output/result.md, output/result.md]",
            claim_sources="[output/not-a-target.md]",
            evidence_sources="[../escape.md]",
        ),
        unit_rows=("U001,Do work,META,alpha,,output/result.md,check,C0,TODO,,CODEX\n",),
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert {
        "duplicate_contract_value",
        "unsafe_artifact_path",
        "case_contract_target_drift",
    }.issubset(caught.value.codes)


def test_case_contract_rejects_unknown_fields(tmp_path: Path) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[output/result.md]",
        target_artifacts="[output/result.md]",
        case_contract=_case_contract_yaml() + "  normalized_claims: true\n",
        unit_rows=("U001,Do work,META,alpha,,output/result.md,check,C0,TODO,,CODEX\n",),
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert "unexpected_case_contract_field" in caught.value.codes


@pytest.mark.parametrize(
    ("yaml_path", "unit_path"),
    (
        (".", "."),
        ("output/./result.md", "output/./result.md"),
        (r"C:\escape.md", r"C:\escape.md"),
        ("output;escape.md", "output;escape.md"),
        ('"output/\\u007fresult.md"', "output/\x7fresult.md"),
    ),
)
def test_artifact_paths_match_skill_runtime_grammar(
    tmp_path: Path,
    yaml_path: str,
    unit_path: str,
) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces=f"[{yaml_path}]",
        target_artifacts=f"[{yaml_path}]",
        unit_rows=(f"U001,Do work,META,alpha,,{unit_path},check,C0,TODO,,CODEX\n",),
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert "unsafe_artifact_path" in caught.value.codes


def test_human_checkpoint_requires_an_approval_prompt(tmp_path: Path) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[human-checkpoint]",
        produces="[DECISIONS.md]",
        target_artifacts="[DECISIONS.md]",
        required_checks="[human-checkpoint]",
        unit_rows=(
            "U001,Approve,META,human-checkpoint,DECISIONS.md,DECISIONS.md,approve,C0,TODO,,HUMAN\n",
        ),
    )
    pipeline.write_text(
        pipeline.read_text(encoding="utf-8").replace(
            "    produces: [DECISIONS.md]\n---\n",
            "    produces: [DECISIONS.md]\n"
            "    human_checkpoint:\n"
            "      write_to: DECISIONS.md\n"
            "---\n",
        ),
        encoding="utf-8",
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert "human_checkpoint_prompt_missing" in caught.value.codes


@pytest.mark.parametrize(
    ("skill", "owner"),
    (("human-checkpoint", "CODEX"), ("alpha", "HUMAN")),
)
def test_human_controlled_stage_requires_a_human_checkpoint_block(
    tmp_path: Path,
    skill: str,
    owner: str,
) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills=f"[{skill}]",
        produces="[DECISIONS.md]",
        target_artifacts="[DECISIONS.md]",
        required_checks=f"[{skill}]",
        unit_rows=(
            f"U001,Approval,META,{skill},DECISIONS.md,DECISIONS.md,approve,C0,TODO,,{owner}\n",
        ),
    )

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert "human_checkpoint_contract_missing" in caught.value.codes


def test_human_checkpoint_accepts_an_alternative_human_skill(tmp_path: Path) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[approval-review]",
        produces="[DECISIONS.md]",
        target_artifacts="[DECISIONS.md]",
        required_checks="[approval-review]",
        unit_rows=(
            "U001,Approval,META,approval-review,DECISIONS.md,DECISIONS.md,approve,C0,TODO,,HUMAN\n",
        ),
    )
    _add_human_checkpoint(pipeline)

    workflow = load_workflow_definition(pipeline, units_path=units)

    assert workflow.stages[0].human_checkpoint["write_to"] == "DECISIONS.md"
    assert workflow.units[0].skill == "approval-review"
    assert workflow.units[0].owner == "HUMAN"


def test_human_checkpoint_requires_a_human_owned_unit(tmp_path: Path) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[alpha]",
        produces="[DECISIONS.md]",
        target_artifacts="[DECISIONS.md]",
        required_checks="[alpha]",
        unit_rows=(
            "U001,Approval,META,alpha,DECISIONS.md,DECISIONS.md,approve,C0,TODO,,CODEX\n",
        ),
    )
    _add_human_checkpoint(pipeline)

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert "human_checkpoint_unit_drift" in caught.value.codes


@pytest.mark.parametrize(
    ("inputs", "outputs"),
    (("", "DECISIONS.md"), ("DECISIONS.md", "")),
)
def test_human_checkpoint_unit_must_read_and_write_decisions(
    tmp_path: Path,
    inputs: str,
    outputs: str,
) -> None:
    pipeline, units = _write_contract(
        tmp_path,
        required_skills="[approval-review]",
        produces="[DECISIONS.md]",
        target_artifacts="[DECISIONS.md]",
        required_checks="[approval-review]",
        unit_rows=(
            f"U001,Approval,META,approval-review,{inputs},{outputs},approve,C0,TODO,,HUMAN\n",
        ),
    )
    _add_human_checkpoint(pipeline)

    with pytest.raises(WorkflowValidationError) as caught:
        load_workflow_definition(pipeline, units_path=units)

    assert "human_checkpoint_artifact_drift" in caught.value.codes


def _add_human_checkpoint(pipeline: Path) -> None:
    pipeline.write_text(
        pipeline.read_text(encoding="utf-8").replace(
            "    produces: [DECISIONS.md]\n---\n",
            "    produces: [DECISIONS.md]\n"
            "    human_checkpoint:\n"
            "      approve: Approve checkpoint\n"
            "      write_to: DECISIONS.md\n"
            "---\n",
        ),
        encoding="utf-8",
    )


def _write_contract(
    tmp_path: Path,
    *,
    required_skills: str,
    produces: str,
    target_artifacts: str,
    unit_rows: tuple[str, ...],
    required_checks: str = "[alpha]",
    case_contract: str | None = None,
) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    pipeline = tmp_path / "example.pipeline.md"
    units = tmp_path / "UNITS.csv"
    if case_contract is None:
        case_contract = _case_contract_yaml(
            views=target_artifacts,
            claim_sources=target_artifacts,
            evidence_sources=target_artifacts,
            decision_sources=target_artifacts,
        )
    pipeline.write_text(
        "---\n"
        "contract_model: pipeline.frontmatter/v1\n"
        "name: example\n"
        "version: 1\n"
        "profile: example\n"
        "units_template: UNITS.csv\n"
        "default_checkpoints: [C0]\n"
        f"target_artifacts: {target_artifacts}\n"
        f"{case_contract}"
        "quality_contract:\n"
        "  completion_policy:\n"
        f"    required_checks: {required_checks}\n"
        "stages:\n"
        "  C0:\n"
        "    title: Example\n"
        "    checkpoint: C0\n"
        "    mode: no_prose\n"
        f"    required_skills: {required_skills}\n"
        "    optional_skills: []\n"
        f"    produces: {produces}\n"
        "---\n",
        encoding="utf-8",
    )
    units.write_text(UNIT_HEADER + "".join(unit_rows), encoding="utf-8")
    return pipeline, units


def _case_contract_yaml(
    *,
    kind: str = "brief",
    views: str = "[output/result.md]",
    claim_sources: str = "[output/result.md]",
    evidence_sources: str = "[output/result.md]",
    decision_sources: str = "[output/result.md]",
    omit: frozenset[str] = frozenset(),
) -> str:
    values = {
        "kind": kind,
        "views": views,
        "claim_sources": claim_sources,
        "evidence_sources": evidence_sources,
        "decision_sources": decision_sources,
    }
    return "case_contract:\n" + "".join(
        f"  {field}: {value}\n" for field, value in values.items() if field not in omit
    )
