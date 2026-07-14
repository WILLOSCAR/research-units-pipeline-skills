from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tooling.common import (
    atomic_write_text,
    load_workspace_pipeline_spec,
    now_iso_seconds,
    read_jsonl,
    read_tsv,
)


SCORECARD_SCHEMA = "paper-review-scorecard.v1"
DEFAULT_PASS_SCORE = 80
DEFAULT_CRITICAL_DIMENSIONS = {
    "claim_traceability",
    "evidence_coverage",
    "review_traceability",
}


def evaluate_paper_review(workspace: Path) -> dict[str, Any]:
    """Evaluate the stable, observable contract of a paper-review Run."""

    output = workspace / "output"
    claims = _read_records(output / "CLAIMS.jsonl")
    gaps = _read_records(output / "EVIDENCE_AUDIT.jsonl")
    novelty_rows = read_tsv(output / "NOVELTY_MATRIX.tsv")
    review_path = output / "REVIEW.md"
    review_text = review_path.read_text(encoding="utf-8", errors="ignore") if review_path.exists() else ""

    pass_score, critical_dimensions = _rubric_policy(workspace)
    dimensions = [
        _artifact_dimension(output),
        _claim_dimension(claims),
        _evidence_dimension(claims, gaps),
        _novelty_dimension(claims, novelty_rows),
        _review_dimension(review_text, gaps),
        _recommendation_dimension(review_text, gaps),
    ]
    max_score = sum(int(item["max_score"]) for item in dimensions)
    earned_score = sum(int(item["score"]) for item in dimensions)
    score = round((earned_score / max_score) * 100) if max_score else 0
    failed_critical = [
        str(item["id"])
        for item in dimensions
        if item["id"] in critical_dimensions and item["status"] != "PASS"
    ]
    failures = [_dimension_failure(item) for item in dimensions if item["status"] != "PASS"]
    verdict = "PASS" if score >= pass_score and not failed_critical else "FAIL"

    return {
        "schema": SCORECARD_SCHEMA,
        "generated_at": now_iso_seconds(),
        "workflow": "paper-review",
        "verdict": verdict,
        "score": score,
        "pass_score": pass_score,
        "critical_dimensions": sorted(critical_dimensions),
        "failed_critical_dimensions": failed_critical,
        "counts": {
            "claims": len(claims),
            "evidence_gaps": len(gaps),
            "novelty_rows": len(novelty_rows),
            "major_gaps": len([gap for gap in gaps if _clean(gap.get("severity")) == "major"]),
        },
        "dimensions": dimensions,
        "failures": failures,
        "limitations": [
            "This scorecard validates observable semantic contracts and traceability; it does not replace expert judgment of scientific correctness.",
            "Novelty quality is bounded by the related work available inside the Workspace.",
        ],
    }


def write_paper_review_scorecard(workspace: Path) -> tuple[int, dict[str, Any]]:
    payload = evaluate_paper_review(workspace)
    output = workspace / "output"
    output.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        output / "REVIEW_SCORECARD.json",
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    atomic_write_text(output / "REVIEW_SCORECARD.md", render_paper_review_scorecard(payload))
    return (0 if payload["verdict"] == "PASS" else 2), payload


def validate_paper_review_scorecard(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != SCORECARD_SCHEMA:
        errors.append(f"schema must be {SCORECARD_SCHEMA}")
    if payload.get("verdict") not in {"PASS", "FAIL"}:
        errors.append("verdict must be PASS or FAIL")
    if not isinstance(payload.get("score"), int) or not 0 <= int(payload.get("score", -1)) <= 100:
        errors.append("score must be an integer from 0 to 100")
    dimensions = payload.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        errors.append("dimensions must be a non-empty list")
    failures = payload.get("failures")
    if not isinstance(failures, list):
        errors.append("failures must be a list")
    return errors


def render_paper_review_scorecard(payload: dict[str, Any]) -> str:
    lines = [
        "# Paper Review Scorecard",
        "",
        f"- Verdict: {payload['verdict']}",
        f"- Score: {payload['score']}/100",
        f"- Pass threshold: {payload['pass_score']}/100",
        "",
        "## Dimensions",
        "",
        "| Dimension | Status | Score | Evidence | Repair surface |",
        "|---|---|---:|---|---|",
    ]
    for item in payload["dimensions"]:
        evidence = _escape_table(str(item.get("evidence") or ""))
        repair = _escape_table(", ".join(str(value) for value in item.get("repair_surface") or []))
        lines.append(
            f"| {item['label']} | {item['status']} | {item['score']}/{item['max_score']} | {evidence} | {repair} |"
        )
    lines.extend(["", "## Failed Checks", ""])
    if payload["failures"]:
        for failure in payload["failures"]:
            lines.append(f"- `{failure['code']}`: {failure['message']}")
    else:
        lines.append("- (none)")
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {item}" for item in payload["limitations"])
    return "\n".join(lines).rstrip() + "\n"


def _read_records(path: Path) -> list[dict[str, Any]]:
    try:
        return [dict(record) for record in read_jsonl(path) if isinstance(record, dict)]
    except (json.JSONDecodeError, OSError):
        return []


def _rubric_policy(workspace: Path) -> tuple[int, set[str]]:
    spec = load_workspace_pipeline_spec(workspace)
    rubric = spec.quality_contract.get("semantic_rubric", {}) if spec is not None else {}
    try:
        pass_score = int(rubric.get("pass_score", DEFAULT_PASS_SCORE))
    except (TypeError, ValueError):
        pass_score = DEFAULT_PASS_SCORE
    values = rubric.get("critical_dimensions", DEFAULT_CRITICAL_DIMENSIONS)
    critical = {_clean(value) for value in values if _clean(value)} if isinstance(values, (list, tuple, set)) else set(DEFAULT_CRITICAL_DIMENSIONS)
    return pass_score, critical or set(DEFAULT_CRITICAL_DIMENSIONS)


def _artifact_dimension(output: Path) -> dict[str, Any]:
    required = ["CLAIMS.jsonl", "EVIDENCE_AUDIT.jsonl", "NOVELTY_MATRIX.tsv", "REVIEW.md"]
    missing = [name for name in required if not (output / name).exists() or (output / name).stat().st_size == 0]
    return _dimension(
        "artifact_completeness",
        "Artifact completeness",
        passed=not missing,
        partial=len(missing) < len(required),
        evidence="All structured review artifacts are present." if not missing else f"Missing: {', '.join(missing)}",
        repair_surface=[f"output/{name}" for name in missing] or ["pipelines/paper-review.pipeline.md"],
    )


def _claim_dimension(claims: list[dict[str, Any]]) -> dict[str, Any]:
    valid_types = {"empirical", "conceptual"}
    valid = [
        claim
        for claim in claims
        if _clean(claim.get("claim_id"))
        and _clean(claim.get("text"))
        and _clean(claim.get("claim_type")) in valid_types
        and _clean(claim.get("source_pointer"))
    ]
    return _dimension(
        "claim_traceability",
        "Claim traceability",
        passed=bool(claims) and len(valid) == len(claims),
        partial=bool(valid),
        evidence=f"{len(valid)}/{len(claims)} claims have ID, type, text, and source pointer.",
        repair_surface=[".codex/skills/claims-extractor/SKILL.md", "output/CLAIMS.jsonl"],
    )


def _evidence_dimension(claims: list[dict[str, Any]], gaps: list[dict[str, Any]]) -> dict[str, Any]:
    claim_ids = {_clean(claim.get("claim_id")) for claim in claims if _clean(claim.get("claim_id"))}
    covered = {
        _clean(gap.get("claim_id"))
        for gap in gaps
        if _clean(gap.get("claim_id")) in claim_ids
        and _clean(gap.get("evidence_present"))
        and _clean(gap.get("gap"))
        and _clean(gap.get("minimal_fix"))
        and _clean(gap.get("severity")) in {"minor", "major", "critical"}
    }
    return _dimension(
        "evidence_coverage",
        "Evidence coverage",
        passed=bool(claim_ids) and covered == claim_ids,
        partial=bool(covered),
        evidence=f"{len(covered)}/{len(claim_ids)} claims have a complete evidence assessment.",
        repair_surface=[".codex/skills/evidence-auditor/SKILL.md", "output/EVIDENCE_AUDIT.jsonl"],
    )


def _novelty_dimension(claims: list[dict[str, Any]], rows: list[dict[str, str]]) -> dict[str, Any]:
    claim_ids = {_clean(claim.get("claim_id")) for claim in claims if _clean(claim.get("claim_id"))}
    covered = {
        _clean(row.get("claim_id"))
        for row in rows
        if _clean(row.get("claim_id")) in claim_ids
        and _clean(row.get("related_work"))
        and _clean(row.get("overlap"))
        and _clean(row.get("delta"))
        and _clean(row.get("evidence"))
    }
    unavailable = [row for row in rows if "unavailable" in _clean(row.get("related_work"))]
    passed = bool(claim_ids) and covered == claim_ids and not unavailable
    return _dimension(
        "novelty_positioning",
        "Novelty positioning",
        passed=passed,
        partial=bool(covered),
        evidence=f"{len(covered)}/{len(claim_ids)} claims are positioned; unavailable rows={len(unavailable)}.",
        repair_surface=[".codex/skills/novelty-matrix/SKILL.md", "output/NOVELTY_MATRIX.tsv"],
    )


def _review_dimension(review_text: str, gaps: list[dict[str, Any]]) -> dict[str, Any]:
    required_sections = (
        "### Summary",
        "### Novelty",
        "### Soundness",
        "### Clarity",
        "### Impact",
        "### Major Concerns",
        "### Minor Comments",
        "### Recommendation",
    )
    missing_sections = [section for section in required_sections if section not in review_text]
    major = [gap for gap in gaps if _clean(gap.get("severity")) in {"major", "critical"}]
    review_lower = review_text.lower()
    traced = [
        gap
        for gap in major
        if _clean(gap.get("gap_id")) in review_lower or _clean(gap.get("claim_id")) in review_lower
    ]
    passed = bool(review_text.strip()) and not missing_sections and len(traced) == len(major)
    return _dimension(
        "review_traceability",
        "Review traceability",
        passed=passed,
        partial=bool(review_text.strip()) and len(missing_sections) < len(required_sections),
        evidence=f"Missing sections={len(missing_sections)}; traced major concerns={len(traced)}/{len(major)}.",
        repair_surface=[".codex/skills/rubric-writer/SKILL.md", "output/REVIEW.md"],
    )


def _recommendation_dimension(review_text: str, gaps: list[dict[str, Any]]) -> dict[str, Any]:
    match = re.search(r"(?im)^-\s*(strong_accept|accept|weak_accept|borderline|weak_reject|reject|strong_reject)\s*$", review_text)
    recommendation = match.group(1).lower() if match else ""
    has_major = any(_clean(gap.get("severity")) in {"major", "critical"} for gap in gaps)
    inconsistent = has_major and recommendation in {"strong_accept", "accept", "weak_accept"}
    return _dimension(
        "recommendation_consistency",
        "Recommendation consistency",
        passed=bool(recommendation) and not inconsistent,
        partial=bool(recommendation),
        evidence=f"Recommendation={recommendation or 'missing'}; major gap present={str(has_major).lower()}.",
        repair_surface=[".codex/skills/rubric-writer/SKILL.md", "output/REVIEW.md"],
    )


def _dimension(
    dimension_id: str,
    label: str,
    *,
    passed: bool,
    partial: bool,
    evidence: str,
    repair_surface: list[str],
) -> dict[str, Any]:
    score = 4 if passed else (2 if partial else 0)
    return {
        "id": dimension_id,
        "label": label,
        "status": "PASS" if passed else "FAIL",
        "score": score,
        "max_score": 4,
        "evidence": evidence,
        "repair_surface": repair_surface,
    }


def _dimension_failure(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": str(item["id"]),
        "message": str(item["evidence"]),
        "causal_behavior": f"The {item['label'].lower()} contract is incomplete or inconsistent.",
        "repair_surface": list(item.get("repair_surface") or []),
        "severity": "high" if item["id"] in DEFAULT_CRITICAL_DIMENSIONS else "medium",
    }


def _clean(value: Any) -> str:
    return str(value or "").strip().lower()


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
