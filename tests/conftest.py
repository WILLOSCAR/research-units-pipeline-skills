from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def ensure_repository_workspace_root() -> None:
    """Keep repo-local Workspace integration tests self-contained in clean clones."""

    (REPO_ROOT / "workspaces").mkdir(parents=True, exist_ok=True)
