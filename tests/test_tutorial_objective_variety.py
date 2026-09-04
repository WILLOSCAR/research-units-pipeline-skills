"""Regression: source-tutorial learning objectives are varied, not one template.

An L2 whole-SPEC coherence review, run on a real repo doc (docs/AUTO_RESEARCH_DESIGN_SYSTEM.md),
found every learning objective was the same template repeated verbatim —
"Explain how `X` fits into the end-to-end tutorial flow." — for all five
concepts, so the objectives did not state a distinct learner performance per
concept.

_objective_from_concept now varies the action clause by the concept's position
(cycling _OBJECTIVE_CLAUSES), so consecutive objectives differ even when the
concepts share a bucket/verb.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _OBJECTIVE_CLAUSES, _objective_from_concept


def test_objectives_vary_by_position() -> None:
    concepts = [
        {"title": "System Thesis", "bucket": "foundation"},
        {"title": "Domain Shape", "bucket": "foundation"},
        {"title": "Loop", "bucket": "foundation"},
        {"title": "Harness As Referee", "bucket": "foundation"},
    ]
    objectives = [_objective_from_concept(c, i) for i, c in enumerate(concepts)]
    # Each concept's title appears in its objective.
    for c, o in zip(concepts, objectives):
        assert c["title"] in o, (c, o)
    # The action clauses are distinct (not one repeated template) across the set.
    clauses = [o.split(":", 1)[1].strip() for o in objectives]
    assert len(set(clauses)) == len(clauses), clauses
    # And they are not the old fixed "fits into the end-to-end tutorial flow" for all.
    assert not all("fits into the end-to-end tutorial flow" in o for o in objectives), objectives


def test_bucket_verb_still_applied() -> None:
    # The bucket->verb mapping is preserved (an evaluate-bucket concept -> "Compare").
    obj = _objective_from_concept({"title": "Held-out Eval", "bucket": "evaluate"}, 0)
    assert obj.startswith("Compare "), obj


def test_clause_cycle_wraps() -> None:
    # The clause list has one entry per possible core concept (<=6), so a concept
    # at index N uses clause[N % len]; wrapping past the list stays title-anchored
    # and never crashes.
    n = len(_OBJECTIVE_CLAUSES)
    obj = _objective_from_concept({"title": "Wrapped Concept", "bucket": "foundation"}, n)
    assert "Wrapped Concept" in obj
    assert obj.split(":", 1)[1].strip() == _OBJECTIVE_CLAUSES[0]
    # Each in-range index maps to its own distinct clause (one objective per concept).
    in_range = [
        _objective_from_concept({"title": f"C{i}", "bucket": "foundation"}, i).split(":", 1)[1].strip()
        for i in range(n)
    ]
    assert len(set(in_range)) == n, in_range
