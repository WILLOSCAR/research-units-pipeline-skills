"""Regression: the Clarity note names the specific claim behind the concern.

The referee Clarity section was a generic sentence ("whether each top claim
states its protocol, metric, and boundary explicitly") that named no claim.
Grounding data is available in-hand: `major_gaps` carry a claim_id and `claims`
carry that claim's text. The renderer now names the specific claim (and quotes
it) behind the first major concern, falling back to the generic note when no
major gap / claim text is available.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_rubric_review_markdown

_CLAIMS = [
    {"claim_id": "C01", "text": "It improves F1 by 5.1 points on TCGA.", "claim_type": "empirical", "scope": "Abstract scope"},
    {"claim_id": "C03", "text": "The coverage-calibrated filter improves variant calling without test-time weight updates.", "claim_type": "empirical", "scope": "6. Conclusion scope"},
]
_MAJOR = [{"claim_id": "C03", "gap_id": "G03", "gap": "underspecified", "minimal_fix": "state metric"}]


def _clarity(review: str) -> str:
    return review.split("### Clarity", 1)[1].split("###", 1)[0]


def test_clarity_names_the_specific_claim() -> None:
    review = render_rubric_review_markdown(
        claim_count=len(_CLAIMS), gap_count=3, major_gaps=_MAJOR,
        novelty_available=True, claims=_CLAIMS,
    )
    clarity = _clarity(review)
    assert "C03" in clarity, clarity
    assert "coverage-calibrated filter improves variant calling" in clarity, clarity
    assert "whether each top claim states" not in clarity


def test_clarity_falls_back_without_grounding() -> None:
    # No major gaps / no claims → the generic clarity note is preserved.
    review = render_rubric_review_markdown(
        claim_count=2, gap_count=0, major_gaps=[], novelty_available=True
    )
    clarity = _clarity(review)
    assert "each top claim states its protocol, metric, and boundary" in clarity
