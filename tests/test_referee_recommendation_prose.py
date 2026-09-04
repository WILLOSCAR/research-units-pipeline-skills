"""Regression: the referee Recommendation is reader-facing prose, not a bare enum.

A read of a generated REVIEW.md found the Recommendation section contained
only the machine enum label "- weak_accept", not referee prose — an author/editor
reads it as raw pipeline output.

`render_rubric_review_markdown` now renders a verdict sentence tied to the report's
concern profile ("Weak accept: no major concerns, N minor concerns to address in
revision." / "Weak reject: N major concern(s) must be resolved ..."). The
recommendation-consistency scorecard dimension (`_recommendation_dimension`) parses
the leading verdict phrase from the prose (still accepting a legacy bare enum).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_evaluation import _recommendation_dimension
from tooling.review_render import render_rubric_review_markdown

_CLAIMS = [{"claim_id": "C01", "text": "5-18% gains on CIFAR-10C.", "claim_type": "empirical"}]
_NOVELTY = {"related_work": "Liang et al.", "overlap": "x", "delta": "y"}


def _rec_section(review: str) -> str:
    return review.split("### Recommendation", 1)[1]


def test_recommendation_is_prose_not_bare_enum_accept() -> None:
    review = render_rubric_review_markdown(
        claim_count=2, gap_count=2, major_gaps=[], novelty_available=True, claims=_CLAIMS,
        minor_gaps=[{"claim_id": "C01", "gap": "needs baseline"}, {"claim_id": "C02", "gap": "needs boundary"}],
        novelty_row=_NOVELTY,
    )
    section = _rec_section(review)
    assert "Weak accept:" in section, section
    assert "no major concerns" in section, section
    assert "2 minor concerns to address in revision" in section, section
    # Not a bare enum line.
    assert "- weak_accept" not in section, section


def test_recommendation_is_prose_not_bare_enum_reject() -> None:
    review = render_rubric_review_markdown(
        claim_count=1, gap_count=1,
        major_gaps=[{"claim_id": "C01", "gap": "no baseline", "minimal_fix": "add"}],
        novelty_available=True, claims=_CLAIMS, minor_gaps=[], novelty_row=_NOVELTY,
    )
    section = _rec_section(review)
    assert "Weak reject:" in section, section
    assert "must be resolved" in section, section
    assert "- weak_reject" not in section, section


def test_scorecard_parses_verdict_from_prose() -> None:
    # The recommendation-consistency dimension reads the verdict from prose.
    accept = "### Recommendation\n- Weak accept: no major concerns, 1 minor concern to address in revision.\n"
    d = _recommendation_dimension(accept, gaps=[])
    assert "Recommendation=weak_accept" in d["evidence"], d["evidence"]

    reject = "### Recommendation\n- Weak reject: 1 major concern must be resolved before the manuscript can be accepted.\n"
    d2 = _recommendation_dimension(reject, gaps=[{"severity": "major"}])
    assert "Recommendation=weak_reject" in d2["evidence"], d2["evidence"]

    # An accept verdict with a major gap is still flagged inconsistent.
    d3 = _recommendation_dimension(accept, gaps=[{"severity": "major"}])
    assert d3["status"] != "PASS", d3

    # Legacy bare-enum line still parses.
    d4 = _recommendation_dimension("### Recommendation\n- weak_accept\n", gaps=[])
    assert "Recommendation=weak_accept" in d4["evidence"], d4["evidence"]
