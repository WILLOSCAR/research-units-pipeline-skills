"""Regression: the referee Summary anchors on the PRIMARY contribution, not a
secondary refinement, when no empirical result claim exists.

A read of a generated REVIEW.md (strong TDN interatomic-potentials
manuscript, real corpus abstract) found the Summary headline was
'To further reduce the number of parameters, we propose path-weight sharing ...'
— a SECONDARY refinement — because after all the manuscript's claims are
conceptual and `_summary_claim_sentence` fell to its last resort: the FIRST
claim in extraction order...' sentence as the real
contribution.

`_summary_claim_sentence` now prefers a primary-contribution sentence ('we
develop/propose/present <X>' that is not a refinement opener) over the
first-listed claim, and never anchors on a refinement sentence ('To further
...', 'Additionally ...', 'We also ...'). Empirical-with-number still wins first.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import _summary_claim_sentence


def test_primary_contribution_beats_first_listed_refinement() -> None:
    claims = [
        {"text": "To further reduce the number of parameters, we propose path-weight sharing across the O(L^3) CG paths.",
         "claim_type": "conceptual", "scope": "abstract"},
        {"text": "To accelerate the computation, we develop tensor decomposition networks (TDNs) in which CG tensor products are replaced by low-rank decompositions.",
         "claim_type": "conceptual", "scope": "abstract"},
    ]
    headline = _summary_claim_sentence(claims)
    assert "we develop tensor decomposition networks" in headline, headline
    assert "path-weight sharing" not in headline, headline


def test_empirical_result_still_wins_over_contribution() -> None:
    claims = [
        {"text": "We develop a new adaptation method for robotics.", "claim_type": "conceptual", "scope": "abstract"},
        {"text": "On four benchmarks it improves task success by 6.4 points over the strongest baseline.",
         "claim_type": "empirical", "scope": "abstract"},
    ]
    headline = _summary_claim_sentence(claims)
    assert "improves task success by 6.4 points" in headline, headline


def test_never_anchors_on_a_refinement_when_avoidable() -> None:
    # No "we develop" contribution sentence; must still avoid the refinement opener.
    claims = [
        {"text": "Additionally, we tune the threshold per benchmark.", "claim_type": "conceptual", "scope": "abstract"},
        {"text": "The framework separates context selection from verification and correction.",
         "claim_type": "conceptual", "scope": "abstract"},
    ]
    headline = _summary_claim_sentence(claims)
    assert headline.startswith("The framework separates"), headline


def test_falls_back_to_any_text_when_all_are_refinements() -> None:
    claims = [{"text": "Additionally, we tune the threshold per benchmark.", "claim_type": "conceptual", "scope": "abstract"}]
    # Only a refinement sentence exists -> the last-resort predicate still returns it.
    assert _summary_claim_sentence(claims) == "Additionally, we tune the threshold per benchmark."
