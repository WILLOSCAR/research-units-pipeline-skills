"""Regression: the research-brief "What to read first" middle steps are distinct.

A read of a generated SNAPSHOT.md (real embodied-adaptation and clinical
corpora) found the two MIDDLE reading-path steps ("Read next" and "Then") giving
byte-identical notes — "build on the entry point before comparing approaches
across the selected set." — so the middle of the path read as boilerplate rather
than a genuine sequence. This is the read-first path's
CONTENT-distinctness axis (established the Start/Read-next/Then/Finally
sequencing; the middle reasons were still a single shared string).

`render_research_brief_markdown` now gives each middle step a distinct note:
advancing through the comparison lenses when they exist, else a position-distinct
sequencing role.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_research_brief_markdown


def _papers(n: int) -> list[dict]:
    return [
        {"paper_id": f"P{i:04d}", "title": f"Paper {i}", "url": f"http://x/{i}",
         "abstract": f"We propose method {i} for test-time adaptation and report distinct result {i}."}
        for i in range(1, n + 1)
    ]


def _section(brief: str, name: str) -> str:
    return brief.split(f"## {name}", 1)[1].split("\n## ", 1)[0]


def _middle_notes(read_first: str) -> list[str]:
    notes = []
    for ln in read_first.splitlines():
        ln = ln.strip()
        if ln.startswith("- Read next") or ln.startswith("- Then"):
            notes.append(ln.split(":", 1)[1].strip() if ":" in ln else ln)
    return notes


def test_middle_steps_are_distinct_single_topic_corpus() -> None:
    # No section adds a dimension beyond the topic -> lenses empty -> fallbacks.
    brief = render_research_brief_markdown(
        goal="# Goal\n\nOrient me on test-time adaptation.", papers=_papers(12),
        sections=["Test Time Adaptation", "Distribution Shift"],
    )
    read_first = _section(brief, "What to read first")
    notes = _middle_notes(read_first)
    assert len(notes) == 2, read_first
    assert notes[0] != notes[1], notes
    # The old shared boilerplate line must be gone.
    assert "build on the entry point before comparing approaches across the selected set" not in read_first, read_first


def test_middle_steps_advance_through_lenses_when_present() -> None:
    brief = render_research_brief_markdown(
        goal="# Goal\n\nSurvey graph neural networks.", papers=_papers(12),
        sections=["Introduction", "Benchmark Design", "Uncertainty Calibration", "Deployment Latency", "Conclusion"],
    )
    read_first = _section(brief, "What to read first")
    notes = _middle_notes(read_first)
    assert len(notes) == 2 and notes[0] != notes[1], read_first
    # Distinct lenses drive the two middle steps.
    assert "Uncertainty Calibration" in read_first and "Deployment Latency" in read_first, read_first


def test_first_and_last_reasons_unchanged() -> None:
    brief = render_research_brief_markdown(
        goal="# Goal\n\nOrient me.", papers=_papers(12), sections=["Methods", "Evaluation"],
    )
    read_first = _section(brief, "What to read first")
    assert "it is the entry point for the topic" in read_first, read_first
    assert "read last to see where the open problems and risks concentrate" in read_first, read_first
