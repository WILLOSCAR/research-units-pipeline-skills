"""Regression: concept-graph node summaries are source-specific, not templated.

An INDEPENDENT review of the source-tutorial concept_graph found every
heading-concept summary was the generic "Teach `X` as a section of `src`."
template with only the title swapped. The node summary now includes the
concept's first prose sentence from its source section, so it explains what the
concept actually covers.

(The reviewer also flagged all-one-bucket progression and a linear dependency
chain — those require semantic understanding of pedagogical prerequisites and
are LLM-bound, recorded but not deterministically fixed.)
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _heading_context, _collect_phrase_candidates


_DOC = """# Research Loop Architecture

Intro paragraph.

## System Thesis

A polished report is insufficient when a reader cannot tell how it was produced.
More detail follows here.

## Domain Shape

A Goal is a bounded request plus its constraints, and the taxonomy answers it.
"""


def test_heading_context_returns_first_prose_sentence() -> None:
    ctx = _heading_context(_DOC, "System Thesis")
    assert ctx.startswith("A polished report is insufficient"), ctx
    ctx2 = _heading_context(_DOC, "Domain Shape")
    assert ctx2.startswith("A Goal is a bounded request"), ctx2


def test_heading_concept_summaries_are_not_templated() -> None:
    bundle = [{"source_id": "research-loop", "kind": "markdown",
               "title": "Research Loop Architecture", "text": _DOC}]
    cands = _collect_phrase_candidates(bundle)
    heading_cands = [c for c in cands if c.get("kind") == "heading"]
    assert heading_cands, "expected heading candidates"
    for c in heading_cands:
        # No generic "Teach `X` as a section" template when the section has prose.
        assert not c["summary"].startswith("Teach `"), c["summary"]
        assert "covers:" in c["summary"], c["summary"]
    # The System Thesis summary carries its real source content.
    st = next((c for c in heading_cands if c["display"] == "System Thesis"), None)
    assert st is not None
    assert "polished report" in st["summary"], st["summary"]
