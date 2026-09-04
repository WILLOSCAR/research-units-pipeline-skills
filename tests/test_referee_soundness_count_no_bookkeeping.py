"""Regression: the referee Soundness count exposes no gap-extraction bookkeeping.

Following the Summary fix and the Clarity fix, a per-dimension read
flagged the Soundness count clause "0 major concern(s) and 2 distinct minor
concern(s) (from 8 minor gap(s))" — the "(from N minor gap(s))" parenthetical
exposes the pipeline's internal pre-dedup extraction total ("gap" is the tool's
term), automated bookkeeping a manuscript's authors/editor do not need.

`render_rubric_review_markdown` now states a clean referee count ("N major
concern(s) and M minor concern(s)") using the distinct count the reader will tally
in Minor Comments, with no raw-gap parenthetical and no "distinct" qualifier.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_rubric_review_markdown


def _soundness(md: str) -> str:
    return md.split("### Soundness", 1)[1].split("### Clarity", 1)[0]


def test_soundness_count_has_no_gap_bookkeeping_when_dedup_occurs() -> None:
    # gap_count=8 but only 2 distinct minor concerns -> old code showed
    # "(from 7 minor gap(s))"; the new count is clean.
    md = render_rubric_review_markdown(
        claim_count=8, gap_count=8, novelty_available=True,
        major_gaps=[{"claim_id": "C09", "gap": "a major concern", "minimal_fix": "fix"}],
        minor_gaps=[
            {"claim_id": "C01", "gap": "needs a baseline check", "minimal_fix": "add table"},
            {"claim_id": "C02", "gap": "needs a boundary", "minimal_fix": "clarify"},
        ],
    )
    s = _soundness(md)
    assert "minor gap" not in s, s
    assert "distinct minor" not in s, s
    assert "from 7" not in s, s
    assert "2 minor concerns" in s, s


def test_soundness_count_singular_plural_agreement() -> None:
    md1 = render_rubric_review_markdown(
        claim_count=2, gap_count=1, novelty_available=True, major_gaps=[],
        minor_gaps=[{"claim_id": "C01", "gap": "needs a baseline check", "minimal_fix": "add table"}],
    )
    s1 = _soundness(md1)
    assert "0 major concerns and 1 minor concern" in s1, s1
    assert "1 minor concerns" not in s1, s1  # correct singular

    md2 = render_rubric_review_markdown(
        claim_count=3, gap_count=1, novelty_available=True,
        major_gaps=[{"claim_id": "C09", "gap": "a major concern", "minimal_fix": "fix"}],
        minor_gaps=[{"claim_id": "C01", "gap": "needs a baseline check", "minimal_fix": "add table"}],
    )
    s2 = _soundness(md2)
    assert "1 major concern and 1 minor concern" in s2, s2
