from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from research_harness.workflows import UnitDefinition, WorkflowDefinition
from tooling.pipeline_spec import PipelineSpec


WORKFLOW_PARITY_FIELDS = (
    "name",
    "version",
    "profile",
    "contract_model",
    "checkpoints",
    "targets",
    "stages",
    "units",
    "skills",
    "outputs",
    "checks",
    "dag",
)

_CANONICAL_UNIT_COLUMNS = (
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
_SEMICOLON_UNIT_COLUMNS = frozenset({"inputs", "outputs", "depends_on"})


@dataclass(frozen=True, slots=True)
class WorkflowParityDifference:
    """One differing projection from the legacy and typed Workflow readers."""

    field: str
    legacy_value: object
    typed_value: object


@dataclass(frozen=True, slots=True)
class WorkflowParityReport:
    """Read-only evidence that two Workflow readers preserve the same contract."""

    workflow: str
    pipeline_source: Path
    units_source: Path
    checked_fields: tuple[str, ...]
    differences: tuple[WorkflowParityDifference, ...]

    @property
    def matches(self) -> bool:
        return not self.differences

    @property
    def differing_fields(self) -> tuple[str, ...]:
        return tuple(difference.field for difference in self.differences)


@dataclass(frozen=True, slots=True)
class _WorkflowParityProjection:
    name: object
    version: object
    profile: object
    contract_model: object
    checkpoints: object
    targets: object
    stages: object
    units: object
    skills: object
    outputs: object
    checks: object
    dag: object


def check_workflow_legacy_parity(workflow: WorkflowDefinition) -> WorkflowParityReport:
    """Compare one typed definition with the legacy Pipeline + UNITS readers.

    This migration checker performs no writes. Parsing and I/O exceptions from
    either reader are deliberately allowed to propagate because a failed read
    is not evidence of parity.
    """

    legacy_spec = PipelineSpec.load(workflow.source)
    legacy_units = _read_legacy_units(workflow.units_source)
    legacy = _legacy_projection(legacy_spec, legacy_units)
    typed = _typed_projection(workflow)

    differences = tuple(
        WorkflowParityDifference(
            field=field,
            legacy_value=getattr(legacy, field),
            typed_value=getattr(typed, field),
        )
        for field in WORKFLOW_PARITY_FIELDS
        if getattr(legacy, field) != getattr(typed, field)
    )
    return WorkflowParityReport(
        workflow=workflow.name,
        pipeline_source=workflow.source,
        units_source=workflow.units_source,
        checked_fields=WORKFLOW_PARITY_FIELDS,
        differences=differences,
    )


def _legacy_projection(
    spec: PipelineSpec, units: tuple[dict[str, str], ...]
) -> _WorkflowParityProjection:
    stage_skills = tuple(
        (stage.id, stage.required_skills, stage.optional_skills)
        for stage in spec.stages.values()
    )
    unit_skills = tuple((row["unit_id"], row["skill"]) for row in units)
    all_skills = _ordered_unique(
        skill
        for stage in spec.stages.values()
        for skill in (*stage.required_skills, *stage.optional_skills)
    )
    all_skills = _ordered_unique((*all_skills, *(skill for _, skill in unit_skills)))

    return _WorkflowParityProjection(
        name=spec.name,
        version=spec.version,
        profile=spec.profile,
        contract_model=spec.contract_model,
        checkpoints=spec.default_checkpoints,
        targets=spec.target_artifacts,
        stages=tuple(
            (
                stage.id,
                stage.title,
                stage.checkpoint,
                stage.mode,
                _canonical(stage.human_checkpoint),
            )
            for stage in spec.stages.values()
        ),
        units=_legacy_units_projection(units),
        skills=(stage_skills, unit_skills, all_skills),
        outputs=(
            tuple((stage.id, stage.produces) for stage in spec.stages.values()),
            tuple((row["unit_id"], _semicolon_tuple(row["outputs"])) for row in units),
        ),
        checks=_legacy_required_checks(spec),
        dag=tuple(
            (row["unit_id"], _semicolon_tuple(row["depends_on"])) for row in units
        ),
    )


def _typed_projection(workflow: WorkflowDefinition) -> _WorkflowParityProjection:
    return _WorkflowParityProjection(
        name=workflow.name,
        version=workflow.version,
        profile=workflow.profile,
        contract_model=workflow.contract_model,
        checkpoints=workflow.default_checkpoints,
        targets=workflow.target_artifacts,
        stages=tuple(
            (
                stage.id,
                stage.title,
                stage.checkpoint,
                stage.mode,
                _canonical(stage.human_checkpoint),
            )
            for stage in workflow.stages
        ),
        units=_v2_units_projection(workflow.units),
        skills=(
            tuple(
                (stage.id, stage.required_skills, stage.optional_skills)
                for stage in workflow.stages
            ),
            tuple((unit.id, unit.skill) for unit in workflow.units),
            workflow.skills,
        ),
        outputs=(
            tuple((stage.id, stage.produces) for stage in workflow.stages),
            tuple((unit.id, unit.outputs) for unit in workflow.units),
        ),
        checks=workflow.checks,
        dag=tuple((unit.id, unit.depends_on) for unit in workflow.units),
    )


def _read_legacy_units(source: Path) -> tuple[dict[str, str], ...]:
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        if reader.fieldnames is None:
            raise ValueError(f"UNITS CSV has no header: {source}")
        missing = [
            column
            for column in _CANONICAL_UNIT_COLUMNS
            if column not in reader.fieldnames
        ]
        if missing:
            raise ValueError(
                f"UNITS CSV is missing parity column(s) in {source}: {', '.join(missing)}"
            )
        rows: list[dict[str, str]] = []
        for line_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    f"UNITS CSV row {line_number} has extra cells: {source}"
                )
            normalized: dict[str, str] = {}
            for key, value in row.items():
                if key is None or value is None:
                    raise ValueError(
                        f"UNITS CSV row {line_number} has a missing column value: {source}"
                    )
                normalized[key.strip()] = value.strip()
            rows.append(normalized)
    return tuple(rows)


def _legacy_units_projection(
    units: tuple[dict[str, str], ...],
) -> tuple[tuple[tuple[str, object], ...], ...]:
    return tuple(
        tuple(
            (
                column,
                _semicolon_tuple(row[column])
                if column in _SEMICOLON_UNIT_COLUMNS
                else row[column],
            )
            for column in _CANONICAL_UNIT_COLUMNS
        )
        for row in units
    )


def _v2_units_projection(
    units: tuple[UnitDefinition, ...],
) -> tuple[tuple[tuple[str, object], ...], ...]:
    return tuple(
        (
            ("unit_id", unit.id),
            ("title", unit.title),
            ("type", unit.type),
            ("skill", unit.skill),
            ("inputs", unit.inputs),
            ("outputs", unit.outputs),
            ("acceptance", unit.acceptance),
            ("checkpoint", unit.checkpoint),
            ("status", unit.status),
            ("depends_on", unit.depends_on),
            ("owner", unit.owner),
        )
        for unit in units
    )


def _legacy_required_checks(spec: PipelineSpec) -> tuple[str, ...]:
    completion_policy = spec.quality_contract.get("completion_policy")
    if completion_policy is None:
        return ()
    if not isinstance(completion_policy, Mapping):
        raise TypeError(
            "legacy quality_contract.completion_policy must be a mapping for parity"
        )
    required_checks = completion_policy.get("required_checks")
    if required_checks is None:
        return ()
    if not isinstance(required_checks, list):
        raise TypeError(
            "legacy quality_contract.completion_policy.required_checks must be a list for parity"
        )
    return tuple(str(check).strip() for check in required_checks if str(check).strip())


def _semicolon_tuple(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(";") if item.strip())


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _canonical(value: Any) -> object:
    if isinstance(value, Mapping):
        return tuple(
            (str(key), _canonical(item))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, (list, tuple)):
        return tuple(_canonical(item) for item in value)
    return value
