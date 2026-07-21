from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO_ROOT / "examples" / "course-paper-pilot"
BRIEF_SNAPSHOT = REPO_ROOT / "examples" / "research-brief-harness-proof"
REAL_BRIEF_SNAPSHOT = REPO_ROOT / "examples" / "research-brief-real-source-proof"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_course_paper_snapshot_is_complete_and_hash_consistent() -> None:
    summary = json.loads((SNAPSHOT / "run-summary.json").read_text(encoding="utf-8"))

    assert summary["schema"] == "completed-run-evidence.v1"
    assert summary["workflow"] == "arxiv-survey-latex"
    assert summary["run_state"] == "COMPLETED"
    assert summary["units"] == {"total": 49, "done": 49, "active": 0}
    assert summary["artifact_audit"]["verdict"] == "PASS"
    assert summary["artifact_audit"]["target_artifacts_missing"] == 0
    assert summary["delivery"]["pages"] == 10

    for relative_path, metadata in summary["files"].items():
        artifact = SNAPSHOT / relative_path
        assert artifact.is_file(), relative_path
        assert _sha256(artifact) == metadata["sha256"], relative_path

    assert (SNAPSHOT / "paper.pdf").read_bytes().startswith(b"%PDF-")


def test_course_paper_snapshot_exposes_the_completed_unit_plan() -> None:
    with (SNAPSHOT / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 49
    assert {row["status"] for row in rows} == {"DONE"}
    assert rows[0]["skill"] == "workspace-init"
    assert rows[-1]["skill"] == "artifact-contract-auditor"


def test_research_brief_harness_proof_is_complete_and_hash_consistent() -> None:
    summary = json.loads((BRIEF_SNAPSHOT / "run-summary.json").read_text(encoding="utf-8"))

    assert summary["schema"] == "completed-run-evidence.v1"
    assert summary["workflow"] == "research-brief"
    assert summary["source_mode"] == "deterministic_synthetic_fixture"
    assert summary["run_state"] == "COMPLETED"
    assert summary["completion_protocol"] == "recoverable-provenance.v1"
    assert summary["repository"]["dirty"] is False
    assert len(summary["repository"]["revision"]) == 40
    assert summary["repository"]["locked_kernel_files"] > 0
    assert summary["repository"]["locked_skills"] > 0
    assert summary["units"] == {"total": 11, "done": 11, "active": 0}
    assert summary["attempts"]["succeeded"] == 11
    assert summary["attempts"]["extra_attempts"] == 0
    assert summary["artifact_audit"]["verdict"] == "PASS"
    assert summary["artifact_audit"]["target_artifacts_missing"] == 0
    assert summary["artifact_audit"]["ledger_integrity_issues"] == 0
    assert summary["evaluation"]["verdict"] == "PASS"
    assert summary["evaluation"]["score"] == 100
    assert summary["historical_comparison"]["harness_issue_delta"] == -8

    for relative_path, metadata in summary["files"].items():
        artifact = BRIEF_SNAPSHOT / relative_path
        assert artifact.is_file(), relative_path
        assert _sha256(artifact) == metadata["sha256"], relative_path


def test_research_brief_harness_proof_exposes_plan_sources_and_scorecard() -> None:
    with (BRIEF_SNAPSHOT / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with (BRIEF_SNAPSHOT / "papers" / "core_set.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        core_papers = list(csv.DictReader(handle))
    scorecard = json.loads((BRIEF_SNAPSHOT / "BRIEF_SCORECARD.json").read_text(encoding="utf-8"))

    assert len(rows) == 11
    assert {row["status"] for row in rows} == {"DONE"}
    assert rows[0]["skill"] == "workspace-init"
    assert rows[-1]["skill"] == "artifact-contract-auditor"
    assert len(core_papers) == 12
    assert all(record["url"].startswith("https://example.org/") for record in core_papers)
    assert scorecard["schema"] == "research-brief-scorecard.v1"
    assert scorecard["verdict"] == "PASS"
    assert scorecard["failures"] == []


def test_real_source_research_brief_proof_is_complete_and_hash_consistent() -> None:
    summary = json.loads((REAL_BRIEF_SNAPSHOT / "run-summary.json").read_text(encoding="utf-8"))

    assert summary["schema"] == "completed-run-evidence.v1"
    assert summary["workflow"] == "research-brief"
    assert summary["source_mode"] == "online_arxiv_api"
    assert summary["strict_quality_gates"] is True
    assert summary["run_state"] == "COMPLETED"
    assert summary["completion_protocol"] == "recoverable-provenance.v1"
    assert summary["repository"]["dirty"] is False
    assert len(summary["repository"]["revision"]) == 40
    assert summary["units"] == {"total": 11, "done": 11, "active": 0}
    assert summary["attempts"]["succeeded"] == 11
    assert summary["attempts"]["extra_attempts"] == 0
    assert summary["retrieval"] == {
        "provider": "arxiv_api",
        "raw_records": 80,
        "deduplicated_records": 80,
        "core_papers": 12,
        "minimum_records_gate": 15,
    }
    assert summary["artifact_audit"]["verdict"] == "PASS"
    assert summary["artifact_audit"]["ledger_integrity_issues"] == 0
    assert summary["evaluation"]["verdict"] == "PASS"
    assert summary["evaluation"]["score"] == 100
    assert summary["evaluation"]["words"] == 539
    assert summary["product_loop"]["required_evidence"] == "complete"
    assert summary["baseline_comparison"]["verdict"] == "PASS"

    for relative_path, metadata in summary["files"].items():
        artifact = REAL_BRIEF_SNAPSHOT / relative_path
        assert artifact.is_file(), relative_path
        assert _sha256(artifact) == metadata["sha256"], relative_path


def test_real_source_research_brief_proof_exposes_arxiv_sources_without_private_run_ids() -> None:
    with (REAL_BRIEF_SNAPSHOT / "papers" / "core_set.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        core_papers = list(csv.DictReader(handle))
    scorecard = json.loads((REAL_BRIEF_SNAPSHOT / "BRIEF_SCORECARD.json").read_text(encoding="utf-8"))

    assert len(core_papers) == 12
    assert all("arxiv.org/abs/" in record["url"] for record in core_papers)
    assert all(record["arxiv_id"] for record in core_papers)
    assert scorecard["schema"] == "research-brief-scorecard.v1"
    assert scorecard["verdict"] == "PASS"
    assert scorecard["counts"]["words"] == 539

    for path in REAL_BRIEF_SNAPSHOT.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".json", ".csv"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "/Users/" not in text, path
        assert not re.search(r"\b(?:run|attempt)_[0-9a-f]{8,}\b", text), path
