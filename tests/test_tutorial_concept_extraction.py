"""Regression: source-tutorial concepts come from real headings, not clause fragments.

Before this fix, the concept extractor mined title-cased word-runs out of prose
sentences. On real documentation whose sentences were not governed by an action
verb, the greedy `if "," in sentence` branch sliced whole sentences — subject +
verb clauses included — into "concepts": module titles like "Correctable While
The Goal", "Human Decisions Change", "Unit Of Trust Is The", and "Not The
Answer". A learner was handed grammatically-incoherent clause fragments as the
things to learn.

The extractor now (a) prefers the source's own markdown section headings (the
author's concept decomposition) as concept candidates, and (b) rejects
sentence-derived fragments that read like a clause rather than a concept name
(leading connective/relative pronoun, an embedded finite/relational verb, or a
bare adverb).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import (
    _collect_phrase_candidates,
    _looks_like_concept,
    _source_headings,
)


_REAL_DOC = """# Research Loop Architecture

Research Harness keeps a bounded body of research work inspectable, replayable,
and correctable while the Goal, Evidence, and human Decisions change. The unit
of trust is the Loop, not the answer.

## 1. System Thesis

We do not claim a result is scientifically true; we prove it was produced
correctly, reproducibly, and without letting the model grade itself.

## 2. Domain Shape

The harness may use skills, a Run DAG, repair cycles, and recovery privately.

## 3. The Harness As Referee

The external referee recomputes scorecards rather than trusting a declared pass.
"""


def _bundle():
    return [
        {
            "source_id": "research-loop",
            "kind": "markdown",
            "title": "Research Loop Architecture",
            "text": _REAL_DOC,
        }
    ]


def test_headings_are_extracted_numbering_stripped() -> None:
    headings = _source_headings(_REAL_DOC)
    assert "System Thesis" in headings
    assert "Domain Shape" in headings
    assert "The Harness As Referee" in headings
    # The numbering prefix is stripped.
    assert not any(h[0].isdigit() for h in headings)


def test_clause_fragments_are_rejected_as_concepts() -> None:
    # Clause fragments the old extractor turned into concepts.
    assert not _looks_like_concept("correctable while the Goal")
    assert not _looks_like_concept("human Decisions change")
    assert not _looks_like_concept("the unit of trust is the Loop")
    assert not _looks_like_concept("not the answer")
    assert not _looks_like_concept("which supersedes the earlier framing")
    assert not _looks_like_concept("without letting the model grade itself")
    assert not _looks_like_concept("reproducibly")
    # Genuine noun-led concept phrases still pass.
    assert _looks_like_concept("dataset schema")
    assert _looks_like_concept("training configuration")
    assert _looks_like_concept("replayable")


def test_concept_candidates_prefer_headings_over_clause_fragments() -> None:
    candidates = _collect_phrase_candidates(_bundle())
    displays = {c["display"] for c in candidates}
    kinds = {c["display"]: c["kind"] for c in candidates}
    # The author's headings are present as heading candidates.
    for heading in ("System Thesis", "Domain Shape", "Harness As Referee"):
        assert heading in displays, sorted(displays)
        assert kinds[heading] == "heading"
    # The clause fragments are gone entirely.
    for junk in (
        "Correctable While The Goal",
        "Human Decisions Change",
        "Unit Of Trust Is The",
        "Not The Answer",
        "Which Supersedes The Earlier Framing",
        "Without Letting The Model Grade",
    ):
        assert junk not in displays, junk
