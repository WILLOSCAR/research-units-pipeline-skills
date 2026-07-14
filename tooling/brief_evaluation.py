from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from tooling.common import atomic_write_text, load_workspace_pipeline_spec, now_iso_seconds


SCORECARD_SCHEMA = "research-brief-scorecard.v1"
DEFAULT_PASS_SCORE = 80
DEFAULT_CRITICAL_DIMENSIONS = {
    "brief_specificity",
    "deliverable_structure",
    "source_traceability",
}
REQUIRED_SECTIONS = (
    "## Scope",
    "## Key themes",
    "## What to read first",
    "## Open problems / risks",
)


def evaluate_research_brief(workspace: Path) -> dict[str, Any]:
    """Evaluate the observable delivery contract of a research-brief Run."""

    snapshot_path = workspace / "output" / "SNAPSHOT.md"
    snapshot = snapshot_path.read_text(encoding="utf-8", errors="ignore") if snapshot_path.exists() else ""
    paper_ids = _core_paper_ids(workspace / "papers" / "core_set.csv")
    pointer_ids = set(re.findall(r"\bP\d{4}\b", snapshot))
    reading_ids = set(re.findall(r"\bP\d{4}\b", _section(snapshot, "## What to read first")))
    grounded_ids = set(
        re.findall(
            r"\bP\d{4}\b",
            _section(snapshot, "## Scope") + "\n" + _section(snapshot, "## Key themes"),
        )
    )

    pass_score, critical_dimensions = _rubric_policy(workspace)
    dimensions = [
        _artifact_dimension(snapshot_path, workspace / "papers" / "core_set.csv"),
        _structure_dimension(snapshot),
        _specificity_dimension(snapshot),
        _traceability_dimension(pointer_ids, paper_ids),
        _reading_path_dimension(reading_ids, paper_ids),
        _grounding_dimension(grounded_ids, paper_ids),
        _compactness_dimension(snapshot),
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

    return {
        "schema": SCORECARD_SCHEMA,
        "generated_at": now_iso_seconds(),
        "workflow": "research-brief",
        "verdict": "PASS" if score >= pass_score and not failed_critical else "FAIL",
        "score": score,
        "pass_score": pass_score,
        "critical_dimensions": sorted(critical_dimensions),
        "failed_critical_dimensions": failed_critical,
        "counts": {
            "core_papers": len(paper_ids),
            "unique_pointers": len(pointer_ids),
            "reading_path_pointers": len(reading_ids),
            "words": len(re.findall(r"\b\w+\b", snapshot)),
        },
        "dimensions": dimensions,
        "failures": failures,
        "limitations": [
            "This scorecard validates structure, compactness, and pointer traceability; it does not judge whether the selected literature is complete or scientifically correct.",
            "Reading-path quality is bounded by the papers already present in the Workspace core set.",
        ],
    }


def write_research_brief_scorecard(workspace: Path) -> tuple[int, dict[str, Any]]:
    payload = evaluate_research_brief(workspace)
    output = workspace / "output"
    output.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        output / "BRIEF_SCORECARD.json",
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    atomic_write_text(output / "BRIEF_SCORECARD.md", render_research_brief_scorecard(payload))
    return (0 if payload["verdict"] == "PASS" else 2), payload


def validate_research_brief_scorecard(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != SCORECARD_SCHEMA:
        errors.append(f"schema must be {SCORECARD_SCHEMA}")
    if payload.get("verdict") not in {"PASS", "FAIL"}:
        errors.append("verdict must be PASS or FAIL")
    if not isinstance(payload.get("score"), int) or not 0 <= int(payload.get("score", -1)) <= 100:
        errors.append("score must be an integer from 0 to 100")
    if not isinstance(payload.get("dimensions"), list) or not payload.get("dimensions"):
        errors.append("dimensions must be a non-empty list")
    if not isinstance(payload.get("failures"), list):
        errors.append("failures must be a list")
    return errors


def render_research_brief_scorecard(payload: dict[str, Any]) -> str:
    lines = [
        "# Research Brief Scorecard",
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
        lines.extend(f"- `{item['code']}`: {item['message']}" for item in payload["failures"])
    else:
        lines.append("- (none)")
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {item}" for item in payload["limitations"])
    return "\n".join(lines).rstrip() + "\n"


def _core_paper_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    return {
        str(row.get("paper_id") or f"P{index:04d}").strip()
        for index, row in enumerate(rows, start=1)
    }


def _section(text: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(heading)}[ \t]*\r?\n(.*?)(?=^##[ \t]|\Z)",
        text,
    )
    return match.group(1).strip() if match else ""


def _rubric_policy(workspace: Path) -> tuple[int, set[str]]:
    spec = load_workspace_pipeline_spec(workspace)
    rubric = spec.quality_contract.get("semantic_rubric", {}) if spec is not None else {}
    try:
        pass_score = int(rubric.get("pass_score", DEFAULT_PASS_SCORE))
    except (TypeError, ValueError):
        pass_score = DEFAULT_PASS_SCORE
    values = rubric.get("critical_dimensions", DEFAULT_CRITICAL_DIMENSIONS)
    critical = (
        {str(value or "").strip() for value in values if str(value or "").strip()}
        if isinstance(values, (list, tuple, set))
        else set(DEFAULT_CRITICAL_DIMENSIONS)
    )
    return pass_score, critical or set(DEFAULT_CRITICAL_DIMENSIONS)


def _artifact_dimension(snapshot_path: Path, core_path: Path) -> dict[str, Any]:
    missing = [
        str(path.relative_to(snapshot_path.parents[1]))
        for path in (snapshot_path, core_path)
        if not path.exists() or path.stat().st_size == 0
    ]
    return _dimension(
        "artifact_completeness",
        "Artifact completeness",
        passed=not missing,
        partial=len(missing) == 1,
        evidence="Snapshot and core set are present." if not missing else f"Missing: {', '.join(missing)}",
        repair_surface=missing or ["pipelines/research-brief.pipeline.md"],
    )


def _structure_dimension(snapshot: str) -> dict[str, Any]:
    missing = [heading for heading in REQUIRED_SECTIONS if not _section(snapshot, heading)]
    return _dimension(
        "deliverable_structure",
        "Deliverable structure",
        passed=bool(snapshot.strip()) and not missing,
        partial=bool(snapshot.strip()) and len(missing) < len(REQUIRED_SECTIONS),
        evidence="All four briefing sections contain content." if not missing else f"Missing or empty: {', '.join(missing)}",
        repair_surface=[".codex/skills/snapshot-writer/SKILL.md", "output/SNAPSHOT.md"],
    )


def _traceability_dimension(pointer_ids: set[str], paper_ids: set[str]) -> dict[str, Any]:
    invalid = sorted(pointer_ids - paper_ids)
    valid = pointer_ids & paper_ids
    return _dimension(
        "source_traceability",
        "Source traceability",
        passed=len(valid) >= 3 and not invalid,
        partial=bool(valid),
        evidence=f"Valid pointers={len(valid)}; invalid pointers={', '.join(invalid) if invalid else 'none'}.",
        repair_surface=[".codex/skills/snapshot-writer/SKILL.md", "papers/core_set.csv", "output/SNAPSHOT.md"],
    )


def _specificity_dimension(snapshot: str) -> dict[str, Any]:
    forbidden = (
        "why the survey",
        "survey scope",
        "this survey",
        "expected cites",
        "chapter lead plan",
        "subsection must cover",
        "intro + background",
    )
    found = [phrase for phrase in forbidden if phrase in snapshot.lower()]
    return _dimension(
        "brief_specificity",
        "Brief specificity",
        passed=not found,
        partial=len(found) <= 1,
        evidence="No survey scaffold language leaked into the brief." if not found else f"Scaffold phrases: {', '.join(found)}.",
        repair_surface=[".codex/skills/snapshot-writer/SKILL.md", "tooling/review_render.py", "output/SNAPSHOT.md"],
    )


def _reading_path_dimension(reading_ids: set[str], paper_ids: set[str]) -> dict[str, Any]:
    valid = reading_ids & paper_ids
    return _dimension(
        "reading_path",
        "Reading path",
        passed=len(valid) >= 3,
        partial=bool(valid),
        evidence=f"The reading path contains {len(valid)} unique valid paper pointers.",
        repair_surface=[".codex/skills/snapshot-writer/SKILL.md", "output/SNAPSHOT.md"],
    )


def _grounding_dimension(grounded_ids: set[str], paper_ids: set[str]) -> dict[str, Any]:
    valid = grounded_ids & paper_ids
    return _dimension(
        "theme_grounding",
        "Theme grounding",
        passed=len(valid) >= 2,
        partial=bool(valid),
        evidence=f"Scope and key themes cite {len(valid)} unique core-set papers.",
        repair_surface=[".codex/skills/snapshot-writer/SKILL.md", "output/SNAPSHOT.md"],
    )


def _compactness_dimension(snapshot: str) -> dict[str, Any]:
    word_count = len(re.findall(r"\b\w+\b", snapshot))
    passed = 100 <= word_count <= 1200
    return _dimension(
        "compactness",
        "Compactness",
        passed=passed,
        partial=50 <= word_count <= 1800,
        evidence=f"Word count={word_count}; expected 100-1200 words.",
        repair_surface=[".codex/skills/snapshot-writer/SKILL.md", "output/SNAPSHOT.md"],
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
    return {
        "id": dimension_id,
        "label": label,
        "status": "PASS" if passed else "FAIL",
        "score": 4 if passed else (2 if partial else 0),
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


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
