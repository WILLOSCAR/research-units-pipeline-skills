"""Regression: source-tutorial context-pack snippets are self-contained + distinct.

A read of a real-corpus context pack (pipeline-taxonomy doc via the
real builders) found module source snippets that opened mid-argument — M01 "So
this catalog separates two things ..." (a dangling discourse connective) and M02
"Its exporter target is ..." (an unresolved pronoun) — so a learner reading a
snippet alone could not resolve the opener.

`_best_snippet` now (a) strips a leading discourse connective ("So this ..." ->
"This ...") — the remainder stays a contiguous substring of the source, so
grounding still holds — and (b) applies a relevance penalty to a sentence opening
with a bare pronoun so an equally-relevant self-contained sentence wins. The
snippet-selection query drops the generic `running_example_steps` boilerplate
(whose identical wording across modules had collapsed distinct snippets onto one
shared sentence), keeping per-module snippets distinct.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import (
    _best_snippet,
    _snippet_is_self_contained,
    _strip_leading_connective,
)

_CONNECTIVES = ("so", "thus", "therefore", "hence", "and", "but", "however", "moreover")


def test_strip_leading_connective_removes_discourse_marker() -> None:
    assert _strip_leading_connective("So this catalog separates two things") == "This catalog separates two things"
    assert _strip_leading_connective("Therefore, the loop converges") == "The loop converges"
    assert _strip_leading_connective("However the run fails") == "The run fails"
    # A pronoun opener is NOT stripped (it carries meaning).
    assert _strip_leading_connective("Its exporter target is X") == "Its exporter target is X"
    # A plain sentence is unchanged.
    assert _strip_leading_connective("A Recipe runs a verify loop") == "A Recipe runs a verify loop"


def test_pronoun_opener_is_not_self_contained() -> None:
    assert _snippet_is_self_contained("A Recipe runs a verify loop") is True
    assert _snippet_is_self_contained("Its exporter target is a LaTeX adapter") is False
    assert _snippet_is_self_contained("They inherit the survey lifecycle") is False


def test_best_snippet_prefers_self_contained_over_pronoun_opener() -> None:
    text = (
        "# Doc\n\n"
        "Its exporter target is a LaTeX adapter over the survey recipe.\n\n"
        "The exporter migration converts a survey recipe into a LaTeX adapter cleanly.\n"
    )
    query = "exporter migration survey recipe LaTeX adapter"
    snippet = _best_snippet(text, query)
    # The self-contained sentence (equal-ish relevance) must win over the pronoun opener.
    assert not snippet.lower().startswith("its "), snippet
    assert _snippet_is_self_contained(snippet), snippet


def test_best_snippet_strips_leading_connective_from_top_sentence() -> None:
    text = (
        "# Doc\n\n"
        "So this catalog separates two recipe families and records their maturity.\n"
    )
    query = "catalog recipe families maturity"
    snippet = _best_snippet(text, query)
    assert not re.match(r"(?i)^so\b", snippet), snippet
    assert snippet.startswith("This catalog separates"), snippet
    # Grounding: the stripped snippet is still a contiguous substring (casefold).
    norm_src = re.sub(r"\s+", " ", text).strip().casefold()
    assert re.sub(r"\s+", " ", snippet).strip().casefold() in norm_src, snippet
