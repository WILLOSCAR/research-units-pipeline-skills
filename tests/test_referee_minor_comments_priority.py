"""Regression: Minor Comments are ordered by execution priority and do not repeat
the load-bearing Soundness/Clarity concern verbatim.

A read of a generated paper review (AgenticSum clinical manuscript) found two
defects in '### Minor Comments':
  1. The FIRST minor comment (the load-bearing claim C01) restated the exact
     concern already given as the Soundness load-bearing gap AND the Clarity
     sharpest risk — a third verbatim copy in the action list.
  2. Minor Comments were ordered by raw manuscript claim-id (C01, C04, C06), not
     by execution priority.

Fix in tooling/review_render.py: order minor gaps by `_minor_gap_priority`
(concrete-result-check > dataset-provenance > qualitative > conceptual-boundary),
and render the load-bearing focus claim (when no major gap and other minors exist)
as a back-reference to Soundness/Clarity instead of a verbatim third copy — while
keeping the Soundness<->Minor count coherent.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import _minor_gap_priority, render_rubric_review_markdown


def _claims() -> list[dict]:
    return [{"claim_id": f"C0{i}", "text": f"Claim {i} text about the method.", "claim_type": "conceptual"} for i in (1, 4, 6)]


def _minor() -> list[dict]:
    return [
        {"claim_id": "C01", "gap": "The conceptual claim needs a clearer boundary and stronger relation to prior work.", "minimal_fix": "Clarify what the claim excludes."},
        {"claim_id": "C04", "gap": "The claim reports a qualitative finding but states no concrete evidence.", "minimal_fix": "State the per-result numbers."},
        {"claim_id": "C06", "gap": "The methods/dataset claim needs provenance and coverage.", "minimal_fix": "State the dataset provenance, exact size, coverage, and evaluation protocol."},
    ]


def _minor_section(review: str) -> str:
    return review.split("### Minor Comments", 1)[1].split("### Recommendation", 1)[0]


def test_priority_key_ranks_actionable_first() -> None:
    assert _minor_gap_priority({"gap": "reports a concrete result but still needs an explicit baseline/protocol check"}) == 0
    assert _minor_gap_priority({"gap": "The methods/dataset claim needs provenance and coverage: ... evaluation protocol"}) == 1
    assert _minor_gap_priority({"gap": "The claim reports a qualitative finding but states no concrete evidence"}) == 2
    assert _minor_gap_priority({"gap": "The conceptual claim needs a clearer boundary and stronger relation to prior work"}) == 3


def test_minor_comments_ordered_by_priority_not_claim_id() -> None:
    review = render_rubric_review_markdown(
        claim_count=3, gap_count=3, major_gaps=[], novelty_available=True,
        claims=_claims(), novelty_row={"related_work": "Smith et al.", "claim_id": "C01"}, minor_gaps=_minor(),
    )
    minor = _minor_section(review)
    pos = {cid: minor.find(f"Claim {cid}:") for cid in ("C01", "C04", "C06")}
    # Priority order: C06 (provenance) < C04 (qualitative) < C01 (conceptual, last).
    assert pos["C06"] < pos["C04"] < pos["C01"], minor
    # NOT raw claim-id order.
    assert not (pos["C01"] < pos["C04"] < pos["C06"]), minor


def test_load_bearing_claim_is_backreference_not_verbatim_repeat() -> None:
    review = render_rubric_review_markdown(
        claim_count=3, gap_count=3, major_gaps=[], novelty_available=True,
        claims=_claims(), novelty_row={"related_work": "Smith et al.", "claim_id": "C01"}, minor_gaps=_minor(),
    )
    minor = _minor_section(review)
    # C01 (the Soundness/Clarity focus) is a back-reference, not a 3rd verbatim copy.
    assert "addressed under Soundness and Clarity above" in minor, minor
    # The full C01 concern text appears once (in the back-ref line it is NOT repeated).
    assert minor.count("The conceptual claim needs a clearer boundary") == 0, minor
    # Count coherence with Soundness (3 minor concerns) is preserved: 3 bullets.
    assert minor.count("\n- ") == 3, minor


def test_single_minor_focus_still_shows_its_concern() -> None:
    # If the focus claim is the ONLY minor, show its concern (no circular back-ref).
    review = render_rubric_review_markdown(
        claim_count=1, gap_count=1, major_gaps=[], novelty_available=True,
        claims=[{"claim_id": "C01", "text": "A measured result.", "claim_type": "conceptual"}],
        novelty_row={"related_work": "Smith et al.", "claim_id": "C01"},
        minor_gaps=[{"claim_id": "C01", "gap": "The conceptual claim needs a clearer boundary."}],
    )
    minor = _minor_section(review)
    assert "The conceptual claim needs a clearer boundary" in minor, minor
    assert "addressed under Soundness and Clarity above" not in minor, minor


def test_focus_backreference_skipped_when_a_major_gap_leads() -> None:
    # With a major gap, the focus is a MAJOR concern; minors are different claims
    # and must NOT be turned into back-references.
    review = render_rubric_review_markdown(
        claim_count=3, gap_count=3, novelty_available=True, claims=_claims(),
        novelty_row={"related_work": "Smith et al.", "claim_id": "C01"},
        major_gaps=[{"claim_id": "C01", "gap": "The empirical claim is underspecified.", "minimal_fix": "State the task, metric, baseline, and result."}],
        minor_gaps=[
            {"claim_id": "C04", "gap": "The claim reports a qualitative finding but states no concrete evidence."},
            {"claim_id": "C06", "gap": "The methods/dataset claim needs provenance and coverage."},
        ],
    )
    minor = _minor_section(review)
    assert "addressed under Soundness and Clarity above" not in minor, minor
    assert "Claim C04:" in minor and "Claim C06:" in minor, minor
