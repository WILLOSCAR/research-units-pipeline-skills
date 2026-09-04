"""Regression: the tutorial's learning-objective lists read as learner outcomes.

An earlier fix reframed the module-body "Why it matters" objective ("Explain X:")
into a learner outcome ("By the end you should be able to explain X: ..."), but
the top-level "What You Will Learn" list (TUTORIAL.md) and "Learning objectives"
list (TUTORIAL_SPEC.md) still rendered the raw authoring imperative. A read
of a full-builders TUTORIAL.md (real SCHEMAS.md doc) confirmed all six "What You
Will Learn" bullets read as authoring imperatives.

Both render sites now apply `_reader_facing_objective`, so the lists read as
outcomes addressed to the learner.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import (
    render_source_tutorial_spec_markdown,
)

_SPEC = {
    "title": "Schemas Tutorial",
    "goal": "Teach a new engineer the repo's data schemas from the source doc.",
    "audience": ["Readers who want a guided path."],
    "prerequisites": ["Comfort reading technical material."],
    "learning_objectives": [
        "Explain `Schemas`: how it fits into the end-to-end flow.",
        "Compare `Run Projection Status`: the key trade-off it introduces.",
    ],
    "non_goals": ["Not exhaustive."],
    "source_scope": ["`sch` (markdown) - Schemas - used for Schemas."],
    "running_example_policy": {"mode": "none"},
    "delivery_shape": ["Article-first."],
    "core_concepts": [{"id": "c01", "title": "Schemas", "summary": "x"}],
}


def test_spec_learning_objectives_are_reader_outcomes() -> None:
    md = render_source_tutorial_spec_markdown(_SPEC)
    section = md.split("## Learning objectives", 1)[1].split("\n## ", 1)[0]
    # Reframed as outcomes, no bare "Explain X:" / "Compare X:" authoring imperative.
    assert "By the end you should be able to explain `Schemas`" in section, section
    assert "By the end you should be able to compare `Run Projection Status`" in section, section
    for line in section.splitlines():
        s = line.strip()
        if s.startswith("- "):
            assert not s[2:].startswith("Explain `"), s
            assert not s[2:].startswith("Compare `"), s


def test_tutorial_what_you_will_learn_is_reader_outcomes(tmp_path: Path) -> None:
    import json

    from tooling.tutorial_workflows import (
        build_concept_graph,
        build_module_plan,
        build_module_source_coverage,
        build_source_tutorial_spec,
        build_tutorial_context_packs,
        render_source_tutorial_markdown,
    )
    from tooling.common import dump_yaml

    src = (REPO_ROOT / "docs" / "SCHEMAS.md").read_text(encoding="utf-8")
    ws = tmp_path
    (ws / "sources").mkdir(parents=True); (ws / "outline").mkdir(); (ws / "output").mkdir()
    (ws / "GOAL.md").write_text("# Goal\n\nTeach a new engineer the repo's data schemas from the source doc.\n")
    (ws / "sources" / "sch.md").write_text(src)
    (ws / "sources" / "index.jsonl").write_text(json.dumps({"source_id": "sch", "status": "success", "kind": "markdown", "title": "Schemas", "local_path": "sources/sch.md"}) + "\n")
    (ws / "sources" / "provenance.jsonl").write_text(json.dumps({"source_id": "sch", "pointer": "docs/SCHEMAS.md", "local_path": "sources/sch.md", "origin_url_or_path": "docs/SCHEMAS.md"}) + "\n")
    (ws / "DECISIONS.md").write_text("# Decisions log\n\n## Approvals\n- [x] Approve C2\n")
    spec = build_source_tutorial_spec(ws)
    plan = build_module_plan(build_concept_graph(spec), spec_data=spec)
    dump_yaml(ws / "outline" / "module_plan.yml", plan)
    cov = build_module_source_coverage(ws, plan)
    (ws / "outline" / "source_coverage.jsonl").write_text("\n".join(json.dumps(r) for r in cov) + "\n")
    packs = build_tutorial_context_packs(ws, plan, cov)
    (ws / "outline" / "tutorial_context_packs.jsonl").write_text("\n".join(json.dumps(r) for r in packs) + "\n")
    tut = render_source_tutorial_markdown(ws, spec_data=spec)
    section = tut.split("## What You Will Learn", 1)[1].split("## How To Use", 1)[0]
    for line in section.splitlines():
        s = line.strip()
        if s.startswith("- "):
            assert s[2:].startswith("By the end you should be able to"), s
