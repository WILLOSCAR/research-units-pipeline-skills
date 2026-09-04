"""Regression: referee report frames a conceptual paper appropriately.

A review (a purely-conceptual / position paper with
no empirical claims) found the referee report used empirical-paper language: it
called the proposed framework a "result", said the impact would be to "compare
and reproduce", and asked each claim to state a "protocol, metric". A position
paper is judged on argument clarity and positioning, not reproducibility.

`render_rubric_review_markdown` now detects a paper with no empirical claim and
adapts Summary/Clarity/Impact: "headline contribution" (not "result"), "scope
boundary and relation to prior work" (not "protocol, metric"), and impact framed
as sharpening the argument (not "compare and reproduce"). Empirical papers are
unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_rubric_review_markdown


_CONCEPTUAL = [
    {"claim_id": "C01", "text": "We propose a conceptual framework for compositional generalization.",
     "claim_type": "conceptual", "scope": "abstract"},
    {"claim_id": "C02", "text": "Binding stability is the governing primitive.",
     "claim_type": "conceptual", "scope": "framework"},
]
_EMPIRICAL = [
    {"claim_id": "C01", "text": "GAD improves top-1 accuracy by 2.3 points over the baseline.",
     "claim_type": "empirical", "scope": "abstract"},
]
_ROW = {"claim_id": "C01", "related_work": "Lake et al. 2017", "overlap": "x", "delta": "the stability axis"}


def _sec(review: str, header: str) -> str:
    return review.split(header, 1)[1].split("###", 1)[0]


def test_conceptual_paper_impact_not_result_or_reproduce() -> None:
    review = render_rubric_review_markdown(
        claim_count=2, gap_count=1, major_gaps=[], novelty_available=True,
        claims=_CONCEPTUAL, novelty_row=_ROW,
        minor_gaps=[{"claim_id": "C01", "gap": "needs a clearer boundary", "minimal_fix": "clarify"}],
    )
    impact = _sec(review, "### Impact").lower()
    assert "headline contribution" in impact, impact
    assert "reproduce" not in impact, impact
    assert "headline result" not in impact, impact
    clarity = _sec(review, "### Clarity").lower()
    assert "relation to prior work" in clarity, clarity
    assert "protocol, metric" not in clarity, clarity


def test_empirical_paper_framing_unchanged() -> None:
    review = render_rubric_review_markdown(
        claim_count=1, gap_count=1, major_gaps=[{"claim_id": "C01", "gap_id": "G01", "gap": "underspecified", "minimal_fix": "state metric"}],
        novelty_available=True, claims=_EMPIRICAL, novelty_row=_ROW,
    )
    impact = _sec(review, "### Impact").lower()
    assert "headline result" in impact, impact
    clarity = _sec(review, "### Clarity").lower()
    assert "protocol, metric" in clarity, clarity
