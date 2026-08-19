from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path

import pytest

from research_harness.migration import (
    WORKFLOW_PARITY_FIELDS,
    check_workflow_legacy_parity,
)
from research_harness.workflows import load_workflow_definition


REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTABLE_WORKFLOWS = (
    "arxiv-survey-latex",
    "arxiv-survey",
    "evidence-review",
    "idea-brainstorm",
    "paper-review",
    "research-brief",
    "source-tutorial",
)
CANONICAL_UNIT_COLUMNS = (
    "unit_id",
    "title",
    "type",
    "skill",
    "inputs",
    "outputs",
    "acceptance",
    "checkpoint",
    "status",
    "depends_on",
    "owner",
)


@pytest.mark.parametrize("workflow_name", EXECUTABLE_WORKFLOWS)
def test_v2_workflow_reader_has_zero_legacy_projection_differences(
    workflow_name: str,
) -> None:
    workflow = load_workflow_definition(
        REPO_ROOT / "pipelines" / f"{workflow_name}.pipeline.md",
        repo_root=REPO_ROOT,
    )

    report = check_workflow_legacy_parity(workflow)

    assert report.matches
    assert report.differences == ()
    assert report.differing_fields == ()
    assert report.checked_fields == WORKFLOW_PARITY_FIELDS
    assert report.pipeline_source == workflow.source
    assert report.units_source == workflow.units_source


def test_one_intentionally_drifted_definition_reports_every_projection() -> None:
    workflow = load_workflow_definition(
        REPO_ROOT / "pipelines" / "paper-review.pipeline.md",
        repo_root=REPO_ROOT,
    )
    first_stage = replace(
        workflow.stages[0],
        title="Drifted stage",
        required_skills=(*workflow.stages[0].required_skills, "drifted-skill"),
        produces=(*workflow.stages[0].produces, "output/DRIFT.md"),
    )
    first_unit = replace(
        workflow.units[0],
        title="Drifted unit",
        type="DRIFTED",
        skill="drifted-skill",
        inputs=(*workflow.units[0].inputs, "output/DRIFT_INPUT.md"),
        outputs=(*workflow.units[0].outputs, "output/DRIFT.md"),
        acceptance="Drifted acceptance",
        checkpoint="C999",
        status="BLOCKED",
        depends_on=("U999",),
        owner="HUMAN",
    )
    drifted = replace(
        workflow,
        name="drifted-name",
        version="999",
        profile="drifted-profile",
        contract_model="drifted-contract-model",
        default_checkpoints=tuple(reversed(workflow.default_checkpoints)),
        target_artifacts=(*workflow.target_artifacts, "output/DRIFT.md"),
        stages=(first_stage, *workflow.stages[1:]),
        units=(first_unit, *workflow.units[1:]),
        quality_contract={"completion_policy": {"required_checks": ("drifted-check",)}},
    )

    report = check_workflow_legacy_parity(drifted)

    assert not report.matches
    assert report.differing_fields == WORKFLOW_PARITY_FIELDS
    differences = {difference.field: difference for difference in report.differences}
    assert differences["name"].legacy_value == "paper-review"
    assert differences["name"].typed_value == "drifted-name"
    assert differences["contract_model"].typed_value == "drifted-contract-model"
    assert "output/DRIFT.md" in differences["targets"].typed_value
    assert ("U001", ("U999",)) in differences["dag"].typed_value
    unit_projection = dict(differences["units"].typed_value[0])
    assert tuple(unit_projection) == CANONICAL_UNIT_COLUMNS
    assert unit_projection == {
        "unit_id": first_unit.id,
        "title": first_unit.title,
        "type": first_unit.type,
        "skill": first_unit.skill,
        "inputs": first_unit.inputs,
        "outputs": first_unit.outputs,
        "acceptance": first_unit.acceptance,
        "checkpoint": first_unit.checkpoint,
        "status": first_unit.status,
        "depends_on": first_unit.depends_on,
        "owner": first_unit.owner,
    }


def test_legacy_reader_exceptions_are_not_converted_to_false_parity(
    tmp_path: Path,
) -> None:
    workflow = load_workflow_definition(
        REPO_ROOT / "pipelines" / "paper-review.pipeline.md",
        repo_root=REPO_ROOT,
    )
    missing_legacy_source = replace(workflow, source=tmp_path / "missing.pipeline.md")

    with pytest.raises(FileNotFoundError):
        check_workflow_legacy_parity(missing_legacy_source)


@pytest.mark.parametrize("missing_column", CANONICAL_UNIT_COLUMNS)
def test_legacy_reader_requires_every_canonical_unit_column(
    tmp_path: Path,
    missing_column: str,
) -> None:
    workflow = load_workflow_definition(
        REPO_ROOT / "pipelines" / "paper-review.pipeline.md",
        repo_root=REPO_ROOT,
    )
    with workflow.units_source.open(encoding="utf-8-sig", newline="") as source_handle:
        source_rows = list(csv.DictReader(source_handle))
    columns = [column for column in CANONICAL_UNIT_COLUMNS if column != missing_column]
    incomplete_units = tmp_path / "UNITS.incomplete.csv"
    with incomplete_units.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(
            {column: row[column] for column in columns} for row in source_rows
        )

    with pytest.raises(ValueError, match=rf"missing parity column.*{missing_column}"):
        check_workflow_legacy_parity(replace(workflow, units_source=incomplete_units))
