from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Collection, Mapping, Sequence

from tooling.common import atomic_write_text, load_workspace_pipeline_spec, now_iso_seconds


def load_scorecard_policy(
    workspace: Path,
    *,
    default_pass_score: int,
    default_critical_dimensions: Collection[str],
) -> tuple[int, set[str]]:
    """Load a Workflow's semantic threshold without owning its rubric."""

    spec = load_workspace_pipeline_spec(workspace)
    rubric = spec.quality_contract.get("semantic_rubric", {}) if spec is not None else {}
    raw_pass_score = rubric.get("pass_score", default_pass_score)
    if isinstance(raw_pass_score, bool):
        raise ValueError("semantic_rubric.pass_score must be an integer from 0 to 100")
    try:
        pass_score = int(raw_pass_score)
    except (TypeError, ValueError) as exc:
        raise ValueError("semantic_rubric.pass_score must be an integer from 0 to 100") from exc
    if not 0 <= pass_score <= 100:
        raise ValueError("semantic_rubric.pass_score must be an integer from 0 to 100")

    defaults = _normalized_values(default_critical_dimensions)
    configured = rubric.get("critical_dimensions", defaults)
    critical_dimensions = (
        _normalized_values(configured)
        if isinstance(configured, (list, tuple, set, frozenset))
        else defaults
    )
    return pass_score, critical_dimensions or defaults


def build_dimension(
    dimension_id: str,
    label: str,
    *,
    passed: bool,
    partial: bool,
    evidence: str,
    repair_surface: Sequence[str],
) -> dict[str, Any]:
    """Build one scored semantic dimension using the shared four-point scale."""

    score = 4 if passed else (2 if partial else 0)
    return {
        "id": dimension_id,
        "label": label,
        "status": "PASS" if passed else "FAIL",
        "score": score,
        "max_score": 4,
        "evidence": evidence,
        "repair_surface": list(repair_surface),
    }


def finalize_scorecard(
    *,
    schema: str,
    workflow: str,
    dimensions: Sequence[Mapping[str, Any]],
    pass_score: int,
    critical_dimensions: Collection[str],
    counts: Mapping[str, int],
    limitations: Sequence[str],
) -> dict[str, Any]:
    """Project Workflow-local dimensions into the common Harness envelope."""

    if not _is_score(pass_score):
        raise ValueError("pass_score must be an integer from 0 to 100")
    dimension_records = [dict(item) for item in dimensions]
    critical = _normalized_values(critical_dimensions)
    max_score = sum(int(item["max_score"]) for item in dimension_records)
    earned_score = sum(int(item["score"]) for item in dimension_records)
    score = round((earned_score / max_score) * 100) if max_score else 0
    failed_critical = [
        str(item["id"])
        for item in dimension_records
        if str(item["id"]) in critical and item["status"] != "PASS"
    ]
    failures = [
        _dimension_failure(item, critical_dimensions=critical)
        for item in dimension_records
        if item["status"] != "PASS"
    ]

    return {
        "schema": schema,
        "generated_at": now_iso_seconds(),
        "workflow": workflow,
        "verdict": "PASS" if score >= pass_score and not failed_critical else "FAIL",
        "score": score,
        "pass_score": pass_score,
        "critical_dimensions": sorted(critical),
        "failed_critical_dimensions": failed_critical,
        "counts": dict(counts),
        "dimensions": dimension_records,
        "failures": failures,
        "limitations": list(limitations),
    }


def validate_scorecard(payload: Mapping[str, Any], *, schema: str) -> list[str]:
    """Validate the stable envelope shared by Workflow-local scorecards."""

    errors: list[str] = []
    if payload.get("schema") != schema:
        errors.append(f"schema must be {schema}")
    if payload.get("verdict") not in {"PASS", "FAIL"}:
        errors.append("verdict must be PASS or FAIL")
    score = payload.get("score")
    if not _is_score(score):
        errors.append("score must be an integer from 0 to 100")
    if not _is_score(payload.get("pass_score")):
        errors.append("pass_score must be an integer from 0 to 100")
    if not isinstance(payload.get("workflow"), str) or not str(payload.get("workflow") or "").strip():
        errors.append("workflow must be a non-empty string")
    if not isinstance(payload.get("generated_at"), str) or not str(payload.get("generated_at") or "").strip():
        errors.append("generated_at must be a non-empty string")
    if not _is_string_list(payload.get("critical_dimensions")):
        errors.append("critical_dimensions must be a list of strings")
    if not _is_string_list(payload.get("failed_critical_dimensions")):
        errors.append("failed_critical_dimensions must be a list of strings")
    if not isinstance(payload.get("counts"), Mapping):
        errors.append("counts must be an object")
    if not _is_string_list(payload.get("limitations")):
        errors.append("limitations must be a list of strings")

    dimensions = payload.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        errors.append("dimensions must be a non-empty list")
    else:
        for index, dimension in enumerate(dimensions):
            if not _valid_dimension(dimension):
                errors.append(f"dimensions[{index}] must match the scorecard dimension contract")

    failures = payload.get("failures")
    if not isinstance(failures, list):
        errors.append("failures must be a list")
    else:
        for index, failure in enumerate(failures):
            if not _valid_failure(failure):
                errors.append(f"failures[{index}] must match the scorecard failure contract")
    errors.extend(_scorecard_consistency_errors(payload))
    return errors


def render_scorecard(payload: Mapping[str, Any], *, title: str) -> str:
    """Render the human-readable companion to a machine-readable scorecard."""

    lines = [
        f"# {title}",
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
    failures = payload["failures"]
    if failures:
        lines.extend(f"- `{item['code']}`: {item['message']}" for item in failures)
    else:
        lines.append("- (none)")
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {item}" for item in payload["limitations"])
    return "\n".join(lines).rstrip() + "\n"


def write_scorecard(
    workspace: Path,
    *,
    payload: Mapping[str, Any],
    json_name: str,
    markdown_name: str,
    title: str,
) -> tuple[int, dict[str, Any]]:
    """Persist both scorecard views and return the Harness-compatible exit code."""

    record = dict(payload)
    output = workspace / "output"
    output.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output / json_name, json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    atomic_write_text(output / markdown_name, render_scorecard(record, title=title))
    return (0 if record["verdict"] == "PASS" else 2), record


def _dimension_failure(
    dimension: Mapping[str, Any],
    *,
    critical_dimensions: Collection[str],
) -> dict[str, Any]:
    dimension_id = str(dimension["id"])
    return {
        "code": dimension_id,
        "message": str(dimension["evidence"]),
        "causal_behavior": f"The {str(dimension['label']).lower()} contract is incomplete or inconsistent.",
        "repair_surface": list(dimension.get("repair_surface") or []),
        "severity": "high" if dimension_id in critical_dimensions else "medium",
    }


def _normalized_values(values: Collection[object]) -> set[str]:
    return {
        str(value or "").strip().lower()
        for value in values
        if str(value or "").strip()
    }


def _is_score(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _valid_dimension(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    required_text = ("id", "label", "status", "evidence")
    if any(not isinstance(value.get(key), str) or not str(value.get(key) or "").strip() for key in required_text):
        return False
    if value.get("status") not in {"PASS", "FAIL"}:
        return False
    score = value.get("score")
    max_score = value.get("max_score")
    if not isinstance(score, int) or isinstance(score, bool):
        return False
    if not isinstance(max_score, int) or isinstance(max_score, bool) or max_score <= 0:
        return False
    if not 0 <= score <= max_score:
        return False
    return _is_string_list(value.get("repair_surface"))


def _valid_failure(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    required_text = ("code", "message", "causal_behavior", "severity")
    if any(not isinstance(value.get(key), str) or not str(value.get(key) or "").strip() for key in required_text):
        return False
    return _is_string_list(value.get("repair_surface"))


def _scorecard_consistency_errors(payload: Mapping[str, Any]) -> list[str]:
    """Recompute derived fields after the envelope has passed shape checks."""

    dimensions = payload.get("dimensions")
    critical_values = payload.get("critical_dimensions")
    failed_values = payload.get("failed_critical_dimensions")
    failures = payload.get("failures")
    pass_score = payload.get("pass_score")
    score = payload.get("score")
    verdict = payload.get("verdict")
    if (
        not isinstance(dimensions, list)
        or not dimensions
        or any(not _valid_dimension(item) for item in dimensions)
        or not _is_string_list(critical_values)
        or not _is_string_list(failed_values)
        or not isinstance(failures, list)
        or any(not _valid_failure(item) for item in failures)
        or not _is_score(pass_score)
        or not _is_score(score)
        or verdict not in {"PASS", "FAIL"}
    ):
        return []

    records = [dict(item) for item in dimensions]
    errors: list[str] = []
    dimension_ids = [str(item["id"]) for item in records]
    if len(set(dimension_ids)) != len(dimension_ids):
        errors.append("dimension ids must be unique")

    critical = _normalized_values(critical_values)
    unknown_critical = sorted(critical - _normalized_values(dimension_ids))
    if unknown_critical:
        errors.append(
            "critical_dimensions reference unknown dimensions: "
            + ", ".join(unknown_critical)
        )

    for index, item in enumerate(records):
        expected_status = "PASS" if item["score"] == item["max_score"] else "FAIL"
        if item["status"] != expected_status:
            errors.append(
                f"dimensions[{index}].status must be {expected_status} for "
                f"score {item['score']}/{item['max_score']}"
            )

    max_score = sum(int(item["max_score"]) for item in records)
    earned_score = sum(int(item["score"]) for item in records)
    expected_score = round((earned_score / max_score) * 100) if max_score else 0
    if score != expected_score:
        errors.append(f"score must equal the recomputed dimension score {expected_score}")

    expected_failed = [
        str(item["id"])
        for item in records
        if str(item["id"]).strip().lower() in critical and item["status"] != "PASS"
    ]
    if failed_values != expected_failed:
        errors.append("failed_critical_dimensions must match failed critical dimensions")

    expected_verdict = (
        "PASS" if expected_score >= pass_score and not expected_failed else "FAIL"
    )
    if verdict != expected_verdict:
        errors.append(f"verdict must be {expected_verdict} for the recomputed score and critical failures")

    expected_failures = [
        _dimension_failure(item, critical_dimensions=critical)
        for item in records
        if item["status"] != "PASS"
    ]
    if failures != expected_failures:
        errors.append("failures must match failed dimensions")
    return errors


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
