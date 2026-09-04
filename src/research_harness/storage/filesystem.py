from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable, Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - production local storage targets POSIX.
    fcntl = None  # type: ignore[assignment]

from research_harness.domain.checkpoints import checkpoint_decisions_projection
from research_harness.domain.model import (
    ArtifactEvidence,
    CheckpointReviewBasis,
    CompletionManifest,
    ManifestStatus,
    RunAggregate,
)

from .codecs import (
    decode_completion_manifest,
    decode_run_aggregate,
    encode_completion_manifest,
    encode_run_aggregate,
)
from .errors import (
    ArtifactChangedError,
    ConcurrentStorageInvocationError,
    ConcurrentStorageWriteError,
    InvalidArtifactPathError,
    InvalidManifestTransitionError,
    ManifestConflictError,
    ManifestNotFoundError,
    StorageConfigurationError,
    StorageCorruptionError,
    StorageIdentityError,
    StorageIOError,
)


_STATE_DIR = ".harness-v3"
_STATE_FILE = "state.json"
_LOCK_FILE = "invocation.lock"
_MANIFEST_DIR = "manifests"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


class FilesystemRunLedger:
    """One atomic canonical Run aggregate plus a POSIX workspace lock."""

    def __init__(self, workspace: str | os.PathLike[str]) -> None:
        self.workspace = _workspace_path(workspace)
        self.state_root = self.workspace / _STATE_DIR
        self._lock_guard = threading.Lock()
        self._lock_owner: int | None = None
        self._lock_depth = 0
        self._lock_run_id = ""

    @contextmanager
    def lock(self, run_id: str, operation: str) -> Iterator[None]:
        run_id = _safe_text(run_id, "run_id")
        operation = _safe_text(operation, "operation")
        thread_id = threading.get_ident()
        with self._lock_guard:
            if self._lock_owner == thread_id:
                if self._lock_run_id != run_id:
                    raise StorageIdentityError(
                        "A nested storage lock cannot change the Run identity."
                    )
                self._lock_depth += 1
                nested = True
            else:
                nested = False

        if nested:
            try:
                yield
            finally:
                with self._lock_guard:
                    self._lock_depth -= 1
            return

        if fcntl is None:
            raise StorageConfigurationError(
                "FilesystemRunLedger requires POSIX fcntl locking."
            )
        root = _ensure_state_root(self.workspace, self.state_root)
        lock_path = root / _LOCK_FILE
        descriptor = _open_lock_file(lock_path)
        handle = os.fdopen(descriptor, "a+b", closefd=True)
        acquired = False
        try:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ConcurrentStorageInvocationError(
                    run_id=run_id, operation=operation
                ) from exc
            acquired = True
            with self._lock_guard:
                if self._lock_owner is not None:
                    raise ConcurrentStorageInvocationError(
                        run_id=run_id, operation=operation
                    )
                self._lock_owner = thread_id
                self._lock_depth = 1
                self._lock_run_id = run_id
            yield
        finally:
            if acquired:
                with self._lock_guard:
                    if self._lock_owner == thread_id:
                        self._lock_depth -= 1
                        if self._lock_depth == 0:
                            self._lock_owner = None
                            self._lock_run_id = ""
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
            handle.close()

    def current_run_id(self) -> str | None:
        """Read the sole aggregate identity without a mutable pointer file."""

        run = self._read_state()
        return run.id if run is not None else None

    def load(self, run_id: str) -> RunAggregate | None:
        run_id = _safe_text(run_id, "run_id")
        run = self._read_state()
        if run is None:
            return None
        if run.id != run_id:
            raise StorageIdentityError(
                f"Workspace is bound to Run {run.id}, not requested Run {run_id}."
            )
        return run

    def save(self, run: RunAggregate, *, expected_version: int) -> None:
        if not isinstance(run, RunAggregate):
            raise TypeError("run must be a RunAggregate")
        if not isinstance(expected_version, int) or isinstance(expected_version, bool):
            raise TypeError("expected_version must be an integer")
        if expected_version < 0:
            raise ValueError("expected_version must not be negative")

        current = self._read_state()
        if current is None:
            if expected_version != 0:
                raise ConcurrentStorageWriteError(
                    f"Run {run.id} does not exist at expected version {expected_version}.",
                    run_id=run.id,
                )
            current_version = 0
        else:
            if current.id != run.id:
                raise StorageIdentityError(
                    f"Workspace already contains canonical Run {current.id}; Run {run.id} cannot replace it."
                )
            current_version = current.version
            if current_version != expected_version:
                raise ConcurrentStorageWriteError(
                    f"Run {run.id} changed from version {expected_version} to {current_version}.",
                    run_id=run.id,
                )
            if run.events[:current_version] != current.events:
                raise ConcurrentStorageWriteError(
                    f"Run {run.id} attempted to rewrite append-only Event history.",
                    run_id=run.id,
                )

        if run.version <= current_version:
            raise ConcurrentStorageWriteError(
                f"Run {run.id} save must append at least one Event.", run_id=run.id
            )
        payload = encode_run_aggregate(run)
        _atomic_write_json(self._state_path(create=True), payload)

    def _state_path(self, *, create: bool) -> Path:
        root = (
            _ensure_state_root(self.workspace, self.state_root)
            if create
            else _existing_state_root(self.workspace, self.state_root)
        )
        return root / _STATE_FILE

    def _read_state(self) -> RunAggregate | None:
        state_path = self._state_path(create=False)
        payload = _read_json_object(state_path)
        if payload is None:
            return None
        return decode_run_aggregate(payload)


class FilesystemArtifacts:
    """Workspace Artifact fingerprints and atomic Completion Manifests."""

    def __init__(self, workspace: str | os.PathLike[str]) -> None:
        self.workspace = _workspace_path(workspace)
        self.state_root = self.workspace / _STATE_DIR

    def snapshot(
        self, run_id: str, paths: Iterable[str]
    ) -> tuple[ArtifactEvidence, ...]:
        _safe_text(run_id, "run_id")
        evidence: list[ArtifactEvidence] = []
        for raw_path in paths:
            display, path = self._artifact_path(raw_path)
            item = self._fingerprint(display, path)
            if item is not None:
                evidence.append(item)
        return tuple(evidence)

    def checkpoint_review_basis(
        self,
        *,
        run_id: str,
        checkpoint: str,
        unit_id: str,
        paths: Iterable[str],
    ) -> CheckpointReviewBasis:
        _safe_text(run_id, "run_id")
        checkpoint = _safe_text(checkpoint, "checkpoint")
        unit_id = _safe_text(unit_id, "unit_id")
        evidence: list[ArtifactEvidence] = []
        approved = False
        for raw_path in paths:
            display, path = self._artifact_path(raw_path)
            if not path.exists():
                continue
            if display == "DECISIONS.md":
                if not path.is_file():
                    raise InvalidArtifactPathError(
                        "DECISIONS.md must be a regular file."
                    )
                try:
                    content = path.read_bytes().decode("utf-8", errors="replace")
                except OSError as exc:
                    raise StorageIOError(
                        "Could not read checkpoint decisions evidence."
                    ) from exc
                projected, approved = checkpoint_decisions_projection(
                    content, checkpoint=checkpoint
                )
                if projected:
                    evidence.append(
                        _fingerprint_bytes(
                            path=display,
                            content=projected.encode("utf-8"),
                            normalization=(
                                "checkpoint-block-and-approval-checkbox-insensitive.v1"
                            ),
                        )
                    )
                continue
            item = self._fingerprint(display, path)
            if item is not None:
                evidence.append(item)
        return CheckpointReviewBasis(
            checkpoint=checkpoint,
            unit_id=unit_id,
            artifacts=tuple(evidence),
            approved=approved,
        )

    def write_manifest(self, manifest: CompletionManifest) -> None:
        payload = encode_completion_manifest(manifest)
        path = self._manifest_path(manifest.id, create=True)
        existing = _read_json_object(path)
        if existing is not None:
            decoded = decode_completion_manifest(existing)
            if decoded == manifest:
                return
            raise ManifestConflictError(
                f"Manifest {manifest.id} already exists with different evidence."
            )
        _atomic_write_json(path, payload)

    def read_manifest(self, manifest_id: str) -> CompletionManifest | None:
        path = self._manifest_path(manifest_id, create=False)
        payload = _read_json_object(path)
        return decode_completion_manifest(payload) if payload is not None else None

    def list_manifests(self, run_id: str) -> tuple[CompletionManifest, ...]:
        run_id = _safe_text(run_id, "run_id")
        directory = self._manifest_directory(create=False)
        if not directory.exists():
            return ()
        manifests: list[CompletionManifest] = []
        try:
            paths = sorted(directory.glob("*.json"), key=lambda item: item.name)
        except OSError as exc:
            raise StorageIOError("Could not list Completion Manifests.") from exc
        for path in paths:
            payload = _read_json_object(path)
            if payload is None:
                continue
            manifest = decode_completion_manifest(payload)
            if path.name != f"{manifest.id}.json":
                raise StorageCorruptionError(
                    "Completion Manifest filename disagrees with its identity."
                )
            if manifest.run_id == run_id:
                manifests.append(manifest)
        return tuple(manifests)

    def set_manifest_status(self, manifest_id: str, status: ManifestStatus) -> None:
        if not isinstance(status, ManifestStatus):
            raise TypeError("status must be a ManifestStatus")
        manifest = self.read_manifest(manifest_id)
        if manifest is None:
            raise ManifestNotFoundError(f"Unknown Manifest {manifest_id}")
        if manifest.status is status:
            return
        if manifest.status is ManifestStatus.BLOCKED and status is ManifestStatus.DONE:
            raise InvalidManifestTransitionError(
                f"Blocked Manifest {manifest_id} cannot become DONE."
            )
        _atomic_write_json(
            self._manifest_path(manifest_id, create=True),
            encode_completion_manifest(replace(manifest, status=status)),
        )

    def _manifest_directory(self, *, create: bool) -> Path:
        root = (
            _ensure_state_root(self.workspace, self.state_root)
            if create
            else _existing_state_root(self.workspace, self.state_root)
        )
        directory = root / _MANIFEST_DIR
        if create:
            _ensure_directory(directory, within=root)
        elif directory.exists() and (directory.is_symlink() or not directory.is_dir()):
            raise StorageConfigurationError(
                "The Completion Manifest storage path is not a safe directory."
            )
        return directory

    def _manifest_path(self, manifest_id: str, *, create: bool) -> Path:
        manifest_id = _safe_identifier(manifest_id, "manifest_id")
        return self._manifest_directory(create=create) / f"{manifest_id}.json"

    def _artifact_path(self, raw_path: str) -> tuple[str, Path]:
        if not isinstance(raw_path, str):
            raise InvalidArtifactPathError("Artifact path must be a string.")
        display = raw_path
        if (
            not display
            or display == "."
            or "\\" in display
            or ";" in display
            or any(
                ord(character) < 32 or ord(character) == 127 for character in display
            )
        ):
            raise InvalidArtifactPathError("Artifact path must be a safe POSIX path.")
        if display.startswith("?"):
            raise InvalidArtifactPathError(
                "Artifact path must not include an optional-output marker."
            )
        raw_parts = display.split("/")
        if display.endswith("/"):
            raw_parts = raw_parts[:-1]
        if not raw_parts or any(part in {"", ".", ".."} for part in raw_parts):
            raise InvalidArtifactPathError(
                "Artifact path contains an empty or traversal segment."
            )
        windows = PureWindowsPath(display)
        posix = PurePosixPath(display.rstrip("/"))
        if windows.is_absolute() or windows.drive or posix.is_absolute():
            raise InvalidArtifactPathError(
                "Artifact path must remain inside the Workspace."
            )
        if posix.parts and posix.parts[0] == _STATE_DIR:
            raise InvalidArtifactPathError("Harness storage is not an Artifact.")
        candidate = self.workspace.joinpath(*posix.parts)
        resolved = _resolve_inside_workspace(
            candidate,
            workspace=self.workspace,
            state_root=self.state_root,
            label="Artifact",
        )
        return display, resolved

    def _fingerprint(self, display: str, path: Path) -> ArtifactEvidence | None:
        if not path.exists():
            return None
        if path.is_file():
            digest, size = _hash_file_stably(path)
            return ArtifactEvidence(path=display, sha256=digest, size=size)
        if path.is_dir():
            digest, size = _hash_directory_stably(
                path,
                workspace=self.workspace,
                state_root=self.state_root,
                ancestry=frozenset(),
            )
            return ArtifactEvidence(
                path=display,
                sha256=digest,
                size=size,
                normalization="directory-tree-sha256.v1",
            )
        raise InvalidArtifactPathError(
            f"Artifact {display!r} is not a regular file or directory."
        )


def _workspace_path(workspace: str | os.PathLike[str]) -> Path:
    try:
        path = Path(workspace).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise StorageConfigurationError(
            "Workspace does not exist or cannot be resolved."
        ) from exc
    if not path.is_dir():
        raise StorageConfigurationError("Workspace must be an existing directory.")
    return path


def _existing_state_root(workspace: Path, state_root: Path) -> Path:
    if not state_root.exists() and not state_root.is_symlink():
        return state_root
    if state_root.is_symlink() or not state_root.is_dir():
        raise StorageConfigurationError(
            ".harness-v3 must be a real Workspace directory."
        )
    resolved = _resolve_inside_workspace(
        state_root,
        workspace=workspace,
        state_root=state_root,
        label="storage root",
        allow_state_root=True,
    )
    return resolved


def _ensure_state_root(workspace: Path, state_root: Path) -> Path:
    if state_root.is_symlink():
        raise StorageConfigurationError(".harness-v3 must not be a symbolic link.")
    try:
        state_root.mkdir(mode=0o700, exist_ok=True)
    except OSError as exc:
        raise StorageIOError("Could not create .harness-v3 storage.") from exc
    root = _existing_state_root(workspace, state_root)
    _fsync_directory(workspace)
    return root


def _ensure_directory(path: Path, *, within: Path) -> None:
    if path.is_symlink():
        raise StorageConfigurationError(
            "Storage subdirectories must not be symbolic links."
        )
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as exc:
        raise StorageIOError("Could not create a storage directory.") from exc
    if path.is_symlink() or not path.is_dir():
        raise StorageConfigurationError("Storage subdirectory is not a safe directory.")
    try:
        path.resolve(strict=True).relative_to(within.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise StorageConfigurationError(
            "Storage subdirectory escapes .harness-v3."
        ) from exc
    _fsync_directory(path.parent)


def _open_lock_file(path: Path) -> int:
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        return os.open(path, flags, 0o600)
    except OSError as exc:
        raise StorageIOError("Could not open the workspace invocation lock.") from exc


def _read_json_object(path: Path) -> dict[str, object] | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise StorageCorruptionError("Durable JSON path is not a regular file.")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StorageIOError("Could not read durable JSON.") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StorageCorruptionError("Durable JSON is malformed.") from exc
    if not isinstance(payload, dict) or any(
        not isinstance(key, str) for key in payload
    ):
        raise StorageCorruptionError("Durable JSON must contain one object.")
    return payload


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    try:
        encoded = (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise StorageCorruptionError(
            "Durable payload is not JSON-serializable."
        ) from exc
    _ensure_directory(path.parent, within=path.parent.parent)
    descriptor = -1
    temporary = ""
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = ""
        _fsync_directory(path.parent)
    except OSError as exc:
        raise StorageIOError("Atomic durable JSON write failed.") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(path, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise StorageIOError("Could not fsync a durable storage directory.") from exc


def _resolve_inside_workspace(
    path: Path,
    *,
    workspace: Path,
    state_root: Path,
    label: str,
    allow_state_root: bool = False,
) -> Path:
    try:
        resolved = path.resolve(strict=False)
        resolved.relative_to(workspace)
    except (OSError, RuntimeError, ValueError) as exc:
        raise InvalidArtifactPathError(f"{label} path escapes the Workspace.") from exc
    state_resolved = state_root.resolve(strict=False)
    if not allow_state_root and (
        resolved == state_resolved or state_resolved in resolved.parents
    ):
        raise InvalidArtifactPathError(f"{label} path enters .harness-v3.")
    return resolved


def _hash_file_stably(path: Path) -> tuple[str, int]:
    try:
        before = path.stat()
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        after = path.stat()
    except OSError as exc:
        raise StorageIOError("Could not fingerprint an Artifact file.") from exc
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after or size != after.st_size:
        raise ArtifactChangedError("Artifact file changed while it was fingerprinted.")
    return digest.hexdigest(), size


def _hash_directory_stably(
    path: Path,
    *,
    workspace: Path,
    state_root: Path,
    ancestry: frozenset[tuple[int, int]],
) -> tuple[str, int]:
    try:
        before = path.stat()
    except OSError as exc:
        raise StorageIOError("Could not inspect an Artifact directory.") from exc
    identity = (before.st_dev, before.st_ino)
    if identity in ancestry:
        raise InvalidArtifactPathError("Artifact directory contains a symlink cycle.")
    ancestry = ancestry | {identity}
    digest = hashlib.sha256(b"directory-tree-sha256.v1\0")
    total_size = 0
    try:
        entries = sorted(path.iterdir(), key=lambda item: os.fsencode(item.name))
    except OSError as exc:
        raise StorageIOError("Could not list an Artifact directory.") from exc
    for entry in entries:
        if entry == state_root:
            continue
        resolved = _resolve_inside_workspace(
            entry,
            workspace=workspace,
            state_root=state_root,
            label="Artifact descendant",
        )
        name = os.fsencode(entry.name)
        if resolved.is_file():
            child_digest, child_size = _hash_file_stably(resolved)
            kind = b"L-F" if entry.is_symlink() else b"F"
        elif resolved.is_dir():
            child_digest, child_size = _hash_directory_stably(
                resolved,
                workspace=workspace,
                state_root=state_root,
                ancestry=ancestry,
            )
            kind = b"L-D" if entry.is_symlink() else b"D"
        else:
            raise InvalidArtifactPathError(
                "Artifact directory contains a non-file entry."
            )
        digest.update(kind)
        digest.update(b"\0")
        digest.update(str(len(name)).encode("ascii"))
        digest.update(b":")
        digest.update(name)
        digest.update(b"\0")
        digest.update(str(child_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(child_digest.encode("ascii"))
        digest.update(b"\0")
        total_size += child_size
    try:
        after = path.stat()
    except OSError as exc:
        raise StorageIOError("Could not recheck an Artifact directory.") from exc
    if (before.st_dev, before.st_ino, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_mtime_ns,
    ):
        raise ArtifactChangedError(
            "Artifact directory changed while it was fingerprinted."
        )
    return digest.hexdigest(), total_size


def _fingerprint_bytes(
    *, path: str, content: bytes, normalization: str
) -> ArtifactEvidence:
    return ArtifactEvidence(
        path=path,
        sha256=hashlib.sha256(content).hexdigest(),
        size=len(content),
        normalization=normalization,
    )


def _safe_text(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    result = value.strip()
    if not result or any(ord(character) < 32 for character in result):
        raise ValueError(f"{label} must be a non-empty single-line value")
    return result


def _safe_identifier(value: str, label: str) -> str:
    result = _safe_text(value, label)
    if not _SAFE_ID.fullmatch(result):
        raise StorageIdentityError(f"{label} is not a safe local identifier.")
    return result
