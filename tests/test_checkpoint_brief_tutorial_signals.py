"""Regression: the source-tutorial C2 checkpoint brief carries substantive signal.

A read of the C2 checkpoint brief (the `## C2 review` block of
DECISIONS.md a maintainer approves before tutorial prose is written) found it
reported only file presence and byte counts ("non-empty-lines=165, chars=7575")
for the tutorial spec, concept graph, module plan, and source coverage — so a
maintainer could not review scope or structure without opening all four files.

`_summarize_artifact` now dispatches source-tutorial artifacts to dedicated
summarizers that surface: the spec scope title + enumerated objectives + concept
names; the concept graph's node/edge counts + prerequisite chain + isolated
nodes; the module titles + concept counts; and the coverage's per-module
sources, gaps, and ingested-but-unused sources.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from tooling.checkpoint_brief import (
    _summarize_concept_graph,
    _summarize_module_plan,
    _summarize_source_coverage,
    _summarize_tutorial_spec,
)


def test_tutorial_spec_summary_surfaces_scope_objectives_concepts(tmp_path: Path) -> None:
    spec_md = (
        "# Pipeline Taxonomy Tutorial\n\n"
        "## Learning objectives\n"
        "- Explain `Recipes`: what they are.\n"
        "- Explain `Loops`: how they run.\n\n"
        "## Core concepts\n"
        "- `c01-recipes` Recipes - the catalog of recipe families.\n"
        "- `c02-loops` Loops - the verify/repair/re-run cycle.\n"
    )
    p = tmp_path / "TUTORIAL_SPEC.md"
    p.write_text(spec_md, encoding="utf-8")
    out = _summarize_tutorial_spec(p, "output/TUTORIAL_SPEC.md")
    assert 'scope="Pipeline Taxonomy Tutorial"' in out, out
    assert "learning-objectives=2" in out and "core-concepts=2" in out, out
    # objectives enumerated, concepts named
    assert "objective: Explain `Recipes`: what they are." in out, out
    assert "concept: Recipes" in out and "concept: Loops" in out, out
    # not a byte count
    assert "chars=" not in out, out


def test_concept_graph_summary_enumerates_prerequisite_chain(tmp_path: Path) -> None:
    import yaml

    graph = {
        "nodes": [
            {"id": "c01", "title": "Recipes"},
            {"id": "c02", "title": "Loops"},
            {"id": "c03", "title": "Evidence"},
        ],
        "edges": [{"from": "c01", "to": "c02"}, {"from": "c02", "to": "c03"}],
    }
    p = tmp_path / "concept_graph.yml"
    p.write_text(yaml.safe_dump(graph), encoding="utf-8")
    out = _summarize_concept_graph(p, "outline/concept_graph.yml")
    assert "concepts=3, prerequisite-edges=2" in out, out
    assert "Recipes -> Loops" in out and "Loops -> Evidence" in out, out


def test_concept_graph_summary_flags_isolated_node(tmp_path: Path) -> None:
    import yaml

    graph = {
        "nodes": [{"id": "c01", "title": "Recipes"}, {"id": "c02", "title": "Orphan"}],
        "edges": [],
    }
    p = tmp_path / "concept_graph.yml"
    p.write_text(yaml.safe_dump(graph), encoding="utf-8")
    out = _summarize_concept_graph(p, "outline/concept_graph.yml")
    assert "isolated (no prerequisite link)=2" in out, out
    assert "Recipes" in out and "Orphan" in out, out


def test_module_plan_summary_lists_titles_and_concept_counts(tmp_path: Path) -> None:
    import yaml

    plan = {
        "modules": [
            {"id": "M01", "title": "Recipes and Loops", "concepts": ["a", "b"]},
            {"id": "M02", "title": "Evidence", "concepts": ["c"]},
        ]
    }
    p = tmp_path / "module_plan.yml"
    p.write_text(yaml.safe_dump(plan), encoding="utf-8")
    out = _summarize_module_plan(p, "outline/module_plan.yml")
    assert "modules=2" in out, out
    assert "M01: Recipes and Loops (concepts=2)" in out, out
    assert "M02: Evidence (concepts=1)" in out, out


def test_source_coverage_summary_surfaces_gaps_and_unused(tmp_path: Path) -> None:
    records = [
        {"module_id": "M01", "source_ids": ["tax"], "gaps": []},
        {"module_id": "M02", "source_ids": ["tax"], "gaps": ["a module gap"]},
        {"record_type": "corpus_reconciliation", "ingested_source_ids": ["tax", "extra"],
         "attributed_source_ids": ["tax"], "unused_source_ids": ["extra"], "gaps": ["unused: extra"]},
    ]
    p = tmp_path / "source_coverage.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    out = _summarize_source_coverage(p, "outline/source_coverage.jsonl")
    assert "modules-covered=2, modules-with-gaps=1" in out, out
    assert "M02: sources=[tax] [GAP]" in out, out
    assert "ingested-but-unused sources=extra" in out, out


def test_source_coverage_summary_flags_missing_reconciliation(tmp_path: Path) -> None:
    records = [{"module_id": "M01", "source_ids": ["tax"], "gaps": []}]
    p = tmp_path / "source_coverage.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    out = _summarize_source_coverage(p, "outline/source_coverage.jsonl")
    assert "corpus reconciliation: MISSING" in out, out
