from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Iterable

from .errors import ErrorCode, HarnessError


CURRENT_COMPLETION_PROTOCOL = "recoverable-provenance.v2"


class Owner(str, Enum):
    CODEX = "CODEX"
    HUMAN = "HUMAN"


class RunStatus(str, Enum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"


class UnitStatus(str, Enum):
    TODO = "TODO"
    DOING = "DOING"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    SKIPPED = "SKIP"


class AttemptStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    INTERRUPTED = "INTERRUPTED"


class CompletionPhase(str, Enum):
    PREPARED = "PREPARED"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


class ManifestStatus(str, Enum):
    PREPARED = "PREPARED"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class HarnessRevision:
    pipeline_digest: str
    kernel_digest: str
    completion_protocol: str = CURRENT_COMPLETION_PROTOCOL


@dataclass(frozen=True, slots=True)
class Goal:
    id: str
    request: str
    workflow: str
    constraints: tuple[str, ...] = ()
    target_artifacts: tuple[str, ...] = ()
    success_criteria: tuple[str, ...] = ()
    required_checks: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UnitPlan:
    id: str
    title: str
    skill: str
    depends_on: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    owner: Owner = Owner.CODEX
    checkpoint: str = ""
    workflow_type: str = ""
    acceptance: str = ""

    @property
    def required_inputs(self) -> tuple[str, ...]:
        return tuple(path for path in self.inputs if path and not path.startswith("?"))

    @property
    def all_input_paths(self) -> tuple[str, ...]:
        return tuple(_without_optional_marker(path) for path in self.inputs if path)

    @property
    def required_outputs(self) -> tuple[str, ...]:
        return tuple(path for path in self.outputs if path and not path.startswith("?"))

    @property
    def all_output_paths(self) -> tuple[str, ...]:
        return tuple(_without_optional_marker(path) for path in self.outputs if path)


@dataclass(frozen=True, slots=True)
class RunPlan:
    goal: Goal
    units: tuple[UnitPlan, ...]

    def unit(self, unit_id: str) -> UnitPlan:
        for unit in self.units:
            if unit.id == unit_id:
                return unit
        raise HarnessError(
            ErrorCode.UNIT_NOT_FOUND,
            f"Run plan has no Unit {unit_id}.",
            unit_id=unit_id,
        )

    def review_artifacts(self, unit_id: str) -> tuple[tuple[str, bool], ...]:
        """Return bounded Checkpoint evidence: Unit inputs plus direct dependency evidence."""

        unit = self.unit(unit_id)
        units = {item.id: item for item in self.units}
        required_by_path: dict[str, bool] = {}

        def add(paths: Iterable[str]) -> None:
            for raw_path in paths:
                optional = raw_path.startswith("?")
                path = _without_optional_marker(raw_path)
                if not path or path in {"STATUS.md", "UNITS.csv", "CHECKPOINTS.md"}:
                    continue
                required_by_path[path] = (
                    required_by_path.get(path, False) or not optional
                )

        add(unit.inputs)
        for dependency_id in unit.depends_on:
            dependency = units[dependency_id]
            add(dependency.inputs)
            add(dependency.outputs)
        return tuple(sorted(required_by_path.items()))


@dataclass(frozen=True, slots=True)
class ArtifactEvidence:
    path: str
    sha256: str
    size: int
    normalization: str = "file-sha256.v1"


@dataclass(frozen=True, slots=True)
class CheckpointReviewBasis:
    checkpoint: str
    unit_id: str
    artifacts: tuple[ArtifactEvidence, ...]
    schema: str = "checkpoint-review-basis.v1"
    approved: bool = False


@dataclass(frozen=True, slots=True)
class AcceptanceEvidence:
    passed: bool
    checks: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AttemptView:
    id: str
    unit_id: str
    skill: str
    status: AttemptStatus
    started_sequence: int
    finished_sequence: int | None = None
    message: str = ""


@dataclass(frozen=True, slots=True)
class CompletionView:
    id: str
    unit_id: str
    attempt_id: str
    manifest_id: str
    phase: CompletionPhase
    artifacts: tuple[ArtifactEvidence, ...]
    acceptance: AcceptanceEvidence


@dataclass(frozen=True, slots=True)
class CheckpointApprovalView:
    id: str
    checkpoint: str
    unit_id: str
    review_basis: CheckpointReviewBasis
    active: bool
    sequence: int


@dataclass(frozen=True, slots=True)
class UnitView:
    plan: UnitPlan
    status: UnitStatus


@dataclass(frozen=True, slots=True)
class EventView:
    sequence: int
    kind: str
    unit_id: str = ""
    attempt_id: str = ""
    details: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class RunView:
    id: str
    goal: Goal
    revision: HarnessRevision
    status: RunStatus
    units: tuple[UnitView, ...]
    attempts: tuple[AttemptView, ...]
    completions: tuple[CompletionView, ...]
    checkpoint_approvals: tuple[CheckpointApprovalView, ...]
    events: tuple[EventView, ...]
    active_attempt_id: str | None
    version: int

    def unit(self, unit_id: str) -> UnitView:
        for unit in self.units:
            if unit.plan.id == unit_id:
                return unit
        raise HarnessError(
            ErrorCode.UNIT_NOT_FOUND,
            f"Run {self.id} has no Unit {unit_id}.",
            run_id=self.id,
            unit_id=unit_id,
        )


@dataclass(frozen=True, slots=True)
class CompletionManifest:
    id: str
    completion_id: str
    run_id: str
    unit_id: str
    attempt_id: str
    status: ManifestStatus
    artifacts: tuple[ArtifactEvidence, ...]
    acceptance: AcceptanceEvidence


@dataclass(slots=True)
class RunAggregate:
    """Internal aggregate that owns all Run transition invariants."""

    id: str
    plan: RunPlan
    revision: HarnessRevision
    unit_status: dict[str, UnitStatus]
    attempts: list[AttemptView] = field(default_factory=list)
    completions: list[CompletionView] = field(default_factory=list)
    approvals: list[CheckpointApprovalView] = field(default_factory=list)
    events: list[EventView] = field(default_factory=list)
    active_attempt_id: str | None = None

    @classmethod
    def create(
        cls, *, run_id: str, plan: RunPlan, revision: HarnessRevision
    ) -> RunAggregate:
        validate_run_contract(run_id=run_id, plan=plan, revision=revision)
        aggregate = cls(
            id=run_id,
            plan=plan,
            revision=revision,
            unit_status={unit.id: UnitStatus.TODO for unit in plan.units},
        )
        aggregate._emit("run.created")
        aggregate._emit("run.planned", details={"unit_count": str(len(plan.units))})
        return aggregate

    @property
    def version(self) -> int:
        return len(self.events)

    @property
    def status(self) -> RunStatus:
        statuses = tuple(self.unit_status.values())
        if statuses and all(status is UnitStatus.DONE for status in statuses):
            return RunStatus.COMPLETED
        if (
            self.active_attempt_id
            or UnitStatus.DOING in statuses
            or self.pending_completion() is not None
        ):
            return RunStatus.RUNNING
        if UnitStatus.BLOCKED in statuses or UnitStatus.SKIPPED in statuses:
            return RunStatus.BLOCKED
        if self.attempts or UnitStatus.DONE in statuses:
            return RunStatus.RUNNING
        return RunStatus.PLANNED

    def begin_attempt(self, *, unit_id: str, attempt_id: str) -> None:
        unit = self.plan.unit(unit_id)
        if self.pending_completion() is not None:
            raise HarnessError(
                ErrorCode.RECOVERY_REQUIRED,
                "A PREPARED Completion must be reconciled before more work starts.",
                run_id=self.id,
                unit_id=unit_id,
            )
        if self.active_attempt_id:
            raise HarnessError(
                ErrorCode.ACTIVE_ATTEMPT_EXISTS,
                f"Attempt {self.active_attempt_id} already owns this Run.",
                run_id=self.id,
                unit_id=unit_id,
                attempt_id=self.active_attempt_id,
            )
        status = self.unit_status[unit_id]
        if status not in {UnitStatus.TODO, UnitStatus.BLOCKED}:
            raise HarnessError(
                ErrorCode.INVALID_TRANSITION,
                f"Unit {unit_id} cannot begin from {status.value}.",
                run_id=self.id,
                unit_id=unit_id,
            )
        missing = tuple(
            dependency
            for dependency in unit.depends_on
            if self.unit_status[dependency] is not UnitStatus.DONE
        )
        if missing:
            raise HarnessError(
                ErrorCode.DEPENDENCIES_NOT_READY,
                f"Unit {unit_id} is waiting on: {', '.join(missing)}.",
                run_id=self.id,
                unit_id=unit_id,
                details={"dependencies": missing},
            )
        sequence = self.version + 1
        self.attempts.append(
            AttemptView(
                id=attempt_id,
                unit_id=unit_id,
                skill=unit.skill,
                status=AttemptStatus.RUNNING,
                started_sequence=sequence,
            )
        )
        self.unit_status[unit_id] = UnitStatus.DOING
        self.active_attempt_id = attempt_id
        self._emit("unit.attempt.started", unit_id=unit_id, attempt_id=attempt_id)

    def fail_attempt(self, *, attempt_id: str, reason: str) -> None:
        index, attempt = self._attempt(attempt_id)
        if attempt.status is not AttemptStatus.RUNNING:
            raise HarnessError(
                ErrorCode.INVALID_TRANSITION,
                f"Attempt {attempt_id} is already {attempt.status.value}.",
                run_id=self.id,
                unit_id=attempt.unit_id,
                attempt_id=attempt_id,
            )
        sequence = self.version + 1
        self.attempts[index] = replace(
            attempt,
            status=AttemptStatus.FAILED_RETRYABLE,
            finished_sequence=sequence,
            message=reason,
        )
        self.unit_status[attempt.unit_id] = UnitStatus.BLOCKED
        if self.active_attempt_id == attempt_id:
            self.active_attempt_id = None
        self._emit(
            "unit.attempt.failed",
            unit_id=attempt.unit_id,
            attempt_id=attempt_id,
            details={"reason": reason},
        )

    def approve_checkpoint(
        self,
        *,
        checkpoint: str,
        approval_id: str,
        review_basis: CheckpointReviewBasis,
    ) -> str:
        candidates = [
            unit
            for unit in self.plan.units
            if unit.checkpoint == checkpoint
            and (unit.owner is Owner.HUMAN or unit.skill == "human-checkpoint")
            and self.unit_status[unit.id]
            in {UnitStatus.TODO, UnitStatus.DOING, UnitStatus.BLOCKED}
            and all(
                self.unit_status[dependency] is UnitStatus.DONE
                for dependency in unit.depends_on
            )
        ]
        if len(candidates) != 1:
            raise HarnessError(
                ErrorCode.CHECKPOINT_NOT_FOUND,
                f"Checkpoint {checkpoint} must resolve to exactly one active HUMAN Unit; found {len(candidates)}.",
                run_id=self.id,
            )
        unit = candidates[0]
        if (
            review_basis.schema != "checkpoint-review-basis.v1"
            or review_basis.checkpoint != checkpoint
            or review_basis.unit_id != unit.id
            or not review_basis.artifacts
            or not review_basis.approved
        ):
            raise HarnessError(
                ErrorCode.INVALID_TRANSITION,
                f"Checkpoint {checkpoint} requires a non-empty checkpoint-review-basis.v1 for Unit {unit.id}.",
                run_id=self.id,
                unit_id=unit.id,
            )
        for index, approval in enumerate(self.approvals):
            if approval.checkpoint == checkpoint and approval.active:
                self.approvals[index] = replace(approval, active=False)
        sequence = self.version + 1
        self.approvals.append(
            CheckpointApprovalView(
                id=approval_id,
                checkpoint=checkpoint,
                unit_id=unit.id,
                review_basis=review_basis,
                active=True,
                sequence=sequence,
            )
        )
        self._emit(
            "checkpoint.approved", unit_id=unit.id, details={"checkpoint": checkpoint}
        )
        return unit.id

    def revoke_checkpoint(self, *, checkpoint: str, reason: str) -> None:
        changed = False
        unit_id = ""
        for index, approval in enumerate(self.approvals):
            if approval.checkpoint == checkpoint and approval.active:
                self.approvals[index] = replace(approval, active=False)
                unit_id = approval.unit_id
                changed = True
        if changed:
            self._emit(
                "checkpoint.approval.revoked",
                unit_id=unit_id,
                details={"checkpoint": checkpoint, "reason": reason},
            )

    def reopen_checkpoint(self, *, unit_id: str, reason: str) -> None:
        unit = self.plan.unit(unit_id)
        if not unit.checkpoint or (
            unit.owner is not Owner.HUMAN and unit.skill != "human-checkpoint"
        ):
            raise HarnessError(
                ErrorCode.INVALID_TRANSITION,
                f"Unit {unit_id} is not a HUMAN Checkpoint.",
                run_id=self.id,
                unit_id=unit_id,
            )
        if self.unit_status[unit_id] is not UnitStatus.DONE:
            raise HarnessError(
                ErrorCode.INVALID_TRANSITION,
                f"Checkpoint Unit {unit_id} cannot reopen from {self.unit_status[unit_id].value}.",
                run_id=self.id,
                unit_id=unit_id,
            )
        self.unit_status[unit_id] = UnitStatus.BLOCKED
        self._emit(
            "checkpoint.reopened",
            unit_id=unit_id,
            details={"checkpoint": unit.checkpoint, "reason": reason},
        )

    def invalidate_downstream(
        self, *, root_unit_id: str, reason: str
    ) -> tuple[str, ...]:
        """Reset every materialized transitive descendant after an upstream gate reopens."""

        children: dict[str, list[str]] = {}
        for unit in self.plan.units:
            for dependency in unit.depends_on:
                children.setdefault(dependency, []).append(unit.id)

        descendants: set[str] = set()
        pending = [root_unit_id]
        while pending:
            parent = pending.pop()
            for child in children.get(parent, ()):
                if child in descendants:
                    continue
                descendants.add(child)
                pending.append(child)

        invalidated: list[str] = []
        for unit in self.plan.units:
            if (
                unit.id not in descendants
                or self.unit_status[unit.id] is UnitStatus.TODO
            ):
                continue
            if unit.checkpoint and (
                unit.owner is Owner.HUMAN or unit.skill == "human-checkpoint"
            ):
                self.revoke_checkpoint(checkpoint=unit.checkpoint, reason=reason)
            self.unit_status[unit.id] = UnitStatus.TODO
            invalidated.append(unit.id)
            self._emit(
                "unit.invalidated",
                unit_id=unit.id,
                details={"root_unit_id": root_unit_id, "reason": reason},
            )
        return tuple(invalidated)

    def active_approval(self, checkpoint: str) -> CheckpointApprovalView | None:
        for approval in reversed(self.approvals):
            if approval.checkpoint == checkpoint and approval.active:
                return approval
        return None

    def prepare_completion(
        self,
        *,
        completion_id: str,
        attempt_id: str,
        manifest_id: str,
        artifacts: tuple[ArtifactEvidence, ...],
        acceptance: AcceptanceEvidence,
    ) -> None:
        _, attempt = self._attempt(attempt_id)
        if (
            attempt.status is not AttemptStatus.RUNNING
            or self.active_attempt_id != attempt_id
        ):
            raise HarnessError(
                ErrorCode.INVALID_TRANSITION,
                f"Attempt {attempt_id} is not the active RUNNING Attempt.",
                run_id=self.id,
                unit_id=attempt.unit_id,
                attempt_id=attempt_id,
            )
        if self.pending_completion() is not None:
            raise HarnessError(
                ErrorCode.RECOVERY_REQUIRED,
                "A PREPARED Completion already exists.",
                run_id=self.id,
                unit_id=attempt.unit_id,
                attempt_id=attempt_id,
            )
        self.completions.append(
            CompletionView(
                id=completion_id,
                unit_id=attempt.unit_id,
                attempt_id=attempt_id,
                manifest_id=manifest_id,
                phase=CompletionPhase.PREPARED,
                artifacts=artifacts,
                acceptance=acceptance,
            )
        )
        self._emit(
            "unit.completion.prepared", unit_id=attempt.unit_id, attempt_id=attempt_id
        )

    def succeed_prepared_attempt(self, completion_id: str) -> None:
        completion = self._completion(completion_id)
        index, attempt = self._attempt(completion.attempt_id)
        if attempt.status is AttemptStatus.SUCCEEDED:
            return
        if attempt.status is not AttemptStatus.RUNNING:
            raise HarnessError(
                ErrorCode.INVALID_TRANSITION,
                f"Prepared Completion points to {attempt.status.value} Attempt {attempt.id}.",
                run_id=self.id,
                unit_id=attempt.unit_id,
                attempt_id=attempt.id,
            )
        sequence = self.version + 1
        self.attempts[index] = replace(
            attempt,
            status=AttemptStatus.SUCCEEDED,
            finished_sequence=sequence,
        )
        if self.active_attempt_id == attempt.id:
            self.active_attempt_id = None
        self._emit(
            "unit.attempt.succeeded", unit_id=attempt.unit_id, attempt_id=attempt.id
        )

    def commit_completion(self, completion_id: str) -> None:
        index, completion = self._completion_with_index(completion_id)
        _, attempt = self._attempt(completion.attempt_id)
        if (
            completion.phase is not CompletionPhase.PREPARED
            or attempt.status is not AttemptStatus.SUCCEEDED
        ):
            raise HarnessError(
                ErrorCode.INVALID_TRANSITION,
                f"Completion {completion_id} is not prepared against a successful Attempt.",
                run_id=self.id,
                unit_id=completion.unit_id,
                attempt_id=completion.attempt_id,
            )
        self.completions[index] = replace(completion, phase=CompletionPhase.COMMITTED)
        self.unit_status[completion.unit_id] = UnitStatus.DONE
        self._emit(
            "unit.completion.committed",
            unit_id=completion.unit_id,
            attempt_id=completion.attempt_id,
        )
        if self.status is RunStatus.COMPLETED:
            self._emit("run.completed")

    def abort_completion(self, completion_id: str, *, reason: str) -> None:
        index, completion = self._completion_with_index(completion_id)
        if completion.phase is not CompletionPhase.PREPARED:
            raise HarnessError(
                ErrorCode.INVALID_TRANSITION,
                f"Completion {completion_id} is already {completion.phase.value}.",
                run_id=self.id,
                unit_id=completion.unit_id,
                attempt_id=completion.attempt_id,
            )
        self.completions[index] = replace(completion, phase=CompletionPhase.ABORTED)
        _, attempt = self._attempt(completion.attempt_id)
        self._emit(
            "unit.completion.aborted",
            unit_id=completion.unit_id,
            attempt_id=completion.attempt_id,
            details={"reason": reason},
        )
        if attempt.status is AttemptStatus.RUNNING:
            self.fail_attempt(attempt_id=attempt.id, reason=reason)
        else:
            self.unit_status[completion.unit_id] = UnitStatus.BLOCKED

    def pending_completion(self) -> CompletionView | None:
        for completion in self.completions:
            if completion.phase is CompletionPhase.PREPARED:
                return completion
        return None

    def view(self) -> RunView:
        return RunView(
            id=self.id,
            goal=self.plan.goal,
            revision=self.revision,
            status=self.status,
            units=tuple(
                UnitView(unit, self.unit_status[unit.id]) for unit in self.plan.units
            ),
            attempts=tuple(self.attempts),
            completions=tuple(self.completions),
            checkpoint_approvals=tuple(self.approvals),
            events=tuple(self.events),
            active_attempt_id=self.active_attempt_id,
            version=self.version,
        )

    def _attempt(self, attempt_id: str) -> tuple[int, AttemptView]:
        for index, attempt in enumerate(self.attempts):
            if attempt.id == attempt_id:
                return index, attempt
        raise HarnessError(
            ErrorCode.ATTEMPT_NOT_FOUND,
            f"Run {self.id} has no Attempt {attempt_id}.",
            run_id=self.id,
            attempt_id=attempt_id,
        )

    def _completion(self, completion_id: str) -> CompletionView:
        return self._completion_with_index(completion_id)[1]

    def _completion_with_index(self, completion_id: str) -> tuple[int, CompletionView]:
        for index, completion in enumerate(self.completions):
            if completion.id == completion_id:
                return index, completion
        raise HarnessError(
            ErrorCode.INVALID_TRANSITION,
            f"Run {self.id} has no Completion {completion_id}.",
            run_id=self.id,
        )

    def _emit(
        self,
        kind: str,
        *,
        unit_id: str = "",
        attempt_id: str = "",
        details: dict[str, str] | None = None,
    ) -> None:
        self.events.append(
            EventView(
                sequence=self.version + 1,
                kind=kind,
                unit_id=unit_id,
                attempt_id=attempt_id,
                details=tuple(sorted((details or {}).items())),
            )
        )


def validate_run_contract(
    *, run_id: str, plan: RunPlan, revision: HarnessRevision
) -> None:
    problems: list[str] = []
    if not run_id.strip():
        problems.append("run_id must be non-empty")
    if not plan.goal.id.strip():
        problems.append("Goal.id must be non-empty")
    if not plan.goal.workflow.strip():
        problems.append("Goal.workflow must be non-empty")
    if not revision.pipeline_digest.strip() or not revision.kernel_digest.strip():
        problems.append("Pipeline and Kernel revision digests must be non-empty")
    if revision.completion_protocol != CURRENT_COMPLETION_PROTOCOL:
        problems.append(f"Completion Protocol must be {CURRENT_COMPLETION_PROTOCOL}")
    if not plan.units:
        problems.append("RunPlan must declare at least one Unit")

    required_checks = plan.goal.required_checks
    if any(not check.strip() for check in required_checks):
        problems.append("Goal.required_checks must contain non-empty skill names")
    if len(set(required_checks)) != len(required_checks):
        problems.append("Goal.required_checks must not contain duplicates")

    for raw_path in plan.goal.target_artifacts:
        if not _is_safe_artifact_path(raw_path, allow_directory=False):
            problems.append(f"Goal has unsafe target Artifact path: {raw_path}")

    unit_ids = [unit.id for unit in plan.units]
    if len(set(unit_ids)) != len(unit_ids):
        problems.append("Unit IDs must be unique")
    known = set(unit_ids)
    for unit in plan.units:
        if not unit.id.strip() or not unit.skill.strip():
            problems.append("Every Unit must have non-empty id and skill")
        is_human_gate = unit.owner is Owner.HUMAN or unit.skill == "human-checkpoint"
        if is_human_gate:
            if not unit.checkpoint.strip():
                problems.append(
                    f"HUMAN Checkpoint Unit {unit.id} must declare a non-empty checkpoint"
                )
            if "DECISIONS.md" not in unit.inputs or "DECISIONS.md" not in unit.outputs:
                problems.append(
                    f"HUMAN Checkpoint Unit {unit.id} must read and write DECISIONS.md"
                )
        unknown = sorted(set(unit.depends_on) - known)
        if unknown:
            problems.append(
                f"Unit {unit.id} has unknown dependencies: {', '.join(unknown)}"
            )
        if unit.id in unit.depends_on:
            problems.append(f"Unit {unit.id} cannot depend on itself")
        for raw_path in unit.inputs:
            if not _is_safe_artifact_path(raw_path, allow_directory=True):
                problems.append(f"Unit {unit.id} has unsafe Artifact path: {raw_path}")
        for raw_path in unit.outputs:
            path = _without_optional_marker(raw_path)
            if not _is_safe_artifact_path(path, allow_directory=False):
                problems.append(f"Unit {unit.id} has unsafe Artifact path: {raw_path}")

    visiting: set[str] = set()
    visited: set[str] = set()
    dependencies = {unit.id: unit.depends_on for unit in plan.units}

    def visit(unit_id: str) -> None:
        if unit_id in visited:
            return
        if unit_id in visiting:
            problems.append(f"Unit dependency graph contains a cycle at {unit_id}")
            return
        visiting.add(unit_id)
        for dependency in dependencies.get(unit_id, ()):
            visit(dependency)
        visiting.remove(unit_id)
        visited.add(unit_id)

    for unit_id in unit_ids:
        visit(unit_id)

    checkpoint_counts: dict[str, int] = {}
    for unit in plan.units:
        if unit.checkpoint and (
            unit.owner is Owner.HUMAN or unit.skill == "human-checkpoint"
        ):
            checkpoint_counts[unit.checkpoint] = (
                checkpoint_counts.get(unit.checkpoint, 0) + 1
            )
    duplicates = sorted(
        checkpoint for checkpoint, count in checkpoint_counts.items() if count != 1
    )
    if duplicates:
        problems.append(
            f"Each Checkpoint must bind exactly one HUMAN Unit: {', '.join(duplicates)}"
        )

    if problems:
        raise HarnessError(
            ErrorCode.INVALID_COMMAND,
            "; ".join(dict.fromkeys(problems)),
            run_id=run_id,
        )


def _without_optional_marker(path: str) -> str:
    return path[1:] if path.startswith("?") else path


def _is_safe_artifact_path(path: str, *, allow_directory: bool) -> bool:
    if not isinstance(path, str) or not path or path == "." or path.startswith("?"):
        return False
    if "\\" in path or ";" in path or _contains_control_character(path):
        return False
    posix_path = PurePosixPath(path)
    windows_path = PureWindowsPath(path)
    if posix_path.is_absolute() or windows_path.is_absolute() or windows_path.drive:
        return False
    if any(part in {".", ".."} for part in path.split("/")):
        return False
    return allow_directory or not path.endswith("/")


def _contains_control_character(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)
