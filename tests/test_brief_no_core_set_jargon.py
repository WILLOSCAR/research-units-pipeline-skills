"""Regression: the research-brief SNAPSHOT prose uses no internal-selection jargon.

A read of a generated SNAPSHOT.md (real embodied-adaptation corpus)
found the reader-facing prose exposed the harness's internal selection vocabulary
to a researcher: "12 selected core-set papers" (Scope), "The first listed core
paper is [X]" (Scope anchor), and "The core set is deliberately compact" (Open
problems).

`render_research_brief_markdown` now uses plain reader-facing wording: "selected
papers", "The first listed paper is", "the selected set".
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_research_brief_markdown

# Internal-selection jargon that must not appear in the reader-facing brief.
_BANNED = ("core-set", "core set", "core paper", "ranked core")


def _papers(n: int) -> list[dict]:
    return [
        {"paper_id": f"P{i:04d}", "title": f"Paper {i}", "url": f"http://x/{i}",
         "abstract": "We study test-time adaptation under distribution shift."}
        for i in range(1, n + 1)
    ]


def test_snapshot_prose_has_no_core_set_jargon() -> None:
    brief = render_research_brief_markdown(
        goal="# Goal\n\nOrient me on test-time adaptation.", papers=_papers(12),
        sections=["Methods", "Evaluation"],
    )
    low = brief.lower()
    for phrase in _BANNED:
        assert phrase not in low, (phrase, brief)
    # The reader-facing replacements are present.
    assert "12 selected papers" in brief, brief
    assert "The first listed paper is" in brief, brief
    assert "The selected set is deliberately compact" in brief, brief


def test_snapshot_small_set_has_no_core_set_jargon() -> None:
    brief = render_research_brief_markdown(
        goal="# Goal\n\nOrient me.", papers=_papers(3), sections=["Methods"],
    )
    low = brief.lower()
    for phrase in _BANNED:
        assert phrase not in low, (phrase, brief)
