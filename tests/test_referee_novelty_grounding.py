"""Regression: the referee Novelty note cites the closest related work + delta.

The Novelty section said only "Novelty was assessed conservatively from the
available novelty matrix" — it named neither the closest related work nor the
delta, though the novelty matrix (NOVELTY_MATRIX.tsv) carries exactly that per
claim. The renderer now accepts a novelty_row and cites related_work + delta,
falling back to the generic note when no row is supplied.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_rubric_review_markdown

_ROW = {
    "claim_id": "C01",
    "claim": "It improves F1 by 5.1 points on TCGA.",
    "related_work": "Salemi et al. Retrieval-augmented methods for variant calling. 2024.",
    "overlap": "adjacent problem setting",
    "delta": "claimed method delta requires verification",
}


def _novelty(review: str) -> str:
    return review.split("### Novelty", 1)[1].split("###", 1)[0]


def test_novelty_cites_related_work_and_delta() -> None:
    review = render_rubric_review_markdown(
        claim_count=2, gap_count=0, major_gaps=[], novelty_available=True, novelty_row=_ROW
    )
    novelty = _novelty(review)
    assert "Salemi et al" in novelty and "adjacent problem setting" in novelty, novelty
    assert "requires verification" in novelty
    assert "assessed conservatively from the available novelty matrix" not in novelty


def test_novelty_falls_back_without_row() -> None:
    review = render_rubric_review_markdown(
        claim_count=2, gap_count=0, major_gaps=[], novelty_available=True
    )
    novelty = _novelty(review)
    assert "assessed conservatively from the available novelty matrix" in novelty
