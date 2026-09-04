"""Regression: referee Novelty/Impact prose uses a clean author phrase and reads
as referee prose, not a pasted reference string or a generation note.

A read (real ML-interatomic-potentials manuscript with a two-author-heavy
Related Work, via the full paper-review engine) surfaced two coupled defects in
the '## Novelty' note:

  1. The related work was pasted as its FULL bibliographic string —
     "Behler and Parrinello. Generalized neural-network representation of
     potential energy surfaces. 2007." — whose internal periods make the
     sentence appear to end at "Behler and Parrinello." with the title/year
     dangling as a fragment.
  2. The note read as a generation instruction: "delta vs it: X. Confirm this
     is the closest comparator (...)".

`render_rubric_review_markdown` now (a) reduces the related-work entry to a
clean author phrase via `_related_work_label` (dropping the title and year), and
(b) states the delta and the citation-order caveat as referee prose. The honesty invariant (the matrix is citation-ordered, not relevance-ranked) is
preserved.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import _related_work_label, render_rubric_review_markdown

_CLAIMS = [{"claim_id": "C01", "text": "A universal harmonic potential predicts phonon spectra.", "claim_type": "empirical"}]


def _section(review: str, header: str) -> str:
    return review.split(header, 1)[1].split("###", 1)[0] if header in review else ""


def test_related_work_label_reduces_full_reference() -> None:
    assert _related_work_label(
        "Behler and Parrinello. Generalized neural-network representation of potential energy surfaces. 2007."
    ) == "Behler and Parrinello"
    assert _related_work_label("- Salemi et al. Retrieval-augmented methods. 2024.") == "Salemi et al."
    assert _related_work_label("Chen. Model-based online adaptation. 2022.") == "Chen"
    assert _related_work_label("Bartok and Csanyi. Gaussian approximation potentials. 2015.") == "Bartok and Csanyi"


def test_novelty_note_has_no_dangling_reference_fragment() -> None:
    row = {
        "claim_id": "C01",
        "related_work": "Behler and Parrinello. Generalized neural-network representation of potential energy surfaces. 2007.",
        "overlap": "neural-network potentials for energy surfaces",
        "delta": "the harmonic restriction that yields calibrated uncertainty",
    }
    review = render_rubric_review_markdown(
        claim_count=1, gap_count=1, major_gaps=[], novelty_available=True,
        claims=_CLAIMS, novelty_row=row, minor_gaps=[{"claim_id": "C01", "gap": "g", "minimal_fix": "f"}],
    )
    novelty = _section(review, "### Novelty")
    # The full title/year string must not be pasted into the referee prose.
    assert "Generalized neural-network representation" not in novelty, novelty
    assert "2007" not in novelty, novelty
    # The clean author phrase is present, the delta is stated, and the
    # no-overclaim honesty caveat is preserved.
    assert "Behler and Parrinello" in novelty, novelty
    assert "harmonic restriction" in novelty, novelty
    assert "may not be the most directly comparable" in novelty, novelty
    assert "novelty matrix" not in novelty and "citation order" not in novelty, novelty
    # The overlap renders as a relative clause ("the work of X, which ..."), not a
    # bare-verb parenthetical, and the author phrase is not repeated inside it.
    assert "the work of Behler and Parrinello, which" in novelty, novelty
    assert novelty.count("Behler and Parrinello") == 1, novelty


def test_novelty_note_is_referee_prose_not_generation_note() -> None:
    row = {"claim_id": "C01", "related_work": "Salemi et al. 2024", "overlap": "adjacent setting", "delta": "the gate"}
    review = render_rubric_review_markdown(
        claim_count=1, gap_count=0, major_gaps=[], novelty_available=True,
        claims=_CLAIMS, novelty_row=row,
    )
    novelty = _section(review, "### Novelty")
    # The telegraphic / instruction-like fragments are gone.
    assert "delta vs it:" not in novelty, novelty
    assert "Confirm this is the closest comparator" not in novelty, novelty
    # Still carries the substance.
    assert "Salemi et al." in novelty and "the gate" in novelty, novelty


def test_impact_uses_clean_author_phrase() -> None:
    row = {
        "claim_id": "C01",
        "related_work": "Behler and Parrinello. Generalized neural-network representation of potential energy surfaces. 2007.",
        "overlap": "neural-network potentials",
        "delta": "the harmonic restriction",
    }
    review = render_rubric_review_markdown(
        claim_count=1, gap_count=1, major_gaps=[], novelty_available=True,
        claims=_CLAIMS, novelty_row=row, minor_gaps=[{"claim_id": "C01", "gap": "g", "minimal_fix": "f"}],
    )
    impact = _section(review, "### Impact")
    if "cited prior work" in impact:
        assert "Generalized neural-network representation" not in impact, impact
        assert "Behler and Parrinello" in impact, impact
