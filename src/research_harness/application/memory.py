from __future__ import annotations

import copy
import hashlib
import threading
from contextlib import contextmanager
from dataclasses import replace
from typing import Iterable, Iterator

from research_harness.domain.checkpoints import checkpoint_decisions_projection
from research_harness.domain.errors import ErrorCode, HarnessError
from research_harness.domain.model import (
    AcceptanceEvidence,
    ArtifactEvidence,
    CheckpointReviewBasis,
    CompletionManifest,
    ManifestStatus,
    RunAggregate,
    RunView,
    UnitPlan,
)


class InMemoryRunLedger:
    """Thread-safe adapter used by interface tests and embedding callers."""

    def __init__(self) -> None:
        self._runs: dict[str, RunAggregate] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._meta_lock = threading.Lock()
        self._fail_save_once = False

    def fail_next_save(self) -> None:
        """Make the next ``save`` raise a storage I/O fault, leaving state intact.

        Simulates a transient ``FilesystemRunLedger`` write failure -- the atomic
        ``os.replace`` of ``state.json`` -- for fault-injection tests: the
        optimistic-concurrency checks still run, but the canonical state is left
        at the prior version, exactly as the filesystem ledger preserves the
        prior canonical state on a failed atomic replace. The fault is one-shot.
        """

        self._fail_save_once = True

    @contextmanager
    def lock(self, run_id: str, operation: str) -> Iterator[None]:
        with self._meta_lock:
            lock = self._locks.setdefault(run_id, threading.Lock())
        if not lock.acquire(blocking=False):
            raise HarnessError(
                ErrorCode.CONCURRENT_INVOCATION,
                f"Run {run_id} is already executing another invocation.",
                run_id=run_id,
                details={"operation": operation},
            )
        try:
            yield
        finally:
            lock.release()

    def load(self, run_id: str) -> RunAggregate | None:
        run = self._runs.get(run_id)
        return copy.deepcopy(run) if run is not None else None

    def save(self, run: RunAggregate, *, expected_version: int) -> None:
        current = self._runs.get(run.id)
        current_version = current.version if current is not None else 0
        if current_version != expected_version:
            raise HarnessError(
                ErrorCode.CONCURRENT_WRITE,
                f"Run {run.id} changed from version {expected_version} to {current_version}.",
                run_id=run.id,
            )
        if current is not None and run.events[:current_version] != current.events:
            raise HarnessError(
                ErrorCode.CONCURRENT_WRITE,
                f"Run {run.id} attempted to rewrite append-only Event history.",
                run_id=run.id,
            )
        if run.version <= current_version:
            raise HarnessError(
                ErrorCode.CONCURRENT_WRITE,
                f"Run {run.id} save must append at least one Event.",
                run_id=run.id,
            )
        if self._fail_save_once:
            self._fail_save_once = False
            raise OSError("injected state-write failure")
        self._runs[run.id] = copy.deepcopy(run)


class InMemoryArtifacts:
    """Artifact/Manifest adapter with deterministic SHA-256 evidence."""

    def __init__(self) -> None:
        self._content: dict[tuple[str, str], bytes] = {}
        self._manifests: dict[str, CompletionManifest] = {}
        self._fail_finalize_once = False
        self._fail_status_once: ManifestStatus | None = None

    def put(self, run_id: str, path: str, content: str | bytes) -> None:
        self._content[(run_id, path)] = (
            content.encode("utf-8") if isinstance(content, str) else bytes(content)
        )

    def remove(self, run_id: str, path: str) -> None:
        self._content.pop((run_id, path), None)

    def fail_next_finalize(self) -> None:
        self._fail_finalize_once = True

    def fail_next_status(self, status: ManifestStatus) -> None:
        self._fail_status_once = status

    def snapshot(
        self, run_id: str, paths: Iterable[str]
    ) -> tuple[ArtifactEvidence, ...]:
        evidence: list[ArtifactEvidence] = []
        for path in paths:
            content = self._content.get((run_id, path))
            if content is None:
                continue
            evidence.append(_fingerprint(path=path, content=content))
        return tuple(evidence)

    def checkpoint_review_basis(
        self,
        *,
        run_id: str,
        checkpoint: str,
        unit_id: str,
        paths: Iterable[str],
    ) -> CheckpointReviewBasis:
        evidence: list[ArtifactEvidence] = []
        approved = False
        for path in paths:
            content = self._content.get((run_id, path))
            if content is None:
                continue
            if path == "DECISIONS.md":
                projected, approved = checkpoint_decisions_projection(
                    content.decode("utf-8", errors="replace"),
                    checkpoint=checkpoint,
                )
                projected = projected.encode("utf-8")
                if not projected:
                    continue
                evidence.append(
                    _fingerprint(
                        path=path,
                        content=projected,
                        normalization="checkpoint-block-and-approval-checkbox-insensitive.v1",
                    )
                )
                continue
            evidence.append(_fingerprint(path=path, content=content))
        return CheckpointReviewBasis(
            checkpoint=checkpoint,
            unit_id=unit_id,
            artifacts=tuple(evidence),
            approved=approved,
        )

    def write_manifest(self, manifest: CompletionManifest) -> None:
        existing = self._manifests.get(manifest.id)
        if existing is not None and existing != manifest:
            raise ValueError(
                f"Manifest {manifest.id} already exists with different evidence."
            )
        self._manifests[manifest.id] = copy.deepcopy(manifest)

    def read_manifest(self, manifest_id: str) -> CompletionManifest | None:
        manifest = self._manifests.get(manifest_id)
        return copy.deepcopy(manifest) if manifest is not None else None

    def list_manifests(self, run_id: str) -> tuple[CompletionManifest, ...]:
        return tuple(
            copy.deepcopy(manifest)
            for manifest in self._manifests.values()
            if manifest.run_id == run_id
        )

    def set_manifest_status(self, manifest_id: str, status: ManifestStatus) -> None:
        if status is self._fail_status_once:
            self._fail_status_once = None
            raise OSError(f"injected one-shot Manifest {status.value} failure")
        if status is ManifestStatus.DONE and self._fail_finalize_once:
            self._fail_finalize_once = False
            raise OSError("injected one-shot Manifest finalization failure")
        manifest = self._manifests.get(manifest_id)
        if manifest is None:
            raise KeyError(f"Unknown Manifest {manifest_id}")
        if manifest.status is ManifestStatus.BLOCKED and status is ManifestStatus.DONE:
            raise ValueError(f"Blocked Manifest {manifest_id} cannot become DONE.")
        self._manifests[manifest_id] = replace(manifest, status=status)


def _fingerprint(
    *,
    path: str,
    content: bytes,
    normalization: str = "file-sha256.v1",
) -> ArtifactEvidence:
    return ArtifactEvidence(
        path=path,
        sha256=hashlib.sha256(content).hexdigest(),
        size=len(content),
        normalization=normalization,
    )


class InMemoryAcceptance:
    """Configurable Workflow acceptance adapter for interface tests."""

    def __init__(self) -> None:
        self._rejections: dict[str, tuple[str, ...]] = {}

    def reject(self, unit_id: str, *issues: str) -> None:
        self._rejections[unit_id] = tuple(issues) or (
            "Rejected by in-memory acceptance policy.",
        )

    def allow(self, unit_id: str) -> None:
        self._rejections.pop(unit_id, None)

    def evaluate(
        self,
        *,
        run: RunView,
        unit: UnitPlan,
        artifacts: tuple[ArtifactEvidence, ...],
    ) -> AcceptanceEvidence:
        del run, artifacts
        issues = self._rejections.get(unit.id, ())
        return AcceptanceEvidence(
            passed=not issues,
            checks=(unit.skill,),
            issues=issues,
        )
