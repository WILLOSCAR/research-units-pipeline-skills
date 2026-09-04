"""The versionless public Interface for one Research Harness Workspace.

Callers choose an intent and inspect one read model.  Repository composition,
Workflow compilation, storage, recovery, Skill execution, and acceptance stay
behind this seam.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Union

from research_harness._local_runtime import (
    compose_inspection_engine,
    compose_repository_engine,
    initialize_repository_run,
    inspection_contract_issues,
)
from research_harness.domain import RunView as RunSnapshot
from research_harness.engine import (
    AdvanceRun,
    AdvanceUntil,
    ApproveLocalCheckpoint,
    EngineError,
    EngineInspection,
    EngineOutcome,
    EngineResult,
    InspectionState,
    RecoverLocalRun,
)
from research_harness.skills import SkillRuntimeError
from research_harness.storage import StorageError
from research_harness.workflows import WorkflowContractError


class RunOutcome(str, Enum):
    """Stable caller outcomes; internal transaction phases stay private."""

    CREATED = "CREATED"
    PROGRESSED = "PROGRESSED"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    NO_CHANGE = "NO_CHANGE"


class WorkspaceState(str, Enum):
    EMPTY = "EMPTY"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    LEGACY_READ_ONLY = "LEGACY_READ_ONLY"


@dataclass(frozen=True, slots=True)
class LegacyRunSummary:
    """Bounded, read-only identity recovered from a retained legacy Run."""

    id: str = ""
    goal_id: str = ""
    workflow: str = ""
    status: str = ""
    source_format: str = ""
    evidence_files: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Create:
    """Create one new Run without mutating an existing Workspace."""

    workflow: str | Path
    goal: str
    run_id: str = ""


@dataclass(frozen=True, slots=True)
class Advance:
    """Advance deterministically to a meaningful stop by default."""

    unit: str = ""
    single_step: bool = False


@dataclass(frozen=True, slots=True)
class Approve:
    checkpoint: str


@dataclass(frozen=True, slots=True)
class Recover:
    """Explicitly authorize interruption only after liveness is gone."""

    interrupt_active: bool = False


HarnessCommand = Union[Create, Advance, Approve, Recover]


class HarnessFault(RuntimeError):
    """One bounded public fault translated from implementation-specific errors."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        issues: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.issues = issues


@dataclass(frozen=True, slots=True)
class RunInspection:
    workspace: Path
    state: WorkspaceState
    run: RunSnapshot | LegacyRunSummary | None
    next_unit_id: str = ""
    waiting_checkpoint: str = ""
    issues: tuple[str, ...] = ()

    @property
    def run_id(self) -> str:
        return self.run.id if self.run is not None else ""

    @property
    def next_action(self) -> str:
        if self.state is WorkspaceState.LEGACY_READ_ONLY:
            return "Inspect the retained legacy Run; create a new Workspace to execute."
        if self.waiting_checkpoint:
            return f"Review and approve Checkpoint {self.waiting_checkpoint}."
        if self.next_unit_id:
            return f"Advance Unit {self.next_unit_id}."
        if self.state is WorkspaceState.COMPLETED:
            return "Inspect the Deliverable and its Evidence."
        if self.issues:
            return self.issues[0]
        return "No action is currently available."


@dataclass(frozen=True, slots=True)
class RunResult:
    outcome: RunOutcome
    inspection: RunInspection
    unit_ids: tuple[str, ...] = ()
    attempt_ids: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    recovered: bool = False


class ResearchHarness:
    """One deep Workspace-bound Module with execute and inspect operations."""

    def __init__(self, workspace: Path, *, repository: Path | None = None) -> None:
        self.workspace = _absolute_without_resolving(workspace)
        self.repository = (
            _absolute_without_resolving(repository) if repository is not None else None
        )

    @classmethod
    def open(
        cls,
        workspace: Path,
        *,
        repository: Path | None = None,
    ) -> ResearchHarness:
        return cls(workspace, repository=repository)

    def execute(self, command: HarnessCommand) -> RunResult:
        try:
            if self.workspace.exists():
                inspected = self.inspect()
                if inspected.state is WorkspaceState.LEGACY_READ_ONLY:
                    raise HarnessFault(
                        "legacy_read_only",
                        "Legacy Run evidence is read-only to the current Harness.",
                    )
            if isinstance(command, Create):
                repository = self._require_repository()
                result, _ = initialize_repository_run(
                    workspace=self.workspace,
                    repo_root=repository,
                    pipeline=command.workflow,
                    request=command.goal,
                    run_id=command.run_id,
                )
                return _result(result)

            engine = compose_repository_engine(
                workspace=self.workspace,
                repo_root=self._require_repository(),
            )
            if isinstance(command, Advance):
                until = (
                    AdvanceUntil.AFTER_ONE
                    if command.single_step or command.unit.strip()
                    else AdvanceUntil.BLOCKED_OR_COMPLETE
                )
                return _result(
                    engine.execute(AdvanceRun(unit_id=command.unit, until=until))
                )
            if isinstance(command, Approve):
                return _result(
                    engine.execute(
                        ApproveLocalCheckpoint(checkpoint=command.checkpoint)
                    )
                )
            if isinstance(command, Recover):
                return _result(
                    engine.execute(
                        RecoverLocalRun(interrupt_active=command.interrupt_active)
                    )
                )
            raise HarnessFault(
                "invalid_command",
                f"Unsupported Harness command: {type(command).__name__}",
            )
        except HarnessFault:
            raise
        except Exception as exc:
            raise _fault(exc) from None

    def inspect(self) -> RunInspection:
        if not self.workspace.exists():
            return RunInspection(
                workspace=self.workspace,
                state=WorkspaceState.EMPTY,
                run=None,
                issues=("No current Run is bound to this Workspace.",),
            )
        try:
            inspection = compose_inspection_engine(workspace=self.workspace).inspect()
            contract_issues = inspection_contract_issues(workspace=self.workspace)
            legacy_summary: LegacyRunSummary | None = None
            legacy_issues: tuple[str, ...] = ()
            if inspection.state is InspectionState.LEGACY_READ_ONLY:
                legacy_summary, legacy_issues = _read_legacy_run_summary(self.workspace)
            if contract_issues:
                inspection = replace(
                    inspection,
                    issues=tuple(dict.fromkeys((*inspection.issues, *contract_issues))),
                )
            return _inspection(
                inspection,
                legacy_summary=legacy_summary,
                extra_issues=legacy_issues,
            )
        except Exception as exc:
            raise _fault(exc) from None

    def _require_repository(self) -> Path:
        if self.repository is None:
            raise HarnessFault(
                "repository_required",
                "Executing a Run requires a Research Harness source repository.",
            )
        return self.repository


def _result(result: EngineResult) -> RunResult:
    outcomes = {
        EngineOutcome.CREATED: RunOutcome.CREATED,
        EngineOutcome.ADVANCED: RunOutcome.PROGRESSED,
        EngineOutcome.APPROVED: RunOutcome.PROGRESSED,
        EngineOutcome.RECOVERED: RunOutcome.PROGRESSED,
        EngineOutcome.COMPLETED: RunOutcome.COMPLETED,
        EngineOutcome.WAITING_FOR_CHECKPOINT: RunOutcome.WAITING,
        EngineOutcome.BLOCKED: RunOutcome.BLOCKED,
        EngineOutcome.SKILL_FAILED: RunOutcome.BLOCKED,
        EngineOutcome.NOOP: RunOutcome.NO_CHANGE,
    }
    return RunResult(
        outcome=outcomes[result.outcome],
        inspection=_inspection(result.inspection),
        unit_ids=result.unit_ids,
        attempt_ids=result.attempt_ids,
        issues=result.issues,
        recovered=result.recovered,
    )


def _inspection(
    inspection: EngineInspection,
    *,
    legacy_summary: LegacyRunSummary | None = None,
    extra_issues: tuple[str, ...] = (),
) -> RunInspection:
    states = {
        InspectionState.EMPTY: WorkspaceState.EMPTY,
        InspectionState.ACTIVE: WorkspaceState.ACTIVE,
        InspectionState.COMPLETED: WorkspaceState.COMPLETED,
        InspectionState.LEGACY_READ_ONLY: WorkspaceState.LEGACY_READ_ONLY,
    }
    return RunInspection(
        workspace=inspection.workspace,
        state=states[inspection.state],
        run=legacy_summary if legacy_summary is not None else inspection.run,
        next_unit_id=inspection.next_unit_id,
        waiting_checkpoint=inspection.waiting_checkpoint,
        issues=tuple(dict.fromkeys((*inspection.issues, *extra_issues))),
    )


def _absolute_without_resolving(value: str | os.PathLike[str]) -> Path:
    raw = Path(value).expanduser()
    return Path(os.path.abspath(os.fspath(raw)))


def _read_legacy_run_summary(
    workspace: Path,
) -> tuple[LegacyRunSummary, tuple[str, ...]]:
    root = workspace / ".harness"
    if root.is_symlink() or not root.is_dir():
        return (
            LegacyRunSummary(),
            ("Legacy evidence root is missing or unsafe.",),
        )
    payloads: dict[str, dict[str, object]] = {}
    evidence_files: list[str] = []
    issues: list[str] = []
    for name in ("run.json", "goal.json", "harness.lock.json"):
        path = root / name
        if path.is_symlink():
            issues.append(f"Legacy evidence file is a symbolic link: .harness/{name}")
            continue
        if not path.is_file():
            continue
        evidence_files.append(f".harness/{name}")
        try:
            content = path.read_bytes()
            if len(content) > 1024 * 1024:
                raise ValueError("file exceeds the 1 MiB inspection limit")
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("top-level JSON value is not an object")
            payloads[name] = payload
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            issues.append(
                f"Could not read retained legacy evidence .harness/{name}: {exc}"
            )

    run = payloads.get("run.json", {})
    goal = payloads.get("goal.json", {})
    lock = payloads.get("harness.lock.json", {})
    return (
        LegacyRunSummary(
            id=_bounded_legacy_text(run.get("run_id") or lock.get("run_id")),
            goal_id=_bounded_legacy_text(run.get("goal_id") or goal.get("goal_id")),
            workflow=_bounded_legacy_text(
                run.get("workflow") or goal.get("workflow") or lock.get("workflow")
            ),
            status=_bounded_legacy_text(run.get("state") or run.get("status")),
            source_format=_bounded_legacy_text(lock.get("schema")),
            evidence_files=tuple(evidence_files),
        ),
        tuple(issues),
    )


def _bounded_legacy_text(value: object) -> str:
    text = str(value or "").strip()
    if any(ord(character) < 32 for character in text):
        return ""
    return text[:500]


def _fault(error: Exception) -> HarnessFault:
    if isinstance(error, EngineError):
        return HarnessFault(
            error.code.value,
            error.message,
            issues=error.issues,
        )
    if isinstance(error, WorkflowContractError):
        issues = tuple(
            f"{issue.code}: {issue.message}" for issue in getattr(error, "issues", ())
        )
        return HarnessFault("workflow_invalid", str(error), issues=issues)
    if isinstance(error, StorageError):
        return HarnessFault("storage_failure", str(error))
    if isinstance(error, SkillRuntimeError):
        return HarnessFault("adapter_failure", str(error))
    if isinstance(error, FileNotFoundError):
        return HarnessFault("not_found", str(error))
    if isinstance(error, (OSError, TypeError, ValueError)):
        return HarnessFault("invalid_request", str(error))
    return HarnessFault(
        "internal_failure",
        f"Harness implementation failed with {type(error).__name__}.",
    )
