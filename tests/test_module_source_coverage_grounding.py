"""Regression: module-source-coverage attributes only concept-contributing sources.

An INDEPENDENT review of a MULTI-source source-tutorial run found every
module attributed to BOTH sources (`arch` + `schemas`), even though all module
concepts came only from `arch`. `build_module_source_coverage` re-scored the
full source bundle by lexical match against the generic module text and took the
top-2 with score>0 — over-attributing a source that contributed no concept.

It now uses the module's concept-derived `source_ids` (authoritative) as the
grounding, falling back to lexical match only when a module has no concept
sources recorded.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def _make_workspace(tmp_path: Path) -> Path:
    ws = tmp_path
    (ws / "sources" / "normalized").mkdir(parents=True, exist_ok=True)
    # Two real sources; index + provenance so load_source_bundle sees both.
    (ws / "sources" / "normalized" / "arch.md").write_text("# Arch\n\nArchitecture prose.\n", encoding="utf-8")
    (ws / "sources" / "normalized" / "schemas.md").write_text("# Schemas\n\nSchema prose.\n", encoding="utf-8")
    import json
    (ws / "sources" / "index.jsonl").write_text(
        json.dumps({"source_id": "arch", "kind": "markdown", "status": "success", "title": "Arch",
                    "local_path": "sources/normalized/arch.md"}) + "\n" +
        json.dumps({"source_id": "schemas", "kind": "markdown", "status": "success", "title": "Schemas",
                    "local_path": "sources/normalized/schemas.md"}) + "\n",
        encoding="utf-8",
    )
    (ws / "sources" / "provenance.jsonl").write_text(
        json.dumps({"source_id": "arch", "pointer": "sources/normalized/arch.md", "local_path": "sources/normalized/arch.md"}) + "\n" +
        json.dumps({"source_id": "schemas", "pointer": "sources/normalized/schemas.md", "local_path": "sources/normalized/schemas.md"}) + "\n",
        encoding="utf-8",
    )
    return ws


def test_coverage_uses_concept_source_ids_not_lexical_overmatch(tmp_path: Path) -> None:
    from tooling.tutorial_workflows import build_module_source_coverage

    ws = _make_workspace(tmp_path)
    # A module whose concepts came ONLY from `arch`.
    plan = {
        "modules": [
            {
                "id": "M01",
                "title": "Architecture and Thesis",
                "objectives": ["Explain how `Architecture` fits into the flow."],
                "source_ids": ["arch"],  # concept-derived grounding
            }
        ]
    }
    records = build_module_source_coverage(ws, plan)
    module_records = [r for r in records if r.get("module_id")]
    assert len(module_records) == 1
    rec = module_records[0]
    # Only `arch` — `schemas` (no concept contribution) must NOT be attributed.
    assert rec["source_ids"] == ["arch"], rec["source_ids"]
    assert all("schemas" not in p for p in rec["matched_pointers"]), rec["matched_pointers"]
    # `schemas` was ingested but used by no module: the corpus reconciliation
    # record must surface it as an explicit gap rather than dropping it silently.
    recon = [r for r in records if r.get("record_type") == "corpus_reconciliation"]
    assert len(recon) == 1, records
    assert recon[0]["unused_source_ids"] == ["schemas"], recon[0]
    assert recon[0]["gaps"], recon[0]


def test_coverage_falls_back_to_lexical_when_no_concept_sources(tmp_path: Path) -> None:
    from tooling.tutorial_workflows import build_module_source_coverage

    ws = _make_workspace(tmp_path)
    plan = {"modules": [{"id": "M01", "title": "Arch topic", "objectives": ["Architecture prose."], "source_ids": []}]}
    records = build_module_source_coverage(ws, plan)
    # No concept sources -> lexical fallback still attributes something + flags a gap.
    assert records[0]["source_ids"], records[0]
    assert records[0]["gaps"], records[0]
