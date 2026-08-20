"""Transitional adapter for repository-local deterministic quality checks.

Deterministic quality functions and registry introspection enter through the
:class:`~.quality_provider.QualityCheckProvider` Port, defaulting to the
legacy ``tooling.quality_gate`` adapter.  The evaluator never asks legacy Run
state which checks are required; the validated Workflow is authoritative.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

from research_harness.domain.model import AcceptanceEvidence

from .legacy_tooling import default_quality_provider
from .policy import (
    AcceptanceRequest,
    WorkflowAcceptancePolicy,
    _sanitize_evaluator_issues,
)
from .quality_provider import QualityCheckProvider, QualityIssueLike

if TYPE_CHECKING:
    from research_harness.workflows import WorkflowDefinition


WorkspaceResolver: TypeAlias = Callable[[str], Path]
_MAX_ISSUES = 16
_MAX_CODE_CHARS = 96
_MAX_MESSAGE_CHARS = 512


@dataclass(frozen=True, slots=True)
class RepositoryQualityEvaluator:
    """Adapt current repository quality functions to ``AcceptanceEvaluator``."""

    workspace_for_run: WorkspaceResolver
    provider: QualityCheckProvider = field(default_factory=default_quality_provider)

    def evaluate(self, request: AcceptanceRequest) -> AcceptanceEvidence:
        workspace = Path(self.workspace_for_run(request.run.id)).expanduser().resolve()
        declared_outputs = set(request.unit.all_output_paths)
        outputs = [
            artifact.path
            for artifact in request.artifacts
            if artifact.path in declared_outputs
        ]
        issues = [
            *self.provider.check_completion_invariants(
                skill=request.unit.skill,
                workspace=workspace,
                outputs=outputs,
            ),
            *self.provider.check_unit_outputs(
                skill=request.unit.skill,
                workspace=workspace,
                outputs=outputs,
            ),
        ]
        bounded = _sanitize_evaluator_issues(
            _bounded_issues(issues),
            absolute_roots=(workspace,),
        )
        return AcceptanceEvidence(
            passed=not bounded,
            checks=(request.unit.skill,) if not bounded else (),
            issues=bounded,
        )


def build_repository_acceptance_policy(
    *,
    workflows: Iterable[WorkflowDefinition],
    workspace_for_run: WorkspaceResolver,
    provider: QualityCheckProvider | None = None,
) -> WorkflowAcceptancePolicy:
    """Build exact bindings from validated Workflows to current quality checks.

    Construction fails if a Workflow-required check has no registered quality
    check or completion invariant.  Registered non-required Skills are also
    bound, so their semantic checks run without gaining required-check status.

    ``provider`` selects the quality-check backend; it defaults to the legacy
    ``tooling.quality_gate`` adapter so runtime behavior is unchanged.
    """

    resolved_provider = provider or default_quality_provider()
    registered = resolved_provider.registered_quality_skills()
    evaluator = RepositoryQualityEvaluator(
        workspace_for_run=workspace_for_run,
        provider=resolved_provider,
    )
    evaluators: dict[
        tuple[str, str],
        RepositoryQualityEvaluator,
    ] = {}
    for workflow in workflows:
        supported = frozenset(
            skill
            for skill in workflow.skills
            if skill in registered
            or resolved_provider.has_completion_invariant(skill)
        )
        missing = tuple(skill for skill in workflow.checks if skill not in supported)
        if missing:
            raise ValueError(
                f"Workflow {workflow.name} has no repository acceptance evaluator "
                f"for required Skill(s): {', '.join(missing)}."
            )
        for skill in workflow.skills:
            if skill not in supported:
                continue
            evaluators[(workflow.name, skill)] = evaluator
    return WorkflowAcceptancePolicy(evaluators=evaluators)


def _bounded_issues(issues: Iterable[QualityIssueLike]) -> tuple[str, ...]:
    bounded: list[str] = []
    for issue in issues:
        if len(bounded) == _MAX_ISSUES:
            break
        code = _bounded_text(getattr(issue, "code", ""), _MAX_CODE_CHARS)
        message = _bounded_text(getattr(issue, "message", ""), _MAX_MESSAGE_CHARS)
        bounded.append(
            f"{code or 'quality_issue'}: {message or 'Acceptance check failed.'}"
        )
    return tuple(bounded)


def _bounded_text(value: object, limit: int) -> str:
    normalized = " ".join(str(value or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."
