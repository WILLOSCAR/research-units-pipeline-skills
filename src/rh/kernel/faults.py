"""Faults: a failed verify, named by gate, criterion, ground, and the step to repair.

Routing decides which step a repair pass reopens. The default is the step
that was checked; a prover may implicate an upstream step only when it
cites Evidence that step produced.
"""

from __future__ import annotations

from rh.kernel.evidence import EvidenceStore
from rh.kernel.records import Fault, Finding, GateDecl, GateResult, Ground, RunState

INTEGRITY_GATE = "integrity"
SPEC_GATE = "spec-valid"
HUMAN_GATE = "decision"


def fault(
    state: RunState,
    gate: str,
    step: str,
    message: str,
    *,
    ground: Ground = Ground.COMPUTATION,
    criterion: str | None = None,
    checked_step: str | None = None,
    evidence: list[str] = (),
    pass_id: str = "",
    offset: int = 0,
) -> Fault:
    """A new Fault numbered after those the Run holds (plus ``offset`` siblings not yet appended)."""
    return Fault(
        id=f"F{len(state.faults) + offset + 1:03d}",
        gate=gate,
        criterion=criterion,
        ground=ground,
        step=step,
        checked_step=checked_step or step,
        message=message,
        evidence=list(evidence),
        pass_id=pass_id,
        budget_remaining=max(0, state.budget.passes_total - state.passes_used),
    )


def from_result(state: RunState, store: EvidenceStore, result: GateResult, decl: GateDecl) -> list[Fault]:
    """One Fault per finding, each routed on its own; a finding-less failure yields one Fault."""
    default = result.criteria[0] if result.criteria else None
    findings = result.findings or [Finding(f"gate {result.gate} failed on {result.pass_id}")]
    return [
        fault(
            state,
            result.gate,
            route(state, store, result, decl, finding),
            finding.message,
            ground=result.ground,
            criterion=finding.criterion or default,
            checked_step=result.step,
            evidence=finding.evidence,
            pass_id=result.pass_id,
            offset=i,
        )
        for i, finding in enumerate(findings)
    ]


def route(state: RunState, store: EvidenceStore, result: GateResult, decl: GateDecl, finding: Finding) -> str:
    """The step a finding sends repair to.

    ``checked_step`` routing always names the checked step. Under
    ``upstream_of_cited_evidence`` a finding may implicate an upstream step,
    honored only when that step produced some Evidence the finding cites.
    """
    if decl.routing != "upstream_of_cited_evidence":
        return result.step
    target = finding.implicates
    if target is None or target not in {s.id for s in state.plan.upstream(result.step)}:
        return result.step
    if any(_producing_step(store, h) == target for h in finding.evidence):
        return target
    return result.step


def _producing_step(store: EvidenceStore, digest: str) -> str | None:
    producer = store.producer_of(digest)
    if producer is None or "#" not in producer:
        return None
    return producer.split("#", 1)[0]


def earliest_step(state: RunState, step_ids: list[str]) -> str:
    order = {s.id: i for i, s in enumerate(state.plan.steps)}
    return min(step_ids, key=lambda s: order[s])
