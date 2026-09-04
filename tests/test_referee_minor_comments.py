"""Regression: Minor Comments list the real minor gaps, deduplicated.

The referee "Minor Comments" section iterated `major_gaps[:3]` and printed their
minimal_fix strings — so it showed duplicated copies of the MAJOR concerns' fix
and never surfaced the actual minor gaps. A referee got no real minor feedback.

The renderer now takes the structured minor_gaps, deduplicates them, and lists
each with its claim reference and concern (plus fix). It falls back to the
distinct major fixes only when no structured minor gaps are supplied.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_rubric_review_markdown

_MAJOR = [{"claim_id": "C05", "gap_id": "G05", "gap": "underspecified", "minimal_fix": "state the metric"}]
_MINOR = [
    {"claim_id": "C01", "gap": "The claim still needs an explicit baseline/protocol check.", "minimal_fix": "Add a comparison table."},
    {"claim_id": "C02", "gap": "The conceptual claim needs a clearer boundary.", "minimal_fix": "Clarify what it excludes."},
    {"claim_id": "C03", "gap": "The claim still needs an explicit baseline/protocol check.", "minimal_fix": "Add a comparison table."},
]


def _minor(review: str) -> str:
    return review.split("### Minor Comments", 1)[1].split("### Recommendation", 1)[0]


def test_minor_comments_list_real_deduplicated_minor_gaps() -> None:
    review = render_rubric_review_markdown(
        claim_count=3, gap_count=4, major_gaps=_MAJOR,
        novelty_available=True, minor_gaps=_MINOR,
    )
    minor = _minor(review)
    # Both distinct minor concerns appear, tied to their claims.
    assert "Claim C01" in minor and "baseline/protocol check" in minor, minor
    assert "Claim C02" in minor and "clearer boundary" in minor, minor
    # Deduplicated: the C01/C03 identical concern is not listed twice.
    assert minor.count("baseline/protocol check") == 1, minor
    # It is NOT echoing the major concern's fix.
    assert "state the metric" not in minor


def test_minor_comments_fall_back_to_distinct_major_fixes() -> None:
    review = render_rubric_review_markdown(
        claim_count=3, gap_count=2, major_gaps=_MAJOR, novelty_available=True
    )
    minor = _minor(review)
    assert "state the metric" in minor  # graceful fallback when no minor gaps supplied
