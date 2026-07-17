from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO_ROOT / "examples" / "course-paper-pilot"
BRIEF_SNAPSHOT = REPO_ROOT / "examples" / "research-brief-harness-proof"


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
    assert summary["repository"]["dirty"] is True
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
