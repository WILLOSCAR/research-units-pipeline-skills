"""Decisions: the only place a human enters the Loop.

A Decision binds exactly what was reviewed, by hash. If a reviewed file
changes afterwards the Decision is stale and cannot be answered.
"""

from __future__ import annotations

from rh.kernel.evidence import sha256_file
from rh.kernel.kinds import Kind
from rh.kernel.records import BasisEntry, Decision, DecisionOutcome, Pass, Role, RunState, now
from rh.kernel.run import GOAL_FILE, PROOF_PACK_JSON, SPEC_FILE, Workspace

D0 = "D0"
D_FINAL = "D-final"
STOP_OPTIONS = [DecisionOutcome.EXTEND, DecisionOutcome.REVISE, DecisionOutcome.ABANDON]
REVIEW_OPTIONS = [DecisionOutcome.ACCEPT, DecisionOutcome.REJECT]


class DecisionError(ValueError):
    pass


# --- raise / resolve ------------------------------------------------------------


def raise_decision(state: RunState, base: str, prompt: str, basis: list[BasisEntry], options: list[DecisionOutcome]) -> Decision:
    """Append a fresh Decision ``base`` (``base-2``, ``base-3`` … when re-raised); stale any still pending."""
    for d in state.decisions:
        if d.pending:
            d.stale = True
    taken = {d.id for d in state.decisions}
    decision_id, n = base, 2
    while decision_id in taken:
        decision_id, n = f"{base}-{n}", n + 1
    decision = Decision(id=decision_id, prompt=prompt, basis=basis, options=options)
    state.decisions.append(decision)
    return decision


def resolve(
    state: RunState,
    decision: Decision,
    outcome: DecisionOutcome,
    *,
    reason: str | None = None,
    criterion: str | None = None,
    by: str | None = None,
) -> None:
    if decision.outcome is not None:
        raise DecisionError(f"{decision.id} was already answered ({decision.outcome.value})")
    if decision.stale:
        raise DecisionError(f"{decision.id} is stale: what it reviewed has changed; run `rh continue` first")
    if outcome not in decision.options:
        raise DecisionError(f"{decision.id} accepts only: {', '.join(o.value for o in decision.options)}")
    if outcome in (DecisionOutcome.REJECT, DecisionOutcome.REVISE) and not (reason or "").strip():
        raise DecisionError(f"{outcome.value} needs --reason")
    known = {c.id for c in state.spec.criteria} if state.spec else set()
    if criterion is not None and criterion not in known:
        raise DecisionError(f"unknown criterion {criterion!r}")
    decision.outcome, decision.reason, decision.criterion, decision.by, decision.at = outcome, reason, criterion, by, now()


# --- basis: what a Decision reviews, by hash -----------------------------------------


def spec_basis(state: RunState) -> list[BasisEntry]:
    basis = [BasisEntry(GOAL_FILE, state.goal.hash)]
    if state.spec_hash:
        basis.append(BasisEntry(SPEC_FILE, state.spec_hash))
    return basis


def artifact_basis(state: RunState, kind: Kind) -> list[BasisEntry]:
    names = {"deliverable": kind.deliverable, "statements": kind.statements, "proof_pack": PROOF_PACK_JSON}
    return [BasisEntry(names[key], state.artifact[key]) for key in names if key in state.artifact]


def outputs_basis(pass_: Pass) -> list[BasisEntry]:
    """A pass's outputs, named ``<pass>:<output>`` so they can never be confused with projections."""
    return [BasisEntry(f"{pass_.id}:{name}", digest) for name, digest in sorted(pass_.outputs.items())]


def latest_basis(state: RunState, step_id: str) -> list[BasisEntry]:
    """The latest outputs of ``step_id`` (a stop Decision's basis), or the spec basis if it has none yet."""
    for pass_ in reversed(state.passes_for(step_id)):
        if pass_.role is not Role.PROVER and pass_.outputs:
            return outputs_basis(pass_)
    return spec_basis(state)


def projections(kind: Kind) -> dict[str, str]:
    """Basis name → workspace-relative path of the projection a human might edit."""
    return {
        GOAL_FILE: GOAL_FILE,
        SPEC_FILE: SPEC_FILE,
        kind.deliverable: f"artifact/{kind.deliverable}",
        kind.statements: f"artifact/{kind.statements}",
        PROOF_PACK_JSON: f"artifact/{PROOF_PACK_JSON}",
    }


def changed_basis(ws: Workspace, decision: Decision, kind: Kind) -> list[str]:
    """Names in the basis whose projection on disk no longer matches the reviewed hash."""
    changed: list[str] = []
    for entry in decision.basis:
        rel = projections(kind).get(entry.name)
        if rel is None:
            continue
        path = ws.root / rel
        if not path.is_file() or sha256_file(path) != entry.hash:
            changed.append(entry.name)
    return changed


# --- projection --------------------------------------------------------------------------


def render(decision: Decision) -> str:
    """``decisions/<id>.md``: the prompt, what was reviewed by hash, and the answer once given."""
    lines = [f"# {decision.id}", "", decision.prompt, "", "Reviewed (by hash):", ""]
    lines += [f"- `{e.name}` {e.hash}" for e in decision.basis]
    lines += ["", f"Options: {', '.join(o.value for o in decision.options)}", ""]
    if decision.stale:
        lines.append("Stale: what this Decision reviewed has changed.")
    if decision.outcome is not None:
        lines.append(f"Answer: **{decision.outcome.value}**" + (f" ({decision.reason})" if decision.reason else ""))
        if decision.criterion:
            lines.append(f"Criterion: {decision.criterion}")
        lines.append(f"At: {decision.at}" + (f" by {decision.by}" if decision.by else ""))
    return "\n".join(lines) + "\n"
