"""Regression: idea-brainstorm glance-table cells never end mid-phrase.

A read of a generated idea memo (clinical-summarization corpus) found six
"at a glance" table cells truncated mid-phrase — every fast-kill
criterion ended on a dangling object-requiring preposition ("...already isolates
clinical sensitivity against") and two payoff cells ended on a bare slash-scope
("...for large /"), so a researcher could not read the kill criteria or the
promised contribution from the triage table. All six cells were affected.

`_glance_cell` now drops trailing object-requiring prepositions (against, into,
than, ...) and orphaned punctuation tokens (a bare "/" left when a "large /
adapted" scope is cut after the slash), so every cell ends on a content word.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.ideation import _glance_cell

# Object-requiring prepositions / conjunctions a cell must not dangle on.
_BAD_TAIL = {
    "against", "into", "than", "between", "among", "across", "toward", "towards",
    "onto", "to", "of", "for", "with", "by", "from", "because", "while", "and",
    "or", "but", "isolating", "holding", "varying", "a", "an", "the",
}


def _last_word(cell: str) -> str:
    return cell.split()[-1].lower().strip(",;:-/") if cell.split() else ""


def test_glance_cell_does_not_dangle_on_object_preposition() -> None:
    cell = _glance_cell(
        "Kill quickly if the strongest prior work already isolates clinical "
        "sensitivity against nearby design choices and evaluation framing."
    )
    assert not cell.endswith("against"), cell
    assert _last_word(cell) not in _BAD_TAIL, cell
    assert "isolates clinical sensitivity" in cell, cell


def test_glance_cell_strips_trailing_slash_scope() -> None:
    cell = _glance_cell(
        "Could turn clinidigest sensitivity into a cleaner explanatory variable "
        "for large / clinidigest case study summarization"
    )
    assert not cell.rstrip().endswith("/"), cell
    assert _last_word(cell) not in _BAD_TAIL, cell


def test_glance_cell_does_not_dangle_on_because_isolating() -> None:
    cell = _glance_cell(
        "Ranks behind What clinical sensitivity is really doing in Clinical Text "
        "because isolating the shape of the confound is what makes it decisive"
    )
    assert not cell.endswith("because isolating"), cell
    assert _last_word(cell) not in _BAD_TAIL, cell


def test_glance_cell_keeps_short_complete_phrase() -> None:
    # A short, already-complete cell is returned essentially unchanged.
    assert _glance_cell("Leads on time-to-clarity") == "Leads on time-to-clarity"
    assert _glance_cell("") == ""


def test_glance_cells_end_on_content_across_samples() -> None:
    samples = [
        "Kill quickly if the strongest prior work already isolates adapted sensitivity against nearby design choices",
        "Could turn adapted sensitivity into a cleaner explanatory variable for large / adapted large language model work",
        "Leads because it offers the fastest path to a decisive mechanism clarification result in clinical text summarization",
        "Kill if the first controlled probe leaves both the metric and the qualitative failure taxonomy essentially unchanged",
    ]
    for s in samples:
        cell = _glance_cell(s)
        assert cell, s
        assert _last_word(cell) not in _BAD_TAIL, cell
        assert not cell.rstrip().endswith(("/", "-")), cell
