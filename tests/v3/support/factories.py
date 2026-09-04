from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from research_harness.acceptance import (
    AcceptanceRequest,
    WorkflowAcceptancePolicy,
)
from research_harness.application import InMemoryArtifacts, InMemoryRunLedger
from research_harness.domain import (
    AcceptanceEvidence,
    Goal,
    HarnessRevision,
    Owner,
    RunPlan,
    UnitPlan,
)
from research_harness.engine import CreateLocalRun, LocalRunEngine
from research_harness.skills import InMemorySkillAdapter, SkillContext


class PassingSelfAttestingEvaluator:
    """Deterministic adapter used at the public acceptance seam."""

    def evaluate(self, request: AcceptanceRequest) -> AcceptanceEvidence:
        return AcceptanceEvidence(passed=True, checks=(request.unit.skill,))


@dataclass(frozen=True, slots=True)
class EngineFixture:
    engine: LocalRunEngine
    ledger: InMemoryRunLedger
    artifacts: InMemoryArtifacts
    run_id: str
    calls: list[str]


EngineSkillHandler = Callable[
    [SkillContext, InMemoryArtifacts, str, list[str]],
    int | None,
]


def revision(name: str = "current") -> HarnessRevision:
    return HarnessRevision(
        pipeline_digest=f"pipeline-{name}",
        kernel_digest=f"kernel-{name}",
    )


def make_engine(
    plan: RunPlan,
    *,
    workspace: Path,
    run_id: str,
    ledger: InMemoryRunLedger | None = None,
    artifacts: InMemoryArtifacts | None = None,
    harness_revision: HarnessRevision | None = None,
    handlers: Mapping[str, EngineSkillHandler] | None = None,
) -> EngineFixture:
    ledger = ledger or InMemoryRunLedger()
    artifacts = artifacts or InMemoryArtifacts()
    calls: list[str] = []
    acceptance = make_acceptance(plan)
    configured_handlers = dict(handlers or {})
    adapters: dict[str, InMemorySkillAdapter] = {}
    for unit in plan.units:
        if unit.owner is Owner.HUMAN or unit.skill == "human-checkpoint":
            continue
        if unit.skill in adapters:
            continue
        handler = configured_handlers.get(unit.skill, _write_declared_outputs)
        adapters[unit.skill] = InMemorySkillAdapter(
            handler=_bind_handler(
                handler,
                artifacts=artifacts,
                run_id=run_id,
                calls=calls,
            ),
            adapter=f"fixture:{unit.skill}",
        )
    return EngineFixture(
        engine=LocalRunEngine(
            workspace,
            ledger=ledger,
            artifacts=artifacts,
            skill_adapters=adapters,
            acceptance=acceptance,
            revision=harness_revision or revision(),
        ),
        ledger=ledger,
        artifacts=artifacts,
        run_id=run_id,
        calls=calls,
    )


def make_acceptance(plan: RunPlan) -> WorkflowAcceptancePolicy:
    evaluator = PassingSelfAttestingEvaluator()
    evaluators = {
        (plan.goal.workflow, skill): evaluator for skill in plan.goal.required_checks
    }
    return WorkflowAcceptancePolicy(evaluators=evaluators)


def create_run(fixture: EngineFixture, plan: RunPlan, *, run_id: str) -> None:
    if run_id != fixture.run_id:
        raise ValueError("Fixture and CreateLocalRun identities must match.")
    fixture.engine.execute(CreateLocalRun(run_id=run_id, plan=plan))


def _bind_handler(
    handler: EngineSkillHandler,
    *,
    artifacts: InMemoryArtifacts,
    run_id: str,
    calls: list[str],
) -> Callable[[SkillContext], int | None]:
    def invoke(context: SkillContext) -> int | None:
        calls.append(context.unit_id)
        return handler(context, artifacts, run_id, calls)

    return invoke


def _write_declared_outputs(
    context: SkillContext,
    artifacts: InMemoryArtifacts,
    run_id: str,
    calls: list[str],
) -> None:
    del calls
    for output in context.outputs:
        artifacts.put(run_id, output.as_posix(), f"created by {context.unit_id}")


def single_unit_plan(*, required: bool = False) -> RunPlan:
    skill = "paper-review-auditor" if required else "paper-review-writer"
    return RunPlan(
        goal=Goal(
            id="goal_review",
            request="Review the paper",
            workflow="paper-review",
            target_artifacts=("output/review.md",),
            required_checks=(skill,) if required else (),
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Review",
                skill=skill,
                outputs=("output/review.md",),
            ),
        ),
    )


def checkpoint_plan() -> RunPlan:
    return RunPlan(
        goal=Goal(
            id="goal_checkpoint",
            request="Approve a scope",
            workflow="research-brief",
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Write scope",
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


def required_check_plan() -> RunPlan:
    return RunPlan(
        goal=Goal(
            id="goal_freshness",
            request="Check then deliver",
            workflow="paper-review",
            target_artifacts=("report.md",),
            required_checks=("paper-review-auditor",),
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Produce source",
                skill="producer",
                outputs=("source.md",),
            ),
            UnitPlan(
                id="U020",
                title="Check source",
                skill="paper-review-auditor",
                depends_on=("U010",),
                inputs=("source.md",),
                outputs=("check.md",),
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


def approved_decision(checkpoint: str) -> str:
    return (
        f"- [x] Approve {checkpoint}\n"
        f"<!-- BEGIN CHECKPOINT:{checkpoint} -->\n"
        "approved review basis\n"
        f"<!-- END CHECKPOINT:{checkpoint} -->\n"
    )
