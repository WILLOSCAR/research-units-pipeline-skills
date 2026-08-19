from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping, Protocol

from research_harness.domain.model import (
    AcceptanceEvidence,
    ArtifactEvidence,
    RunView,
    UnitPlan,
)


_MAX_EVALUATOR_ISSUES = 16
_MAX_EVALUATOR_ISSUE_CHARS = 1_000
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?P<prefix>(?<![\w])['\"]?"
    r"(?:secret|token|password|api[_-]?key)['\"]?\s*[:=]\s*)"
    r"(?P<value>\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;]+)"
)
_QUOTED_ABSOLUTE_PATH = re.compile(
    r'''(?:"(?:file://)?(?:/|[A-Za-z]:[\\/])[^"\r\n]*"'''
    r"""|'(?:file://)?(?:/|[A-Za-z]:[\\/])[^'\r\n]*' """
    r"""|`(?:file://)?(?:/|[A-Za-z]:[\\/])[^`\r\n]*`)""",
    re.VERBOSE,
)
_FILE_URI = re.compile(r"(?<![\w])file:///[^\s,;)\]}]+")
_UNQUOTED_ABSOLUTE_PATH = re.compile(
    r"(?<![\w:/.])(?:[A-Za-z]:[\\/]|/(?!/))[^\r\n,;)\]}]+"
)


@dataclass(frozen=True, slots=True)
class AcceptanceRequest:
    """Pure input presented to one Workflow acceptance evaluator."""

    run: RunView
    unit: UnitPlan
    artifacts: tuple[ArtifactEvidence, ...]


class AcceptanceEvaluator(Protocol):
    """Adapter seam for one deterministic, versioned quality evaluator."""

    def evaluate(self, request: AcceptanceRequest) -> AcceptanceEvidence: ...


class WorkflowAcceptancePolicy:
    """Exact, fail-closed Workflow acceptance at the Harness seam.

    Non-required Skills without a binding pass without attesting any check.
    Required checks need an exact Workflow/Skill evaluator, a passing result,
    and exact self-attestation by Skill name.  One immutable mapping replaces
    the former catalog-to-registry double lookup.
    """

    def __init__(
        self,
        *,
        evaluators: Mapping[tuple[str, str], AcceptanceEvaluator],
    ) -> None:
        resolved: dict[tuple[str, str], AcceptanceEvaluator] = {}
        for key, evaluator in evaluators.items():
            if (
                not isinstance(key, tuple)
                or len(key) != 2
                or not all(isinstance(value, str) and value.strip() for value in key)
            ):
                raise ValueError(
                    "Acceptance evaluator keys must be (workflow, skill) text pairs."
                )
            if not callable(getattr(evaluator, "evaluate", None)):
                raise TypeError("Acceptance evaluators must implement evaluate().")
            resolved[(key[0].strip(), key[1].strip())] = evaluator
        self._evaluators = MappingProxyType(resolved)

    def evaluate(
        self,
        *,
        run: RunView,
        unit: UnitPlan,
        artifacts: tuple[ArtifactEvidence, ...],
    ) -> AcceptanceEvidence:
        required = unit.skill in run.goal.required_checks
        evaluator = self._evaluators.get((run.goal.workflow, unit.skill))
        if evaluator is None:
            if required:
                return AcceptanceEvidence(
                    passed=False,
                    issues=(
                        f"Required checker {unit.skill} has no configured "
                        "acceptance evaluator.",
                    ),
                )
            return AcceptanceEvidence(passed=True)

        try:
            evidence = evaluator.evaluate(
                AcceptanceRequest(run=run, unit=unit, artifacts=artifacts)
            )
        except Exception as exc:
            return AcceptanceEvidence(
                passed=False,
                issues=(
                    f"Acceptance evaluator for {run.goal.workflow}/{unit.skill} "
                    "failed with "
                    f"{type(exc).__name__}.",
                ),
            )
        if not isinstance(evidence, AcceptanceEvidence):
            return AcceptanceEvidence(
                passed=False,
                issues=(
                    f"Acceptance evaluator for {run.goal.workflow}/{unit.skill} "
                    "returned an invalid result.",
                ),
            )
        sanitized_issues = _sanitize_evaluator_issues(evidence.issues)
        self_attested = unit.skill in evidence.checks
        if required and evidence.passed and not self_attested:
            return AcceptanceEvidence(
                passed=False,
                issues=_sanitize_evaluator_issues(
                    (
                        f"Required checker {unit.skill} did not exactly self-attest.",
                        *sanitized_issues,
                    )
                ),
            )
        return AcceptanceEvidence(
            passed=evidence.passed,
            checks=(unit.skill,) if self_attested else (),
            issues=sanitized_issues,
        )


def _sanitize_evaluator_issues(
    issues: Iterable[object],
    *,
    absolute_roots: Iterable[object] = (),
) -> tuple[str, ...]:
    roots = tuple(
        str(root).strip().rstrip("/\\")
        for root in absolute_roots
        if str(root).strip().rstrip("/\\")
    )
    sanitized: list[str] = []
    for raw_issue in issues:
        if len(sanitized) == _MAX_EVALUATOR_ISSUES:
            break
        issue = " ".join(str(raw_issue or "").split())
        for root in roots:
            issue = issue.replace(root, "<path>")
        issue = _QUOTED_ABSOLUTE_PATH.sub("<path>", issue)
        issue = _FILE_URI.sub("<path>", issue)
        issue = _UNQUOTED_ABSOLUTE_PATH.sub("<path>", issue)
        issue = _SECRET_ASSIGNMENT.sub(
            lambda match: f"{match.group('prefix')}<redacted>",
            issue,
        )
        if not issue:
            issue = "Acceptance evaluator reported an unspecified issue."
        if len(issue) > _MAX_EVALUATOR_ISSUE_CHARS:
            issue = issue[: _MAX_EVALUATOR_ISSUE_CHARS - 3] + "..."
        sanitized.append(issue)
    return tuple(sanitized)
