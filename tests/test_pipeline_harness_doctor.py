from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tooling.executor import run_one_unit
from tooling.harness import (
    build_doctor_payload,
    build_run_audit_payload,
    build_run_audit_diff_payload,
    render_run_audit_report,
    render_run_audit_diff_report,
    validate_artifact_pack_payload,
    validate_doctor_payload,
    validate_improvement_payload,
    validate_run_audit_diff_payload,
    validate_run_audit_payload,
    write_unit_manifest,
)
from tooling.pipeline_spec import PipelineSpec
from tooling.run_state import initialize_run_state, record_evaluation


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
    attempts: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
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
    if attempts is not None:
        payload["attempts"] = attempts
    return payload


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
    (workspace / "PIPELINE.lock.md").write_text("pipeline: pipelines/source-tutorial.pipeline.md\n", encoding="utf-8")
    (workspace / "output").mkdir(parents=True)
    (workspace / "output" / "seed.md").write_text("seed\n", encoding="utf-8")

    result = run_command("scripts/pipeline.py", "doctor", "--workspace", str(workspace))

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Next runnable: `U010` Write (`demo`)" in result.stdout
    assert "Kind: `run_next_unit`" in result.stdout
    assert f"Command: `uv run python scripts/pipeline.py run --workspace {workspace.resolve()}`" in result.stdout
    assert "Reason: Next runnable unit U010 is ready." in result.stdout
    assert "Current checkpoint: `C1`" in result.stdout
    assert "DONE: 1" in result.stdout
    assert "TODO: 1" in result.stdout


def test_standalone_doctor_skips_deep_ledger_integrity_scan(monkeypatch, tmp_path: Path) -> None:
    import tooling.run_state as run_state

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
                "status": "TODO",
            }
        ],
    )
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")

    def fail_if_called(_workspace: Path) -> dict[str, object]:
        raise AssertionError("standalone Doctor must not run the deep integrity pass")

    monkeypatch.setattr(run_state, "inspect_run_integrity", fail_if_called)

    exit_code, payload = build_doctor_payload(workspace=workspace, repo_root=REPO_ROOT)

    assert exit_code == 0
    assert payload["schema"] == "doctor-report.v1"


def test_run_audit_loads_the_pinned_pipeline_snapshot_without_live_lookup(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import tooling.harness as harness
    import tooling.common as common

    workspace = tmp_path / "snapshot-run"
    result = run_command(
        "scripts/pipeline.py",
        "init",
        "--workspace",
        str(workspace),
        "--pipeline",
        "arxiv-survey-latex",
    )
    assert result.returncode == 0, result.stderr or result.stdout

    monkeypatch.setattr(
        common,
        "resolve_pipeline_spec_path",
        lambda **_: (_ for _ in ()).throw(AssertionError("live Pipeline lookup must not run")),
    )

    snapshot = harness._collect_workspace_inspection_snapshot(
        workspace=workspace,
        repo_root=REPO_ROOT,
    )

    assert snapshot.pipeline_name == "arxiv-survey-latex"


def test_doctor_points_blocked_units_to_repair_reports(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U010",
                "title": "Retrieve",
                "skill": "arxiv-search",
                "owner": "CODEX",
                "outputs": "papers/papers_raw.jsonl",
                "status": "BLOCKED",
            },
        ],
    )

    result = run_command("scripts/pipeline.py", "doctor", "--workspace", str(workspace))

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Next runnable: `U010` Retrieve (`arxiv-search`) [BLOCKED]" in result.stdout
    assert "Kind: `repair_blocked_unit`" in result.stdout
    assert f"Command: `uv run python scripts/pipeline.py improve --workspace {workspace.resolve()} --write`" in result.stdout
    assert "Unit U010 is BLOCKED; inspect `output/QUALITY_GATE.md`, `output/RUN_ERRORS.md`, and unit logs" in result.stdout


def test_doctor_routes_human_checkpoint_to_explicit_approval(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U055",
                "title": "Approve outline",
                "skill": "human-checkpoint",
                "owner": "HUMAN",
                "checkpoint": "C2",
                "status": "BLOCKED",
            },
        ],
    )

    result = run_command("scripts/pipeline.py", "doctor", "--workspace", str(workspace))

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Kind: `await_human_approval`" in result.stdout
    assert (
        f"Command: `uv run python scripts/pipeline.py approve --workspace {workspace.resolve()} --checkpoint C2`"
        in result.stdout
    )
    assert "review `DECISIONS.md` and approve it explicitly" in result.stdout


def test_reopening_upstream_revokes_stale_downstream_checkpoint_approval(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U050",
                "title": "Build mapping",
                "skill": "section-mapper",
                "owner": "CODEX",
                "checkpoint": "C2",
                "status": "DONE",
            },
            {
                "unit_id": "U055",
                "title": "Approve structure",
                "skill": "human-checkpoint",
                "owner": "HUMAN",
                "depends_on": "U050",
                "checkpoint": "C2",
                "status": "DONE",
            },
            {
                "unit_id": "U060",
                "title": "Bind evidence",
                "skill": "evidence-binder",
                "owner": "CODEX",
                "depends_on": "U055",
                "checkpoint": "C3",
                "status": "DONE",
            },
        ],
    )
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    (workspace / "DECISIONS.md").write_text(
        "# Decisions\n\n## Approvals (check to unblock)\n- [x] Approve C2\n",
        encoding="utf-8",
    )

    result = run_command(
        "scripts/pipeline.py",
        "mark",
        "--workspace",
        str(workspace),
        "--unit-id",
        "U050",
        "--status",
        "TODO",
        "--note",
        "rebuild mapping",
    )

    assert result.returncode == 0, result.stderr or result.stdout
    with (workspace / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        statuses = {row["unit_id"]: row["status"] for row in csv.DictReader(handle)}
    assert statuses == {"U050": "TODO", "U055": "TODO", "U060": "TODO"}
    assert "- [ ] Approve C2" in (workspace / "DECISIONS.md").read_text(encoding="utf-8")
    assert "revoked stale checkpoint approval(s): C2" in (workspace / "STATUS.md").read_text(
        encoding="utf-8"
    )
    decisions = [
        json.loads(line)
        for line in (workspace / ".harness" / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [record["action"] for record in decisions] == [
        "checkpoint.approval.revoked",
        "unit.status.changed",
    ]
    assert "reset 2 downstream unit(s) to TODO" in result.stdout
    assert "revoked checkpoint approval(s): C2" in result.stdout


def test_doctor_resume_command_quotes_workspace_paths_with_spaces(tmp_path: Path) -> None:
    workspace = tmp_path / "ws with space"
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U010",
                "title": "Write",
                "skill": "demo",
                "owner": "CODEX",
                "outputs": "output/write.md",
                "status": "TODO",
            },
        ],
    )

    result = run_command("scripts/pipeline.py", "doctor", "--workspace", str(workspace))

    assert result.returncode == 0, result.stderr or result.stdout
    quoted_workspace = f"'{workspace.resolve()}'"
    assert f"Command: `uv run python scripts/pipeline.py run --workspace {quoted_workspace}`" in result.stdout


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
    assert f"Command: `uv run python scripts/pipeline.py improve --workspace {workspace.resolve()} --write`" in result.stdout
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
    assert f"Command: `uv run python scripts/pipeline.py audit --workspace {workspace.resolve()} --write`" in report
    assert "No harness issues" in report
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "doctor-report.v1"
    assert payload["unit_status"] == {"DONE": 1}
    assert payload["resume_hint"]["kind"] == "audit_state"
    assert payload["resume_hint"]["command"] == f"uv run python scripts/pipeline.py audit --workspace {workspace.resolve()} --write"
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
        "resume_hint": {"kind": 10, "command": "uv run python scripts/pipeline.py audit --workspace /tmp/ws --write"},
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
    assert result.returncode == 2, result.stdout
    assert audit_path.exists()
    assert audit_json_path.exists()
    assert "Wrote " in result.stdout
    assert "Pipeline: `research-brief`" in result.stdout
    assert "JSON sidecar: `output/RUN_AUDIT.json`" in result.stdout
    assert "Current checkpoint: `C3`" in result.stdout
    assert "Phase: `complete_candidate`" in result.stdout
    assert f"Target artifacts: {len(spec.target_artifacts)} present / 0 missing" in result.stdout
    assert "DONE: 1" in result.stdout
    assert "Manifests: 1" in result.stdout
    assert "No harness issues" in result.stdout
    assert "INCOMPLETE" in audit_path.read_text(encoding="utf-8")
    audit_payload = json.loads(audit_json_path.read_text(encoding="utf-8"))
    assert audit_payload["schema"] == "run-audit.v2"
    assert audit_payload["pipeline"] == "research-brief"
    assert audit_payload["verdict"] == "INCOMPLETE"
    assert audit_payload["run_state"]["phase"] == "complete_candidate"
    assert audit_payload["run_state"]["target_artifacts_missing"] == 0
    assert audit_payload["run_state"]["unit_output_manifest_count"] == 1
    assert audit_payload["unit_status"] == {"DONE": 1}
    assert audit_payload["unit_output_manifests"]["count"] == 1
    assert validate_run_audit_payload(audit_payload) == []


def test_run_audit_projects_latest_template_residue_evaluation(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U109",
                "title": "Audit draft",
                "skill": "pipeline-auditor",
                "owner": "CODEX",
                "outputs": (
                    "output/AUDIT_REPORT.md;"
                    "output/TEMPLATE_RESIDUE_SCORECARD.json"
                ),
                "status": "BLOCKED",
            }
        ],
    )
    (workspace / "PIPELINE.lock.md").write_text(
        "pipeline: pipelines/arxiv-survey.pipeline.md\n",
        encoding="utf-8",
    )
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    record_evaluation(
        workspace=workspace,
        attempt_id="attempt_residue",
        unit_id="U109",
        skill="pipeline-auditor",
        scorecard_path="output/TEMPLATE_RESIDUE_SCORECARD.json",
        payload={
            "schema": "template-residue-scorecard.v1",
            "workflow": "arxiv-survey",
            "verdict": "FAIL",
            "score": 50,
            "pass_score": 100,
            "dimensions": [
                {
                    "id": "template_residue_limit",
                    "status": "FAIL",
                    "matched_sentence_count": 96,
                    "sentence_count": 140,
                    "matched_sentence_ratio": 0.685714,
                    "max_ratio": 0.1,
                    "template_asset_count": 5,
                },
                {
                    "id": "template_source_provenance",
                    "status": "PASS",
                    "selection_status": "PASS",
                    "implementation_lock_status": "PASS",
                    "selected_assets": [
                        "asset-a.json",
                        "asset-b.json",
                        "asset-c.json",
                        "asset-d.json",
                        "asset-e.json",
                    ],
                    "drifted_skills": [],
                },
            ],
            "failures": [],
        },
    )

    _, payload = build_run_audit_payload(workspace=workspace, repo_root=REPO_ROOT)

    observation = payload["quality_observations"]["template_residue"]
    assert observation == {
        "status": "RECORDED",
        "evaluator_id": "template-residue-scorecard.v1",
        "evaluation_id": observation["evaluation_id"],
        "attempt_id": "attempt_residue",
        "unit_id": "U109",
        "verdict": "FAIL",
        "scorecard_path": "output/TEMPLATE_RESIDUE_SCORECARD.json",
        "matched_sentence_count": 96,
        "sentence_count": 140,
        "matched_sentence_ratio": 0.685714,
        "max_ratio": 0.1,
        "template_asset_count": 5,
        "selection_status": "PASS",
        "implementation_lock_status": "PASS",
        "selected_assets": [
            "asset-a.json",
            "asset-b.json",
            "asset-c.json",
            "asset-d.json",
            "asset-e.json",
        ],
        "drifted_skills": [],
    }
    assert validate_run_audit_payload(payload) == []
    report = render_run_audit_report(payload)
    assert "Whole-draft literal residue: 96/140 = 68.6%" in report
    assert "Writer implementation lock: `PASS`" in report


def test_run_audit_reports_malformed_evaluation_ledger_without_crashing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U109",
                "title": "Audit draft",
                "skill": "pipeline-auditor",
                "owner": "CODEX",
                "outputs": "output/AUDIT_REPORT.md",
                "status": "BLOCKED",
            }
        ],
    )
    (workspace / "PIPELINE.lock.md").write_text(
        "pipeline: pipelines/arxiv-survey.pipeline.md\n",
        encoding="utf-8",
    )
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    initialize_run_state(
        workspace=workspace,
        repo_root=REPO_ROOT,
        pipeline_path=REPO_ROOT / "pipelines" / "arxiv-survey.pipeline.md",
        units_template="",
    )
    ledger = workspace / ".harness" / "evaluations" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("{not-json}\n", encoding="utf-8")

    exit_code, payload = build_run_audit_payload(
        workspace=workspace,
        repo_root=REPO_ROOT,
    )

    assert exit_code == 2
    assert payload["quality_observations"]["template_residue"]["status"] == (
        "UNAVAILABLE"
    )
    assert any(
        issue["code"] == "malformed_ledger_record"
        for issue in payload["harness_issues"]
    )


def test_run_audit_rejects_contradictory_template_residue_evaluation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U109",
                "title": "Audit draft",
                "skill": "pipeline-auditor",
                "owner": "CODEX",
                "outputs": "output/TEMPLATE_RESIDUE_SCORECARD.json",
                "status": "BLOCKED",
            }
        ],
    )
    (workspace / "PIPELINE.lock.md").write_text(
        "pipeline: pipelines/arxiv-survey.pipeline.md\n",
        encoding="utf-8",
    )
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    record_evaluation(
        workspace=workspace,
        attempt_id="attempt_contradictory",
        unit_id="U109",
        skill="pipeline-auditor",
        scorecard_path="output/TEMPLATE_RESIDUE_SCORECARD.json",
        payload={
            "schema": "template-residue-scorecard.v1",
            "workflow": "arxiv-survey",
            "verdict": "PASS",
            "score": 100,
            "pass_score": 100,
            "dimensions": [
                {
                    "id": "template_residue_limit",
                    "status": "PASS",
                    "matched_sentence_count": 96,
                    "sentence_count": 140,
                    "matched_sentence_ratio": 0.685714,
                    "max_ratio": 0.1,
                    "template_asset_count": 1,
                },
                {
                    "id": "template_source_provenance",
                    "status": "PASS",
                    "selection_status": "PASS",
                    "implementation_lock_status": "PASS",
                    "selected_assets": ["asset-a.json"],
                    "drifted_skills": [],
                },
            ],
            "failures": [],
        },
    )

    exit_code, payload = build_run_audit_payload(
        workspace=workspace,
        repo_root=REPO_ROOT,
    )

    observation = payload["quality_observations"]["template_residue"]
    assert exit_code == 2
    assert observation["status"] == "INVALID"
    assert "template_residue_limit.status contradicts its metrics" in observation[
        "invalid_reasons"
    ]
    assert any(
        issue["code"] == "invalid_template_residue_evaluation"
        for issue in payload["harness_issues"]
    )


def test_run_audit_fails_closed_without_pipeline_lock(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": "U001",
                "title": "Unbound result",
                "skill": "snapshot-writer",
                "owner": "CODEX",
                "outputs": "output/SNAPSHOT.md",
                "status": "TODO",
            }
        ],
    )
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")

    result = run_command("scripts/pipeline.py", "audit", "--workspace", str(workspace), "--write")

    assert result.returncode == 2
    payload = json.loads((workspace / "output" / "RUN_AUDIT.json").read_text(encoding="utf-8"))
    assert payload["verdict"] == "ATTENTION"
    assert payload["pipeline"] == ""
    assert "missing_pipeline_lock" in {issue["code"] for issue in payload["harness_issues"]}


def test_in_progress_audit_cannot_be_promoted_by_composed_reports(tmp_path: Path) -> None:
    import tooling.harness as harness

    workspace = tmp_path / "ws"
    spec = PipelineSpec.load(REPO_ROOT / "pipelines" / "research-brief.pipeline.md")
    required_skills = spec.quality_contract["completion_policy"]["required_checks"]
    write_units(
        workspace / "UNITS.csv",
        [
            {
                "unit_id": f"U{index:03d}",
                "title": f"Pending {skill}",
                "skill": skill,
                "owner": "CODEX",
                "outputs": f"output/{skill}.md",
                "status": "TODO",
            }
            for index, skill in enumerate(required_skills, start=1)
        ],
    )
    (workspace / "PIPELINE.lock.md").write_text(
        "pipeline: pipelines/research-brief.pipeline.md\n"
        "units_template: templates/UNITS.research-brief.csv\n",
        encoding="utf-8",
    )
    for relpath in spec.target_artifacts:
        path = workspace / relpath
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relpath}\n", encoding="utf-8")

    inspection = harness.build_harness_inspection(
        workspace=workspace,
        repo_root=REPO_ROOT,
    )

    assert inspection.audit_exit_code == 2
    assert inspection.audit["verdict"] == "IN_PROGRESS"
    assert inspection.improvement_exit_code == 2
    assert inspection.improvement["verdict"] == "ATTENTION"
    assert inspection.artifact_pack_exit_code == 2
    assert inspection.artifact_pack["verdict"] == "ATTENTION"


def test_run_audit_summarizes_verified_workflow_acceptance(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from tooling import quality_gate
    from tooling.completion import commit_unit_completion

    workspace = tmp_path / "ws"
    spec = PipelineSpec.load(REPO_ROOT / "pipelines" / "research-brief.pipeline.md")
    required_skills = sorted(spec.quality_contract["completion_policy"]["required_checks"])
    rows: list[dict[str, str]] = []
    for index, skill in enumerate(required_skills, start=1):
        unit_id = f"U{index:03d}"
        output_relpath = f"output/{skill}.md"
        rows.append(
            {
                "unit_id": unit_id,
                "title": f"Verify {skill}",
                "skill": skill,
                "owner": "CODEX",
                "outputs": output_relpath,
                "status": "TODO",
            }
        )
        output = workspace / output_relpath
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{skill} accepted\n", encoding="utf-8")
    write_units(workspace / "UNITS.csv", rows)
    (workspace / "PIPELINE.lock.md").write_text(
        "pipeline: pipelines/research-brief.pipeline.md\n"
        "units_template: templates/UNITS.research-brief.csv\n"
        "locked_at: 2026-07-22\n",
        encoding="utf-8",
    )
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    monkeypatch.setattr(quality_gate, "check_completion_acceptance", lambda **_: [])
    for row in rows:
        result = commit_unit_completion(
            workspace=workspace,
            repo_root=REPO_ROOT,
            unit_id=row["unit_id"],
            message="Workflow acceptance passed",
        )
        assert result.status == "DONE"
    for relpath in spec.target_artifacts:
        path = workspace / relpath
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{relpath}\n", encoding="utf-8")

    result = run_command("scripts/pipeline.py", "audit", "--workspace", str(workspace), "--write")

    assert result.returncode == 0, result.stdout
    payload = json.loads((workspace / "output" / "RUN_AUDIT.json").read_text(encoding="utf-8"))
    acceptance = payload["workflow_acceptance"]
    assert acceptance["status"] == "PASS"
    assert acceptance["required_skill_count"] == len(required_skills)
    assert acceptance["required_unit_count"] == len(required_skills)
    assert acceptance["verified_unit_count"] == len(required_skills)
    assert acceptance["unverified_done_unit_count"] == 0
    assert acceptance["uncovered_required_skills"] == []
    kernel_lock = payload["ledger_integrity"]["kernel_lock"]
    assert kernel_lock["status"] == "PASS"
    assert kernel_lock["matched_file_count"] == kernel_lock["current_file_count"]
    assert "## Workflow acceptance" in result.stdout
    assert "Coverage status: `PASS`" in result.stdout
    assert "Harness Kernel lock: `PASS`" in result.stdout
    assert validate_run_audit_payload(payload) == []


def test_run_audit_payload_validator_reports_schema_drift() -> None:
    payload = {
        "schema": "run-audit.v3",
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
        "attempts": {
            "started": "1",
            "finished": 0,
            "open": 0,
            "retry_units": 0,
            "extra_attempts": 0,
            "by_status": {},
            "by_execution_mode": {},
            "process_metrics": {
                "measured_attempts": 0,
                "total_elapsed_ms": "unknown",
                "mean_elapsed_ms": None,
                "max_elapsed_ms": None,
                "stdout_chars": 0,
                "stderr_chars": 0,
            },
        },
        "ledger_integrity": {
            "enabled": True,
            "run_id": "run_test",
            "issue_count": 0,
            "ledger_record_counts": {},
            "issues": [],
            "kernel_lock": {
                "status": "UNKNOWN",
                "locked_file_count": -1,
                "current_file_count": True,
                "matched_file_count": 3,
                "missing_paths": "tooling/run_state.py",
                "unexpected_paths": [1],
                "drifted_paths": [],
            },
            "compatibility": {
                "mode": 1,
                "recorded_completion_protocol": "unversioned",
                "current_completion_protocol": "recoverable-provenance.v2",
                "legacy_evidence_gap_codes": ["done_without_manifest", 2],
                "interpretation": "historical",
            },
        },
        "harness_issues": [],
        "remediation_summary": {},
        "recent_reports": [],
        "verdict": "PASS",
        "exit_code": 0,
    }

    issues = validate_run_audit_payload(payload)

    assert "`schema` must be `run-audit.v2`" in issues
    assert "`schema` must be one of: run-audit.v1, run-audit.v2" in issues
    assert "`run_ledger_files.PIPELINE.lock.md` is missing" in issues
    assert "`run_ledger_files.UNITS.csv` must be a boolean" in issues
    assert "`run_state.phase` must be a string" in issues
    assert "`run_state.units_total` must be an integer" in issues
    assert "`run_state.active_units` must be an integer" in issues
    assert "`unit_status.DONE` must be an integer" in issues
    assert "`attempts.started` must be an integer" in issues
    assert "`attempts.process_metrics.total_elapsed_ms` must be a number" in issues
    assert "`ledger_integrity.compatibility.mode` must be a string" in issues
    assert "`ledger_integrity.compatibility.legacy_evidence_gap_codes[1]` must be a string" in issues
    assert "`ledger_integrity.kernel_lock.status` must be one of: DRIFT, NOT_APPLICABLE, PASS" in issues
    assert "`ledger_integrity.kernel_lock.locked_file_count` must be a non-negative integer" in issues
    assert "`ledger_integrity.kernel_lock.current_file_count` must be a non-negative integer" in issues
    assert "`ledger_integrity.kernel_lock.missing_paths` must be a list of strings" in issues
    assert "`ledger_integrity.kernel_lock.unexpected_paths` must be a list of strings" in issues


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
    assert "uv run python scripts/pipeline.py audit --workspace" in result.stdout
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
    assert result.returncode == 2, result.stdout
    assert report_path.exists()
    assert json_path.exists()
    assert excerpt_md_path.exists()
    assert excerpt_tsv_path.exists()
    assert "Artifact pack" in result.stdout
    assert "target_artifact" in result.stdout
    assert "run_ledger" in result.stdout
    assert "unit_manifest" in result.stdout
    assert (
        f"Run state: `complete_candidate`; {len(spec.target_artifacts)} target artifacts present, "
        "0 missing; 0 errors"
    ) in result.stdout
    assert "ARTIFACT_PACK_EXCERPT.md" in result.stdout
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "artifact-pack.v1"
    assert payload["verdict"] == "ATTENTION"
    assert payload["source_reports"]["run_audit"]["schema"] == "run-audit.v2"
    assert payload["source_reports"]["run_audit"]["verdict"] == "INCOMPLETE"
    assert payload["source_reports"]["run_audit"]["run_state"]["phase"] == "complete_candidate"
    assert payload["source_reports"]["run_audit"]["run_state"]["target_artifacts_missing"] == 0
    assert payload["summary"]["by_category"]["target_artifact"]["missing"] == 0
    categories = {record["category"] for record in payload["artifacts"]}
    assert {"target_artifact", "unit_output", "run_ledger", "harness_report", "unit_manifest"}.issubset(categories)
    assert any(
        record["category"] == "run_ledger" and record["path"] == ".harness/decisions.jsonl"
        for record in payload["artifacts"]
    )
    excerpt_md = excerpt_md_path.read_text(encoding="utf-8")
    excerpt_tsv = excerpt_tsv_path.read_text(encoding="utf-8")
    assert "# Artifact Pack Excerpt" in excerpt_md
    assert "artifact-pack.v1" in excerpt_md
    assert "| `target_artifact` | `output/SNAPSHOT.md` | true | final deliverable or declared target artifact |" in excerpt_md
    assert "category\tpath\texists\trole" in excerpt_tsv
    assert "target_artifact\toutput/SNAPSHOT.md\ttrue\tfinal deliverable or declared target artifact" in excerpt_tsv
    assert validate_artifact_pack_payload(payload) == []


def test_harness_inspection_uses_one_shared_workspace_snapshot(monkeypatch, tmp_path: Path) -> None:
    import tooling.harness as harness

    workspace = tmp_path / "ws"
    write_units(workspace / "UNITS.csv", [])
    calls = {"snapshot": 0}
    original_snapshot = harness._collect_workspace_inspection_snapshot

    def counted_snapshot(*, workspace: Path, repo_root: Path):
        calls["snapshot"] += 1
        return original_snapshot(workspace=workspace, repo_root=repo_root)

    monkeypatch.setattr(harness, "_collect_workspace_inspection_snapshot", counted_snapshot)

    inspection = harness.build_harness_inspection(workspace=workspace, repo_root=REPO_ROOT)

    assert calls == {"snapshot": 1}
    assert inspection.doctor["schema"] == "doctor-report.v1"
    assert inspection.audit["schema"] == "run-audit.v2"
    assert inspection.improvement["schema"] == "improvement-report.v1"
    assert inspection.artifact_pack["schema"] == "artifact-pack.v1"
    assert {
        inspection.doctor["generated_at"],
        inspection.audit["generated_at"],
        inspection.improvement["generated_at"],
        inspection.artifact_pack["generated_at"],
    } == {inspection.doctor["generated_at"]}


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
        attempts={
            "started": 2,
            "finished": 2,
            "open": 0,
            "retry_units": 1,
            "extra_attempts": 1,
            "by_status": {"failed": 1, "succeeded": 1},
            "by_execution_mode": {"script": 2},
            "process_metrics": {
                "measured_attempts": 2,
                "total_elapsed_ms": 120.0,
                "mean_elapsed_ms": 60.0,
                "max_elapsed_ms": 80.0,
                "stdout_chars": 200,
                "stderr_chars": 20,
            },
        },
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
        attempts={
            "started": 3,
            "finished": 3,
            "open": 0,
            "retry_units": 0,
            "extra_attempts": 0,
            "by_status": {"succeeded": 3},
            "by_execution_mode": {"script": 3},
            "process_metrics": {
                "measured_attempts": 3,
                "total_elapsed_ms": 150.0,
                "mean_elapsed_ms": 50.0,
                "max_elapsed_ms": 70.0,
                "stdout_chars": 240,
                "stderr_chars": 0,
            },
        },
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
    assert "Extra Attempts: 1 -> 0 (-1)" in result.stdout
    assert "Mean adapter elapsed ms: 60.0 -> 50.0 (-10.0)" in result.stdout
    assert "No comparison issues" in result.stdout
    assert diff_json_path.exists()
    diff_payload = json.loads(diff_json_path.read_text(encoding="utf-8"))
    assert diff_payload["schema"] == "run-audit-diff.v1"
    assert diff_payload["verdict"] == "PASS"
    assert diff_payload["manifest_counts"] == {"before": 0, "after": 1, "delta": 1}
    assert diff_payload["attempt_comparison"]["available"] is True
    assert diff_payload["attempt_comparison"]["counters"]["extra_attempts"]["delta"] == -1
    assert diff_payload["attempt_comparison"]["process_metrics"]["mean_elapsed_ms"]["delta"] == -10.0
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


def test_audit_diff_keeps_legacy_payloads_without_attempt_summaries_comparable(tmp_path: Path) -> None:
    before_payload = run_audit_payload(
        workspace="/tmp/old",
        unit_status={"DONE": 1},
        target_artifacts=[{"path": "output/SNAPSHOT.md", "exists": True}],
        manifest_count=0,
        issues=[],
        verdict="PASS",
    )
    after_payload = run_audit_payload(
        workspace="/tmp/new",
        unit_status={"DONE": 1},
        target_artifacts=[{"path": "output/SNAPSHOT.md", "exists": True}],
        manifest_count=1,
        issues=[],
        verdict="PASS",
        attempts={
            "started": 1,
            "finished": 1,
            "open": 0,
            "retry_units": 0,
            "extra_attempts": 0,
            "by_status": {"succeeded": 1},
            "by_execution_mode": {"script": 1},
            "process_metrics": {
                "measured_attempts": 1,
                "total_elapsed_ms": 40.0,
                "mean_elapsed_ms": 40.0,
                "max_elapsed_ms": 40.0,
                "stdout_chars": 20,
                "stderr_chars": 0,
            },
        },
    )

    exit_code, payload = build_run_audit_diff_payload(
        before_path=tmp_path / "before.json",
        before_payload=before_payload,
        after_path=tmp_path / "after.json",
        after_payload=after_payload,
    )

    assert exit_code == 0
    assert payload["attempt_comparison"] == {
        "available": False,
        "counters": {},
        "process_metrics": {},
        "note": "One or both audits predate Attempt summaries.",
    }
    assert validate_run_audit_diff_payload(payload) == []
    assert "Unavailable: One or both audits predate Attempt summaries." in render_run_audit_diff_report(payload)


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
        "attempt_comparison": {
            "available": "yes",
            "note": 123,
            "counters": {
                "extra_attempts": {"before": 1, "after": 0, "delta": "-1"},
                "unsupported": {"before": 0, "after": 0, "delta": 0},
            },
            "process_metrics": {
                "mean_elapsed_ms": {"before": 10.0, "after": False, "delta": None},
            },
        },
        "comparison_issues": [123],
        "verdict": "PASS",
        "exit_code": 0,
    }

    issues = validate_run_audit_diff_payload(payload)

    assert "`schema` must be `run-audit-diff.v1`" in issues
    assert "`unit_status_delta.DONE` must be an integer" in issues
    assert "`target_artifact_changes[0].before_exists` must be a boolean or null" in issues
    assert "`manifest_counts.delta` must be an integer" in issues
    assert "`attempt_comparison.available` must be a boolean" in issues
    assert "`attempt_comparison.note` must be a string" in issues
    assert "`attempt_comparison.counters.extra_attempts.delta` must be an integer or null" in issues
    assert "`attempt_comparison.counters.unsupported` is not a supported counter" in issues
    assert "`attempt_comparison.process_metrics.mean_elapsed_ms.after` must be a number or null" in issues
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

    manifest_paths = list((workspace / "output" / "unit_logs").glob("U001.demo-skill.*.manifest.json"))
    assert result.status == "DONE"
    assert len(manifest_paths) == 1
    manifest_path = manifest_paths[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["unit_id"] == "U001"
    assert manifest["run_id"].startswith("run_")
    assert manifest["attempt_id"].startswith("attempt_")
    assert manifest["skill"] == "demo-skill"
    assert manifest["exit_code"] == 0
    assert manifest["outputs"][0]["path"] == "output/demo.md"
    assert manifest["outputs"][0]["exists"] is True
    assert manifest["outputs"][0]["sha256"]
    assert manifest["implementation"]["skill"]["sha256"]
    artifact_records = [
        json.loads(line)
        for line in (workspace / ".harness" / "artifacts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    demo_artifact = next(record for record in artifact_records if record["path"] == "output/demo.md")
    assert demo_artifact["attempt_id"] == manifest["attempt_id"]
    assert demo_artifact["sha256"] == manifest["outputs"][0]["sha256"]

    script_path.write_text(script_path.read_text(encoding="utf-8") + "# changed after completion\n", encoding="utf-8")
    exit_code, doctor = build_doctor_payload(workspace=workspace, repo_root=repo_root)
    assert exit_code == 2
    assert "stale_done_implementation" in {issue["code"] for issue in doctor["harness_issues"]}
