from __future__ import annotations

from pathlib import Path

import pytest

from research_harness.application import (
    AcceptAll,
    AcceptancePolicy,
    ApproveCheckpoint,
    BeginAttempt,
    CompleteAttempt,
    CreateRun,
    FailAttempt,
    Harness,
    InMemoryAcceptance,
    InMemoryArtifacts,
    InMemoryRunLedger,
    ReconcileRun,
    ResultOutcome,
    plan_from_workflow,
)
from research_harness.domain import (
    AttemptStatus,
    CompletionPhase,
    ErrorCode,
    Goal,
    HarnessError,
    HarnessRevision,
    ManifestStatus,
    Owner,
    RunPlan,
    RunStatus,
    UnitPlan,
    UnitStatus,
)
from research_harness.workflows import load_workflow_definition


REPO_ROOT = Path(__file__).resolve().parents[2]


def _revision(suffix: str = "v2") -> HarnessRevision:
    return HarnessRevision(
        pipeline_digest=f"pipeline-{suffix}",
        kernel_digest=f"kernel-{suffix}",
    )


def _single_unit_plan() -> RunPlan:
    return RunPlan(
        goal=Goal(
            id="goal_review",
            request="Review the paper",
            workflow="paper-review",
            target_artifacts=("output/review.md",),
            success_criteria=("review is traceable",),
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Draft review",
                skill="paper-review-writer",
                outputs=("output/review.md", "?output/notes.json"),
            ),
        ),
    )


def _decisions(checkpoint: str, *, checked: bool, body: str = "review basis") -> str:
    mark = "x" if checked else " "
    return (
        f"- [{mark}] Approve {checkpoint}\n"
        f"<!-- BEGIN CHECKPOINT:{checkpoint} -->\n"
        f"{body}\n"
        f"<!-- END CHECKPOINT:{checkpoint} -->\n"
    )


def _target_handoff_plan() -> RunPlan:
    return RunPlan(
        goal=Goal(
            id="goal_targets",
            request="Deliver current targets",
            workflow="target-handoff",
            target_artifacts=("target.md", "final.md"),
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Produce target",
                skill="producer",
                outputs=("target.md",),
            ),
            UnitPlan(
                id="U020",
                title="Finalize",
                skill="finalizer",
                depends_on=("U010",),
                outputs=("final.md",),
            ),
        ),
    )


def _required_checker_plan() -> RunPlan:
    return RunPlan(
        goal=Goal(
            id="goal_checker_freshness",
            request="Check then deliver",
            workflow="checker-freshness",
            target_artifacts=("report.md",),
            required_checks=("required-checker",),
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Produce checker input",
                skill="producer",
                outputs=("source.md",),
            ),
            UnitPlan(
                id="U020",
                title="Check source",
                skill="required-checker",
                depends_on=("U010",),
                inputs=("source.md",),
                outputs=("check.md", "?optional-check.md"),
            ),
            UnitPlan(
                id="U030",
                title="Deliver",
                skill="writer",
                depends_on=("U020",),
                outputs=("report.md",),
            ),
        ),
    )


def _in_place_lineage_plan(*, writer_declares_input: bool = True) -> RunPlan:
    polish_skill = "mandatory-polish" if writer_declares_input else "untracked-writer"
    required_checks = (
        ("mandatory-merge", "mandatory-polish", "mandatory-audit")
        if writer_declares_input
        else ("mandatory-merge", "mandatory-audit")
    )
    return RunPlan(
        goal=Goal(
            id="goal_lineage",
            request="Advance a checked draft",
            workflow="lineage",
            target_artifacts=("audit.md",),
            required_checks=required_checks,
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Merge draft",
                skill="mandatory-merge",
                outputs=("DRAFT.md",),
            ),
            UnitPlan(
                id="U020",
                title="Polish draft",
                skill=polish_skill,
                depends_on=("U010",),
                inputs=("DRAFT.md",) if writer_declares_input else (),
                outputs=("DRAFT.md",),
            ),
            UnitPlan(
                id="U030",
                title="Audit current draft",
                skill="mandatory-audit",
                depends_on=("U020",),
                inputs=("DRAFT.md",),
                outputs=("audit.md",),
            ),
        ),
    )


def _laundering_lineage_plan() -> RunPlan:
    return RunPlan(
        goal=Goal(
            id="goal_laundering",
            request="Reject undeclared intermediate writers",
            workflow="lineage",
            target_artifacts=("audit.md",),
            required_checks=("mandatory-merge", "mandatory-audit"),
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Merge draft",
                skill="mandatory-merge",
                outputs=("DRAFT.md",),
            ),
            UnitPlan(
                id="U020",
                title="Undeclared overwrite",
                skill="bad-writer",
                depends_on=("U010",),
                outputs=("DRAFT.md",),
            ),
            UnitPlan(
                id="U030",
                title="Declared later rewrite",
                skill="good-writer",
                depends_on=("U020",),
                inputs=("DRAFT.md",),
                outputs=("DRAFT.md",),
            ),
            UnitPlan(
                id="U040",
                title="Audit",
                skill="mandatory-audit",
                depends_on=("U030",),
                inputs=("DRAFT.md",),
                outputs=("audit.md",),
            ),
        ),
    )


def _directory_lineage_plan(*, manifest_declares_input: bool) -> RunPlan:
    return RunPlan(
        goal=Goal(
            id="goal_directory_lineage",
            request="Advance a checked directory projection",
            workflow="directory-lineage",
            target_artifacts=("audit.md",),
            required_checks=("directory-checker", "directory-audit"),
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Check directory",
                skill="directory-checker",
                inputs=("sections/",),
                outputs=("check.md",),
            ),
            UnitPlan(
                id="U020",
                title="Write directory manifest",
                skill="manifest-writer",
                depends_on=("U010",),
                inputs=("sections/",) if manifest_declares_input else (),
                outputs=("sections/sections_manifest.jsonl",),
            ),
            UnitPlan(
                id="U030",
                title="Audit directory",
                skill="directory-audit",
                depends_on=("U020",),
                inputs=("sections/",),
                outputs=("audit.md",),
            ),
        ),
    )


def _manifest_refresh_plan(*, refresher_declares_parent_input: bool) -> RunPlan:
    manifest_path = "sections/sections_manifest.jsonl"
    return RunPlan(
        goal=Goal(
            id="goal_manifest_refresh",
            request="Refresh a checked manifest",
            workflow="manifest-refresh",
            target_artifacts=("audit.md",),
            required_checks=("manifest-checker", "manifest-audit"),
        ),
        units=(
            UnitPlan(
                id="U100",
                title="Check manifest",
                skill="manifest-checker",
                outputs=(manifest_path,),
            ),
            UnitPlan(
                id="U1025",
                title="Refresh manifest from directory",
                skill="manifest-refresher",
                depends_on=("U100",),
                inputs=("sections/",) if refresher_declares_parent_input else (),
                outputs=(manifest_path,),
            ),
            UnitPlan(
                id="U110",
                title="Audit refreshed manifest",
                skill="manifest-audit",
                depends_on=("U1025",),
                inputs=(manifest_path,),
                outputs=("audit.md",),
            ),
        ),
    )


def _complete_required_checker_prefix(
    harness: Harness,
    artifacts: InMemoryArtifacts,
    *,
    run_id: str,
) -> None:
    harness.execute(CreateRun(run_id=run_id, plan=_required_checker_plan()))
    producer = harness.execute(BeginAttempt(run_id=run_id, unit_id="U010"))
    artifacts.put(run_id, "source.md", "source-v1")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=producer.attempt_id))
    checker = harness.execute(BeginAttempt(run_id=run_id, unit_id="U020"))
    artifacts.put(run_id, "check.md", "check-v1")
    artifacts.put(run_id, "optional-check.md", "optional-v1")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=checker.attempt_id))


def _harness(
    *,
    revision: HarnessRevision | None = None,
    ledger: InMemoryRunLedger | None = None,
    artifacts: InMemoryArtifacts | None = None,
    acceptance: AcceptancePolicy | None = None,
) -> tuple[Harness, InMemoryRunLedger, InMemoryArtifacts, AcceptancePolicy]:
    ledger = ledger or InMemoryRunLedger()
    artifacts = artifacts or InMemoryArtifacts()
    acceptance = acceptance or InMemoryAcceptance()
    harness = Harness(
        ledger=ledger,
        artifacts=artifacts,
        acceptance=acceptance,
        revision=revision or _revision(),
    )
    return harness, ledger, artifacts, acceptance


class _FailOnceLedger(InMemoryRunLedger):
    def __init__(self) -> None:
        super().__init__()
        self.fail_next_save = False

    def save(self, run, *, expected_version: int) -> None:  # type: ignore[no-untyped-def]
        if self.fail_next_save:
            self.fail_next_save = False
            raise OSError("injected ledger failure")
        super().save(run, expected_version=expected_version)


def test_two_entry_point_interface_commits_provenance_in_order() -> None:
    harness, _, artifacts, _ = _harness()
    created = harness.execute(CreateRun(run_id="run_review", plan=_single_unit_plan()))
    assert created.outcome is ResultOutcome.CREATED

    started = harness.execute(BeginAttempt(run_id="run_review", unit_id="U010"))
    artifacts.put("run_review", "output/review.md", "evidence-backed review")
    committed = harness.execute(
        CompleteAttempt(run_id="run_review", attempt_id=started.attempt_id)
    )

    assert committed.outcome is ResultOutcome.COMMITTED
    inspected = harness.inspect("run_review")
    assert inspected.status is RunStatus.COMPLETED
    assert inspected.unit("U010").status is UnitStatus.DONE
    assert inspected.attempts[0].status is AttemptStatus.SUCCEEDED
    assert inspected.completions[0].phase is CompletionPhase.COMMITTED

    event_kinds = [event.kind for event in inspected.events]
    assert (
        event_kinds.index("unit.completion.prepared")
        < event_kinds.index("unit.attempt.succeeded")
        < event_kinds.index("unit.completion.committed")
    )
    manifest = artifacts.read_manifest(inspected.completions[0].manifest_id)
    assert manifest is not None
    assert manifest.status is ManifestStatus.DONE
    assert manifest.artifacts[0].path == "output/review.md"


def test_retry_preserves_failed_attempt_and_creates_new_identity() -> None:
    harness, _, artifacts, _ = _harness()
    harness.execute(CreateRun(run_id="run_retry", plan=_single_unit_plan()))
    first = harness.execute(BeginAttempt(run_id="run_retry", unit_id="U010"))
    blocked = harness.execute(
        FailAttempt(
            run_id="run_retry", attempt_id=first.attempt_id, reason="source unavailable"
        )
    )
    assert blocked.outcome is ResultOutcome.BLOCKED

    second = harness.execute(BeginAttempt(run_id="run_retry", unit_id="U010"))
    assert second.attempt_id != first.attempt_id
    artifacts.put("run_retry", "output/review.md", "recovered")
    harness.execute(CompleteAttempt(run_id="run_retry", attempt_id=second.attempt_id))

    attempts = harness.inspect("run_retry").attempts
    assert [attempt.status for attempt in attempts] == [
        AttemptStatus.FAILED_RETRYABLE,
        AttemptStatus.SUCCEEDED,
    ]
    assert attempts[0].message == "source unavailable"


def test_dependencies_fail_closed_without_creating_attempt_evidence() -> None:
    plan = RunPlan(
        goal=Goal(id="goal_dag", request="Build", workflow="paper-review"),
        units=(
            UnitPlan(id="U010", title="Collect", skill="collector", outputs=("a.md",)),
            UnitPlan(
                id="U020",
                title="Write",
                skill="writer",
                depends_on=("U010",),
                outputs=("b.md",),
            ),
        ),
    )
    harness, _, _, _ = _harness()
    harness.execute(CreateRun(run_id="run_dag", plan=plan))

    with pytest.raises(HarnessError) as caught:
        harness.execute(BeginAttempt(run_id="run_dag", unit_id="U020"))

    assert caught.value.code is ErrorCode.DEPENDENCIES_NOT_READY
    inspected = harness.inspect("run_dag")
    assert inspected.attempts == ()
    assert inspected.unit("U020").status is UnitStatus.TODO


def test_skipped_dependency_is_not_ready_and_cannot_complete_the_run() -> None:
    harness, ledger, _, _ = _harness()
    harness.execute(
        CreateRun(
            run_id="run_skip",
            plan=RunPlan(
                goal=Goal(id="goal_skip", request="Build", workflow="paper-review"),
                units=(
                    UnitPlan(id="U010", title="Collect", skill="collector"),
                    UnitPlan(
                        id="U020",
                        title="Write",
                        skill="writer",
                        depends_on=("U010",),
                    ),
                ),
            ),
        )
    )
    aggregate = ledger.load("run_skip")
    assert aggregate is not None
    aggregate.unit_status["U010"] = UnitStatus.SKIPPED

    with pytest.raises(HarnessError) as caught:
        aggregate.begin_attempt(unit_id="U020", attempt_id="attempt_forbidden")

    assert caught.value.code is ErrorCode.DEPENDENCIES_NOT_READY
    assert aggregate.attempts == []
    assert aggregate.status is RunStatus.BLOCKED


@pytest.mark.parametrize(
    "unsafe_path",
    (
        ".",
        "output/./report.md",
        "C:\\escape.txt",
        "output;escape.md",
        "output/../escape.md",
        "output/control\n.md",
    ),
)
def test_domain_rejects_nonportable_artifact_paths(unsafe_path: str) -> None:
    plan = RunPlan(
        goal=Goal(
            id="goal_path",
            request="Build",
            workflow="paper-review",
            target_artifacts=(unsafe_path,),
        ),
        units=(UnitPlan(id="U010", title="Write", skill="writer"),),
    )
    harness, _, _, _ = _harness()

    with pytest.raises(HarnessError) as caught:
        harness.execute(CreateRun(run_id=f"run_path_{len(unsafe_path)}", plan=plan))

    assert caught.value.code is ErrorCode.INVALID_COMMAND
    assert "unsafe target Artifact path" in caught.value.message


def test_domain_allows_input_directories_but_rejects_output_directories() -> None:
    harness, _, _, _ = _harness()
    valid = RunPlan(
        goal=Goal(id="goal_input_dir", request="Build", workflow="paper-review"),
        units=(
            UnitPlan(
                id="U010",
                title="Read directory",
                skill="reader",
                inputs=("sources/",),
                outputs=("report.md",),
            ),
        ),
    )
    assert (
        harness.execute(CreateRun(run_id="run_input_dir", plan=valid)).outcome
        is ResultOutcome.CREATED
    )

    invalid = RunPlan(
        goal=Goal(id="goal_output_dir", request="Build", workflow="paper-review"),
        units=(
            UnitPlan(
                id="U010",
                title="Write directory",
                skill="writer",
                outputs=("output/",),
            ),
        ),
    )
    with pytest.raises(HarnessError) as caught:
        harness.execute(CreateRun(run_id="run_output_dir", plan=invalid))
    assert caught.value.code is ErrorCode.INVALID_COMMAND


def test_checkpoint_approval_is_bound_to_reviewed_artifact_versions() -> None:
    plan = RunPlan(
        goal=Goal(
            id="goal_checkpoint", request="Review scope", workflow="research-brief"
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Prepare scope",
                skill="scope-writer",
                outputs=("scope.md",),
            ),
            UnitPlan(
                id="U020",
                title="Approve scope",
                skill="human-checkpoint",
                depends_on=("U010",),
                inputs=("scope.md", "DECISIONS.md"),
                outputs=("DECISIONS.md",),
                owner=Owner.HUMAN,
                checkpoint="C1",
            ),
        ),
    )
    harness, _, artifacts, _ = _harness()
    harness.execute(CreateRun(run_id="run_checkpoint", plan=plan))
    producer = harness.execute(BeginAttempt(run_id="run_checkpoint", unit_id="U010"))
    artifacts.put("run_checkpoint", "scope.md", "scope version 1")
    harness.execute(
        CompleteAttempt(run_id="run_checkpoint", attempt_id=producer.attempt_id)
    )

    artifacts.put("run_checkpoint", "DECISIONS.md", _decisions("C1", checked=True))
    harness.execute(ApproveCheckpoint(run_id="run_checkpoint", checkpoint="C1"))
    artifacts.put("run_checkpoint", "scope.md", "scope version 2")
    human = harness.execute(BeginAttempt(run_id="run_checkpoint", unit_id="U020"))
    result = harness.execute(
        CompleteAttempt(run_id="run_checkpoint", attempt_id=human.attempt_id)
    )

    assert result.outcome is ResultOutcome.BLOCKED
    assert "stale" in result.message
    inspected = harness.inspect("run_checkpoint")
    assert inspected.unit("U020").status is UnitStatus.BLOCKED
    assert inspected.attempts[-1].status is AttemptStatus.FAILED_RETRYABLE
    assert not inspected.checkpoint_approvals[-1].active
    assert "checkpoint.approval.revoked" in {event.kind for event in inspected.events}


def test_stale_completed_checkpoint_reopens_before_downstream_attempt() -> None:
    plan = RunPlan(
        goal=Goal(
            id="goal_reopen", request="Approve then deliver", workflow="research-brief"
        ),
        units=(
            UnitPlan(
                id="U010", title="Scope", skill="scope-writer", outputs=("scope.md",)
            ),
            UnitPlan(
                id="U020",
                title="Approve",
                skill="human-checkpoint",
                depends_on=("U010",),
                inputs=("scope.md", "DECISIONS.md"),
                outputs=("DECISIONS.md",),
                owner=Owner.HUMAN,
                checkpoint="C1",
            ),
            UnitPlan(
                id="U030",
                title="Deliver branch A",
                skill="brief-writer-a",
                depends_on=("U020",),
                outputs=("brief-a.md",),
            ),
            UnitPlan(
                id="U040",
                title="Deliver branch B",
                skill="brief-writer-b",
                depends_on=("U020",),
                outputs=("brief-b.md",),
            ),
            UnitPlan(
                id="U035",
                title="Publish branch A",
                skill="publisher-a",
                depends_on=("U030",),
                outputs=("final-a.md",),
            ),
        ),
    )
    harness, _, artifacts, _ = _harness()
    harness.execute(CreateRun(run_id="run_reopen", plan=plan))
    producer = harness.execute(BeginAttempt(run_id="run_reopen", unit_id="U010"))
    artifacts.put("run_reopen", "scope.md", "version 1")
    harness.execute(
        CompleteAttempt(run_id="run_reopen", attempt_id=producer.attempt_id)
    )
    artifacts.put("run_reopen", "DECISIONS.md", _decisions("C1", checked=True))
    harness.execute(ApproveCheckpoint(run_id="run_reopen", checkpoint="C1"))
    checkpoint = harness.execute(BeginAttempt(run_id="run_reopen", unit_id="U020"))
    harness.execute(
        CompleteAttempt(run_id="run_reopen", attempt_id=checkpoint.attempt_id)
    )
    branch_a = harness.execute(BeginAttempt(run_id="run_reopen", unit_id="U030"))
    artifacts.put("run_reopen", "brief-a.md", "stale branch")
    harness.execute(
        CompleteAttempt(run_id="run_reopen", attempt_id=branch_a.attempt_id)
    )
    published_a = harness.execute(BeginAttempt(run_id="run_reopen", unit_id="U035"))
    artifacts.put("run_reopen", "final-a.md", "stale publication")
    harness.execute(
        CompleteAttempt(run_id="run_reopen", attempt_id=published_a.attempt_id)
    )

    artifacts.put("run_reopen", "scope.md", "version 2")
    blocked = harness.execute(BeginAttempt(run_id="run_reopen", unit_id="U040"))

    assert blocked.outcome is ResultOutcome.BLOCKED
    assert blocked.attempt_id == ""
    assert "stale" in blocked.message
    inspected = harness.inspect("run_reopen")
    assert inspected.unit("U020").status is UnitStatus.BLOCKED
    assert inspected.unit("U030").status is UnitStatus.TODO
    assert inspected.unit("U035").status is UnitStatus.TODO
    assert inspected.unit("U040").status is UnitStatus.TODO
    assert len(inspected.attempts) == 4
    assert {
        completion.unit_id
        for completion in inspected.completions
        if completion.phase is CompletionPhase.COMMITTED
    } >= {"U030", "U035"}
    assert "checkpoint.reopened" in {event.kind for event in inspected.events}
    assert "unit.invalidated" in {event.kind for event in inspected.events}


def test_prepared_completion_recovers_after_manifest_finalize_failure() -> None:
    harness, _, artifacts, _ = _harness()
    harness.execute(CreateRun(run_id="run_recovery", plan=_single_unit_plan()))
    started = harness.execute(BeginAttempt(run_id="run_recovery", unit_id="U010"))
    artifacts.put("run_recovery", "output/review.md", "durable output")
    artifacts.fail_next_finalize()

    with pytest.raises(HarnessError) as caught:
        harness.execute(
            CompleteAttempt(run_id="run_recovery", attempt_id=started.attempt_id)
        )
    assert caught.value.code is ErrorCode.ADAPTER_FAILURE

    interrupted = harness.inspect("run_recovery")
    assert interrupted.status is RunStatus.RUNNING
    assert interrupted.unit("U010").status is UnitStatus.DOING
    assert interrupted.attempts[0].status is AttemptStatus.SUCCEEDED
    assert interrupted.completions[0].phase is CompletionPhase.PREPARED

    recovered = harness.execute(ReconcileRun(run_id="run_recovery"))
    assert recovered.outcome is ResultOutcome.RECONCILED
    assert recovered.run.unit("U010").status is UnitStatus.DONE
    assert recovered.run.completions[0].phase is CompletionPhase.COMMITTED


def test_orphan_prepared_manifest_recovers_after_first_ledger_save_failure() -> None:
    ledger = _FailOnceLedger()
    harness, _, artifacts, _ = _harness(ledger=ledger)
    harness.execute(CreateRun(run_id="run_orphan", plan=_single_unit_plan()))
    started = harness.execute(BeginAttempt(run_id="run_orphan", unit_id="U010"))
    artifacts.put("run_orphan", "output/review.md", "durable output")
    ledger.fail_next_save = True

    with pytest.raises(HarnessError) as caught:
        harness.execute(
            CompleteAttempt(run_id="run_orphan", attempt_id=started.attempt_id)
        )
    assert caught.value.code is ErrorCode.ADAPTER_FAILURE
    interrupted = harness.inspect("run_orphan")
    assert interrupted.completions == ()
    assert interrupted.attempts[0].status is AttemptStatus.RUNNING
    manifests = artifacts.list_manifests("run_orphan")
    assert len(manifests) == 1
    assert manifests[0].status is ManifestStatus.PREPARED

    with pytest.raises(HarnessError) as gated:
        harness.execute(
            CompleteAttempt(run_id="run_orphan", attempt_id=started.attempt_id)
        )
    assert gated.value.code is ErrorCode.RECOVERY_REQUIRED

    recovered = harness.execute(ReconcileRun(run_id="run_orphan"))
    assert recovered.outcome is ResultOutcome.RECONCILED
    assert recovered.run.unit("U010").status is UnitStatus.DONE
    assert recovered.run.completions[0].phase is CompletionPhase.COMMITTED
    assert artifacts.list_manifests("run_orphan")[0].status is ManifestStatus.DONE


def test_reconcile_rejection_retries_when_blocking_manifest_write_fails() -> None:
    ledger = _FailOnceLedger()
    harness, _, artifacts, _ = _harness(ledger=ledger)
    harness.execute(CreateRun(run_id="run_reject_recovery", plan=_single_unit_plan()))
    started = harness.execute(
        BeginAttempt(run_id="run_reject_recovery", unit_id="U010")
    )
    artifacts.put("run_reject_recovery", "output/review.md", "version 1")
    artifacts.fail_next_finalize()
    with pytest.raises(HarnessError):
        harness.execute(
            CompleteAttempt(
                run_id="run_reject_recovery",
                attempt_id=started.attempt_id,
            )
        )

    artifacts.put("run_reject_recovery", "output/review.md", "version 2")
    artifacts.fail_next_status(ManifestStatus.BLOCKED)
    with pytest.raises(HarnessError) as caught:
        harness.execute(ReconcileRun(run_id="run_reject_recovery"))
    assert caught.value.code is ErrorCode.ADAPTER_FAILURE
    still_prepared = harness.inspect("run_reject_recovery")
    assert still_prepared.completions[0].phase is CompletionPhase.PREPARED
    assert (
        artifacts.list_manifests("run_reject_recovery")[0].status
        is ManifestStatus.PREPARED
    )

    ledger.fail_next_save = True
    with pytest.raises(HarnessError) as ledger_failure:
        harness.execute(ReconcileRun(run_id="run_reject_recovery"))
    assert ledger_failure.value.code is ErrorCode.ADAPTER_FAILURE
    still_prepared = harness.inspect("run_reject_recovery")
    assert still_prepared.completions[0].phase is CompletionPhase.PREPARED
    assert (
        artifacts.list_manifests("run_reject_recovery")[0].status
        is ManifestStatus.BLOCKED
    )

    blocked = harness.execute(ReconcileRun(run_id="run_reject_recovery"))
    assert blocked.outcome is ResultOutcome.BLOCKED
    assert blocked.run.completions[0].phase is CompletionPhase.ABORTED
    assert blocked.run.unit("U010").status is UnitStatus.BLOCKED
    assert (
        artifacts.list_manifests("run_reject_recovery")[0].status
        is ManifestStatus.BLOCKED
    )


def test_final_completion_captures_latest_targets_in_stable_order() -> None:
    harness, _, artifacts, _ = _harness()
    harness.execute(CreateRun(run_id="run_targets", plan=_target_handoff_plan()))
    producer = harness.execute(BeginAttempt(run_id="run_targets", unit_id="U010"))
    artifacts.put("run_targets", "target.md", "target-v1")
    harness.execute(
        CompleteAttempt(run_id="run_targets", attempt_id=producer.attempt_id)
    )

    artifacts.put("run_targets", "target.md", "target-v2")
    finalizer = harness.execute(BeginAttempt(run_id="run_targets", unit_id="U020"))
    artifacts.put("run_targets", "final.md", "final")
    completed = harness.execute(
        CompleteAttempt(run_id="run_targets", attempt_id=finalizer.attempt_id)
    )

    latest_target = artifacts.snapshot("run_targets", ("target.md",))[0]
    completion = completed.run.completions[-1]
    assert tuple(item.path for item in completion.artifacts) == (
        "final.md",
        "target.md",
    )
    assert (
        next(item for item in completion.artifacts if item.path == "target.md")
        == latest_target
    )
    manifest = artifacts.read_manifest(completion.manifest_id)
    assert manifest is not None
    assert manifest.artifacts == completion.artifacts


def test_reconcile_rejects_a_final_completion_when_target_evidence_changes() -> None:
    harness, _, artifacts, _ = _harness()
    harness.execute(
        CreateRun(run_id="run_target_recovery", plan=_target_handoff_plan())
    )
    producer = harness.execute(
        BeginAttempt(run_id="run_target_recovery", unit_id="U010")
    )
    artifacts.put("run_target_recovery", "target.md", "target-v1")
    harness.execute(
        CompleteAttempt(run_id="run_target_recovery", attempt_id=producer.attempt_id)
    )
    finalizer = harness.execute(
        BeginAttempt(run_id="run_target_recovery", unit_id="U020")
    )
    artifacts.put("run_target_recovery", "target.md", "target-v2")
    artifacts.put("run_target_recovery", "final.md", "final")
    artifacts.fail_next_finalize()
    with pytest.raises(HarnessError):
        harness.execute(
            CompleteAttempt(
                run_id="run_target_recovery",
                attempt_id=finalizer.attempt_id,
            )
        )

    prepared = harness.inspect("run_target_recovery").completions[-1]
    assert {item.path for item in prepared.artifacts} == {"target.md", "final.md"}
    artifacts.put("run_target_recovery", "target.md", "target-v3")
    blocked = harness.execute(ReconcileRun(run_id="run_target_recovery"))
    assert blocked.outcome is ResultOutcome.BLOCKED
    assert "fingerprints changed" in blocked.message
    assert blocked.run.completions[-1].phase is CompletionPhase.ABORTED


def test_human_unit_requires_checkpoint_and_approval_requires_review_evidence() -> None:
    harness, _, _, _ = _harness()
    missing_checkpoint = RunPlan(
        goal=Goal(id="goal_human", request="Approve", workflow="research-brief"),
        units=(
            UnitPlan(
                id="U010",
                title="Approve",
                skill="human-checkpoint",
                owner=Owner.HUMAN,
                checkpoint="   ",
                inputs=("DECISIONS.md",),
                outputs=("DECISIONS.md",),
            ),
        ),
    )
    with pytest.raises(HarnessError) as invalid:
        harness.execute(CreateRun(run_id="run_human", plan=missing_checkpoint))
    assert invalid.value.code is ErrorCode.INVALID_COMMAND

    empty_basis = RunPlan(
        goal=Goal(id="goal_empty", request="Approve", workflow="research-brief"),
        units=(
            UnitPlan(
                id="U010",
                title="Approve",
                skill="human-checkpoint",
                owner=Owner.HUMAN,
                checkpoint="C1",
                inputs=("DECISIONS.md",),
                outputs=("DECISIONS.md",),
            ),
        ),
    )
    harness.execute(CreateRun(run_id="run_empty_basis", plan=empty_basis))
    with pytest.raises(HarnessError) as unbound:
        harness.execute(ApproveCheckpoint(run_id="run_empty_basis", checkpoint="C1"))
    assert unbound.value.code is ErrorCode.INVALID_TRANSITION
    assert harness.inspect("run_empty_basis").checkpoint_approvals == ()


def test_checkpoint_decision_basis_ignores_checkbox_and_unrelated_blocks() -> None:
    plan = RunPlan(
        goal=Goal(id="goal_decision", request="Approve", workflow="research-brief"),
        units=(
            UnitPlan(
                id="U010",
                title="Prepare scope",
                skill="scope-writer",
                outputs=("scope.md",),
            ),
            UnitPlan(
                id="U020",
                title="Approve scope",
                skill="human-checkpoint",
                depends_on=("U010",),
                inputs=("scope.md", "DECISIONS.md"),
                outputs=("DECISIONS.md",),
                owner=Owner.HUMAN,
                checkpoint="C1",
            ),
        ),
    )
    harness, _, artifacts, _ = _harness()
    harness.execute(CreateRun(run_id="run_decision", plan=plan))
    producer = harness.execute(BeginAttempt(run_id="run_decision", unit_id="U010"))
    artifacts.put("run_decision", "scope.md", "scope")
    artifacts.put(
        "run_decision",
        "DECISIONS.md",
        _decisions("C1", checked=False, body="review scope"),
    )
    harness.execute(
        CompleteAttempt(run_id="run_decision", attempt_id=producer.attempt_id)
    )
    with pytest.raises(HarnessError) as unchecked:
        harness.execute(ApproveCheckpoint(run_id="run_decision", checkpoint="C1"))
    assert unchecked.value.code is ErrorCode.INVALID_TRANSITION
    assert "not explicitly checked/approved" in unchecked.value.message

    artifacts.put(
        "run_decision",
        "DECISIONS.md",
        _decisions("C1", checked=True, body="review scope"),
    )
    approved = harness.execute(
        ApproveCheckpoint(run_id="run_decision", checkpoint="C1")
    )
    basis = approved.run.checkpoint_approvals[-1].review_basis
    assert basis.schema == "checkpoint-review-basis.v1"
    assert basis.approved
    assert any(
        item.normalization == "checkpoint-block-and-approval-checkbox-insensitive.v1"
        for item in basis.artifacts
    )

    artifacts.put(
        "run_decision",
        "DECISIONS.md",
        _decisions("C1", checked=True, body="review scope")
        + "\n"
        + _decisions("C2", checked=True, body="unrelated"),
    )
    human = harness.execute(BeginAttempt(run_id="run_decision", unit_id="U020"))
    completed = harness.execute(
        CompleteAttempt(run_id="run_decision", attempt_id=human.attempt_id)
    )
    assert completed.outcome is ResultOutcome.COMMITTED


def test_human_completion_blocks_when_the_recorded_decision_is_unchecked() -> None:
    plan = RunPlan(
        goal=Goal(id="goal_unchecked", request="Approve", workflow="research-brief"),
        units=(
            UnitPlan(
                id="U010",
                title="Prepare",
                skill="preparer",
                outputs=("scope.md",),
            ),
            UnitPlan(
                id="U020",
                title="Approve",
                skill="human-checkpoint",
                depends_on=("U010",),
                inputs=("scope.md", "DECISIONS.md"),
                outputs=("DECISIONS.md",),
                owner=Owner.HUMAN,
                checkpoint="C1",
            ),
        ),
    )
    harness, _, artifacts, _ = _harness()
    harness.execute(CreateRun(run_id="run_unchecked", plan=plan))
    prepared = harness.execute(BeginAttempt(run_id="run_unchecked", unit_id="U010"))
    artifacts.put("run_unchecked", "scope.md", "scope")
    artifacts.put("run_unchecked", "DECISIONS.md", _decisions("C1", checked=True))
    harness.execute(
        CompleteAttempt(run_id="run_unchecked", attempt_id=prepared.attempt_id)
    )
    harness.execute(ApproveCheckpoint(run_id="run_unchecked", checkpoint="C1"))
    human = harness.execute(BeginAttempt(run_id="run_unchecked", unit_id="U020"))

    artifacts.put("run_unchecked", "DECISIONS.md", _decisions("C1", checked=False))
    blocked = harness.execute(
        CompleteAttempt(run_id="run_unchecked", attempt_id=human.attempt_id)
    )
    assert blocked.outcome is ResultOutcome.BLOCKED
    assert "no longer explicitly checked/approved" in blocked.message
    assert not blocked.run.checkpoint_approvals[-1].active


def test_accept_all_fails_closed_for_a_mandatory_check_skill() -> None:
    plan = RunPlan(
        goal=Goal(
            id="goal_mandatory",
            request="Audit",
            workflow="audit",
            target_artifacts=("report.md",),
            required_checks=("contract-auditor",),
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Audit",
                skill="contract-auditor",
                outputs=("report.md",),
            ),
        ),
    )
    harness, _, artifacts, _ = _harness(acceptance=AcceptAll())
    harness.execute(CreateRun(run_id="run_accept_all", plan=plan))
    attempt = harness.execute(BeginAttempt(run_id="run_accept_all", unit_id="U010"))
    artifacts.put("run_accept_all", "report.md", "PASS")
    blocked = harness.execute(
        CompleteAttempt(run_id="run_accept_all", attempt_id=attempt.attempt_id)
    )

    assert blocked.outcome is ResultOutcome.BLOCKED
    assert "did not explicitly attest" in blocked.message
    assert artifacts.list_manifests("run_accept_all") == ()


def test_final_completion_blocks_when_required_checker_coverage_is_missing() -> None:
    plan = RunPlan(
        goal=Goal(
            id="goal_missing_check",
            request="Deliver",
            workflow="audit",
            target_artifacts=("report.md",),
            required_checks=("checker-a", "checker-b"),
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Check A",
                skill="checker-a",
                outputs=("check-a.md",),
            ),
            UnitPlan(
                id="U020",
                title="Deliver",
                skill="writer",
                depends_on=("U010",),
                outputs=("report.md",),
            ),
        ),
    )
    harness, _, artifacts, _ = _harness()
    harness.execute(CreateRun(run_id="run_missing_check", plan=plan))
    check = harness.execute(BeginAttempt(run_id="run_missing_check", unit_id="U010"))
    artifacts.put("run_missing_check", "check-a.md", "PASS")
    harness.execute(
        CompleteAttempt(run_id="run_missing_check", attempt_id=check.attempt_id)
    )
    final = harness.execute(BeginAttempt(run_id="run_missing_check", unit_id="U020"))
    artifacts.put("run_missing_check", "report.md", "report")
    blocked = harness.execute(
        CompleteAttempt(run_id="run_missing_check", attempt_id=final.attempt_id)
    )

    assert blocked.outcome is ResultOutcome.BLOCKED
    assert "checker-b" in blocked.message
    assert "committed/current coverage" in blocked.message


def test_final_completion_commits_when_all_required_checks_are_covered() -> None:
    plan = RunPlan(
        goal=Goal(
            id="goal_covered",
            request="Deliver",
            workflow="audit",
            target_artifacts=("report.md",),
            required_checks=("checker-a", "checker-b"),
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Check A",
                skill="checker-a",
                outputs=("check-a.md",),
            ),
            UnitPlan(
                id="U020",
                title="Check B and deliver",
                skill="checker-b",
                depends_on=("U010",),
                outputs=("report.md",),
            ),
        ),
    )
    harness, _, artifacts, _ = _harness()
    harness.execute(CreateRun(run_id="run_covered", plan=plan))
    first = harness.execute(BeginAttempt(run_id="run_covered", unit_id="U010"))
    artifacts.put("run_covered", "check-a.md", "PASS")
    harness.execute(CompleteAttempt(run_id="run_covered", attempt_id=first.attempt_id))
    final = harness.execute(BeginAttempt(run_id="run_covered", unit_id="U020"))
    artifacts.put("run_covered", "report.md", "PASS")
    committed = harness.execute(
        CompleteAttempt(run_id="run_covered", attempt_id=final.attempt_id)
    )

    assert committed.outcome is ResultOutcome.COMMITTED
    assert committed.run.status is RunStatus.COMPLETED
    covered = {
        check
        for completion in committed.run.completions
        for check in completion.acceptance.checks
    }
    assert covered >= {"checker-a", "checker-b"}


@pytest.mark.parametrize("changed_path", ("source.md", "check.md"))
def test_final_completion_blocks_when_required_checker_evidence_changes(
    changed_path: str,
) -> None:
    harness, _, artifacts, _ = _harness()
    run_id = f"run_checker_stale_{changed_path.replace('.', '_')}"
    _complete_required_checker_prefix(harness, artifacts, run_id=run_id)
    checker_completion = harness.inspect(run_id).completions[-1]
    assert tuple(item.path for item in checker_completion.artifacts) == (
        "source.md",
        "check.md",
        "optional-check.md",
    )

    artifacts.put(run_id, changed_path, "changed-after-check")
    final = harness.execute(BeginAttempt(run_id=run_id, unit_id="U030"))
    artifacts.put(run_id, "report.md", "report")
    blocked = harness.execute(
        CompleteAttempt(run_id=run_id, attempt_id=final.attempt_id)
    )

    assert blocked.outcome is ResultOutcome.BLOCKED
    assert (
        "Required check required-checker is stale: bound Artifact evidence changed"
        in blocked.message
    )


def test_reconcile_aborts_when_prior_required_checker_evidence_changes() -> None:
    harness, _, artifacts, _ = _harness()
    run_id = "run_checker_reconcile"
    _complete_required_checker_prefix(harness, artifacts, run_id=run_id)
    final = harness.execute(BeginAttempt(run_id=run_id, unit_id="U030"))
    artifacts.put(run_id, "report.md", "report")
    artifacts.fail_next_finalize()
    with pytest.raises(HarnessError):
        harness.execute(CompleteAttempt(run_id=run_id, attempt_id=final.attempt_id))

    artifacts.put(run_id, "check.md", "changed-after-prepare")
    blocked = harness.execute(ReconcileRun(run_id=run_id))
    assert blocked.outcome is ResultOutcome.BLOCKED
    assert "Required check required-checker is stale" in blocked.message
    assert blocked.run.completions[-1].phase is CompletionPhase.ABORTED


def test_unchanged_required_checker_evidence_allows_final_completion() -> None:
    harness, _, artifacts, _ = _harness()
    run_id = "run_checker_fresh"
    _complete_required_checker_prefix(harness, artifacts, run_id=run_id)
    final = harness.execute(BeginAttempt(run_id=run_id, unit_id="U030"))
    artifacts.put(run_id, "report.md", "report")
    committed = harness.execute(
        CompleteAttempt(run_id=run_id, attempt_id=final.attempt_id)
    )

    assert committed.outcome is ResultOutcome.COMMITTED
    assert committed.run.status is RunStatus.COMPLETED
    assert tuple(item.path for item in committed.run.completions[-1].artifacts) == (
        "report.md",
    )


def test_declared_in_place_lineage_supersedes_earlier_checker_evidence() -> None:
    harness, _, artifacts, _ = _harness()
    run_id = "run_declared_lineage"
    harness.execute(CreateRun(run_id=run_id, plan=_in_place_lineage_plan()))
    merge = harness.execute(BeginAttempt(run_id=run_id, unit_id="U010"))
    artifacts.put(run_id, "DRAFT.md", "draft-v1")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=merge.attempt_id))

    polish = harness.execute(BeginAttempt(run_id=run_id, unit_id="U020"))
    artifacts.put(run_id, "DRAFT.md", "draft-v2")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=polish.attempt_id))

    audit = harness.execute(BeginAttempt(run_id=run_id, unit_id="U030"))
    artifacts.put(run_id, "audit.md", "PASS")
    committed = harness.execute(
        CompleteAttempt(run_id=run_id, attempt_id=audit.attempt_id)
    )

    assert committed.outcome is ResultOutcome.COMMITTED
    assert committed.run.status is RunStatus.COMPLETED
    assert [
        tuple(item.path for item in completion.artifacts)
        for completion in committed.run.completions
    ] == [("DRAFT.md",), ("DRAFT.md",), ("DRAFT.md", "audit.md")]


def test_later_writer_without_in_place_input_does_not_establish_lineage() -> None:
    harness, _, artifacts, _ = _harness()
    run_id = "run_undeclared_lineage"
    harness.execute(
        CreateRun(
            run_id=run_id,
            plan=_in_place_lineage_plan(writer_declares_input=False),
        )
    )
    merge = harness.execute(BeginAttempt(run_id=run_id, unit_id="U010"))
    artifacts.put(run_id, "DRAFT.md", "draft-v1")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=merge.attempt_id))
    writer = harness.execute(BeginAttempt(run_id=run_id, unit_id="U020"))
    artifacts.put(run_id, "DRAFT.md", "draft-v2")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=writer.attempt_id))
    audit = harness.execute(BeginAttempt(run_id=run_id, unit_id="U030"))
    artifacts.put(run_id, "audit.md", "PASS")
    blocked = harness.execute(
        CompleteAttempt(run_id=run_id, attempt_id=audit.attempt_id)
    )

    assert blocked.outcome is ResultOutcome.BLOCKED
    assert "without declared in-place lineage" in blocked.message
    assert "DRAFT.md" in blocked.message


def test_invalid_intermediate_writer_cannot_be_laundered_by_a_later_valid_hop() -> None:
    harness, _, artifacts, _ = _harness()
    run_id = "run_lineage_laundering"
    harness.execute(CreateRun(run_id=run_id, plan=_laundering_lineage_plan()))
    source = harness.execute(BeginAttempt(run_id=run_id, unit_id="U010"))
    artifacts.put(run_id, "DRAFT.md", "draft-v1")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=source.attempt_id))

    invalid = harness.execute(BeginAttempt(run_id=run_id, unit_id="U020"))
    artifacts.put(run_id, "DRAFT.md", "draft-v2-invalid")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=invalid.attempt_id))
    later_valid = harness.execute(BeginAttempt(run_id=run_id, unit_id="U030"))
    artifacts.put(run_id, "DRAFT.md", "draft-v3")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=later_valid.attempt_id))

    audit = harness.execute(BeginAttempt(run_id=run_id, unit_id="U040"))
    artifacts.put(run_id, "audit.md", "PASS")
    blocked = harness.execute(
        CompleteAttempt(run_id=run_id, attempt_id=audit.attempt_id)
    )
    assert blocked.outcome is ResultOutcome.BLOCKED
    assert "without declared in-place lineage" in blocked.message
    assert "DRAFT.md" in blocked.message


def test_directory_projection_completion_advances_declared_lineage() -> None:
    harness, _, artifacts, _ = _harness()
    run_id = "run_directory_lineage"
    harness.execute(
        CreateRun(
            run_id=run_id,
            plan=_directory_lineage_plan(manifest_declares_input=True),
        )
    )
    checker = harness.execute(BeginAttempt(run_id=run_id, unit_id="U010"))
    artifacts.put(run_id, "sections/", "directory-v1")
    artifacts.put(run_id, "check.md", "PASS")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=checker.attempt_id))

    manifest = harness.execute(BeginAttempt(run_id=run_id, unit_id="U020"))
    artifacts.put(run_id, "sections/sections_manifest.jsonl", '{"section": 1}')
    artifacts.put(run_id, "sections/", "directory-v2")
    manifest_result = harness.execute(
        CompleteAttempt(run_id=run_id, attempt_id=manifest.attempt_id)
    )
    assert tuple(
        item.path for item in manifest_result.run.completions[-1].artifacts
    ) == (
        "sections/sections_manifest.jsonl",
        "sections/",
    )

    audit = harness.execute(BeginAttempt(run_id=run_id, unit_id="U030"))
    artifacts.put(run_id, "audit.md", "PASS")
    committed = harness.execute(
        CompleteAttempt(run_id=run_id, attempt_id=audit.attempt_id)
    )
    assert committed.outcome is ResultOutcome.COMMITTED
    assert committed.run.status is RunStatus.COMPLETED


def test_directory_projection_without_declared_directory_input_is_stale() -> None:
    harness, _, artifacts, _ = _harness()
    run_id = "run_directory_untracked"
    harness.execute(
        CreateRun(
            run_id=run_id,
            plan=_directory_lineage_plan(manifest_declares_input=False),
        )
    )
    checker = harness.execute(BeginAttempt(run_id=run_id, unit_id="U010"))
    artifacts.put(run_id, "sections/", "directory-v1")
    artifacts.put(run_id, "check.md", "PASS")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=checker.attempt_id))
    manifest = harness.execute(BeginAttempt(run_id=run_id, unit_id="U020"))
    artifacts.put(run_id, "sections/sections_manifest.jsonl", '{"section": 1}')
    artifacts.put(run_id, "sections/", "directory-v2")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=manifest.attempt_id))

    audit = harness.execute(BeginAttempt(run_id=run_id, unit_id="U030"))
    artifacts.put(run_id, "audit.md", "PASS")
    blocked = harness.execute(
        CompleteAttempt(run_id=run_id, attempt_id=audit.attempt_id)
    )
    assert blocked.outcome is ResultOutcome.BLOCKED
    assert "without declared in-place lineage" in blocked.message
    assert "sections/" in blocked.message


def test_parent_directory_input_can_consume_and_refresh_a_tracked_file() -> None:
    harness, _, artifacts, _ = _harness()
    run_id = "run_manifest_refresh"
    harness.execute(
        CreateRun(
            run_id=run_id,
            plan=_manifest_refresh_plan(refresher_declares_parent_input=True),
        )
    )
    manifest_path = "sections/sections_manifest.jsonl"
    checker = harness.execute(BeginAttempt(run_id=run_id, unit_id="U100"))
    artifacts.put(run_id, manifest_path, "manifest-v1")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=checker.attempt_id))

    refresher = harness.execute(BeginAttempt(run_id=run_id, unit_id="U1025"))
    artifacts.put(run_id, "sections/", "directory-v2")
    artifacts.put(run_id, manifest_path, "manifest-v2")
    refreshed = harness.execute(
        CompleteAttempt(run_id=run_id, attempt_id=refresher.attempt_id)
    )
    assert tuple(item.path for item in refreshed.run.completions[-1].artifacts) == (
        manifest_path,
        "sections/",
    )

    audit = harness.execute(BeginAttempt(run_id=run_id, unit_id="U110"))
    artifacts.put(run_id, "audit.md", "PASS")
    committed = harness.execute(
        CompleteAttempt(run_id=run_id, attempt_id=audit.attempt_id)
    )
    assert committed.outcome is ResultOutcome.COMMITTED
    assert committed.run.status is RunStatus.COMPLETED


def test_file_refresh_without_exact_or_parent_directory_input_is_stale() -> None:
    harness, _, artifacts, _ = _harness()
    run_id = "run_manifest_refresh_untracked"
    harness.execute(
        CreateRun(
            run_id=run_id,
            plan=_manifest_refresh_plan(refresher_declares_parent_input=False),
        )
    )
    manifest_path = "sections/sections_manifest.jsonl"
    checker = harness.execute(BeginAttempt(run_id=run_id, unit_id="U100"))
    artifacts.put(run_id, manifest_path, "manifest-v1")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=checker.attempt_id))
    refresher = harness.execute(BeginAttempt(run_id=run_id, unit_id="U1025"))
    artifacts.put(run_id, manifest_path, "manifest-v2")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=refresher.attempt_id))

    audit = harness.execute(BeginAttempt(run_id=run_id, unit_id="U110"))
    artifacts.put(run_id, "audit.md", "PASS")
    blocked = harness.execute(
        CompleteAttempt(run_id=run_id, attempt_id=audit.attempt_id)
    )
    assert blocked.outcome is ResultOutcome.BLOCKED
    assert "without declared in-place lineage" in blocked.message
    assert manifest_path in blocked.message


def test_revision_drift_blocks_mutation_but_not_inspection() -> None:
    ledger = InMemoryRunLedger()
    artifacts = InMemoryArtifacts()
    original, _, _, _ = _harness(
        revision=_revision("original"), ledger=ledger, artifacts=artifacts
    )
    original.execute(CreateRun(run_id="run_pinned", plan=_single_unit_plan()))

    drifted, _, _, _ = _harness(
        revision=_revision("changed"), ledger=ledger, artifacts=artifacts
    )
    with pytest.raises(HarnessError) as caught:
        drifted.execute(BeginAttempt(run_id="run_pinned", unit_id="U010"))

    assert caught.value.code is ErrorCode.REVISION_DRIFT
    assert drifted.inspect("run_pinned").attempts == ()


def test_paper_review_workflow_maps_losslessly_into_a_runnable_plan() -> None:
    workflow = load_workflow_definition(
        REPO_ROOT / "pipelines" / "paper-review.pipeline.md",
        repo_root=REPO_ROOT,
    )
    plan = plan_from_workflow(
        workflow,
        goal_id="goal_paper_review",
        request="Review this manuscript",
    )

    assert plan.goal.workflow == workflow.name
    assert plan.goal.target_artifacts == workflow.target_artifacts
    assert plan.goal.required_checks == workflow.checks
    assert plan.goal.success_criteria == tuple(
        f"required-artifact:{path}" for path in workflow.target_artifacts
    ) + tuple(f"required-check:{skill}" for skill in workflow.checks)
    assert [
        (
            unit.id,
            unit.title,
            unit.workflow_type,
            unit.skill,
            unit.depends_on,
            unit.inputs,
            unit.outputs,
            unit.acceptance,
            unit.checkpoint,
            unit.owner.value,
        )
        for unit in plan.units
    ] == [
        (
            unit.id,
            unit.title,
            unit.type,
            unit.skill,
            unit.depends_on,
            unit.inputs,
            unit.outputs,
            unit.acceptance,
            unit.checkpoint,
            unit.owner,
        )
        for unit in workflow.units
    ]

    harness, _, _, _ = _harness()
    created = harness.execute(CreateRun(run_id="run_paper_review", plan=plan))
    assert created.outcome is ResultOutcome.CREATED
    assert tuple(unit.plan.id for unit in created.run.units) == tuple(
        unit.id for unit in workflow.units
    )
