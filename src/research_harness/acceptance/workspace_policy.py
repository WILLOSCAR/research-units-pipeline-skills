"""Typed acceptance Port for workspace-policy reads.

Several deterministic quality checks (the survey-retrieval / delivery family)
do not merely inspect a Unit's declared output file: they first read *workspace
policy* -- the run profile, evidence mode, core-set target, and the pipeline's
quality contract -- which today lives in ``PIPELINE.lock.md`` / ``queries.md``
resolved through the pipeline spec.  Those reads are the real coupling that
keeps such checks in ``tooling``.

This module declares the seam for that policy surface, expressed entirely
inside ``research_harness`` with no ``tooling`` import (mirroring
``quality_provider``).  A concrete backend implements
:class:`WorkspacePolicyPort` and is injected as an adapter; the transitional
implementation is ``LegacyToolingPolicyReader`` in ``legacy_tooling`` (the
single named seam that wraps ``tooling``).

The method surface is a deliberately small, coherent subset: the policy reads
the siblings of ``check_citation_injection`` in
``tooling.quality_checks.survey_retrieval`` depend on, plus the Goal-constraint
read the delivery ``latex-compile-qa`` check needs.  It is the seam that lets
those checks go native without hauling in the whole of ``tooling.common``.
Generic file readers (e.g. ``read_jsonl``) are intentionally *not* here: they
are not workspace policy.

Signatures mirror the module-level helpers in
``tooling.quality_checks.survey_policy`` and ``tooling.common`` exactly so a
future native reader can be swapped in without touching call sites.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class WorkspacePolicyPort(Protocol):
    """Port for the workspace-policy reads a native survey check would need.

    Methods mirror the current ``tooling.quality_checks.survey_policy`` /
    ``tooling.common`` functions exactly so the coupling is expressed as this
    single named seam plus one adapter.
    """

    def pipeline_profile_name(self, workspace: Path) -> str:
        """Return the run's pipeline profile (``"default"`` when unresolved)."""
        ...

    def evidence_mode(self, workspace: Path) -> str:
        """Return the run's research-evidence mode (``"abstract"`` or ``"fulltext"``)."""
        ...

    def core_size(self, workspace: Path) -> int:
        """Return the core-set size contract for the run."""
        ...

    def pipeline_quality_contract_value(
        self, workspace: Path, *keys: str, default: Any = None
    ) -> Any:
        """Return a nested value from the pipeline's quality contract, or ``default``."""
        ...

    def workspace_goal_constraints(self, workspace: Path) -> dict[str, Any]:
        """Return the run's structured Goal constraints (``{}`` when unresolved).

        Mirrors ``tooling.common.load_workspace_goal_constraints``: reads
        ``.harness/goal.json`` first, falling back to parsing ``GOAL.md``.  A
        native delivery check (``latex-compile-qa``) reads the ``page_range``
        constraint through this rather than importing ``tooling.common``.
        """
        ...
