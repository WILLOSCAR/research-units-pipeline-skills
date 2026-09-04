"""Regression: brief annotations don't end on a dangling word/ellipsis.

The review also flagged that a "What to read first"
annotation was truncated mid-phrase — "... across representative binary and
ternary amorphous..." — because the paper's contribution sentence (29 words) was
one word over the 28-word cap and got cut before "alloys systems".

_brief_summary now (a) keeps a single sentence whole when it only slightly
exceeds the cap (ends on its natural terminator, no ellipsis), and (b) when it
must hard-truncate, drops a trailing connective/preposition so the text does not
end on a dangling function word before the "...".
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import _brief_summary


_P0004_ABSTRACT = (
    "While traditional trial-and-error methods for designing amorphous alloys are costly, "
    "machine learning approaches based solely on composition lack structural information. "
    "In this work, we develop a general-purpose machine learning interatomic potential for "
    "amorphous alloys by using a dataset comprising 20400 configurations across representative "
    "binary and ternary amorphous alloys systems."
)


def test_slightly_over_cap_sentence_kept_whole() -> None:
    # The 29-word contribution sentence (1 over the 28 cap) is kept whole and ends
    # on its natural period, not cut before "alloys systems" with an ellipsis.
    summary = _brief_summary(_P0004_ABSTRACT, max_words=28)
    assert summary.rstrip().endswith("alloys systems."), summary
    assert not summary.rstrip().endswith("amorphous..."), summary


def test_hard_truncation_drops_trailing_function_word() -> None:
    # A genuinely long single run truncates, but never ends on a dangling
    # connective/preposition before the ellipsis.
    text = (
        "In this work the authors evaluate the approach and adapt it to a new domain by "
        "using a large dataset across many benchmark tasks and settings and additionally "
        "compare against several strong published baselines and further"
    )
    summary = _brief_summary(text, max_words=18)
    assert summary.endswith("..."), summary
    last = summary[:-3].rstrip().split()[-1].lower()
    assert last not in {"and", "or", "of", "for", "to", "with", "the", "a", "an", "by", "across", "using", "via"}, summary


def test_long_multi_sentence_still_truncates() -> None:
    # A very long single sentence (well over 1.25x cap) still hard-truncates.
    text = "The authors " + "improve throughput and reduce latency and cut memory " * 8
    summary = _brief_summary(text, max_words=10)
    assert summary.endswith("..."), summary
    assert len(summary.split()) <= 12, summary
