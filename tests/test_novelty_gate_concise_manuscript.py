"""Regression: novelty gate accepts a concise, fully-positioned manuscript.

Driving the full paper-review engine on a REAL ml-interatomic manuscript (P0006)
that cites exactly 4 genuine prior works blocked the entire referee report: the
novelty_positioning gate required >= 5 DISTINCT related works, so a paper that
positioned ALL 8 of its claims against 4 real works (every row complete, 0
unavailable) FAILED and no REVIEW.md was produced.

`_novelty_dimension` now passes when every claim is mapped (covered == claim_ids),
there are no unavailable rows, and there are >= 3 distinct related works. This still
FAILS genuinely thin positioning (1-2 distinct works) and any uncovered/unavailable
claim — preserving the shallow-novelty and unavailable-row true negatives in
test_review_architecture.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_evaluation import _novelty_dimension


def _rows(claim_ids: list[str], works: list[str]) -> list[dict]:
    """One complete novelty row per (claim, work) pair."""
    return [
        {"claim_id": c, "related_work": w, "overlap": "same problem setting",
         "delta": "no explicit delta stated in the manuscript; verify against this work",
         "evidence": "manuscript related-work section"}
        for c in claim_ids for w in works
    ]


def _claims(ids: list[str]) -> list[dict]:
    return [{"claim_id": i} for i in ids]


def test_eight_claims_four_works_passes() -> None:
    # The real P0006 shape: 8 claims positioned against 4 distinct real prior works.
    ids = [f"C{i:02d}" for i in range(1, 9)]
    works = ["Behler and Parrinello", "Bartok et al.", "Batzner et al.", "Batatia et al."]
    dim = _novelty_dimension(_claims(ids), _rows(ids, works))
    assert dim["status"] == "PASS", dim


def test_three_distinct_works_is_the_floor() -> None:
    ids = ["C01", "C02"]
    dim3 = _novelty_dimension(_claims(ids), _rows(ids, ["W1", "W2", "W3"]))
    dim2 = _novelty_dimension(_claims(ids), _rows(ids, ["W1", "W2"]))
    assert dim3["status"] == "PASS", dim3
    assert dim2["status"] != "PASS", dim2  # two works is thin positioning


def test_two_distinct_works_is_shallow_and_fails() -> None:
    # Even with many claims, only 2 distinct prior works is thin positioning.
    ids = [f"C{i:02d}" for i in range(1, 6)]
    dim = _novelty_dimension(_claims(ids), _rows(ids, ["W1", "W2"]))
    assert dim["status"] != "PASS", dim


def test_unavailable_rows_still_fail() -> None:
    ids = ["C01", "C02", "C03"]
    rows = _rows(ids, ["W1", "W2", "W3"])
    rows.append({"claim_id": "C04", "related_work": "related works unavailable",
                 "overlap": "unavailable", "delta": "unavailable", "evidence": "no reference list"})
    dim = _novelty_dimension(_claims(ids + ["C04"]), rows)
    assert dim["status"] != "PASS", dim


def test_uncovered_claim_fails() -> None:
    # A claim with no complete novelty row is not covered -> fail.
    ids = ["C01", "C02", "C03"]
    rows = _rows(["C01", "C02"], ["W1", "W2", "W3"])  # C03 has no row
    dim = _novelty_dimension(_claims(ids), rows)
    assert dim["status"] != "PASS", dim
