"""Typed acceptance Port for deterministic quality-check providers.

This module declares the seam that the acceptance layer needs from any
quality-check backend, expressed entirely inside ``research_harness``.  It
does not import ``tooling``: concrete backends implement
:class:`QualityCheckProvider` and are injected as adapters.  Two
implementations ship in this package -- ``NativeQualityProvider`` (the
tooling-free default) and ``LegacyToolingQualityProvider`` (a transitional
adapter over ``tooling.quality_gate``, retained as a reversible escape
hatch).

Signatures mirror the module-level functions in ``tooling.quality_gate`` so a
backend can be swapped in without touching call sites.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


class QualityIssueLike(Protocol):
    """Structural view of a single quality issue.

    Both the legacy ``tooling.quality_checks.common.QualityIssue`` dataclass
    and any future native issue type satisfy this shape, so the acceptance
    layer never needs to import a concrete issue class.
    """

    code: str
    message: str


@runtime_checkable
class QualityCheckProvider(Protocol):
    """Port for the deterministic quality checks the acceptance layer needs.

    Methods mirror the current ``tooling.quality_gate`` functions exactly so
    the coupling is expressed as this single named seam plus one adapter.
    """

    def registered_quality_skills(self) -> frozenset[str]:
        """Skills with semantic checks beyond output existence."""
        ...

    def has_completion_invariant(self, skill: str) -> bool:
        """Whether the Skill has a registered mandatory completion invariant."""
        ...

    def check_completion_invariants(
        self, *, skill: str, workspace: Path, outputs: list[str]
    ) -> list[QualityIssueLike]:
        """Run mandatory Workflow-domain invariants for the Skill."""
        ...

    def check_unit_outputs(
        self, *, skill: str, workspace: Path, outputs: list[str]
    ) -> list[QualityIssueLike]:
        """Run the Skill's registered semantic output checks."""
        ...
