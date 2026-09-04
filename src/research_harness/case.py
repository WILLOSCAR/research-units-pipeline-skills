"""Loop-first public Interface projected from one canonical Research Harness Run.

``Loop`` deliberately owns no durable state.  It translates caller intents to
the retained versionless ``ResearchHarness`` implementation and derives every
read from the canonical ``.harness-v3`` Run plus its pinned Workflow snapshot.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Union

from research_harness._local_runtime import inspection_contract_issues
from research_harness.domain import (
    ArtifactEvidence,
    CompletionPhase,
    ManifestStatus,
    RunStatus,
    RunView,
)
from research_harness.workflows import CASE_KIND_BY_WORKFLOW
from research_harness.harness import (
    Advance as _Advance,
    Approve as _Approve,
    Create as _Create,
    HarnessFault as _HarnessFault,
    ResearchHarness as _ResearchHarness,
    RunInspection as _RunInspection,
    WorkspaceState as _WorkspaceState,
)
from research_harness.storage import FilesystemArtifacts, StorageError


_CASE_CONTRACT_KEYS = frozenset(
    {
        "kind",
        "views",
        "claim_sources",
        "evidence_sources",
        "decision_sources",
    }
)
_PROJECTION_ROLES = (
    "views",
    "claim_sources",
    "evidence_sources",
    "decision_sources",
)
# Human- and skill-readable Workspace files that are live projections of the
# canonical Run, not immutable Evidence. They are recorded as committed
# artifacts (so the required-check binding invariant stays consistent), but the
# Run rewrites them as it advances (e.g. UNITS.csv status), so the
# post-Completion drift comparison exempts them from hash equality while still
# requiring them to exist. Mirrors the legacy engine's MUTABLE_PROJECTION_PATHS.
_MUTABLE_PROJECTION_PATHS = frozenset(
    {
        "STATUS.md",
        "UNITS.csv",
        "CHECKPOINTS.md",
        "DECISIONS.md",
        "output/QUALITY_GATE.md",
        "output/RUN_ERRORS.md",
        "output/CONTRACT_REPORT.md",
        "output/DOCTOR_REPORT.md",
        "output/DOCTOR_REPORT.json",
        "output/RUN_AUDIT.md",
        "output/RUN_AUDIT.json",
        "output/IMPROVEMENT_REPORT.md",
        "output/IMPROVEMENT_REPORT.json",
        "output/ARTIFACT_PACK.md",
        "output/ARTIFACT_PACK.json",
    }
)
_MAX_CONTRACT_BYTES = 4 * 1024 * 1024
_MAX_EXPLANATION_CHARS = 500


class LoopKind(str, Enum):
    BRIEF = "brief"
    REVIEW = "review"
    EVIDENCE_SYNTHESIS = "evidence-synthesis"
    SURVEY = "survey"
    IDEAS = "ideas"
    TUTORIAL = "tutorial"


class LoopState(str, Enum):
    EMPTY = "EMPTY"
    WORKING = "WORKING"
    NEEDS_DECISION = "NEEDS_DECISION"
    READY = "READY"
    BLOCKED = "BLOCKED"
    LEGACY_READ_ONLY = "LEGACY_READ_ONLY"


class LoopQualityState(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    PASSED = "PASSED"
    PENDING = "PENDING"
    BLOCKED = "BLOCKED"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class LoopQualitySignal:
    status: LoopQualityState
    explanation: str

    def __post_init__(self) -> None:
        explanation = _bounded_text(self.explanation)
        if not explanation:
            raise ValueError("Loop quality explanation must be non-empty.")
        object.__setattr__(self, "explanation", explanation)


@dataclass(frozen=True, slots=True)
class LoopQuality:
    execution_integrity: LoopQualitySignal
    contract_acceptance: LoopQualitySignal
    research_quality: LoopQualitySignal


@dataclass(frozen=True, slots=True)
class Start:
    goal: str
    kind: LoopKind
    formats: tuple[str, ...] = ()
    case_id: str = ""


@dataclass(frozen=True, slots=True)
class Continue:
    pass


@dataclass(frozen=True, slots=True)
class Decide:
    pass


_LoopIntent = Union[Start, Continue, Decide]


class LoopFault(RuntimeError):
    """Stable Loop-level fault with bounded diagnostics."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        issues: tuple[str, ...] = (),
    ) -> None:
        bounded_message = _bounded_text(message)
        super().__init__(bounded_message)
        self.code = _bounded_text(code, limit=96) or "case_failure"
        self.message = bounded_message
        self.issues = tuple(
            _bounded_text(issue) for issue in issues[:16] if _bounded_text(issue)
        )


@dataclass(frozen=True, slots=True)
class LoopArtifact:
    path: str
    role: str
    exists: bool
    sha256: str | None = None
    size: int | None = None


@dataclass(frozen=True, slots=True)
class PendingDecision:
    prompt: str
    reviewed_artifacts: tuple[LoopArtifact, ...]


@dataclass(frozen=True, slots=True)
class LoopDetails:
    """Bounded implementation detail for an explicitly expanded Loop view."""

    workflow: str
    status: str
    version: int
    steps_total: int
    steps_completed: int
    steps_blocked: int
    attempts: int
    completions: int


@dataclass(frozen=True, slots=True)
class LoopInspection:
    workspace: Path
    state: LoopState
    quality: LoopQuality
    case_id: str = ""
    question: str = ""
    kind: LoopKind | None = None
    views: tuple[LoopArtifact, ...] = ()
    claim_sources: tuple[LoopArtifact, ...] = ()
    evidence_sources: tuple[LoopArtifact, ...] = ()
    decision_sources: tuple[LoopArtifact, ...] = ()
    pending_decision: PendingDecision | None = None
    normalized_claims_available: bool = False
    issues: tuple[str, ...] = ()
    details: LoopDetails | None = None

    @property
    def artifacts(self) -> tuple[LoopArtifact, ...]:
        return (
            *self.views,
            *self.claim_sources,
            *self.evidence_sources,
            *self.decision_sources,
        )

    @property
    def next_action(self) -> str:
        if self.state is LoopState.EMPTY:
            return "Start this Loop with a research question and intended result."
        if self.state is LoopState.LEGACY_READ_ONLY:
            return (
                "Inspect retained legacy Evidence; start a new Loop to continue work."
            )
        if self.state is LoopState.NEEDS_DECISION:
            if self.pending_decision is not None:
                return self.pending_decision.prompt
            return "Review the current Decision evidence, then decide how to continue."
        if self.state is LoopState.READY:
            return (
                "Review the result and its Evidence; READY does not establish "
                "research truth."
            )
        if self.state is LoopState.BLOCKED:
            return "Resolve the blocking issue, then continue this Loop."
        return "Continue working toward the next meaningful stop."


@dataclass(frozen=True, slots=True)
class LoopResult:
    inspection: LoopInspection
    issues: tuple[str, ...] = ()

    @property
    def state(self) -> LoopState:
        return self.inspection.state


@dataclass(frozen=True, slots=True)
class _LoopContract:
    kind: LoopKind
    views: tuple[str, ...]
    claim_sources: tuple[str, ...]
    evidence_sources: tuple[str, ...]
    decision_sources: tuple[str, ...]
    decision_prompt: str = ""


class Loop:
    """A living research object projected from one canonical Run."""

    def __init__(
        self,
        workspace: Path,
        *,
        repository: Path | None = None,
    ) -> None:
        self.workspace = _absolute_without_resolving(workspace)
        self.repository = (
            _absolute_without_resolving(repository) if repository is not None else None
        )
        self._harness = _ResearchHarness.open(
            self.workspace,
            repository=self.repository,
        )

    @classmethod
    def open(
        cls,
        workspace: Path,
        *,
        repository: Path | None = None,
    ) -> Loop:
        return cls(workspace, repository=repository)

    def advance(self, intent: _LoopIntent) -> LoopResult:
        _validate_workspace(self.workspace, allow_missing=True)
        if not isinstance(intent, (Start, Continue, Decide)):
            raise LoopFault(
                "invalid_intent",
                f"Unsupported Loop intent: {type(intent).__name__}.",
            )

        if isinstance(intent, Start):
            current = self.inspect()
            if current.state is LoopState.LEGACY_READ_ONLY:
                raise LoopFault(
                    "legacy_read_only",
                    "Retained legacy Evidence is read-only; start the Loop in a new Workspace.",
                )
            if current.state is not LoopState.EMPTY:
                raise LoopFault(
                    "case_exists",
                    "This Workspace already contains a Loop; continue it instead.",
                )
            goal = _required_goal(intent.goal)
            try:
                kind = LoopKind(intent.kind)
            except (TypeError, ValueError) as exc:
                raise LoopFault("invalid_kind", "Start.kind is not supported.") from exc
            workflow = _workflow_for(kind, intent.formats)
            try:
                created = self._harness.execute(
                    _Create(
                        workflow=workflow,
                        goal=goal,
                        run_id=_optional_text(intent.case_id, "case_id"),
                    )
                )
            except Exception as exc:
                raise _case_fault(exc) from None
            created_result = self._result(created.issues)
            if created_result.state is not LoopState.WORKING:
                return created_result
            return self._continue()

        current = self.inspect()
        if current.state is LoopState.EMPTY:
            raise LoopFault("case_not_found", "No Loop exists in this Workspace.")
        if current.state is LoopState.LEGACY_READ_ONLY:
            raise LoopFault(
                "legacy_read_only",
                "Retained legacy Evidence is read-only; canonical Loop claims are unavailable.",
            )

        if isinstance(intent, Continue):
            return self._continue()

        if isinstance(intent, Decide):
            base = self._base_inspection()
            waiting = base.waiting_checkpoint
            if current.state is not LoopState.NEEDS_DECISION or not waiting:
                raise LoopFault(
                    "decision_not_expected",
                    "This Loop is not waiting for a Decision.",
                )
            try:
                approved = self._harness.execute(_Approve(checkpoint=waiting))
            except Exception as exc:
                raise _case_fault(exc) from None
            approved_result = self._result(
                approved.issues,
            )
            if approved_result.state is not LoopState.WORKING:
                return approved_result
            return self._continue()

        raise LoopFault("invalid_intent", "Unsupported Loop intent.")

    def inspect(self, *, details: bool = False) -> LoopInspection:
        _validate_workspace(self.workspace, allow_missing=True)
        base = self._base_inspection()

        if base.state is _WorkspaceState.EMPTY:
            return LoopInspection(
                workspace=self.workspace,
                state=LoopState.EMPTY,
                quality=_quality(
                    state=LoopState.EMPTY,
                    execution_verified=False,
                ),
                issues=(),
                details=None,
            )

        if base.state is _WorkspaceState.LEGACY_READ_ONLY:
            issues = _bounded_issues(
                (
                    *base.issues,
                    "Canonical Loop claims are unavailable for retained legacy Evidence.",
                )
            )
            return LoopInspection(
                workspace=self.workspace,
                state=LoopState.LEGACY_READ_ONLY,
                quality=_quality(
                    state=LoopState.LEGACY_READ_ONLY,
                    execution_verified=False,
                ),
                case_id=base.run_id,
                normalized_claims_available=False,
                issues=issues,
                details=_case_details(base) if details else None,
            )

        if not isinstance(base.run, RunView):
            raise LoopFault(
                "canonical_state_unavailable",
                "The canonical Loop state could not be decoded.",
            )

        contract, projection_issues = _read_case_contract(
            self.workspace,
            expected_workflow=base.run.goal.workflow,
            waiting_checkpoint=base.waiting_checkpoint,
        )
        pinned_issues = tuple(inspection_contract_issues(workspace=self.workspace))
        run_issues = _current_run_issues(base.run)
        projected: Mapping[str, tuple[LoopArtifact, ...]] = {
            role: () for role in _PROJECTION_ROLES
        }
        if contract is not None:
            projected = _project_artifacts(self.workspace, contract)
        pending_decision: PendingDecision | None = None
        decision_issues: tuple[str, ...] = ()
        if contract is not None and base.waiting_checkpoint:
            pending_decision, decision_issues = _project_pending_decision(
                workspace=self.workspace,
                run=base.run,
                checkpoint=base.waiting_checkpoint,
                prompt=contract.decision_prompt,
            )
        evidence_issues = _run_evidence_issues(
            workspace=self.workspace,
            run=base.run,
            projected=projected,
        )
        issues = _bounded_issues(
            (
                *(_public_issue(issue) for issue in base.issues),
                *run_issues,
                *pinned_issues,
                *projection_issues,
                *decision_issues,
                *evidence_issues,
            )
        )

        state = _case_state(
            base,
            contract_available=contract is not None,
            issues=issues,
        )
        execution_verified = not (pinned_issues or projection_issues or evidence_issues)
        return LoopInspection(
            workspace=self.workspace,
            state=state,
            quality=_quality(
                state=state,
                execution_verified=execution_verified,
            ),
            case_id=base.run.id,
            question=base.run.goal.request,
            kind=contract.kind if contract is not None else None,
            views=projected["views"],
            claim_sources=projected["claim_sources"],
            evidence_sources=projected["evidence_sources"],
            decision_sources=projected["decision_sources"],
            pending_decision=pending_decision,
            normalized_claims_available=False,
            issues=issues,
            details=_case_details(base) if details else None,
        )

    def _base_inspection(self) -> _RunInspection:
        try:
            return self._harness.inspect()
        except Exception as exc:
            raise _case_fault(exc) from None

    def _continue(self) -> LoopResult:
        try:
            advanced = self._harness.execute(_Advance(single_step=False))
        except Exception as exc:
            raise _case_fault(exc) from None
        return self._result(advanced.issues)

    def _result(self, issues: tuple[str, ...]) -> LoopResult:
        inspection = self.inspect()
        return LoopResult(
            inspection=inspection,
            issues=_bounded_issues(
                _public_issue(issue)
                for issue in (*issues, *inspection.issues)
                if str(issue).strip()
            ),
        )


def _workflow_for(kind: LoopKind, formats: tuple[str, ...]) -> str:
    if isinstance(formats, (str, bytes)):
        raise LoopFault("invalid_formats", "Start.formats must be a tuple of strings.")
    normalized: set[str] = set()
    try:
        for item in formats:
            value = _required_text(item, "format").lower()
            normalized.add(value)
    except TypeError as exc:
        raise LoopFault(
            "invalid_formats", "Start.formats must be a tuple of strings."
        ) from exc
    unknown = normalized.difference({"pdf", "latex"})
    if unknown:
        raise LoopFault(
            "invalid_formats",
            "Start.formats contains an unsupported result format.",
        )
    if kind is LoopKind.SURVEY:
        return (
            "arxiv-survey-latex"
            if normalized.intersection({"pdf", "latex"})
            else "arxiv-survey"
        )
    if normalized:
        raise LoopFault(
            "invalid_formats",
            "Start.formats is supported only for a survey Loop.",
        )
    return {
        LoopKind.BRIEF: "research-brief",
        LoopKind.REVIEW: "paper-review",
        LoopKind.EVIDENCE_SYNTHESIS: "evidence-review",
        LoopKind.IDEAS: "idea-brainstorm",
        LoopKind.TUTORIAL: "source-tutorial",
    }[kind]


def _case_state(
    inspection: _RunInspection,
    *,
    contract_available: bool,
    issues: tuple[str, ...],
) -> LoopState:
    run = inspection.run
    if not contract_available:
        return LoopState.BLOCKED
    if issues or (isinstance(run, RunView) and run.status is RunStatus.BLOCKED):
        return LoopState.BLOCKED
    if inspection.waiting_checkpoint:
        return LoopState.NEEDS_DECISION
    if inspection.state is _WorkspaceState.COMPLETED:
        return LoopState.READY
    return LoopState.WORKING


def _case_details(inspection: _RunInspection) -> LoopDetails:
    run = inspection.run
    if isinstance(run, RunView):
        statuses = tuple(unit.status.value for unit in run.units)
        return LoopDetails(
            workflow=run.goal.workflow,
            status=run.status.value,
            version=run.version,
            steps_total=len(run.units),
            steps_completed=sum(status == "DONE" for status in statuses),
            steps_blocked=sum(status == "BLOCKED" for status in statuses),
            attempts=len(run.attempts),
            completions=len(run.completions),
        )
    return LoopDetails(
        workflow=_bounded_text(getattr(run, "workflow", ""), limit=200),
        status=_bounded_text(getattr(run, "status", ""), limit=96),
        version=0,
        steps_total=0,
        steps_completed=0,
        steps_blocked=0,
        attempts=0,
        completions=0,
    )


def _quality(*, state: LoopState, execution_verified: bool) -> LoopQuality:
    execution = LoopQualitySignal(
        LoopQualityState.VERIFIED
        if execution_verified
        else LoopQualityState.UNVERIFIED,
        (
            "Canonical state decoded and pinned Loop contracts verified."
            if execution_verified
            else "Canonical state and pinned Loop contracts are not both verified."
        ),
    )
    if state is LoopState.READY:
        acceptance = LoopQualitySignal(
            LoopQualityState.PASSED,
            "The declared result contract completed with current Evidence.",
        )
    elif state is LoopState.BLOCKED:
        acceptance = LoopQualitySignal(
            LoopQualityState.BLOCKED,
            "The declared result contract is blocked or its Evidence is incomplete.",
        )
    elif state is LoopState.LEGACY_READ_ONLY:
        acceptance = LoopQualitySignal(
            LoopQualityState.UNVERIFIED,
            "Contract acceptance is unavailable from the canonical Loop projection.",
        )
    else:
        acceptance = LoopQualitySignal(
            LoopQualityState.PENDING,
            "The declared result contract has not completed yet.",
        )
    research = LoopQualitySignal(
        LoopQualityState.NOT_EVALUATED,
        "Research quality requires independent Evaluation; READY does not establish truth.",
    )
    return LoopQuality(
        execution_integrity=execution,
        contract_acceptance=acceptance,
        research_quality=research,
    )


def _current_run_issues(run: RunView) -> tuple[str, ...]:
    if run.status is not RunStatus.BLOCKED:
        return ()
    blocked_units = {
        unit.plan.id for unit in run.units if unit.status.value == "BLOCKED"
    }
    for attempt in reversed(run.attempts):
        if attempt.unit_id in blocked_units and attempt.status.value.startswith(
            "FAILED"
        ):
            return (_public_issue(attempt.message),)
    return ()


def _public_issue(value: object) -> str:
    text = _bounded_text(value)
    if text.startswith("Skill adapter"):
        marker = " stderr="
        if marker in text:
            detail = text.split(marker, 1)[1].strip()
            if len(detail) >= 2 and detail[0] == detail[-1] == "'":
                detail = detail[1:-1]
            detail = detail.replace("\\n", " ").strip()
            if detail:
                return _bounded_text(f"A private Recipe step stopped: {detail}")
        return "A private Recipe step stopped before it could produce its result."
    return text


def _read_case_contract(
    workspace: Path,
    *,
    expected_workflow: str,
    waiting_checkpoint: str = "",
) -> tuple[_LoopContract | None, tuple[str, ...]]:
    root = workspace / ".harness-v3"
    contracts = root / "contracts"
    snapshot = contracts / "workflow.json"
    if root.is_symlink() or contracts.is_symlink() or snapshot.is_symlink():
        raise LoopFault(
            "unsafe_case_contract",
            "Pinned Loop contract paths must not be symbolic links.",
        )
    if not snapshot.is_file():
        return None, ("Pinned Workflow snapshot has no Loop contract.",)
    try:
        content = snapshot.read_bytes()
    except OSError as exc:
        raise LoopFault(
            "case_contract_unreadable",
            "Pinned Workflow snapshot could not be read.",
        ) from exc
    if len(content) > _MAX_CONTRACT_BYTES:
        return None, ("Pinned Workflow snapshot exceeds the inspection limit.",)
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, ("Pinned Workflow snapshot is not valid JSON.",)
    if not isinstance(payload, dict):
        return None, ("Pinned Workflow snapshot must contain one object.",)
    if payload.get("schema") != "research-harness.workflow-snapshot/v2":
        return None, (
            "Pinned Workflow snapshot does not support the Loop projection contract.",
        )
    snapshot_workflow = payload.get("name")
    if snapshot_workflow != expected_workflow:
        return None, ("Pinned Workflow snapshot names a different private Recipe.",)
    raw_targets = payload.get("target_artifacts")
    if (
        not isinstance(raw_targets, list)
        or not raw_targets
        or any(not isinstance(item, str) or not item.strip() for item in raw_targets)
    ):
        return None, ("Pinned Workflow snapshot has no valid target Artifacts.",)
    targets = {item.strip() for item in raw_targets}
    raw = payload.get("case_contract")
    if not isinstance(raw, dict):
        return None, ("Pinned Workflow snapshot has no valid Loop contract.",)
    if set(raw) != _CASE_CONTRACT_KEYS:
        return None, ("Pinned Loop contract fields do not match the supported schema.",)
    try:
        kind = LoopKind(raw["kind"])
    except (TypeError, ValueError):
        return None, ("Pinned Loop contract kind is unsupported.",)
    expected_kind = CASE_KIND_BY_WORKFLOW.get(expected_workflow)
    if expected_kind is not None and kind.value != expected_kind:
        return None, ("Pinned Loop kind disagrees with its private Recipe.",)

    values: dict[str, tuple[str, ...]] = {}
    for role in _PROJECTION_ROLES:
        items = raw[role]
        if not isinstance(items, list) or any(
            not isinstance(item, str) for item in items
        ):
            return None, (f"Pinned Loop contract {role} must be a list of paths.",)
        paths = tuple(item.strip() for item in items)
        if (
            not paths
            or any(not path for path in paths)
            or len(set(paths)) != len(paths)
        ):
            return None, (
                f"Pinned Loop contract {role} must contain unique non-empty paths.",
            )
        if any(path not in targets for path in paths):
            return None, (
                f"Pinned Loop contract {role} references an undeclared target Artifact.",
            )
        values[role] = paths
    decision_prompt = ""
    if waiting_checkpoint:
        stages = payload.get("stages")
        if not isinstance(stages, list):
            return None, ("Pinned Workflow snapshot has no Decision stages.",)
        prompts: list[str] = []
        for stage in stages:
            if (
                not isinstance(stage, dict)
                or stage.get("checkpoint") != waiting_checkpoint
            ):
                continue
            human = stage.get("human_checkpoint")
            if not isinstance(human, dict):
                continue
            approve = human.get("approve")
            question = human.get("question")
            if isinstance(approve, str) and approve.strip():
                prompts.append(f'Confirm "{approve.strip()}" and continue?')
            elif isinstance(question, str) and question.strip():
                prompts.append(question.strip())
        if len(set(prompts)) != 1:
            return None, (
                "Pinned Workflow snapshot has no unambiguous Decision prompt.",
            )
        decision_prompt = prompts[0]
    return (
        _LoopContract(
            kind=kind,
            views=values["views"],
            claim_sources=values["claim_sources"],
            evidence_sources=values["evidence_sources"],
            decision_sources=values["decision_sources"],
            decision_prompt=decision_prompt,
        ),
        (),
    )


def _project_artifacts(
    workspace: Path,
    contract: _LoopContract,
) -> Mapping[str, tuple[LoopArtifact, ...]]:
    by_role = {role: tuple(getattr(contract, role)) for role in _PROJECTION_ROLES}
    unique_paths = tuple(
        dict.fromkeys(path for paths in by_role.values() for path in paths)
    )
    for path in unique_paths:
        _validate_artifact_path(workspace, path)
    try:
        evidence = FilesystemArtifacts(workspace).snapshot(
            "case-projection", unique_paths
        )
    except StorageError as exc:
        raise _case_fault(exc) from None
    for path in unique_paths:
        _validate_artifact_path(workspace, path)
    evidence_by_path = {item.path: item for item in evidence}
    return {
        role: tuple(
            LoopArtifact(
                path=path,
                role=role,
                exists=path in evidence_by_path,
                sha256=(
                    evidence_by_path[path].sha256 if path in evidence_by_path else None
                ),
                size=(
                    evidence_by_path[path].size if path in evidence_by_path else None
                ),
            )
            for path in paths
        )
        for role, paths in by_role.items()
    }


def _project_pending_decision(
    *,
    workspace: Path,
    run: RunView,
    checkpoint: str,
    prompt: str,
) -> tuple[PendingDecision | None, tuple[str, ...]]:
    units = tuple(
        unit.plan
        for unit in run.units
        if unit.plan.checkpoint == checkpoint
        and (unit.plan.owner.value == "HUMAN" or unit.plan.skill == "human-checkpoint")
    )
    if not units:
        return None, ("Current Decision has no human review basis in the Run plan.",)
    paths = tuple(
        dict.fromkeys(
            path
            for unit in units
            for path in (*unit.inputs, *unit.outputs)
            if not path.startswith("?")
        )
    )
    for path in paths:
        _validate_artifact_path(workspace, path)
    try:
        evidence = FilesystemArtifacts(workspace).snapshot(run.id, paths)
    except StorageError as exc:
        raise _case_fault(exc) from None
    evidence_by_path = {item.path: item for item in evidence}
    return (
        PendingDecision(
            prompt=prompt,
            reviewed_artifacts=tuple(
                LoopArtifact(
                    path=path,
                    role="decision_basis",
                    exists=path in evidence_by_path,
                    sha256=(
                        evidence_by_path[path].sha256
                        if path in evidence_by_path
                        else None
                    ),
                    size=(
                        evidence_by_path[path].size
                        if path in evidence_by_path
                        else None
                    ),
                )
                for path in paths
            ),
        ),
        (),
    )


def _run_evidence_issues(
    *,
    workspace: Path,
    run: RunView,
    projected: Mapping[str, tuple[LoopArtifact, ...]],
) -> tuple[str, ...]:
    completed = run.status is RunStatus.COMPLETED
    try:
        manifests = FilesystemArtifacts(workspace).list_manifests(run.id)
    except StorageError as exc:
        raise _case_fault(exc) from None
    manifests_by_id = {manifest.id: manifest for manifest in manifests}
    issues: list[str] = []
    latest_evidence: dict[str, ArtifactEvidence] = {}
    referenced_manifests = {completion.manifest_id for completion in run.completions}
    orphan_count = sum(
        manifest.id not in referenced_manifests for manifest in manifests
    )
    if orphan_count:
        issues.append(
            "Execution recovery is required for "
            f"{orphan_count} detached Completion Manifest(s)."
        )
    for completion in run.completions:
        manifest = manifests_by_id.get(completion.manifest_id)
        expected_status = {
            CompletionPhase.PREPARED: ManifestStatus.PREPARED,
            CompletionPhase.COMMITTED: ManifestStatus.DONE,
            CompletionPhase.ABORTED: ManifestStatus.BLOCKED,
        }[completion.phase]
        if manifest is None:
            issues.append("Execution evidence is missing a Completion Manifest.")
        elif (
            manifest.status is not expected_status
            or manifest.completion_id != completion.id
            or manifest.unit_id != completion.unit_id
            or manifest.attempt_id != completion.attempt_id
            or manifest.artifacts != completion.artifacts
            or manifest.acceptance != completion.acceptance
        ):
            issues.append("Execution evidence disagrees with its Completion Manifest.")
        if completion.phase is CompletionPhase.PREPARED:
            issues.append("Execution recovery is required for a prepared Completion.")
        if completion.phase is not CompletionPhase.COMMITTED:
            continue
        for artifact in completion.artifacts:
            latest_evidence[artifact.path] = artifact

    try:
        current_evidence = FilesystemArtifacts(workspace).snapshot(
            run.id,
            latest_evidence,
        )
    except StorageError as exc:
        raise _case_fault(exc) from None
    current_by_path = {artifact.path: artifact for artifact in current_evidence}
    for path, expected in latest_evidence.items():
        current = current_by_path.get(path)
        if current is None:
            issues.append(f"Committed Loop evidence is missing: {path}.")
        elif current != expected and path not in _MUTABLE_PROJECTION_PATHS:
            issues.append(f"Committed Loop evidence changed after Completion: {path}.")

    if not completed:
        return _bounded_issues(issues)

    artifacts = tuple(
        dict.fromkeys(
            artifact
            for role in _PROJECTION_ROLES
            for artifact in projected.get(role, ())
        )
    )
    for artifact in artifacts:
        if not artifact.exists:
            issues.append(f"Declared Loop Artifact is missing: {artifact.path}.")
            continue
        expected = latest_evidence.get(artifact.path)
        if expected is None:
            issues.append(
                f"Declared Loop Artifact has no committed evidence: {artifact.path}."
            )
            continue
        if artifact.sha256 != expected.sha256 or artifact.size != expected.size:
            if artifact.path in _MUTABLE_PROJECTION_PATHS:
                continue
            issues.append(
                f"Declared Loop Artifact changed after Completion: {artifact.path}."
            )
    return _bounded_issues(issues)


def _validate_artifact_path(workspace: Path, value: str) -> None:
    if (
        not value
        or value == "."
        or value.startswith("?")
        or "\\" in value
        or ";" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise LoopFault(
            "unsafe_artifact", "Loop contract contains an unsafe Artifact path."
        )
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value.rstrip("/"))
    raw_parts = value.rstrip("/").split("/")
    if (
        not raw_parts
        or windows.is_absolute()
        or windows.drive
        or posix.is_absolute()
        or any(part in {"", ".", ".."} for part in raw_parts)
        or raw_parts[0] in {".harness", ".harness-v3"}
    ):
        raise LoopFault(
            "unsafe_artifact", "Loop contract contains an unsafe Artifact path."
        )

    candidate = workspace.joinpath(*posix.parts)
    current = workspace
    for part in posix.parts:
        current = current / part
        if current.is_symlink():
            raise LoopFault(
                "unsafe_artifact",
                "Loop Artifact projection refuses symbolic links.",
            )
        if not current.exists():
            break
    try:
        candidate.resolve(strict=False).relative_to(workspace.resolve(strict=True))
    except (OSError, RuntimeError, ValueError) as exc:
        raise LoopFault(
            "unsafe_artifact",
            "Loop Artifact path escapes the Workspace.",
        ) from exc
    if candidate.exists() and candidate.is_dir():
        for directory, directories, files in os.walk(candidate, followlinks=False):
            root = Path(directory)
            for name in (*directories, *files):
                if (root / name).is_symlink():
                    raise LoopFault(
                        "unsafe_artifact",
                        "Loop Artifact projection refuses symbolic links.",
                    )


def _validate_workspace(workspace: Path, *, allow_missing: bool) -> None:
    if workspace.is_symlink():
        raise LoopFault(
            "unsafe_workspace", "Loop Workspace must not be a symbolic link."
        )
    if workspace.exists() and not workspace.is_dir():
        raise LoopFault("unsafe_workspace", "Loop Workspace must be a directory.")
    if not allow_missing and not workspace.is_dir():
        raise LoopFault("case_not_found", "Loop Workspace does not exist.")
    if (
        workspace.is_dir()
        and _state_root_has_content(workspace / ".harness-v3")
        and _state_root_has_content(workspace / ".harness")
    ):
        raise LoopFault(
            "mixed_state_authority",
            "Workspace contains both current and legacy state authorities.",
        )


def _state_root_has_content(path: Path) -> bool:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        return True
    if not path.is_dir():
        return False
    try:
        return next(path.iterdir(), None) is not None
    except OSError:
        return True


def _absolute_without_resolving(value: str | os.PathLike[str]) -> Path:
    raw = Path(value).expanduser()
    return Path(os.path.abspath(os.fspath(raw)))


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise LoopFault("invalid_request", f"{label} must be a string.")
    result = value.strip()
    if not result or any(ord(character) < 32 for character in result):
        raise LoopFault(
            "invalid_request", f"{label} must be a non-empty single-line value."
        )
    return result


def _required_goal(value: object) -> str:
    if not isinstance(value, str):
        raise LoopFault("invalid_request", "goal must be a string.")
    result = value.strip()
    if not result or any(
        (ord(character) < 32 and character not in {"\n", "\r", "\t"})
        or ord(character) == 127
        for character in result
    ):
        raise LoopFault("invalid_request", "goal contains unsafe text.")
    return result


def _optional_text(value: object, label: str) -> str:
    if value == "":
        return ""
    return _required_text(value, label)


def _bounded_text(value: object, *, limit: int = _MAX_EXPLANATION_CHARS) -> str:
    text = " ".join(str(value or "").replace("\x00", "�").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _bounded_issues(values: Iterable[object], *, limit: int = 32) -> tuple[str, ...]:
    candidates = tuple(values)
    issues = tuple(
        dict.fromkeys(
            _bounded_text(value) for value in candidates if _bounded_text(value)
        )
    )
    if len(issues) <= limit:
        return issues
    remaining = len(issues) - (limit - 1)
    return (*issues[: limit - 1], f"{remaining} additional issues were omitted.")


def _case_fault(error: Exception) -> LoopFault:
    if isinstance(error, LoopFault):
        return error
    if isinstance(error, _HarnessFault):
        if error.code == "storage_failure":
            return LoopFault(
                "canonical_state_unavailable",
                "Canonical Loop state could not be read safely.",
            )
        return LoopFault(error.code, error.message, issues=error.issues)
    if isinstance(error, StorageError):
        return LoopFault("storage_failure", str(error))
    return LoopFault(
        "case_failure",
        f"Loop implementation failed with {type(error).__name__}.",
    )
