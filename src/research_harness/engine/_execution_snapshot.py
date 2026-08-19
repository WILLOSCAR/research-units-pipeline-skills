"""Immutable, revision-addressed execution trees for repository Skills.

The canonical Run stores business state and a Kernel revision.  This private
module turns that revision's component manifest into a repo-shaped execution
tree so subprocess adapters never retain mutable source-checkout paths.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_STATE_DIR = ".harness-v3"
_EXECUTION_DIR = "execution"


@dataclass(frozen=True, slots=True)
class _Component:
    path: PurePosixPath
    sha256: str
    size: int

    @property
    def text_path(self) -> str:
        return self.path.as_posix()


def materialize_execution_snapshot(
    *,
    workspace: Path,
    repo_root: Path,
    revision_id: str,
    components: object,
) -> Path:
    """Return an immutable repo tree containing exactly ``components``.

    Publication is atomic.  Every source file is read once and the copied bytes
    must match the already-pinned digest and size; a checkout mutation during
    materialization therefore either preserves the pinned revision or fails
    closed.
    """

    revision = str(revision_id or "")
    if not _DIGEST.fullmatch(revision):
        raise ValueError("Kernel revision must be a SHA-256 digest.")
    records, canonical = _validated_components(components)
    if hashlib.sha256(canonical).hexdigest() != revision:
        raise ValueError("Execution components do not identify the Kernel revision.")

    workspace_root = Path(workspace).expanduser().resolve(strict=True)
    source_root = Path(repo_root).expanduser().resolve(strict=True)
    if not workspace_root.is_dir() or not source_root.is_dir():
        raise ValueError("Execution snapshot roots must be directories.")

    state_root = workspace_root / _STATE_DIR
    if state_root.is_symlink() or not state_root.is_dir():
        raise ValueError("Harness state directory is missing or unsafe.")
    execution_root = state_root / _EXECUTION_DIR
    _ensure_private_directory(execution_root)
    target = execution_root / revision
    if target.is_symlink():
        raise ValueError("Execution snapshot path is unsafe.")
    if target.exists():
        _validate_snapshot(target, records)
        return target.resolve(strict=True)

    temporary = Path(
        tempfile.mkdtemp(prefix=f".{revision}.", suffix=".tmp", dir=execution_root)
    )
    published = False
    try:
        for record in records:
            content, mode = _read_pinned_source(source_root, record)
            destination = temporary.joinpath(*record.path.parts)
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            _write_snapshot_file(destination, content, mode=mode)
        _validate_snapshot(temporary, records)
        _make_tree_read_only(temporary)
        _fsync_directory_tree(temporary)
        try:
            os.rename(temporary, target)
            published = True
            _fsync_directory(execution_root)
        except OSError:
            if target.is_symlink() or not target.is_dir():
                raise
            _validate_snapshot(target, records)
        return target.resolve(strict=True)
    finally:
        if not published and temporary.exists():
            _remove_private_tree(temporary)


def _validated_components(
    value: object,
) -> tuple[tuple[_Component, ...], bytes]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise ValueError("Execution component manifest must be a list.")
    raw_records = list(value)
    if not raw_records:
        raise ValueError("Execution component manifest must be non-empty.")
    components: list[_Component] = []
    previous = ""
    for raw in raw_records:
        if not isinstance(raw, Mapping) or set(raw) != {"path", "sha256", "size"}:
            raise ValueError("Execution component record is malformed.")
        raw_path = raw["path"]
        digest = raw["sha256"]
        size = raw["size"]
        if not isinstance(raw_path, str) or not _safe_relative_path(raw_path):
            raise ValueError("Execution component path is unsafe.")
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise ValueError("Execution component digest is malformed.")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError("Execution component size is malformed.")
        if raw_path <= previous:
            raise ValueError("Execution component paths must be unique and sorted.")
        previous = raw_path
        components.append(
            _Component(path=PurePosixPath(raw_path), sha256=digest, size=size)
        )
    canonical = json.dumps(
        raw_records,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return tuple(components), canonical


def _safe_relative_path(value: str) -> bool:
    if not value or "\\" in value or any(ord(character) < 32 for character in value):
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and path.as_posix() == value
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _ensure_private_directory(path: Path) -> None:
    if path.is_symlink():
        raise ValueError("Execution snapshot directory is unsafe.")
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        pass
    if path.is_symlink() or not path.is_dir():
        raise ValueError("Execution snapshot directory is unsafe.")


def _read_pinned_source(root: Path, component: _Component) -> tuple[bytes, int]:
    source = root.joinpath(*component.path.parts)
    if source.is_symlink():
        raise ValueError(
            f"Pinned runtime component is a symbolic link: {component.text_path}"
        )
    try:
        resolved = source.resolve(strict=True)
        resolved.relative_to(root)
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError(
            f"Pinned runtime component is missing or unsafe: {component.text_path}"
        ) from exc

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        raise ValueError(
            f"Pinned runtime component cannot be opened: {component.text_path}"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(
                f"Pinned runtime component is not a file: {component.text_path}"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            content = handle.read()
    finally:
        os.close(descriptor)
    if (
        len(content) != component.size
        or hashlib.sha256(content).hexdigest() != component.sha256
    ):
        raise ValueError(
            f"Pinned runtime component changed during compose: {component.text_path}"
        )
    return content, stat.S_IMODE(metadata.st_mode)


def _write_snapshot_file(path: Path, content: bytes, *, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, mode & 0o777)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validate_snapshot(root: Path, records: tuple[_Component, ...]) -> None:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Execution snapshot is missing or unsafe.")
    expected = {record.text_path: record for record in records}
    actual: set[str] = set()
    for candidate in root.rglob("*"):
        relative = candidate.relative_to(root).as_posix()
        if candidate.is_symlink():
            raise ValueError(f"Execution snapshot contains a link: {relative}")
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise ValueError(f"Execution snapshot contains an unsafe entry: {relative}")
        actual.add(relative)
        record = expected.get(relative)
        if record is None:
            raise ValueError(f"Execution snapshot contains an extra file: {relative}")
        if (
            candidate.stat().st_size != record.size
            or _sha256(candidate) != record.sha256
        ):
            raise ValueError(f"Execution snapshot file is inconsistent: {relative}")
    if actual != set(expected):
        raise ValueError("Execution snapshot is incomplete.")


def _make_tree_read_only(root: Path) -> None:
    files: list[Path] = []
    directories: list[Path] = [root]
    for candidate in root.rglob("*"):
        (directories if candidate.is_dir() else files).append(candidate)
    for path in files:
        path.chmod(0o444 | (path.stat().st_mode & 0o111))
    for path in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o555)


def _fsync_directory_tree(root: Path) -> None:
    directories = [root]
    directories.extend(candidate for candidate in root.rglob("*") if candidate.is_dir())
    for directory in sorted(
        directories, key=lambda item: len(item.parts), reverse=True
    ):
        _fsync_directory(directory)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _remove_private_tree(path: Path) -> None:
    for candidate in path.rglob("*"):
        if candidate.is_dir():
            candidate.chmod(0o700)
        else:
            candidate.chmod(0o600)
    path.chmod(0o700)
    shutil.rmtree(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
