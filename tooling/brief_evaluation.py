from __future__ import annotations

import csv
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


SCORECARD_SCHEMA = "research-brief-scorecard.v1"
DEFAULT_PASS_SCORE = 80
DEFAULT_CRITICAL_DIMENSIONS = {
    "brief_specificity",
    "deliverable_structure",
    "reading_path",
    "source_traceability",
    "theme_grounding",
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
    scope_pointer_ids = set(re.findall(r"\bP\d{4}\b", _section(snapshot, "## Scope")))
    theme_lines = [
        line.strip()
        for line in _section(snapshot, "## Key themes").splitlines()
        if line.strip().startswith(("- ", "* "))
    ]
    theme_pointer_sets = [set(re.findall(r"\bP\d{4}\b", line)) for line in theme_lines]

    pass_score, critical_dimensions = _rubric_policy(workspace)
    dimensions = [
        _artifact_dimension(snapshot_path, workspace / "papers" / "core_set.csv"),
        _structure_dimension(snapshot),
        _specificity_dimension(snapshot),
        _traceability_dimension(pointer_ids, paper_ids),
        _reading_path_dimension(reading_ids, paper_ids),
        _grounding_dimension(scope_pointer_ids, theme_pointer_sets, paper_ids),
        _compactness_dimension(snapshot),
    ]
    return finalize_scorecard(
        schema=SCORECARD_SCHEMA,
        workflow="research-brief",
        dimensions=dimensions,
        pass_score=pass_score,
        critical_dimensions=critical_dimensions,
        counts={
            "core_papers": len(paper_ids),
            "unique_pointers": len(pointer_ids),
            "reading_path_pointers": len(reading_ids),
            "words": len(re.findall(r"\b\w+\b", snapshot)),
        },
        limitations=[
            "This scorecard validates structure, compactness, and pointer traceability; it does not judge whether the selected literature is complete or scientifically correct.",
            "Reading-path quality is bounded by the papers already present in the Workspace core set.",
        ],
    )


def write_research_brief_scorecard(workspace: Path) -> tuple[int, dict[str, Any]]:
    return write_scorecard(
        workspace,
        payload=evaluate_research_brief(workspace),
        json_name="BRIEF_SCORECARD.json",
        markdown_name="BRIEF_SCORECARD.md",
        title="Research Brief Scorecard",
    )


def validate_research_brief_scorecard(payload: dict[str, Any]) -> list[str]:
    return validate_scorecard(payload, schema=SCORECARD_SCHEMA)


def render_research_brief_scorecard(payload: dict[str, Any]) -> str:
    return render_scorecard(payload, title="Research Brief Scorecard")


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
    return load_scorecard_policy(
        workspace,
        default_pass_score=DEFAULT_PASS_SCORE,
        default_critical_dimensions=DEFAULT_CRITICAL_DIMENSIONS,
    )


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


def _grounding_dimension(
    scope_pointer_ids: set[str],
    theme_pointer_sets: list[set[str]],
    paper_ids: set[str],
) -> dict[str, Any]:
    grounded_scope = scope_pointer_ids & paper_ids
    grounded_themes = sum(bool(pointers & paper_ids) for pointers in theme_pointer_sets)
    total_themes = len(theme_pointer_sets)
    grounded_papers = grounded_scope | set().union(
        *(pointers & paper_ids for pointers in theme_pointer_sets)
    )
    passed = (
        bool(grounded_scope)
        and total_themes > 0
        and grounded_themes == total_themes
        and len(grounded_papers) >= 2
    )
    return _dimension(
        "theme_grounding",
        "Theme grounding",
        passed=passed,
        partial=bool(grounded_scope) or grounded_themes > 0,
        evidence=(
            f"Scope grounded={bool(grounded_scope)}; key-theme bullets with valid core-set "
            f"pointers={grounded_themes}/{total_themes}; unique grounded core papers={len(grounded_papers)}/2 minimum."
        ),
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
