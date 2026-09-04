"""Regression: the execution snapshot must include the assets a skill reads.

`tooling/source_text_hygiene.py` loads `<repo_root>/assets/limitation-signals.json`
at use time, and skills that call `has_limitation_signal` (paper-notes,
evidence-draft, writer-context-pack) execute from the immutable execution
snapshot. If that asset is not pinned into the snapshot, those skills crash with
FileNotFoundError under the snapshot even though they work from a live checkout.

This test drives a workflow that includes `paper-notes` far enough to execute it
from the snapshot, and asserts the asset is materialized into the snapshot tree.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from research_harness._local_runtime import (
    compose_repository_engine,
    initialize_repository_run,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _copy_repository(destination: Path) -> Path:
    shutil.copytree(
        REPO_ROOT,
        destination,
        ignore=shutil.ignore_patterns(
            ".git", ".venv", ".pytest_cache", "__pycache__", "workspaces", ".scratch",
        ),
    )
    return destination


def test_execution_snapshot_includes_limitation_signal_asset(tmp_path: Path) -> None:
    repo_copy = _copy_repository(tmp_path / "repo")
    workspace = tmp_path / "workspace"
    # idea-brainstorm includes paper-notes, which transitively reads
    # assets/limitation-signals.json via tooling.source_text_hygiene.
    initialize_repository_run(
        workspace=workspace,
        repo_root=repo_copy,
        pipeline="idea-brainstorm",
        request="Brainstorm research directions on test-time adaptation.",
        run_id="asset-pin-regression",
    )
    compose_repository_engine(workspace=workspace, repo_root=repo_copy)

    execution = workspace / ".harness-v3" / "execution"
    snapshots = [p for p in execution.iterdir() if p.is_dir()] if execution.is_dir() else []
    assert snapshots, "no execution snapshot was materialized"
    for snap in snapshots:
        asset = snap / "assets" / "limitation-signals.json"
        assert asset.is_file(), (
            f"execution snapshot {snap.name} is missing assets/limitation-signals.json; "
            "skills that call has_limitation_signal (paper-notes, evidence-draft, "
            "writer-context-pack) would crash with FileNotFoundError from the snapshot"
        )
        # sanity: the pinned bytes match the live checkout
        assert asset.read_bytes() == (repo_copy / "assets" / "limitation-signals.json").read_bytes()
