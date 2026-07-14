from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO_ROOT / "examples" / "course-paper-pilot"


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
