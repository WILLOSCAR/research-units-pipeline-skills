from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from tooling.review_artifacts import load_candidate_records, stable_paper_id
from tooling.review_protocol import parse_protocol
from tooling.scorecards import (
    build_dimension as _dimension,
    finalize_scorecard,
    load_scorecard_policy,
    render_scorecard,
    validate_scorecard,
    write_scorecard,
)


SCORECARD_SCHEMA = "evidence-review-scorecard.v1"
DEFAULT_PASS_SCORE = 80
DEFAULT_CRITICAL_DIMENSIONS = {
    "bias_completeness",
    "conclusion_boundedness",
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
    candidates = load_candidate_records(workspace)
    candidate_ids = {
        stable_paper_id(record, index=index)
        for index, record in enumerate(candidates, start=1)
    }
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
        _screening_dimension(screening, protocol, candidate_ids),
        _extraction_dimension(extraction, included_ids),
        _bias_dimension(extraction),
        _structure_dimension(synthesis),
        _traceability_dimension(synthesis_ids, extraction_ids, included_ids),
        _boundedness_dimension(synthesis),
    ]
    return finalize_scorecard(
        schema=SCORECARD_SCHEMA,
        workflow="evidence-review",
        dimensions=dimensions,
        pass_score=pass_score,
        critical_dimensions=critical_dimensions,
        counts={
            "screened_records": len(screening),
            "candidate_records": len(candidate_ids),
            "included_records": len(included_ids),
            "extracted_records": len(extraction_ids),
            "synthesis_pointers": len(synthesis_ids),
        },
        limitations=[
            "This scorecard validates protocol-to-synthesis traceability and extraction completeness; it does not perform meta-analysis or establish causal truth.",
            "A PASS remains bounded by the retrieved pool, source text, and human-approved protocol in this Workspace.",
        ],
    )


def write_evidence_review_scorecard(workspace: Path) -> tuple[int, dict[str, Any]]:
    return write_scorecard(
        workspace,
        payload=evaluate_evidence_review(workspace),
        json_name="EVIDENCE_SCORECARD.json",
        markdown_name="EVIDENCE_SCORECARD.md",
        title="Evidence Review Scorecard",
    )


def validate_evidence_review_scorecard(payload: dict[str, Any]) -> list[str]:
    return validate_scorecard(payload, schema=SCORECARD_SCHEMA)


def render_evidence_review_scorecard(payload: dict[str, Any]) -> str:
    return render_scorecard(payload, title="Evidence Review Scorecard")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _rubric_policy(workspace: Path) -> tuple[int, set[str]]:
    return load_scorecard_policy(
        workspace,
        default_pass_score=DEFAULT_PASS_SCORE,
        default_critical_dimensions=DEFAULT_CRITICAL_DIMENSIONS,
    )


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


def _screening_dimension(
    rows: list[dict[str, str]],
    protocol: dict[str, Any],
    candidate_ids: set[str],
) -> dict[str, Any]:
    valid_codes = {code for code, _ in (protocol.get("inclusion") or []) + (protocol.get("exclusion") or [])}
    invalid_rows = 0
    include_count = 0
    row_ids: list[str] = []
    for row in rows:
        decision = str(row.get("decision") or "").strip().lower()
        if decision == "include":
            include_count += 1
        paper_id = str(row.get("paper_id") or "").strip()
        if paper_id:
            row_ids.append(paper_id)
        codes = {value.strip() for value in re.split(r"[;,\s]+", str(row.get("reason_codes") or "")) if value.strip()}
        if (
            decision not in {"include", "exclude"}
            or not str(row.get("paper_id") or "").strip()
            or not str(row.get("reason") or "").strip()
            or not codes
            or not codes.issubset(valid_codes)
        ):
            invalid_rows += 1
    screened_ids = set(row_ids)
    duplicate_ids = len(row_ids) - len(screened_ids)
    missing_ids = candidate_ids - screened_ids
    unexpected_ids = screened_ids - candidate_ids
    passed = (
        bool(rows)
        and bool(candidate_ids)
        and include_count > 0
        and invalid_rows == 0
        and duplicate_ids == 0
        and not missing_ids
        and not unexpected_ids
    )
    return _dimension(
        "screening_traceability",
        "Screening traceability",
        passed=passed,
        partial=bool(rows) and invalid_rows < len(rows),
        evidence=(
            f"Rows={len(rows)}/{len(candidate_ids)} candidates; included={include_count}; "
            f"invalid clause-linked rows={invalid_rows}; duplicate IDs={duplicate_ids}; "
            f"missing IDs={len(missing_ids)}; unexpected IDs={len(unexpected_ids)}."
        ),
        repair_surface=[".codex/skills/screening-manager/SKILL.md", "papers/screening_log.csv", "output/PROTOCOL.md"],
    )


def _extraction_dimension(rows: list[dict[str, str]], included_ids: set[str]) -> dict[str, Any]:
    extraction_id_list = [str(row.get("paper_id") or "").strip() for row in rows if str(row.get("paper_id") or "").strip()]
    extraction_ids = set(extraction_id_list)
    duplicate_ids = len(extraction_id_list) - len(extraction_ids)
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
    passed = (
        bool(rows)
        and duplicate_ids == 0
        and not missing_ids
        and extraction_ids == included_ids
        and ratio >= 0.9
        and rows_missing_pointer == 0
    )
    return _dimension(
        "extraction_coverage",
        "Extraction coverage",
        passed=passed,
        partial=bool(rows) and not missing_ids and ratio >= 0.5,
        evidence=(
            f"Extracted={len(extraction_ids)}/{len(included_ids)} included IDs; duplicate IDs={duplicate_ids}; "
            f"substantive cells={substantive}/{total}; rows missing result/pointer={rows_missing_pointer}."
        ),
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
    forbidden = _unbounded_overclaim_tokens(synthesis)
    has_limits = "## Needs more evidence" in synthesis and "## Risk of bias" in synthesis
    return _dimension(
        "conclusion_boundedness",
        "Conclusion boundedness",
        passed=has_limits and not forbidden,
        partial=has_limits and len(forbidden) <= 1,
        evidence="Conclusions retain explicit evidence and bias limits." if has_limits and not forbidden else f"Overclaim tokens={', '.join(forbidden) if forbidden else 'none'}; limits present={has_limits}.",
        repair_surface=[".codex/skills/synthesis-writer/SKILL.md", "output/SYNTHESIS.md"],
    )


def _unbounded_overclaim_tokens(synthesis: str) -> list[str]:
    """Find strong conclusion language while preserving explicit negation and critique."""

    tokens: list[str] = []
    in_fence = False
    pattern = re.compile(
        r"(?i)\b("
        r"proves?|definitive(?:ly)?|causes?|guarantees?|conclusive|"
        r"demonstrat(?:e|es|ed|ing)|establish(?:es|ed|ing)?|"
        r"confirm(?:s|ed|ing)?|validat(?:e|es|ed|ing)"
        r")\b"
    )
    recommendation_pattern = re.compile(
        r"(?i)\b("
        r"strongly\s+supports?\s+(?:deploying|deployment|adopting|adoption|implementing|implementation|use)|"
        r"supports?\s+(?:immediate|routine|broad|universal)\s+"
        r"(?:deployment|adoption|implementation|use)|"
        r"should\s+(?:now\s+)?(?:be\s+)?(?:deployed|adopted|implemented|used)"
        r")\b"
    )
    for line in synthesis.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or stripped.startswith(("#", ">")):
            continue
        for match in recommendation_pattern.finditer(line):
            before = line[max(0, match.start() - 80) : match.start()].casefold()
            if not _is_negated_or_hedged(before):
                tokens.append(match.group(1))
        for match in pattern.finditer(line):
            before = line[max(0, match.start() - 80) : match.start()].casefold()
            after = line[match.end() : match.end() + 45].casefold()
            nearby_before = " ".join(before.split()[-8:])
            if _is_negated_or_hedged(nearby_before):
                continue
            if re.search(r"\b(?:claim|word|term|language|statement)s?\s+(?:that\s+)?$", nearby_before):
                continue
            token = match.group(1)
            if token.casefold() in {"cause", "causes"} and re.match(
                r"\s+(?:remain|include|were|are|may|might|could|uncertain|unknown)\b",
                after,
            ):
                continue
            tokens.append(token)
    return tokens


def _is_negated_or_hedged(before: str) -> bool:
    nearby = " ".join(str(before or "").casefold().split()[-8:])
    return bool(
        re.search(
            r"(?:\bnot\b|\bno\b|\bnever\b|\bcannot\b|\bcan't\b|\bdoesn't\b|\bdoes\s+not\b|"
            r"\bdid\s+not\b|\bfails?\s+to\b|\bavoid(?:s|ed|ing)?\b|\bwithout\b|"
            r"\bmay\b|\bmight\b|\bcould\b|\bappears?\s+to\b|\bseems?\s+to\b)",
            nearby,
        )
    )


def _is_substantive(value: object) -> bool:
    text = str(value or "").strip().lower()
    return bool(text) and not text.startswith("not reported") and not text.startswith("not classifiable")
