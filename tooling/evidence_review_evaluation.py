from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from tooling.common import atomic_write_text, load_workspace_pipeline_spec, now_iso_seconds
from tooling.review_protocol import parse_protocol


SCORECARD_SCHEMA = "evidence-review-scorecard.v1"
DEFAULT_PASS_SCORE = 80
DEFAULT_CRITICAL_DIMENSIONS = {
    "protocol_operability",
    "screening_traceability",
    "extraction_coverage",
    "synthesis_traceability",
}
CANONICAL_EXTRACTION_FIELDS = (
    "population_or_setting",
    "task",
    "metric",
    "study_type",
    "result_summary",
    "evidence_pointer",
)
REQUIRED_SYNTHESIS_SECTIONS = (
    "## Research questions + scope",
    "## Included studies summary",
    "## Extracted evidence table",
    "## Findings by theme",
    "## Risk of bias",
    "## Supported conclusions",
    "## Needs more evidence",
)


def evaluate_evidence_review(workspace: Path) -> dict[str, Any]:
    protocol_path = workspace / "output" / "PROTOCOL.md"
    protocol_text = protocol_path.read_text(encoding="utf-8", errors="ignore") if protocol_path.exists() else ""
    protocol = parse_protocol(protocol_text)
    screening = _read_csv(workspace / "papers" / "screening_log.csv")
    extraction = _read_csv(workspace / "papers" / "extraction_table.csv")
    synthesis_path = workspace / "output" / "SYNTHESIS.md"
    synthesis = synthesis_path.read_text(encoding="utf-8", errors="ignore") if synthesis_path.exists() else ""
    included_ids = {
        str(row.get("paper_id") or "").strip()
        for row in screening
        if str(row.get("decision") or "").strip().lower() == "include" and str(row.get("paper_id") or "").strip()
    }
    extraction_ids = {str(row.get("paper_id") or "").strip() for row in extraction if str(row.get("paper_id") or "").strip()}
    synthesis_ids = set(re.findall(r"\bP\d{4}\b", synthesis))
    pass_score, critical_dimensions = _rubric_policy(workspace)

    dimensions = [
        _artifact_dimension(workspace),
        _protocol_dimension(protocol_text, protocol),
        _screening_dimension(screening, protocol),
        _extraction_dimension(extraction, included_ids),
        _bias_dimension(extraction),
        _structure_dimension(synthesis),
        _traceability_dimension(synthesis_ids, extraction_ids, included_ids),
        _boundedness_dimension(synthesis),
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
        "workflow": "evidence-review",
        "verdict": "PASS" if score >= pass_score and not failed_critical else "FAIL",
        "score": score,
        "pass_score": pass_score,
        "critical_dimensions": sorted(critical_dimensions),
        "failed_critical_dimensions": failed_critical,
        "counts": {
            "screened_records": len(screening),
            "included_records": len(included_ids),
            "extracted_records": len(extraction_ids),
            "synthesis_pointers": len(synthesis_ids),
        },
        "dimensions": dimensions,
        "failures": failures,
        "limitations": [
            "This scorecard validates protocol-to-synthesis traceability and extraction completeness; it does not perform meta-analysis or establish causal truth.",
            "A PASS remains bounded by the retrieved pool, source text, and human-approved protocol in this Workspace.",
        ],
    }


def write_evidence_review_scorecard(workspace: Path) -> tuple[int, dict[str, Any]]:
    payload = evaluate_evidence_review(workspace)
    output = workspace / "output"
    output.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output / "EVIDENCE_SCORECARD.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    atomic_write_text(output / "EVIDENCE_SCORECARD.md", render_evidence_review_scorecard(payload))
    return (0 if payload["verdict"] == "PASS" else 2), payload


def validate_evidence_review_scorecard(payload: dict[str, Any]) -> list[str]:
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


def render_evidence_review_scorecard(payload: dict[str, Any]) -> str:
    lines = [
        "# Evidence Review Scorecard",
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
        lines.append(f"| {item['label']} | {item['status']} | {item['score']}/{item['max_score']} | {evidence} | {repair} |")
    lines.extend(["", "## Failed Checks", ""])
    if payload["failures"]:
        lines.extend(f"- `{item['code']}`: {item['message']}" for item in payload["failures"])
    else:
        lines.append("- (none)")
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {item}" for item in payload["limitations"])
    return "\n".join(lines).rstrip() + "\n"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _artifact_dimension(workspace: Path) -> dict[str, Any]:
    required = (
        "output/PROTOCOL.md",
        "papers/screening_log.csv",
        "papers/extraction_table.csv",
        "output/SYNTHESIS.md",
    )
    missing = [relpath for relpath in required if not (workspace / relpath).exists() or (workspace / relpath).stat().st_size == 0]
    return _dimension(
        "artifact_completeness",
        "Artifact completeness",
        passed=not missing,
        partial=len(missing) < len(required),
        evidence="Protocol, screening, extraction, and synthesis artifacts are present." if not missing else f"Missing: {', '.join(missing)}",
        repair_surface=missing or ["pipelines/evidence-review.pipeline.md"],
    )


def _protocol_dimension(text: str, protocol: dict[str, Any]) -> dict[str, Any]:
    field_names = {str(item.get("field") or "").strip() for item in protocol.get("extraction_fields") or []}
    missing_fields = [field for field in CANONICAL_EXTRACTION_FIELDS if field not in field_names]
    passed = (
        len(protocol.get("review_questions") or []) >= 1
        and len(protocol.get("inclusion") or []) >= 2
        and len(protocol.get("exclusion") or []) >= 2
        and not missing_fields
        and "## Databases and Sources" in text
        and "## Time Window" in text
    )
    return _dimension(
        "protocol_operability",
        "Protocol operability",
        passed=passed,
        partial=bool(protocol.get("review_questions")) and bool(protocol.get("inclusion")) and bool(protocol.get("exclusion")),
        evidence=(
            "Protocol has review questions, clause IDs, databases, time window, and the canonical extraction schema."
            if passed
            else f"Missing canonical extraction fields={', '.join(missing_fields) if missing_fields else 'none'}; databases/time-window headings may be absent."
        ),
        repair_surface=[".codex/skills/protocol-writer/SKILL.md", "output/PROTOCOL.md"],
    )


def _screening_dimension(rows: list[dict[str, str]], protocol: dict[str, Any]) -> dict[str, Any]:
    valid_codes = {code for code, _ in (protocol.get("inclusion") or []) + (protocol.get("exclusion") or [])}
    invalid_rows = 0
    include_count = 0
    for row in rows:
        decision = str(row.get("decision") or "").strip().lower()
        if decision == "include":
            include_count += 1
        codes = {value.strip() for value in re.split(r"[;,\s]+", str(row.get("reason_codes") or "")) if value.strip()}
        if (
            decision not in {"include", "exclude"}
            or not str(row.get("paper_id") or "").strip()
            or not str(row.get("reason") or "").strip()
            or not codes
            or not codes.issubset(valid_codes)
        ):
            invalid_rows += 1
    passed = bool(rows) and include_count > 0 and invalid_rows == 0
    return _dimension(
        "screening_traceability",
        "Screening traceability",
        passed=passed,
        partial=bool(rows) and invalid_rows < len(rows),
        evidence=f"Rows={len(rows)}; included={include_count}; invalid clause-linked rows={invalid_rows}.",
        repair_surface=[".codex/skills/screening-manager/SKILL.md", "papers/screening_log.csv", "output/PROTOCOL.md"],
    )


def _extraction_dimension(rows: list[dict[str, str]], included_ids: set[str]) -> dict[str, Any]:
    extraction_ids = {str(row.get("paper_id") or "").strip() for row in rows if str(row.get("paper_id") or "").strip()}
    missing_ids = sorted(included_ids - extraction_ids)
    substantive = 0
    total = len(rows) * len(CANONICAL_EXTRACTION_FIELDS)
    rows_missing_pointer = 0
    for row in rows:
        for field in CANONICAL_EXTRACTION_FIELDS:
            substantive += int(_is_substantive(row.get(field)))
        if not _is_substantive(row.get("evidence_pointer")) or not _is_substantive(row.get("result_summary")):
            rows_missing_pointer += 1
    ratio = substantive / total if total else 0.0
    passed = bool(rows) and not missing_ids and extraction_ids == included_ids and ratio >= 0.9 and rows_missing_pointer == 0
    return _dimension(
        "extraction_coverage",
        "Extraction coverage",
        passed=passed,
        partial=bool(rows) and not missing_ids and ratio >= 0.5,
        evidence=f"Extracted={len(extraction_ids)}/{len(included_ids)} included IDs; substantive cells={substantive}/{total}; rows missing result/pointer={rows_missing_pointer}.",
        repair_surface=[".codex/skills/extraction-form/SKILL.md", "papers/extraction_table.csv"],
    )


def _bias_dimension(rows: list[dict[str, str]]) -> dict[str, Any]:
    allowed = {"low", "unclear", "high"}
    fields = ("rob_selection", "rob_measurement", "rob_confounding", "rob_reporting", "rob_overall")
    invalid = 0
    for row in rows:
        if any(str(row.get(field) or "").strip().lower() not in allowed for field in fields):
            invalid += 1
        elif not str(row.get("rob_notes") or "").strip():
            invalid += 1
    return _dimension(
        "bias_completeness",
        "Risk-of-bias completeness",
        passed=bool(rows) and invalid == 0,
        partial=bool(rows) and invalid < len(rows),
        evidence=f"Rows={len(rows)}; invalid or undocumented RoB rows={invalid}.",
        repair_surface=[".codex/skills/bias-assessor/SKILL.md", "papers/extraction_table.csv"],
    )


def _structure_dimension(synthesis: str) -> dict[str, Any]:
    missing = [heading for heading in REQUIRED_SYNTHESIS_SECTIONS if heading not in synthesis]
    return _dimension(
        "synthesis_structure",
        "Synthesis structure",
        passed=bool(synthesis.strip()) and not missing,
        partial=bool(synthesis.strip()) and len(missing) <= 2,
        evidence="All bounded synthesis sections are present." if not missing else f"Missing: {', '.join(missing)}",
        repair_surface=[".codex/skills/synthesis-writer/SKILL.md", "output/SYNTHESIS.md"],
    )


def _traceability_dimension(synthesis_ids: set[str], extraction_ids: set[str], included_ids: set[str]) -> dict[str, Any]:
    expected = extraction_ids or included_ids
    invalid = sorted(synthesis_ids - expected)
    missing = sorted(expected - synthesis_ids)
    passed = bool(expected) and not invalid and not missing
    return _dimension(
        "synthesis_traceability",
        "Synthesis traceability",
        passed=passed,
        partial=bool(synthesis_ids & expected),
        evidence=f"Resolved pointers={len(synthesis_ids & expected)}/{len(expected)}; invalid={', '.join(invalid) if invalid else 'none'}; missing={', '.join(missing) if missing else 'none'}.",
        repair_surface=[".codex/skills/synthesis-writer/SKILL.md", "papers/extraction_table.csv", "output/SYNTHESIS.md"],
    )


def _boundedness_dimension(synthesis: str) -> dict[str, Any]:
    forbidden = re.findall(r"(?i)\b(proves?|definitive(?:ly)?|causes?|guarantees?|conclusive)\b", synthesis)
    has_limits = "## Needs more evidence" in synthesis and "## Risk of bias" in synthesis
    return _dimension(
        "conclusion_boundedness",
        "Conclusion boundedness",
        passed=has_limits and not forbidden,
        partial=has_limits and len(forbidden) <= 1,
        evidence="Conclusions retain explicit evidence and bias limits." if has_limits and not forbidden else f"Overclaim tokens={', '.join(forbidden) if forbidden else 'none'}; limits present={has_limits}.",
        repair_surface=[".codex/skills/synthesis-writer/SKILL.md", "output/SYNTHESIS.md"],
    )


def _is_substantive(value: object) -> bool:
    text = str(value or "").strip().lower()
    return bool(text) and not text.startswith("not reported") and not text.startswith("not classifiable")


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
