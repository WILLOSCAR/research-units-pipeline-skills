"""Regression: enumerated contributions split into one claim per contribution.

A review found the claims extractor collapsed a manuscript's enumerated
contributions ("Our contributions are threefold: (1) ...; (2) ...; (3) ...")
into a SINGLE claim, so a referee could not assess or evidence each contribution
individually.

`split_sentences` now expands a sentence that enumerates >=2 distinct
contributions (markers "(1)"/"(i)"/"1)") after a contributions/summary lead-in
into one claim per item, prefixing the lead-in so each stands alone. Incidental
in-text parentheticals ("the model (1) shown in Figure 2") and ordinary
sentences are left untouched.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_text import pick_claim_candidates, split_sentences


def test_numbered_contributions_split_into_one_claim_each() -> None:
    sentence = (
        "Our contributions are threefold: (1) we introduce a context-adaptive "
        "entropy model that lowers bitrate by 12%; (2) we design a lightweight "
        "decoder that runs in real time on mobile GPUs; (3) we release a benchmark "
        "of 5,000 annotated images for reproducible evaluation."
    )
    out = split_sentences(sentence)
    assert len(out) == 3, out
    joined = " ".join(out).lower()
    assert "entropy model" in joined
    assert "lightweight decoder" in joined
    assert "benchmark of 5,000" in joined
    # Each item stands alone with the lead-in prefixed.
    assert all(item.lower().startswith("our contributions are threefold:") for item in out), out


def test_roman_numeral_contributions_split() -> None:
    out = split_sentences(
        "We present the following: (i) a novel encoder; (ii) an ablation study; "
        "(iii) a released model."
    )
    assert len(out) == 3, out


def test_incidental_parenthetical_not_split() -> None:
    # A "(1)" that is not an enumerated contribution list must NOT trigger a split.
    for sentence in (
        "The model (1) shown in Figure 2 achieves state of the art on the suite.",
        "We evaluate on three datasets and report mean accuracy across five seeds.",
        "The method improves F1 by 5.1 points over the strongest baseline.",
    ):
        assert split_sentences(sentence) == [sentence], sentence


def test_contributions_appear_as_separate_claims_in_pool() -> None:
    paper = (
        "# NeuralCompress\n\n## 1. Introduction\n\n"
        "Learned image compression has advanced rapidly. Our contributions are "
        "threefold: (1) we introduce a context-adaptive entropy model that lowers "
        "bitrate by 12%; (2) we design a lightweight decoder that runs in real time "
        "on mobile GPUs; (3) we release a benchmark of 5,000 annotated images for "
        "reproducible evaluation.\n"
    )
    claims = [c["sentence"] for c in pick_claim_candidates(paper)]
    # The three contributions are distinct claims, not one collapsed claim.
    assert sum("entropy model" in c for c in claims) >= 1, claims
    assert sum("lightweight decoder" in c for c in claims) >= 1, claims
    assert sum("benchmark of 5,000" in c for c in claims) >= 1, claims
    # No single claim carries all three markers.
    assert not any(
        ("entropy model" in c and "lightweight decoder" in c and "benchmark of 5,000" in c)
        for c in claims
    ), claims
