"""Regression: research-brief Scope does not overclaim the first paper as the topic anchor.

A read of a research-brief SNAPSHOT (real embodied-adaptation corpus via the
full engine) found the Scope line "The boundary is anchored by [P0001 - CANDI:
Curated Test-Time Adaptation for Multivariate Time-Series Anomaly Detection ...]" —
CANDI is a narrow anomaly-detection paper, but it is merely chosen[0] (core-set
order), not a topically-chosen anchor for the whole area. Presenting it as "anchoring
the boundary" overclaims a representativeness judgment the tool never made.

`render_research_brief_markdown` now labels chosen[0] accurately as "The first
listed core paper is [X]" instead of "The boundary is anchored by [X]".
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
         "abstract": "We study test-time adaptation under distribution shift."}
        for i in range(1, n + 1)
    ]


def _scope(brief: str) -> str:
    return brief.split("## Scope", 1)[1].split("## Key themes", 1)[0]


def test_scope_does_not_claim_anchored_by() -> None:
    brief = render_research_brief_markdown(
        goal="# Goal\n\nOrient me on test-time adaptation.", papers=_papers(12),
        sections=["Methods", "Evaluation"],
    )
    scope = _scope(brief)
    assert "anchored by" not in scope, scope
    assert "The first listed paper is" in scope, scope
    assert "P0001 - Paper 1" in scope, scope


def test_scope_first_paper_line_present_for_small_set() -> None:
    brief = render_research_brief_markdown(
        goal="# Goal\n\nOrient me.", papers=_papers(3), sections=["Methods"],
    )
    scope = _scope(brief)
    assert "The first listed paper is" in scope, scope
    assert "anchored by" not in scope, scope


def test_scope_no_anchor_line_when_no_papers() -> None:
    brief = render_research_brief_markdown(
        goal="# Goal\n\nOrient me.", papers=[], sections=["Methods"],
    )
    scope = _scope(brief)
    assert "The first listed paper is" not in scope, scope
    assert "anchored by" not in scope, scope
