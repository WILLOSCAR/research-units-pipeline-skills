"""Regression: novelty overlap cell does not restate the work's own citation.

A read of a generated referee report found the Novelty note rendered
"A cited prior work to position against is Thong et al. (Thong et al.); ...".
The overlap cell (printed in parentheses next to the work name) had collapsed to
the work's own citation, because the Related-Work sentence
"Thong et al. (2022) developed a ... potential." was split at "et al." — the
sentence-boundary guard only protected "et al." before a lowercase word, not
before a parenthesized citation year — leaving a bare "Thong et al." fragment
whose overlap fallback restated the name.

`related_work_delta` now (a) does not split "et al. (YYYY)" citations and
(b) strips a leading self-citation from the overlap fallback, so the overlap
describes what the work DOES.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_text import _strip_leading_citation, extract_related_works, related_work_delta


_RW = (
    "## Related Work\n\n"
    "Thong et al. (2022) developed a machine-learning interatomic potential for molecular dynamics of complex alloys. "
    "Bizot et al. (2025) studied crystal nucleation in eutectic Al-Si alloys using machine-learned potentials. "
    "Lee et al. (2024) proposed a universal harmonic interatomic potential. "
    "Loew et al. (2024) benchmarked universal machine-learning interatomic potentials for production simulations.\n"
)


def test_overlap_does_not_restate_the_citation() -> None:
    works = extract_related_works(_RW)
    assert works[:1] == ["Thong et al."], works
    overlap, _delta = related_work_delta(_RW, "Thong et al.")
    # The overlap describes what the work does, not its citation.
    assert overlap, "overlap should be a content description, not empty"
    assert not overlap.lower().startswith("thong"), overlap
    assert "et al." not in overlap.lower(), overlap
    assert "developed a machine-learning interatomic potential" in overlap, overlap
    # No trailing sentence terminator leaking into the parenthetical.
    assert not overlap.endswith("."), overlap


def test_et_al_year_citation_is_not_split() -> None:
    # Each of the four works must produce a distinct, name-free overlap — proof
    # the "et al. (YYYY)" citations were not fragmented into bare-name rows.
    overlaps = {w: related_work_delta(_RW, w)[0] for w in extract_related_works(_RW)}
    for work, overlap in overlaps.items():
        assert overlap, f"{work}: empty overlap"
        assert "et al." not in overlap.lower(), f"{work}: {overlap!r} restates a citation"
    assert overlaps["Bizot et al."].startswith("studied crystal nucleation"), overlaps
    assert overlaps["Loew et al."].startswith("benchmarked"), overlaps


def test_strip_leading_citation_edges() -> None:
    assert _strip_leading_citation("Thong et al. (2022) developed X", "Thong") == "developed X"
    assert _strip_leading_citation("Smith et al. study Y", "Smith") == "study Y"
    # Two-author citation.
    assert _strip_leading_citation("Behler and Parrinello introduced Z", "Behler") == "introduced Z"
    # No citation prefix: returned unchanged.
    assert _strip_leading_citation("no citation prefix here", "Nobody") == "no citation prefix here"
    # Stripping to empty falls back to the original clause.
    assert _strip_leading_citation("Thong et al. (2022)", "Thong") == "Thong et al. (2022)"
