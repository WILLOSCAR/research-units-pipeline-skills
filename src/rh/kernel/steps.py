"""Passes and packets: how the harness hands work to the agent and takes it back.

Opening a Pass materialises its inputs from Evidence and writes a packet.
Closing a Pass hashes every declared output into Evidence; a missing or
empty output is an integrity failure, not a matter of opinion.
"""

from __future__ import annotations

import json

from rh.kernel.kinds import Kind
from rh.kernel.records import Criterion, Fault, GateDecl, Pass, Role, RunState, Step, StepStatus, encode, now
from rh.kernel.run import GATE_RESULT_FILE, GOAL_FILE, SPEC_FILE, Workspace
from rh.kernel.skills import Skill

PACKET_SCHEMA = "rh.packet/1"


def is_dir_output(name: str) -> bool:
    return name.endswith("/")


class InputsUnavailable(RuntimeError):
    pass


# --- inputs ---------------------------------------------------------------


def available_hashes(state: RunState, name: str) -> dict[str, str]:
    """Current Evidence for one consumed name: ``{relative name: hash}``.

    Files map to one entry; directory outputs (``sources/``) map to every
    file the admitted producer wrote under them.
    """
    if name == GOAL_FILE:
        return {GOAL_FILE: state.goal.hash}
    if name == SPEC_FILE and state.spec_hash:
        return {SPEC_FILE: state.spec_hash}
    producers = state.plan.producers_of(name)
    if not producers and any(name in s.produces for s in state.plan.steps if s.status is StepStatus.SKIPPED):
        return {}  # every producer was skipped: the input is absent, not pending
    for step in reversed(producers):
        if step.admitted_pass is None:
            continue
        outputs = state.get_pass(step.admitted_pass).outputs
        if is_dir_output(name):
            return {k: v for k, v in outputs.items() if k.startswith(name)}
        if name in outputs:
            return {name: outputs[name]}
    raise InputsUnavailable(f"no admitted step produces {name!r}")


def inputs_for(state: RunState, step: Step) -> list[tuple[str, str]]:
    """``(relative name, hash)`` of every input a pass on ``step`` is given, in packet order.

    The Success Spec joins every step after ``spec`` once D0 has bound it.
    """
    consumed = list(step.consumes)
    if SPEC_FILE not in consumed and state.spec_hash and step.id != "spec":
        consumed.append(SPEC_FILE)
    return [pair for name in consumed for pair in sorted(available_hashes(state, name).items())]


def inputs_ready(state: RunState, step: Step) -> bool:
    try:
        inputs_for(state, step)
    except InputsUnavailable:
        return False
    return True


def given_hashes(state: RunState, pass_: Pass) -> set[str]:
    """Every hash a pass was handed: its inputs, the outputs it checks (prover), the Evidence its Faults cite (repair).

    Recomputed from state, never read back from the packet, so what a
    statement or finding may cite does not depend on a projection.
    """
    given = {digest for _, digest in inputs_for(state, state.plan.get(pass_.step))}
    if pass_.checked:
        given |= set(state.get_pass(pass_.checked).outputs.values())
    if pass_.role is Role.REPAIR:
        given |= repair_evidence(state, pass_, [f for f in state.faults if f.id in pass_.faults])
    return given


def repair_evidence(state: RunState, pass_: Pass, faults: list[Fault]) -> set[str]:
    """Cited Evidence excluding every earlier output of the step being repaired.

    Bound by pass number so closing this repair cannot change what it was
    given. Faults retain their original references for audit and routing.
    """
    prior = {h for p in state.passes_for(pass_.step) if p.n < pass_.n for h in p.outputs.values()}
    return {h for f in faults for h in f.evidence} - prior


# --- open / close -----------------------------------------------------------


def open_pass(
    ws: Workspace,
    state: RunState,
    kind: Kind,
    step: Step,
    skill: Skill,
    role: Role,
    criteria: list[Criterion],
    *,
    gate: GateDecl | None = None,
    checked: Pass | None = None,
    faults: list[Fault] = (),
) -> Pass:
    n = len(state.passes_for(step.id)) + 1
    pass_ = Pass(
        id=f"{step.id}#{n}",
        step=step.id,
        n=n,
        role=role,
        gate=gate.id if gate else None,
        checked=checked.id if checked else None,
        faults=[f.id for f in faults],
        skill_identity=skill.identity,
    )
    root = ws.pass_dir(pass_.id)
    (root / "inputs").mkdir(parents=True, exist_ok=True)
    (root / "outputs").mkdir(parents=True, exist_ok=True)

    given = inputs_for(state, step)
    if checked is not None:
        given += sorted(checked.outputs.items())
    inputs = [_materialise(ws, pass_, rel, digest) for rel, digest in given]
    cited: list[dict] = []
    if role is Role.REPAIR:
        # Fresh context: the Faults and the Evidence they cite, never the failed attempt itself.
        for digest in sorted(repair_evidence(state, pass_, faults)):
            if ws.evidence.has(digest):
                cited.append(_materialise(ws, pass_, f"evidence/{digest[:16]}", digest))
        (root / "inputs" / "faults.json").write_text(
            json.dumps([encode(f) for f in faults], indent=2, ensure_ascii=False), encoding="utf-8"
        )

    outputs = [GATE_RESULT_FILE] if role is Role.PROVER else list(step.produces)
    if role is not Role.PROVER:
        state.passes_used += 1  # verification passes are not budgeted
    packet = {
        "schema": PACKET_SCHEMA,
        "run_id": state.run_id,
        "kind": kind.kind,
        "pass_id": pass_.id,
        "step": step.id,
        "n": n,
        "role": role.value,
        "skill": {"name": skill.name, "path": str(skill.path), "identity": skill.identity},
        "goal": {"text": state.goal.text, "constraints": state.goal.constraints},
        "criteria": [encode(c) for c in criteria],
        "inputs": inputs,
        "outputs": [{"name": o, "path": f"outputs/{o}"} for o in outputs],
        "budget": {
            "passes_used": state.passes_used,
            "passes_total": state.budget.passes_total,
            "passes_per_gate": state.budget.passes_per_gate,
        },
        "opened_at": now(),
    }
    if gate is not None and checked is not None:
        packet["gate"] = {
            "id": gate.id,
            "kind": gate.kind.value,
            "ground": gate.ground.value,
            "serves": gate.serves,
            "checked_pass": checked.id,
            "checked_step": checked.step,
            "result_path": f"outputs/{GATE_RESULT_FILE}",
        }
    if role is Role.REPAIR:
        packet["faults"] = [encode(f) for f in faults]
        packet["cited_evidence"] = cited
    packet["instructions"] = _instructions(role)

    (root / "packet.json").write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
    (root / "packet.md").write_text(render_packet(packet), encoding="utf-8")

    state.passes.append(pass_)
    state.pending_pass = pass_.id
    ws.log("pass.opened", pass_id=pass_.id, role=role.value, gate=pass_.gate, skill=skill.name)
    return pass_


def close_pass(ws: Workspace, state: RunState, pass_: Pass, declared: list[str]) -> list[str]:
    """Hash every declared output into Evidence. Returns integrity problems."""
    root = ws.pass_dir(pass_.id) / "outputs"
    problems: list[str] = []
    outputs: dict[str, str] = {}
    for name in declared:
        path = root / name
        if is_dir_output(name):
            files = sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else []
            if not files:
                problems.append(f"declared output {name!r} is missing or empty")
            for file in files:
                rel = f"{name}{file.relative_to(path).as_posix()}"
                outputs[rel] = ws.evidence.put_file(file, rel, pass_.id).hash
        elif not path.is_file() or path.stat().st_size == 0:
            problems.append(f"declared output {name!r} is missing or empty")
        else:
            outputs[name] = ws.evidence.put_file(path, name, pass_.id).hash
    pass_.outputs = outputs
    pass_.closed_at = now()
    ws.log("pass.closed", pass_id=pass_.id, outputs=len(outputs), problems=problems)
    return problems


def output_bytes(ws: Workspace, pass_: Pass) -> dict[str, bytes]:
    return {name: ws.evidence.get(digest) for name, digest in pass_.outputs.items()}


# --- helpers ----------------------------------------------------------------


def _materialise(ws: Workspace, pass_: Pass, name: str, digest: str) -> dict:
    ws.evidence.link_into(digest, ws.pass_dir(pass_.id) / "inputs" / name)
    return {"name": name, "path": f"inputs/{name}", "hash": digest}


def _instructions(role: Role) -> str:
    base = (
        "Read the Skill at skill.path and follow it. Read inputs from the listed paths. "
        "Write every declared output under outputs/ with exactly the declared name, then run `rh continue`."
    )
    if role is Role.PROVER:
        return (
            "You are the prover for one gate. Judge the checked pass's outputs against the listed criteria "
            "using only the Evidence in inputs/. Never read or trust a verdict written by the producer. "
            "Write outputs/gate_result.json (schema rh.gate_result/1); a failing verdict must cite Evidence. "
            "Then run `rh continue`."
        )
    if role is Role.REPAIR:
        return (
            "This is a repair pass in a fresh context: you are given the Faults and the Evidence they cite, "
            "not the failed attempt. Produce the outputs anew from the inputs so that each Fault is answered. " + base
        )
    return base


def render_packet(packet: dict) -> str:
    lines = [
        f"# Packet {packet['pass_id']} ({packet['role']})",
        "",
        f"Run `{packet['run_id']}` · kind `{packet['kind']}` · step `{packet['step']}` · pass {packet['n']}",
        f"Skill: `{packet['skill']['name']}` — {packet['skill']['path']}",
        "",
        "## Goal",
        "",
        packet["goal"]["text"].strip(),
        "",
    ]
    if packet.get("gate"):
        g = packet["gate"]
        lines += [
            "## Gate",
            "",
            f"`{g['id']}` ({g['kind']}, ground {g['ground']}) on pass `{g['checked_pass']}` of step `{g['checked_step']}`.",
            f"Write the result to `{g['result_path']}`.",
            "",
        ]
    if packet["criteria"]:
        lines += ["## Criteria", ""]
        for c in packet["criteria"]:
            lines.append(f"- **{c['id']}** [{c['kind']}, {c['ground']}] {c['text']}")
        lines.append("")
    if packet.get("faults"):
        lines += ["## Faults to repair", ""]
        for f in packet["faults"]:
            crit = f" ({f['criterion']})" if f.get("criterion") else ""
            lines.append(f"- **{f['id']}** gate `{f['gate']}`{crit}: {f['message']}")
        lines.append("")
    lines += ["## Inputs", ""]
    for i in packet["inputs"]:
        lines.append(f"- `{i['path']}` ({i['hash'][:12]})")
    if packet.get("cited_evidence"):
        lines += ["", "Evidence the Faults cite:", ""]
        for i in packet["cited_evidence"]:
            lines.append(f"- `{i['path']}` ({i['hash'][:12]})")
    lines += ["", "## Outputs to write", ""]
    for o in packet["outputs"]:
        lines.append(f"- `{o['path']}`")
    b = packet["budget"]
    lines += [
        "",
        f"Budget: {b['passes_used']} of {b['passes_total']} passes used; {b['passes_per_gate']} per gate.",
        "",
        "## Instructions",
        "",
        packet["instructions"],
        "",
    ]
    return "\n".join(lines)
