"""Regression: the tutorial Prerequisites line joins concepts grammatically.

A read of a generated TUTORIAL.md flagged the
Prerequisites line "Basic familiarity with the terms behind current recipes,
exporter migration is enough; the rest is taught in sequence." as grammatically
broken — the two concept titles were comma-joined, reading as a comma-splice
mid-sentence rather than a two-item list. With no concepts the line also emitted
the broken "behind  is enough" (empty focus, double space).

`_prerequisite_from_concepts` now joins two titles with "and" and falls back to a
generic prerequisite when there are no concepts.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _prerequisite_from_concepts


def test_two_concepts_joined_with_and() -> None:
    line = _prerequisite_from_concepts([{"title": "Current Recipes"}, {"title": "Exporter Migration"}])
    assert "current recipes and exporter migration" in line, line
    # No bare comma-splice between the two concept titles.
    assert "current recipes, exporter migration" not in line, line


def test_single_concept_unchanged() -> None:
    line = _prerequisite_from_concepts([{"title": "Schemas"}])
    assert "the terms behind schemas is enough" in line, line
    assert " and " not in line.split("is enough")[0], line  # no spurious conjunction


def test_no_concepts_falls_back_cleanly() -> None:
    line = _prerequisite_from_concepts([])
    # No broken "behind  is enough" with an empty focus / double space.
    assert "behind  is enough" not in line, line
    assert "  " not in line, line
    assert line == "No specific background is assumed; each concept is taught in sequence.", line


def test_more_than_two_concepts_uses_first_two() -> None:
    line = _prerequisite_from_concepts([{"title": "Alpha"}, {"title": "Beta"}, {"title": "Gamma"}])
    assert "behind alpha and beta is enough" in line, line
    # Only the first two concepts are named; the third is not listed.
    assert "gamma" not in line.lower(), line
