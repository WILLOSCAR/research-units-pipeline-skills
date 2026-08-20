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

from .quality_provider import QualityCheckProvider, QualityIssueLike


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
