"""Regression: the command printed by the legacy-CLI refusal paths is invocable.

Both legacy entry points refuse a Workspace owned by current ResearchHarness
state (`.harness-v3`) and print a single onward command. That printed command is
the user's only exit path, so it must actually exist in the current CLI.

The failure mode this guards against is a printed command that does not parse:
the CLI exposes `{loop, workflow}`, so an advertised subcommand outside that set
leaves every user who trips the guard holding a dead command.

These tests drive the REAL refusal paths (not a string constant), extract the
advertised `python -m research_harness ...` invocation from the emitted message,
and then EXECUTE it as a subprocess to prove the command parses and is
dispatchable.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# The advertised invocation, e.g. "python -m research_harness loop work ...".
_ADVERTISED = re.compile(r"python -m research_harness ([a-z]+(?: [a-z]+)?)")


def _advertised_command(message: str) -> list[str]:
    match = _ADVERTISED.search(message)
    assert match is not None, f"no `python -m research_harness ...` guidance found in: {message!r}"
    return match.group(1).split()


def _run_cli(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "research_harness", *argv, "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _harness_v3_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".harness-v3").mkdir()
    return workspace


def test_product_cli_refusal_advertises_an_invocable_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tooling.product_cli import _is_current_harness_workspace

    workspace = _harness_v3_workspace(tmp_path)
    # Drive the real guard: it must refuse this workspace...
    assert _is_current_harness_workspace(str(workspace)) is True
    message = capsys.readouterr().err
    assert ".harness-v3" in message, message

    # ...and the command it hands the user must actually run.
    argv = _advertised_command(message)
    assert argv[0] != "run", f"advertises the removed `run` group: {argv}"
    result = _run_cli(argv)
    assert result.returncode == 0, (
        f"advertised command {argv} is not invocable:\n{result.stderr}"
    )
    assert "invalid choice" not in result.stderr, result.stderr


def test_pipeline_cli_refusal_advertises_an_invocable_command(tmp_path: Path) -> None:
    from scripts.pipeline import _require_no_current_harness_state

    workspace = _harness_v3_workspace(tmp_path)
    # Drive the real guard: it must refuse this workspace...
    with pytest.raises(SystemExit) as excinfo:
        _require_no_current_harness_state(workspace)
    message = str(excinfo.value)
    assert ".harness-v3" in message, message

    # ...and the command it hands the user must actually run.
    argv = _advertised_command(message)
    assert argv[0] != "run", f"advertises the removed `run` group: {argv}"
    result = _run_cli(argv)
    assert result.returncode == 0, (
        f"advertised command {argv} is not invocable:\n{result.stderr}"
    )
    assert "invalid choice" not in result.stderr, result.stderr


def test_removed_run_group_is_still_absent_from_the_cli() -> None:
    # Held-out guard: if `run` is ever reintroduced, the guidance above should be
    # revisited deliberately rather than silently becoming valid again.
    result = _run_cli(["run"])
    assert result.returncode != 0, "`run` unexpectedly dispatches; revisit the refusal guidance"
    assert "invalid choice" in result.stderr, result.stderr
