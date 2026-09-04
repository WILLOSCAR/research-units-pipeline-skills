"""Regression: source-tutorial spec emits one learning objective per core concept.

The C2 checkpoint brief surfaced that `build_source_tutorial_spec` capped
`learning_objectives = concepts[:5]`, so a 6-concept spec (the `_select_concepts`
maximum) left the 6th concept with NO stated objective in TUTORIAL_SPEC.md — a
scope under-coverage a maintainer reviewing "What You Will Learn" would notice.

The cap is removed: every core concept now gets its own objective, and a 6th
clause keeps all six phrasings distinct.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from tooling.tutorial_workflows import build_source_tutorial_spec


def _spec_on(doc_relpath: str, goal: str) -> dict:
    src = (REPO_ROOT / doc_relpath).read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / "sources").mkdir(parents=True)
        (ws / "GOAL.md").write_text(goal, encoding="utf-8")
        (ws / "sources" / "s.md").write_text(src, encoding="utf-8")
        (ws / "sources" / "index.jsonl").write_text(
            json.dumps({"source_id": "s", "status": "success", "kind": "markdown",
                        "title": "Source", "local_path": "sources/s.md"}) + "\n", encoding="utf-8")
        (ws / "sources" / "provenance.jsonl").write_text(
            json.dumps({"source_id": "s", "pointer": doc_relpath, "local_path": "sources/s.md",
                        "origin_url_or_path": doc_relpath}) + "\n", encoding="utf-8")
        return build_source_tutorial_spec(ws)


def test_one_objective_per_concept_on_six_concept_doc() -> None:
    spec = _spec_on("docs/PIPELINE_TAXONOMY.md", "# Goal\n\nTeach the pipeline taxonomy from the source doc.\n")
    concepts = spec["core_concepts"]
    objectives = spec["learning_objectives"]
    assert len(concepts) >= 6, len(concepts)  # this doc yields the 6-concept case
    assert len(objectives) == len(concepts), (len(objectives), len(concepts))
    # Every concept title appears in some objective (the 6th is no longer orphaned).
    for concept in concepts:
        title = concept["title"]
        assert any(f"`{title}`" in obj for obj in objectives), (title, objectives)
    # Objectives are distinct (no repeated template across the set).
    assert len(set(objectives)) == len(objectives), objectives


def test_objective_count_tracks_concept_count_on_small_doc() -> None:
    # A smaller doc with fewer concepts still gets exactly one objective each.
    spec = _spec_on("docs/PROJECT_LANGUAGE.md", "# Goal\n\nTeach the project's shared vocabulary from the doc.\n")
    assert len(spec["learning_objectives"]) == len(spec["core_concepts"]), spec["learning_objectives"]
