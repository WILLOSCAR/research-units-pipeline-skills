from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def make_execution_snapshots_removable(tmp_path: Path):
    """Restore owner write bits so pytest can remove read-only snapshot trees."""

    yield
    for execution_root in tmp_path.rglob(".harness-v3/execution"):
        for candidate in execution_root.rglob("*"):
            if candidate.is_symlink():
                continue
            candidate.chmod(0o700 if candidate.is_dir() else 0o600)
        execution_root.chmod(0o700)
