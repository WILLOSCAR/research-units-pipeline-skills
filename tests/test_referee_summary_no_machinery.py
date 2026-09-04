"""Regression: the referee-report Summary exposes no claim-extraction machinery.

A read of a generated REVIEW.md (real clinical-summarization abstract
via the paper-review engine) found the Summary line ended with
"(8 extracted claim(s) reviewed via explicit claim and gap extraction)" — the
manuscript's authors and editor should read a referee statement, not the
pipeline's internal machinery ("extracted claim(s)", "claim and gap extraction").

`render_rubric_review_markdown` now states the same useful signal (how many
central claims the review examined) in referee-facing language, with correct
singular/plural agreement, in both the headline and no-headline branches.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_rubric_review_markdown

_BANNED = (
    "extracted claim", "claim and gap extraction", "gap extraction", "extraction)",
    "this review assesses", "central claim",
)


def _summary(md: str) -> str:
    return md.split("### Summary", 1)[1].split("### Novelty", 1)[0]


def test_summary_has_no_extraction_machinery_with_headline() -> None:
    md = render_rubric_review_markdown(
        claim_count=8, gap_count=0, major_gaps=[], novelty_available=True,
        claims=[{"claim_id": "C1", "text": "We propose a new pipeline for factual alignment.", "claim_type": "empirical"}],
        novelty_row={"related_work": "Weng et al.", "overlap": "negation", "delta": "unstated"},
    )
    summary = _summary(md)
    for phrase in _BANNED:
        assert phrase not in summary, (phrase, summary)
    # The Summary states the paper's own headline claim, nothing about the review process.
    assert "We propose a new pipeline for factual alignment." in summary, summary


def test_summary_has_no_extraction_machinery_no_headline() -> None:
    md = render_rubric_review_markdown(
        claim_count=3, gap_count=0, major_gaps=[], novelty_available=False,
        claims=[{"claim_id": "C1", "text": ""}],
    )
    summary = _summary(md)
    for phrase in _BANNED:
        assert phrase not in summary, (phrase, summary)
    # The no-headline fallback still names the manuscript's contribution count,
    # framed around the paper (not the extraction pipeline).
    assert "main contribution" in summary, summary


def test_summary_states_headline_claim_only() -> None:
    md = render_rubric_review_markdown(
        claim_count=1, gap_count=0, major_gaps=[], novelty_available=True,
        claims=[{"claim_id": "C1", "text": "We report a 5 point gain.", "claim_type": "empirical"}],
        novelty_row={"related_work": "X", "overlap": "y", "delta": "z"},
    )
    summary = _summary(md).strip()
    # Exactly the headline claim line — no trailing parenthetical meta-commentary.
    assert summary == '- The paper\'s headline claim is: "We report a 5 point gain."', repr(summary)
