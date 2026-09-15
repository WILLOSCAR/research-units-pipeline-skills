"""Artifact: the deliverable, its statements, and the proof pack.

Everything here is assembled from Evidence bytes. The files under
``artifact/`` are projections the kernel writes and never reads back;
``reverify`` recomputes every recorded hash so a tampered object is found
rather than trusted.
"""

from __future__ import annotations

import json

import rh
from rh.kernel.evidence import EvidenceCorrupt, EvidenceStore, sha256_text
from rh.kernel.gates import parse_statements, result_text
from rh.kernel.kinds import Kind, KindError
from rh.kernel.records import (
    Criterion,
    Decision,
    DecisionOutcome,
    GateResult,
    Ground,
    Role,
    RunState,
    RunStatus,
    StepStatus,
    Verdict,
    encode,
)
from rh.kernel.run import PROOF_PACK_JSON, PROOF_PACK_MD, Workspace

PROOF_PACK_SCHEMA = "rh.proof_pack/1"


class ArtifactError(RuntimeError):
    """The Artifact cannot be assembled from the Run as it stands."""


# --- deliverable ------------------------------------------------------------


def deliverable(state: RunState, kind: Kind, strict: bool = True) -> dict[str, str]:
    """``{'deliverable': hash, 'statements': hash}`` from the artifact step's admitted pass.

    Strict: ``ArtifactError`` if the step is not admitted or an output is
    missing. Lenient (an abandoned Run): the step's latest pass supplies
    whatever it produced and missing outputs are left out.
    """
    try:
        step = state.plan.get(kind.artifact_step().id)
    except (KindError, KeyError) as exc:
        raise ArtifactError(f"the plan has no step producing {kind.deliverable!r}") from exc
    if step.status is StepStatus.ADMITTED and step.admitted_pass:
        outputs = state.get_pass(step.admitted_pass).outputs
    elif strict:
        raise ArtifactError(f"step {step.id!r} is not admitted; the Artifact cannot be assembled")
    else:
        passes = [p for p in state.passes_for(step.id) if p.role is not Role.PROVER]
        outputs = passes[-1].outputs if passes else {}
    hashes: dict[str, str] = {}
    for key, name in (("deliverable", kind.deliverable), ("statements", kind.statements)):
        if name in outputs:
            hashes[key] = outputs[name]
        elif strict:
            raise ArtifactError(f"the artifact step's admitted pass did not produce {name!r}")
    return hashes


# --- proof pack -------------------------------------------------------------


def proof_pack(state: RunState, kind: Kind, store: EvidenceStore) -> dict:
    """JSON-ready proof pack: the entries of PRODUCT_DESIGN § C7, from Evidence only.

    Integrity is recomputed from the store, never read from ``pass.status``.
    A Run whose deliverable is not yet (or never) admitted still gets a proof
    pack; the statements section then reports no hash.
    """
    hashes = deliverable(state, kind, strict=False)
    criteria = state.spec.criteria if state.spec else []
    return {
        "schema": PROOF_PACK_SCHEMA,
        "run_id": state.run_id,
        "kind": kind.kind,
        "goal": {"text": state.goal.text, "hash": state.goal.hash},
        "status": state.status.value,
        "stop": encode(state.stop),
        "spec": {"hash": state.spec_hash, "criteria": [_criterion_row(c) for c in criteria]},
        "decisions": [_decision_row(d) for d in state.decisions],
        "integrity": _integrity(state, store),
        "gates": [_gate_row(r) for r in state.gate_results],
        "criteria_coverage": [_coverage(state, c) for c in criteria],
        "statements": _statements(hashes.get("statements"), store),
        "loop": _loop(state),
        "identities": _identities(state),
        "evidence": _evidence_index(store),
    }


def _criterion_row(c: Criterion) -> dict:
    return {
        "id": c.id,
        "text": c.text,
        "kind": c.kind,
        "ground": c.ground.value,
        "layer": c.layer.value,
        "gates": list(c.gates),
    }


def _decision_row(d: Decision) -> dict:
    return {
        "id": d.id,
        "outcome": d.outcome.value if d.outcome else None,
        "reason": d.reason,
        "criterion": d.criterion,
        "by": d.by,
        "at": d.at,
        "stale": d.stale,
        "basis": encode(d.basis),
    }


def _integrity(state: RunState, store: EvidenceStore) -> dict:
    verified: list[str] = []
    broken: list[dict] = []
    for p in state.passes:
        bad = set(store.verify_all(list(p.outputs.values())))
        if bad:
            broken.extend({"pass_id": p.id, "output": n, "hash": h} for n, h in p.outputs.items() if h in bad)
        else:
            verified.append(p.id)
    return {"passes_verified": verified, "broken": broken, "ok": not broken}


def _gate_row(r: GateResult) -> dict:
    return {
        "gate": r.gate,
        "step": r.step,
        "pass_id": r.pass_id,
        "verdict": r.verdict.value,
        "score": r.score,
        "executor": r.executor.value,
        "kind": r.kind.value,
        "ground": r.ground.value,
        "calibration": dict(r.calibration),
        "produced_by": r.produced_by,
        "findings_count": len(r.findings),
        "criteria": list(r.criteria),
    }


def _coverage(state: RunState, c: Criterion) -> dict:
    served = [s.id for s in state.plan.active() if c.kind in s.serves]
    latest: dict[tuple[str, str], GateResult] = {}
    for r in state.gate_results:
        if c.id in r.criteria or r.gate in c.gates:
            latest[(r.gate, r.step)] = r
    results = [
        {"gate": r.gate, "step": r.step, "verdict": r.verdict.value, "pass_id": r.pass_id} for r in latest.values()
    ]
    satisfied: bool | None
    if c.ground is Ground.HUMAN:
        final = next((d for d in reversed(state.decisions) if d.id == "D-final" or d.id.startswith("D-final-")), None)
        if state.status in (RunStatus.RUNNING, RunStatus.BLOCKED) or final is None or final.stale or final.outcome is None:
            satisfied = None
        else:
            satisfied = final.outcome is DecisionOutcome.ACCEPT
    else:
        satisfied = bool(results) and all(r.verdict is Verdict.PASS for r in latest.values())
    return {
        "criterion": c.id,
        "ground": c.ground.value,
        "layer": c.layer.value,
        "served_by_steps": served,
        "latest_results": results,
        "satisfied": satisfied,
    }


def _statements(digest: str | None, store: EvidenceStore) -> dict:
    out: dict = {"hash": digest, "count": 0, "pointers_resolving": 0, "pointers_broken": 0, "problems": []}
    if digest is None:
        out["problems"].append("no statements output recorded")
        return out
    try:
        data = store.get(digest)
    except EvidenceCorrupt as exc:
        out["problems"].append(str(exc))
        return out
    statements, problems = parse_statements(data)
    out["count"] = len(statements)
    out["problems"] = problems
    for s in statements:
        for p in s.evidence:
            key = "pointers_resolving" if store.has(p.hash) else "pointers_broken"
            out[key] += 1
    return out


def _loop(state: RunState) -> dict:
    return {
        "passes_total": state.budget.passes_total,
        "passes_used": state.passes_used,
        "passes": [
            {"id": p.id, "step": p.step, "role": p.role.value, "gate": p.gate, "status": p.status.value}
            for p in state.passes
        ],
        "faults": [
            {
                "id": f.id,
                "gate": f.gate,
                "criterion": f.criterion,
                "step": f.step,
                "checked_step": f.checked_step,
                "resolved": f.resolved,
            }
            for f in state.faults
        ],
        "repairs": sum(1 for p in state.passes if p.role is Role.REPAIR),
    }


def _identities(state: RunState) -> dict:
    return {"steps": state.skill_identities(), "kernel": rh.__version__}


def _evidence_index(store: EvidenceStore) -> dict:
    hashes = sorted({e.hash for e in store.entries()})
    return {"count": len(hashes), "hashes": hashes}


# --- rendering --------------------------------------------------------------


def _short(digest: str | None) -> str:
    return digest[:12] if digest else "(none)"


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, (list, tuple)):
        return ", ".join(_cell(v) for v in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}={_cell(v)}" for k, v in value.items())
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(headers: list[str], rows: list[list[object]]) -> list[str]:
    if not rows:
        return ["(none)", ""]
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return lines + [""]


def _stop_line(stop: dict | None) -> str:
    if not stop:
        return "not stopped"
    parts = [stop["reason"]]
    if stop.get("pass_id"):
        parts.append(f"at pass {stop['pass_id']}")
    if stop.get("gate"):
        parts.append(f"on gate {stop['gate']}")
    return " ".join(parts)


def _quality_line(satisfied: bool | None) -> str:
    if satisfied is None:
        return "pending D-final"
    return "accepted at D-final" if satisfied else "rejected at D-final"


def render_proof_pack(pack: dict) -> str:
    """Readable Markdown for a proof pack: a heading per section, the three layers kept apart."""
    spec, integrity, statements, loop = pack["spec"], pack["integrity"], pack["statements"], pack["loop"]
    human = Ground.HUMAN.value
    contract = [c for c in pack["criteria_coverage"] if c["ground"] != human]
    quality = [c for c in pack["criteria_coverage"] if c["ground"] == human]
    lines = [
        f"# Proof pack: {pack['run_id']}",
        "",
        f"- Kind: {pack['kind']}",
        f"- Status: {pack['status']}",
        f"- Stop: {_stop_line(pack['stop'])}",
        f"- Goal hash: {_short(pack['goal']['hash'])}",
        "",
        "## Goal",
        "",
        pack["goal"]["text"].strip() or "(empty)",
        "",
        f"## Success Spec ({_short(spec['hash'])})",
        "",
        *_table(
            ["id", "kind", "ground", "layer", "gates", "text"],
            [[c["id"], c["kind"], c["ground"], c["layer"], c["gates"], c["text"]] for c in spec["criteria"]],
        ),
        "## Decisions",
        "",
        *_table(
            ["id", "outcome", "reason", "criterion", "by", "at", "stale", "basis"],
            [
                [
                    d["id"],
                    d["outcome"],
                    d["reason"],
                    d["criterion"],
                    d["by"],
                    d["at"],
                    d["stale"],
                    [f"{b['name']}@{_short(b['hash'])}" for b in d["basis"]],
                ]
                for d in pack["decisions"]
            ],
        ),
        "## Layer 1: execution integrity",
        "",
        f"- Record consistent: {_cell(integrity['ok'])}",
        f"- Passes verified: {_cell(integrity['passes_verified']) or '(none)'}",
        *[f"- Broken: pass {b['pass_id']} output {b['output']} ({_short(b['hash'])})" for b in integrity["broken"]],
        "",
        "## Layer 2: contract acceptance",
        "",
        *_table(
            ["gate", "step", "pass", "verdict", "score", "executor", "kind", "ground", "calibration", "findings"],
            [
                [
                    g["gate"],
                    g["step"],
                    g["pass_id"],
                    g["verdict"],
                    g["score"],
                    g["executor"],
                    g["kind"],
                    g["ground"],
                    g["calibration"].get("status"),
                    g["findings_count"],
                ]
                for g in pack["gates"]
            ],
        ),
        "Criteria coverage:",
        "",
        *_table(
            ["criterion", "ground", "served by", "latest results", "satisfied"],
            [
                [
                    c["criterion"],
                    c["ground"],
                    c["served_by_steps"],
                    [f"{r['gate']}@{r['pass_id']}={r['verdict']}" for r in c["latest_results"]],
                    c["satisfied"],
                ]
                for c in contract
            ],
        ),
        "## Layer 3: research quality",
        "",
        *([f"- {c['criterion']}: {_quality_line(c['satisfied'])}" for c in quality] or ["(no human-ground criteria)"]),
        "",
        "## Statement provenance",
        "",
        f"- Statements: {_short(statements['hash'])}, {statements['count']} statements",
        f"- Pointers resolving: {statements['pointers_resolving']}, broken: {statements['pointers_broken']}",
        *[f"- Problem: {p}" for p in statements.get("problems", [])],
        "",
        "## Loop trace",
        "",
        f"- Passes: {loop['passes_used']} of {loop['passes_total']} used, {loop['repairs']} repairs",
        "",
        *_table(
            ["pass", "step", "role", "gate", "status"],
            [[p["id"], p["step"], p["role"], p["gate"], p["status"]] for p in loop["passes"]],
        ),
        *_table(
            ["fault", "gate", "criterion", "step", "checked step", "resolved"],
            [[f["id"], f["gate"], f["criterion"], f["step"], f["checked_step"], f["resolved"]] for f in loop["faults"]],
        ),
        "## Identities",
        "",
        *_table(["step", "skill identity"], [[s, h] for s, h in pack["identities"]["steps"].items()]),
        f"Kernel: rh {pack['identities']['kernel']}",
        "",
        "## Evidence index",
        "",
        f"{pack['evidence']['count']} objects",
        "",
        *[f"- `{h}`" for h in pack["evidence"]["hashes"]],
    ]
    return "\n".join(lines).rstrip() + "\n"


# --- assembly ---------------------------------------------------------------


def assemble(ws: Workspace, state: RunState, kind: Kind) -> dict[str, str]:
    """Build the Artifact for the current state and return its hashes.

    The deliverable and statements come from the artifact step's admitted
    pass (``deliverable_hashes``). The proof pack is written to Evidence as
    ``proof_pack.json`` and ``proof_pack.md`` (produced_by ``kernel``), and
    all four are projected under ``ws.artifact/``.

    For an abandoned Run the artifact step need not be admitted: the latest
    pass of that step supplies whatever it produced (a missing deliverable
    or statements is left out of the result) and the proof pack is still
    written, so the Run ends with a record of how it stopped.

    Does not mutate or commit ``state``; the caller stores the returned dict
    into ``state.artifact`` inside its own transaction.
    """
    hashes = deliverable(state, kind, strict=state.status is not RunStatus.ABANDONED)
    pack = proof_pack(state, kind, ws.evidence)
    pack_json = json.dumps(pack, indent=2, ensure_ascii=False)
    hashes["proof_pack"] = ws.evidence.put_text(pack_json, PROOF_PACK_JSON, "kernel").hash
    hashes["proof_pack_md"] = ws.evidence.put_text(render_proof_pack(pack), PROOF_PACK_MD, "kernel").hash
    names = {
        "deliverable": kind.deliverable,
        "statements": kind.statements,
        "proof_pack": PROOF_PACK_JSON,
        "proof_pack_md": PROOF_PACK_MD,
    }
    for key, digest in hashes.items():
        ws.evidence.link_into(digest, ws.artifact / names[key])
    return hashes


def reverify(ws: Workspace, state: RunState) -> list[str]:
    """Recompute every hash in ``state.artifact``, every pass output and every gate result; return the problems."""
    store = ws.evidence
    broken = "does not resolve or match its hash"
    problems = [
        f"artifact {name}: evidence {digest[:12]} {broken}" for name, digest in state.artifact.items() if store.verify_all([digest])
    ]
    problems += [f"pass {b['pass_id']} output {b['output']}: evidence {b['hash'][:12]} {broken}" for b in _integrity(state, store)["broken"]]
    for r in state.gate_results:
        if r.hash and store.verify_all([r.hash]):
            problems.append(f"gate result {r.pass_id}/{r.gate}: evidence {r.hash[:12]} {broken}")
        projection = ws.gates / f"{r.pass_id}.{r.gate}.json"
        if projection.is_file() and sha256_text(result_text(json.loads(projection.read_text(encoding="utf-8")))) != r.hash:
            problems.append(f"gate result projection {projection.name} was edited; the recorded result stands")
    return problems
