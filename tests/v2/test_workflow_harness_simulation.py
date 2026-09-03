from __future__ import annotations

from pathlib import Path

import pytest

from research_harness.application import (
    ApproveCheckpoint,
    BeginAttempt,
    CompleteAttempt,
    CreateRun,
    Harness,
    InMemoryAcceptance,
    InMemoryArtifacts,
    InMemoryRunLedger,
    ResultOutcome,
    plan_from_workflow,
)
from research_harness.domain import HarnessRevision, Owner, RunPlan, RunStatus
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


@pytest.mark.parametrize("workflow_name", EXECUTABLE_WORKFLOWS)
def test_declared_workflow_can_reach_completed_through_v2_interfaces(
    workflow_name: str,
) -> None:
    """Prove contract reachability, not the semantic quality of real Skills."""

    workflow = load_workflow_definition(
        REPO_ROOT / "pipelines" / f"{workflow_name}.pipeline.md",
        repo_root=REPO_ROOT,
    )
    plan = plan_from_workflow(
        workflow,
        goal_id=f"goal-{workflow_name}",
        request="Exercise the declared Workflow contract",
    )
    artifacts = InMemoryArtifacts()
    harness = Harness(
        ledger=InMemoryRunLedger(),
        artifacts=artifacts,
        acceptance=InMemoryAcceptance(),
        revision=HarnessRevision(
            pipeline_digest="pipeline-fixture",
            kernel_digest="kernel-fixture",
        ),
    )
    run_id = f"simulation-{workflow_name}"
    harness.execute(CreateRun(run_id=run_id, plan=plan))

    decisions = _approved_decisions(plan)
    artifacts.put(run_id, "DECISIONS.md", decisions)
    present = {"DECISIONS.md"}
    completed: set[str] = set()
    pending = list(plan.units)

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
        for raw_path in unit.inputs:
            path = raw_path.removeprefix("?")
            if path not in present:
                artifacts.put(run_id, path, f"fixture input: {path}")
                present.add(path)

        if unit.owner is Owner.HUMAN or unit.skill == "human-checkpoint":
            artifacts.put(run_id, "DECISIONS.md", decisions)
            harness.execute(
                ApproveCheckpoint(run_id=run_id, checkpoint=unit.checkpoint)
            )

        attempt = harness.execute(BeginAttempt(run_id=run_id, unit_id=unit.id))
        for raw_path in unit.outputs:
            path = raw_path.removeprefix("?")
            content = decisions if path == "DECISIONS.md" else f"{unit.id}: {path}"
            artifacts.put(run_id, path, content)
            present.add(path)
        _advance_declared_directory_projections(
            artifacts=artifacts,
            run_id=run_id,
            unit_id=unit.id,
            inputs=unit.all_input_paths,
            outputs=unit.all_output_paths,
            present=present,
        )

        result = harness.execute(
            CompleteAttempt(run_id=run_id, attempt_id=attempt.attempt_id)
        )
        assert result.outcome is ResultOutcome.COMMITTED, result.message
        completed.add(unit.id)
        pending.remove(unit)

    inspected = harness.inspect(run_id)
    assert inspected.status is RunStatus.COMPLETED
    assert len(inspected.completions) == len(plan.units)


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


def _advance_declared_directory_projections(
    *,
    artifacts: InMemoryArtifacts,
    run_id: str,
    unit_id: str,
    inputs: tuple[str, ...],
    outputs: tuple[str, ...],
    present: set[str],
) -> None:
    for directory in (path for path in inputs if path.endswith("/")):
        if any(output.startswith(directory) for output in outputs):
            artifacts.put(run_id, directory, f"{unit_id}: projection {directory}")
            present.add(directory)
