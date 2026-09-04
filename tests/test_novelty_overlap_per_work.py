"""Regression: per-work overlap cells in the novelty matrix are row-specific.

A review (real ml-interatomic manuscript, P0006) whose
Related Work prose reads "... Gaussian Approximation Potentials were developed by
Bartok et al. More recent graph-based approaches include NequIP by Batzner et al.
and MACE by Batatia et al." found `related_work_delta` gave Bartok, Batzner, and
Batatia the IDENTICAL overlap cell — a merged two-sentence blob naming all three.
Two causes, both in `related_work_delta`:

1. The abbreviation guard rewrote EVERY "et al." including one that ends a
   sentence ("...Bartok et al. More recent ..."), so Bartok's sentence merged with
   the following Batzner/Batatia sentence. Fixed: only guard a mid-sentence
   "et al." (followed by a lowercase word); a sentence-ending "et al." is a real
   boundary.
2. A single sentence naming several works ("NequIP by Batzner et al. and MACE by
   Batatia et al.") gave every named work the whole sentence. Fixed:
   `_isolate_work_clause` narrows a multi-citation sentence to this work's clause. This is a distinct
earliest owner from the extraction fix (that added the two-author form to the
LIST; this makes each work's overlap CELL row-specific).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_text import _isolate_work_clause, related_work_delta


_PAPER = """# Machine Learning a Universal Harmonic Interatomic Potential

## Abstract
We present a machine-learned universal harmonic interatomic potential.

## Related Work
Neural-network potentials were introduced by Behler and Parrinello. Gaussian
Approximation Potentials were developed by Bartok et al. More recent graph-based
approaches include NequIP by Batzner et al. and MACE by Batatia et al.

## Method
It works.
"""


def _overlap(work: str) -> str:
    return related_work_delta(_PAPER, work)[0]


def test_sentence_ending_et_al_is_a_real_boundary() -> None:
    # Bartok's overlap must NOT bleed into the following NequIP/MACE sentence.
    bartok = _overlap("Bartok et al.")
    assert "bartok" in bartok.lower(), bartok
    assert "nequip" not in bartok.lower(), bartok
    assert "mace" not in bartok.lower(), bartok


def test_multi_citation_sentence_is_split_per_work() -> None:
    batzner = _overlap("Batzner et al.")
    batatia = _overlap("Batatia et al.")
    # Each row's overlap names its own method, not the sibling's.
    assert "nequip" in batzner.lower() and "mace" not in batzner.lower(), batzner
    assert "mace" in batatia.lower() and "nequip" not in batatia.lower(), batatia


def test_all_four_overlaps_are_distinct() -> None:
    works = ["Behler and Parrinello", "Bartok et al.", "Batzner et al.", "Batatia et al."]
    overlaps = [_overlap(w) for w in works]
    assert all(overlaps), overlaps
    assert len(set(overlaps)) == 4, overlaps


def test_single_two_author_sentence_returned_whole() -> None:
    # One citation anchor -> not split by the internal "and".
    s = "Neural-network potentials were introduced by Behler and Parrinello."
    assert _isolate_work_clause(s, "Behler") == s


def test_mid_sentence_et_al_still_guarded() -> None:
    # A mid-sentence "et al." (followed by a lowercase word) must NOT split, so the
    # delta clause is preserved (c-earlier behaviour locked by test_novelty_matrix_deltas).
    paper = (
        "# X\n\n## Related Work\nKumar et al. study calibrated confidence, both of "
        "which our method combines.\n\n## Method\nx\n"
    )
    _, delta = related_work_delta(paper, "Kumar et al.")
    assert "combined" in delta.lower(), delta
