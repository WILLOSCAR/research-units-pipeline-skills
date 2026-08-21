"""Transitional adapter binding the acceptance Port to ``tooling.quality_gate``.

This is the *only* module in ``research_harness`` that imports the legacy
``tooling.quality_gate`` deterministic quality functions.  It exists so the
coupling is a single, named, replaceable seam: swapping in a native provider
later means implementing :class:`~.quality_provider.QualityCheckProvider`
elsewhere and injecting it, without editing acceptance call sites.

Imports from ``tooling`` stay lazy (inside methods) so isolated Workflow
parsing and acceptance construction remain independent of the legacy Harness
import graph until a check actually runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .quality_provider import QualityCheckProvider, QualityIssueLike
from .workspace_policy import WorkspacePolicyPort


@dataclass(frozen=True, slots=True)
class LegacyToolingQualityProvider(QualityCheckProvider):
    """Delegate the acceptance Port to ``tooling.quality_gate``.

    Each method mirrors the corresponding ``tooling.quality_gate`` function
    exactly, so behavior is identical to importing that function directly.
    """

    def registered_quality_skills(self) -> frozenset[str]:
        from tooling.quality_gate import registered_quality_skills

        return registered_quality_skills()

    def has_completion_invariant(self, skill: str) -> bool:
        from tooling.quality_gate import has_completion_invariant

        return has_completion_invariant(skill)

    def check_completion_invariants(
        self, *, skill: str, workspace: Path, outputs: list[str]
    ) -> list[QualityIssueLike]:
        from tooling.quality_gate import check_completion_invariants

        return check_completion_invariants(
            skill=skill, workspace=workspace, outputs=outputs
        )

    def check_unit_outputs(
        self, *, skill: str, workspace: Path, outputs: list[str]
    ) -> list[QualityIssueLike]:
        from tooling.quality_gate import check_unit_outputs

        return check_unit_outputs(skill=skill, workspace=workspace, outputs=outputs)


def default_quality_provider() -> QualityCheckProvider:
    """Return the default (legacy) provider.

    Centralizes the choice of provider so a future native default is a
    one-line change here rather than at every call site.
    """

    return LegacyToolingQualityProvider()


@dataclass(frozen=True, slots=True)
class LegacyToolingPolicyReader(WorkspacePolicyPort):
    """Delegate the workspace-policy Port to ``tooling``.

    Each method mirrors the corresponding ``tooling.quality_checks.survey_policy``
    / ``tooling.common`` function exactly, so behavior is identical to importing
    that function directly.  Imports stay lazy (inside methods) so acceptance
    construction remains independent of the legacy import graph until a policy
    read actually runs -- matching ``LegacyToolingQualityProvider``.
    """

    def pipeline_profile_name(self, workspace: Path) -> str:
        from tooling.quality_checks.survey_policy import pipeline_profile_name

        return pipeline_profile_name(workspace)

    def evidence_mode(self, workspace: Path) -> str:
        from tooling.quality_checks.survey_policy import evidence_mode

        return evidence_mode(workspace)

    def core_size(self, workspace: Path) -> int:
        from tooling.quality_checks.survey_policy import core_size

        return core_size(workspace)

    def pipeline_quality_contract_value(
        self, workspace: Path, *keys: str, default: Any = None
    ) -> Any:
        from tooling.common import pipeline_quality_contract_value

        return pipeline_quality_contract_value(workspace, *keys, default=default)


def default_workspace_policy_reader() -> WorkspacePolicyPort:
    """Return the default (legacy) workspace-policy reader.

    Centralizes the choice of reader so a future native default is a one-line
    change here rather than at every call site.
    """

    return LegacyToolingPolicyReader()
