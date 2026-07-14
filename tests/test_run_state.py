from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tooling.executor import run_one_unit
from tooling.harness import build_improvement_payload, validate_improvement_payload


REPO_ROOT = Path(__file__).resolve().parents[1]
UNIT_FIELDS = [
    "unit_id",
    "title",
    "type",
    "skill",
    "inputs",
    "outputs",
    "acceptance",
    "checkpoint",
    "status",
    "depends_on",
    "owner",
]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_units(
    path: Path,
    *,
    status: str = "TODO",
    skill: str = "skill-without-script",
    outputs: str = "output/result.md",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=UNIT_FIELDS)
        writer.writeheader()
        writer.writerow(
            {
                "unit_id": "U010",
                "title": "Demonstrate attempt history",
                "type": "TEST",
                "skill": skill,
                "outputs": outputs,
                "checkpoint": "C1",
                "status": status,
                "owner": "CODEX",
            }
        )


def test_init_creates_pinned_machine_readable_run_ledger(tmp_path: Path) -> None:
    workspace = tmp_path / "run"

    result = _run(
        "scripts/pipeline.py",
        "init",
        "--workspace",
        str(workspace),
        "--pipeline",
        "research-brief",
        "--goal",
        "produce a focused robot adaptation briefing",
    )

    assert result.returncode == 0, result.stderr or result.stdout
    harness = workspace / ".harness"
    required = (
        "goal.json",
        "run.json",
        "harness.lock.json",
        "events.jsonl",
        "attempts.jsonl",
        "decisions.jsonl",
        "artifacts.jsonl",
        "failures/ledger.jsonl",
        "evaluations/ledger.jsonl",
        "plan/planned.json",
        "plan/effective.json",
    )
    assert [rel for rel in required if not (harness / rel).exists()] == []

    run = json.loads((harness / "run.json").read_text(encoding="utf-8"))
    goal = json.loads((harness / "goal.json").read_text(encoding="utf-8"))
    lock = json.loads((harness / "harness.lock.json").read_text(encoding="utf-8"))
    events = _jsonl(harness / "events.jsonl")

    assert run["schema"] == "run-state.v1"
    assert run["run_id"].startswith("run_")
    assert run["goal_id"].startswith("goal_")
    assert run["workflow"] == "research-brief"
    assert goal["request"] == "produce a focused robot adaptation briefing"
    assert goal["schema"] == "goal-spec.v2"
    assert goal["constraints"] == {}
    assert goal["success_criteria"]["required_artifacts"] == goal["target_artifacts"]
    assert lock["schema"] == "harness-lock.v1"
    assert len(lock["repository"]["revision"]) == 40
    assert lock["pipeline"]["sha256"]
    assert lock["units_template"]["sha256"]
    assert lock["skills"]
    assert all(record.get("script_sha256") for record in lock["skills"].values())
    assert all(record.get("implementation_sha256") for record in lock["skills"].values())
    assert all(record.get("implementation_file_count", 0) > 0 for record in lock["skills"].values())
    assert lock["kernel"]["tooling/run_state.py"]
    assert lock["kernel"]["tooling/scorecards.py"]
    assert lock["kernel"]["tooling/quality_checks/survey_writing.py"]
    assert lock["kernel"]["tooling/brief_evaluation.py"]
    assert lock["kernel"]["tooling/review_evaluation.py"]
    assert [event["type"] for event in events] == ["run.created", "run.planned"]
    assert [event["seq"] for event in events] == [1, 2]


def test_harness_lock_pins_skill_assets_with_the_executable_implementation(tmp_path: Path) -> None:
    workspace = tmp_path / "idea-run"

    result = _run(
        "scripts/pipeline.py",
        "init",
        "--workspace",
        str(workspace),
        "--pipeline",
        "idea-brainstorm",
    )

    assert result.returncode == 0, result.stderr or result.stdout
    lock = json.loads((workspace / ".harness" / "harness.lock.json").read_text(encoding="utf-8"))
    idea_brief = lock["skills"]["idea-brief"]
    assert idea_brief["implementation_path"] == ".codex/skills/idea-brief"
    assert idea_brief["implementation_file_count"] >= 3
    assert len(idea_brief["implementation_sha256"]) == 64


def test_invalid_declared_scorecard_blocks_success_and_is_not_recorded(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    workspace = tmp_path / "run"
    skill = "invalid-scorecard-skill"
    scorecard_rel = "output/INVALID_SCORECARD.json"
    _write_units(workspace / "UNITS.csv", skill=skill, outputs=scorecard_rel)
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")

    script = repo_root / ".codex" / "skills" / skill / "scripts" / "run.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        "\n".join(
            [
                "import argparse",
                "import json",
                "from pathlib import Path",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--workspace', required=True)",
                "parser.add_argument('--unit-id')",
                "parser.add_argument('--inputs')",
                "parser.add_argument('--outputs', required=True)",
                "parser.add_argument('--checkpoint')",
                "args = parser.parse_args()",
                "path = Path(args.workspace) / args.outputs.split(';')[0]",
                "path.parent.mkdir(parents=True, exist_ok=True)",
                "path.write_text(json.dumps({'schema': 'invalid.v1', 'verdict': 'PASS', 'score': True, 'pass_score': 'eighty'}), encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_one_unit(workspace=workspace, repo_root=repo_root, strict=True)

    assert result.status == "BLOCKED"
    assert "is invalid" in result.message
    assert _jsonl(workspace / ".harness" / "evaluations" / "ledger.jsonl") == []
    failures = _jsonl(workspace / ".harness" / "failures" / "ledger.jsonl")
    assert failures[-1]["failure_type"] == "semantic_quality_gate_failed"


def test_retries_preserve_attempt_and_failure_history(tmp_path: Path) -> None:
    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")

    first = run_one_unit(workspace=workspace, repo_root=REPO_ROOT)
    second = run_one_unit(workspace=workspace, repo_root=REPO_ROOT)

    assert first.status == "BLOCKED"
    assert second.status == "BLOCKED"
    attempts = _jsonl(workspace / ".harness" / "attempts.jsonl")
    starts = [record for record in attempts if record["record_type"] == "started"]
    finishes = [record for record in attempts if record["record_type"] == "finished"]
    failures = _jsonl(workspace / ".harness" / "failures" / "ledger.jsonl")
    assert len(starts) == 2
    assert len(finishes) == 2
    assert starts[0]["attempt_id"] != starts[1]["attempt_id"]
    assert {record["status"] for record in finishes} == {"FAILED_TERMINAL"}
    assert len(failures) == 2
    assert {record["failure_type"] for record in failures} == {"missing_skill_adapter"}

    exit_code, improvement = build_improvement_payload(workspace=workspace, repo_root=REPO_ROOT)
    failure_suggestions = [
        item for item in improvement["suggestions"] if item["source_report"] == "failure_ledger"
    ]
    assert exit_code == 2
    assert improvement["source_reports"]["failure_ledger"]["record_count"] == 2
    assert len(failure_suggestions) == 1
    assert "missing_skill_adapter" in failure_suggestions[0]["evidence"]
    assert validate_improvement_payload(improvement) == []


def test_stale_doing_recovery_records_interrupted_attempt(tmp_path: Path) -> None:
    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv", status="DOING")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")

    result = run_one_unit(workspace=workspace, repo_root=REPO_ROOT)

    assert result.status == "BLOCKED"
    events = _jsonl(workspace / ".harness" / "events.jsonl")
    assert "unit.attempt.interrupted" in {record["type"] for record in events}


def test_successful_retry_resolves_open_failure_records(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")

    script = repo_root / ".codex" / "skills" / "skill-without-script" / "scripts" / "run.py"
    script.parent.mkdir(parents=True)
    script.write_text("import sys\nsys.exit(7)\n", encoding="utf-8")
    failed = run_one_unit(workspace=workspace, repo_root=repo_root)
    assert failed.status == "BLOCKED"

    script.write_text(
        "\n".join(
            [
                "import argparse",
                "from pathlib import Path",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--workspace', required=True)",
                "parser.add_argument('--unit-id')",
                "parser.add_argument('--inputs')",
                "parser.add_argument('--outputs', required=True)",
                "parser.add_argument('--checkpoint')",
                "args = parser.parse_args()",
                "path = Path(args.workspace) / args.outputs.split(';')[0]",
                "path.parent.mkdir(parents=True, exist_ok=True)",
                "path.write_text('recovered output\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    succeeded = run_one_unit(workspace=workspace, repo_root=repo_root)
    assert succeeded.status == "DONE"
    ledger = _jsonl(workspace / ".harness" / "failures" / "ledger.jsonl")
    assert [record["status"] for record in ledger] == ["open", "resolved"]
    manifests = list((workspace / "output" / "unit_logs").glob("U010.skill-without-script.*.manifest.json"))
    assert len(manifests) == 2
    manifest_attempts = {
        json.loads(path.read_text(encoding="utf-8"))["attempt_id"] for path in manifests
    }
    assert len(manifest_attempts) == 2

    _, improvement = build_improvement_payload(workspace=workspace, repo_root=repo_root)
    assert improvement["source_reports"]["failure_ledger"]["record_count"] == 0
    assert improvement["source_reports"]["failure_ledger"]["resolved_count"] == 1
    assert improvement["repair_history"]["entries"][0]["status"] == "resolved"
    assert [item for item in improvement["suggestions"] if item["source_report"] == "failure_ledger"] == []


def test_manual_final_status_is_recorded_as_decision_and_completion(tmp_path: Path) -> None:
    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")

    result = _run(
        "scripts/pipeline.py",
        "mark",
        "--workspace",
        str(workspace),
        "--unit-id",
        "U010",
        "--status",
        "DONE",
        "--note",
        "manual semantic work completed",
    )

    assert result.returncode == 0, result.stderr or result.stdout
    run = json.loads((workspace / ".harness" / "run.json").read_text(encoding="utf-8"))
    decisions = _jsonl(workspace / ".harness" / "decisions.jsonl")
    events = _jsonl(workspace / ".harness" / "events.jsonl")
    assert run["state"] == "COMPLETED"
    assert decisions[-1]["decision"] == "TODO->DONE"
    assert events[-1]["type"] == "run.completed"


def test_product_cli_goal_create_maps_to_existing_workflow(tmp_path: Path) -> None:
    workspace = tmp_path / "product-run"

    result = _run(
        "-m",
        "tooling.product_cli",
        "goal",
        "create",
        "--topic",
        "robot adaptation",
        "--workflow",
        "research-brief",
        "--workspace",
        str(workspace),
    )

    assert result.returncode == 0, result.stderr or result.stdout
    goal = json.loads((workspace / ".harness" / "goal.json").read_text(encoding="utf-8"))
    assert goal["request"] == "robot adaptation"
    assert goal["workflow"] == "research-brief"
    assert "Workspace ready:" in result.stdout
    assert "uv run rh run start --workspace" in result.stdout

    status = _run("-m", "tooling.product_cli", "run", "status", "--workspace", str(workspace))
    assert status.returncode == 0, status.stderr or status.stdout
    assert "State: PLANNED" in status.stdout
    assert "Resume: uv run rh run resume --workspace" in status.stdout
    assert "scripts/pipeline.py" not in status.stdout


def test_product_status_does_not_create_a_missing_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "missing"

    result = _run("-m", "tooling.product_cli", "run", "status", "--workspace", str(workspace))

    assert result.returncode == 2
    assert "Workspace not found:" in result.stderr
    assert not workspace.exists()


def test_product_evidence_and_improve_commands_return_compact_summaries(tmp_path: Path) -> None:
    workspace = tmp_path / "product-run"
    created = _run(
        "-m",
        "tooling.product_cli",
        "goal",
        "create",
        "--topic",
        "robot adaptation",
        "--workflow",
        "paper-review",
        "--workspace",
        str(workspace),
    )
    assert created.returncode == 0, created.stderr or created.stdout

    evidence = _run("-m", "tooling.product_cli", "evidence", "inspect", "--workspace", str(workspace))
    improve = _run("-m", "tooling.product_cli", "improve", "diagnose", "--workspace", str(workspace))

    assert evidence.returncode == 2
    assert "Evidence: ATTENTION" in evidence.stdout
    assert "Targets:" in evidence.stdout
    assert "# Run audit" not in evidence.stdout
    assert improve.returncode == 2
    assert "Improve: ATTENTION" in improve.stdout
    assert "Open repairs:" in improve.stdout
    assert "# Improvement report" not in improve.stdout


def test_product_evidence_uses_latest_generic_evaluation(tmp_path: Path) -> None:
    from tooling.run_state import initialize_run_state, record_evaluation

    workspace = tmp_path / "product-evaluation"
    workspace.mkdir()
    (workspace / "UNITS.csv").write_text(
        ",".join(UNIT_FIELDS) + "\n",
        encoding="utf-8",
    )
    initialize_run_state(
        workspace=workspace,
        repo_root=REPO_ROOT,
        pipeline_path=REPO_ROOT / "pipelines" / "research-brief.pipeline.md",
        units_template="templates/UNITS.research-brief.csv",
        goal_text="robot adaptation briefing",
    )
    record_evaluation(
        workspace=workspace,
        attempt_id="attempt_test",
        unit_id="U055",
        skill="deliverable-selfloop",
        scorecard_path="output/BRIEF_SCORECARD.json",
        payload={
            "schema": "research-brief-scorecard.v1",
            "workflow": "research-brief",
            "verdict": "PASS",
            "score": 88,
            "pass_score": 80,
            "dimensions": [],
            "failures": [],
        },
    )

    evidence = _run("-m", "tooling.product_cli", "evidence", "inspect", "--workspace", str(workspace))

    assert "Scorecard: PASS 88/100 [research-brief]" in evidence.stdout
