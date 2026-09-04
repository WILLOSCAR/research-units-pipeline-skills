from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union
from uuid import uuid4

from research_harness.domain.errors import ErrorCode, HarnessError
from research_harness.domain.model import (
    AcceptanceEvidence,
    ArtifactEvidence,
    AttemptStatus,
    CheckpointReviewBasis,
    CompletionManifest,
    CompletionPhase,
    CompletionView,
    Goal,
    HarnessRevision,
    ManifestStatus,
    Owner,
    RunAggregate,
    RunPlan,
    RunView,
    UnitPlan,
    UnitStatus,
)

from .ports import AcceptancePolicy, ArtifactPort, RunLedger


_ACCEPTANCE_EVIDENCE_CHANGED = (
    "Artifact evidence changed during acceptance evaluation; retry the Unit "
    "against a stable Workspace."
)


class ResultOutcome(str, Enum):
    CREATED = "CREATED"
    STARTED = "STARTED"
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    COMMITTED = "COMMITTED"
    RECONCILED = "RECONCILED"
    NOOP = "NOOP"


@dataclass(frozen=True, slots=True)
class CreateRun:
    plan: RunPlan
    run_id: str = ""


@dataclass(frozen=True, slots=True)
class BeginAttempt:
    run_id: str
    unit_id: str


@dataclass(frozen=True, slots=True)
class CompleteAttempt:
    run_id: str
    attempt_id: str
    message: str = "OK"


@dataclass(frozen=True, slots=True)
class FailAttempt:
    run_id: str
    attempt_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class ApproveCheckpoint:
    run_id: str
    checkpoint: str


@dataclass(frozen=True, slots=True)
class ReconcileRun:
    run_id: str


HarnessCommand = Union[
    CreateRun,
    BeginAttempt,
    CompleteAttempt,
    FailAttempt,
    ApproveCheckpoint,
    ReconcileRun,
]


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: str
    outcome: ResultOutcome
    run: RunView
    unit_id: str = ""
    attempt_id: str = ""
    completion_id: str = ""
    message: str = ""
    issues: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _CompletionAssessment:
    artifacts: tuple[ArtifactEvidence, ...]
    acceptance: AcceptanceEvidence | None
    issues: tuple[str, ...]
    is_final: bool


class Harness:
    """Deep module for one local, serialized, evidence-backed research Run.

    External callers only learn two entry points: ``execute(command)`` for all
    mutations and ``inspect(run_id)`` for a read-only view. A Harness instance
    represents the currently executing Pipeline/Kernel revision; CreateRun
    pins it and every later mutation fails closed on drift.
    """

    def __init__(
        self,
        *,
        ledger: RunLedger,
        artifacts: ArtifactPort,
        acceptance: AcceptancePolicy,
        revision: HarnessRevision,
    ) -> None:
        self._ledger = ledger
        self._artifacts = artifacts
        self._acceptance = acceptance
        self._revision = revision

    def execute(self, command: HarnessCommand) -> CommandResult:
        if not isinstance(
            command,
            (
                CreateRun,
                BeginAttempt,
                CompleteAttempt,
                FailAttempt,
                ApproveCheckpoint,
                ReconcileRun,
            ),
        ):
            raise HarnessError(
                ErrorCode.INVALID_COMMAND,
                f"Unsupported command: {type(command).__name__}",
            )
        if isinstance(command, CreateRun):
            run_id = command.run_id.strip() or _new_id("run")
            with self._ledger.lock(run_id, "create-run"):
                if self._ledger.load(run_id) is not None:
                    raise HarnessError(
                        ErrorCode.RUN_EXISTS,
                        f"Run {run_id} already exists.",
                        run_id=run_id,
                    )
                plan = _with_goal_id(command.plan)
                run = RunAggregate.create(
                    run_id=run_id, plan=plan, revision=self._revision
                )
                self._save(run, expected_version=0)
                return self._result("create-run", ResultOutcome.CREATED, run)

        run_id = command.run_id.strip()
        if not run_id:
            raise HarnessError(ErrorCode.INVALID_COMMAND, "run_id must be non-empty.")
        with self._ledger.lock(run_id, type(command).__name__):
            run = self._load(run_id)
            self._require_current_revision(run)
            if not isinstance(command, ReconcileRun) and (
                run.pending_completion() is not None or self._orphan_manifests(run)
            ):
                raise HarnessError(
                    ErrorCode.RECOVERY_REQUIRED,
                    "A durable PREPARED Completion must be reconciled before another mutation.",
                    run_id=run.id,
                )
            if isinstance(command, BeginAttempt):
                return self._begin(run, command)
            if isinstance(command, FailAttempt):
                return self._fail(run, command)
            if isinstance(command, ApproveCheckpoint):
                return self._approve(run, command)
            if isinstance(command, CompleteAttempt):
                return self._complete(run, command)
            if isinstance(command, ReconcileRun):
                return self._reconcile(run)
        raise HarnessError(
            ErrorCode.INVALID_COMMAND, f"Unsupported command: {type(command).__name__}"
        )

    def inspect(self, run_id: str) -> RunView:
        """Inspect durable evidence even when the executing revision has drifted."""

        run_id = run_id.strip()
        if not run_id:
            raise HarnessError(ErrorCode.INVALID_COMMAND, "run_id must be non-empty.")
        with self._ledger.lock(run_id, "inspect"):
            return self._load(run_id).view()

    def _begin(self, run: RunAggregate, command: BeginAttempt) -> CommandResult:
        if run.active_attempt_id:
            raise HarnessError(
                ErrorCode.ACTIVE_ATTEMPT_EXISTS,
                f"Attempt {run.active_attempt_id} already owns this Run.",
                run_id=run.id,
                unit_id=command.unit_id,
                attempt_id=run.active_attempt_id,
            )
        stale_checkpoint = self._stale_completed_checkpoint(run, command.unit_id)
        if stale_checkpoint is not None:
            checkpoint_unit, issue = stale_checkpoint
            expected = run.version
            run.revoke_checkpoint(checkpoint=checkpoint_unit.checkpoint, reason=issue)
            run.reopen_checkpoint(unit_id=checkpoint_unit.id, reason=issue)
            run.invalidate_downstream(root_unit_id=checkpoint_unit.id, reason=issue)
            self._save(run, expected_version=expected)
            return self._result(
                "begin-attempt",
                ResultOutcome.BLOCKED,
                run,
                unit_id=command.unit_id,
                message=issue,
                issues=(issue,),
            )
        expected = run.version
        attempt_id = _new_id("attempt")
        run.begin_attempt(unit_id=command.unit_id, attempt_id=attempt_id)
        self._save(run, expected_version=expected)
        return self._result(
            "begin-attempt",
            ResultOutcome.STARTED,
            run,
            unit_id=command.unit_id,
            attempt_id=attempt_id,
        )

    def _fail(self, run: RunAggregate, command: FailAttempt) -> CommandResult:
        if not command.reason.strip():
            raise HarnessError(
                ErrorCode.INVALID_COMMAND,
                "FailAttempt.reason must be non-empty.",
                run_id=run.id,
                attempt_id=command.attempt_id,
            )
        attempt = _attempt(run, command.attempt_id)
        expected = run.version
        run.fail_attempt(attempt_id=command.attempt_id, reason=command.reason.strip())
        self._save(run, expected_version=expected)
        return self._result(
            "fail-attempt",
            ResultOutcome.BLOCKED,
            run,
            unit_id=attempt.unit_id,
            attempt_id=attempt.id,
            message=command.reason.strip(),
            issues=(command.reason.strip(),),
        )

    def _approve(self, run: RunAggregate, command: ApproveCheckpoint) -> CommandResult:
        unit = _active_checkpoint_unit(run, command.checkpoint)
        requirements = run.plan.review_artifacts(unit.id)
        review_basis = self._checkpoint_review_basis(
            run_id=run.id,
            checkpoint=command.checkpoint,
            unit_id=unit.id,
            paths=tuple(path for path, _ in requirements),
        )
        missing = _missing_required(requirements, review_basis.artifacts)
        if missing:
            raise HarnessError(
                ErrorCode.INVALID_TRANSITION,
                f"Checkpoint {command.checkpoint} review basis is missing: {', '.join(missing)}.",
                run_id=run.id,
                unit_id=unit.id,
                details={"missing_artifacts": missing},
            )
        if not review_basis.artifacts:
            raise HarnessError(
                ErrorCode.INVALID_TRANSITION,
                f"Checkpoint {command.checkpoint} has no review Artifacts to bind.",
                run_id=run.id,
                unit_id=unit.id,
            )
        if not review_basis.approved:
            raise HarnessError(
                ErrorCode.INVALID_TRANSITION,
                f"Checkpoint {command.checkpoint} Decision is not explicitly checked/approved.",
                run_id=run.id,
                unit_id=unit.id,
            )
        expected = run.version
        unit_id = run.approve_checkpoint(
            checkpoint=command.checkpoint,
            approval_id=_new_id("decision"),
            review_basis=review_basis,
        )
        self._save(run, expected_version=expected)
        return self._result(
            "approve-checkpoint",
            ResultOutcome.APPROVED,
            run,
            unit_id=unit_id,
            message=(
                f"Checkpoint {command.checkpoint} approved against "
                f"{len(review_basis.artifacts)} Artifacts."
            ),
        )

    def _complete(self, run: RunAggregate, command: CompleteAttempt) -> CommandResult:
        attempt = _attempt(run, command.attempt_id)
        if (
            attempt.status is not AttemptStatus.RUNNING
            or run.active_attempt_id != attempt.id
        ):
            raise HarnessError(
                ErrorCode.INVALID_TRANSITION,
                f"Attempt {attempt.id} is not the active RUNNING Attempt.",
                run_id=run.id,
                unit_id=attempt.unit_id,
                attempt_id=attempt.id,
            )
        unit = run.plan.unit(attempt.unit_id)

        checkpoint_issue = self._checkpoint_issue(run, unit)
        if checkpoint_issue:
            expected = run.version
            if unit.checkpoint:
                run.revoke_checkpoint(
                    checkpoint=unit.checkpoint, reason=checkpoint_issue
                )
            run.fail_attempt(attempt_id=attempt.id, reason=checkpoint_issue)
            self._save(run, expected_version=expected)
            return self._result(
                "complete-attempt",
                ResultOutcome.BLOCKED,
                run,
                unit_id=unit.id,
                attempt_id=attempt.id,
                message=checkpoint_issue,
                issues=(checkpoint_issue,),
            )

        assessment = self._assess_completion(run, unit)
        if assessment.issues:
            return self._reject_completion(
                run,
                attempt_id=attempt.id,
                issue="; ".join(assessment.issues),
            )
        if assessment.acceptance is None:
            raise HarnessError(
                ErrorCode.ADAPTER_FAILURE,
                "Completion assessment produced no acceptance evidence.",
                run_id=run.id,
                unit_id=unit.id,
                attempt_id=attempt.id,
            )

        completion_id = _new_id("completion")
        manifest_id = _new_id("manifest")
        manifest = CompletionManifest(
            id=manifest_id,
            completion_id=completion_id,
            run_id=run.id,
            unit_id=unit.id,
            attempt_id=attempt.id,
            status=ManifestStatus.PREPARED,
            artifacts=assessment.artifacts,
            acceptance=assessment.acceptance,
        )
        self._write_manifest(manifest)

        expected = run.version
        run.prepare_completion(
            completion_id=completion_id,
            attempt_id=attempt.id,
            manifest_id=manifest_id,
            artifacts=assessment.artifacts,
            acceptance=assessment.acceptance,
        )
        self._save(run, expected_version=expected)

        expected = run.version
        run.succeed_prepared_attempt(completion_id)
        self._save(run, expected_version=expected)

        self._set_manifest_status(manifest_id, ManifestStatus.DONE)
        expected = run.version
        run.commit_completion(completion_id)
        self._save(run, expected_version=expected)
        return self._result(
            "complete-attempt",
            ResultOutcome.COMMITTED,
            run,
            unit_id=unit.id,
            attempt_id=attempt.id,
            completion_id=completion_id,
            message=command.message,
        )

    def _reconcile(self, run: RunAggregate) -> CommandResult:
        completion = run.pending_completion()
        if completion is None:
            recovered = self._recover_orphan_manifest(run)
            if isinstance(recovered, CommandResult):
                return recovered
            completion = recovered
        if completion is None:
            return self._result(
                "reconcile-run",
                ResultOutcome.NOOP,
                run,
                message="No PREPARED Completion requires recovery.",
            )
        unit = run.plan.unit(completion.unit_id)
        issues: list[str] = []
        manifest = self._read_manifest(completion.manifest_id)
        if manifest is None:
            issues.append("PREPARED Completion Manifest is missing.")
        elif (
            manifest.completion_id != completion.id
            or manifest.run_id != run.id
            or manifest.unit_id != unit.id
            or manifest.attempt_id != completion.attempt_id
            or manifest.artifacts != completion.artifacts
            or manifest.acceptance != completion.acceptance
        ):
            issues.append(
                "PREPARED Completion Manifest identity or evidence disagrees with the Run ledger."
            )
        if manifest is not None and manifest.status is ManifestStatus.BLOCKED:
            issues.append(
                "Completion Manifest was durably BLOCKED by an earlier recovery attempt."
            )

        assessment = self._assess_completion(
            run,
            unit,
            validate_prior_required_checks=True,
        )
        if assessment.artifacts != completion.artifacts:
            issues.append(
                "Prepared Artifact fingerprints changed before Completion committed."
            )
        if (
            assessment.acceptance is not None
            and assessment.acceptance != completion.acceptance
        ):
            issues.append("Workflow acceptance changed during Completion recovery.")
        issues.extend(assessment.issues)
        checkpoint_issue = self._checkpoint_issue(run, unit)
        if checkpoint_issue:
            issues.append(checkpoint_issue)

        if issues:
            if manifest is not None:
                self._set_manifest_status(manifest.id, ManifestStatus.BLOCKED)
            expected = run.version
            if checkpoint_issue and unit.checkpoint:
                run.revoke_checkpoint(
                    checkpoint=unit.checkpoint, reason=checkpoint_issue
                )
            run.abort_completion(completion.id, reason="; ".join(issues))
            self._save(run, expected_version=expected)
            return self._result(
                "reconcile-run",
                ResultOutcome.BLOCKED,
                run,
                unit_id=unit.id,
                attempt_id=completion.attempt_id,
                completion_id=completion.id,
                message="; ".join(issues),
                issues=tuple(issues),
            )

        attempt = _attempt(run, completion.attempt_id)
        if attempt.status is AttemptStatus.RUNNING:
            expected = run.version
            run.succeed_prepared_attempt(completion.id)
            self._save(run, expected_version=expected)
        elif attempt.status is not AttemptStatus.SUCCEEDED:
            raise HarnessError(
                ErrorCode.INVALID_TRANSITION,
                f"Prepared Completion points to {attempt.status.value} Attempt {attempt.id}.",
                run_id=run.id,
                unit_id=unit.id,
                attempt_id=attempt.id,
            )

        self._set_manifest_status(completion.manifest_id, ManifestStatus.DONE)
        expected = run.version
        run.commit_completion(completion.id)
        self._save(run, expected_version=expected)
        return self._result(
            "reconcile-run",
            ResultOutcome.RECONCILED,
            run,
            unit_id=unit.id,
            attempt_id=completion.attempt_id,
            completion_id=completion.id,
            message="Recovered PREPARED Completion.",
        )

    def _reject_completion(
        self,
        run: RunAggregate,
        *,
        attempt_id: str,
        issue: str,
    ) -> CommandResult:
        attempt = _attempt(run, attempt_id)
        expected = run.version
        run.fail_attempt(attempt_id=attempt_id, reason=issue)
        self._save(run, expected_version=expected)
        return self._result(
            "complete-attempt",
            ResultOutcome.BLOCKED,
            run,
            unit_id=attempt.unit_id,
            attempt_id=attempt.id,
            message=issue,
            issues=(issue,),
        )

    def _checkpoint_issue(self, run: RunAggregate, unit: UnitPlan) -> str:
        if not unit.checkpoint or (
            unit.owner is not Owner.HUMAN and unit.skill != "human-checkpoint"
        ):
            return ""
        approval = run.active_approval(unit.checkpoint)
        if approval is None:
            return (
                f"Checkpoint {unit.checkpoint} has no active artifact-bound approval."
            )
        requirements = run.plan.review_artifacts(unit.id)
        current = self._checkpoint_review_basis(
            run_id=run.id,
            checkpoint=unit.checkpoint,
            unit_id=unit.id,
            paths=tuple(path for path, _ in requirements),
        )
        missing = _missing_required(requirements, current.artifacts)
        if missing:
            return f"Checkpoint {unit.checkpoint} review evidence is missing: {', '.join(missing)}."
        if not current.approved:
            return f"Checkpoint {unit.checkpoint} Decision is no longer explicitly checked/approved."
        if current != approval.review_basis:
            return f"Checkpoint {unit.checkpoint} approval is stale because reviewed Artifacts changed."
        return ""

    def _assess_completion(
        self,
        run: RunAggregate,
        unit: UnitPlan,
        *,
        validate_prior_required_checks: bool = False,
    ) -> _CompletionAssessment:
        is_final = all(
            other.id == unit.id or run.unit_status[other.id] is UnitStatus.DONE
            for other in run.plan.units
        )
        artifact_paths, required_paths = self._completion_artifact_contract(
            run,
            unit,
            is_final=is_final,
        )
        artifacts = self._snapshot(run.id, artifact_paths)
        issues: list[str] = []
        missing = _missing_required(
            tuple((path, True) for path in required_paths),
            artifacts,
        )
        if missing:
            issues.append(f"Required outputs are missing: {', '.join(missing)}.")
            return _CompletionAssessment(
                artifacts=artifacts,
                acceptance=None,
                issues=tuple(issues),
                is_final=is_final,
            )

        acceptance = self._evaluate(run, unit, artifacts)
        if not acceptance.passed:
            issues.extend(acceptance.issues or ("Workflow acceptance did not pass.",))

        mandatory = run.plan.goal.required_checks
        if (
            acceptance.passed
            and unit.skill in mandatory
            and unit.skill not in acceptance.checks
        ):
            issues.append(
                f"Mandatory check {unit.skill} did not explicitly attest its own skill."
            )
        covered: set[str] = set()
        if is_final or validate_prior_required_checks:
            freshness_issues, covered = self._required_check_freshness(run)
            issues.extend(freshness_issues)
        if is_final:
            if acceptance.passed and unit.skill in acceptance.checks:
                covered.add(unit.skill)
            uncovered = tuple(
                check
                for check in mandatory
                if check not in covered
                and not (not acceptance.passed and check == unit.skill)
            )
            if uncovered:
                issues.append(
                    "Required checks lack committed/current coverage: "
                    + ", ".join(uncovered)
                    + "."
                )
        current_artifacts = self._snapshot(run.id, artifact_paths)
        if current_artifacts != artifacts:
            issues.append(_ACCEPTANCE_EVIDENCE_CHANGED)
        artifacts = current_artifacts
        return _CompletionAssessment(
            artifacts=artifacts,
            acceptance=acceptance,
            issues=tuple(dict.fromkeys(issues)),
            is_final=is_final,
        )

    @staticmethod
    def _completion_artifact_contract(
        run: RunAggregate,
        unit: UnitPlan,
        *,
        is_final: bool,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        mandatory = unit.skill in run.plan.goal.required_checks
        projected_directories = tuple(
            path
            for path in unit.all_input_paths
            if path.endswith("/")
            and any(output.startswith(path) for output in unit.all_output_paths)
        )
        bound_paths = (
            (*unit.all_input_paths, *unit.all_output_paths)
            if mandatory
            else (*unit.all_output_paths, *projected_directories)
        )
        required_paths = (
            (*unit.required_inputs, *unit.required_outputs)
            if mandatory
            else (*unit.required_outputs, *projected_directories)
        )
        targets = run.plan.goal.target_artifacts if is_final else ()
        return (
            tuple(dict.fromkeys((*bound_paths, *targets))),
            tuple(dict.fromkeys((*required_paths, *targets))),
        )

    def _required_check_freshness(
        self,
        run: RunAggregate,
    ) -> tuple[tuple[str, ...], set[str]]:
        issues: list[str] = []
        covered: set[str] = set()
        mandatory = set(run.plan.goal.required_checks)
        current_completions = self._current_done_completions(run)
        by_unit = {
            unit.id: (index, unit, completion)
            for index, unit, completion in current_completions
        }
        for checker in run.plan.units:
            if (
                checker.skill not in mandatory
                or run.unit_status[checker.id] is not UnitStatus.DONE
            ):
                continue
            current = by_unit.get(checker.id)
            if current is None:
                issues.append(
                    f"Required check {checker.skill} is stale: DONE Unit {checker.id} has no current committed Completion evidence."
                )
                continue
            completion_index, _, completion = current
            if (
                not completion.acceptance.passed
                or checker.skill not in completion.acceptance.checks
            ):
                issues.append(
                    f"Required check {checker.skill} is stale: stored acceptance for Unit {checker.id} is not passed with exact self-attestation."
                )
                continue
            paths, required_paths = self._completion_artifact_contract(
                run,
                checker,
                is_final=False,
            )
            stored_by_path = {item.path: item for item in completion.artifacts}
            if (
                len(stored_by_path) != len(completion.artifacts)
                or any(path not in paths for path in stored_by_path)
                or any(path not in stored_by_path for path in required_paths)
            ):
                issues.append(
                    f"Required check {checker.skill} is stale: stored Artifact binding for Unit {checker.id} disagrees with its declared inputs/outputs."
                )
                continue
            current_by_path = {
                item.path: item
                for item in self._snapshot(run.id, tuple(stored_by_path))
            }
            stale_paths = tuple(
                path
                for path, stored_evidence in stored_by_path.items()
                if not self._artifact_lineage_is_current(
                    run,
                    source_index=completion_index,
                    source_unit=checker,
                    path=path,
                    source_evidence=stored_evidence,
                    current_evidence=current_by_path.get(path),
                    current_completions=current_completions,
                )
            )
            if stale_paths:
                issues.append(
                    f"Required check {checker.skill} is stale: bound Artifact evidence changed without declared in-place lineage for Unit {checker.id}: {', '.join(stale_paths)}."
                )
                continue
            covered.add(checker.skill)
        return tuple(issues), covered

    @staticmethod
    def _current_done_completions(
        run: RunAggregate,
    ) -> tuple[tuple[int, UnitPlan, CompletionView], ...]:
        latest: dict[str, tuple[int, CompletionView]] = {}
        for index, completion in enumerate(run.completions):
            if (
                completion.phase is CompletionPhase.COMMITTED
                and run.unit_status[completion.unit_id] is UnitStatus.DONE
            ):
                latest[completion.unit_id] = (index, completion)
        records = (
            (index, run.plan.unit(unit_id), completion)
            for unit_id, (index, completion) in latest.items()
        )
        return tuple(sorted(records, key=lambda item: item[0]))

    @classmethod
    def _artifact_lineage_is_current(
        cls,
        run: RunAggregate,
        *,
        source_index: int,
        source_unit: UnitPlan,
        path: str,
        source_evidence: ArtifactEvidence,
        current_evidence: ArtifactEvidence | None,
        current_completions: tuple[tuple[int, UnitPlan, CompletionView], ...],
    ) -> bool:
        if current_evidence == source_evidence:
            return True
        if current_evidence is None:
            return False

        producer_id = source_unit.id
        lineage_evidence = source_evidence
        for completion_index, producer, completion in current_completions:
            if completion_index <= source_index:
                continue
            declares_output = (
                any(output.startswith(path) for output in producer.all_output_paths)
                if path.endswith("/")
                else path in producer.all_output_paths
            )
            if not declares_output:
                continue
            produced_evidence = next(
                (item for item in completion.artifacts if item.path == path),
                None,
            )
            if produced_evidence is None:
                return False
            if produced_evidence == lineage_evidence:
                continue
            if not cls._producer_consumes_tracked_path(
                producer, path=path
            ) or not cls._unit_transitively_depends_on(
                run,
                unit_id=producer.id,
                ancestor_id=producer_id,
            ):
                return False
            producer_id = producer.id
            lineage_evidence = produced_evidence
        return lineage_evidence == current_evidence

    @staticmethod
    def _producer_consumes_tracked_path(producer: UnitPlan, *, path: str) -> bool:
        if path in producer.all_input_paths:
            return True
        if path.endswith("/"):
            return False
        return any(
            declared_input.endswith("/") and path.startswith(declared_input)
            for declared_input in producer.all_input_paths
        )

    @staticmethod
    def _unit_transitively_depends_on(
        run: RunAggregate,
        *,
        unit_id: str,
        ancestor_id: str,
    ) -> bool:
        units = {unit.id: unit for unit in run.plan.units}
        pending = list(units[unit_id].depends_on)
        seen: set[str] = set()
        while pending:
            dependency = pending.pop()
            if dependency == ancestor_id:
                return True
            if dependency in seen:
                continue
            seen.add(dependency)
            pending.extend(units[dependency].depends_on)
        return False

    def _stale_completed_checkpoint(
        self,
        run: RunAggregate,
        unit_id: str,
    ) -> tuple[UnitPlan, str] | None:
        units = {unit.id: unit for unit in run.plan.units}
        pending = list(run.plan.unit(unit_id).depends_on)
        seen: set[str] = set()
        while pending:
            ancestor_id = pending.pop()
            if ancestor_id in seen:
                continue
            seen.add(ancestor_id)
            ancestor = units[ancestor_id]
            pending.extend(ancestor.depends_on)
            if run.unit_status[ancestor_id] is not UnitStatus.DONE:
                continue
            issue = self._checkpoint_issue(run, ancestor)
            if issue:
                return ancestor, issue
        return None

    def _recover_orphan_manifest(
        self,
        run: RunAggregate,
    ) -> CompletionView | CommandResult | None:
        orphans = self._orphan_manifests(run)
        if not orphans:
            return None
        if len(orphans) != 1:
            raise HarnessError(
                ErrorCode.RECOVERY_REQUIRED,
                f"Run {run.id} has {len(orphans)} unlinked Completion Manifests; recovery is ambiguous.",
                run_id=run.id,
                details={"manifest_ids": tuple(manifest.id for manifest in orphans)},
            )

        manifest = orphans[0]
        if any(
            completion.id == manifest.completion_id for completion in run.completions
        ):
            raise HarnessError(
                ErrorCode.RECOVERY_REQUIRED,
                f"Orphan Manifest {manifest.id} reuses Completion {manifest.completion_id}.",
                run_id=run.id,
            )
        attempt = _attempt(run, manifest.attempt_id)
        if (
            attempt.status is not AttemptStatus.RUNNING
            or run.active_attempt_id != attempt.id
            or attempt.unit_id != manifest.unit_id
            or manifest.run_id != run.id
        ):
            raise HarnessError(
                ErrorCode.RECOVERY_REQUIRED,
                f"Orphan Manifest {manifest.id} does not match the active RUNNING Attempt.",
                run_id=run.id,
                unit_id=manifest.unit_id,
                attempt_id=manifest.attempt_id,
            )

        unit = run.plan.unit(manifest.unit_id)
        issues: list[str] = []
        if manifest.status is ManifestStatus.BLOCKED:
            issues.append("Orphan Completion Manifest was durably BLOCKED.")
        assessment = self._assess_completion(
            run,
            unit,
            validate_prior_required_checks=True,
        )
        if assessment.artifacts != manifest.artifacts:
            issues.append(
                "Orphan Manifest Artifact fingerprints changed before recovery."
            )
        if (
            assessment.acceptance is not None
            and assessment.acceptance != manifest.acceptance
        ):
            issues.append("Workflow acceptance changed before orphan recovery.")
        issues.extend(assessment.issues)
        checkpoint_issue = self._checkpoint_issue(run, unit)
        if checkpoint_issue:
            issues.append(checkpoint_issue)

        if issues:
            self._set_manifest_status(manifest.id, ManifestStatus.BLOCKED)
            expected = run.version
            if checkpoint_issue and unit.checkpoint:
                run.revoke_checkpoint(
                    checkpoint=unit.checkpoint,
                    reason=checkpoint_issue,
                )
            run.prepare_completion(
                completion_id=manifest.completion_id,
                attempt_id=attempt.id,
                manifest_id=manifest.id,
                artifacts=manifest.artifacts,
                acceptance=manifest.acceptance,
            )
            run.abort_completion(manifest.completion_id, reason="; ".join(issues))
            self._save(run, expected_version=expected)
            return self._result(
                "reconcile-run",
                ResultOutcome.BLOCKED,
                run,
                unit_id=unit.id,
                attempt_id=attempt.id,
                completion_id=manifest.completion_id,
                message="; ".join(issues),
                issues=tuple(issues),
            )

        expected = run.version
        run.prepare_completion(
            completion_id=manifest.completion_id,
            attempt_id=attempt.id,
            manifest_id=manifest.id,
            artifacts=manifest.artifacts,
            acceptance=manifest.acceptance,
        )
        self._save(run, expected_version=expected)
        return run.pending_completion()

    def _orphan_manifests(self, run: RunAggregate) -> tuple[CompletionManifest, ...]:
        referenced = {completion.manifest_id for completion in run.completions}
        return tuple(
            manifest
            for manifest in self._list_manifests(run.id)
            if manifest.id not in referenced
            and manifest.status in {ManifestStatus.PREPARED, ManifestStatus.BLOCKED}
        )

    def _require_current_revision(self, run: RunAggregate) -> None:
        if run.revision != self._revision:
            raise HarnessError(
                ErrorCode.REVISION_DRIFT,
                "Active Run does not match the executing Pipeline/Kernel revision; start a new Run.",
                run_id=run.id,
                details={
                    "pinned_revision": run.revision,
                    "executing_revision": self._revision,
                },
            )

    def _load(self, run_id: str) -> RunAggregate:
        run = self._ledger.load(run_id)
        if run is None:
            raise HarnessError(
                ErrorCode.RUN_NOT_FOUND, f"Run {run_id} does not exist.", run_id=run_id
            )
        return run

    def _save(self, run: RunAggregate, *, expected_version: int) -> None:
        try:
            self._ledger.save(run, expected_version=expected_version)
        except HarnessError:
            raise
        except Exception as exc:
            raise HarnessError(
                ErrorCode.ADAPTER_FAILURE,
                f"Run ledger write failed: {type(exc).__name__}: {exc}",
                run_id=run.id,
            ) from exc

    def _snapshot(
        self, run_id: str, paths: tuple[str, ...]
    ) -> tuple[ArtifactEvidence, ...]:
        try:
            evidence = self._artifacts.snapshot(run_id, paths)
        except HarnessError:
            raise
        except Exception as exc:
            raise HarnessError(
                ErrorCode.ADAPTER_FAILURE,
                f"Artifact inspection failed: {type(exc).__name__}: {exc}",
                run_id=run_id,
            ) from exc
        by_path = {item.path: item for item in evidence}
        return tuple(by_path[path] for path in paths if path in by_path)

    def _checkpoint_review_basis(
        self,
        *,
        run_id: str,
        checkpoint: str,
        unit_id: str,
        paths: tuple[str, ...],
    ) -> CheckpointReviewBasis:
        try:
            basis = self._artifacts.checkpoint_review_basis(
                run_id=run_id,
                checkpoint=checkpoint,
                unit_id=unit_id,
                paths=paths,
            )
        except HarnessError:
            raise
        except Exception as exc:
            raise HarnessError(
                ErrorCode.ADAPTER_FAILURE,
                f"Checkpoint review fingerprinting failed: {type(exc).__name__}: {exc}",
                run_id=run_id,
                unit_id=unit_id,
            ) from exc
        if (
            basis.schema != "checkpoint-review-basis.v1"
            or basis.checkpoint != checkpoint
            or basis.unit_id != unit_id
        ):
            raise HarnessError(
                ErrorCode.ADAPTER_FAILURE,
                "Artifact adapter returned a mismatched Checkpoint review basis.",
                run_id=run_id,
                unit_id=unit_id,
            )
        by_path = {item.path: item for item in basis.artifacts}
        return CheckpointReviewBasis(
            checkpoint=checkpoint,
            unit_id=unit_id,
            artifacts=tuple(by_path[path] for path in paths if path in by_path),
            approved=basis.approved,
        )

    def _evaluate(
        self,
        run: RunAggregate,
        unit: UnitPlan,
        artifacts: tuple[ArtifactEvidence, ...],
    ) -> AcceptanceEvidence:
        try:
            return self._acceptance.evaluate(
                run=run.view(), unit=unit, artifacts=artifacts
            )
        except HarnessError:
            raise
        except Exception as exc:
            raise HarnessError(
                ErrorCode.ADAPTER_FAILURE,
                f"Acceptance evaluation failed: {type(exc).__name__}: {exc}",
                run_id=run.id,
                unit_id=unit.id,
            ) from exc

    def _write_manifest(self, manifest: CompletionManifest) -> None:
        try:
            self._artifacts.write_manifest(manifest)
        except HarnessError:
            raise
        except Exception as exc:
            raise HarnessError(
                ErrorCode.ADAPTER_FAILURE,
                f"Completion Manifest write failed: {type(exc).__name__}: {exc}",
                run_id=manifest.run_id,
                unit_id=manifest.unit_id,
                attempt_id=manifest.attempt_id,
            ) from exc

    def _read_manifest(self, manifest_id: str) -> CompletionManifest | None:
        try:
            return self._artifacts.read_manifest(manifest_id)
        except HarnessError:
            raise
        except Exception as exc:
            raise HarnessError(
                ErrorCode.ADAPTER_FAILURE,
                f"Completion Manifest read failed: {type(exc).__name__}: {exc}",
            ) from exc

    def _list_manifests(self, run_id: str) -> tuple[CompletionManifest, ...]:
        try:
            manifests = self._artifacts.list_manifests(run_id)
        except HarnessError:
            raise
        except Exception as exc:
            raise HarnessError(
                ErrorCode.ADAPTER_FAILURE,
                f"Completion Manifest index read failed: {type(exc).__name__}: {exc}",
                run_id=run_id,
            ) from exc
        return tuple(manifest for manifest in manifests if manifest.run_id == run_id)

    def _set_manifest_status(self, manifest_id: str, status: ManifestStatus) -> None:
        try:
            self._artifacts.set_manifest_status(manifest_id, status)
        except HarnessError:
            raise
        except Exception as exc:
            raise HarnessError(
                ErrorCode.ADAPTER_FAILURE,
                f"Completion Manifest update failed: {type(exc).__name__}: {exc}",
                details={"manifest_id": manifest_id, "status": status.value},
            ) from exc

    @staticmethod
    def _result(
        command: str,
        outcome: ResultOutcome,
        run: RunAggregate,
        *,
        unit_id: str = "",
        attempt_id: str = "",
        completion_id: str = "",
        message: str = "",
        issues: tuple[str, ...] = (),
    ) -> CommandResult:
        return CommandResult(
            command=command,
            outcome=outcome,
            run=run.view(),
            unit_id=unit_id,
            attempt_id=attempt_id,
            completion_id=completion_id,
            message=message,
            issues=issues,
        )


def _attempt(run: RunAggregate, attempt_id: str):
    for attempt in run.attempts:
        if attempt.id == attempt_id:
            return attempt
    raise HarnessError(
        ErrorCode.ATTEMPT_NOT_FOUND,
        f"Run {run.id} has no Attempt {attempt_id}.",
        run_id=run.id,
        attempt_id=attempt_id,
    )


def _active_checkpoint_unit(run: RunAggregate, checkpoint: str) -> UnitPlan:
    candidates = [
        unit
        for unit in run.plan.units
        if unit.checkpoint == checkpoint
        and (unit.owner is Owner.HUMAN or unit.skill == "human-checkpoint")
        and run.unit_status[unit.id]
        in {UnitStatus.TODO, UnitStatus.DOING, UnitStatus.BLOCKED}
        and all(
            run.unit_status[dependency] is UnitStatus.DONE
            for dependency in unit.depends_on
        )
    ]
    if len(candidates) != 1:
        raise HarnessError(
            ErrorCode.CHECKPOINT_NOT_FOUND,
            f"Checkpoint {checkpoint} must resolve to exactly one active HUMAN Unit; found {len(candidates)}.",
            run_id=run.id,
        )
    return candidates[0]


def _missing_required(
    requirements: tuple[tuple[str, bool], ...],
    evidence: tuple[ArtifactEvidence, ...],
) -> tuple[str, ...]:
    present = {item.path for item in evidence}
    return tuple(
        path for path, required in requirements if required and path not in present
    )


def _with_goal_id(plan: RunPlan) -> RunPlan:
    if plan.goal.id.strip():
        return plan
    goal = Goal(
        id=_new_id("goal"),
        request=plan.goal.request,
        workflow=plan.goal.workflow,
        constraints=plan.goal.constraints,
        target_artifacts=plan.goal.target_artifacts,
        success_criteria=plan.goal.success_criteria,
    )
    return RunPlan(goal=goal, units=plan.units)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
