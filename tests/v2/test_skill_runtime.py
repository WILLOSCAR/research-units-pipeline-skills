from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path, PurePosixPath

import pytest

from research_harness.skills import (
    InMemorySkillAdapter,
    InvalidSkillAdapterError,
    InvalidSkillPathError,
    SkillAdapter,
    SkillContext,
    SkillProcessError,
    SkillTimeoutError,
    SubprocessSkillAdapter,
)


def test_repository_adapter_rejects_an_unsafe_skill_name(tmp_path: Path) -> None:
    with pytest.raises(InvalidSkillAdapterError, match="lowercase repository Skill"):
        SubprocessSkillAdapter.for_repo_skill(
            repo_root=tmp_path,
            skill="bad_skill",
        )


def test_repository_adapter_rejects_a_skill_symlink_outside_repo_root(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    outside_skill = tmp_path / "outside-skill"
    script = outside_skill / "scripts" / "run.py"
    script.parent.mkdir(parents=True)
    script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    skill_link = repo_root / ".codex" / "skills" / "escaped"
    skill_link.parent.mkdir(parents=True)
    skill_link.symlink_to(outside_skill, target_is_directory=True)

    with pytest.raises(InvalidSkillAdapterError, match="inside repo_root"):
        SubprocessSkillAdapter.for_repo_skill(
            repo_root=repo_root,
            skill="escaped",
        )


def test_context_normalizes_workspace_relative_paths(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    context = SkillContext(
        workspace=workspace,
        unit_id="C0.U01",
        inputs=("GOAL.md", Path("sources/index.jsonl")),
        outputs=("output/report.md",),
        checkpoint="C0",
    )

    assert context.workspace == workspace.resolve()
    assert context.inputs == (
        PurePosixPath("GOAL.md"),
        PurePosixPath("sources/index.jsonl"),
    )
    assert context.outputs == (PurePosixPath("output/report.md"),)
    assert context.output_paths == (workspace.resolve() / "output" / "report.md",)


def test_context_accepts_and_normalizes_an_input_directory(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "sections").mkdir()

    context = SkillContext(
        workspace=workspace,
        unit_id="U1",
        inputs=("sections/",),
    )

    assert context.inputs == (PurePosixPath("sections"),)
    assert context.input_paths == (workspace.resolve() / "sections",)


def test_context_rejects_an_output_directory_marker(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(InvalidSkillPathError, match="directory slash"):
        SkillContext(workspace=workspace, unit_id="U1", outputs=("output/",))


def test_context_resolve_rejects_a_raw_directory_marker(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    context = SkillContext(workspace=workspace, unit_id="U1")

    with pytest.raises(InvalidSkillPathError, match="directory slash"):
        context.resolve("output/")


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "/tmp/outside.txt",
        "../outside.txt",
        "nested/../../outside.txt",
        r"C:\outside.txt",
        "output;other.txt",
        "?output/optional.txt",
    ],
)
def test_context_rejects_non_workspace_paths(tmp_path: Path, unsafe_path: str) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(InvalidSkillPathError):
        SkillContext(workspace=workspace, unit_id="U1", outputs=(unsafe_path,))


def test_context_rejects_symlink_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (workspace / "escaped").symlink_to(outside, target_is_directory=True)

    with pytest.raises(InvalidSkillPathError, match="outside the Workspace"):
        SkillContext(workspace=workspace, unit_id="U1", outputs=("escaped/report.md",))


def test_adapter_rechecks_symlinks_immediately_before_execution(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    slot = workspace / "slot"
    slot.mkdir()
    context = SkillContext(
        workspace=workspace, unit_id="U1", outputs=("slot/report.md",)
    )

    slot.rmdir()
    slot.symlink_to(outside, target_is_directory=True)
    adapter = InMemorySkillAdapter(handler=lambda _: 0)

    with pytest.raises(InvalidSkillPathError, match="outside the Workspace"):
        adapter.run(context)


def test_in_memory_adapter_runs_through_the_public_interface(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    context = SkillContext(
        workspace=workspace, unit_id="U1", outputs=("output/result.txt",)
    )

    def handler(skill_context: SkillContext) -> None:
        output = skill_context.output_paths[0]
        output.parent.mkdir(parents=True)
        output.write_text("done\n", encoding="utf-8")
        print("captured stdout")
        print("captured stderr", file=sys.stderr)

    adapter = InMemorySkillAdapter(handler=handler, adapter="fixture:in-memory")

    assert isinstance(adapter, SkillAdapter)
    result = adapter.run(context)

    assert result.succeeded is True
    assert result.exit_code == 0
    assert result.adapter == "fixture:in-memory"
    assert result.stdout == "captured stdout\n"
    assert result.stderr == "captured stderr\n"
    assert result.elapsed_ms >= 0
    assert (workspace / "output" / "result.txt").read_text(encoding="utf-8") == "done\n"


def test_subprocess_adapter_builds_existing_run_py_protocol(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repo_root = tmp_path / "repo"
    script = repo_root / ".codex" / "skills" / "fixture-skill" / "scripts" / "run.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        """
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--workspace", required=True)
parser.add_argument("--unit-id", required=True)
parser.add_argument("--inputs", required=True)
parser.add_argument("--outputs", required=True)
parser.add_argument("--checkpoint", required=True)
args = parser.parse_args()
workspace = Path(args.workspace)
target = workspace / args.outputs.split(";")[0]
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps({
    "unit_id": args.unit_id,
    "inputs": args.inputs,
    "checkpoint": args.checkpoint,
}), encoding="utf-8")
print("adapter ok")
""".lstrip(),
        encoding="utf-8",
    )
    context = SkillContext(
        workspace=workspace,
        unit_id="C0.U01",
        inputs=("GOAL.md", "sources/manifest.yml"),
        outputs=("output/result.json",),
        checkpoint="C0",
    )
    adapter = SubprocessSkillAdapter.for_repo_skill(
        repo_root=repo_root,
        skill="fixture-skill",
        python_executable=sys.executable,
    )

    result = adapter.run(context)

    assert result.succeeded is True
    assert result.adapter == "skill:fixture-skill:subprocess"
    assert result.stdout == "adapter ok\n"
    assert json.loads(
        (workspace / "output" / "result.json").read_text(encoding="utf-8")
    ) == {
        "unit_id": "C0.U01",
        "inputs": "GOAL.md;sources/manifest.yml",
        "checkpoint": "C0",
    }


def test_nonzero_exit_preserves_bounded_diagnostics_without_env_or_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    script = tmp_path / "run.py"
    script.write_text(
        """
import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--workspace")
parser.add_argument("--unit-id")
parser.add_argument("--inputs")
parser.add_argument("--outputs")
parser.add_argument("--checkpoint")
parser.parse_args()
print("useful stdout")
print("useful stderr", file=sys.stderr)
raise SystemExit(7)
""".lstrip(),
        encoding="utf-8",
    )
    secret = "must-not-appear-in-runtime-error"
    monkeypatch.setenv("SKILL_RUNTIME_TEST_SECRET", secret)
    context = SkillContext(
        workspace=workspace, unit_id="U1", outputs=("output/result.txt",)
    )
    adapter = SubprocessSkillAdapter(
        script_path=script,
        adapter="fixture:failure",
        python_executable=sys.executable,
    )

    with pytest.raises(SkillProcessError) as raised:
        adapter.run(context)

    error = raised.value
    assert error.adapter == "fixture:failure"
    assert error.exit_code == 7
    assert error.stdout == "useful stdout\n"
    assert error.stderr == "useful stderr\n"
    assert error.elapsed_ms >= 0
    assert not hasattr(error, "environment")
    assert not hasattr(error, "env")
    assert not hasattr(error, "argv")
    assert not hasattr(error, "command")
    bounded_diagnostics = repr(error.__dict__) + repr(error) + str(error)
    assert secret not in bounded_diagnostics
    assert os.fspath(script) not in bounded_diagnostics
    assert os.fspath(workspace) not in bounded_diagnostics


def test_subprocess_adapter_exposes_a_bounded_live_process_group_handle(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    script = tmp_path / "repo" / ".codex" / "skills" / "sleeper" / "scripts" / "run.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        """
import argparse
import time

parser = argparse.ArgumentParser()
parser.add_argument("--workspace")
parser.add_argument("--unit-id")
parser.add_argument("--inputs")
parser.add_argument("--outputs")
parser.add_argument("--checkpoint")
parser.parse_args()
time.sleep(60)
""".lstrip(),
        encoding="utf-8",
    )
    adapter = SubprocessSkillAdapter.for_repo_skill(
        repo_root=tmp_path / "repo",
        skill="sleeper",
    )

    handle = adapter.start(SkillContext(workspace=workspace, unit_id="U010"))
    try:
        assert handle.owner.pid > 0
        assert handle.owner.process_group_id == handle.owner.pid
        assert handle.owner.adapter == "skill:sleeper:subprocess"
        assert len(handle.owner.start_token) == 64
        assert handle.owner.is_live() is True
        assert handle.is_alive() is True
        assert os.fspath(script) not in repr(handle)
    finally:
        handle.terminate()
        with pytest.raises(SkillProcessError):
            handle.wait()
    assert handle.is_alive() is False


def test_subprocess_does_not_execute_skill_code_until_gate_release(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    script = tmp_path / "repo" / ".codex" / "skills" / "gated" / "scripts" / "run.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        """
import argparse
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--workspace", required=True)
parser.add_argument("--unit-id")
parser.add_argument("--inputs")
parser.add_argument("--outputs")
parser.add_argument("--checkpoint")
args = parser.parse_args()
Path(args.workspace, "skill-started").write_text("yes\\n", encoding="utf-8")
time.sleep(60)
""".lstrip(),
        encoding="utf-8",
    )
    adapter = SubprocessSkillAdapter.for_repo_skill(
        repo_root=tmp_path / "repo",
        skill="gated",
    )
    handle = adapter.start(SkillContext(workspace=workspace, unit_id="U010"))

    time.sleep(0.05)
    assert not (workspace / "skill-started").exists()
    handle.release()
    deadline = time.monotonic() + 2
    while not (workspace / "skill-started").exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert (workspace / "skill-started").exists()
    handle.terminate()
    with pytest.raises(SkillProcessError):
        handle.wait()


def test_subprocess_timeout_terminates_the_entire_process_group(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    script = tmp_path / "repo" / ".codex" / "skills" / "tree" / "scripts" / "run.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        """
import argparse
import subprocess
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--workspace", required=True)
parser.add_argument("--unit-id")
parser.add_argument("--inputs")
parser.add_argument("--outputs")
parser.add_argument("--checkpoint")
args = parser.parse_args()
child = subprocess.Popen([
    sys.executable,
    "-c",
    "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)",
])
Path(args.workspace, "child.pid").write_text(str(child.pid), encoding="utf-8")
print("started", flush=True)
time.sleep(60)
""".lstrip(),
        encoding="utf-8",
    )
    adapter = SubprocessSkillAdapter.for_repo_skill(
        repo_root=tmp_path / "repo",
        skill="tree",
        timeout_seconds=0.15,
    )
    handle = adapter.start(SkillContext(workspace=workspace, unit_id="U010"))
    process_group_id = handle.owner.process_group_id

    with pytest.raises(SkillTimeoutError):
        handle.wait()

    deadline = time.monotonic() + 2
    while _process_group_is_alive(process_group_id) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert handle.is_alive() is False
    assert _process_group_is_alive(process_group_id) is False


def _process_group_is_alive(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
