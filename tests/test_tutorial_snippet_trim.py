"""Regression: tutorial source snippets do not dangle mid-sentence on a conjunction.

The unblock + read surfaced this L2 defect: a Module "Key idea" snippet
ended "...produced correctly, reproducibly, and" — `_trim_snippet` capped at 240
chars at a word boundary but left the phrase dangling on a conjunction, so the
central teaching sentence read as unfinished.

`_trim_snippet` now prefers to end at the last sentence terminator within the cap,
and otherwise drops a trailing dangling conjunction/connector word so a truncated
snippet ends on content, not on "and"/"to"/"the". The snippet stays a contiguous
prefix substring of the raw provenance (the grounding check) — we only ever DROP
trailing tokens, never insert an ellipsis.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _trim_snippet

_DANGLING_TAIL = re.compile(
    r"(?i)\b(?:and|or|but|nor|yet|so|because|which|while|that|with|to|of|the|a|an|for|in|on|at|by|from|into|than|as)$"
)


def test_snippet_does_not_end_on_dangling_conjunction() -> None:
    long = (
        "A Recipe does not promise a scientifically true result — it runs a verify, "
        "repair, re-run Loop and, when the Run converges, keeps the checkable Evidence "
        "and proof pack that show the Artifact was produced correctly, reproducibly, and "
        "without the model grading itself."
    )
    trimmed = _trim_snippet(long)
    assert not _DANGLING_TAIL.search(trimmed.rstrip(" ,;:-")), trimmed
    assert not trimmed.rstrip().endswith("and"), trimmed


def test_trimmed_snippet_is_contiguous_prefix_substring() -> None:
    long = (
        "Underneath, every Run is a DAG of content-addressed steps; the Loop repairs "
        "locally and within bounds; the harness — the external referee — decides "
        "whether each pass counts and keeps the retained scorecards for later audit."
    )
    trimmed = _trim_snippet(long)

    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()

    assert norm(trimmed) in norm(long), (trimmed, long)


def test_short_snippet_unchanged() -> None:
    s = "A concise, complete key idea."
    assert _trim_snippet(s) == s


def test_snippet_prefers_sentence_terminator_within_cap() -> None:
    # A snippet whose first sentence terminator sits past the halfway cap (120) but
    # within the 240-char cap ends at that terminator, dropping the overflow sentence.
    text = (
        "This opening clause is a deliberately long and fully self-contained sentence "
        "that comfortably passes the halfway point of the character cap so it becomes "
        "the eligible cut point for the trimmer. A second sentence then continues on "
        "well beyond the two hundred and forty character cap with additional filler text."
    )
    assert len(text) > 240
    trimmed = _trim_snippet(text)
    assert trimmed.endswith("."), trimmed
    assert "A second sentence then continues" not in trimmed, trimmed
