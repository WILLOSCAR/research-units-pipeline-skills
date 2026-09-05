"""Leaf-level provenance and identity primitives.

These are the pure, stdlib-only helpers the Run state layer stamps into its
durable provenance records: content fingerprints (file and directory SHA-256,
implementation and Checkpoint-review fingerprints), the Checkpoint decisions
projection they normalize over, git revision reads, workspace-relative path
formatting, and fresh record identifiers. They hold no shared mutable state and
depend only on the filesystem, git, and the standard library, so they are kept
separate from the mutation helpers in ``tooling.run_state`` (which re-exports
them to preserve its public surface).
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any


def _path_fingerprint(path: Path) -> dict[str, Any]:
    if path.is_dir():
        files = sorted(item for item in path.rglob("*") if item.is_file())
        digest = hashlib.sha256()
        for item in files:
            digest.update(str(item.relative_to(path)).encode("utf-8"))
            digest.update(_file_sha256(item).encode("ascii"))
        return {"type": "directory", "file_count": len(files), "sha256": digest.hexdigest()}
    return {"type": "file", "size": path.stat().st_size, "sha256": _file_sha256(path)}


def _checkpoint_artifact_fingerprint(
    *,
    path: Path,
    relpath: str,
    checkpoint: str,
) -> dict[str, Any]:
    if relpath != "DECISIONS.md" or not path.is_file():
        return _path_fingerprint(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    normalized = _checkpoint_decisions_projection(text, checkpoint=checkpoint).encode("utf-8")
    return {
        "type": "file",
        "size": len(normalized),
        "sha256": hashlib.sha256(normalized).hexdigest(),
        "normalization": "checkpoint-block-and-approval-checkbox-insensitive",
    }


def _checkpoint_decisions_projection(text: str, *, checkpoint: str) -> str:
    """Project only one Checkpoint block so later Decisions do not stale earlier approval."""

    block_match = re.search(
        rf"<!-- BEGIN CHECKPOINT:{re.escape(checkpoint)} -->(.*?)<!-- END CHECKPOINT:{re.escape(checkpoint)} -->",
        text,
        flags=re.DOTALL,
    )
    if block_match is None:
        return ""
    approval_match = re.search(
        rf"^(\s*-\s*)\[[ xX]\](\s*(?:Approve\s+)?{re.escape(checkpoint)}\b.*)$",
        text,
        flags=re.MULTILINE,
    )
    approval = ""
    if approval_match is not None:
        approval = f"{approval_match.group(1)}[ ]{approval_match.group(2)}"
    return f"{approval}\n{block_match.group(0).strip()}\n"


def implementation_fingerprint(path: Path) -> dict[str, Any]:
    files = sorted(
        item
        for item in path.rglob("*")
        if item.is_file()
        and "__pycache__" not in item.parts
        and item.suffix not in {".pyc", ".pyo"}
    )
    digest = hashlib.sha256()
    for item in files:
        digest.update(str(item.relative_to(path)).encode("utf-8"))
        digest.update(bytes.fromhex(_file_sha256(item)))
    return {"file_count": len(files), "sha256": digest.hexdigest()}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_output(repo_root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _relative_or_absolute(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
