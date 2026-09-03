from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class LoopContract:
    """Read-only Loop projection metadata over existing Workflow Artifacts.

    The paths identify current Workflow outputs that a Loop reader may project.
    They do not make those Artifacts canonical Run state or imply that claim or
    evidence contents share a normalized schema.
    """

    kind: str
    views: tuple[str, ...]
    claim_sources: tuple[str, ...]
    evidence_sources: tuple[str, ...]
    decision_sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UnitDefinition:
    """One deliverable and its execution dependencies."""

    id: str
    title: str
    type: str
    skill: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    acceptance: str
    checkpoint: str
    status: str
    depends_on: tuple[str, ...]
    owner: str

    @property
    def required_outputs(self) -> tuple[str, ...]:
        return tuple(output for output in self.outputs if not output.startswith("?"))

    @property
    def optional_outputs(self) -> tuple[str, ...]:
        return tuple(output[1:] for output in self.outputs if output.startswith("?"))


@dataclass(frozen=True, slots=True)
class StageDefinition:
    """The Pipeline declaration for one ordered checkpoint."""

    id: str
    title: str
    checkpoint: str
    mode: str
    required_skills: tuple[str, ...]
    optional_skills: tuple[str, ...]
    produces: tuple[str, ...]
    human_checkpoint: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """The single validated view of Pipeline frontmatter and its UNITS table."""

    source: Path
    units_source: Path
    name: str
    version: str
    profile: str
    contract_model: str
    units_template: str
    default_checkpoints: tuple[str, ...]
    target_artifacts: tuple[str, ...]
    case_contract: LoopContract
    stages: tuple[StageDefinition, ...]
    units: tuple[UnitDefinition, ...]
    quality_contract: Mapping[str, Any]
    variant_of: str = ""

    @property
    def skills(self) -> tuple[str, ...]:
        skills = _ordered_unique(
            skill
            for stage in self.stages
            for skill in (*stage.required_skills, *stage.optional_skills)
        )
        unit_only_skills = _ordered_unique(unit.skill for unit in self.units)
        return _ordered_unique((*skills, *unit_only_skills))

    @property
    def dag(self) -> Mapping[str, tuple[str, ...]]:
        return MappingProxyType({unit.id: unit.depends_on for unit in self.units})

    @property
    def checks(self) -> tuple[str, ...]:
        completion_policy = self.quality_contract.get("completion_policy", {})
        if not isinstance(completion_policy, Mapping):
            return ()
        raw_checks = completion_policy.get("required_checks", ())
        return tuple(raw_checks) if isinstance(raw_checks, tuple) else ()


def _ordered_unique(values: Iterable[object]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value)
        if text not in seen:
            seen.add(text)
            ordered.append(text)
    return tuple(ordered)
