from __future__ import annotations

from pathlib import Path

import pytest

from research_harness.application import InMemoryAcceptance, plan_from_workflow
from research_harness.domain import HarnessRevision, Owner, RunPlan, RunStatus
from research_harness.engine import (
    AdvanceRun,
    ApproveLocalCheckpoint,
    CreateLocalRun,
    EngineOutcome,
    LocalRunEngine,
)
from research_harness.skills import InMemorySkillAdapter, SkillContext
from research_harness.workflows import load_workflow_definition


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
REVISION = HarnessRevision(
    pipeline_digest="durable-workflow-simulation",
    kernel_digest="durable-workflow-simulation",
)


@pytest.mark.parametrize("workflow_name", EXECUTABLE_WORKFLOWS)
def test_workflow_reaches_completion_across_filesystem_restarts(
    workflow_name: str,
    tmp_path: Path,
) -> None:
    """Prove durable contract reachability, not real Skill research quality."""

    workflow = load_workflow_definition(
        REPO_ROOT / "pipelines" / f"{workflow_name}.pipeline.md",
        repo_root=REPO_ROOT,
    )
    plan = plan_from_workflow(
        workflow,
        goal_id=f"goal-{workflow_name}",
        request="Exercise durable next-engine contract reachability",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    run_id = f"durable-{workflow_name}"
    adapters = _adapters(plan, workspace=workspace)
    _engine(workspace, adapters).execute(CreateLocalRun(plan=plan, run_id=run_id))

    decisions = _approved_decisions(plan)
    completed: set[str] = set()
    pending = list(plan.units)
    restart_count = 0
    while pending:
        unit = next(
            (
                candidate
                for candidate in pending
                if set(candidate.depends_on) <= completed
            ),
            None,
        )
        assert unit is not None, "validated Workflow DAG must remain schedulable"
        _seed_required_inputs(workspace, unit.required_inputs, decisions=decisions)
        engine = _engine(workspace, adapters)
        restart_count += 1
        if unit.owner is Owner.HUMAN or unit.skill == "human-checkpoint":
            (workspace / "DECISIONS.md").write_text(decisions, encoding="utf-8")
            approved = engine.execute(
                ApproveLocalCheckpoint(checkpoint=unit.checkpoint)
            )
            assert approved.outcome is EngineOutcome.APPROVED

        result = engine.execute(AdvanceRun(unit_id=unit.id))
        assert result.outcome in {EngineOutcome.ADVANCED, EngineOutcome.COMPLETED}, (
            workflow_name,
            unit.id,
            result.issues,
        )
        completed.add(unit.id)
        pending.remove(unit)

    inspected = _engine(workspace, adapters).inspect().run
    assert inspected is not None
    assert inspected.status is RunStatus.COMPLETED
    assert len(inspected.completions) == len(plan.units)
    assert restart_count == len(plan.units)
    assert (workspace / ".harness-v3" / "state.json").is_file()
    assert len(tuple((workspace / ".harness-v3" / "manifests").glob("*.json"))) == len(
        plan.units
    )


def _engine(
    workspace: Path,
    adapters: dict[str, InMemorySkillAdapter],
) -> LocalRunEngine:
    return LocalRunEngine.for_workspace(
        workspace,
        skill_adapters=adapters,
        acceptance=InMemoryAcceptance(),
        revision=REVISION,
    )


def _adapters(
    plan: RunPlan,
    *,
    workspace: Path,
) -> dict[str, InMemorySkillAdapter]:
    units = {unit.id: unit for unit in plan.units}

    def materialize(context: SkillContext) -> None:
        unit = units[context.unit_id]
        for raw_path in unit.all_output_paths:
            path = workspace / raw_path
            path.parent.mkdir(parents=True, exist_ok=True)
            content = (
                _approved_decisions(plan)
                if raw_path == "DECISIONS.md"
                else f"{unit.id} materialized {raw_path}\n"
            )
            path.write_text(content, encoding="utf-8")

    return {
        skill: InMemorySkillAdapter(
            handler=materialize,
            adapter=f"durable-fixture:{skill}",
        )
        for skill in dict.fromkeys(unit.skill for unit in plan.units)
        if skill != "human-checkpoint"
    }


def _seed_required_inputs(
    workspace: Path,
    inputs: tuple[str, ...],
    *,
    decisions: str,
) -> None:
    for raw_path in inputs:
        if raw_path.endswith("/"):
            (workspace / raw_path).mkdir(parents=True, exist_ok=True)
            continue
        path = workspace / raw_path
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            decisions if raw_path == "DECISIONS.md" else f"fixture input {raw_path}\n",
            encoding="utf-8",
        )


def _approved_decisions(plan: RunPlan) -> str:
    checkpoints = sorted({unit.checkpoint for unit in plan.units if unit.checkpoint})
    return (
        "\n".join(
            f"- [x] Approve {checkpoint}\n"
            f"<!-- BEGIN CHECKPOINT:{checkpoint} -->\n"
            f"approved {checkpoint}\n"
            f"<!-- END CHECKPOINT:{checkpoint} -->"
            for checkpoint in checkpoints
        )
        + "\n"
    )
