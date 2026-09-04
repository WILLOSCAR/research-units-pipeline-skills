"""Regression: referee Novelty note is honest when no related work is available.

When a novelty-matrix row is the "related works unavailable" sentinel (the
manuscript has no related-work / references section), the referee renderer used
to print the sentinel verbatim: "Closest related work is related works
unavailable (unavailable); delta vs it: unavailable." The renderer now emits an
honest "Novelty could not be positioned ..." note instead.

NOTE: whether the paper-review scorecard should BLOCK such a manuscript (current
policy, asserted by test_review_architecture) or degrade gracefully is a
deliberate design decision; this cycle intentionally did NOT change that policy.
Only the reader-facing sentinel leak is fixed here.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_rubric_review_markdown


def test_renderer_novelty_note_when_unavailable() -> None:
    review = render_rubric_review_markdown(
        claim_count=2, gap_count=0, major_gaps=[], novelty_available=True,
        novelty_row={"claim_id": "C01", "related_work": "related works unavailable",
                     "overlap": "unavailable", "delta": "unavailable"},
    )
    novelty = review.split("### Novelty", 1)[1].split("###", 1)[0]
    assert "could not be positioned" in novelty, novelty
    # The raw sentinel must not leak into the reader-facing note.
    assert "related works unavailable" not in novelty, novelty


def test_renderer_novelty_note_normal_row_unchanged() -> None:
    review = render_rubric_review_markdown(
        claim_count=1, gap_count=0, major_gaps=[], novelty_available=True,
        novelty_row={"claim_id": "C01", "related_work": "Salemi et al. 2024",
                     "overlap": "adjacent setting", "delta": "the gate"},
    )
    novelty = review.split("### Novelty", 1)[1].split("###", 1)[0]
    # the reader-facing note shows the author phrase ("Salemi et al."),
    # not the full reference with the trailing year.
    assert "Salemi et al." in novelty, novelty
    assert "the gate" in novelty, novelty
