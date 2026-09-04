from __future__ import annotations

from research_harness.domain.errors import ErrorCode, HarnessError
from research_harness.domain.model import Goal, Owner, RunPlan, UnitPlan
from research_harness.workflows import WorkflowDefinition


def plan_from_workflow(
    workflow: WorkflowDefinition,
    *,
    goal_id: str,
    request: str,
) -> RunPlan:
    """Map one validated Workflow contract into the Harness domain plan.

    This application adapter keeps the domain independent of Pipeline parsing
    while preserving execution-relevant Unit fields and the Workflow success
    contract used to initialize a Goal.
    """

    units: list[UnitPlan] = []
    for unit in workflow.units:
        if unit.status.upper() != "TODO":
            raise HarnessError(
                ErrorCode.INVALID_COMMAND,
                f"Workflow Unit {unit.id} must start as TODO, not {unit.status!r}.",
                unit_id=unit.id,
            )
        try:
            owner = Owner(unit.owner)
        except ValueError as exc:
            raise HarnessError(
                ErrorCode.INVALID_COMMAND,
                f"Workflow Unit {unit.id} has unsupported owner {unit.owner!r}.",
                unit_id=unit.id,
            ) from exc
        units.append(
            UnitPlan(
                id=unit.id,
                title=unit.title,
                skill=unit.skill,
                workflow_type=unit.type,
                acceptance=unit.acceptance,
                depends_on=unit.depends_on,
                inputs=unit.inputs,
                outputs=unit.outputs,
                owner=owner,
                checkpoint=unit.checkpoint,
            )
        )

    success_criteria = tuple(
        f"required-artifact:{path}" for path in workflow.target_artifacts
    ) + tuple(f"required-check:{skill}" for skill in workflow.checks)
    goal = Goal(
        id=goal_id,
        request=request,
        workflow=workflow.name,
        constraints=(
            f"workflow-version:{workflow.version}",
            f"delivery-profile:{workflow.profile}",
            f"contract-model:{workflow.contract_model}",
        ),
        target_artifacts=workflow.target_artifacts,
        success_criteria=success_criteria,
        required_checks=workflow.checks,
    )
    return RunPlan(goal=goal, units=tuple(units))
