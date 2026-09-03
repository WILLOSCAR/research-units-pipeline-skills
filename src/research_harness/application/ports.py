from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Iterable, Protocol

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


class RunLedger(Protocol):
    """Append-preserving Run storage plus the Workspace invocation lock seam."""

    def lock(self, run_id: str, operation: str) -> AbstractContextManager[None]: ...

    def load(self, run_id: str) -> RunAggregate | None: ...

    def save(self, run: RunAggregate, *, expected_version: int) -> None: ...


class ArtifactPort(Protocol):
    """Artifact fingerprint and Completion Manifest seam.

    Checkpoint bases must isolate the named DECISIONS block and set
    ``approved=True`` only for one explicit checked approval choice.
    """

    def snapshot(
        self, run_id: str, paths: Iterable[str]
    ) -> tuple[ArtifactEvidence, ...]: ...

    def checkpoint_review_basis(
        self,
        *,
        run_id: str,
        checkpoint: str,
        unit_id: str,
        paths: Iterable[str],
    ) -> CheckpointReviewBasis: ...

    def write_manifest(self, manifest: CompletionManifest) -> None: ...

    def read_manifest(self, manifest_id: str) -> CompletionManifest | None: ...

    def list_manifests(self, run_id: str) -> tuple[CompletionManifest, ...]: ...

    def set_manifest_status(self, manifest_id: str, status: ManifestStatus) -> None: ...


class AcceptancePolicy(Protocol):
    """Workflow-local contract acceptance seam.

    A mandatory check Unit attests execution by including its exact Skill name
    in ``AcceptanceEvidence.checks``; arbitrary cross-Skill claims are ignored.
    """

    def evaluate(
        self,
        *,
        run: RunView,
        unit: UnitPlan,
        artifacts: tuple[ArtifactEvidence, ...],
    ) -> AcceptanceEvidence: ...


class AcceptAll:
    """Minimal adapter for Workflows without a mandatory completion check."""

    def evaluate(
        self,
        *,
        run: RunView,
        unit: UnitPlan,
        artifacts: tuple[ArtifactEvidence, ...],
    ) -> AcceptanceEvidence:
        del run, artifacts
        return AcceptanceEvidence(passed=True, checks=(f"{unit.skill}:not-required",))
