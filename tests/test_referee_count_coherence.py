"""Regression: referee Soundness minor-count matches the Minor Comments list.

An INDEPENDENT whole-report coherence review (the review) flagged a cross-section
inconsistency the per-section checks missed: Soundness said "3 major and 5 minor
evidence issue(s)" while Minor Comments listed only 2. The Soundness count used
the RAW non-major gap total (gap_count - n_major) while Minor Comments renders
DEDUPLICATED distinct minor concerns.

The Soundness count now reports the distinct-minor count that matches the
rendered list, in referee language ("N major concern(s) and M minor concern(s)").
It does NOT expose the raw pre-dedup gap total via a "(from N minor gap(s))"
parenthetical — that is the pipeline's internal extraction bookkeeping (the same
process-residue class the Summary fix removed) — so a reader tallies the
same number in both sections without seeing the machinery.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_rubric_review_markdown

_MAJOR = [{"claim_id": "C04", "gap_id": "G04", "gap": "underspecified empirical claim", "minimal_fix": "state metric"}]
# 5 raw minor gaps, but only 2 DISTINCT concerns (C01/C03/C05 share one).
_MINOR = [
    {"claim_id": "C01", "gap": "needs a baseline/protocol check", "minimal_fix": "add a comparison table"},
    {"claim_id": "C02", "gap": "needs a clearer conceptual boundary", "minimal_fix": "clarify exclusions"},
    {"claim_id": "C03", "gap": "needs a baseline/protocol check", "minimal_fix": "add a comparison table"},
    {"claim_id": "C05", "gap": "needs a baseline/protocol check", "minimal_fix": "add a comparison table"},
    {"claim_id": "C06", "gap": "needs a clearer conceptual boundary", "minimal_fix": "clarify exclusions"},
]


def _section(review: str, header: str, nxt: str) -> str:
    return review.split(header, 1)[1].split(nxt, 1)[0]


def test_soundness_minor_count_matches_minor_comments_list() -> None:
    review = render_rubric_review_markdown(
        claim_count=6, gap_count=6, major_gaps=_MAJOR, novelty_available=True, minor_gaps=_MINOR,
    )
    soundness = _section(review, "### Soundness", "### Clarity")
    minor = _section(review, "### Minor Comments", "### Recommendation")
    listed = [ln for ln in minor.splitlines() if ln.strip().startswith("- ")]
    assert len(listed) == 2, (len(listed), minor)  # 5 raw -> 2 distinct
    # Soundness reports the distinct count (2), consistent with the list.
    nums = re.findall(r"(\d+) minor concern", soundness)
    assert nums and int(nums[0]) == len(listed), (soundness, listed)
    # It does NOT expose the raw pre-dedup gap total (internal bookkeeping).
    assert "minor gap" not in soundness, soundness
    assert "from 5" not in soundness, soundness


def test_soundness_count_plain_when_no_dedup_needed() -> None:
    # When distinct == raw, keep the simple phrasing.
    minor = [
        {"claim_id": "C01", "gap": "needs a baseline check", "minimal_fix": "add table"},
        {"claim_id": "C02", "gap": "needs a boundary", "minimal_fix": "clarify"},
    ]
    review = render_rubric_review_markdown(
        claim_count=3, gap_count=3, major_gaps=_MAJOR, novelty_available=True, minor_gaps=minor,
    )
    soundness = _section(review, "### Soundness", "### Clarity")
    listed = [ln for ln in _section(review, "### Minor Comments", "### Recommendation").splitlines() if ln.strip().startswith("- ")]
    assert len(listed) == 2, listed
    assert "2 minor concern" in soundness, soundness
    assert "minor gap" not in soundness, soundness
