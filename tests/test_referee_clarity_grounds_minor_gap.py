"""Regression: the referee Clarity dimension grounds in a claim even with 0 major gaps.

A read of a generated REVIEW.md (real embodied test-time-adaptation abstract,
DART / label-distribution shift) found an asymmetry: Soundness grounded in claim
C01 (the reported 5-18% CIFAR-10C gain) but Clarity fell to the generic template
"whether each top claim states its protocol, metric, and boundary explicitly",
which reads identically for any paper.

Root cause: `render_rubric_review_markdown` derived the Clarity focus claim only
from `major_gaps[0]`; with 0 major gaps (only minor), the focus was empty and
Clarity dropped to the generic branch — while Soundness grounded via its own
minor-gap fallback. The focus now falls back to the first MINOR gap's claim, so
Clarity grounds consistently with Soundness.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_rubric_review_markdown


def _dim(md: str, name: str) -> str:
    return md.split(f"### {name}", 1)[1].split("\n### ", 1)[0]


def test_clarity_grounds_in_minor_gap_claim_when_no_major_gap() -> None:
    md = render_rubric_review_markdown(
        claim_count=2, gap_count=2, major_gaps=[], novelty_available=True,
        claims=[
            {"claim_id": "C01", "text": "Our method exhibits 5-18% gains on CIFAR-10C.", "claim_type": "empirical"},
            {"claim_id": "C02", "text": "We introduce a refinement step.", "claim_type": "conceptual"},
        ],
        minor_gaps=[
            {"claim_id": "C01", "gap": "The concrete result needs a baseline/protocol check.",
             "minimal_fix": "Add a comparison table."},
            {"claim_id": "C02", "gap": "The conceptual claim needs a clearer boundary."},
        ],
        novelty_row={"related_work": "Liang et al.", "overlap": "TTA survey", "delta": "unstated"},
    )
    clarity = _dim(md, "Clarity")
    # Clarity now names the specific claim, not the generic "each top claim" template.
    assert "claim C01" in clarity, clarity
    assert "CIFAR-10C" in clarity, clarity
    assert "whether each top claim" not in clarity, clarity


def test_clarity_generic_only_when_no_gaps_at_all() -> None:
    # With no gaps at all, there is no focus claim, so the generic clarity note is
    # the correct (honest) fallback.
    md = render_rubric_review_markdown(
        claim_count=1, gap_count=0, major_gaps=[], novelty_available=True,
        claims=[{"claim_id": "C01", "text": "A result.", "claim_type": "empirical"}],
        minor_gaps=[],
        novelty_row={"related_work": "X", "overlap": "y", "delta": "z"},
    )
    clarity = _dim(md, "Clarity")
    assert "whether each top claim" in clarity, clarity
