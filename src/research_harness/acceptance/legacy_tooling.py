"""Transitional adapter binding the acceptance Port to ``tooling.quality_gate``.

This is the *only* module in ``research_harness`` that imports the legacy
``tooling.quality_gate`` deterministic quality functions.  It exists so the
coupling is a single, named, replaceable seam: swapping in a native provider
later means implementing :class:`~.quality_provider.QualityCheckProvider`
elsewhere and injecting it, without editing acceptance call sites.

Imports from ``tooling`` stay lazy (inside methods) so isolated Workflow
parsing and acceptance construction remain independent of the legacy Harness
import graph until a check actually runs.

Provider selection
------------------
:func:`default_quality_provider` centralizes *which* backend the acceptance
layer uses.  It consults the ``RESEARCH_HARNESS_QUALITY_PROVIDER`` opt-in
environment variable (see :data:`_QUALITY_PROVIDER_ENV_VAR`):

- unset / empty / any unrecognized value -> ``legacy`` (the default; behavior
  is byte-for-byte identical to before this seam existed);
- ``"legacy"`` -> the transitional legacy adapter;
- ``"native"`` -> :class:`~.native.NativeQualityProvider`.

Parsing is deliberately defensive so a typo or stray value can never silently
change acceptance outcomes: anything that is not exactly ``native`` (after
strip + case-fold) resolves to legacy.  This is the single seam a future
cutover flips; nothing wires native as the default today.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .quality_provider import QualityCheckProvider, QualityIssueLike
from .workspace_policy import WorkspacePolicyPort

#: Opt-in environment variable selecting the acceptance quality-check backend.
#: Recognized (case-insensitive) values are ``legacy`` and ``native``; every
#: other value -- including unset and empty -- resolves to ``legacy``.
_QUALITY_PROVIDER_ENV_VAR = "RESEARCH_HARNESS_QUALITY_PROVIDER"

#: The provider selected when no valid opt-in is present.
_DEFAULT_PROVIDER_CHOICE = "legacy"

#: The full set of recognized selector values.
_KNOWN_PROVIDER_CHOICES = frozenset({"legacy", "native"})


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


def _selected_provider_choice(env: Mapping[str, str] | None = None) -> str:
    """Resolve the opt-in selector to a recognized provider choice.

    Defensive by design: reads :data:`_QUALITY_PROVIDER_ENV_VAR`, strips
    surrounding whitespace, case-folds, and returns it only if it is a known
    choice.  Anything else -- unset, empty, whitespace, a typo -- resolves to
    :data:`_DEFAULT_PROVIDER_CHOICE` (``legacy``), so an invalid opt-in can
    never silently change acceptance outcomes.
    """

    source = os.environ if env is None else env
    raw = source.get(_QUALITY_PROVIDER_ENV_VAR, "")
    normalized = raw.strip().casefold()
    if normalized in _KNOWN_PROVIDER_CHOICES:
        return normalized
    return _DEFAULT_PROVIDER_CHOICE


def default_quality_provider() -> QualityCheckProvider:
    """Return the acceptance quality-check backend selected by the opt-in.

    With no opt-in set the result is the legacy adapter, so runtime behavior is
    identical to before this seam existed.  Setting
    ``RESEARCH_HARNESS_QUALITY_PROVIDER=native`` selects
    :class:`~.native.NativeQualityProvider` instead; every other value (unset,
    empty, or unrecognized) resolves to legacy.

    Centralizing the choice here keeps a future native cutover a one-line
    default change (or a documented opt-in flip) rather than an edit at every
    call site.
    """

    if _selected_provider_choice() == "native":
        # Lazy import: ``native`` imports from this module, so importing it at
        # top level would create a cycle.  It is only needed when opted in.
        from .native import NativeQualityProvider

        return NativeQualityProvider()
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
