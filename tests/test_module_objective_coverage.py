"""Regression: every module concept has a learning objective.

An independent review of the source-tutorial module_plan found a module
("Three Pillars and Product Interface") whose objectives covered only the first
concept — the second concept (beyond the spec's top-N learning_objectives) had
no objective, because `_module_objectives` only mapped resolvable objective_refs
and silently dropped concepts whose ref fell outside the objectives list.

`_module_objectives` now synthesizes an objective from a concept's title when
its referenced objective does not resolve, so every module concept is covered.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _module_objectives, build_module_plan


def test_module_objectives_cover_concept_beyond_spec_objectives() -> None:
    # Two concepts; only the first has a resolvable objective_ref (the spec kept
    # only the top-1 objective). The second must still get an objective.
    chunk = [
        {"id": "c05-three-pillars", "title": "Three Pillars", "objective_refs": [0]},
        {"id": "c06-product-interface", "title": "Product Interface", "objective_refs": [5]},
    ]
    objectives = ["Explain how `Three Pillars` fits into the end-to-end tutorial flow."]
    out = _module_objectives(chunk, objectives)
    joined = " ".join(out).lower()
    assert "three pillars" in joined, out
    assert "product interface" in joined, out  # was previously dropped


def test_build_module_plan_every_concept_has_objective() -> None:
    graph = {
        "nodes": [
            {"id": "c01-a", "title": "Alpha", "objective_refs": [0]},
            {"id": "c02-b", "title": "Beta", "objective_refs": [1]},
            {"id": "c03-c", "title": "Gamma", "objective_refs": [2]},
            {"id": "c04-d", "title": "Delta", "objective_refs": [3]},
            {"id": "c05-e", "title": "Epsilon", "objective_refs": [4]},
            {"id": "c06-f", "title": "Zeta", "objective_refs": [5]},  # beyond top-5
        ],
        "edges": [],
    }
    spec = {"learning_objectives": [f"Explain how `{t}` fits into the end-to-end tutorial flow."
                                    for t in ("Alpha", "Beta", "Gamma", "Delta", "Epsilon")]}
    plan = build_module_plan(graph, spec_data=spec)
    title_by_id = {n["id"]: n["title"] for n in graph["nodes"]}
    for module in plan["modules"]:
        objs = " ".join(module.get("objectives", [])).lower()
        for cid in module.get("concepts", []):
            title = title_by_id.get(cid, "").lower()
            if title:
                assert title in objs, (module["id"], cid, title, module.get("objectives"))
