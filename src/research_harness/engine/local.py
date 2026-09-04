"""Workspace-bound orchestration for local Research Harness Runs.

The external interface deliberately exposes only ``execute(command)`` and
``inspect()``.  Attempt choreography, recovery, Skill dispatch, and Completion
remain behind this seam.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import tempfile
import threading
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypeVar, Union
from uuid import uuid4

from research_harness.application import (
    AcceptancePolicy,
    ApproveCheckpoint,
    ArtifactPort,
    BeginAttempt,
    CompleteAttempt,
    CreateRun,
    FailAttempt,
    Harness,
    ReconcileRun,
    ResultOutcome,
    RunLedger,
)
from research_harness.domain import (
    ArtifactEvidence,
    AttemptStatus,
    ErrorCode,
    HarnessError,
    HarnessRevision,
    Owner,
    RunPlan,
    RunStatus,
    RunView,
    UnitStatus,
    UnitView,
)
from research_harness.domain.model import RunAggregate
from research_harness.skills import (
    LifecycleSkillAdapter,
    SkillAdapter,
    SkillContext,
    SkillExecutionHandle,
    SkillExecutionError,
    SkillProcessOwner,
    SkillResult,
    SkillRuntimeError,
)


_MAX_ISSUES = 16
_MAX_ISSUE_CHARS = 1_000
_ResultT = TypeVar("_ResultT")
_RUNTIME_OWNER_SCHEMA = "research-harness.active-skill-owner/v1"
_RUNTIME_OWNER_FIELDS = frozenset(
    {
        "schema",
        "run_id",
        "attempt_id",
        "unit_id",
        "adapter",
        "pid",
        "process_group_id",
        "start_token",
    }
)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SECRET_ASSIGNMENT = re.compile(
    r"(?im)\b([a-z0-9_-]*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"token|secret|password|authorization|cookie))\b\s*[:=]\s*[^\r\n]*"
)
_BEARER_SECRET = re.compile(r"(?i)\bBearer\s+[^\s,;]+")


class AdvanceUntil(str, Enum):
    AFTER_ONE = "AFTER_ONE"
    BLOCKED_OR_COMPLETE = "BLOCKED_OR_COMPLETE"


@dataclass(frozen=True, slots=True)
class CreateLocalRun:
    plan: RunPlan
    run_id: str = ""


@dataclass(frozen=True, slots=True)
class AdvanceRun:
    unit_id: str = ""
    until: AdvanceUntil = AdvanceUntil.AFTER_ONE


@dataclass(frozen=True, slots=True)
class ApproveLocalCheckpoint:
    checkpoint: str


@dataclass(frozen=True, slots=True)
class RecoverLocalRun:
    interrupt_active: bool = False


LocalRunCommand = Union[
    CreateLocalRun,
    AdvanceRun,
    ApproveLocalCheckpoint,
    RecoverLocalRun,
]


class EngineOutcome(str, Enum):
    CREATED = "CREATED"
    ADVANCED = "ADVANCED"
    APPROVED = "APPROVED"
    RECOVERED = "RECOVERED"
    COMPLETED = "COMPLETED"
    WAITING_FOR_CHECKPOINT = "WAITING_FOR_CHECKPOINT"
    BLOCKED = "BLOCKED"
    SKILL_FAILED = "SKILL_FAILED"
    NOOP = "NOOP"


class InspectionState(str, Enum):
    EMPTY = "EMPTY"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    LEGACY_READ_ONLY = "LEGACY_READ_ONLY"


class EngineErrorCode(str, Enum):
    INVALID_COMMAND = "invalid_command"
    INVALID_WORKSPACE = "invalid_workspace"
    RUN_NOT_FOUND = "run_not_found"
    RUN_EXISTS = "run_exists"
    LEGACY_READ_ONLY = "legacy_read_only"
    SKILL_ADAPTER_NOT_FOUND = "skill_adapter_not_found"
    SKILL_CONTEXT_INVALID = "skill_context_invalid"
    REVISION_DRIFT = "revision_drift"
    CONCURRENT_INVOCATION = "concurrent_invocation"
    INTEGRITY_VIOLATION = "integrity_violation"
    STORAGE_FAILURE = "storage_failure"
    ADAPTER_FAILURE = "adapter_failure"


class EngineError(RuntimeError):
    """Typed engine failure with bounded, serialization-safe diagnostics."""

    def __init__(
        self,
        code: EngineErrorCode,
        message: str,
        *,
        run_id: str = "",
        unit_id: str = "",
        issues: tuple[str, ...] = (),
    ) -> None:
        bounded_message = _clip(message)
        super().__init__(bounded_message)
        self.code = code
        self.message = bounded_message
        self.run_id = run_id
        self.unit_id = unit_id
        self.issues = _bounded_issues(issues)

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"


@dataclass(frozen=True, slots=True)
class EngineInspection:
    workspace: Path
    state: InspectionState
    run: RunView | None = None
    next_unit_id: str = ""
    waiting_checkpoint: str = ""
    issues: tuple[str, ...] = ()

    @property
    def run_id(self) -> str:
        return self.run.id if self.run is not None else ""


@dataclass(frozen=True, slots=True)
class EngineResult:
    command: str
    outcome: EngineOutcome
    inspection: EngineInspection
    unit_ids: tuple[str, ...] = ()
    attempt_ids: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    recovered: bool = False


@dataclass(frozen=True, slots=True)
class _StepResult:
    outcome: EngineOutcome
    inspection: EngineInspection
    unit_id: str = ""
    attempt_id: str = ""
    issues: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _RuntimeOwnerRecord:
    run_id: str
    attempt_id: str
    unit_id: str
    adapter: str
    pid: int
    process_group_id: int
    start_token: str

    def is_live(self) -> bool:
        try:
            owner = SkillProcessOwner(
                adapter=self.adapter,
                pid=self.pid,
                process_group_id=self.process_group_id,
                start_token=self.start_token,
            )
        except ValueError:
            return False
        return owner.is_live()


class _RuntimeOwnerStore:
    """Durable process liveness metadata kept outside canonical Run state."""

    def __init__(self, workspace: Path) -> None:
        self._root = workspace / ".harness-v3" / "runtime"
        self._path = self._root / "active-attempt.json"

    def record(
        self,
        *,
        run_id: str,
        attempt_id: str,
        unit_id: str,
        owner: SkillProcessOwner,
        workspace: Path,
    ) -> None:
        self._validate_layout(run_id=run_id)
        for label, value in (
            ("run_id", run_id),
            ("attempt_id", attempt_id),
            ("unit_id", unit_id),
        ):
            if not _is_safe_runtime_text(value):
                raise EngineError(
                    EngineErrorCode.INTEGRITY_VIOLATION,
                    f"Skill process ownership {label} is invalid.",
                    run_id=run_id,
                    unit_id=unit_id,
                )
        existing = self.load(run_id=run_id, attempt_id=attempt_id, required=False)
        if existing is not None:
            raise EngineError(
                EngineErrorCode.INTEGRITY_VIOLATION,
                "Active Skill process ownership is already recorded.",
                run_id=run_id,
                unit_id=unit_id,
            )
        payload = {
            "schema": _RUNTIME_OWNER_SCHEMA,
            "run_id": run_id,
            "attempt_id": attempt_id,
            "unit_id": unit_id,
            "adapter": _redact_diagnostic(owner.adapter, workspace=workspace),
            "pid": owner.pid,
            "process_group_id": owner.process_group_id,
            "start_token": owner.start_token,
        }
        descriptor = -1
        temporary: Path | None = None
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            self._validate_layout(run_id=run_id)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".active-attempt-", suffix=".tmp", dir=self._root
            )
            temporary = Path(temporary_name)
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
            _fsync_directory(self._root)
        except Exception as exc:
            try:
                if descriptor >= 0:
                    os.close(descriptor)
            except OSError:
                pass
            try:
                if temporary is not None:
                    temporary.unlink()
            except OSError:
                pass
            raise EngineError(
                EngineErrorCode.STORAGE_FAILURE,
                f"Skill process ownership write failed with {type(exc).__name__}.",
                run_id=run_id,
                unit_id=unit_id,
            ) from exc

    def load(
        self,
        *,
        run_id: str,
        attempt_id: str,
        required: bool = False,
    ) -> _RuntimeOwnerRecord | None:
        self._validate_layout(run_id=run_id)
        if not self._path.exists():
            if required:
                raise EngineError(
                    EngineErrorCode.INTEGRITY_VIOLATION,
                    "Active Skill process ownership metadata is missing.",
                    run_id=run_id,
                )
            return None
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or set(payload) != _RUNTIME_OWNER_FIELDS:
                raise ValueError("unexpected owner fields")
            if any(
                not _is_safe_runtime_text(payload[field])
                for field in (
                    "schema",
                    "run_id",
                    "attempt_id",
                    "unit_id",
                    "adapter",
                    "start_token",
                )
            ):
                raise ValueError("invalid owner text")
            if (
                not isinstance(payload["pid"], int)
                or isinstance(payload["pid"], bool)
                or not isinstance(payload["process_group_id"], int)
                or isinstance(payload["process_group_id"], bool)
            ):
                raise ValueError("invalid owner process identity")
            record = _RuntimeOwnerRecord(
                run_id=payload["run_id"],
                attempt_id=payload["attempt_id"],
                unit_id=payload["unit_id"],
                adapter=payload["adapter"],
                pid=payload["pid"],
                process_group_id=payload["process_group_id"],
                start_token=payload["start_token"],
            )
        except Exception as exc:
            raise EngineError(
                EngineErrorCode.INTEGRITY_VIOLATION,
                f"Skill process ownership metadata is invalid ({type(exc).__name__}).",
                run_id=run_id,
            ) from exc
        if (
            payload.get("schema") != _RUNTIME_OWNER_SCHEMA
            or record.run_id != run_id
            or record.attempt_id != attempt_id
            or not record.unit_id
            or not record.adapter
            or record.pid <= 0
            or record.process_group_id <= 0
            or not re.fullmatch(r"[0-9a-f]{64}", record.start_token)
        ):
            raise EngineError(
                EngineErrorCode.INTEGRITY_VIOLATION,
                "Skill process ownership metadata disagrees with the active Attempt.",
                run_id=run_id,
            )
        return record

    def clear(self, *, run_id: str, attempt_id: str) -> None:
        record = self.load(run_id=run_id, attempt_id=attempt_id, required=False)
        if record is None:
            return
        try:
            self._path.unlink()
            _fsync_directory(self._root)
        except OSError as exc:
            raise EngineError(
                EngineErrorCode.STORAGE_FAILURE,
                f"Skill process ownership cleanup failed with {type(exc).__name__}.",
                run_id=run_id,
                unit_id=record.unit_id,
            ) from exc

    def _validate_layout(self, *, run_id: str) -> None:
        if self._root.is_symlink() or (self._root.exists() and not self._root.is_dir()):
            raise EngineError(
                EngineErrorCode.INTEGRITY_VIOLATION,
                "Skill runtime metadata directory is not a trusted directory.",
                run_id=run_id,
            )
        if self._path.is_symlink() or (
            self._path.exists() and not self._path.is_file()
        ):
            raise EngineError(
                EngineErrorCode.INTEGRITY_VIOLATION,
                "Skill runtime ownership record is not a trusted regular file.",
                run_id=run_id,
            )


class _ReentrantRunLedger:
    """Make one injected RunLedger safe for outer-engine plus inner-Harness locks."""

    def __init__(self, delegate: RunLedger) -> None:
        self.delegate = delegate
        self._state = threading.local()

    @contextmanager
    def lock(self, run_id: str, operation: str) -> Iterator[None]:
        depth = int(getattr(self._state, "depth", 0))
        if depth:
            self._state.depth = depth + 1
            try:
                yield
            finally:
                self._state.depth = depth
            return
        with self.delegate.lock(run_id, operation):
            self._state.depth = 1
            try:
                yield
            finally:
                self._state.depth = 0

    def load(self, run_id: str) -> RunAggregate | None:
        return self.delegate.load(run_id)

    def save(self, run: RunAggregate, *, expected_version: int) -> None:
        self.delegate.save(run, expected_version=expected_version)


class LocalRunEngine:
    """Deep module for one canonical local Run bound to one Workspace."""

    def __init__(
        self,
        workspace: str | Path,
        *,
        ledger: RunLedger,
        artifacts: ArtifactPort,
        skill_adapters: Mapping[str, SkillAdapter],
        acceptance: AcceptancePolicy,
        revision: HarnessRevision,
    ) -> None:
        workspace_path = Path(workspace).expanduser().resolve()
        if not workspace_path.is_dir():
            raise EngineError(
                EngineErrorCode.INVALID_WORKSPACE,
                f"Workspace must be an existing directory: {workspace_path}",
            )
        self.workspace = workspace_path
        self._raw_ledger = ledger
        self._ledger = _ReentrantRunLedger(ledger)
        self._artifacts = artifacts
        self._skill_adapters = dict(skill_adapters)
        self._acceptance = acceptance
        self._revision = revision
        self._runtime_owners = _RuntimeOwnerStore(workspace_path)
        self._harness = Harness(
            ledger=self._ledger,
            artifacts=artifacts,
            acceptance=acceptance,
            revision=revision,
        )
        self._invocation_lock = threading.Lock()
        self._run_id = self._discover_run_id()

    @classmethod
    def for_workspace(
        cls,
        workspace: str | Path,
        *,
        skill_adapters: Mapping[str, SkillAdapter],
        acceptance: AcceptancePolicy,
        revision: HarnessRevision,
    ) -> LocalRunEngine:
        """Build the default local engine without imposing storage on tests."""

        try:
            from research_harness.storage import (
                FilesystemArtifacts,
                FilesystemRunLedger,
            )
        except ImportError as exc:
            raise EngineError(
                EngineErrorCode.STORAGE_FAILURE,
                "Filesystem storage adapters are unavailable.",
            ) from exc
        workspace_path = Path(workspace).expanduser().resolve()
        if not workspace_path.is_dir():
            raise EngineError(
                EngineErrorCode.INVALID_WORKSPACE,
                f"Workspace must be an existing directory: {workspace_path}",
            )
        return cls(
            workspace_path,
            ledger=FilesystemRunLedger(workspace_path),
            artifacts=FilesystemArtifacts(workspace_path),
            skill_adapters=skill_adapters,
            acceptance=acceptance,
            revision=revision,
        )

    def execute(self, command: LocalRunCommand) -> EngineResult:
        if not isinstance(
            command,
            (
                CreateLocalRun,
                AdvanceRun,
                ApproveLocalCheckpoint,
                RecoverLocalRun,
            ),
        ):
            raise EngineError(
                EngineErrorCode.INVALID_COMMAND,
                f"Unsupported local Run command: {type(command).__name__}",
            )
        if self._has_legacy_v2_evidence():
            raise EngineError(
                EngineErrorCode.LEGACY_READ_ONLY,
                "Legacy Run evidence is read-only to the current engine.",
            )

        with self._exclusive_invocation():
            if isinstance(command, CreateLocalRun):
                candidate = command.run_id.strip() or f"run_{uuid4().hex}"
                return self._under_workspace_lock(
                    candidate,
                    "engine.create-local-run",
                    lambda: self._create(command, candidate),
                )

            self._refresh_bound_run_id()
            run_id = self._require_run_id()
            operation = {
                AdvanceRun: "engine.advance-run",
                ApproveLocalCheckpoint: "engine.approve-local-checkpoint",
                RecoverLocalRun: "engine.recover-local-run",
            }[type(command)]
            return self._under_workspace_lock(
                run_id,
                operation,
                lambda: self._dispatch_bound(command),
            )

    def _project_run_units(self, run: RunView | None) -> None:
        """Project committed Unit status into the Workspace UNITS.csv projection.

        The canonical authority is the Run aggregate in ``.harness-v3``; UNITS.csv
        is a human- and skill-readable projection. Some repository Skills (e.g.
        the contract auditor) read Unit status from UNITS.csv, so keep it faithful
        as the Run advances. UNITS.csv is exempt from the post-Completion drift
        comparison (see ``case._MUTABLE_PROJECTION_PATHS``), so rewriting it here
        does not trip the immutable-output check. No-op when UNITS.csv is absent,
        which keeps in-memory and stub Workspaces untouched.
        """

        if run is None:
            return
        units_path = self.workspace / "UNITS.csv"
        if not units_path.is_file():
            return
        status_by_unit = {unit.plan.id: unit.status.value for unit in run.units}
        if not status_by_unit:
            return
        try:
            with units_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = reader.fieldnames or []
                if "unit_id" not in fieldnames or "status" not in fieldnames:
                    return
                rows = list(reader)
        except (OSError, csv.Error):
            return

        changed = False
        for row in rows:
            unit_id = (row.get("unit_id") or "").strip()
            projected = status_by_unit.get(unit_id)
            if projected is not None and row.get("status") != projected:
                row["status"] = projected
                changed = True
        if not changed:
            return

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        try:
            self._atomic_write_text(units_path, buffer.getvalue())
        except OSError:
            return

    @staticmethod
    def _atomic_write_text(path: Path, text: str) -> None:
        handle = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        )
        try:
            with handle:
                handle.write(text)
            os.replace(handle.name, path)
        except OSError:
            try:
                os.unlink(handle.name)
            except OSError:
                pass
            raise

    def inspect(self) -> EngineInspection:
        if self._has_legacy_v2_evidence():
            return EngineInspection(
                workspace=self.workspace,
                state=InspectionState.LEGACY_READ_ONLY,
                issues=("Legacy Run detected; use its retained read-only inspector.",),
            )
        with self._exclusive_invocation():
            self._refresh_bound_run_id()
            if not self._run_id:
                return EngineInspection(
                    workspace=self.workspace,
                    state=InspectionState.EMPTY,
                    issues=("No current Run is bound to this Workspace.",),
                )
            return self._under_workspace_lock(
                self._run_id,
                "engine.inspect",
                self._inspect_bound,
            )

    def _create(self, command: CreateLocalRun, candidate: str) -> EngineResult:
        self._refresh_bound_run_id()
        if self._run_id:
            raise EngineError(
                EngineErrorCode.RUN_EXISTS,
                f"Workspace is already bound to Run {self._run_id}.",
                run_id=self._run_id,
            )
        result = self._harness.execute(CreateRun(plan=command.plan, run_id=candidate))
        self._run_id = result.run.id
        return EngineResult(
            command="create-local-run",
            outcome=EngineOutcome.CREATED,
            inspection=self._inspection(result.run),
        )

    def _dispatch_bound(self, command: LocalRunCommand) -> EngineResult:
        self._refresh_bound_run_id()
        self._require_run_id()
        if isinstance(command, AdvanceRun):
            return self._advance(command)
        if isinstance(command, ApproveLocalCheckpoint):
            return self._approve(command)
        if isinstance(command, RecoverLocalRun):
            return self._recover(command)
        raise EngineError(
            EngineErrorCode.INVALID_COMMAND,
            f"Unsupported bound Run command: {type(command).__name__}",
        )

    def _advance(self, command: AdvanceRun) -> EngineResult:
        try:
            until = AdvanceUntil(command.until)
        except ValueError as exc:
            raise EngineError(
                EngineErrorCode.INVALID_COMMAND,
                f"Unsupported advance limit: {command.until!r}",
                run_id=self._run_id,
            ) from exc

        recovery = self._harness.execute(ReconcileRun(run_id=self._run_id))
        recovered = recovery.outcome is ResultOutcome.RECONCILED
        if recovery.outcome is ResultOutcome.BLOCKED:
            return EngineResult(
                command="advance-run",
                outcome=EngineOutcome.BLOCKED,
                inspection=self._inspection(recovery.run),
                issues=_bounded_issues(recovery.issues or (recovery.message,)),
            )
        if recovery.run.active_attempt_id:
            issue = _active_attempt_recovery_issue(recovery.run)
            return EngineResult(
                command="advance-run",
                outcome=EngineOutcome.BLOCKED,
                inspection=self._inspection(recovery.run),
                issues=(issue,),
                recovered=recovered,
            )

        requested_unit = command.unit_id.strip()
        unit_ids: list[str] = []
        attempt_ids: list[str] = []
        while True:
            inspection = self._inspect_bound()
            run = inspection.run
            if run is None:
                raise EngineError(
                    EngineErrorCode.RUN_NOT_FOUND,
                    "The canonical Run disappeared during advance.",
                    run_id=self._run_id,
                )
            if run.status is RunStatus.COMPLETED:
                return EngineResult(
                    command="advance-run",
                    outcome=EngineOutcome.COMPLETED,
                    inspection=inspection,
                    unit_ids=tuple(unit_ids),
                    attempt_ids=tuple(attempt_ids),
                    recovered=recovered,
                )

            unit = self._select_unit(run, requested_unit)
            if unit is None:
                if (
                    requested_unit
                    and run.unit(requested_unit).status is UnitStatus.DONE
                ):
                    outcome = EngineOutcome.NOOP
                    issues: tuple[str, ...] = ()
                else:
                    outcome = EngineOutcome.BLOCKED
                    issues = ("No Unit is runnable from the current durable state.",)
                return EngineResult(
                    command="advance-run",
                    outcome=outcome,
                    inspection=inspection,
                    unit_ids=tuple(unit_ids),
                    attempt_ids=tuple(attempt_ids),
                    issues=issues,
                    recovered=recovered,
                )

            if _is_human(unit) and not _has_active_approval(run, unit):
                return EngineResult(
                    command="advance-run",
                    outcome=EngineOutcome.WAITING_FOR_CHECKPOINT,
                    inspection=inspection,
                    unit_ids=tuple(unit_ids),
                    attempt_ids=tuple(attempt_ids),
                    issues=(
                        f"Checkpoint {unit.plan.checkpoint} requires explicit approval.",
                    ),
                    recovered=recovered,
                )

            adapter = None if _is_human(unit) else self._adapter_for(unit)
            step = self._execute_unit(unit, adapter=adapter)
            if step.unit_id:
                unit_ids.append(step.unit_id)
            if step.attempt_id:
                attempt_ids.append(step.attempt_id)
            # Keep UNITS.csv faithful to committed status before the next Unit
            # runs, so skills reading UNITS.csv see the true state mid-advance.
            self._project_run_units(step.inspection.run)
            if step.outcome in {
                EngineOutcome.BLOCKED,
                EngineOutcome.SKILL_FAILED,
            }:
                return EngineResult(
                    command="advance-run",
                    outcome=step.outcome,
                    inspection=step.inspection,
                    unit_ids=tuple(unit_ids),
                    attempt_ids=tuple(attempt_ids),
                    issues=step.issues,
                    recovered=recovered,
                )
            if step.inspection.state is InspectionState.COMPLETED:
                return EngineResult(
                    command="advance-run",
                    outcome=EngineOutcome.COMPLETED,
                    inspection=step.inspection,
                    unit_ids=tuple(unit_ids),
                    attempt_ids=tuple(attempt_ids),
                    recovered=recovered,
                )
            if requested_unit or until is AdvanceUntil.AFTER_ONE:
                return EngineResult(
                    command="advance-run",
                    outcome=EngineOutcome.ADVANCED,
                    inspection=step.inspection,
                    unit_ids=tuple(unit_ids),
                    attempt_ids=tuple(attempt_ids),
                    recovered=recovered,
                )

    def _execute_unit(
        self,
        unit: UnitView,
        *,
        adapter: SkillAdapter | None,
    ) -> _StepResult:
        context = None
        retry_baseline: dict[str, ArtifactEvidence] | None = None
        if not _is_human(unit):
            try:
                context = SkillContext(
                    workspace=self.workspace,
                    unit_id=unit.plan.id,
                    inputs=unit.plan.all_input_paths,
                    outputs=unit.plan.all_output_paths,
                    checkpoint=unit.plan.checkpoint,
                )
            except SkillRuntimeError as exc:
                raise EngineError(
                    EngineErrorCode.SKILL_CONTEXT_INVALID,
                    f"Skill context for Unit {unit.plan.id} is unsafe: "
                    f"{type(exc).__name__}.",
                    run_id=self._run_id,
                    unit_id=unit.plan.id,
                ) from exc
            retry_baseline = self._retry_output_baseline(unit)
        begun = self._harness.execute(
            BeginAttempt(run_id=self._run_id, unit_id=unit.plan.id)
        )
        if begun.outcome is ResultOutcome.BLOCKED:
            return _StepResult(
                outcome=EngineOutcome.BLOCKED,
                inspection=self._inspection(begun.run),
                issues=_bounded_issues(begun.issues or (begun.message,)),
            )
        attempt_id = begun.attempt_id

        # The Unit is now DOING in the canonical Run. Project that into UNITS.csv
        # before invoking the skill subprocess so a skill that reads UNITS.csv
        # status (e.g. the contract auditor) sees prior Units as DONE and itself
        # as DOING, matching the legacy runner's contract.
        self._project_run_units(begun.run)

        if context is not None:
            assert adapter is not None
            try:
                skill_result = self._invoke_skill(
                    adapter,
                    context,
                    attempt_id=attempt_id,
                    unit_id=unit.plan.id,
                )
                if not skill_result.succeeded:
                    issue = _reported_skill_failure(
                        skill_result,
                        workspace=self.workspace,
                    )
                    return self._fail_skill_attempt(unit, attempt_id, issue)
                reuse_issue = self._retry_reuse_issue(unit, retry_baseline)
                if reuse_issue:
                    return self._fail_skill_attempt(unit, attempt_id, reuse_issue)
            except EngineError:
                raise
            except (SkillRuntimeError, OSError) as exc:
                issue = _skill_failure_issue(
                    exc,
                    adapter=adapter,
                    workspace=self.workspace,
                )
                return self._fail_skill_attempt(unit, attempt_id, issue)
            except Exception as exc:
                adapter_name = _redact_diagnostic(
                    adapter.adapter,
                    workspace=self.workspace,
                )
                issue = f"Skill adapter {adapter_name!r} raised {type(exc).__name__}."
                return self._fail_skill_attempt(unit, attempt_id, issue)

        completed = self._harness.execute(
            CompleteAttempt(run_id=self._run_id, attempt_id=attempt_id)
        )
        if completed.outcome is ResultOutcome.BLOCKED:
            return _StepResult(
                outcome=EngineOutcome.BLOCKED,
                inspection=self._inspection(completed.run),
                unit_id=unit.plan.id,
                attempt_id=attempt_id,
                issues=_bounded_issues(completed.issues or (completed.message,)),
            )
        return _StepResult(
            outcome=EngineOutcome.ADVANCED,
            inspection=self._inspection(completed.run),
            unit_id=unit.plan.id,
            attempt_id=attempt_id,
        )

    def _invoke_skill(
        self,
        adapter: SkillAdapter,
        context: SkillContext,
        *,
        attempt_id: str,
        unit_id: str,
    ) -> SkillResult:
        if not isinstance(adapter, LifecycleSkillAdapter):
            return adapter.run(context)
        execution = adapter.start(context)
        if not isinstance(execution, SkillExecutionHandle):
            raise EngineError(
                EngineErrorCode.ADAPTER_FAILURE,
                "Lifecycle Skill adapter returned an invalid execution handle.",
                run_id=self._run_id,
                unit_id=unit_id,
            )
        try:
            self._runtime_owners.record(
                run_id=self._run_id,
                attempt_id=attempt_id,
                unit_id=unit_id,
                owner=execution.owner,
                workspace=self.workspace,
            )
        except Exception:
            execution.terminate()
            raise
        try:
            execution.release()
            result = execution.wait()
        except Exception as exc:
            try:
                execution.terminate()
            except Exception:
                pass
            if execution.is_alive():
                raise EngineError(
                    EngineErrorCode.ADAPTER_FAILURE,
                    "Skill lifecycle failed while its recorded process owner remains live.",
                    run_id=self._run_id,
                    unit_id=unit_id,
                ) from exc
            self._runtime_owners.clear(
                run_id=self._run_id,
                attempt_id=attempt_id,
            )
            raise
        self._runtime_owners.clear(
            run_id=self._run_id,
            attempt_id=attempt_id,
        )
        return result

    def _retry_output_baseline(
        self,
        unit: UnitView,
    ) -> dict[str, ArtifactEvidence] | None:
        run = self._harness.inspect(self._run_id)
        is_retry = any(
            attempt.unit_id == unit.plan.id
            and attempt.status is AttemptStatus.FAILED_RETRYABLE
            for attempt in run.attempts
        )
        if not is_retry:
            return None
        return self._snapshot_required_outputs(unit)

    def _snapshot_required_outputs(
        self,
        unit: UnitView,
    ) -> dict[str, ArtifactEvidence]:
        try:
            evidence = self._artifacts.snapshot(
                self._run_id,
                unit.plan.required_outputs,
            )
        except Exception as exc:
            raise EngineError(
                EngineErrorCode.ADAPTER_FAILURE,
                f"Required output snapshot failed with {type(exc).__name__}.",
                run_id=self._run_id,
                unit_id=unit.plan.id,
            ) from exc
        return {item.path: item for item in evidence}

    def _retry_reuse_issue(
        self,
        unit: UnitView,
        baseline: dict[str, ArtifactEvidence] | None,
    ) -> str:
        if baseline is None or not baseline:
            return ""
        current = self._snapshot_required_outputs(unit)
        unchanged = tuple(
            path
            for path in unit.plan.required_outputs
            if path in baseline and current.get(path) == baseline[path]
        )
        if not unchanged:
            return ""
        return _clip(
            "Retry must produce a new evidence version for every existing required "
            f"output; unchanged: {', '.join(unchanged)}."
        )

    def _fail_skill_attempt(
        self,
        unit: UnitView,
        attempt_id: str,
        issue: str,
    ) -> _StepResult:
        failed = self._harness.execute(
            FailAttempt(run_id=self._run_id, attempt_id=attempt_id, reason=_clip(issue))
        )
        return _StepResult(
            outcome=EngineOutcome.SKILL_FAILED,
            inspection=self._inspection(failed.run),
            unit_id=unit.plan.id,
            attempt_id=attempt_id,
            issues=(_clip(issue),),
        )

    def _approve(self, command: ApproveLocalCheckpoint) -> EngineResult:
        checkpoint = command.checkpoint.strip()
        if not checkpoint:
            raise EngineError(
                EngineErrorCode.INVALID_COMMAND,
                "checkpoint must be non-empty.",
                run_id=self._run_id,
            )
        result = self._harness.execute(
            ApproveCheckpoint(run_id=self._run_id, checkpoint=checkpoint)
        )
        return EngineResult(
            command="approve-local-checkpoint",
            outcome=EngineOutcome.APPROVED,
            inspection=self._inspection(result.run),
        )

    def _recover(self, command: RecoverLocalRun | None = None) -> EngineResult:
        command = command or RecoverLocalRun()
        if not isinstance(command.interrupt_active, bool):
            raise EngineError(
                EngineErrorCode.INVALID_COMMAND,
                "interrupt_active must be a boolean.",
                run_id=self._run_id,
            )
        result = self._harness.execute(ReconcileRun(run_id=self._run_id))
        if result.outcome is ResultOutcome.NOOP and result.run.active_attempt_id:
            issue = _active_attempt_recovery_issue(result.run)
            if not command.interrupt_active:
                return EngineResult(
                    command="recover-local-run",
                    outcome=EngineOutcome.BLOCKED,
                    inspection=self._inspection(result.run),
                    issues=(issue,),
                )
            owner = self._runtime_owners.load(
                run_id=self._run_id,
                attempt_id=result.run.active_attempt_id,
                required=False,
            )
            if owner is None and self._active_attempt_requires_owner(result.run):
                return EngineResult(
                    command="recover-local-run",
                    outcome=EngineOutcome.BLOCKED,
                    inspection=self._inspection(result.run),
                    issues=(
                        "Lifecycle-backed active Attempt has no trustworthy process "
                        "ownership metadata; explicit interruption was refused.",
                    ),
                )
            if owner is not None and owner.is_live():
                return EngineResult(
                    command="recover-local-run",
                    outcome=EngineOutcome.BLOCKED,
                    inspection=self._inspection(result.run),
                    issues=(
                        "Recorded Skill subprocess owner is still live; explicit "
                        "interruption was refused.",
                    ),
                )
            if owner is not None:
                self._runtime_owners.clear(
                    run_id=self._run_id,
                    attempt_id=result.run.active_attempt_id,
                )
            interrupted = self._harness.execute(
                FailAttempt(
                    run_id=self._run_id,
                    attempt_id=result.run.active_attempt_id,
                    reason=(
                        "Interrupted by explicit local recovery while holding the "
                        "Workspace invocation lock."
                    ),
                )
            )
            return EngineResult(
                command="recover-local-run",
                outcome=EngineOutcome.RECOVERED,
                inspection=self._inspection(interrupted.run),
                issues=("Active Attempt was durably marked interrupted/retryable.",),
                recovered=True,
            )
        outcome = {
            ResultOutcome.RECONCILED: EngineOutcome.RECOVERED,
            ResultOutcome.NOOP: EngineOutcome.NOOP,
            ResultOutcome.BLOCKED: EngineOutcome.BLOCKED,
        }.get(result.outcome)
        if outcome is None:
            raise EngineError(
                EngineErrorCode.INTEGRITY_VIOLATION,
                f"Unexpected recovery outcome: {result.outcome.value}",
                run_id=self._run_id,
            )
        return EngineResult(
            command="recover-local-run",
            outcome=outcome,
            inspection=self._inspection(result.run),
            issues=_bounded_issues(result.issues),
            recovered=outcome is EngineOutcome.RECOVERED,
        )

    def _active_attempt_requires_owner(self, run: RunView) -> bool:
        active_id = run.active_attempt_id
        attempt = next(
            (item for item in run.attempts if item.id == active_id),
            None,
        )
        if attempt is None:
            return True
        adapter = self._skill_adapters.get(attempt.skill)
        return adapter is None or isinstance(adapter, LifecycleSkillAdapter)

    def _adapter_for(self, unit: UnitView) -> SkillAdapter:
        adapter = self._skill_adapters.get(unit.plan.skill)
        if adapter is None:
            raise EngineError(
                EngineErrorCode.SKILL_ADAPTER_NOT_FOUND,
                f"No Skill adapter is registered for {unit.plan.skill!r}.",
                run_id=self._run_id,
                unit_id=unit.plan.id,
            )
        if not isinstance(adapter, SkillAdapter):
            raise EngineError(
                EngineErrorCode.ADAPTER_FAILURE,
                f"Registered adapter for {unit.plan.skill!r} does not satisfy SkillAdapter.",
                run_id=self._run_id,
                unit_id=unit.plan.id,
            )
        return adapter

    def _select_unit(self, run: RunView, requested_unit: str) -> UnitView | None:
        if requested_unit:
            unit = run.unit(requested_unit)
            return unit if _is_runnable(run, unit) else None
        return next((unit for unit in run.units if _is_runnable(run, unit)), None)

    def _inspect_bound(self) -> EngineInspection:
        return self._inspection(self._harness.inspect(self._require_run_id()))

    def _inspection(self, run: RunView) -> EngineInspection:
        next_unit = next(
            (unit for unit in run.units if _is_runnable(run, unit)),
            None,
        )
        waiting_checkpoint = ""
        if (
            next_unit is not None
            and _is_human(next_unit)
            and not _has_active_approval(run, next_unit)
        ):
            waiting_checkpoint = next_unit.plan.checkpoint
        issues: tuple[str, ...] = ()
        if run.active_attempt_id:
            issues = (f"Attempt {run.active_attempt_id} is still active.",)
        return EngineInspection(
            workspace=self.workspace,
            state=(
                InspectionState.COMPLETED
                if run.status is RunStatus.COMPLETED
                else InspectionState.ACTIVE
            ),
            run=run,
            next_unit_id=next_unit.plan.id if next_unit is not None else "",
            waiting_checkpoint=waiting_checkpoint,
            issues=_bounded_issues(issues),
        )

    def _discover_run_id(self) -> str:
        finder = getattr(self._raw_ledger, "current_run_id", None)
        if finder is None:
            return ""
        try:
            run_id = finder()
        except Exception as exc:
            raise EngineError(
                EngineErrorCode.STORAGE_FAILURE,
                f"Canonical Run discovery failed with {type(exc).__name__}.",
            ) from exc
        if run_id is None:
            return ""
        if not isinstance(run_id, str) or not run_id.strip():
            raise EngineError(
                EngineErrorCode.INTEGRITY_VIOLATION,
                "Storage returned an invalid canonical Run identity.",
            )
        return run_id.strip()

    def _refresh_bound_run_id(self) -> None:
        discovered = self._discover_run_id()
        if not discovered:
            return
        if self._run_id and self._run_id != discovered:
            raise EngineError(
                EngineErrorCode.INTEGRITY_VIOLATION,
                "Workspace canonical Run identity changed unexpectedly.",
                run_id=self._run_id,
                issues=(f"storage_run_id={discovered}",),
            )
        self._run_id = discovered

    def _require_run_id(self) -> str:
        if not self._run_id:
            raise EngineError(
                EngineErrorCode.RUN_NOT_FOUND,
                "No current Run is bound to this Workspace.",
            )
        return self._run_id

    def _has_legacy_v2_evidence(self) -> bool:
        legacy_root = self.workspace / ".harness"
        if legacy_root.is_symlink():
            return True
        if not legacy_root.exists():
            return False
        if not legacy_root.is_dir():
            return True
        try:
            next(legacy_root.iterdir())
        except StopIteration:
            return False
        except OSError:
            return True
        return True

    @contextmanager
    def _exclusive_invocation(self) -> Iterator[None]:
        if not self._invocation_lock.acquire(blocking=False):
            raise EngineError(
                EngineErrorCode.CONCURRENT_INVOCATION,
                "Another command already owns this LocalRunEngine.",
                run_id=self._run_id,
            )
        try:
            yield
        finally:
            self._invocation_lock.release()

    def _under_workspace_lock(
        self,
        run_id: str,
        operation: str,
        action: Callable[[], _ResultT],
    ) -> _ResultT:
        try:
            with self._ledger.lock(run_id, operation):
                return action()
        except EngineError:
            raise
        except HarnessError as exc:
            raise _engine_error_from_harness(exc) from exc
        except Exception as exc:
            diagnostic = _redact_diagnostic(str(exc), workspace=self.workspace)
            raise EngineError(
                EngineErrorCode.STORAGE_FAILURE,
                f"Workspace operation failed: {type(exc).__name__}: "
                f"{_clip(diagnostic)}",
                run_id=run_id,
            ) from exc


def _is_runnable(run: RunView, unit: UnitView) -> bool:
    if unit.status not in {UnitStatus.TODO, UnitStatus.BLOCKED}:
        return False
    statuses = {item.plan.id: item.status for item in run.units}
    return all(
        statuses.get(dependency) is UnitStatus.DONE
        for dependency in unit.plan.depends_on
    )


def _is_human(unit: UnitView) -> bool:
    return unit.plan.owner is Owner.HUMAN or unit.plan.skill == "human-checkpoint"


def _has_active_approval(run: RunView, unit: UnitView) -> bool:
    return any(
        approval.active
        and approval.unit_id == unit.plan.id
        and approval.checkpoint == unit.plan.checkpoint
        for approval in run.checkpoint_approvals
    )


def _skill_failure_issue(
    exc: Exception,
    *,
    adapter: SkillAdapter,
    workspace: Path,
) -> str:
    adapter_name = _redact_diagnostic(adapter.adapter, workspace=workspace)
    parts = [f"Skill adapter {adapter_name!r} failed with {type(exc).__name__}."]
    if isinstance(exc, SkillExecutionError):
        if exc.exit_code is not None:
            parts.append(f"exit_code={exc.exit_code}")
        if exc.stdout:
            stdout = _redact_diagnostic(exc.stdout, workspace=workspace)
            parts.append(f"stdout={_clip(stdout, limit=400)!r}")
        if exc.stderr:
            stderr = _redact_diagnostic(exc.stderr, workspace=workspace)
            parts.append(f"stderr={_clip(stderr, limit=400)!r}")
    return _clip(" ".join(parts))


def _reported_skill_failure(result: SkillResult, *, workspace: Path) -> str:
    adapter_name = _redact_diagnostic(result.adapter, workspace=workspace)
    parts = [f"Skill adapter {adapter_name!r} returned exit code {result.exit_code}."]
    if result.stdout:
        stdout = _redact_diagnostic(result.stdout, workspace=workspace)
        parts.append(f"stdout={_clip(stdout, limit=400)!r}")
    if result.stderr:
        stderr = _redact_diagnostic(result.stderr, workspace=workspace)
        parts.append(f"stderr={_clip(stderr, limit=400)!r}")
    return _clip(" ".join(parts))


def _active_attempt_recovery_issue(run: RunView) -> str:
    return _clip(
        f"Attempt {run.active_attempt_id} is still active; automatic recovery "
        "will not infer process death. After confirming its owner is gone, execute "
        "RecoverLocalRun(interrupt_active=True)."
    )


def _engine_error_from_harness(error: HarnessError) -> EngineError:
    code = {
        ErrorCode.RUN_NOT_FOUND: EngineErrorCode.RUN_NOT_FOUND,
        ErrorCode.RUN_EXISTS: EngineErrorCode.RUN_EXISTS,
        ErrorCode.REVISION_DRIFT: EngineErrorCode.REVISION_DRIFT,
        ErrorCode.CONCURRENT_INVOCATION: EngineErrorCode.CONCURRENT_INVOCATION,
        ErrorCode.CONCURRENT_WRITE: EngineErrorCode.CONCURRENT_INVOCATION,
        ErrorCode.ADAPTER_FAILURE: EngineErrorCode.ADAPTER_FAILURE,
        ErrorCode.RECOVERY_REQUIRED: EngineErrorCode.INTEGRITY_VIOLATION,
    }.get(error.code, EngineErrorCode.INVALID_COMMAND)
    return EngineError(
        code,
        error.message,
        run_id=error.run_id,
        unit_id=error.unit_id,
    )


def _bounded_issues(issues: Iterable[object]) -> tuple[str, ...]:
    return tuple(
        _clip(str(issue)) for issue in tuple(issues)[:_MAX_ISSUES] if str(issue).strip()
    )


def _redact_diagnostic(value: object, *, workspace: Path) -> str:
    text = str(value).replace(os.fspath(workspace), "<WORKSPACE>")
    text = text.replace(os.fspath(_REPO_ROOT), "<REPO>")
    text = _BEARER_SECRET.sub("Bearer <REDACTED>", text)
    return _SECRET_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}=<REDACTED>",
        text,
    )


def _is_safe_runtime_text(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _clip(value: str, *, limit: int = _MAX_ISSUE_CHARS) -> str:
    text = str(value).replace("\x00", "�")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"
