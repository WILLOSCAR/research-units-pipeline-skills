from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tooling.executor import run_one_unit
from tooling.harness import (
    validate_artifact_pack_payload,
    validate_doctor_payload,
    validate_improvement_payload,
    validate_run_audit_diff_payload,
    validate_run_audit_payload,
    write_unit_manifest,
)
from tooling.pipeline_spec import PipelineSpec


REPO_ROOT = Path(__file__).resolve().parents[1]
UNIT_FIELDS = [
    "unit_id",
    "title",
    "skill",
    "owner",
    "depends_on",
    "checkpoint",
    "inputs",
    "outputs",
    "status",
]


def run_command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write_units(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=UNIT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in UNIT_FIELDS})


def run_audit_payload(
    *,
    workspace: str,
    unit_status: dict[str, int],
    target_artifacts: list[dict[str, object]],
    manifest_count: int,
    issues: list[dict[str, str]],
    verdict: str,
) -> dict[str, object]:
    return {
        "schema": "run-audit.v1",
        "generated_at": "2026-05-30T00:00:00",
        "workspace": workspace,
        "repo": "/tmp/repo",
        "pipeline_lock": "pipeline: pipelines/research-brief.pipeline.md",
        "pipeline": "research-brief",
        "current_checkpoint": "C1",
        "run_ledger_files": {
            "PIPELINE.lock.md": True,
            "GOAL.md": True,
            "UNITS.csv": True,
            "STATUS.md": True,
            "CHECKPOINTS.md": True,
            "DECISIONS.md": True,
        },
        "run_state": {
            "phase": "attention" if issues else "complete_candidate",
            "units_total": sum(unit_status.values()),
            "active_units": sum(unit_status.get(status, 0) for status in ("TODO", "DOING", "BLOCKED")),
            "target_artifacts_total": len(target_artifacts),
            "target_artifacts_present": sum(1 for item in target_artifacts if item.get("exists") is True),
            "target_artifacts_missing": sum(1 for item in target_artifacts if item.get("exists") is not True),
            "unit_output_manifest_count": manifest_count,
            "harness_issue_count": len(issues),
            "error_count": len([issue for issue in issues if issue.get("level") == "ERROR"]),
            "warn_count": len([issue for issue in issues if issue.get("level") == "WARN"]),
        },
        "unit_status": unit_status,
        "target_artifacts": target_artifacts,
        "unit_output_manifests": {
            "count": manifest_count,
            "by_status": {"DONE": manifest_count} if manifest_count else {},
            "latest": {},
            "records": [],
        },
        "harness_issues": issues,
        "remediation_summary": {"repair_run_artifacts": len(issues)} if issues else {},
        "recent_reports": [],
        "verdict": verdict,
        "exit_code": 0 if verdict == "PASS" else 2,
    }


def test_doctor_reports_next_runnable_unit(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U001",
                "title": "Seed",
                "skill": "demo",
                "owner": "CODEX",
                "outputs": "output/seed.md",
                "status": "DONE",
            },
            {
                "unit_id": "U010",
                "title": "Write",
                "skill": "demo",
                "owner": "CODEX",
                "depends_on": "U001",
                "checkpoint": "C1",
                "outputs": "output/write.md",
                "status": "TODO",
            },
        ],
    )
    (workspace / "STATUS.md").write_text("# Status\n\n## Current checkpoint\n- `C1`\n", encoding="utf-8")
    (workspace / "PIPELINE.lock.md").write_text("pipeline: pipelines/tutorial.pipeline.md\n", encoding="utf-8")
    (workspace / "output").mkdir(parents=True)
    (workspace / "output" / "seed.md").write_text("seed\n", encoding="utf-8")

    result = run_command("scripts/pipeline.py", "doctor", "--workspace", str(workspace))

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Next runnable: `U010` Write (`demo`)" in result.stdout
    assert "Kind: `run_next_unit`" in result.stdout
    assert f"Command: `python scripts/pipeline.py run --workspace {workspace.resolve()}`" in result.stdout
    assert "Reason: Next runnable unit U010 is ready." in result.stdout
    assert "Current checkpoint: `C1`" in result.stdout
    assert "DONE: 1" in result.stdout
    assert "TODO: 1" in result.stdout


def test_doctor_flags_units_dependency_and_artifact_problems(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U001",
                "title": "Done but missing output",
                "skill": "demo",
                "owner": "CODEX",
                "outputs": "output/missing.md",
                "status": "DONE",
            },
            {
                "unit_id": "U010",
                "title": "Missing dep",
                "skill": "demo",
                "owner": "CODEX",
                "depends_on": "U999",
                "outputs": "output/next.md",
                "status": "TODO",
            },
            {
                "unit_id": "U020",
                "title": "Human gate",
                "skill": "human-checkpoint",
                "owner": "HUMAN",
                "status": "TODO",
            },
        ],
    )

    result = run_command("scripts/pipeline.py", "doctor", "--workspace", str(workspace))

    assert result.returncode == 2, result.stdout
    assert "ERROR `missing_dependency`: `U010` depends on missing `U999`" in result.stdout
    assert "Remediation: `repair_dependency_graph`" in result.stdout
    assert "Next action: Add or restore the dependency unit" in result.stdout
    assert "ERROR `missing_done_output`: `U001` is DONE but `output/missing.md` is missing" in result.stdout
    assert "Remediation: `repair_artifact_contract`" in result.stdout
    assert "WARN `human_checkpoint_missing`: `U020` is HUMAN-owned but has no checkpoint" in result.stdout
    assert "Remediation: `record_human_checkpoint`" in result.stdout
    assert "`repair_artifact_contract`: 1" in result.stdout
    assert "`repair_dependency_graph`: 1" in result.stdout
    assert "`record_human_checkpoint`: 1" in result.stdout


def test_doctor_flags_units_cycles_and_invalid_statuses(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U001",
                "title": "A",
                "skill": "demo",
                "owner": "CODEX",
                "depends_on": "U020",
                "outputs": "output/a.md",
                "status": "DONE",
            },
            {
                "unit_id": "U020",
                "title": "B",
                "skill": "demo",
                "owner": "CODEX",
                "depends_on": "U001",
                "outputs": "output/b.md",
                "status": "WAITING",
            },
        ],
    )
    (workspace / "output").mkdir(parents=True)
    (workspace / "output" / "a.md").write_text("a\n", encoding="utf-8")

    result = run_command("scripts/pipeline.py", "doctor", "--workspace", str(workspace))

    assert result.returncode == 2, result.stdout
    assert "ERROR `invalid_status`: `U020` has invalid status `WAITING`" in result.stdout
    assert "Remediation: `repair_unit_status`" in result.stdout
    assert "ERROR `dependency_cycle`: `U001` -> `U020` -> `U001`" in result.stdout
    assert "Remediation: `repair_dependency_graph`" in result.stdout


def test_doctor_reports_typed_remediation_for_missing_units(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()

    result = run_command("scripts/pipeline.py", "doctor", "--workspace", str(workspace))

    assert result.returncode == 2, result.stdout
    assert "ERROR `missing_units`: Missing" in result.stdout
    assert "Remediation: `restore_workspace_contract`" in result.stdout
    assert "Next action: Create or restore `UNITS.csv` from the selected pipeline unit template" in result.stdout
    assert "Kind: `repair_first`" in result.stdout
    assert f"Command: `python scripts/pipeline.py improve --workspace {workspace.resolve()} --write`" in result.stdout
    assert "`restore_workspace_contract`: 1" in result.stdout


def test_doctor_writes_durable_report_when_requested(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U001",
                "title": "Seed",
                "skill": "demo",
                "owner": "CODEX",
                "outputs": "output/seed.md",
                "status": "DONE",
            }
        ],
    )
    (workspace / "output").mkdir(parents=True)
    (workspace / "output" / "seed.md").write_text("seed\n", encoding="utf-8")

    result = run_command("scripts/pipeline.py", "doctor", "--workspace", str(workspace), "--write")

    report_path = workspace / "output" / "DOCTOR_REPORT.md"
    json_path = workspace / "output" / "DOCTOR_REPORT.json"
    assert result.returncode == 0, result.stdout
    assert report_path.exists()
    assert json_path.exists()
    assert f"Wrote {report_path}" in result.stdout
    assert f"Wrote {json_path}" in result.stdout
    report = report_path.read_text(encoding="utf-8")
    assert "# Pipeline doctor" in report
    assert "DONE: 1" in report
    assert "Kind: `audit_state`" in report
    assert f"Command: `python scripts/pipeline.py audit --workspace {workspace.resolve()} --write`" in report
    assert "No harness issues" in report
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "doctor-report.v1"
    assert payload["unit_status"] == {"DONE": 1}
    assert payload["resume_hint"]["kind"] == "audit_state"
    assert payload["resume_hint"]["command"] == f"python scripts/pipeline.py audit --workspace {workspace.resolve()} --write"
    assert payload["verdict"] == "PASS"
    assert validate_doctor_payload(payload) == []


def test_doctor_payload_validator_reports_schema_drift() -> None:
    payload = {
        "schema": "doctor-report.v2",
        "generated_at": "2026-05-29T00:00:00",
        "workspace": "/tmp/ws",
        "repo": "/tmp/repo",
        "pipeline_lock": "",
        "current_checkpoint": "unknown",
        "units_present": "yes",
        "unit_status": {"DONE": "1"},
        "next_runnable": {"unit_id": 10},
        "resume_hint": {"kind": 10, "command": "python scripts/pipeline.py audit --workspace /tmp/ws --write"},
        "harness_issues": [],
        "remediation_summary": {},
        "recent_reports": [],
        "verdict": "PASS",
        "exit_code": 0,
    }

    issues = validate_doctor_payload(payload)

    assert "`schema` must be `doctor-report.v1`" in issues
    assert "`units_present` must be a boolean" in issues
    assert "`unit_status.DONE` must be an integer" in issues
    assert "`next_runnable.unit_id` must be a string" in issues
    assert "`resume_hint.kind` must be a string" in issues
    assert "`resume_hint.reason` is missing" in issues


def test_audit_writes_compact_run_ledger_when_artifacts_are_present(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    spec = PipelineSpec.load(REPO_ROOT / "pipelines" / "research-brief.pipeline.md")
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U001",
                "title": "Snapshot",
                "skill": "snapshot-writer",
                "owner": "CODEX",
                "outputs": "output/SNAPSHOT.md",
                "status": "DONE",
            }
        ],
    )
    (workspace / "PIPELINE.lock.md").write_text(
        "pipeline: pipelines/research-brief.pipeline.md\n"
        "units_template: templates/UNITS.research-brief.csv\n"
        "locked_at: 2026-05-28\n",
        encoding="utf-8",
    )
    (workspace / "STATUS.md").write_text("# Status\n\n## Current checkpoint\n- `C3`\n", encoding="utf-8")
    for relpath in spec.target_artifacts:
        path = workspace / relpath
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relpath}\n", encoding="utf-8")
    write_unit_manifest(
        workspace=workspace,
        unit_id="U001",
        skill="snapshot-writer",
        outputs=["output/SNAPSHOT.md"],
        exit_code=0,
        status="DONE",
    )

    result = run_command("scripts/pipeline.py", "audit", "--workspace", str(workspace), "--write")

    audit_path = workspace / "output" / "RUN_AUDIT.md"
    audit_json_path = workspace / "output" / "RUN_AUDIT.json"
    assert result.returncode == 0, result.stdout
    assert audit_path.exists()
    assert audit_json_path.exists()
    assert "Wrote " in result.stdout
    assert "Pipeline: `research-brief`" in result.stdout
    assert "JSON sidecar: `output/RUN_AUDIT.json`" in result.stdout
    assert "Current checkpoint: `C3`" in result.stdout
    assert "Phase: `complete_candidate`" in result.stdout
    assert "Target artifacts: 16 present / 0 missing" in result.stdout
    assert "DONE: 1" in result.stdout
    assert "Manifests: 1" in result.stdout
    assert "No harness issues" in result.stdout
    assert "PASS" in audit_path.read_text(encoding="utf-8")
    audit_payload = json.loads(audit_json_path.read_text(encoding="utf-8"))
    assert audit_payload["schema"] == "run-audit.v1"
    assert audit_payload["pipeline"] == "research-brief"
    assert audit_payload["verdict"] == "PASS"
    assert audit_payload["run_state"]["phase"] == "complete_candidate"
    assert audit_payload["run_state"]["target_artifacts_missing"] == 0
    assert audit_payload["run_state"]["unit_output_manifest_count"] == 1
    assert audit_payload["unit_status"] == {"DONE": 1}
    assert audit_payload["unit_output_manifests"]["count"] == 1
    assert validate_run_audit_payload(audit_payload) == []


def test_run_audit_payload_validator_reports_schema_drift() -> None:
    payload = {
        "schema": "run-audit.v2",
        "generated_at": "2026-05-29T00:00:00",
        "workspace": "/tmp/ws",
        "repo": "/tmp/repo",
        "pipeline_lock": "",
        "pipeline": "",
        "current_checkpoint": "unknown",
        "run_ledger_files": {"UNITS.csv": "yes"},
        "run_state": {"phase": 10, "units_total": "1"},
        "unit_status": {"DONE": "1"},
        "target_artifacts": [{"path": "output/SNAPSHOT.md", "exists": True}],
        "unit_output_manifests": {"count": 0, "by_status": {}, "latest": {}, "records": []},
        "harness_issues": [],
        "remediation_summary": {},
        "recent_reports": [],
        "verdict": "PASS",
        "exit_code": 0,
    }

    issues = validate_run_audit_payload(payload)

    assert "`schema` must be `run-audit.v1`" in issues
    assert "`run_ledger_files.PIPELINE.lock.md` is missing" in issues
    assert "`run_ledger_files.UNITS.csv` must be a boolean" in issues
    assert "`run_state.phase` must be a string" in issues
    assert "`run_state.units_total` must be an integer" in issues
    assert "`run_state.active_units` must be an integer" in issues
    assert "`unit_status.DONE` must be an integer" in issues


def test_audit_reports_missing_target_artifacts(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U001",
                "title": "Snapshot",
                "skill": "snapshot-writer",
                "owner": "CODEX",
                "outputs": "output/SNAPSHOT.md",
                "status": "DONE",
            }
        ],
    )
    (workspace / "PIPELINE.lock.md").write_text(
        "pipeline: pipelines/research-brief.pipeline.md\n"
        "units_template: templates/UNITS.research-brief.csv\n"
        "locked_at: 2026-05-28\n",
        encoding="utf-8",
    )

    result = run_command("scripts/pipeline.py", "audit", "--workspace", str(workspace))

    assert result.returncode == 2, result.stdout
    assert "ERROR `missing_target_artifact`: Target artifact `output/SNAPSHOT.md` is missing" in result.stdout
    assert "Remediation: `repair_run_artifacts`" in result.stdout
    assert "ATTENTION" in result.stdout


def test_improve_writes_repair_suggestions_from_run_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U001",
                "title": "Snapshot",
                "skill": "snapshot-writer",
                "owner": "CODEX",
                "outputs": "output/SNAPSHOT.md",
                "status": "DONE",
            }
        ],
    )
    (workspace / "PIPELINE.lock.md").write_text(
        "pipeline: pipelines/research-brief.pipeline.md\n"
        "units_template: templates/UNITS.research-brief.csv\n"
        "locked_at: 2026-05-30\n",
        encoding="utf-8",
    )

    result = run_command("scripts/pipeline.py", "improve", "--workspace", str(workspace), "--write")

    report_path = workspace / "output" / "IMPROVEMENT_REPORT.md"
    json_path = workspace / "output" / "IMPROVEMENT_REPORT.json"
    assert result.returncode == 2, result.stdout
    assert report_path.exists()
    assert json_path.exists()
    assert "Improvement report" in result.stdout
    assert "Target artifact contract" in result.stdout
    assert "repair_run_artifacts" in result.stdout
    assert "python scripts/pipeline.py audit --workspace" in result.stdout
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "improvement-report.v1"
    assert payload["verdict"] == "ATTENTION"
    assert payload["artifact_interface_standard"] == "docs/PROJECT_LANGUAGE.md"
    assert payload["suggestions"][0]["upstream_interface"] == "Artifact contract / unit outputs"
    assert validate_improvement_payload(payload) == []


def test_improvement_payload_validator_reports_shape_errors() -> None:
    payload = {
        "schema": "improvement-report.v2",
        "generated_at": "2026-05-30T00:00:00",
        "workspace": "/tmp/ws",
        "repo": "/tmp/repo",
        "pipeline": "research-brief",
        "artifact_interface_standard": "docs/PROJECT_LANGUAGE.md",
        "source_reports": {"doctor": {"schema": "doctor-report.v1", "verdict": "PASS", "exit_code": "0"}},
        "suggestions": [{"id": "S001", "source_report": "doctor", "observed_problem": 123}],
        "verdict": "PASS",
        "exit_code": 0,
    }

    issues = validate_improvement_payload(payload)

    assert "`schema` must be `improvement-report.v1`" in issues
    assert "`source_reports.doctor.exit_code` must be an integer" in issues
    assert "`suggestions[0].observed_problem` must be a string" in issues
    assert "`suggestions[0].repair_surface` must be a string" in issues


def test_pack_writes_reviewable_artifact_manifest(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    spec = PipelineSpec.load(REPO_ROOT / "pipelines" / "research-brief.pipeline.md")
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U001",
                "title": "Snapshot",
                "skill": "snapshot-writer",
                "owner": "CODEX",
                "outputs": "output/SNAPSHOT.md",
                "status": "DONE",
            }
        ],
    )
    (workspace / "PIPELINE.lock.md").write_text(
        "pipeline: pipelines/research-brief.pipeline.md\n"
        "units_template: templates/UNITS.research-brief.csv\n"
        "locked_at: 2026-05-30\n",
        encoding="utf-8",
    )
    (workspace / "GOAL.md").write_text("# Goal\n\nDemo\n", encoding="utf-8")
    (workspace / "STATUS.md").write_text("# Status\n\n## Current checkpoint\n- `C3`\n", encoding="utf-8")
    (workspace / "CHECKPOINTS.md").write_text("# Checkpoints\n", encoding="utf-8")
    (workspace / "DECISIONS.md").write_text("# Decisions\n", encoding="utf-8")
    for relpath in spec.target_artifacts:
        path = workspace / relpath
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relpath}\n", encoding="utf-8")
    write_unit_manifest(
        workspace=workspace,
        unit_id="U001",
        skill="snapshot-writer",
        outputs=["output/SNAPSHOT.md"],
        exit_code=0,
        status="DONE",
    )

    result = run_command(
        "scripts/pipeline.py",
        "pack",
        "--workspace",
        str(workspace),
        "--write",
        "--write-excerpt",
    )

    report_path = workspace / "output" / "ARTIFACT_PACK.md"
    json_path = workspace / "output" / "ARTIFACT_PACK.json"
    excerpt_md_path = workspace / "output" / "ARTIFACT_PACK_EXCERPT.md"
    excerpt_tsv_path = workspace / "output" / "ARTIFACT_PACK_EXCERPT.tsv"
    assert result.returncode == 0, result.stdout
    assert report_path.exists()
    assert json_path.exists()
    assert excerpt_md_path.exists()
    assert excerpt_tsv_path.exists()
    assert "Artifact pack" in result.stdout
    assert "target_artifact" in result.stdout
    assert "run_ledger" in result.stdout
    assert "unit_manifest" in result.stdout
    assert "Run state: `complete_candidate`; 16 target artifacts present, 0 missing; 0 errors" in result.stdout
    assert "ARTIFACT_PACK_EXCERPT.md" in result.stdout
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "artifact-pack.v1"
    assert payload["verdict"] == "PASS"
    assert payload["source_reports"]["run_audit"]["schema"] == "run-audit.v1"
    assert payload["source_reports"]["run_audit"]["run_state"]["phase"] == "complete_candidate"
    assert payload["source_reports"]["run_audit"]["run_state"]["target_artifacts_missing"] == 0
    assert payload["summary"]["by_category"]["target_artifact"]["missing"] == 0
    categories = {record["category"] for record in payload["artifacts"]}
    assert {"target_artifact", "unit_output", "run_ledger", "harness_report", "unit_manifest"}.issubset(categories)
    excerpt_md = excerpt_md_path.read_text(encoding="utf-8")
    excerpt_tsv = excerpt_tsv_path.read_text(encoding="utf-8")
    assert "# Artifact Pack Excerpt" in excerpt_md
    assert "artifact-pack.v1" in excerpt_md
    assert "| `target_artifact` | `output/SNAPSHOT.md` | true | final deliverable or declared target artifact |" in excerpt_md
    assert "category\tpath\texists\trole" in excerpt_tsv
    assert "target_artifact\toutput/SNAPSHOT.md\ttrue\tfinal deliverable or declared target artifact" in excerpt_tsv
    assert validate_artifact_pack_payload(payload) == []


def test_artifact_pack_payload_validator_reports_shape_errors() -> None:
    payload = {
        "schema": "artifact-pack.v2",
        "generated_at": "2026-05-30T00:00:00",
        "workspace": "/tmp/ws",
        "repo": "/tmp/repo",
        "pipeline": "research-brief",
        "artifact_interface_standard": "docs/PROJECT_LANGUAGE.md",
        "source_reports": {
            "run_audit": {
                "schema": "run-audit.v1",
                "verdict": "PASS",
                "exit_code": "0",
                "run_state": {"phase": "stuck", "units_total": "1"},
            }
        },
        "artifacts": [{"category": "target_artifact", "path": "output/SNAPSHOT.md", "exists": "yes"}],
        "summary": {"total": 1, "present": "1", "missing": 0, "by_category": {"target_artifact": {"total": 1}}},
        "verdict": "PASS",
        "exit_code": 0,
    }

    issues = validate_artifact_pack_payload(payload)

    assert "`schema` must be `artifact-pack.v1`" in issues
    assert "`source_reports.run_audit.exit_code` must be an integer" in issues
    assert "`source_reports.run_audit.run_state.phase` must be one of attention, complete_candidate, in_progress" in issues
    assert "`source_reports.run_audit.run_state.units_total` must be an integer" in issues
    assert "`source_reports.run_audit.run_state.active_units` must be an integer" in issues
    assert "`artifacts[0].exists` must be a boolean" in issues
    assert "`summary.present` must be an integer" in issues
    assert "`summary.by_category.target_artifact.present` must be an integer" in issues


def test_audit_diff_reports_improved_target_artifact_coverage(tmp_path: Path) -> None:
    before_path = tmp_path / "before" / "RUN_AUDIT.json"
    after_path = tmp_path / "after" / "RUN_AUDIT.json"
    before_path.parent.mkdir(parents=True)
    after_path.parent.mkdir(parents=True)
    before_payload = run_audit_payload(
        workspace="/tmp/ws",
        unit_status={"TODO": 1},
        target_artifacts=[
            {"path": "output/SNAPSHOT.md", "exists": True},
            {"path": "output/CONTRACT_REPORT.md", "exists": False},
        ],
        manifest_count=0,
        issues=[
            {
                "level": "ERROR",
                "code": "missing_target_artifact",
                "message": "Target artifact `output/CONTRACT_REPORT.md` is missing",
                "remediation_category": "repair_run_artifacts",
                "next_action": "Finish the producing unit.",
            }
        ],
        verdict="ATTENTION",
    )
    after_payload = run_audit_payload(
        workspace="/tmp/ws",
        unit_status={"DONE": 1},
        target_artifacts=[
            {"path": "output/SNAPSHOT.md", "exists": True},
            {"path": "output/CONTRACT_REPORT.md", "exists": True},
        ],
        manifest_count=1,
        issues=[],
        verdict="PASS",
    )
    before_path.write_text(json.dumps(before_payload), encoding="utf-8")
    after_path.write_text(json.dumps(after_payload), encoding="utf-8")

    result = run_command(
        "scripts/pipeline.py",
        "audit-diff",
        "--before",
        str(before_path),
        "--after",
        str(after_path),
        "--write",
    )

    diff_json_path = after_path.parent / "RUN_AUDIT_DIFF.json"
    assert result.returncode == 0, result.stdout
    assert "Run audit diff" in result.stdout
    assert "`output/CONTRACT_REPORT.md`: became_present" in result.stdout
    assert "TODO: -1" in result.stdout
    assert "DONE: +1" in result.stdout
    assert "No comparison issues" in result.stdout
    assert diff_json_path.exists()
    diff_payload = json.loads(diff_json_path.read_text(encoding="utf-8"))
    assert diff_payload["schema"] == "run-audit-diff.v1"
    assert diff_payload["verdict"] == "PASS"
    assert diff_payload["manifest_counts"] == {"before": 0, "after": 1, "delta": 1}
    assert validate_run_audit_diff_payload(diff_payload) == []


def test_audit_diff_flags_after_regression(tmp_path: Path) -> None:
    before_path = tmp_path / "before" / "RUN_AUDIT.json"
    after_path = tmp_path / "after" / "RUN_AUDIT.json"
    before_path.parent.mkdir(parents=True)
    after_path.parent.mkdir(parents=True)
    before_path.write_text(
        json.dumps(
            run_audit_payload(
                workspace="/tmp/ws",
                unit_status={"DONE": 1},
                target_artifacts=[{"path": "output/SNAPSHOT.md", "exists": True}],
                manifest_count=1,
                issues=[],
                verdict="PASS",
            )
        ),
        encoding="utf-8",
    )
    after_path.write_text(
        json.dumps(
            run_audit_payload(
                workspace="/tmp/ws",
                unit_status={"DONE": 1},
                target_artifacts=[{"path": "output/SNAPSHOT.md", "exists": False}],
                manifest_count=1,
                issues=[
                    {
                        "level": "ERROR",
                        "code": "missing_target_artifact",
                        "message": "Target artifact `output/SNAPSHOT.md` is missing",
                        "remediation_category": "repair_run_artifacts",
                        "next_action": "Finish the producing unit.",
                    }
                ],
                verdict="ATTENTION",
            )
        ),
        encoding="utf-8",
    )

    result = run_command("scripts/pipeline.py", "audit-diff", "--before", str(before_path), "--after", str(after_path))

    assert result.returncode == 2, result.stdout
    assert "`output/SNAPSHOT.md`: became_missing" in result.stdout
    assert "Target artifact `output/SNAPSHOT.md` is missing in the after audit" in result.stdout
    assert "Diff verdict" in result.stdout
    assert "ATTENTION" in result.stdout


def test_run_audit_diff_payload_validator_reports_schema_drift() -> None:
    payload = {
        "schema": "run-audit-diff.v2",
        "generated_at": "2026-05-30T00:00:00",
        "before_path": "/tmp/before.json",
        "after_path": "/tmp/after.json",
        "before_schema": "run-audit.v1",
        "after_schema": "run-audit.v1",
        "before_workspace": "/tmp/ws",
        "after_workspace": "/tmp/ws",
        "before_pipeline": "research-brief",
        "after_pipeline": "research-brief",
        "before_verdict": "ATTENTION",
        "after_verdict": "PASS",
        "unit_status_delta": {"DONE": "1"},
        "target_artifact_changes": [{"path": "output/a.md", "before_exists": "no", "after_exists": True}],
        "manifest_counts": {"before": 0, "after": 1, "delta": "1"},
        "harness_issue_counts": {"before": 1, "after": 0, "delta": -1},
        "comparison_issues": [123],
        "verdict": "PASS",
        "exit_code": 0,
    }

    issues = validate_run_audit_diff_payload(payload)

    assert "`schema` must be `run-audit-diff.v1`" in issues
    assert "`unit_status_delta.DONE` must be an integer" in issues
    assert "`target_artifact_changes[0].before_exists` must be a boolean or null" in issues
    assert "`manifest_counts.delta` must be an integer" in issues
    assert "`comparison_issues[0]` must be a string" in issues


def test_executor_writes_manifest_for_scripted_unit_outputs(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    script_path = repo_root / ".codex" / "skills" / "demo-skill" / "scripts" / "run.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse",
                "from pathlib import Path",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--workspace', required=True)",
                "parser.add_argument('--unit-id', required=True)",
                "parser.add_argument('--inputs', default='')",
                "parser.add_argument('--outputs', default='')",
                "parser.add_argument('--checkpoint', default='')",
                "args = parser.parse_args()",
                "output = [x for x in args.outputs.split(';') if x][0]",
                "path = Path(args.workspace) / output",
                "path.parent.mkdir(parents=True, exist_ok=True)",
                "path.write_text('demo output\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U001",
                "title": "Demo",
                "skill": "demo-skill",
                "owner": "CODEX",
                "outputs": "output/demo.md",
                "status": "TODO",
            }
        ],
    )

    result = run_one_unit(workspace=workspace, repo_root=repo_root)

    manifest_path = workspace / "output" / "unit_logs" / "U001.demo-skill.manifest.json"
    assert result.status == "DONE"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["unit_id"] == "U001"
    assert manifest["skill"] == "demo-skill"
    assert manifest["exit_code"] == 0
    assert manifest["outputs"][0]["path"] == "output/demo.md"
    assert manifest["outputs"][0]["exists"] is True
    assert manifest["outputs"][0]["sha256"]
