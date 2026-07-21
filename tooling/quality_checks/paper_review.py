from __future__ import annotations

from pathlib import Path

from tooling.quality_checks.common import QualityIssue
from tooling.review_evaluation import evaluate_paper_review


def _check_dimensions(workspace: Path, dimension_ids: tuple[str, ...]) -> list[QualityIssue]:
    scorecard = evaluate_paper_review(workspace)
    dimensions = {
        str(item.get("id") or ""): item
        for item in scorecard.get("dimensions") or []
        if isinstance(item, dict)
    }
    issues: list[QualityIssue] = []
    for dimension_id in dimension_ids:
        dimension = dimensions.get(dimension_id)
        if dimension is None:
            issues.append(
                QualityIssue(
                    code=f"paper_review_{dimension_id}_missing",
                    message=f"Paper-review evaluation did not emit `{dimension_id}`.",
                )
            )
            continue
        if str(dimension.get("status") or "").upper() == "PASS":
            continue
        issues.append(
            QualityIssue(
                code=f"paper_review_{dimension_id}",
                message=(
                    f"Paper-review `{dimension_id}` is {dimension.get('status') or 'unavailable'}: "
                    f"{dimension.get('evidence') or 'no evidence summary'}"
                ),
            )
        )
    return issues


def check_claims(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return _check_dimensions(workspace, ("claim_traceability",))


def check_evidence_audit(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return _check_dimensions(workspace, ("evidence_coverage",))


def check_novelty_matrix(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return _check_dimensions(workspace, ("novelty_positioning",))


def check_review(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    return _check_dimensions(
        workspace,
        ("review_traceability", "recommendation_consistency"),
    )
