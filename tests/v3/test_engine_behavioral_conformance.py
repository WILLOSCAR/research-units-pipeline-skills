from __future__ import annotations

from pathlib import Path

import pytest

from research_harness.application import InMemoryArtifacts, plan_from_workflow
from research_harness.domain import (
    AttemptStatus,
    CompletionPhase,
    RunStatus,
    UnitStatus,
)
from research_harness.engine import (
    AdvanceRun,
    ApproveLocalCheckpoint,
    CreateLocalRun,
    EngineError,
    EngineErrorCode,
    EngineOutcome,
    LocalRunEngine,
    RecoverLocalRun,
)
from research_harness.skills import SkillContext
from research_harness.workflows import load_workflow_definition
from tests.v3.support.factories import (
    approved_decision,
    checkpoint_plan,
    create_run,
    make_acceptance,
    make_engine,
    required_check_plan,
    revision,
    single_unit_plan,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTABLE_WORKFLOWS = (
    "arxiv-survey-latex",
    "arxiv-survey",
    "evidence-review",
    "idea-brainstorm",
    "paper-review",
    "research-brief",
    "source-tutorial",
)


def test_retry_preserves_the_failed_attempt_and_uses_a_new_identity(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    plan = single_unit_plan()

    def fail_then_succeed(
        context: SkillContext,
        artifacts: InMemoryArtifacts,
        run_id: str,
        calls: list[str],
    ) -> None:
        del context
        if len(calls) == 1:
            raise RuntimeError("source unavailable")
        artifacts.put(run_id, "output/review.md", "recovered review")

    fixture = make_engine(
        plan,
        workspace=workspace,
        run_id="run_retry",
        handlers={"paper-review-writer": fail_then_succeed},
    )
    create_run(fixture, plan, run_id="run_retry")

    failed = fixture.engine.execute(AdvanceRun())
    retried = fixture.engine.execute(AdvanceRun())

    inspected = fixture.engine.inspect().run
    assert inspected is not None
    assert failed.outcome is EngineOutcome.SKILL_FAILED
    assert retried.outcome is EngineOutcome.COMPLETED
    assert failed.attempt_ids[0] != retried.attempt_ids[0]
    assert [attempt.status for attempt in inspected.attempts] == [
        AttemptStatus.FAILED_RETRYABLE,
        AttemptStatus.SUCCEEDED,
    ]
    assert inspected.status is RunStatus.COMPLETED
    assert fixture.calls == ["U010", "U010"]


def test_changed_review_evidence_revokes_a_human_checkpoint(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    plan = checkpoint_plan()
    fixture = make_engine(
        plan,
        workspace=workspace,
        run_id="run_checkpoint",
    )
    create_run(fixture, plan, run_id="run_checkpoint")
    fixture.engine.execute(AdvanceRun(unit_id="U010"))
    fixture.artifacts.put("run_checkpoint", "DECISIONS.md", approved_decision("C1"))
    fixture.engine.execute(ApproveLocalCheckpoint(checkpoint="C1"))

    fixture.artifacts.put("run_checkpoint", "scope.md", "scope-v2")
    blocked = fixture.engine.execute(AdvanceRun(unit_id="U020"))

    inspected = fixture.engine.inspect().run
    assert inspected is not None
    assert blocked.outcome is EngineOutcome.BLOCKED
    assert any("stale" in issue for issue in blocked.issues)
    assert inspected.unit("U020").status is UnitStatus.BLOCKED
    assert not inspected.checkpoint_approvals[-1].active
    assert "checkpoint.approval.revoked" in {event.kind for event in inspected.events}


def test_prepared_completion_recovers_after_manifest_finalize_failure(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    plan = single_unit_plan()
    fixture = make_engine(
        plan,
        workspace=workspace,
        run_id="run_recovery",
    )
    create_run(fixture, plan, run_id="run_recovery")
    fixture.artifacts.fail_next_finalize()

    with pytest.raises(EngineError) as caught:
        fixture.engine.execute(AdvanceRun())

    prepared = fixture.engine.inspect().run
    assert prepared is not None
    assert caught.value.code is EngineErrorCode.ADAPTER_FAILURE
    assert prepared.completions[-1].phase is CompletionPhase.PREPARED
    recovered = fixture.engine.execute(RecoverLocalRun())
    assert recovered.outcome is EngineOutcome.RECOVERED
    assert recovered.recovered
    assert recovered.inspection.run is not None
    assert recovered.inspection.run.completions[-1].phase is CompletionPhase.COMMITTED
    assert recovered.inspection.run.status is RunStatus.COMPLETED
    assert fixture.calls == ["U010"]


def test_revision_drift_blocks_mutation_but_preserves_read_only_inspection(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    plan = single_unit_plan()
    original = LocalRunEngine.for_workspace(
        workspace,
        skill_adapters={},
        acceptance=make_acceptance(plan),
        revision=revision("original"),
    )
    original.execute(CreateLocalRun(run_id="run_pinned", plan=plan))
    drifted = LocalRunEngine.for_workspace(
        workspace,
        skill_adapters={},
        acceptance=make_acceptance(plan),
        revision=revision("changed"),
    )

    with pytest.raises(EngineError) as caught:
        drifted.execute(AdvanceRun())

    assert caught.value.code is EngineErrorCode.REVISION_DRIFT
    inspected = drifted.inspect().run
    assert inspected is not None
    assert inspected.revision == revision("original")
    assert inspected.attempts == ()
    assert tuple(event.kind for event in inspected.events) == (
        "run.created",
        "run.planned",
    )


def test_final_completion_rejects_stale_required_check_evidence(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    plan = required_check_plan()
    fixture = make_engine(
        plan,
        workspace=workspace,
        run_id="run_freshness",
    )
    create_run(fixture, plan, run_id="run_freshness")

    fixture.engine.execute(AdvanceRun(unit_id="U010"))
    checked = fixture.engine.execute(AdvanceRun(unit_id="U020"))
    assert checked.inspection.run is not None
    assert checked.inspection.run.completions[-1].acceptance.checks == (
        "paper-review-auditor",
    )

    fixture.artifacts.put("run_freshness", "source.md", "source-v2")
    blocked = fixture.engine.execute(AdvanceRun(unit_id="U030"))

    assert blocked.outcome is EngineOutcome.BLOCKED
    assert any(
        "Required check paper-review-auditor is stale" in issue
        for issue in blocked.issues
    )
    assert blocked.inspection.run is not None
    assert blocked.inspection.run.status is RunStatus.BLOCKED


@pytest.mark.parametrize("workflow_name", EXECUTABLE_WORKFLOWS)
def test_validated_workflow_compiles_losslessly_into_the_run_contract(
    workflow_name: str,
    tmp_path: Path,
) -> None:
    workflow = load_workflow_definition(
        REPO_ROOT / "pipelines" / f"{workflow_name}.pipeline.md",
        repo_root=REPO_ROOT,
    )
    plan = plan_from_workflow(
        workflow,
        goal_id=f"goal-{workflow_name}",
        request="Exercise the declared contract",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    run_id = f"run-{workflow_name}"
    fixture = make_engine(
        plan,
        workspace=workspace,
        run_id=run_id,
    )
    create_run(fixture, plan, run_id=run_id)

    inspected = fixture.engine.inspect().run
    assert inspected is not None
    assert inspected.goal.workflow == workflow.name
    assert inspected.goal.target_artifacts == workflow.target_artifacts
    assert inspected.goal.required_checks == workflow.checks
    assert tuple(unit.plan.id for unit in inspected.units) == tuple(
        unit.id for unit in workflow.units
    )
    assert tuple(
        (
            unit.plan.skill,
            unit.plan.depends_on,
            unit.plan.inputs,
            unit.plan.outputs,
            unit.plan.owner.value,
        )
        for unit in inspected.units
    ) == tuple(
        (
            unit.skill,
            unit.depends_on,
            unit.inputs,
            unit.outputs,
            unit.owner,
        )
        for unit in workflow.units
    )
