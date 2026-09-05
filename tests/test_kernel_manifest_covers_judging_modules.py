"""Regression: the Kernel manifest covers every module that judges a Run.

ADR 0013 ("All quality-domain modules belong to `HARNESS_KERNEL_PATHS` because
they judge whether a Run may pass") and ADR 0020 ("compare its complete Kernel
manifest with the executing checkout ... a missing, unexpected, malformed, or
hash-mismatched Kernel entry is `DRIFT`") together require that anything
deciding whether a Run passes is pinned and drift-checked.

The risk these guard is extraction: load-bearing logic moving out of an
already-pinned kernel file into a module that never joins the manifest, and the
default quality provider living in `acceptance/native.py`. An unpinned module
could then change with NO drift detected on an active `harness-lock.v2` Run,
defeating ADR 0020's fail-closed guarantee.

These tests assert (a) each module is pinned, and (b) editing any of them makes
a real, initialized Run refuse to execute — with the refusal landing BEFORE any
Attempt is recorded, so a drifted Kernel can never produce new provenance.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.harness_contracts import HARNESS_KERNEL_PATHS

# The modules that decide whether a Run may pass, extracted out of previously
# pinned kernel files (or newly made the runtime default judge).
JUDGING_MODULES = (
    "tooling/provenance_primitives.py",
    "tooling/run_state_io.py",
    "tooling/run_audit_diff.py",
    "tooling/improvement_report.py",
    "src/research_harness/acceptance/native.py",
)


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *argv],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize("relpath", JUDGING_MODULES)
def test_judging_module_is_pinned_in_the_kernel_manifest(relpath: str) -> None:
    assert relpath in HARNESS_KERNEL_PATHS, (
        f"{relpath} judges whether a Run may pass but is absent from "
        "HARNESS_KERNEL_PATHS, so ADR 0020 cannot detect drift in it"
    )


def test_every_manifest_entry_exists_on_disk() -> None:
    missing = [p for p in HARNESS_KERNEL_PATHS if not (REPO_ROOT / p).is_file()]
    assert missing == [], f"manifest pins non-existent paths: {missing}"


@pytest.mark.parametrize("relpath", JUDGING_MODULES)
def test_editing_a_judging_module_drifts_the_run_before_any_attempt(
    tmp_path: Path, relpath: str
) -> None:
    workspace = tmp_path / "run"
    initialized = _run(
        "scripts/pipeline.py", "init",
        "--workspace", str(workspace),
        "--pipeline", "research-brief",
    )
    assert initialized.returncode == 0, initialized.stderr or initialized.stdout

    lock_path = workspace / ".harness" / "harness.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    # The freshly-built lock must already pin this judging module.
    assert relpath in lock["kernel"], f"{relpath} not pinned into a new Run's lock"

    # Simulate an edit to the module that judges the Run.
    lock["kernel"][relpath] = "0" * 64
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")

    result = _run("scripts/pipeline.py", "run-one", "--workspace", str(workspace))

    assert result.returncode == 2, result.stdout or result.stderr
    assert "Harness Kernel drift" in (result.stderr or result.stdout)
    # Fail-closed ordering: the refusal precedes any new provenance.
    assert _jsonl(workspace / ".harness" / "attempts.jsonl") == []
    assert _jsonl(workspace / ".harness" / "decisions.jsonl") == []
