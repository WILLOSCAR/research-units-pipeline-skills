"""Regression: module-source-coverage surfaces ingested-but-unused sources.

A read of a MULTI-source source-tutorial coverage audit (three real
repo docs: schemas / taxonomy / language) found every module attributed only to
`schemas`, while `taxonomy` and `language` were successfully ingested yet
appeared in NO module record. Because the audit emitted only per-module rows,
all `gaps` arrays read `[]` and a C2 checkpoint reviewer would over-read coverage
as complete when two of three ingested docs contributed nothing. The absent
sources need a source-level reconciliation against the declared inventory.

`build_module_source_coverage` now appends one `corpus_reconciliation` record
enumerating ingested / attributed / unused sources with an explicit gap when any
ingested source is unused, and `check_module_source_coverage` requires that
record to be present and honest.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def _scaffold(ws: Path, source_ids: list[str]) -> dict:
    (ws / "sources" / "normalized").mkdir(parents=True, exist_ok=True)
    (ws / "outline").mkdir(parents=True, exist_ok=True)
    idx: list[str] = []
    prov: list[str] = []
    for sid in source_ids:
        (ws / "sources" / "normalized" / f"{sid}.md").write_text(
            f"# {sid.title()}\n\n{sid} prose for the tutorial.\n", encoding="utf-8"
        )
        idx.append(json.dumps({
            "source_id": sid, "kind": "markdown", "status": "success", "title": sid.title(),
            "local_path": f"sources/normalized/{sid}.md",
        }))
        prov.append(json.dumps({
            "source_id": sid, "pointer": f"sources/normalized/{sid}.md",
            "local_path": f"sources/normalized/{sid}.md", "origin_url_or_path": f"sources/normalized/{sid}.md",
        }))
    (ws / "sources" / "index.jsonl").write_text("\n".join(idx) + "\n", encoding="utf-8")
    (ws / "sources" / "provenance.jsonl").write_text("\n".join(prov) + "\n", encoding="utf-8")
    # A single module grounded only in the first source; the rest are unused.
    plan = {"modules": [{"id": "M01", "title": "Topic", "objectives": ["Explain the topic."], "source_ids": [source_ids[0]]}]}
    from tooling.common import dump_yaml
    dump_yaml(ws / "outline" / "module_plan.yml", plan)
    return plan


def _write(ws: Path, records: list[dict]) -> None:
    (ws / "outline" / "source_coverage.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )


def test_reconciliation_flags_ingested_but_unused_source(tmp_path: Path) -> None:
    from tooling.tutorial_workflows import build_module_source_coverage

    plan = _scaffold(tmp_path, ["schemas", "taxonomy", "language"])
    records = build_module_source_coverage(tmp_path, plan)
    recon = [r for r in records if r.get("record_type") == "corpus_reconciliation"]
    assert len(recon) == 1, records
    assert recon[0]["ingested_source_ids"] == ["schemas", "taxonomy", "language"]
    assert recon[0]["attributed_source_ids"] == ["schemas"]
    assert recon[0]["unused_source_ids"] == ["taxonomy", "language"]
    assert recon[0]["gaps"], "unused sources must produce an explicit gap"
    joined = " ".join(recon[0]["gaps"])
    assert "taxonomy" in joined and "language" in joined, joined


def test_gate_clean_when_reconciliation_honest(tmp_path: Path) -> None:
    from tooling.quality_checks.source_tutorial import check_module_source_coverage
    from tooling.tutorial_workflows import build_module_source_coverage

    plan = _scaffold(tmp_path, ["schemas", "taxonomy", "language"])
    _write(tmp_path, build_module_source_coverage(tmp_path, plan))
    issues = check_module_source_coverage(tmp_path, ["outline/source_coverage.jsonl"])
    assert issues == [], [i.code for i in issues]


def test_gate_flags_missing_reconciliation(tmp_path: Path) -> None:
    from tooling.quality_checks.source_tutorial import check_module_source_coverage
    from tooling.tutorial_workflows import build_module_source_coverage

    plan = _scaffold(tmp_path, ["schemas", "taxonomy"])
    records = [r for r in build_module_source_coverage(tmp_path, plan) if r.get("module_id")]
    _write(tmp_path, records)
    codes = {i.code for i in check_module_source_coverage(tmp_path, ["outline/source_coverage.jsonl"])}
    assert "source_coverage_missing_reconciliation" in codes, codes


def test_gate_flags_dishonest_reconciliation(tmp_path: Path) -> None:
    from tooling.quality_checks.source_tutorial import check_module_source_coverage
    from tooling.tutorial_workflows import build_module_source_coverage

    plan = _scaffold(tmp_path, ["schemas", "taxonomy"])
    records = build_module_source_coverage(tmp_path, plan)
    for rec in records:
        if rec.get("record_type") == "corpus_reconciliation":
            rec["unused_source_ids"] = []
            rec["gaps"] = []
    _write(tmp_path, records)
    codes = {i.code for i in check_module_source_coverage(tmp_path, ["outline/source_coverage.jsonl"])}
    assert "source_coverage_reconciliation_unused_mismatch" in codes, codes
    assert "source_coverage_unused_source_not_flagged" in codes, codes


def test_single_source_reconciliation_has_no_gap(tmp_path: Path) -> None:
    from tooling.quality_checks.source_tutorial import check_module_source_coverage
    from tooling.tutorial_workflows import build_module_source_coverage

    plan = _scaffold(tmp_path, ["schemas"])
    records = build_module_source_coverage(tmp_path, plan)
    _write(tmp_path, records)
    recon = [r for r in records if r.get("record_type") == "corpus_reconciliation"][0]
    assert recon["unused_source_ids"] == []
    assert recon["gaps"] == []
    assert check_module_source_coverage(tmp_path, ["outline/source_coverage.jsonl"]) == []
