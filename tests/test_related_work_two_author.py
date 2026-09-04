"""Regression: related-work prose extraction reads the two-author "X and Y" form.

A review (real ml-interatomic manuscript, P0006) whose
Related Work prose opened "Neural-network potentials were introduced by Behler and
Parrinello." found `_prose_related_works` dropped that foundational citation: the
prose fallback matched only "Surname et al.", so a two-author prior work vanished
from the novelty positioning.

`_prose_related_works` now captures BOTH "Surname et al." and the two-author
"Surname and Surname" form, interleaved in prose order. Both surnames must be
capitalized so lowercase coordinations ("energy and force", "input and output")
are not misread as citations. The "et al." path and the References-list path are
unchanged (locked by test_related_work_prose_extraction.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_text import _prose_related_works, extract_related_works


_TWO_AUTHOR_PROSE = """# Paper

## Related Work
Neural-network potentials were introduced by Behler and Parrinello. Gaussian
Approximation Potentials were developed by Bartok et al. More recently, NequIP was
proposed by Batzner et al. and MACE by Batatia et al. These models must balance
energy and force predictions across input and output channels.

## Method
It works.
"""


def test_two_author_citation_extracted() -> None:
    works = extract_related_works(_TWO_AUTHOR_PROSE)
    joined = " ".join(works)
    # The two-author foundational citation is no longer dropped.
    assert "Behler and Parrinello" in joined, works
    # The "et al." forms still come through, interleaved in prose order.
    for name in ("Bartok et al.", "Batzner et al.", "Batatia et al."):
        assert name in joined, (name, works)
    assert works.index("Behler and Parrinello") == 0, works


def test_lowercase_coordination_not_matched() -> None:
    # "energy and force" / "input and output" are lowercase — not citations.
    neg = (
        "The model trades energy and force accuracy; the input and output "
        "tensors are coupled during message passing."
    )
    assert _prose_related_works(neg) == [], _prose_related_works(neg)


def test_two_author_deduped() -> None:
    section = (
        "Behler and Parrinello proposed the scheme. Later, Behler and Parrinello "
        "refined it."
    )
    works = _prose_related_works(section)
    assert works == ["Behler and Parrinello"], works


def test_et_al_only_prose_unchanged() -> None:
    # No two-author form present — behaviour identical to the baseline.
    section = "Prior work by Yu et al. and Kwon et al. studies batching."
    works = _prose_related_works(section)
    assert "Yu et al." in works and "Kwon et al." in works, works
    # No spurious two-author match spanning the "et al." boundary.
    assert not any(" and " in w for w in works), works
