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
        _trace_dimension(workspace),
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
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


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


def _trace_dimension(workspace: Path) -> dict[str, Any]:
    present = [relpath for relpath in TRACE_ARTIFACTS if (workspace / relpath).exists() and (workspace / relpath).stat().st_size > 0]
    missing = [relpath for relpath in TRACE_ARTIFACTS if relpath not in present]
    return _dimension(
        "trace_chain",
        "Trace chain",
        passed=not missing,
        partial=len(present) >= 2,
        evidence="Signals, direction pool, screening, and shortlist sidecars are present." if not missing else f"Missing: {', '.join(missing)}",
        repair_surface=missing or list(TRACE_ARTIFACTS),
    )


def _consistency_dimension(shortlist: list[dict[str, Any]], top: list[dict[str, Any]]) -> dict[str, Any]:
    top_titles = [str(item.get("title") or "").strip() for item in top]
    shortlist_titles = [str(item.get("title") or "").strip() for item in shortlist[: len(top)]]
    passed = bool(top_titles) and top_titles == shortlist_titles and all(top_titles)
    return _dimension(
        "shortlist_report_consistency",
        "Shortlist/report consistency",
        passed=passed,
        partial=bool(set(top_titles) & set(shortlist_titles)),
        evidence="Lead directions preserve shortlist rank order." if passed else f"Report titles={top_titles}; shortlist titles={shortlist_titles}.",
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
