"""Unit tests for the execution-snapshot process-scoped validation cache.

These pin the latency optimization: a second `materialize_execution_snapshot`
call for an already-materialized `(target, revision)` skips the redundant
byte-level re-hash when the read-only tree's stat fingerprint is unchanged, but
STILL detects tampering (fingerprint drift falls back to full validation), and a
fresh process (cleared cache) always performs the full cross-process re-hash.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import research_harness.engine._execution_snapshot as snap
from research_harness.engine._execution_snapshot import (
    _STATE_DIR,
    materialize_execution_snapshot,
)


def _component(repo_root: Path, rel: str, body: bytes) -> dict[str, object]:
    path = repo_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {
        "path": rel,
        "sha256": hashlib.sha256(body).hexdigest(),
        "size": len(body),
    }


def _components_and_revision(repo_root: Path) -> tuple[list[dict[str, object]], str]:
    records = [
        _component(repo_root, ".codex/skills/demo/SKILL.md", b"# demo skill\n"),
        _component(repo_root, ".codex/skills/demo/scripts/run.py", b"print('demo')\n"),
    ]
    records.sort(key=lambda r: r["path"])
    canonical = json.dumps(
        records, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    revision = hashlib.sha256(canonical).hexdigest()
    return records, revision


@pytest.fixture(autouse=True)
def _clear_cache_and_perms(tmp_path: Path):
    snap._VALIDATED_SNAPSHOTS.clear()
    yield
    snap._VALIDATED_SNAPSHOTS.clear()
    for execution_root in tmp_path.rglob(f"{_STATE_DIR}/execution"):
        for candidate in execution_root.rglob("*"):
            if candidate.is_symlink():
                continue
            candidate.chmod(0o700 if candidate.is_dir() else 0o600)
        execution_root.chmod(0o700)


def _make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    (workspace / _STATE_DIR).mkdir(parents=True)
    return workspace


def test_second_materialize_returns_same_target_and_skips_rehash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workspace = _make_workspace(tmp_path)
    records, revision = _components_and_revision(repo_root)

    first = materialize_execution_snapshot(
        workspace=workspace, repo_root=repo_root,
        revision_id=revision, components=records,
    )
    # The warm path must be cached now; count byte-hash calls on the 2nd compose.
    calls = {"n": 0}
    real_sha = snap._sha256

    def counting_sha(path: Path) -> str:
        calls["n"] += 1
        return real_sha(path)

    monkeypatch.setattr(snap, "_sha256", counting_sha)
    second = materialize_execution_snapshot(
        workspace=workspace, repo_root=repo_root,
        revision_id=revision, components=records,
    )
    assert first == second
    assert calls["n"] == 0, "warm re-validation should skip the per-file byte re-hash"


def test_tampering_is_detected_even_with_a_warm_cache(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workspace = _make_workspace(tmp_path)
    records, revision = _components_and_revision(repo_root)

    target = materialize_execution_snapshot(
        workspace=workspace, repo_root=repo_root,
        revision_id=revision, components=records,
    )
    # warm the cache
    materialize_execution_snapshot(
        workspace=workspace, repo_root=repo_root,
        revision_id=revision, components=records,
    )
    # Tamper: rewrite a snapshot file's bytes (same length so size matches),
    # which necessarily changes mtime_ns -> fingerprint drift -> full re-hash.
    victim = target / ".codex" / "skills" / "demo" / "scripts" / "run.py"
    victim.chmod(0o644)
    original = victim.read_bytes()
    tampered = b"print('evil')" + b" " * (len(original) - len(b"print('evil')"))
    assert len(tampered) == len(original)
    victim.write_bytes(tampered)
    victim.chmod(0o444)

    with pytest.raises(ValueError, match="inconsistent|incomplete|unsafe"):
        materialize_execution_snapshot(
            workspace=workspace, repo_root=repo_root,
            revision_id=revision, components=records,
        )


def test_fresh_process_cache_forces_full_rehash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workspace = _make_workspace(tmp_path)
    records, revision = _components_and_revision(repo_root)

    materialize_execution_snapshot(
        workspace=workspace, repo_root=repo_root,
        revision_id=revision, components=records,
    )
    # Simulate a fresh process: empty the module cache.
    snap._VALIDATED_SNAPSHOTS.clear()

    calls = {"n": 0}
    real_sha = snap._sha256

    def counting_sha(path: Path) -> str:
        calls["n"] += 1
        return real_sha(path)

    monkeypatch.setattr(snap, "_sha256", counting_sha)
    materialize_execution_snapshot(
        workspace=workspace, repo_root=repo_root,
        revision_id=revision, components=records,
    )
    assert calls["n"] == len(records), (
        "a cold cache must re-hash every component (cross-process tamper detection)"
    )
