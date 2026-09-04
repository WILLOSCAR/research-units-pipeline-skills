"""Regression: the manuscript-stated delta over a TWO-AUTHOR work is captured.

A review found that when a manuscript explicitly states
"the delta over Behler and Parrinello is a harmonic restriction that yields
calibrated uncertainty", `related_work_delta` returned an EMPTY delta cell for the
two-author work "Behler and Parrinello". Cause: the delta/overlap regexes were
built from `_work_surname` (first token only), so they searched "delta over Behler
is" and missed the author's actual "delta over Behler and Parrinello is".

`_work_author_regex` now matches the first surname with an OPTIONAL " and <Second>"
tail for a two-author work, so both the full author phrase and the first-author
abbreviation are captured. First-author "et al." works are unaffected. Completes the
two-author positioning chain: (list) -> (overlap cell) -> (delta cell).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_text import _work_author_regex, related_work_delta


_PAPER = """# Universal Harmonic Interatomic Potential

## Abstract
We present a universal harmonic interatomic potential.

## Related Work
Neural-network potentials were introduced by Behler and Parrinello. Our approach
differs: the delta over Behler and Parrinello is a harmonic restriction that yields
calibrated uncertainty, and the delta over Bartok is universality across the
periodic table.

## Method
It works.
"""


def test_two_author_explicit_delta_captured() -> None:
    _, delta = related_work_delta(_PAPER, "Behler and Parrinello")
    assert "harmonic restriction" in delta.lower(), delta
    assert "calibrated uncertainty" in delta.lower(), delta


def test_first_author_delta_still_captured() -> None:
    # The single-author "delta over Bartok is ..." path is unchanged.
    _, delta = related_work_delta(_PAPER, "Bartok et al.")
    assert "universality" in delta.lower(), delta


def test_author_regex_shapes() -> None:
    # Two-author work: first surname with an optional " and <second>" tail.
    two = _work_author_regex("Behler and Parrinello")
    assert "Behler" in two and "Parrinello" in two and "?" in two, two
    # First-author work: just the surname, no optional tail.
    one = _work_author_regex("Bartok et al.")
    assert "Bartok" in one and " and " not in one, one


def test_two_author_delta_matches_first_author_abbreviation() -> None:
    # If the manuscript abbreviates a two-author work to its first author in the
    # delta clause, that is still captured (the " and <second>" tail is optional).
    paper = (
        "# X\n\n## Related Work\nBehler and Parrinello proposed the scheme; the delta "
        "over Behler is an added harmonic constraint.\n\n## Method\nx\n"
    )
    _, delta = related_work_delta(paper, "Behler and Parrinello")
    assert "harmonic constraint" in delta.lower(), delta
