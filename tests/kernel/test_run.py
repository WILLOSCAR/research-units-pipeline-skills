"""run: ``run.json`` is the single authority; writes go through a versioned transaction."""

from __future__ import annotations

import json
import re

import pytest
from helpers import sample_run_state

from rh.kernel.records import RunStatus
from rh.kernel.run import RunConflict, RunNotFound, Workspace, new_run_id


def make_run(root):
    ws = Workspace(root / "run-a")
    state = sample_run_state()
    state.version = 0
    ws.create(state)
    return ws, state


# --- create / load ------------------------------------------------------------------------


def test_workspace_paths_hang_off_a_resolved_root(tmp_path):
    ws = Workspace(tmp_path / "run-a")

    assert ws.root.is_absolute() and ws.root == (tmp_path / "run-a").resolve()
    assert ws.run_json == ws.root / "run.json"
    assert ws.lock_path == ws.root / ".run.lock"
    assert ws.trace == ws.root / "trace.jsonl"
    assert ws.evidence.root == ws.root / "evidence"
    assert not ws.exists()


def test_create_writes_run_json_at_version_one(tmp_path):
    ws, state = make_run(tmp_path)

    raw = json.loads(ws.run_json.read_text(encoding="utf-8"))

    assert raw["version"] == 1
    assert raw["schema"] == "rh.run/1"
    assert raw["run_id"] == "brief-20260912-100000-beef"
    assert state.version == 1  # the caller's record is the one that was committed
    assert ws.exists()
    assert ws.load() == state


def test_create_lays_out_the_workspace_and_the_lock_file(tmp_path):
    ws, _ = make_run(tmp_path)

    for path in (ws.steps, ws.decisions, ws.artifact, ws.gates, ws.faults, ws.evidence.objects):
        assert path.is_dir(), path
    assert ws.evidence.index_path.is_file()
    assert ws.lock_path.is_file()
    assert not ws.run_json.with_suffix(".json.tmp").exists()


def test_create_refuses_a_second_run_in_the_same_workspace(tmp_path):
    ws, _ = make_run(tmp_path)
    before = ws.run_json.read_text(encoding="utf-8")

    other = sample_run_state()
    other.run_id = "brief-20260912-110000-cafe"
    with pytest.raises(FileExistsError):
        ws.create(other)

    assert ws.run_json.read_text(encoding="utf-8") == before


def test_load_raises_run_not_found_when_there_is_no_run(tmp_path):
    ws = Workspace(tmp_path / "empty")

    with pytest.raises(RunNotFound):
        ws.load()
    assert issubclass(RunNotFound, FileNotFoundError)


def test_transaction_on_a_missing_run_raises_run_not_found(tmp_path):
    ws = Workspace(tmp_path / "empty")

    with pytest.raises(RunNotFound):
        with ws.transaction():
            pass


# --- transaction ---------------------------------------------------------------------------


def test_transaction_bumps_the_version_and_commits_the_mutation(tmp_path):
    ws, _ = make_run(tmp_path)

    with ws.transaction() as state:
        assert state.version == 1
        state.status = RunStatus.RUNNING
        state.passes_used = 4
        state.pending_pass = None
        state.faults[1].resolved = True

    reloaded = ws.load()
    assert reloaded.version == 2
    assert reloaded.status is RunStatus.RUNNING
    assert reloaded.passes_used == 4
    assert reloaded.pending_pass is None
    assert reloaded.open_faults() == []
    assert reloaded == state  # what was reloaded is exactly what was mutated
    assert state.version == 2


def test_consecutive_transactions_increase_the_version_by_one_each(tmp_path):
    ws, _ = make_run(tmp_path)

    for expected in (2, 3, 4):
        with ws.transaction() as state:
            state.passes_used += 1
        assert ws.load().version == expected
    assert ws.load().passes_used == 6


def test_transaction_that_raises_leaves_run_json_unchanged(tmp_path):
    ws, _ = make_run(tmp_path)
    before = ws.run_json.read_text(encoding="utf-8")

    with pytest.raises(RuntimeError, match="boom"):
        with ws.transaction() as state:
            state.passes_used = 99
            state.status = RunStatus.ABANDONED
            raise RuntimeError("boom")

    assert ws.run_json.read_text(encoding="utf-8") == before
    assert ws.load().version == 1
    assert not ws.run_json.with_suffix(".json.tmp").exists()


def test_out_of_band_change_during_a_transaction_is_refused(tmp_path):
    ws, _ = make_run(tmp_path)

    with pytest.raises(RunConflict):
        with ws.transaction() as state:
            state.passes_used = 99
            # Another writer replaces run.json with a different version while
            # this transaction holds its loaded copy.
            raw = json.loads(ws.run_json.read_text(encoding="utf-8"))
            raw["version"] = 41
            raw["passes_used"] = 7
            ws.run_json.write_text(json.dumps(raw), encoding="utf-8")

    after = ws.load()
    assert after.version == 41  # the out-of-band write stands ...
    assert after.passes_used == 7  # ... and the refused mutation never landed


def test_lock_is_released_after_a_refused_transaction(tmp_path):
    ws, _ = make_run(tmp_path)

    with pytest.raises(RunConflict):
        with ws.transaction():
            raw = json.loads(ws.run_json.read_text(encoding="utf-8"))
            raw["version"] = 41
            ws.run_json.write_text(json.dumps(raw), encoding="utf-8")

    with ws.transaction() as state:  # would block forever if the lock leaked
        state.passes_used = 1
    assert ws.load().version == 42


def test_transaction_commits_atomically_without_leaving_a_temp_file(tmp_path):
    ws, _ = make_run(tmp_path)

    with ws.transaction() as state:
        state.passes_used = 1

    assert sorted(p.name for p in ws.root.iterdir() if p.name.startswith("run.json")) == ["run.json"]


# --- projections ------------------------------------------------------------------------------


def test_pass_dir_maps_a_pass_id_to_steps_step_pass_n(tmp_path):
    ws = Workspace(tmp_path / "run-a")

    assert ws.pass_dir("write#2") == ws.steps / "write" / "pass-2"
    assert ws.pass_dir("write#2").relative_to(ws.root).as_posix() == "steps/write/pass-2"
    assert ws.pass_dir("source-support#1") == ws.steps / "source-support" / "pass-1"


def test_log_appends_json_lines_to_the_trace(tmp_path):
    ws, _ = make_run(tmp_path)

    ws.log("pass.opened", pass_id="write#1", step="write")
    ws.log("gate.failed", gate="length-bound", findings=2)

    lines = ws.trace.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first, second = (json.loads(line) for line in lines)
    assert first["event"] == "pass.opened" and first["pass_id"] == "write#1" and first["step"] == "write"
    assert second["event"] == "gate.failed" and second["gate"] == "length-bound" and second["findings"] == 2
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00", first["at"])


def test_new_run_id_carries_the_kind_a_utc_stamp_and_a_suffix():
    run_id = new_run_id("brief")

    assert re.fullmatch(r"brief-\d{8}-\d{6}-[0-9a-f]{4}", run_id), run_id
    assert new_run_id("survey").startswith("survey-")
