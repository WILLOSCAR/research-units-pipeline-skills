"""Loop policy: after a failed verify, repair or stop.

Three reasons stop a Loop and none of them is silent: converged (every
bound gate passes), exhausted (budget spent, per-gate limit hit, or the
gate stopped improving), escalated (the agent or a human said stop).
"""

from __future__ import annotations

from rh.kernel.records import GateResult, RunState, Verdict


def exhaustion(state: RunState, step_id: str, gate_id: str) -> str | None:
    """Why the Loop is exhausted after ``gate_id`` failed on ``step_id``, or ``None`` if repair may go on."""
    budget = state.budget
    if state.passes_used >= budget.passes_total:
        return f"{state.passes_used} of {budget.passes_total} passes used"
    results = results_since_extension(state, step_id, gate_id)
    failures = sum(1 for r in results if r.verdict is Verdict.FAIL)
    if failures >= budget.passes_per_gate:
        return f"gate {gate_id!r} on step {step_id!r} failed {failures} times"
    if stalled(results, budget.stall_passes):
        return f"gate {gate_id!r} on step {step_id!r} stopped improving over {budget.stall_passes} passes"
    return None


def results_since_extension(state: RunState, step_id: str, gate_id: str) -> list[GateResult]:
    """Results for (step, gate) opened after the last budget extension."""
    order = {p.id: i for i, p in enumerate(state.passes)}
    return [
        r
        for r in state.gate_results
        if r.step == step_id and r.gate == gate_id and order.get(r.pass_id, -1) >= state.budget_epoch
    ]


def stalled(results: list[GateResult], window: int) -> bool:
    """The last ``window + 1`` results all failed and no score rose."""
    tail = results[-(window + 1) :]
    if len(tail) < window + 1 or any(r.verdict is Verdict.PASS for r in tail):
        return False
    scores = [r.score if r.score is not None else 0.0 for r in tail]
    return all(later <= earlier for earlier, later in zip(scores, scores[1:]))
