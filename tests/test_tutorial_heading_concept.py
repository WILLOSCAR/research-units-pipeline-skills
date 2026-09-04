"""Regression: heading-derived concept titles are clean noun-phrases.

A review on a REAL heading-rich repo doc (docs/PROJECT_LANGUAGE.md)
found heading-derived concept titles that were garbled or verb-clausal because
the heading path used the plain _clean_phrase:
  - "The Loop, the graph, and the Skills" -> "Loop The Graph" (comma-list mangled,
    "Skills" dropped);
  - "How the harness acts as referee" -> "Harness Acts As Referee" (verb clause);
  - "Why external and why bounded" -> "External And Why Bounded" (question-word
    fragment).

_heading_concept now (a) keeps a comma/"and" list heading's enumerated items,
and (b) strips a leading question/discourse word then reduces a residual
subject-verb clause to its subject noun-phrase. Plain noun-phrase headings are
unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _collect_phrase_candidates, _heading_concept


def test_comma_list_heading_keeps_items() -> None:
    out = _heading_concept("The Loop, the graph, and the Skills")
    assert "Loop" in out and "Graph" in out and "Skills" in out, out
    # Not the garbled "Loop The Graph".
    assert out != "Loop The Graph", out


def test_question_heading_reduced_to_subject_noun_phrase() -> None:
    out = _heading_concept("How the harness acts as referee")
    assert out.lower().startswith("harness"), out
    assert "acts as referee" not in out.lower(), out


def test_why_heading_drops_question_word() -> None:
    out = _heading_concept("Why external and why bounded")
    assert not out.lower().startswith("why"), out
    assert "why" not in out.lower().split(), out


def test_plain_noun_phrase_headings_unchanged() -> None:
    for h in ("Language Authority", "Three Quality Layers", "Repository Boundary", "Naming Rules"):
        assert _heading_concept(h) == h, h


def test_heading_concepts_have_no_verb_clause_titles() -> None:
    doc = (
        "# Design System\n\n"
        "## Language Authority\nThe glossary is authority.\n\n"
        "## The Loop, the graph, and the Skills\nThey compose.\n\n"
        "## How the harness acts as referee\nIt recomputes.\n\n"
        "## Why external and why bounded\nScope is limited.\n\n"
        "## Repository Boundary\nThe repo owns artifacts.\n"
    )
    bundle = [{"source_id": "ds", "kind": "markdown", "title": "Design System", "text": doc}]
    heading_titles = [c["display"] for c in _collect_phrase_candidates(bundle) if c["kind"] == "heading"]
    for junk in ("Loop The Graph", "Harness Acts As Referee", "External And Why Bounded"):
        assert junk not in heading_titles, (junk, heading_titles)
    assert "Language Authority" in heading_titles, heading_titles
    assert "Repository Boundary" in heading_titles, heading_titles
