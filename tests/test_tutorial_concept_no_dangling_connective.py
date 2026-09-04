"""Regression: a source-tutorial concept never ends on a dangling connective.

A read of concepts extracted from docs/HARNESS_ROADMAP.md found the concept
"Harness-V3 State Json As" — a sentence-fragment concept from
"`.harness-v3/state.json` as the sole mutable authority ..." that was clipped to
end on the dangling connective "as".

`_clean_phrase` trims trailing prepositions/fillers, but the short words
"as"/"at"/"by"/"but" were missing from `_PREPOSITIONS` (which feeds the
trailing-trim), so they survived at the end of a concept. They are added, so a
concept ending on one of them is trimmed.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _clean_phrase


def test_trailing_as_is_trimmed() -> None:
    assert _clean_phrase("harness-v3 state json as the sole mutable authority") == "Harness-V3 State Json"
    # bare trailing "as"
    assert not _clean_phrase("state json as").lower().endswith(" as")


def test_trailing_short_prepositions_trimmed() -> None:
    for tail in ("as", "at", "by", "but"):
        out = _clean_phrase(f"run projection status {tail}")
        assert not out.lower().split()[-1] == tail, (tail, out)
        assert "Run Projection Status" in out, (tail, out)


def test_midphrase_as_is_preserved() -> None:
    # "as" mid-phrase is a real content word and must survive.
    assert _clean_phrase("harness as external referee") == "Harness As External Referee"
