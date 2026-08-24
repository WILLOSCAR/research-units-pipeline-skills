from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from research_harness.application import (
    InMemoryAcceptance,
    InMemoryArtifacts,
    InMemoryRunLedger,
)
from research_harness.domain import (
    AttemptStatus,
    Goal,
    HarnessRevision,
    Owner,
    RunPlan,
    RunStatus,
    UnitPlan,
    UnitStatus,
)
from research_harness.engine import (
    AdvanceRun,
    AdvanceUntil,
    ApproveLocalCheckpoint,
    CreateLocalRun,
    EngineError,
    EngineErrorCode,
    EngineOutcome,
    InspectionState,
    LocalRunEngine,
    RecoverLocalRun,
)
from research_harness.skills import (
    InMemorySkillAdapter,
    SkillAdapter,
    SkillContext,
    SkillProcessError,
    SkillResult,
)


class _SimulatedCrash(BaseException):
    pass


class _CrashAdapter:
    adapter = "fixture:crash"

    def run(self, context: SkillContext) -> SkillResult:
        del context
        raise _SimulatedCrash("simulated process loss")


class _SecretFailureAdapter:
    adapter = "fixture:secret-failure"

    def run(self, context: SkillContext) -> SkillResult:
        del context
        raise RuntimeError("DO-NOT-PERSIST-THIS-SECRET")


class _CrashOnWaitHandle:
    def __init__(self, delegate) -> None:  # type: ignore[no-untyped-def]
        self.delegate = delegate

    @property
    def owner(self):  # type: ignore[no-untyped-def]
        return self.delegate.owner

    def is_alive(self) -> bool:
        return self.delegate.is_alive()

    def release(self) -> None:
        self.delegate.release()

    def terminate(self) -> None:
        self.delegate.terminate()

    def wait(self) -> SkillResult:
        raise _SimulatedCrash("engine disappeared after recording process owner")


class _CrashAfterSubprocessStartAdapter:
    def __init__(self, delegate) -> None:  # type: ignore[no-untyped-def]
        self.delegate = delegate
        self.execution = None

    @property
    def adapter(self) -> str:
        return self.delegate.adapter

    def start(self, context: SkillContext) -> _CrashOnWaitHandle:
        self.execution = self.delegate.start(context)
        return _CrashOnWaitHandle(self.execution)

    def run(self, context: SkillContext) -> SkillResult:
        return self.delegate.run(context)


class _DiagnosticFailureAdapter:
    adapter = "fixture:redaction"

    def __init__(self, diagnostic: str) -> None:
        self.diagnostic = diagnostic

    def run(self, context: SkillContext) -> SkillResult:
        del context
        raise SkillProcessError(
            "redaction fixture",
            adapter=self.adapter,
            stdout=self.diagnostic,
            stderr=self.diagnostic,
            elapsed_ms=1,
            exit_code=1,
        )


def _revision() -> HarnessRevision:
    return HarnessRevision(
        pipeline_digest="pipeline-v3-fixture",
        kernel_digest="kernel-v3-fixture",
    )


def _plan(*units: UnitPlan, targets: tuple[str, ...] = ()) -> RunPlan:
    return RunPlan(
        goal=Goal(
            id="goal-v3",
            request="Exercise the local engine",
            workflow="engine-fixture",
            target_artifacts=targets,
        ),
        units=units,
    )


def _engine(
    workspace: Path,
    *,
    artifacts: InMemoryArtifacts,
    adapters: dict[str, SkillAdapter],
    ledger: InMemoryRunLedger | None = None,
) -> LocalRunEngine:
    return LocalRunEngine(
        workspace,
        ledger=ledger if ledger is not None else InMemoryRunLedger(),
        artifacts=artifacts,
        skill_adapters=adapters,
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )


def _writer(
    artifacts: InMemoryArtifacts,
    *,
    run_id: str,
    output: str,
    calls: list[str],
) -> InMemorySkillAdapter:
    def write(context: SkillContext) -> None:
        calls.append(context.unit_id)
        artifacts.put(run_id, output, f"created by {context.unit_id}")

    return InMemorySkillAdapter(handler=write, adapter=f"fixture:{output}")


def _filesystem_writer(workspace: Path, *, output: str) -> InMemorySkillAdapter:
    """A writer that materializes a real file on disk (for filesystem storage)."""

    def write(context: SkillContext) -> None:
        path = workspace / output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"created by {context.unit_id}\n", encoding="utf-8")

    return InMemorySkillAdapter(handler=write, adapter=f"fixture:fs:{output}")


def test_one_advance_hides_attempt_choreography_and_completes_run(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifacts = InMemoryArtifacts()
    calls: list[str] = []
    run_id = "run-one"
    engine = _engine(
        workspace,
        artifacts=artifacts,
        adapters={
            "writer": _writer(artifacts, run_id=run_id, output="result.md", calls=calls)
        },
    )
    plan = _plan(
        UnitPlan(id="U010", title="Write", skill="writer", outputs=("result.md",)),
        targets=("result.md",),
    )

    created = engine.execute(CreateLocalRun(plan=plan, run_id=run_id))
    result = engine.execute(AdvanceRun())

    assert created.outcome is EngineOutcome.CREATED
    assert result.outcome is EngineOutcome.COMPLETED
    assert result.unit_ids == ("U010",)
    assert calls == ["U010"]
    inspected = engine.inspect()
    assert inspected.state is InspectionState.COMPLETED
    assert inspected.run is not None
    assert inspected.run.status is RunStatus.COMPLETED
    assert inspected.run.unit("U010").status is UnitStatus.DONE
    assert inspected.run.attempts[0].status is AttemptStatus.SUCCEEDED
    assert len(inspected.run.completions) == 1


def test_blocked_or_complete_advances_the_dag_but_after_one_stops(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifacts = InMemoryArtifacts()
    calls: list[str] = []
    run_id = "run-dag"
    engine = _engine(
        workspace,
        artifacts=artifacts,
        adapters={
            "first": _writer(artifacts, run_id=run_id, output="first.md", calls=calls),
            "second": _writer(
                artifacts, run_id=run_id, output="second.md", calls=calls
            ),
        },
    )
    plan = _plan(
        UnitPlan(id="U010", title="First", skill="first", outputs=("first.md",)),
        UnitPlan(
            id="U020",
            title="Second",
            skill="second",
            depends_on=("U010",),
            outputs=("second.md",),
        ),
        targets=("second.md",),
    )
    engine.execute(CreateLocalRun(plan=plan, run_id=run_id))

    first = engine.execute(AdvanceRun())
    finished = engine.execute(AdvanceRun(until=AdvanceUntil.BLOCKED_OR_COMPLETE))

    assert first.outcome is EngineOutcome.ADVANCED
    assert first.unit_ids == ("U010",)
    assert finished.outcome is EngineOutcome.COMPLETED
    assert finished.unit_ids == ("U020",)
    assert calls == ["U010", "U020"]


def test_skill_failure_is_durable_and_not_retried_in_the_same_advance(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifacts = InMemoryArtifacts()
    run_id = "run-retry"
    calls = 0

    def fail_then_succeed(context: SkillContext) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient secret-free failure")
        artifacts.put(run_id, "result.md", "recovered")

    engine = _engine(
        workspace,
        artifacts=artifacts,
        adapters={
            "writer": InMemorySkillAdapter(
                handler=fail_then_succeed, adapter="fixture:retry"
            )
        },
    )
    engine.execute(
        CreateLocalRun(
            run_id=run_id,
            plan=_plan(
                UnitPlan(
                    id="U010", title="Write", skill="writer", outputs=("result.md",)
                ),
                targets=("result.md",),
            ),
        )
    )

    failed = engine.execute(AdvanceRun(until=AdvanceUntil.BLOCKED_OR_COMPLETE))

    assert failed.outcome is EngineOutcome.SKILL_FAILED
    assert calls == 1
    assert len(failed.issues) == 1
    assert "SkillHandlerError" in failed.issues[0]
    first_view = engine.inspect().run
    assert first_view is not None
    assert first_view.unit("U010").status is UnitStatus.BLOCKED
    assert first_view.attempts[0].status is AttemptStatus.FAILED_RETRYABLE

    retried = engine.execute(AdvanceRun())
    assert retried.outcome is EngineOutcome.COMPLETED
    assert calls == 2
    final_view = engine.inspect().run
    assert final_view is not None
    assert [attempt.status for attempt in final_view.attempts] == [
        AttemptStatus.FAILED_RETRYABLE,
        AttemptStatus.SUCCEEDED,
    ]


def test_checkpoint_approval_does_not_dispatch_the_human_skill(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifacts = InMemoryArtifacts()
    calls: list[str] = []
    run_id = "run-human"
    engine = _engine(
        workspace,
        artifacts=artifacts,
        adapters={
            "producer": _writer(
                artifacts, run_id=run_id, output="basis.md", calls=calls
            )
        },
    )
    plan = _plan(
        UnitPlan(id="U010", title="Produce", skill="producer", outputs=("basis.md",)),
        UnitPlan(
            id="U020",
            title="Approve",
            skill="human-checkpoint",
            owner=Owner.HUMAN,
            checkpoint="C1",
            depends_on=("U010",),
            inputs=("basis.md", "DECISIONS.md"),
            outputs=("DECISIONS.md",),
        ),
        targets=("DECISIONS.md",),
    )
    engine.execute(CreateLocalRun(plan=plan, run_id=run_id))

    waiting = engine.execute(AdvanceRun(until=AdvanceUntil.BLOCKED_OR_COMPLETE))
    assert waiting.outcome is EngineOutcome.WAITING_FOR_CHECKPOINT
    assert waiting.unit_ids == ("U010",)
    assert waiting.inspection.waiting_checkpoint == "C1"
    assert calls == ["U010"]

    artifacts.put(
        run_id,
        "DECISIONS.md",
        "- [x] Approve C1\n"
        "<!-- BEGIN CHECKPOINT:C1 -->\nreviewed\n"
        "<!-- END CHECKPOINT:C1 -->\n",
    )
    approved = engine.execute(ApproveLocalCheckpoint(checkpoint="C1"))
    assert approved.outcome is EngineOutcome.APPROVED
    approved_view = engine.inspect().run
    assert approved_view is not None
    assert approved_view.unit("U020").status is UnitStatus.TODO

    completed = engine.execute(AdvanceRun())
    assert completed.outcome is EngineOutcome.COMPLETED
    assert completed.unit_ids == ("U020",)
    assert calls == ["U010"]


def test_advance_automatically_recovers_a_prepared_completion(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifacts = InMemoryArtifacts()
    calls: list[str] = []
    run_id = "run-recover"
    engine = _engine(
        workspace,
        artifacts=artifacts,
        adapters={
            "writer": _writer(artifacts, run_id=run_id, output="result.md", calls=calls)
        },
    )
    engine.execute(
        CreateLocalRun(
            run_id=run_id,
            plan=_plan(
                UnitPlan(
                    id="U010", title="Write", skill="writer", outputs=("result.md",)
                ),
                targets=("result.md",),
            ),
        )
    )
    artifacts.fail_next_finalize()

    with pytest.raises(EngineError) as raised:
        engine.execute(AdvanceRun())
    assert raised.value.code is EngineErrorCode.ADAPTER_FAILURE
    interrupted = engine.inspect().run
    assert interrupted is not None
    assert interrupted.completions[0].phase.value == "PREPARED"

    recovered = engine.execute(AdvanceRun())
    assert recovered.outcome is EngineOutcome.COMPLETED
    assert recovered.recovered is True
    assert recovered.unit_ids == ()
    assert calls == ["U010"]

    no_recovery = engine.execute(RecoverLocalRun())
    assert no_recovery.outcome is EngineOutcome.NOOP


def test_state_write_fault_at_attempt_begin_is_recoverable(
    tmp_path: Path,
) -> None:
    # A ledger state-write fault (the atomic state.json replace failing) at the
    # BeginAttempt save must surface as a bounded adapter error AND leave the
    # canonical Run untouched, so a fresh AdvanceRun reloads the prior state and
    # completes -- the skill runs exactly once (no phantom Attempt, no rerun).
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifacts = InMemoryArtifacts()
    ledger = InMemoryRunLedger()
    calls: list[str] = []
    run_id = "run-save-fault"
    engine = _engine(
        workspace,
        artifacts=artifacts,
        ledger=ledger,
        adapters={
            "writer": _writer(artifacts, run_id=run_id, output="result.md", calls=calls)
        },
    )
    engine.execute(
        CreateLocalRun(
            run_id=run_id,
            plan=_plan(
                UnitPlan(
                    id="U010", title="Write", skill="writer", outputs=("result.md",)
                ),
                targets=("result.md",),
            ),
        )
    )
    created = engine.inspect().run
    assert created is not None
    ledger.fail_next_save()

    with pytest.raises(EngineError) as raised:
        engine.execute(AdvanceRun())
    assert raised.value.code is EngineErrorCode.ADAPTER_FAILURE

    # The fault hit the BeginAttempt save: the canonical state is unchanged --
    # the Unit is still TODO with no Attempt, and the skill never ran.
    interrupted = engine.inspect().run
    assert interrupted is not None
    assert interrupted.version == created.version
    assert interrupted.unit("U010").status is UnitStatus.TODO
    assert interrupted.attempts == ()
    assert interrupted.active_attempt_id is None
    assert calls == []

    # A fresh AdvanceRun reloads the prior canonical state and completes: the
    # fault was one-shot, so the BeginAttempt save now succeeds and the skill
    # runs exactly once.
    recovered = engine.execute(AdvanceRun())
    assert recovered.outcome is EngineOutcome.COMPLETED
    assert calls == ["U010"]
    assert engine.inspect().run.unit("U010").status is UnitStatus.DONE


def test_completed_run_is_replayable_in_a_disposable_workspace(
    tmp_path: Path,
) -> None:
    # Disposable-Workspace replay evidence: a completed Run's durable state
    # (``.harness-v3/`` + the materialized Artifacts) is self-contained and
    # path-independent. Cloning it into a fresh Workspace with a different
    # absolute path and opening an engine there reproduces the same COMPLETED
    # Run, and advancing the replay is a no-op. The durable state -- not the
    # Workspace path -- is the authority.
    source = tmp_path / "source"
    source.mkdir()
    run_id = "run-replay"
    engine = LocalRunEngine.for_workspace(
        source,
        skill_adapters={"writer": _filesystem_writer(source, output="result.md")},
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )
    engine.execute(
        CreateLocalRun(
            run_id=run_id,
            plan=_plan(
                UnitPlan(
                    id="U010", title="Write", skill="writer", outputs=("result.md",)
                ),
                targets=("result.md",),
            ),
        )
    )
    completed = engine.execute(AdvanceRun())
    assert completed.outcome is EngineOutcome.COMPLETED
    source_view = engine.inspect().run
    assert source_view is not None

    # Clone the durable state + the materialized Artifact into a disposable
    # Workspace with a different absolute path.
    disposable = tmp_path / "disposable"
    disposable.mkdir()
    shutil.copytree(source / ".harness-v3", disposable / ".harness-v3")
    shutil.copy2(source / "result.md", disposable / "result.md")

    replay = LocalRunEngine.for_workspace(
        disposable,
        skill_adapters={
            "writer": _filesystem_writer(disposable, output="result.md")
        },
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )
    replayed = replay.inspect().run
    assert replayed is not None
    assert replayed.id == source_view.id
    assert replayed.version == source_view.version
    assert replayed.status is RunStatus.COMPLETED
    assert replayed.completions == source_view.completions
    assert replayed.unit("U010").status is UnitStatus.DONE

    # The replayed engine recognizes the Run as already complete: advancing is
    # a no-op that re-runs no Skill.
    advanced = replay.execute(AdvanceRun())
    assert advanced.outcome is EngineOutcome.COMPLETED
    assert advanced.unit_ids == ()


def test_checkpoint_blocked_run_replays_and_completes_in_a_disposable_workspace(
    tmp_path: Path,
) -> None:
    # Mid-flight replay: a Run blocked at a human checkpoint is cloned into a
    # disposable workspace and driven to completion there. The pending-checkpoint
    # state and the DECISIONS.md artifact are both path-independent, so a human
    # Decision can be resumed and committed in a fresh workspace.
    source = tmp_path / "source"
    source.mkdir()
    run_id = "run-checkpoint-replay"
    engine = LocalRunEngine.for_workspace(
        source,
        skill_adapters={
            "producer": _filesystem_writer(source, output="basis.md"),
        },
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )
    plan = _plan(
        UnitPlan(id="U010", title="Produce", skill="producer", outputs=("basis.md",)),
        UnitPlan(
            id="U020",
            title="Approve",
            skill="human-checkpoint",
            owner=Owner.HUMAN,
            checkpoint="C1",
            depends_on=("U010",),
            inputs=("basis.md", "DECISIONS.md"),
            outputs=("DECISIONS.md",),
        ),
        targets=("DECISIONS.md",),
    )
    engine.execute(CreateLocalRun(plan=plan, run_id=run_id))

    waiting = engine.execute(AdvanceRun(until=AdvanceUntil.BLOCKED_OR_COMPLETE))
    assert waiting.outcome is EngineOutcome.WAITING_FOR_CHECKPOINT
    assert waiting.unit_ids == ("U010",)
    assert waiting.inspection.waiting_checkpoint == "C1"

    # Clone the durable state + the producer's artifact mid-flight, before the
    # human decision exists.
    disposable = tmp_path / "disposable"
    disposable.mkdir()
    shutil.copytree(source / ".harness-v3", disposable / ".harness-v3")
    shutil.copy2(source / "basis.md", disposable / "basis.md")

    # In the disposable workspace, write the human decision and approve it.
    (disposable / "DECISIONS.md").write_text(
        "- [x] Approve C1\n"
        "<!-- BEGIN CHECKPOINT:C1 -->\nreviewed\n"
        "<!-- END CHECKPOINT:C1 -->\n",
        encoding="utf-8",
    )
    replay = LocalRunEngine.for_workspace(
        disposable,
        skill_adapters={
            "producer": _filesystem_writer(disposable, output="basis.md"),
        },
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )
    approved = replay.execute(ApproveLocalCheckpoint(checkpoint="C1"))
    assert approved.outcome is EngineOutcome.APPROVED

    completed = replay.execute(AdvanceRun())
    assert completed.outcome is EngineOutcome.COMPLETED
    assert completed.unit_ids == ("U020",)
    assert replay.inspect().run.status is RunStatus.COMPLETED


def test_legacy_v2_workspace_is_inspectable_but_never_mutated(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    legacy = workspace / ".harness"
    legacy.mkdir(parents=True)
    lock = legacy / "harness.lock.json"
    lock.write_text(json.dumps({"schema": "harness-lock.v2"}), encoding="utf-8")
    artifacts = InMemoryArtifacts()
    engine = _engine(workspace, artifacts=artifacts, adapters={})

    inspected = engine.inspect()
    assert inspected.state is InspectionState.LEGACY_READ_ONLY
    assert inspected.run is None

    with pytest.raises(EngineError) as raised:
        engine.execute(
            CreateLocalRun(
                run_id="forbidden",
                plan=_plan(UnitPlan(id="U010", title="No", skill="never")),
            )
        )
    assert raised.value.code is EngineErrorCode.LEGACY_READ_ONLY
    assert not (workspace / ".harness-v3").exists()


def test_one_workspace_rejects_a_second_canonical_run(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    engine = _engine(workspace, artifacts=InMemoryArtifacts(), adapters={})
    plan = _plan(UnitPlan(id="U010", title="One", skill="one"))
    engine.execute(CreateLocalRun(plan=plan, run_id="canonical"))

    with pytest.raises(EngineError) as raised:
        engine.execute(CreateLocalRun(plan=plan, run_id="replacement"))

    assert raised.value.code is EngineErrorCode.RUN_EXISTS
    assert engine.inspect().run_id == "canonical"


def test_default_filesystem_builder_reopens_the_canonical_run(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def write(context: SkillContext) -> None:
        output = context.output_paths[0]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("durable\n", encoding="utf-8")

    adapters = {
        "writer": InMemorySkillAdapter(
            handler=write,
            adapter="fixture:filesystem",
        )
    }
    engine = LocalRunEngine.for_workspace(
        workspace,
        skill_adapters=adapters,
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )
    engine.execute(
        CreateLocalRun(
            run_id="durable-run",
            plan=_plan(
                UnitPlan(
                    id="U010",
                    title="Write",
                    skill="writer",
                    outputs=("output/result.md",),
                ),
                targets=("output/result.md",),
            ),
        )
    )
    assert engine.execute(AdvanceRun()).outcome is EngineOutcome.COMPLETED

    reopened = LocalRunEngine.for_workspace(
        workspace,
        skill_adapters=adapters,
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )

    assert reopened.inspect().run_id == "durable-run"
    assert reopened.inspect().state is InspectionState.COMPLETED
    with pytest.raises(EngineError) as raised:
        reopened.execute(
            CreateLocalRun(
                run_id="replacement",
                plan=_plan(UnitPlan(id="U020", title="No", skill="writer")),
            )
        )
    assert raised.value.code is EngineErrorCode.RUN_EXISTS


def test_restart_requires_explicit_interruption_of_an_active_attempt(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    plan = _plan(
        UnitPlan(
            id="U010",
            title="Write",
            skill="writer",
            outputs=("output/result.md",),
        ),
        targets=("output/result.md",),
    )
    crashed = LocalRunEngine.for_workspace(
        workspace,
        skill_adapters={"writer": _CrashAdapter()},
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )
    crashed.execute(CreateLocalRun(plan=plan, run_id="crashed-run"))

    with pytest.raises(_SimulatedCrash):
        crashed.execute(AdvanceRun())

    def finish(context: SkillContext) -> None:
        output = context.output_paths[0]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("recovered\n", encoding="utf-8")

    restarted = LocalRunEngine.for_workspace(
        workspace,
        skill_adapters={
            "writer": InMemorySkillAdapter(
                handler=finish,
                adapter="fixture:after-crash",
            )
        },
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )

    advance = restarted.execute(AdvanceRun())
    conservative = restarted.execute(RecoverLocalRun())
    assert advance.outcome is EngineOutcome.BLOCKED
    assert conservative.outcome is EngineOutcome.BLOCKED
    assert "interrupt_active=True" in advance.issues[0]
    still_active = restarted.inspect().run
    assert still_active is not None
    assert still_active.active_attempt_id is not None

    interrupted = restarted.execute(RecoverLocalRun(interrupt_active=True))
    assert interrupted.outcome is EngineOutcome.RECOVERED
    after_interrupt = restarted.inspect().run
    assert after_interrupt is not None
    assert after_interrupt.active_attempt_id is None
    assert after_interrupt.attempts[0].status is AttemptStatus.FAILED_RETRYABLE

    completed = restarted.execute(AdvanceRun())
    assert completed.outcome is EngineOutcome.COMPLETED
    final = restarted.inspect().run
    assert final is not None
    assert [attempt.status for attempt in final.attempts] == [
        AttemptStatus.FAILED_RETRYABLE,
        AttemptStatus.SUCCEEDED,
    ]


def test_unsafe_skill_context_is_not_misclassified_as_storage_failure(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (workspace / "escaped").symlink_to(outside, target_is_directory=True)
    engine = _engine(
        workspace,
        artifacts=InMemoryArtifacts(),
        adapters={
            "writer": InMemorySkillAdapter(
                handler=lambda _: None,
                adapter="fixture:unsafe-context",
            )
        },
    )
    engine.execute(
        CreateLocalRun(
            run_id="unsafe-context",
            plan=_plan(
                UnitPlan(
                    id="U010",
                    title="Escape",
                    skill="writer",
                    outputs=("escaped/result.md",),
                )
            ),
        )
    )

    with pytest.raises(EngineError) as raised:
        engine.execute(AdvanceRun())

    assert raised.value.code is EngineErrorCode.SKILL_CONTEXT_INVALID
    inspected = engine.inspect().run
    assert inspected is not None
    assert inspected.attempts == ()


def test_generic_adapter_failure_does_not_persist_exception_text(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    engine = _engine(
        workspace,
        artifacts=InMemoryArtifacts(),
        adapters={"writer": _SecretFailureAdapter()},
    )
    engine.execute(
        CreateLocalRun(
            run_id="secret-failure",
            plan=_plan(UnitPlan(id="U010", title="Fail", skill="writer")),
        )
    )

    failed = engine.execute(AdvanceRun())

    assert failed.outcome is EngineOutcome.SKILL_FAILED
    assert "DO-NOT-PERSIST" not in failed.issues[0]
    inspected = engine.inspect().run
    assert inspected is not None
    assert "DO-NOT-PERSIST" not in inspected.attempts[0].message


def test_any_nonempty_legacy_harness_directory_is_read_only(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    unexpected = workspace / ".harness" / "future" / "durable.record"
    unexpected.parent.mkdir(parents=True)
    unexpected.write_text("evidence\n", encoding="utf-8")
    engine = _engine(workspace, artifacts=InMemoryArtifacts(), adapters={})

    assert engine.inspect().state is InspectionState.LEGACY_READ_ONLY
    with pytest.raises(EngineError) as raised:
        engine.execute(
            CreateLocalRun(
                run_id="forbidden",
                plan=_plan(UnitPlan(id="U010", title="No", skill="never")),
            )
        )
    assert raised.value.code is EngineErrorCode.LEGACY_READ_ONLY
    assert not (workspace / ".harness-v3").exists()


def test_explicit_recovery_refuses_while_recorded_subprocess_owner_is_live(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    script = tmp_path / "repo" / ".codex" / "skills" / "sleeper" / "scripts" / "run.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        """
import argparse
import time

parser = argparse.ArgumentParser()
parser.add_argument("--workspace")
parser.add_argument("--unit-id")
parser.add_argument("--inputs")
parser.add_argument("--outputs")
parser.add_argument("--checkpoint")
parser.parse_args()
time.sleep(60)
""".lstrip(),
        encoding="utf-8",
    )
    from research_harness.skills import SubprocessSkillAdapter

    subprocess_adapter = SubprocessSkillAdapter.for_repo_skill(
        repo_root=tmp_path / "repo",
        skill="sleeper",
    )
    crashing_adapter = _CrashAfterSubprocessStartAdapter(subprocess_adapter)
    engine = LocalRunEngine.for_workspace(
        workspace,
        skill_adapters={"sleeper": crashing_adapter},
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )
    engine.execute(
        CreateLocalRun(
            run_id="live-owner",
            plan=_plan(UnitPlan(id="U010", title="Sleep", skill="sleeper")),
        )
    )

    with pytest.raises(_SimulatedCrash):
        engine.execute(AdvanceRun())

    owner_path = workspace / ".harness-v3" / "runtime" / "active-attempt.json"
    owner_text = owner_path.read_text(encoding="utf-8")
    owner = json.loads(owner_text)
    assert set(owner) == {
        "schema",
        "run_id",
        "attempt_id",
        "unit_id",
        "adapter",
        "pid",
        "process_group_id",
        "start_token",
    }
    assert owner["pid"] > 0
    assert owner["process_group_id"] == owner["pid"]
    assert len(owner["start_token"]) == 64
    assert str(workspace) not in owner_text
    restarted = LocalRunEngine.for_workspace(
        workspace,
        skill_adapters={"sleeper": subprocess_adapter},
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )

    refused = restarted.execute(RecoverLocalRun(interrupt_active=True))
    assert refused.outcome is EngineOutcome.BLOCKED
    assert "still live" in refused.issues[0]
    assert restarted.inspect().run is not None
    assert restarted.inspect().run.active_attempt_id is not None

    assert crashing_adapter.execution is not None
    crashing_adapter.execution.terminate()
    with pytest.raises(SkillProcessError):
        crashing_adapter.execution.wait()
    recovered = restarted.execute(RecoverLocalRun(interrupt_active=True))
    assert recovered.outcome is EngineOutcome.RECOVERED
    assert not owner_path.exists()


def test_retry_rejects_an_unchanged_required_output_version(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifacts = InMemoryArtifacts()
    run_id = "retry-freshness"
    calls = 0

    def write_once_then_reuse(context: SkillContext) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            artifacts.put(run_id, "draft.md", "version-one")
            raise RuntimeError("first attempt fails after writing")
        if calls == 3:
            artifacts.put(run_id, "draft.md", "version-two")

    engine = _engine(
        workspace,
        artifacts=artifacts,
        adapters={
            "writer": InMemorySkillAdapter(
                handler=write_once_then_reuse,
                adapter="fixture:retry-freshness",
            )
        },
    )
    engine.execute(
        CreateLocalRun(
            run_id=run_id,
            plan=_plan(
                UnitPlan(
                    id="U010",
                    title="Rewrite",
                    skill="writer",
                    inputs=("draft.md",),
                    outputs=("draft.md",),
                ),
                targets=("draft.md",),
            ),
        )
    )

    assert engine.execute(AdvanceRun()).outcome is EngineOutcome.SKILL_FAILED
    reused = engine.execute(AdvanceRun())
    assert reused.outcome is EngineOutcome.SKILL_FAILED
    assert "new evidence version" in reused.issues[0]
    assert engine.inspect().run is not None
    assert len(engine.inspect().run.attempts) == 2

    refreshed = engine.execute(AdvanceRun())
    assert refreshed.outcome is EngineOutcome.COMPLETED
    assert calls == 3


def test_persisted_skill_diagnostics_redact_paths_and_secrets(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository = Path(__file__).resolve().parents[2]
    secret = "sk-live-should-never-persist"
    diagnostic = (
        f"workspace={workspace}/output/result.md\n"
        f"repo={repository}/src/private.py\n"
        f"OPENAI_API_KEY={secret}\n"
        f"Authorization: Bearer {secret}\n"
    )
    engine = _engine(
        workspace,
        artifacts=InMemoryArtifacts(),
        adapters={"writer": _DiagnosticFailureAdapter(diagnostic)},
    )
    engine.execute(
        CreateLocalRun(
            run_id="redacted",
            plan=_plan(UnitPlan(id="U010", title="Fail", skill="writer")),
        )
    )

    failed = engine.execute(AdvanceRun())

    persisted = engine.inspect().run
    assert persisted is not None
    combined = "\n".join((*failed.issues, persisted.attempts[0].message))
    assert str(workspace) not in combined
    assert str(repository) not in combined
    assert secret not in combined
    assert "<WORKSPACE>" in combined
    assert "<REPO>" in combined
    assert "<REDACTED>" in combined


def test_broken_legacy_harness_symlink_is_read_only(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".harness").symlink_to(
        tmp_path / "missing-legacy-target",
        target_is_directory=True,
    )
    engine = _engine(workspace, artifacts=InMemoryArtifacts(), adapters={})

    assert engine.inspect().state is InspectionState.LEGACY_READ_ONLY
    with pytest.raises(EngineError) as raised:
        engine.execute(
            CreateLocalRun(
                run_id="forbidden",
                plan=_plan(UnitPlan(id="U010", title="No", skill="never")),
            )
        )
    assert raised.value.code is EngineErrorCode.LEGACY_READ_ONLY


@pytest.mark.parametrize("layout", ("runtime-symlink", "owner-symlink"))
def test_runtime_owner_metadata_rejects_symlink_layouts(
    tmp_path: Path,
    layout: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repo_root = tmp_path / "repo"
    script = repo_root / ".codex" / "skills" / "sleeper" / "scripts" / "run.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        """
import argparse
import time

parser = argparse.ArgumentParser()
parser.add_argument("--workspace")
parser.add_argument("--unit-id")
parser.add_argument("--inputs")
parser.add_argument("--outputs")
parser.add_argument("--checkpoint")
parser.parse_args()
time.sleep(60)
""".lstrip(),
        encoding="utf-8",
    )
    from research_harness.skills import SubprocessSkillAdapter

    adapter = SubprocessSkillAdapter.for_repo_skill(
        repo_root=repo_root,
        skill="sleeper",
    )
    engine = LocalRunEngine.for_workspace(
        workspace,
        skill_adapters={"sleeper": adapter},
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )
    engine.execute(
        CreateLocalRun(
            run_id=f"unsafe-{layout}",
            plan=_plan(UnitPlan(id="U010", title="Sleep", skill="sleeper")),
        )
    )
    runtime = workspace / ".harness-v3" / "runtime"
    outside = tmp_path / "outside"
    outside.mkdir()
    if layout == "runtime-symlink":
        runtime.symlink_to(outside, target_is_directory=True)
        protected = outside / "active-attempt.json"
    else:
        runtime.mkdir()
        protected = outside / "owner.json"
        protected.write_text("sentinel\n", encoding="utf-8")
        (runtime / "active-attempt.json").symlink_to(protected)

    with pytest.raises(EngineError) as raised:
        engine.execute(AdvanceRun())

    assert raised.value.code is EngineErrorCode.INTEGRITY_VIOLATION
    if layout == "runtime-symlink":
        assert not protected.exists()
    else:
        assert protected.read_text(encoding="utf-8") == "sentinel\n"


@pytest.mark.parametrize("malformation", ("unknown-field", "control-character"))
def test_runtime_owner_decode_rejects_malformed_records(
    tmp_path: Path,
    malformation: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    engine = LocalRunEngine.for_workspace(
        workspace,
        skill_adapters={"writer": _CrashAdapter()},
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )
    engine.execute(
        CreateLocalRun(
            run_id=f"malformed-{malformation}",
            plan=_plan(UnitPlan(id="U010", title="Crash", skill="writer")),
        )
    )
    with pytest.raises(_SimulatedCrash):
        engine.execute(AdvanceRun())
    run = engine.inspect().run
    assert run is not None
    assert run.active_attempt_id is not None
    owner = {
        "schema": "research-harness.active-skill-owner/v1",
        "run_id": run.id,
        "attempt_id": run.active_attempt_id,
        "unit_id": "U010",
        "adapter": "fixture:crash",
        "pid": os.getpid(),
        "process_group_id": os.getpgid(os.getpid()),
        "start_token": "0" * 64,
    }
    if malformation == "unknown-field":
        owner["unexpected"] = True
    else:
        owner["adapter"] = "fixture:\ncrash"
    owner_path = workspace / ".harness-v3" / "runtime" / "active-attempt.json"
    owner_path.parent.mkdir()
    owner_path.write_text(json.dumps(owner), encoding="utf-8")

    with pytest.raises(EngineError) as raised:
        engine.execute(RecoverLocalRun(interrupt_active=True))

    assert raised.value.code is EngineErrorCode.INTEGRITY_VIOLATION
    still_active = engine.inspect().run
    assert still_active is not None
    assert still_active.active_attempt_id is not None


def test_lifecycle_backed_recovery_refuses_missing_owner_metadata(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    crashed = LocalRunEngine.for_workspace(
        workspace,
        skill_adapters={"sleeper": _CrashAdapter()},
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )
    crashed.execute(
        CreateLocalRun(
            run_id="missing-lifecycle-owner",
            plan=_plan(UnitPlan(id="U010", title="Sleep", skill="sleeper")),
        )
    )
    with pytest.raises(_SimulatedCrash):
        crashed.execute(AdvanceRun())

    repo_root = tmp_path / "repo"
    script = repo_root / ".codex" / "skills" / "sleeper" / "scripts" / "run.py"
    script.parent.mkdir(parents=True)
    script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    from research_harness.skills import SubprocessSkillAdapter

    restarted = LocalRunEngine.for_workspace(
        workspace,
        skill_adapters={
            "sleeper": SubprocessSkillAdapter.for_repo_skill(
                repo_root=repo_root,
                skill="sleeper",
            )
        },
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )

    refused = restarted.execute(RecoverLocalRun(interrupt_active=True))

    assert refused.outcome is EngineOutcome.BLOCKED
    assert "no trustworthy process ownership" in refused.issues[0]
    run = restarted.inspect().run
    assert run is not None
    assert run.active_attempt_id is not None
