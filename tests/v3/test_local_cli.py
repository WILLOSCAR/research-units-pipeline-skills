from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

import research_harness._local_runtime as local_runtime
from research_harness._local_runtime import (
    compose_repository_engine,
    initialize_repository_run,
)
from research_harness.cli import main
from research_harness.engine import AdvanceRun, EngineOutcome


REPO_ROOT = Path(__file__).resolve().parents[2]


def _copy_repository(destination: Path) -> Path:
    shutil.copytree(
        REPO_ROOT,
        destination,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            ".pytest_cache",
            "__pycache__",
            "workspaces",
        ),
    )
    return destination


def _start(workspace: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    exit_code = main(
        [
            "loop",
            "work",
            "--workspace",
            str(workspace),
            "--goal",
            "Review the supplied manuscript",
            "--kind",
            "review",
            "--case-id",
            "case-cli",
            "--repository",
            str(REPO_ROOT),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1, captured.err or captured.out
    assert captured.err == ""
    return json.loads(captured.out)


def test_case_work_materializes_one_canonical_run_and_pinned_contracts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"

    payload = _start(workspace, capsys)

    assert payload["schema"] == "research-harness.case-result/v1"
    assert payload["state"] == "BLOCKED"
    inspection = payload["inspection"]
    assert inspection["case_id"] == "case-cli"
    assert inspection["kind"] == "review"
    assert inspection["normalized_claims_available"] is False
    assert inspection["quality"]["execution_integrity"]["status"] == "VERIFIED"
    assert inspection["quality"]["contract_acceptance"]["status"] == "BLOCKED"
    assert inspection["quality"]["research_quality"]["status"] == "NOT_EVALUATED"
    assert all("adapter" not in issue.lower() for issue in payload["issues"])
    assert not (workspace / ".harness").exists()

    state_path = workspace / ".harness-v3" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    contracts = workspace / ".harness-v3" / "contracts"
    workflow = json.loads((contracts / "workflow.json").read_text(encoding="utf-8"))
    identity = json.loads((contracts / "identity.json").read_text(encoding="utf-8"))
    assert state["schema"] == "research-harness.run-aggregate/v1"
    assert workflow["schema"] == "research-harness.workflow-snapshot/v2"
    assert workflow["case_contract"] == {
        "kind": "review",
        "views": ["output/REVIEW.md"],
        "claim_sources": ["output/CLAIMS.jsonl"],
        "evidence_sources": [
            "output/EVIDENCE_AUDIT.jsonl",
            "output/NOVELTY_MATRIX.tsv",
        ],
        "decision_sources": ["DECISIONS.md"],
    }
    assert identity["schema"] == "research-harness.local-identity/v1"
    assert state["revision"] == identity["revision"]
    assert (
        hashlib.sha256(
            json.dumps(
                identity["components"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        == state["revision"]["kernel_digest"]
    )
    execution = (
        workspace / ".harness-v3" / "execution" / state["revision"]["kernel_digest"]
    )
    assert (execution / "AGENTS.md").is_file()
    assert (execution / "pipelines" / "paper-review.pipeline.md").is_file()
    assert (execution / "templates" / "UNITS.paper-review.csv").is_file()
    pinned_script = (
        execution / ".codex" / "skills" / "workspace-init" / "scripts" / "run.py"
    )
    assert pinned_script.is_file()
    assert pinned_script.stat().st_mode & 0o222 == 0
    assert (workspace / "UNITS.csv").read_bytes() == (
        REPO_ROOT / "templates" / "UNITS.paper-review.csv"
    ).read_bytes()


def test_case_show_and_retry_survive_process_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    _start(workspace, capsys)

    show_code = main(
        [
            "loop",
            "show",
            "--workspace",
            str(workspace),
            "--details",
            "--json",
        ]
    )
    shown = json.loads(capsys.readouterr().out)
    assert show_code == 1
    assert shown["schema"] == "research-harness.case-inspection/v1"
    assert shown["inspection"]["state"] == "BLOCKED"
    assert shown["inspection"]["details"]["recipe"] == "paper-review"
    before_version = shown["inspection"]["details"]["state_version"]
    assert shown["inspection"]["details"]["steps"]["completed"] >= 1

    retry_code = main(
        [
            "loop",
            "work",
            "--workspace",
            str(workspace),
            "--repository",
            str(REPO_ROOT),
            "--json",
        ]
    )
    retried = json.loads(capsys.readouterr().out)
    assert retry_code == 1
    assert retried["state"] == "BLOCKED"
    assert all("adapter" not in issue.lower() for issue in retried["issues"])

    show_code = main(
        [
            "loop",
            "show",
            "--workspace",
            str(workspace),
            "--details",
            "--json",
        ]
    )
    shown_again = json.loads(capsys.readouterr().out)
    assert show_code == 1
    assert shown_again["inspection"]["details"]["state_version"] > before_version


def test_composed_engine_executes_immutable_revision_snapshot(
    tmp_path: Path,
) -> None:
    repo_copy = _copy_repository(tmp_path / "repo")
    workspace = tmp_path / "workspace"
    initialize_repository_run(
        workspace=workspace,
        repo_root=repo_copy,
        pipeline="paper-review",
        request="Prove compose-time execution consistency",
        run_id="immutable-compose",
    )
    engine = compose_repository_engine(
        workspace=workspace,
        repo_root=repo_copy,
    )
    run = engine.inspect().run
    assert run is not None
    first = run.units[0].plan
    sentinel = tmp_path / "MUTATED_SKILL_EXECUTED"
    mutable_script = (
        repo_copy / ".codex" / "skills" / first.skill / "scripts" / "run.py"
    )
    mutable_script.write_text(
        "from pathlib import Path\n"
        f"Path({str(sentinel)!r}).write_text('unsafe', encoding='utf-8')\n",
        encoding="utf-8",
    )

    result = engine.execute(AdvanceRun(unit_id=first.id))

    assert result.outcome in {EngineOutcome.ADVANCED, EngineOutcome.COMPLETED}
    assert not sentinel.exists()


def test_snapshot_mismatch_rolls_back_new_workspace_and_retry_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_copy = _copy_repository(tmp_path / "repo")
    workspace = tmp_path / "workspace"
    script = repo_copy / ".codex" / "skills" / "workspace-init" / "scripts" / "run.py"
    original = script.read_bytes()
    real_materialize = local_runtime.materialize_execution_snapshot

    def mutate_then_materialize(**kwargs: object) -> Path:
        script.write_text("raise SystemExit('mutated')\n", encoding="utf-8")
        return real_materialize(**kwargs)

    monkeypatch.setattr(
        local_runtime,
        "materialize_execution_snapshot",
        mutate_then_materialize,
    )
    with pytest.raises(ValueError, match="changed during compose"):
        initialize_repository_run(
            workspace=workspace,
            repo_root=repo_copy,
            pipeline="paper-review",
            request="Rollback an inconsistent bootstrap",
            run_id="retryable-bootstrap",
        )

    assert not workspace.exists()
    assert not tuple(tmp_path.glob(".workspace.*.staging"))

    script.write_bytes(original)
    monkeypatch.setattr(
        local_runtime,
        "materialize_execution_snapshot",
        real_materialize,
    )
    result, _ = initialize_repository_run(
        workspace=workspace,
        repo_root=repo_copy,
        pipeline="paper-review",
        request="Rollback an inconsistent bootstrap",
        run_id="retryable-bootstrap",
    )

    assert result.outcome is EngineOutcome.CREATED
    assert result.inspection.workspace == workspace.resolve()
    assert (workspace / ".harness-v3" / "state.json").is_file()


@pytest.mark.parametrize("root_kind", ("skill", "template"))
def test_init_rejects_symlinked_repository_execution_root_before_workspace_writes(
    tmp_path: Path,
    root_kind: str,
) -> None:
    repo_copy = _copy_repository(tmp_path / "repo")
    skill_root = repo_copy / ".codex" / "skills" / "workspace-init"
    source = (
        skill_root
        if root_kind == "skill"
        else skill_root / "assets" / "workspace-template"
    )
    outside = tmp_path / f"outside-{root_kind}"
    shutil.copytree(source, outside)
    shutil.rmtree(source)
    source.symlink_to(outside, target_is_directory=True)
    workspace = tmp_path / "workspace"

    with pytest.raises(ValueError, match="symbolic link|outside repo_root"):
        initialize_repository_run(
            workspace=workspace,
            repo_root=repo_copy,
            pipeline="paper-review",
            request="Reject mutable execution roots",
            run_id=f"unsafe-{root_kind}",
        )

    assert not workspace.exists()


def test_init_never_overwrites_existing_managed_workspace(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    _start(workspace, capsys)
    state = workspace / ".harness-v3" / "state.json"
    before = hashlib.sha256(state.read_bytes()).hexdigest()

    exit_code = main(
        [
            "loop",
            "work",
            "--workspace",
            str(workspace),
            "--goal",
            "Replacement",
            "--kind",
            "review",
            "--repository",
            str(REPO_ROOT),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["error"]["code"] == "case_exists"
    assert hashlib.sha256(state.read_bytes()).hexdigest() == before


def test_init_rejects_template_directory_symlink_escape(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (workspace / "output").symlink_to(outside, target_is_directory=True)

    exit_code = main(
        [
            "loop",
            "work",
            "--workspace",
            str(workspace),
            "--goal",
            "Do not escape",
            "--kind",
            "review",
            "--repository",
            str(REPO_ROOT),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["error"]["code"] == "invalid_request"
    assert not tuple(outside.iterdir())
    assert not (workspace / ".harness-v3").exists()


def test_legacy_v2_workspace_is_read_only_and_creates_no_v3_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "legacy"
    legacy = workspace / ".harness"
    legacy.mkdir(parents=True)
    (legacy / "harness.lock.json").write_text(
        json.dumps({"schema": "harness-lock.v2"}),
        encoding="utf-8",
    )

    inspect_code = main(["loop", "show", "--workspace", str(workspace), "--json"])
    inspected = json.loads(capsys.readouterr().out)
    assert inspect_code == 0
    assert inspected["inspection"]["state"] == "LEGACY_READ_ONLY"
    assert inspected["inspection"]["normalized_claims_available"] is False

    advance_code = main(
        [
            "loop",
            "work",
            "--workspace",
            str(workspace),
            "--repository",
            str(REPO_ROOT),
            "--json",
        ]
    )
    failed = json.loads(capsys.readouterr().out)
    assert advance_code == 2
    assert failed["error"]["code"] == "legacy_read_only"
    assert not (workspace / ".harness-v3").exists()


def test_mutation_rejects_a_canonical_plan_that_disagrees_with_workflow(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    _start(workspace, capsys)
    state_path = workspace / ".harness-v3" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["plan"]["units"][0]["skill"] = "pipeline-router"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    inspect_code = main(["loop", "show", "--workspace", str(workspace), "--json"])
    inspection = json.loads(capsys.readouterr().out)
    assert inspect_code == 2
    assert inspection["ok"] is False
    assert inspection["error"]["code"] == "canonical_state_unavailable"

    exit_code = main(
        [
            "loop",
            "work",
            "--workspace",
            str(workspace),
            "--repository",
            str(REPO_ROOT),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["error"]["code"] == "canonical_state_unavailable"
    assert (
        payload["error"]["message"] == "Canonical Loop state could not be read safely."
    )


def test_json_usage_errors_are_one_parseable_object(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["loop", "work", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 2
    assert captured.err == ""
    assert payload["schema"] == "research-harness.error/v1"
    assert payload["error"]["code"] == "cli_usage_error"
    assert "--workspace" in payload["error"]["message"]
