from __future__ import annotations

import csv
import re
from pathlib import Path

from tooling.evidence_review_evaluation import (
    CANONICAL_EXTRACTION_FIELDS,
    REQUIRED_SYNTHESIS_SECTIONS,
    evaluate_evidence_review,
)
from tooling.quality_checks.common import QualityIssue, has_placeholder_markers
from tooling.review_protocol import parse_protocol


def check_protocol(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/PROTOCOL.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_protocol", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore")

    issues: list[QualityIssue] = []
    if has_placeholder_markers(text):
        issues.append(
            QualityIssue(
                code="protocol_placeholders",
                message="Protocol contains placeholder markers (TODO/TBD/FIXME).",
            )
        )

    protocol = parse_protocol(text)
    field_names = {
        str(item.get("field") or "").strip()
        for item in protocol.get("extraction_fields") or []
    }
    missing_fields = [field for field in CANONICAL_EXTRACTION_FIELDS if field not in field_names]
    missing_parts: list[str] = []
    if "## Databases and Sources" not in text:
        missing_parts.append("databases and sources")
    if "## Time Window" not in text:
        missing_parts.append("time window")
    if len(protocol.get("review_questions") or []) < 1:
        missing_parts.append("review questions")
    if len(protocol.get("inclusion") or []) < 2:
        missing_parts.append("numbered inclusion clauses")
    if len(protocol.get("exclusion") or []) < 2:
        missing_parts.append("numbered exclusion clauses")
    if missing_fields:
        missing_parts.append("extraction fields: " + ", ".join(missing_fields))
    if missing_parts:
        issues.append(
            QualityIssue(
                code="protocol_missing_sections",
                message=f"Protocol is missing operational contract parts: {', '.join(missing_parts)}.",
            )
        )
    return issues


def check_screening(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "papers/screening_log.csv"
    path = workspace / out_rel
    protocol_path = workspace / "output" / "PROTOCOL.md"
    if not path.exists() or not protocol_path.exists():
        return [
            QualityIssue(
                code="missing_screening_inputs",
                message="Evidence screening requires the protocol and screening log.",
            )
        ]
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    protocol = parse_protocol(protocol_path.read_text(encoding="utf-8", errors="ignore"))
    valid_codes = {
        code
        for code, _ in (protocol.get("inclusion") or []) + (protocol.get("exclusion") or [])
    }
    invalid = 0
    included = 0
    for row in rows:
        decision = str(row.get("decision") or "").strip().lower()
        included += int(decision == "include")
        codes = {
            value.strip()
            for value in re.split(r"[;,\s]+", str(row.get("reason_codes") or ""))
            if value.strip()
        }
        if (
            decision not in {"include", "exclude"}
            or not str(row.get("paper_id") or "").strip()
            or not codes
            or not codes.issubset(valid_codes)
            or not str(row.get("reason") or "").strip()
        ):
            invalid += 1
    issues: list[QualityIssue] = []
    if not rows:
        issues.append(
            QualityIssue(code="empty_screening_log", message=f"`{out_rel}` has no screening decisions.")
        )
    if invalid:
        issues.append(
            QualityIssue(
                code="untraceable_screening_rows",
                message=f"`{out_rel}` has {invalid} row(s) without valid protocol-linked decisions and reasons.",
            )
        )
    if rows and included == 0:
        issues.append(
            QualityIssue(
                code="screening_includes_nothing",
                message=f"`{out_rel}` includes no studies; revise the protocol or candidate pool before extraction.",
            )
        )
    return issues


def check_extraction(
    workspace: Path,
    outputs: list[str],
    *,
    require_bias: bool,
) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "papers/extraction_table.csv"
    path = workspace / out_rel
    screening_path = workspace / "papers" / "screening_log.csv"
    if not path.exists() or not screening_path.exists():
        return [
            QualityIssue(
                code="missing_extraction_inputs",
                message="Evidence extraction requires the screening log and extraction table.",
            )
        ]
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    with screening_path.open("r", encoding="utf-8", newline="") as handle:
        screening = [dict(row) for row in csv.DictReader(handle)]
    included_ids = {
        str(row.get("paper_id") or "").strip()
        for row in screening
        if str(row.get("decision") or "").strip().lower() == "include"
    }
    extracted_ids = {
        str(row.get("paper_id") or "").strip()
        for row in rows
        if str(row.get("paper_id") or "").strip()
    }
    issues: list[QualityIssue] = []
    if not rows:
        return [QualityIssue(code="empty_extraction_table", message=f"`{out_rel}` has no extracted studies.")]
    missing_columns = [field for field in CANONICAL_EXTRACTION_FIELDS if field not in set(rows[0])]
    if missing_columns:
        issues.append(
            QualityIssue(
                code="extraction_missing_columns",
                message=f"`{out_rel}` is missing canonical fields: {', '.join(missing_columns)}.",
            )
        )
    missing_ids = sorted(included_ids - extracted_ids)
    unexpected_ids = sorted(extracted_ids - included_ids)
    if missing_ids or unexpected_ids:
        issues.append(
            QualityIssue(
                code="extraction_screening_mismatch",
                message=(
                    "Extraction IDs must equal included screening IDs; "
                    f"missing={missing_ids}, unexpected={unexpected_ids}."
                ),
            )
        )
    thin_rows = sum(
        1
        for row in rows
        if any(
            not value or value.startswith("not reported") or value.startswith("not classifiable")
            for value in [
                str(row.get(field) or "").strip().lower()
                for field in CANONICAL_EXTRACTION_FIELDS
            ]
        )
    )
    if thin_rows:
        issues.append(
            QualityIssue(
                code="extraction_rows_not_substantive",
                message=(
                    f"`{out_rel}` has {thin_rows} row(s) with missing or explicitly unavailable "
                    "canonical evidence fields; enrich or exclude them before synthesis."
                ),
            )
        )
    if require_bias:
        allowed = {"low", "unclear", "high"}
        rob_fields = (
            "rob_selection",
            "rob_measurement",
            "rob_confounding",
            "rob_reporting",
            "rob_overall",
        )
        invalid_bias = sum(
            1
            for row in rows
            if any(str(row.get(field) or "").strip().lower() not in allowed for field in rob_fields)
            or not str(row.get("rob_notes") or "").strip()
        )
        if invalid_bias:
            issues.append(
                QualityIssue(
                    code="incomplete_bias_assessment",
                    message=f"`{out_rel}` has {invalid_bias} row(s) with incomplete risk-of-bias fields.",
                )
            )
    return issues


def check_synthesis(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/SYNTHESIS.md"
    path = workspace / out_rel
    if not path.exists():
        return [
            QualityIssue(code="missing_evidence_synthesis", message=f"`{out_rel}` does not exist.")
        ]
    text = path.read_text(encoding="utf-8", errors="ignore")
    issues = [
        QualityIssue(
            code="evidence_synthesis_missing_section",
            message=f"`{out_rel}` is missing `{heading}`.",
        )
        for heading in REQUIRED_SYNTHESIS_SECTIONS
        if heading not in text
    ]
    payload = evaluate_evidence_review(workspace)
    trace = next(
        (item for item in payload["dimensions"] if item["id"] == "synthesis_traceability"),
        None,
    )
    if trace and trace["status"] != "PASS":
        issues.append(
            QualityIssue(code="evidence_synthesis_untraceable", message=str(trace["evidence"]))
        )
    return issues
