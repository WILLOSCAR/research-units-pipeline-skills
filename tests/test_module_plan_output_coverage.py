"""Regression: module-plan outputs cover every concept and end coherently.

A whole-module-plan read (real PIPELINE_TAXONOMY.md via the real
spec->graph->module-plan builders) found two defects in `build_module_plan`
outputs:

1. A multi-concept module produced a concrete-artifact output ONLY for its FIRST
   concept (`concept_titles[0]`), so a 2-concept module left its second concept
   unassessed even though both are module objectives.
2. EVERY module's linkage output said "...can be reused by the next module",
   including the FINAL module — where there is no next module, reading as a
   template artifact.

`build_module_plan` now emits one concrete-artifact output per concept in the
module, and gives the final module a synthesis output instead of the "next module"
linkage.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import build_module_plan


def _graph(n: int) -> dict:
    nodes = [
        {"id": f"c{i:02d}", "title": f"Concept {i}", "source_ids": ["s1"],
         "prerequisites": [f"c{i-1:02d}"] if i > 1 else []}
        for i in range(1, n + 1)
    ]
    edges = [{"from": f"c{i-1:02d}", "to": f"c{i:02d}"} for i in range(2, n + 1)]
    return {"nodes": nodes, "edges": edges}


def _plan(n: int) -> dict:
    return build_module_plan(_graph(n), spec_data={"learning_objectives": []})


def test_every_concept_in_a_module_has_a_concrete_output() -> None:
    plan = _plan(6)
    for module in plan["modules"]:
        concrete = [o for o in module["outputs"] if "concrete in the tutorial flow" in o]
        # One concrete-artifact output per concept in the module.
        assert len(concrete) == len(module["concepts"]), (module["id"], module["outputs"])


def test_second_concept_is_named_in_outputs() -> None:
    # A 2-concept module must name BOTH concepts across its concrete outputs.
    plan = _plan(6)
    multi = [m for m in plan["modules"] if len(m["concepts"]) >= 2]
    assert multi, plan
    m = multi[0]
    concrete = " ".join(o for o in m["outputs"] if "concrete in the tutorial flow" in o)
    # Both concept titles appear (the fix: not only the first).
    assert m["title"].split(" and ")[0] in concrete, m["outputs"]
    assert m["title"].split(" and ")[-1] in concrete, m["outputs"]


def test_final_module_has_synthesis_not_next_module_output() -> None:
    plan = _plan(6)
    modules = plan["modules"]
    final = modules[-1]
    joined = " ".join(final["outputs"])
    assert "reused by the next module" not in joined, final["outputs"]
    assert "Synthesize" in joined and "overall goal" in joined, final["outputs"]


def test_non_final_modules_keep_next_module_linkage() -> None:
    plan = _plan(6)
    modules = plan["modules"]
    assert len(modules) >= 2, plan
    for m in modules[:-1]:
        assert any("reused by the next module" in o for o in m["outputs"]), m["outputs"]


def test_single_module_plan_gets_synthesis() -> None:
    # A one-module plan is its own final module -> synthesis, no "next module".
    plan = _plan(1)
    assert len(plan["modules"]) == 1, plan
    joined = " ".join(plan["modules"][0]["outputs"])
    assert "reused by the next module" not in joined, joined
    assert "Synthesize" in joined, joined
