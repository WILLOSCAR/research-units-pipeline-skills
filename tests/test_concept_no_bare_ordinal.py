"""Regression: bare ordinal / list-enumerator words are not tutorial concepts.

A review (a source-tutorial over two SHORT docs where
both genuinely contribute concepts) found a spurious concept node titled "Third"
— a stray inline list marker from a sentence like "avoid `first: ...`, `second:
...`, `third: ...`" that the sentence-fragment fallback surfaced as a concept.

`_looks_like_concept` now rejects a lone ordinal / list-enumerator token
("first", "second", "third", "step", "1st", ...) so such stray markers never
become concept nodes. Real multi-word concepts and genuine noun concepts pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _looks_like_concept


def test_bare_ordinals_rejected() -> None:
    for junk in ("Third", "first", "second", "Step", "point", "1st", "2nd", "3rd", "final"):
        assert _looks_like_concept(junk) is False, junk


def test_real_concepts_pass() -> None:
    for good in ("Core Rule", "Expected Sections", "distribution shift", "binding stability"):
        assert _looks_like_concept(good) is True, good
    # An ordinal used as a modifier inside a real phrase still passes.
    assert _looks_like_concept("first-order logic") is True
