"""Regression: heading-rich sources suppress the noisy sentence-fragment fallback.

A review run on a REAL
heading-rich repository doc (docs/PROJECT_LANGUAGE.md, 12 `##` sections) found
the sentence-fragment fallback piled ~80 noisy clause fragments on top of the
clean heading concepts — verb clauses split from compound sentences ("Does Not
Repeat That Glossary", "It Maps Those Terms", "Names The Private Implementation
Concepts"), bare connectives ("Then"), and stray fragments.

Two fixes at the earliest owner (tooling/tutorial_workflows.py):
1. _fragment_concept rejects a fragment that LEADS with a 3rd-person-singular
   finite verb ("names ...", "does not repeat ...") — a subjectless predicate
   clause (only the unambiguous "-s" form, so a base-form adjective/verb like
   "approximate" that heads a real noun phrase is preserved).
2. _collect_phrase_candidates suppresses the sentence-fragment fallback once a
   source already yields >=4 heading concepts (the author's own decomposition);
   heading-poor sources (prose notes / FAQ / procedures) still use the fallback.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _collect_phrase_candidates, _fragment_concept


def test_leading_finite_verb_clause_rejected() -> None:
    # Subjectless predicate clauses (from splitting a compound sentence on ";"/
    # " and ") are not concepts.
    assert _fragment_concept("names the private implementation concepts precisely") is None
    assert _fragment_concept("does not repeat that glossary") is None
    assert _fragment_concept("maps those terms to the current implementation") is None


def test_leading_base_form_adjective_noun_phrase_preserved() -> None:
    # "approximate" is a base-form verb in the verb lexicon but here heads a real
    # noun phrase; it must NOT be rejected as a leading finite verb.
    assert (
        _fragment_concept("Approximate nearest neighbor indexes trade recall for speed")
        == "Approximate nearest neighbor indexes"
    )


_HEADING_RICH = """# Design System

## Language Authority
The glossary is the single source of truth; it maps those terms and names the private concepts precisely.

## State Authority
Only the engine advances state.

## Naming Rules
Every product term has one implementation term.

## Repository Boundary
The repo owns its own artifacts.

## Quality Layers
Three layers: execution, contract, research.
"""


def test_heading_rich_source_suppresses_sentence_fallback() -> None:
    bundle = [{"source_id": "ds", "kind": "markdown", "title": "Design System", "text": _HEADING_RICH}]
    kinds = {}
    for c in _collect_phrase_candidates(bundle):
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    # >=4 headings -> the noisy sentence fallback is suppressed.
    assert kinds.get("heading", 0) >= 4, kinds
    assert kinds.get("sentence", 0) == 0, kinds
    # None of the verb-clause sentence fragments leak in.
    displays = {c["display"] for c in _collect_phrase_candidates(bundle)}
    for junk in ("It Maps Those Terms", "Names The Private Concepts", "Names The Private Concepts Precisely"):
        assert junk not in displays, junk


def test_heading_poor_source_still_uses_sentence_fallback() -> None:
    # A no-heading prose source must still mine sentence concepts.
    prose = (
        "# RAG Notes\n\n"
        "A retriever selects candidate passages from a corpus. "
        "Chunking splits documents into passages before indexing.\n"
    )
    bundle = [{"source_id": "rag", "kind": "markdown", "title": "RAG Notes", "text": prose}]
    displays = {c["display"] for c in _collect_phrase_candidates(bundle)}
    assert "Retriever" in displays, sorted(displays)
    assert "Chunking" in displays, sorted(displays)
