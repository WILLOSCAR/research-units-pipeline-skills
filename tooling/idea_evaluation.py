from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from tooling.scorecards import (
    build_dimension as _dimension,
    finalize_scorecard,
    load_scorecard_policy,
    render_scorecard,
    validate_scorecard,
    write_scorecard,
)


SCORECARD_SCHEMA = "idea-brainstorm-scorecard.v1"
DEFAULT_PASS_SCORE = 80
DEFAULT_CRITICAL_DIMENSIONS = {
    "deliverable_structure",
    "direction_actionability",
    "evidence_traceability",
    "shortlist_report_consistency",
    "trace_chain",
}
TRACE_ARTIFACTS = (
    "output/trace/IDEA_SIGNAL_TABLE.jsonl",
    "output/trace/IDEA_DIRECTION_POOL.jsonl",
    "output/trace/IDEA_SCREENING_TABLE.jsonl",
    "output/trace/IDEA_SHORTLIST.jsonl",
)


def evaluate_idea_brainstorm(workspace: Path) -> dict[str, Any]:
    """Evaluate whether an ideation Run is discussion-ready and traceable."""

    report_path = workspace / "output" / "REPORT.md"
    report_text = report_path.read_text(encoding="utf-8", errors="ignore") if report_path.exists() else ""
    payload = _read_json(workspace / "output" / "REPORT.json")
    shortlist = _read_jsonl(workspace / "output" / "trace" / "IDEA_SHORTLIST.jsonl")
    top_directions = [item for item in payload.get("top_directions", []) if isinstance(item, dict)]
    core_ids = _core_paper_ids(workspace / "papers" / "core_set.csv")
    referenced_ids = _referenced_paper_ids(shortlist, top_directions)
    pass_score, critical_dimensions = _rubric_policy(workspace)

    dimensions = [
        _artifact_dimension(workspace),
        _structure_dimension(report_text, top_directions),
        _trace_dimension(workspace, core_ids),
        _consistency_dimension(shortlist, top_directions),
        _traceability_dimension(referenced_ids, core_ids),
        _actionability_dimension(top_directions),
        _diversity_dimension(top_directions),
        _compactness_dimension(report_text),
    ]
    return finalize_scorecard(
        schema=SCORECARD_SCHEMA,
        workflow="idea-brainstorm",
        dimensions=dimensions,
        pass_score=pass_score,
        critical_dimensions=critical_dimensions,
        counts={
            "core_papers": len(core_ids),
            "shortlisted_directions": len(shortlist),
            "lead_directions": len(top_directions),
            "referenced_papers": len(referenced_ids),
            "report_words": len(re.findall(r"\b\w+\b", report_text)),
        },
        limitations=[
            "This scorecard validates the observable memo, decision fields, and artifact trace; it does not establish scientific novelty.",
            "Evidence quality remains bounded by the Workspace retrieval pool and the evidence level recorded in paper notes.",
        ],
    )


def write_idea_brainstorm_scorecard(workspace: Path) -> tuple[int, dict[str, Any]]:
    return write_scorecard(
        workspace,
        payload=evaluate_idea_brainstorm(workspace),
        json_name="IDEA_SCORECARD.json",
        markdown_name="IDEA_SCORECARD.md",
        title="Research Idea Scorecard",
    )


def validate_idea_brainstorm_scorecard(payload: dict[str, Any]) -> list[str]:
    return validate_scorecard(payload, schema=SCORECARD_SCHEMA)


def render_idea_brainstorm_scorecard(payload: dict[str, Any]) -> str:
    return render_scorecard(payload, title="Research Idea Scorecard")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows, _ = _read_jsonl_with_errors(path)
    return rows


def _read_jsonl_with_errors(path: Path) -> tuple[list[dict[str, Any]], list[int]]:
    if not path.exists() or path.stat().st_size == 0:
        return [], []
    rows: list[dict[str, Any]] = []
    malformed: list[int] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8", errors="ignore").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            malformed.append(line_number)
            continue
        if isinstance(value, dict):
            rows.append(value)
        else:
            malformed.append(line_number)
    return rows, malformed


def _core_paper_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {
            str(row.get("paper_id") or "").strip()
            for row in csv.DictReader(handle)
            if str(row.get("paper_id") or "").strip()
        }


def _referenced_paper_ids(*groups: list[dict[str, Any]]) -> set[str]:
    paper_ids: set[str] = set()
    for records in groups:
        for record in records:
            values = record.get("paper_ids") or []
            if isinstance(values, str):
                values = [values]
            paper_ids.update(str(value).strip() for value in values if str(value).strip())
    return paper_ids


def _rubric_policy(workspace: Path) -> tuple[int, set[str]]:
    return load_scorecard_policy(
        workspace,
        default_pass_score=DEFAULT_PASS_SCORE,
        default_critical_dimensions=DEFAULT_CRITICAL_DIMENSIONS,
    )


def _artifact_dimension(workspace: Path) -> dict[str, Any]:
    required = (
        "output/REPORT.md",
        "output/APPENDIX.md",
        "output/REPORT.json",
        "papers/core_set.csv",
    )
    missing = [relpath for relpath in required if not (workspace / relpath).exists() or (workspace / relpath).stat().st_size == 0]
    return _dimension(
        "artifact_completeness",
        "Artifact completeness",
        passed=not missing,
        partial=len(missing) < len(required),
        evidence="Memo bundle and core set are present." if not missing else f"Missing: {', '.join(missing)}",
        repair_surface=missing or ["pipelines/idea-brainstorm.pipeline.md"],
    )


def _structure_dimension(report: str, top_directions: list[dict[str, Any]]) -> dict[str, Any]:
    required = (
        "Scope and framing",
        "Big-picture takeaways",
        "Top directions at a glance",
        "Other promising but not prioritized directions",
        "Cross-cutting discussion questions",
        "Uncertainty and disagreement",
        "Suggested next reading / next discussion step",
    )
    missing = [label for label in required if label not in report]
    expanded = len(re.findall(r"(?m)^##\s+\d+\.\s+Direction\s+\d+", report))
    expected = len(top_directions)
    passed = bool(report.strip()) and not missing and expected >= 1 and expanded == expected
    return _dimension(
        "deliverable_structure",
        "Deliverable structure",
        passed=passed,
        partial=bool(report.strip()) and len(missing) <= 2 and expanded > 0,
        evidence=(
            f"All memo sections are present and {expanded} lead directions are expanded."
            if passed
            else f"Missing sections={', '.join(missing) if missing else 'none'}; expanded={expanded}; expected={expected}."
        ),
        repair_surface=[".codex/skills/idea-memo-writer/SKILL.md", "output/REPORT.md"],
    )


def _trace_dimension(workspace: Path, core_ids: set[str]) -> dict[str, Any]:
    present = [relpath for relpath in TRACE_ARTIFACTS if (workspace / relpath).exists() and (workspace / relpath).stat().st_size > 0]
    missing = [relpath for relpath in TRACE_ARTIFACTS if relpath not in present]
    if missing:
        return _dimension(
            "trace_chain",
            "Trace chain",
            passed=False,
            partial=len(present) >= 2,
            evidence=f"Missing: {', '.join(missing)}",
            repair_surface=missing,
        )

    errors: list[str] = []
    parsed: list[list[dict[str, Any]]] = []
    for relpath in TRACE_ARTIFACTS:
        records, malformed_lines = _read_jsonl_with_errors(workspace / relpath)
        parsed.append(records)
        if malformed_lines:
            errors.append(
                f"{relpath} has malformed JSONL lines: {', '.join(str(line) for line in malformed_lines)}"
            )
    signals, directions, screening, shortlist = parsed

    def unique_ids(records: list[dict[str, Any]], field: str, label: str) -> set[str]:
        values = [str(record.get(field) or "").strip() for record in records]
        if not records or any(not value for value in values):
            errors.append(f"{label} has missing {field} values")
        duplicates = sorted({value for value in values if value and values.count(value) > 1})
        if duplicates:
            errors.append(f"{label} repeats {field}: {', '.join(duplicates)}")
        return {value for value in values if value}

    def id_list(record: dict[str, Any], field: str, label: str) -> set[str]:
        value = record.get(field)
        if not isinstance(value, list):
            errors.append(f"{label}.{field} is not a list")
            return set()
        normalized = {str(item or "").strip() for item in value if str(item or "").strip()}
        if not normalized:
            errors.append(f"{label}.{field} is empty")
        return normalized

    signal_ids = unique_ids(signals, "signal_id", "signals")
    direction_ids = unique_ids(directions, "direction_id", "directions")
    screening_ids = unique_ids(screening, "direction_id", "screening")
    shortlist_ids = unique_ids(shortlist, "direction_id", "shortlist")

    signal_papers: dict[str, set[str]] = {}
    for record in signals:
        signal_id = str(record.get("signal_id") or "").strip()
        papers = id_list(record, "paper_ids", f"signal {signal_id or '<missing>'}")
        signal_papers[signal_id] = papers
        unknown = sorted(papers - core_ids)
        if unknown:
            errors.append(f"signal {signal_id} references unknown papers: {', '.join(unknown)}")

    direction_by_id: dict[str, dict[str, Any]] = {}
    for record in directions:
        direction_id = str(record.get("direction_id") or "").strip()
        direction_by_id[direction_id] = record
        linked_signals = id_list(record, "signal_ids", f"direction {direction_id or '<missing>'}")
        unknown_signals = sorted(linked_signals - signal_ids)
        if unknown_signals:
            errors.append(f"direction {direction_id} references unknown signals: {', '.join(unknown_signals)}")
        papers = id_list(record, "paper_ids", f"direction {direction_id or '<missing>'}")
        unknown_papers = sorted(papers - core_ids)
        if unknown_papers:
            errors.append(f"direction {direction_id} references unknown papers: {', '.join(unknown_papers)}")
        linked_papers = set().union(*(signal_papers.get(signal_id, set()) for signal_id in linked_signals))
        if papers - linked_papers:
            errors.append(f"direction {direction_id} has papers not inherited from its signals")

    if screening_ids - direction_ids:
        errors.append("screening references unknown directions: " + ", ".join(sorted(screening_ids - direction_ids)))
    if shortlist_ids - screening_ids:
        errors.append("shortlist references unscreened directions: " + ", ".join(sorted(shortlist_ids - screening_ids)))

    screening_by_id = {
        str(record.get("direction_id") or "").strip(): record
        for record in screening
        if str(record.get("direction_id") or "").strip()
    }
    invalid_recommendations = sorted(
        direction_id
        for direction_id in shortlist_ids
        if str(screening_by_id.get(direction_id, {}).get("recommendation") or "").strip().lower()
        not in {"keep", "maybe"}
    )
    if invalid_recommendations:
        errors.append(
            "shortlist includes directions not retained by screening: "
            + ", ".join(invalid_recommendations)
        )

    for record in shortlist:
        direction_id = str(record.get("direction_id") or "").strip()
        direction = direction_by_id.get(direction_id) or {}
        shortlist_signals = id_list(record, "signal_ids", f"shortlist {direction_id or '<missing>'}")
        direction_signals = {
            str(item or "").strip()
            for item in direction.get("signal_ids") or []
            if str(item or "").strip()
        } if isinstance(direction.get("signal_ids"), list) else set()
        if shortlist_signals != direction_signals:
            errors.append(f"shortlist {direction_id} does not preserve direction signal IDs")
        shortlist_papers = id_list(record, "paper_ids", f"shortlist {direction_id or '<missing>'}")
        direction_papers = {
            str(item or "").strip()
            for item in direction.get("paper_ids") or []
            if str(item or "").strip()
        } if isinstance(direction.get("paper_ids"), list) else set()
        if shortlist_papers - direction_papers:
            errors.append(f"shortlist {direction_id} introduces papers outside its direction")

    return _dimension(
        "trace_chain",
        "Trace chain",
        passed=not errors,
        partial=bool(signal_ids and direction_ids and screening_ids and shortlist_ids),
        evidence=(
            f"Joined {len(signal_ids)} signals -> {len(direction_ids)} directions -> "
            f"{len(screening_ids)} screened -> {len(shortlist_ids)} shortlisted records."
            if not errors
            else "; ".join(errors[:5])
        ),
        repair_surface=list(TRACE_ARTIFACTS),
    )


def shortlist_report_join_errors(
    shortlist: list[dict[str, Any]],
    top: list[dict[str, Any]],
) -> list[str]:
    """Join report directions to shortlist rank and evidence identity."""

    if not top:
        return ["report has no top directions"]
    if len(shortlist) < len(top):
        return [f"report has {len(top)} top directions but shortlist has {len(shortlist)} records"]

    errors: list[str] = []
    for index, (shortlist_record, report_record) in enumerate(
        zip(shortlist[: len(top)], top),
        start=1,
    ):
        for field in ("rank", "direction_id", "title"):
            expected = str(shortlist_record.get(field) or "").strip()
            actual = str(report_record.get(field) or "").strip()
            if not expected or actual != expected:
                errors.append(
                    f"rank {index} {field} mismatch: shortlist={expected or '<missing>'}, report={actual or '<missing>'}"
                )
        for field in ("signal_ids", "paper_ids"):
            expected_values = shortlist_record.get(field)
            actual_values = report_record.get(field)
            expected = sorted(
                str(item or "").strip()
                for item in expected_values
                if str(item or "").strip()
            ) if isinstance(expected_values, list) else []
            actual = sorted(
                str(item or "").strip()
                for item in actual_values
                if str(item or "").strip()
            ) if isinstance(actual_values, list) else []
            if actual != expected:
                errors.append(
                    f"rank {index} {field} mismatch: shortlist={expected}, report={actual}"
                )
    return errors


def _consistency_dimension(shortlist: list[dict[str, Any]], top: list[dict[str, Any]]) -> dict[str, Any]:
    errors = shortlist_report_join_errors(shortlist, top)
    passed = not errors
    return _dimension(
        "shortlist_report_consistency",
        "Shortlist/report consistency",
        passed=passed,
        partial=bool(shortlist and top),
        evidence=(
            "Lead directions preserve shortlist rank and evidence identity."
            if passed
            else "; ".join(errors[:5])
        ),
        repair_surface=[".codex/skills/idea-memo-writer/SKILL.md", "output/REPORT.json", "output/trace/IDEA_SHORTLIST.jsonl"],
    )


def _traceability_dimension(referenced: set[str], core_ids: set[str]) -> dict[str, Any]:
    valid = referenced & core_ids
    invalid = sorted(referenced - core_ids)
    passed = len(valid) >= 3 and not invalid
    return _dimension(
        "evidence_traceability",
        "Evidence traceability",
        passed=passed,
        partial=bool(valid),
        evidence=f"Valid paper pointers={len(valid)}; invalid pointers={', '.join(invalid) if invalid else 'none'}.",
        repair_surface=["papers/core_set.csv", "output/trace/IDEA_SHORTLIST.jsonl", ".codex/skills/idea-shortlist-curator/SKILL.md"],
    )


def _actionability_dimension(top: list[dict[str, Any]]) -> dict[str, Any]:
    complete = 0
    for item in top:
        anchors = item.get("anchor_reading_notes") or []
        complete += int(
            bool(str(item.get("one_line_thesis") or "").strip())
            and bool(item.get("first_probes"))
            and bool(item.get("kill_criteria") or item.get("what_would_change_mind"))
            and len(anchors) >= 2
            and bool(str(item.get("evidence_confidence") or "").strip())
        )
    passed = len(top) >= 1 and complete == len(top)
    return _dimension(
        "direction_actionability",
        "Direction actionability",
        passed=passed,
        partial=complete > 0,
        evidence=f"{complete}/{len(top)} lead directions contain a thesis, first probe, kill criterion, evidence confidence, and at least two anchor notes.",
        repair_surface=[".codex/skills/idea-shortlist-curator/SKILL.md", "output/trace/IDEA_SHORTLIST.jsonl"],
    )


def _diversity_dimension(top: list[dict[str, Any]]) -> dict[str, Any]:
    axes = {
        name: {str(item.get(name) or "").strip() for item in top if str(item.get(name) or "").strip()}
        for name in ("cluster", "direction_type", "program_kind")
    }
    diverse_axes = [name for name, values in axes.items() if len(values) >= 2]
    return _dimension(
        "direction_diversity",
        "Direction diversity",
        passed=len(top) >= 2 and len(diverse_axes) >= 2,
        partial=len(top) >= 2 and bool(diverse_axes),
        evidence=f"Diverse axes={', '.join(diverse_axes) if diverse_axes else 'none'}; " + "; ".join(f"{name}={len(values)}" for name, values in axes.items()),
        repair_surface=[".codex/skills/idea-shortlist-curator/SKILL.md", "output/trace/IDEA_SHORTLIST.jsonl"],
    )


def _compactness_dimension(report: str) -> dict[str, Any]:
    word_count = len(re.findall(r"\b\w+\b", report))
    return _dimension(
        "compactness",
        "Compactness",
        passed=300 <= word_count <= 4500,
        partial=150 <= word_count <= 6500,
        evidence=f"Word count={word_count}; expected 300-4500 words.",
        repair_surface=[".codex/skills/idea-memo-writer/SKILL.md", "output/REPORT.md"],
    )
