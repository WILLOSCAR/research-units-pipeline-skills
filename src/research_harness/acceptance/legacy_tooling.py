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

- unset / empty / any unrecognized value -> ``native`` (the default; every
  registered check has a native equivalent proven byte-identical to legacy);
- ``"native"`` -> :class:`~.native.NativeQualityProvider`;
- ``"legacy"`` -> the transitional legacy adapter (retained escape hatch).

Parsing is deliberately defensive so a typo or stray value can never silently
revert to the legacy path: anything that is not exactly ``legacy`` (after strip
+ case-fold) resolves to native.  This is the single seam the cutover flipped.
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
#: other value -- including unset and empty -- resolves to ``native`` (default).
_QUALITY_PROVIDER_ENV_VAR = "RESEARCH_HARNESS_QUALITY_PROVIDER"

#: The provider selected when no valid opt-in is present.  Now ``native``:
#: every registered quality check has a byte-for-byte native equivalent (proven
#: by the 68-skill equivalence sweep, differential fuzzing, and per-module
#: adversarial audits), so the native provider is the default runtime backend.
#: Set ``RESEARCH_HARNESS_QUALITY_PROVIDER=legacy`` to revert to the transitional
#: ``tooling.quality_gate`` adapter (the escape hatch is retained for one release).
_DEFAULT_PROVIDER_CHOICE = "native"

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
    :data:`_DEFAULT_PROVIDER_CHOICE` (now ``native``), so an invalid opt-in can
    never silently fall back to the legacy path once native is the default.
    """

    source = os.environ if env is None else env
    raw = source.get(_QUALITY_PROVIDER_ENV_VAR, "")
    normalized = raw.strip().casefold()
    if normalized in _KNOWN_PROVIDER_CHOICES:
        return normalized
    return _DEFAULT_PROVIDER_CHOICE


def default_quality_provider() -> QualityCheckProvider:
    """Return the acceptance quality-check backend selected by the opt-in.

    The default is now :class:`~.native.NativeQualityProvider`: every registered
    quality check has a native equivalent proven byte-for-byte identical to the
    legacy ``tooling.quality_gate`` path.  Setting
    ``RESEARCH_HARNESS_QUALITY_PROVIDER=legacy`` reverts to the transitional
    legacy adapter (the retained escape hatch); any other value (including unset
    or unrecognized) resolves to native.

    Centralizing the choice here kept the cutover a one-line default change
    rather than an edit at every call site.
    """

    if _selected_provider_choice() == "native":
        # Lazy import: ``native`` imports from this module, so importing it at
        # top level would create a cycle.
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

    def workspace_goal_constraints(self, workspace: Path) -> dict[str, Any]:
        from tooling.common import load_workspace_goal_constraints

        return load_workspace_goal_constraints(workspace)

    def has_pipeline_contract(self, workspace: Path) -> bool:
        from tooling.common import load_workspace_pipeline_spec

        return load_workspace_pipeline_spec(workspace) is not None

    def resolve_idea_contract(self, workspace: Path) -> dict[str, Any]:
        from tooling.ideation import resolve_idea_contract

        return resolve_idea_contract(workspace)

    def evaluate_paper_review(self, workspace: Path) -> dict[str, Any]:
        from tooling.review_evaluation import evaluate_paper_review

        return evaluate_paper_review(workspace)

    def evaluate_evidence_review(self, workspace: Path) -> dict[str, Any]:
        from tooling.evidence_review_evaluation import evaluate_evidence_review

        return evaluate_evidence_review(workspace)

    def draft_profile(self, workspace: Path) -> str:
        from tooling.quality_checks.survey_policy import draft_profile

        return draft_profile(workspace)

    def global_citation_min_subsections(self, workspace: Path) -> int:
        from tooling.quality_checks.survey_policy import global_citation_min_subsections

        return global_citation_min_subsections(workspace)

    def quality_contract_int(
        self, workspace: Path, *, keys: tuple[str, ...], default: int
    ) -> int:
        from tooling.quality_checks.survey_policy import quality_contract_int

        return quality_contract_int(workspace, keys=keys, default=default)

    def per_subsection(self, workspace: Path) -> int:
        from tooling.quality_checks.survey_policy import per_subsection

        return per_subsection(workspace)

    def template_residue_document_issues(
        self, workspace: Path, documents: list[tuple[str, str]]
    ) -> list[Any]:
        from tooling.quality_checks.template_residue import (
            check_template_residue_documents,
        )

        return check_template_residue_documents(
            workspace=workspace, documents=documents
        )

    def template_residue_subsection_issues(
        self, workspace: Path, relpaths: list[str]
    ) -> list[Any]:
        from tooling.quality_checks.template_residue import (
            check_subsection_template_residue,
        )

        return check_subsection_template_residue(
            workspace=workspace, relpaths=relpaths
        )

    def structure_mode(self, workspace: Path) -> str:
        from tooling.quality_checks.survey_structure import structure_mode

        return structure_mode(workspace)

    def section_first_artifact_issues(self, workspace: Path, *, consumer: str) -> list[Any]:
        from tooling.quality_checks.survey_structure import section_first_artifact_issues

        return section_first_artifact_issues(workspace, consumer=consumer)

    def section_first_cutover_issues(
        self, workspace: Path, *, consumer: str, require_stable_h3: bool
    ) -> list[Any]:
        from tooling.quality_checks.survey_structure import section_first_cutover_issues

        return section_first_cutover_issues(
            workspace, consumer=consumer, require_stable_h3=require_stable_h3
        )


def default_workspace_policy_reader() -> WorkspacePolicyPort:
    """Return the default (legacy) workspace-policy reader.

    Centralizes the choice of reader so a future native default is a one-line
    change here rather than at every call site.
    """

    return LegacyToolingPolicyReader()
