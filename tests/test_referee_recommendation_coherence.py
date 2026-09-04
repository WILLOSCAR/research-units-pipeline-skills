"""Regression: referee recommendation is coherent with concern severity.

A read of a generated REVIEW.md (full paper-review engine on the real ml-interatomic
P0006 manuscript) found the report recommended "borderline" while its own body
stated "0 major concerns and 2 minor comments". A borderline verdict implies
substantive unresolved doubt, so it is inconsistent with a minor-only report — an
editor/author cannot reconcile the recommendation with the severity.

`render_rubric_review_markdown` derived `"weak_reject" if major else ("borderline"
if gap_count else "weak_accept")`, so ANY minor gap forced "borderline". It now
leans positive whenever there are 0 major concerns ("weak_accept" = accept with
minor revisions) and negative only when major concerns exist ("weak_reject"). A
genuine soundness problem is surfaced as a MAJOR gap upstream, so it still
lands in the weak_reject branch rather than a bland borderline.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_rubric_review_markdown


def _recommendation(review: str) -> str:
    """The recommendation is now reader-facing prose ("Weak accept: ..." /
    "Weak reject: ..."); return a normalized verdict token for coherence checks."""
    section = review.split("### Recommendation", 1)[1]
    line = next(ln.strip("- ").strip() for ln in section.splitlines() if ln.strip().startswith("- "))
    low = line.lower()
    if low.startswith("weak reject"):
        return "weak_reject"
    if low.startswith("weak accept"):
        return "weak_accept"
    return line


_CLAIMS = [{"claim_id": "C01", "text": "The method predicts phonon spectra.", "claim_type": "empirical"}]
_MINOR = [{"claim_id": "C01", "gap": "needs concrete metric", "minimal_fix": "state the number"}]
_MAJOR = [{"claim_id": "C01", "gap": "underspecified: no baseline", "minimal_fix": "add baseline"}]


def test_minor_only_report_leans_positive_not_borderline() -> None:
    review = render_rubric_review_markdown(
        claim_count=1, gap_count=3, major_gaps=[], novelty_available=True,
        claims=_CLAIMS, minor_gaps=_MINOR,
    )
    rec = _recommendation(review)
    assert rec == "weak_accept", rec
    assert "borderline" not in review.split("### Recommendation", 1)[1], review
    # Reader-facing prose, not a bare enum label.
    section = review.split("### Recommendation", 1)[1]
    assert "no major concerns" in section, section


def test_no_gaps_report_is_positive() -> None:
    review = render_rubric_review_markdown(
        claim_count=1, gap_count=0, major_gaps=[], novelty_available=True, claims=_CLAIMS,
    )
    assert _recommendation(review) == "weak_accept", review


def test_major_concern_leans_negative() -> None:
    review = render_rubric_review_markdown(
        claim_count=1, gap_count=1, major_gaps=_MAJOR, novelty_available=True,
        claims=_CLAIMS, minor_gaps=[],
    )
    assert _recommendation(review) == "weak_reject", review
    # Prose names the blocking concern count.
    assert "must be resolved" in review.split("### Recommendation", 1)[1], review


def test_recommendation_never_borderline_for_minor_only() -> None:
    # Sweep minor gap counts: none should produce "borderline".
    for n in range(0, 6):
        review = render_rubric_review_markdown(
            claim_count=1, gap_count=n, major_gaps=[], novelty_available=True,
            claims=_CLAIMS, minor_gaps=_MINOR if n else [],
        )
        assert _recommendation(review) != "borderline", (n, review)
