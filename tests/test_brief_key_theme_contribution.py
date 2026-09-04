"""Regression: research-brief Key themes state contributions, not field background.

A review on a REAL brief built from cached
ml-interatomic-potentials abstracts found a "Key themes" bullet that was generic
field background ("Ferroelectric perovskites have been ubiquitously applied in
piezoelectric devices for decades ...") rather than the paper's contribution.

Root cause: _brief_summary scored sentences for a narrow set of contribution
verbs (propose/present/introduce/...), so an abstract whose contribution used
another verb ("we CONSTRUCT a machine-learning interatomic potential of KNbO3")
tied at 0 with the background opener, and the earlier (background) sentence won
the tie-break.

_brief_summary now scores a broader contribution-verb set (construct/build/
design/train/derive/achieve/...) and PENALIZES a field-background opener ("X has
been applied for decades", "in the era of ...").
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import _brief_summary


_P0002_ABSTRACT = (
    "Ferroelectric perovskites have been ubiquitously applied in piezoelectric devices for "
    "decades, among which, eco-friendly lead-free (K,Na)NbO3-based materials have been recently "
    "demonstrated to be an excellent candidate for sustainable development. Molecular dynamics is "
    "a versatile theoretical calculation approach for the investigation of the dynamical properties "
    "of ferroelectric perovskites. However, molecular dynamics simulation of ferroelectric "
    "perovskites has been limited to simple systems, since the conventional construction of "
    "interatomic potential is rather difficult and inefficient. In the present study, we construct "
    "a machine-learning interatomic potential of KNbO3 by using a deep neural network model."
)


def test_summary_prefers_contribution_over_background() -> None:
    summary = _brief_summary(_P0002_ABSTRACT, max_words=45)
    # The contribution sentence (construct an MLIP of KNbO3) is chosen, not the
    # ferroelectric-perovskite field background.
    assert "machine-learning interatomic potential of KNbO3" in summary, summary
    assert "ubiquitously applied" not in summary, summary
    # "we construct" is normalized to "the authors construct".
    assert "the authors construct" in summary.lower(), summary


def test_broadened_contribution_verbs() -> None:
    for verb, obj in [
        ("construct", "a spectral graph model"),
        ("build", "a benchmark suite"),
        ("design", "a lightweight decoder"),
        ("train", "a diffusion policy"),
        ("derive", "a closed-form bound"),
    ]:
        abstract = (
            "This area has been widely studied for decades. "
            f"In this work, we {verb} {obj} for the task."
        )
        summary = _brief_summary(abstract, max_words=40)
        assert obj.split()[-1] in summary, (verb, summary)
        assert "widely studied for decades" not in summary, (verb, summary)


def test_pure_background_paragraph_returns_something() -> None:
    # An all-background abstract still yields a non-empty orientation string
    # (graceful — the penalty never zeroes out every sentence to empty).
    abstract = "Deep learning has been widely applied in vision. It plays a central role in NLP."
    assert _brief_summary(abstract, max_words=30) != ""
