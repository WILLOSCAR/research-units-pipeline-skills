from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tooling.executor import run_one_unit
from tooling.harness import build_improvement_payload, build_run_audit_payload, validate_improvement_payload


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
    from tooling.run_state import initialize_run_state, inspect_run_integrity, start_attempt

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    initialize_run_state(
        workspace=workspace,
        repo_root=REPO_ROOT,
        pipeline_path=None,
        units_template="",
    )
    start_attempt(
        workspace=workspace,
        repo_root=REPO_ROOT,
        unit_id="U010",
        skill="skill-without-script",
        inputs=(),
        execution_mode="process",
        owner_pid=999_999_999,
    )
    _write_units(workspace / "UNITS.csv", status="DOING")

    result = run_one_unit(workspace=workspace, repo_root=REPO_ROOT)

    assert result.status == "BLOCKED"
    events = _jsonl(workspace / ".harness" / "events.jsonl")
    assert "unit.attempt.interrupted" in {record["type"] for record in events}
    attempts = _jsonl(workspace / ".harness" / "attempts.jsonl")
    starts = {str(record["attempt_id"]): record for record in attempts if record["record_type"] == "started"}
    finishes = {str(record["attempt_id"]): record for record in attempts if record["record_type"] == "finished"}
    assert starts.keys() == finishes.keys()
    assert all(starts[attempt_id]["skill"] == finishes[attempt_id]["skill"] for attempt_id in starts)
    assert inspect_run_integrity(workspace)["issue_count"] == 0


def test_doctor_reports_doing_without_attempt_without_rewriting_it(tmp_path: Path) -> None:
    from tooling.harness import build_doctor_payload
    from tooling.run_state import initialize_run_state

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv", status="DOING")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    initialize_run_state(
        workspace=workspace,
        repo_root=REPO_ROOT,
        pipeline_path=None,
        units_template="",
    )

    exit_code, payload = build_doctor_payload(workspace=workspace, repo_root=REPO_ROOT)

    with (workspace / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        assert next(csv.DictReader(handle))["status"] == "DOING"
    assert not (workspace / ".harness" / "attempts.jsonl").read_text(encoding="utf-8").strip()
    assert exit_code == 2
    assert "doing_without_open_attempt" in {issue["code"] for issue in payload["harness_issues"]}


def test_doctor_reconciliation_recovers_stale_doing_before_reporting(tmp_path: Path) -> None:
    from tooling.harness import build_doctor_payload
    from tooling.run_state import initialize_run_state, start_attempt

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    initialize_run_state(
        workspace=workspace,
        repo_root=REPO_ROOT,
        pipeline_path=None,
        units_template="",
    )
    attempt_id = start_attempt(
        workspace=workspace,
        repo_root=REPO_ROOT,
        unit_id="U010",
        skill="skill-without-script",
        inputs=(),
        execution_mode="process",
        owner_pid=999_999_999,
    )
    _write_units(workspace / "UNITS.csv", status="DOING")

    _, payload = build_doctor_payload(workspace=workspace, repo_root=REPO_ROOT)

    with (workspace / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        assert next(csv.DictReader(handle))["status"] == "BLOCKED"
    finishes = {
        str(record["attempt_id"]): record
        for record in _jsonl(workspace / ".harness" / "attempts.jsonl")
        if record["record_type"] == "finished"
    }
    assert finishes[attempt_id]["status"] == "INTERRUPTED"
    assert payload["run_identity"]["state"] == "BLOCKED"


def test_reconciliation_repairs_attempt_started_before_event_append(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tooling.run_state as run_state

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    original_append_event = run_state._append_event

    def interrupt_started_event(**kwargs: object) -> dict[str, object]:
        if kwargs.get("event_type") == "unit.attempt.started":
            raise RuntimeError("simulated crash after Attempt start append")
        return original_append_event(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(run_state, "_append_event", interrupt_started_event)
    with pytest.raises(RuntimeError, match="simulated crash"):
        run_one_unit(workspace=workspace, repo_root=REPO_ROOT)
    monkeypatch.setattr(run_state, "_append_event", original_append_event)

    result = run_one_unit(workspace=workspace, repo_root=REPO_ROOT)

    assert result.status == "BLOCKED"
    events = _jsonl(workspace / ".harness" / "events.jsonl")
    attempts = _jsonl(workspace / ".harness" / "attempts.jsonl")
    first_attempt = str(attempts[0]["attempt_id"])
    assert any(
        event.get("attempt_id") == first_attempt
        and event.get("type") == "unit.attempt.started"
        and event.get("payload", {}).get("recovered") is True
        for event in events
    )
    assert run_state.inspect_run_integrity(workspace)["issue_count"] == 0


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


def test_manual_final_status_requires_outputs_and_commits_provenance(tmp_path: Path) -> None:
    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")

    rejected = _run(
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

    assert rejected.returncode == 2
    assert "Required outputs are missing" in (rejected.stderr or rejected.stdout)
    with (workspace / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        assert next(csv.DictReader(handle))["status"] == "BLOCKED"

    output = workspace / "output" / "result.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("verified manual result\n", encoding="utf-8")
    completed = _run(
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

    assert completed.returncode == 0, completed.stderr or completed.stdout
    run = json.loads((workspace / ".harness" / "run.json").read_text(encoding="utf-8"))
    decisions = _jsonl(workspace / ".harness" / "decisions.jsonl")
    attempts = _jsonl(workspace / ".harness" / "attempts.jsonl")
    artifacts = _jsonl(workspace / ".harness" / "artifacts.jsonl")
    events = _jsonl(workspace / ".harness" / "events.jsonl")
    manifests = list((workspace / "output" / "unit_logs").glob("U010.skill-without-script.*.manifest.json"))
    assert run["state"] == "COMPLETED"
    assert decisions[-1]["action"] == "unit.completion.accepted"
    assert decisions[-1]["decision"] == "BLOCKED->DONE"
    assert any(record["record_type"] == "finished" and record["status"] == "SUCCEEDED" for record in attempts)
    assert any(record["path"] == "output/result.md" for record in artifacts)
    assert len(manifests) == 2
    assert sum(
        json.loads(path.read_text(encoding="utf-8"))["status"] == "DONE" for path in manifests
    ) == 1
    assert "unit.completion.committed" in {event["type"] for event in events}


def test_manual_completion_resolves_missing_adapter_failure(tmp_path: Path) -> None:
    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")

    blocked = run_one_unit(workspace=workspace, repo_root=REPO_ROOT)
    assert blocked.status == "BLOCKED"
    assert "No executable script" in blocked.message

    output = workspace / "output" / "result.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("manual semantic result\n", encoding="utf-8")
    completed = _run(
        "scripts/pipeline.py",
        "mark",
        "--workspace",
        str(workspace),
        "--unit-id",
        "U010",
        "--status",
        "DONE",
        "--note",
        "manual Skill acceptance checked",
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    ledger = _jsonl(workspace / ".harness" / "failures" / "ledger.jsonl")
    opened = next(record for record in ledger if record.get("failure_type") == "missing_skill_adapter")
    resolved = next(record for record in ledger if record.get("record_type") == "resolved")
    assert resolved["failure_id"] == opened["failure_id"]
    assert resolved["verification"]["failure_type"] == "missing_skill_adapter"
    _, improvement = build_improvement_payload(workspace=workspace, repo_root=REPO_ROOT)
    assert [
        item
        for item in improvement["suggestions"]
        if item["source_report"] == "failure_ledger"
    ] == []


def test_maintainer_status_override_requires_reason(tmp_path: Path) -> None:
    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")

    rejected = _run(
        "scripts/pipeline.py",
        "mark",
        "--workspace",
        str(workspace),
        "--unit-id",
        "U010",
        "--status",
        "SKIP",
    )

    assert rejected.returncode == 2
    assert "Unit transitions require an explicit reason" in (rejected.stderr or rejected.stdout)
    with (workspace / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        assert next(csv.DictReader(handle))["status"] == "TODO"


def test_manual_doing_and_done_share_one_attempt(tmp_path: Path) -> None:
    from tooling.run_state import inspect_run_integrity

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")

    started = _run(
        "scripts/pipeline.py",
        "mark",
        "--workspace",
        str(workspace),
        "--unit-id",
        "U010",
        "--status",
        "DOING",
        "--note",
        "starting manual semantic work",
    )

    assert started.returncode == 0, started.stderr or started.stdout
    attempts = _jsonl(workspace / ".harness" / "attempts.jsonl")
    assert [record["record_type"] for record in attempts] == ["started"]
    attempt_id = str(attempts[0]["attempt_id"])

    inspected = _run("scripts/pipeline.py", "doctor", "--workspace", str(workspace))

    assert inspected.returncode == 0, inspected.stderr or inspected.stdout
    with (workspace / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        assert next(csv.DictReader(handle))["status"] == "DOING"
    assert [record["record_type"] for record in _jsonl(workspace / ".harness" / "attempts.jsonl")] == [
        "started"
    ]

    output = workspace / "output" / "result.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("verified manual result\n", encoding="utf-8")
    completed = _run(
        "scripts/pipeline.py",
        "mark",
        "--workspace",
        str(workspace),
        "--unit-id",
        "U010",
        "--status",
        "DONE",
        "--note",
        "acceptance checked",
        "--note",
        "acceptance checked",
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    attempts = _jsonl(workspace / ".harness" / "attempts.jsonl")
    assert [record["record_type"] for record in attempts] == ["started", "finished"]
    assert {str(record["attempt_id"]) for record in attempts} == {attempt_id}
    assert attempts[-1]["status"] == "SUCCEEDED"
    assert inspect_run_integrity(workspace)["issue_count"] == 0


def test_manual_doing_override_interrupts_open_attempt(tmp_path: Path) -> None:
    from tooling.run_state import inspect_run_integrity

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    started = _run(
        "scripts/pipeline.py",
        "mark",
        "--workspace",
        str(workspace),
        "--unit-id",
        "U010",
        "--status",
        "DOING",
        "--note",
        "starting manual semantic work",
    )
    assert started.returncode == 0, started.stderr or started.stdout

    reset = _run(
        "scripts/pipeline.py",
        "mark",
        "--workspace",
        str(workspace),
        "--unit-id",
        "U010",
        "--status",
        "TODO",
        "--note",
        "scope changed before acceptance",
    )

    assert reset.returncode == 0, reset.stderr or reset.stdout
    attempts = _jsonl(workspace / ".harness" / "attempts.jsonl")
    assert [record["record_type"] for record in attempts] == ["started", "finished"]
    assert attempts[-1]["status"] == "INTERRUPTED"
    assert attempts[-1]["message"] == "scope changed before acceptance"
    assert inspect_run_integrity(workspace)["issue_count"] == 0


def test_manual_completion_enforces_and_records_declared_scorecard(tmp_path: Path) -> None:
    workspace = tmp_path / "run"
    scorecard_path = workspace / "output" / "MANUAL_SCORECARD.json"
    _write_units(workspace / "UNITS.csv", outputs="output/MANUAL_SCORECARD.json")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    scorecard_path.parent.mkdir(parents=True, exist_ok=True)
    scorecard_path.write_text(
        json.dumps({"schema": "manual-scorecard.v1", "verdict": "PASS", "score": True}),
        encoding="utf-8",
    )

    invalid = _run(
        "scripts/pipeline.py",
        "mark",
        "--workspace",
        str(workspace),
        "--unit-id",
        "U010",
        "--status",
        "DONE",
        "--note",
        "acceptance checked",
    )

    assert invalid.returncode == 2
    assert "Scorecard `output/MANUAL_SCORECARD.json` is invalid" in (invalid.stderr or invalid.stdout)
    assert _jsonl(workspace / ".harness" / "evaluations" / "ledger.jsonl") == []

    scorecard_path.write_text(
        json.dumps(
            {
                "schema": "manual-scorecard.v1",
                "generated_at": "2026-07-15T00:00:00",
                "workflow": "manual-fixture",
                "verdict": "PASS",
                "score": 100,
                "pass_score": 80,
                "critical_dimensions": ["quality"],
                "failed_critical_dimensions": [],
                "counts": {"checks": 1},
                "dimensions": [
                    {
                        "id": "quality",
                        "label": "Quality",
                        "status": "PASS",
                        "score": 4,
                        "max_score": 4,
                        "evidence": "fixture passed",
                        "repair_surface": ["output/MANUAL_SCORECARD.json"],
                    }
                ],
                "failures": [],
                "limitations": [],
            }
        ),
        encoding="utf-8",
    )
    completed = _run(
        "scripts/pipeline.py",
        "mark",
        "--workspace",
        str(workspace),
        "--unit-id",
        "U010",
        "--status",
        "DONE",
        "--note",
        "scorecard acceptance checked",
    )

    evaluations = _jsonl(workspace / ".harness" / "evaluations" / "ledger.jsonl")
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert len(evaluations) == 1
    assert evaluations[0]["verdict"] == "PASS"
    assert evaluations[0]["attempt_id"]


def test_success_resolves_only_failure_types_verified_by_completion(tmp_path: Path) -> None:
    from tooling.run_state import finish_attempt, initialize_run_state, record_failure, start_attempt

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv", status="DOING")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    initialize_run_state(
        workspace=workspace,
        repo_root=REPO_ROOT,
        pipeline_path=None,
        units_template="",
    )
    failed_attempt = start_attempt(
        workspace=workspace,
        repo_root=REPO_ROOT,
        unit_id="U010",
        skill="skill-without-script",
        inputs=(),
    )
    for failure_type in ("script_failed", "operator_policy_rejected"):
        record_failure(
            workspace=workspace,
            unit_id="U010",
            attempt_id=failed_attempt,
            failure_type=failure_type,
            symptom=failure_type,
            causal_behavior="fixture",
            harness_mechanism="fixture",
            repair_surface=["fixture"],
        )
    finish_attempt(
        workspace=workspace,
        attempt_id=failed_attempt,
        unit_id="U010",
        skill="skill-without-script",
        status="FAILED_RETRYABLE",
        exit_code=7,
    )

    successful_attempt = start_attempt(
        workspace=workspace,
        repo_root=REPO_ROOT,
        unit_id="U010",
        skill="skill-without-script",
        inputs=(),
    )
    finish_attempt(
        workspace=workspace,
        attempt_id=successful_attempt,
        unit_id="U010",
        skill="skill-without-script",
        status="SUCCEEDED",
        exit_code=0,
        resolved_failure_types={"script_failed"},
    )

    ledger = _jsonl(workspace / ".harness" / "failures" / "ledger.jsonl")
    resolved_ids = {str(record["failure_id"]) for record in ledger if record["status"] == "resolved"}
    opened = {str(record["failure_type"]): str(record["failure_id"]) for record in ledger if record["status"] == "open"}
    assert resolved_ids == {opened["script_failed"]}
    assert opened["operator_policy_rejected"] not in resolved_ids


def test_manual_completion_does_not_resolve_unobserved_semantic_failure(tmp_path: Path) -> None:
    from tooling.run_state import finish_attempt, initialize_run_state, record_failure, start_attempt

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    output = workspace / "output" / "result.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("manual result without a scorecard\n", encoding="utf-8")
    initialize_run_state(
        workspace=workspace,
        repo_root=REPO_ROOT,
        pipeline_path=None,
        units_template="",
    )
    failed_attempt = start_attempt(
        workspace=workspace,
        repo_root=REPO_ROOT,
        unit_id="U010",
        skill="skill-without-script",
        inputs=(),
    )
    record_failure(
        workspace=workspace,
        unit_id="U010",
        attempt_id=failed_attempt,
        failure_type="semantic_quality_gate_failed",
        symptom="fixture semantic failure",
        causal_behavior="fixture",
        harness_mechanism="fixture",
        repair_surface=["output/MISSING_SCORECARD.json"],
    )
    finish_attempt(
        workspace=workspace,
        attempt_id=failed_attempt,
        unit_id="U010",
        skill="skill-without-script",
        status="FAILED_RETRYABLE",
        exit_code=2,
    )

    completed = _run(
        "scripts/pipeline.py",
        "mark",
        "--workspace",
        str(workspace),
        "--unit-id",
        "U010",
        "--status",
        "DONE",
        "--note",
        "manual completion does not reverify semantic failure",
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    ledger = _jsonl(workspace / ".harness" / "failures" / "ledger.jsonl")
    assert not [record for record in ledger if record["status"] == "resolved"]


def test_ensure_run_state_recovers_successful_doing_completion(tmp_path: Path) -> None:
    from tooling.harness import write_unit_manifest
    from tooling.run_state import ensure_run_state, finish_attempt, initialize_run_state, start_attempt

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv", status="DOING")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    output = workspace / "output" / "result.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("completed before projection crash\n", encoding="utf-8")
    initialize_run_state(
        workspace=workspace,
        repo_root=REPO_ROOT,
        pipeline_path=None,
        units_template="",
    )
    attempt_id = start_attempt(
        workspace=workspace,
        repo_root=REPO_ROOT,
        unit_id="U010",
        skill="skill-without-script",
        inputs=(),
    )
    write_unit_manifest(
        workspace=workspace,
        unit_id="U010",
        skill="skill-without-script",
        outputs=["output/result.md"],
        exit_code=0,
        status="DONE",
        attempt_id=attempt_id,
        repo_root=REPO_ROOT,
    )
    finish_attempt(
        workspace=workspace,
        attempt_id=attempt_id,
        unit_id="U010",
        skill="skill-without-script",
        status="SUCCEEDED",
        exit_code=0,
        outputs=["output/result.md"],
    )

    snapshot = ensure_run_state(workspace=workspace, repo_root=REPO_ROOT)

    with (workspace / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        assert next(csv.DictReader(handle))["status"] == "DONE"
    assert snapshot["state"] == "COMPLETED"
    assert "unit.completion.recovered" in {event["type"] for event in _jsonl(workspace / ".harness" / "events.jsonl")}


def test_doctor_reconciles_successful_completion_before_reporting(tmp_path: Path) -> None:
    from tooling.harness import build_doctor_payload, write_unit_manifest
    from tooling.run_state import finish_attempt, initialize_run_state, start_attempt

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv", status="DOING")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    output = workspace / "output" / "result.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("completed before doctor\n", encoding="utf-8")
    initialize_run_state(
        workspace=workspace,
        repo_root=REPO_ROOT,
        pipeline_path=None,
        units_template="",
    )
    attempt_id = start_attempt(
        workspace=workspace,
        repo_root=REPO_ROOT,
        unit_id="U010",
        skill="skill-without-script",
        inputs=(),
    )
    write_unit_manifest(
        workspace=workspace,
        unit_id="U010",
        skill="skill-without-script",
        outputs=["output/result.md"],
        exit_code=0,
        status="DONE",
        attempt_id=attempt_id,
        repo_root=REPO_ROOT,
    )
    finish_attempt(
        workspace=workspace,
        attempt_id=attempt_id,
        unit_id="U010",
        skill="skill-without-script",
        status="SUCCEEDED",
        exit_code=0,
        outputs=["output/result.md"],
    )

    exit_code, doctor = build_doctor_payload(workspace=workspace, repo_root=REPO_ROOT)

    assert exit_code == 0
    assert doctor["run_identity"]["state"] == "COMPLETED"
    assert doctor["unit_status"] == {"DONE": 1}


def test_reconciliation_closes_artifact_registered_open_attempt(tmp_path: Path) -> None:
    from tooling.common import UnitsTable
    from tooling.run_state import (
        ensure_run_state,
        initialize_run_state,
        inspect_run_integrity,
        register_artifacts,
        start_attempt,
    )

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv", status="DOING")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    output = workspace / "output" / "result.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("artifact registered before finish crash\n", encoding="utf-8")
    initialize_run_state(
        workspace=workspace,
        repo_root=REPO_ROOT,
        pipeline_path=None,
        units_template="",
    )
    attempt_id = start_attempt(
        workspace=workspace,
        repo_root=REPO_ROOT,
        unit_id="U010",
        skill="skill-without-script",
        inputs=(),
    )
    register_artifacts(
        workspace=workspace,
        run_id=json.loads((workspace / ".harness" / "run.json").read_text(encoding="utf-8"))["run_id"],
        attempt_id=attempt_id,
        unit_id="U010",
        outputs=["output/result.md"],
    )
    table = UnitsTable.load(workspace / "UNITS.csv")
    table.rows[0]["status"] = "BLOCKED"
    table.save(workspace / "UNITS.csv")

    snapshot = ensure_run_state(workspace=workspace, repo_root=REPO_ROOT)

    attempts = _jsonl(workspace / ".harness" / "attempts.jsonl")
    assert attempts[-1]["record_type"] == "finished"
    assert attempts[-1]["attempt_id"] == attempt_id
    assert attempts[-1]["status"] == "INTERRUPTED"
    assert snapshot["active_attempt_id"] is None
    assert inspect_run_integrity(workspace)["issue_count"] == 0


def test_waiting_human_state_survives_reconciliation(tmp_path: Path) -> None:
    from tooling.run_state import ensure_run_state

    workspace = tmp_path / "run"
    workspace.mkdir()
    with (workspace / "UNITS.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=UNIT_FIELDS)
        writer.writeheader()
        writer.writerow(
            {
                "unit_id": "U010",
                "title": "Approve scope",
                "type": "HUMAN",
                "skill": "human-checkpoint",
                "checkpoint": "C1",
                "status": "TODO",
                "owner": "HUMAN",
            }
        )
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    (workspace / "DECISIONS.md").write_text("# Decisions\n\n- [ ] Approve C1\n", encoding="utf-8")

    waiting = run_one_unit(workspace=workspace, repo_root=REPO_ROOT)
    assert waiting.status == "BLOCKED"
    before = json.loads((workspace / ".harness" / "run.json").read_text(encoding="utf-8"))
    assert before["state"] == "WAITING_HUMAN"

    after = ensure_run_state(workspace=workspace, repo_root=REPO_ROOT)

    assert after["state"] == "WAITING_HUMAN"


def test_ensure_run_state_finalizes_prepared_completion_transaction(tmp_path: Path) -> None:
    from tooling.harness import write_unit_manifest
    from tooling.run_state import (
        ensure_run_state,
        initialize_run_state,
        record_completion_stage,
        start_attempt,
    )

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv", status="DOING")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    output = workspace / "output" / "result.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("prepared before process crash\n", encoding="utf-8")
    initialize_run_state(
        workspace=workspace,
        repo_root=REPO_ROOT,
        pipeline_path=None,
        units_template="",
    )
    attempt_id = start_attempt(
        workspace=workspace,
        repo_root=REPO_ROOT,
        unit_id="U010",
        skill="skill-without-script",
        inputs=(),
    )
    manifest_path = write_unit_manifest(
        workspace=workspace,
        unit_id="U010",
        skill="skill-without-script",
        outputs=["output/result.md"],
        exit_code=0,
        status="PREPARED",
        attempt_id=attempt_id,
        repo_root=REPO_ROOT,
    )
    record_completion_stage(
        workspace=workspace,
        unit_id="U010",
        attempt_id=attempt_id,
        stage="prepared",
        manifest_path=str(manifest_path.relative_to(workspace)),
        outputs=["output/result.md"],
    )

    snapshot = ensure_run_state(workspace=workspace, repo_root=REPO_ROOT)

    with (workspace / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        assert next(csv.DictReader(handle))["status"] == "DONE"
    assert snapshot["state"] == "COMPLETED"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["status"] == "DONE"
    finished = [record for record in _jsonl(workspace / ".harness" / "attempts.jsonl") if record["record_type"] == "finished"]
    assert finished[-1]["status"] == "SUCCEEDED"
    assert "unit.completion.recovered" in {event["type"] for event in _jsonl(workspace / ".harness" / "events.jsonl")}


def test_reconciliation_recovers_manifest_written_before_prepared_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tooling.completion as completion
    from tooling.run_state import ensure_run_state, inspect_run_integrity

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    output = workspace / "output" / "result.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("manifest durable before prepared Event\n", encoding="utf-8")
    original_record_completion_stage = completion.record_completion_stage

    def interrupt_prepared_event(**kwargs: object) -> dict[str, object]:
        if kwargs.get("stage") == "prepared":
            raise RuntimeError("simulated crash before prepared Event append")
        return original_record_completion_stage(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(completion, "record_completion_stage", interrupt_prepared_event)
    with pytest.raises(RuntimeError, match="simulated crash"):
        completion.commit_unit_completion(
            workspace=workspace,
            repo_root=REPO_ROOT,
            unit_id="U010",
        )
    monkeypatch.setattr(completion, "record_completion_stage", original_record_completion_stage)

    before_events = _jsonl(workspace / ".harness" / "events.jsonl")
    assert "unit.completion.prepared" not in {event["type"] for event in before_events}
    manifest_path = next((workspace / "output" / "unit_logs").glob("*.manifest.json"))
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["status"] == "PREPARED"

    snapshot = ensure_run_state(workspace=workspace, repo_root=REPO_ROOT)

    assert snapshot["state"] == "COMPLETED"
    with (workspace / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        assert next(csv.DictReader(handle))["status"] == "DONE"
    events = _jsonl(workspace / ".harness" / "events.jsonl")
    assert any(
        event.get("type") == "unit.completion.prepared"
        and event.get("payload", {}).get("recovered") is True
        for event in events
    )
    assert inspect_run_integrity(workspace)["issue_count"] == 0


def test_reconciliation_does_not_recover_prepared_manifest_from_older_attempt(tmp_path: Path) -> None:
    import tooling.run_state as run_state
    from tooling.harness import write_unit_manifest

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv", status="DOING")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    output = workspace / "output" / "result.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("old prepared output\n", encoding="utf-8")
    snapshot = run_state.initialize_run_state(
        workspace=workspace,
        repo_root=REPO_ROOT,
        pipeline_path=None,
        units_template="",
    )
    old_attempt_id = run_state.start_attempt(
        workspace=workspace,
        repo_root=REPO_ROOT,
        unit_id="U010",
        skill="skill-without-script",
        inputs=(),
    )
    manifest_path = write_unit_manifest(
        workspace=workspace,
        unit_id="U010",
        skill="skill-without-script",
        outputs=["output/result.md"],
        exit_code=0,
        status="PREPARED",
        attempt_id=old_attempt_id,
        repo_root=REPO_ROOT,
    )
    newer_attempt_id = "attempt_newer"
    run_state._append_jsonl(
        workspace / ".harness" / "attempts.jsonl",
        {
            "schema": run_state.ATTEMPT_SCHEMA,
            "record_type": "started",
            "run_id": snapshot["run_id"],
            "attempt_id": newer_attempt_id,
            "unit_id": "U010",
            "skill": "skill-without-script",
            "status": "RUNNING",
            "started_at": "2026-07-16T00:00:00",
            "inputs": [],
        },
    )

    assert run_state._recover_unannounced_prepared_manifests(
        workspace=workspace,
        run_id=str(snapshot["run_id"]),
    ) == []
    run_state.record_completion_stage(
        workspace=workspace,
        unit_id="U010",
        attempt_id=old_attempt_id,
        stage="prepared",
        manifest_path=str(manifest_path.relative_to(workspace)),
        outputs=["output/result.md"],
    )
    assert run_state._recover_prepared_completions(
        workspace=workspace,
        run_id=str(snapshot["run_id"]),
    ) == []
    assert not any(
        record.get("record_type") == "finished" and record.get("attempt_id") == old_attempt_id
        for record in _jsonl(workspace / ".harness" / "attempts.jsonl")
    )


def test_reconciliation_repairs_finished_attempt_before_terminal_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tooling.run_state as run_state
    from tooling.completion import commit_unit_completion

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    output = workspace / "output" / "result.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("finished before terminal Event\n", encoding="utf-8")
    original_append_event = run_state._append_event

    def interrupt_terminal_event(**kwargs: object) -> dict[str, object]:
        if kwargs.get("event_type") == "unit.attempt.succeeded":
            raise RuntimeError("simulated crash after Attempt finish append")
        return original_append_event(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(run_state, "_append_event", interrupt_terminal_event)
    with pytest.raises(RuntimeError, match="simulated crash"):
        commit_unit_completion(
            workspace=workspace,
            repo_root=REPO_ROOT,
            unit_id="U010",
        )
    monkeypatch.setattr(run_state, "_append_event", original_append_event)

    snapshot = run_state.ensure_run_state(workspace=workspace, repo_root=REPO_ROOT)

    assert snapshot["state"] == "COMPLETED"
    with (workspace / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        assert next(csv.DictReader(handle))["status"] == "DONE"
    events = _jsonl(workspace / ".harness" / "events.jsonl")
    assert any(
        event.get("type") == "unit.attempt.succeeded"
        and event.get("payload", {}).get("recovered") is True
        for event in events
    )
    assert run_state.inspect_run_integrity(workspace)["issue_count"] == 0


def test_reconciliation_does_not_restore_done_without_artifact_ledger(tmp_path: Path) -> None:
    from tooling.harness import write_unit_manifest
    from tooling.run_state import ensure_run_state, finish_attempt, initialize_run_state, inspect_run_integrity, start_attempt

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv", status="DOING")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    output = workspace / "output" / "result.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("result whose Artifact ledger was lost\n", encoding="utf-8")
    initialize_run_state(
        workspace=workspace,
        repo_root=REPO_ROOT,
        pipeline_path=None,
        units_template="",
    )
    attempt_id = start_attempt(
        workspace=workspace,
        repo_root=REPO_ROOT,
        unit_id="U010",
        skill="skill-without-script",
        inputs=(),
    )
    write_unit_manifest(
        workspace=workspace,
        unit_id="U010",
        skill="skill-without-script",
        outputs=["output/result.md"],
        exit_code=0,
        status="DONE",
        attempt_id=attempt_id,
        repo_root=REPO_ROOT,
    )
    finish_attempt(
        workspace=workspace,
        attempt_id=attempt_id,
        unit_id="U010",
        skill="skill-without-script",
        status="SUCCEEDED",
        exit_code=0,
        outputs=["output/result.md"],
    )
    (workspace / ".harness" / "artifacts.jsonl").write_text("", encoding="utf-8")

    ensure_run_state(workspace=workspace, repo_root=REPO_ROOT)

    with (workspace / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        assert next(csv.DictReader(handle))["status"] == "DOING"
    codes = {issue["code"] for issue in inspect_run_integrity(workspace)["issues"]}
    assert {"attempt_artifact_missing", "manifest_artifact_missing"}.issubset(codes)


def test_run_audit_detects_current_artifact_hash_drift(tmp_path: Path) -> None:
    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    output = workspace / "output" / "result.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("registered result\n", encoding="utf-8")

    completed = _run(
        "scripts/pipeline.py",
        "mark",
        "--workspace",
        str(workspace),
        "--unit-id",
        "U010",
        "--status",
        "DONE",
        "--note",
        "acceptance checked before drift test",
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    output.write_text("mutated after completion\n", encoding="utf-8")

    exit_code, audit = build_run_audit_payload(workspace=workspace, repo_root=REPO_ROOT)

    assert exit_code == 2
    assert "artifact_hash_mismatch" in {issue["code"] for issue in audit["harness_issues"]}


def test_run_audit_detects_manifest_artifact_hash_disagreement(tmp_path: Path) -> None:
    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    output = workspace / "output" / "result.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("registered result\n", encoding="utf-8")

    completed = _run(
        "scripts/pipeline.py",
        "mark",
        "--workspace",
        str(workspace),
        "--unit-id",
        "U010",
        "--status",
        "DONE",
        "--note",
        "acceptance checked before manifest test",
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    manifest_path = next((workspace / "output" / "unit_logs").glob("*.manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outputs"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    exit_code, audit = build_run_audit_payload(workspace=workspace, repo_root=REPO_ROOT)

    assert exit_code == 2
    assert "manifest_artifact_hash_mismatch" in {
        issue["code"] for issue in audit["harness_issues"]
    }


def test_run_audit_rejects_done_unit_without_attempt_or_manifest(tmp_path: Path) -> None:
    from tooling.run_state import initialize_run_state

    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv", status="DONE")
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    output = workspace / "output" / "result.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("unproven result\n", encoding="utf-8")
    initialize_run_state(
        workspace=workspace,
        repo_root=REPO_ROOT,
        pipeline_path=None,
        units_template="",
    )

    exit_code, audit = build_run_audit_payload(workspace=workspace, repo_root=REPO_ROOT)

    codes = {issue["code"] for issue in audit["harness_issues"]}
    assert exit_code == 2
    assert {"done_without_successful_attempt", "done_without_manifest"}.issubset(codes)


def test_auto_approval_records_machine_decision(tmp_path: Path) -> None:
    workspace = tmp_path / "run"
    _write_units(workspace / "UNITS.csv", skill="human-checkpoint", outputs="")
    with (workspace / "UNITS.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["owner"] = "HUMAN"
    with (workspace / "UNITS.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=UNIT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (workspace / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    (workspace / "DECISIONS.md").write_text(
        "# Decisions\n\n## Approvals (check to unblock)\n- [ ] Approve C1\n",
        encoding="utf-8",
    )

    result = run_one_unit(workspace=workspace, repo_root=REPO_ROOT, auto_approve={"C1"})

    decisions = _jsonl(workspace / ".harness" / "decisions.jsonl")
    assert result.status == "DONE"
    assert decisions[-1]["action"] == "checkpoint.auto_approved"
    assert decisions[-1]["actor"] == {"kind": "harness", "id": "auto-approval"}


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


def test_product_start_rejects_an_existing_run_and_resume_continues(tmp_path: Path) -> None:
    workspace = tmp_path / "product-run"
    created = _run(
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
    assert created.returncode == 0, created.stderr or created.stdout

    started = _run(
        "-m",
        "tooling.product_cli",
        "run",
        "start",
        "--workspace",
        str(workspace),
        "--max-steps",
        "1",
    )
    assert started.returncode == 0, started.stderr or started.stdout

    duplicate_start = _run(
        "-m",
        "tooling.product_cli",
        "run",
        "start",
        "--workspace",
        str(workspace),
        "--max-steps",
        "1",
    )
    assert duplicate_start.returncode == 2
    assert "use `uv run rh run resume" in duplicate_start.stderr

    resumed = _run(
        "-m",
        "tooling.product_cli",
        "run",
        "resume",
        "--workspace",
        str(workspace),
        "--max-steps",
        "1",
    )
    assert "already left PLANNED" not in resumed.stderr


def test_product_cli_fails_clearly_without_a_harness_checkout(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from tooling import product_cli

    monkeypatch.setattr(product_cli, "PIPELINE_CLI", tmp_path / "missing" / "pipeline.py")
    assert product_cli._run_pipeline("kickoff", "--topic", "demo") == 2
    assert "not a standalone Harness distribution" in capsys.readouterr().err


def test_product_status_does_not_create_a_missing_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "missing"

    result = _run("-m", "tooling.product_cli", "run", "status", "--workspace", str(workspace))

    assert result.returncode == 2
    assert "Workspace not found:" in result.stderr
    assert not workspace.exists()


def test_pipeline_preflight_does_not_create_invalid_workspace_paths(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    invalid_pipeline_workspace = tmp_path / "invalid-pipeline"

    absent = _run("scripts/pipeline.py", "doctor", "--workspace", str(missing))
    invalid_pipeline = _run(
        "scripts/pipeline.py",
        "init",
        "--workspace",
        str(invalid_pipeline_workspace),
        "--pipeline",
        "not-a-workflow",
    )
    repo_root = _run(
        "scripts/pipeline.py",
        "init",
        "--workspace",
        str(REPO_ROOT),
        "--pipeline",
        "research-brief",
    )

    assert absent.returncode != 0
    assert "Workspace not found:" in absent.stderr
    assert not missing.exists()
    assert invalid_pipeline.returncode != 0
    assert "Pipeline not found:" in invalid_pipeline.stderr
    assert not invalid_pipeline_workspace.exists()
    assert repo_root.returncode != 0
    assert "Refusing to use repo root as workspace" in repo_root.stderr
    assert not (REPO_ROOT / ".harness").exists()


def test_workspace_invocation_lock_rejects_concurrent_commands(tmp_path: Path) -> None:
    from tooling.run_state import workspace_invocation_lock

    workspace = tmp_path / "locked-run"
    created = _run(
        "scripts/pipeline.py",
        "init",
        "--workspace",
        str(workspace),
        "--pipeline",
        "research-brief",
    )
    assert created.returncode == 0, created.stderr or created.stdout

    commands = [
        ("scripts/pipeline.py", "init", "--workspace", str(workspace), "--pipeline", "research-brief"),
        ("scripts/pipeline.py", "kickoff", "--topic", "locked topic", "--workspace", str(workspace)),
        ("scripts/pipeline.py", "run-one", "--workspace", str(workspace)),
        ("scripts/pipeline.py", "run", "--workspace", str(workspace)),
        ("scripts/pipeline.py", "doctor", "--workspace", str(workspace)),
        ("scripts/pipeline.py", "audit", "--workspace", str(workspace)),
        ("scripts/pipeline.py", "improve", "--workspace", str(workspace)),
        ("scripts/pipeline.py", "pack", "--workspace", str(workspace)),
        ("scripts/pipeline.py", "approve", "--workspace", str(workspace), "--checkpoint", "C1"),
        (
            "scripts/pipeline.py",
            "mark",
            "--workspace",
            str(workspace),
            "--unit-id",
            "U010",
            "--status",
            "DOING",
            "--note",
            "lock coverage",
        ),
        ("-m", "tooling.product_cli", "run", "status", "--workspace", str(workspace)),
        ("-m", "tooling.product_cli", "run", "start", "--workspace", str(workspace)),
        ("-m", "tooling.product_cli", "run", "resume", "--workspace", str(workspace)),
        ("-m", "tooling.product_cli", "evidence", "inspect", "--workspace", str(workspace)),
        ("-m", "tooling.product_cli", "improve", "diagnose", "--workspace", str(workspace)),
        (
            "-m",
            "tooling.product_cli",
            "goal",
            "create",
            "--topic",
            "locked topic",
            "--workspace",
            str(workspace),
        ),
    ]

    with workspace_invocation_lock(workspace=workspace, operation="test.owner"):
        blocked_results = [_run(*command) for command in commands]

    assert all(result.returncode == 2 for result in blocked_results)
    assert all("Workspace is busy" in result.stderr for result in blocked_results)
    assert all("operation=test.owner" in result.stderr for result in blocked_results)
    lock_metadata = json.loads((workspace / ".harness" / "invocation.lock").read_text(encoding="utf-8"))
    assert lock_metadata["schema"] == "workspace-invocation-lock.v1"
    assert lock_metadata["operation"] == "test.owner"
    assert lock_metadata["workspace"] == str(workspace.resolve())
    for relpath in (
        "output/DOCTOR_REPORT.json",
        "output/RUN_AUDIT.json",
        "output/IMPROVEMENT_REPORT.json",
        "output/ARTIFACT_PACK.json",
    ):
        assert not (workspace / relpath).exists()

    released = _run("-m", "tooling.product_cli", "run", "status", "--workspace", str(workspace))
    assert released.returncode == 0, released.stderr or released.stdout


def test_workspace_invocation_lock_is_released_when_owner_process_dies(tmp_path: Path) -> None:
    workspace = tmp_path / "crashed-owner-run"
    created = _run(
        "scripts/pipeline.py",
        "init",
        "--workspace",
        str(workspace),
        "--pipeline",
        "research-brief",
    )
    assert created.returncode == 0, created.stderr or created.stdout

    code = "\n".join(
        [
            "import time",
            "from pathlib import Path",
            "from tooling.run_state import workspace_invocation_lock",
            f"workspace = Path({str(workspace)!r})",
            "with workspace_invocation_lock(workspace=workspace, operation='crash.owner'):",
            "    print('LOCKED', flush=True)",
            "    time.sleep(30)",
        ]
    )
    owner = subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert owner.stdout is not None
        assert owner.stdout.readline().strip() == "LOCKED"
        blocked = _run("scripts/pipeline.py", "doctor", "--workspace", str(workspace))
        assert blocked.returncode == 2
        assert "operation=crash.owner" in blocked.stderr
    finally:
        owner.kill()
        owner.wait(timeout=5)

    released = _run("scripts/pipeline.py", "doctor", "--workspace", str(workspace))
    assert released.returncode == 0, released.stderr or released.stdout


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
    assert "Run evidence: ATTENTION" in evidence.stdout
    assert "Research evidence: indexed as Workflow-local Artifacts" in evidence.stdout
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
