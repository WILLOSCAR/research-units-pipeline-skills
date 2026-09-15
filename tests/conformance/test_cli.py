"""The ``rh`` command drives the same surface as the API."""

from __future__ import annotations

import json
from pathlib import Path

from agent_stub import FIXTURES, GOAL, Agent, fresh

from rh.api import Harness
from rh.cli import main


def rh(tmp_path: Path, *argv: str, as_json: bool = False, capsys=None) -> str:
    base = ["-w", str(tmp_path / "ws"), "--skills", str(FIXTURES / "skills"), "--kinds", str(FIXTURES / "kinds"), "--project", str(tmp_path / "project")]
    if as_json:
        base.append("--json")
    code = main([*base, *argv])
    out = capsys.readouterr()
    assert code == 0, out.err
    return out.out


def test_cli_walks_a_run_to_completion(tmp_path, capsys):
    goal = tmp_path / "goal.md"
    goal.write_text(GOAL)
    out = rh(tmp_path, "start", "--goal", str(goal), "--kind", "brief-fixture", capsys=capsys)
    assert out.startswith("PROGRESSED") and "packet:" in out

    harness = Harness(tmp_path / "ws", skills_root=FIXTURES / "skills", kinds_dir=FIXTURES / "kinds", project=tmp_path / "project")
    agent = Agent(harness)
    outcome = agent.drive(harness.continue_())
    assert outcome.decision["id"] == "D0"

    listing = rh(tmp_path, "inspect", capsys=capsys)
    assert "pending Decision D0" in listing and "spec" in listing

    out = rh(tmp_path, "decide", "D0", "--accept", "--by", "logic", as_json=True, capsys=capsys)
    assert json.loads(out)["kind"] == "PROGRESSED"
    outcome = agent.drive(harness.continue_())
    assert outcome.decision["id"] == "D-final"

    out = rh(tmp_path, "decide", "D-final", "--accept", capsys=capsys)
    assert out.startswith("COMPLETED") and "artifact proof_pack" in out
    out = rh(tmp_path, "lessons", "list", capsys=capsys)
    assert "completed" in out
    out = rh(tmp_path, "lessons", "list", as_json=True, capsys=capsys)
    assert json.loads(out)[0]["status"] == "completed"


def test_cli_reports_errors_on_stderr(tmp_path, capsys):
    code = main(["-w", str(tmp_path / "nowhere"), "inspect"])
    err = capsys.readouterr().err
    assert code == 2 and err.startswith("rh: ")


def test_cli_lists_kinds(tmp_path, capsys):
    out = rh(tmp_path, "kinds", capsys=capsys)
    assert "brief-fixture" in out
    rows = json.loads(rh(tmp_path, "kinds", as_json=True, capsys=capsys))
    assert {r["kind"] for r in rows} == {"brief-fixture", "review-fixture"} and rows[0]["deliverable"] == "brief.md"
    assert fresh  # the stub stays importable for other CLI tests
