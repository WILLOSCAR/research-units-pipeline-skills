"""Regression: referee Novelty/Impact does not overclaim the "closest" related work.

A read (real P0006 manuscript via the full paper-review engine) surfaced a
an initially ambiguous case: the review's Novelty
note asserted "Closest related work is Behler and Parrinello" and Impact said the
contribution "is positioned against" it — but the novelty matrix lists works in
CITATION order, not relevance rank, so the FIRST-cited foundational work was
mislabeled the semantically-closest comparator (the manuscript also cites the more
relevant NequIP/MACE). The tool never made a relevance judgment.

`render_rubric_review_markdown` now frames the row as "A cited prior work to
position against ... Confirm this is the closest comparator (the matrix lists works
in citation order, not relevance rank)" and softens Impact to "positioned relative
to a cited prior work", removing the unsupported semantic-relevance claim.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_rubric_review_markdown

_ROW = {"claim_id": "C01", "related_work": "Behler and Parrinello",
        "overlap": "neural-network potentials", "delta": "no explicit delta stated"}
_CLAIMS = [{"claim_id": "C01", "text": "A universal harmonic potential predicts phonon spectra.", "claim_type": "empirical"}]


def _section(review: str, header: str) -> str:
    return review.split(header, 1)[1].split("###", 1)[0] if header in review else ""


def test_novelty_note_does_not_claim_closest() -> None:
    review = render_rubric_review_markdown(
        claim_count=1, gap_count=1, major_gaps=[], novelty_available=True,
        claims=_CLAIMS, novelty_row=_ROW, minor_gaps=[{"claim_id": "C01", "gap": "g", "minimal_fix": "f"}],
    )
    novelty = _section(review, "### Novelty")
    assert "Closest related work is" not in novelty, novelty
    # The honesty caveat (the matrix is citation-ordered, not relevance-ranked, so
    # the tool must not overclaim "closest") is now stated in reader-facing terms
    # rather than by naming the internal "novelty matrix" / "citation order":
    # the note must still hedge that this may not be the most comparable work.
    assert "may not be the most directly comparable" in novelty, novelty
    assert "citation order" not in novelty and "novelty matrix" not in novelty, novelty
    assert "Behler and Parrinello" in novelty, novelty


def test_impact_softens_positioned_against() -> None:
    review = render_rubric_review_markdown(
        claim_count=1, gap_count=1, major_gaps=[], novelty_available=True,
        claims=_CLAIMS, novelty_row=_ROW, minor_gaps=[{"claim_id": "C01", "gap": "g", "minimal_fix": "f"}],
    )
    impact = _section(review, "### Impact")
    assert "positioned relative to a cited prior work" in impact, impact
    assert "is positioned against Behler" not in impact, impact


def test_novelty_note_still_carries_related_work_and_delta() -> None:
    review = render_rubric_review_markdown(
        claim_count=1, gap_count=0, major_gaps=[], novelty_available=True,
        claims=_CLAIMS, novelty_row={"claim_id": "C01", "related_work": "Salemi et al. 2024",
                                      "overlap": "adjacent setting", "delta": "the gate"},
    )
    novelty = _section(review, "### Novelty")
    # The reader-facing note reduces the reference to a clean author phrase
    #: "Salemi et al. 2024" -> "Salemi et al." (year dropped), and still
    # carries the manuscript's stated advance.
    assert "Salemi et al." in novelty and "the gate" in novelty, novelty
