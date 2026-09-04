"""Regression: the referee Summary names the paper's actual headline claim.

`render_rubric_review_markdown` received only counts, so the Summary could only
say "The paper claims N main contribution(s) and is reviewed through explicit
claim and gap extraction" — a process description that tells a referee nothing
about the manuscript. Surfaced by a blind read of a real paper-review REVIEW.md.

The renderer now accepts the extracted claims and anchors the Summary in the
paper's strongest real claim (empirical, front-matter, carrying a number). This
test pins that a manuscript-specific claim appears in the Summary, and that the
old behaviour is preserved when no claims are supplied.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_rubric_review_markdown

_CLAIMS = [
    {
        "text": "On the TCGA benchmark dataset it improves F1 by 5.1 points (accuracy 0.914) over the strongest ensemble baseline.",
        "claim_type": "empirical",
        "scope": "Abstract scope",
    },
    {
        "text": "The coverage-calibrated filter improves variant calling.",
        "claim_type": "empirical",
        "scope": "6. Conclusion scope",
    },
]


def test_summary_names_the_headline_claim() -> None:
    review = render_rubric_review_markdown(
        claim_count=len(_CLAIMS),
        gap_count=0,
        major_gaps=[],
        novelty_available=True,
        claims=_CLAIMS,
    )
    summary = review.split("### Summary", 1)[1].split("###", 1)[0]
    # The front-matter empirical claim with a number is chosen and quoted.
    assert "TCGA benchmark dataset" in summary and "F1 by 5.1 points" in summary, summary
    # It is NOT the generic process boilerplate.
    assert "reviewed through explicit claim and gap extraction" not in summary


def test_summary_falls_back_without_claims() -> None:
    review = render_rubric_review_markdown(
        claim_count=3, gap_count=0, major_gaps=[], novelty_available=True
    )
    summary = review.split("### Summary", 1)[1].split("###", 1)[0]
    # Backward-compatible generic summary when no claims are provided.
    assert "3 main contribution(s)" in summary
