"""The outer loop: Lessons distilled from ended Runs, evolves verified by replay.

A Lesson belongs to the project. It records what failed, against which
ground, which step owned it, what repair did, and how the Loop stopped, and
it carries the Evidence bytes needed to replay each failing gate. An evolve
cites Lessons and is adopted only after replay shows every cited Fault is
caught; agent gates need a human attestation, since the kernel cannot re-run
them.

Layout under the project root::

    lessons/<run-id>.json
    lessons/<run-id>/evidence/          replay bundle (an EvidenceStore)
    evolve/<evolve-id>/proposal.json
    evolve/<evolve-id>/replay.json
"""

from __future__ import annotations

import json
import re
import secrets
from itertools import pairwise
from pathlib import Path

from rh.kernel.evidence import EvidenceCorrupt, EvidenceStore
from rh.kernel.gates import KERNEL_GATES, GateContext, parse_statements
from rh.kernel.kinds import Kind
from rh.kernel.records import (
    Criterion,
    Executor,
    GateResult,
    Pass,
    Role,
    RunState,
    Step,
    Verdict,
    decode,
    encode,
    now,
)
from rh.kernel.run import Workspace, write_json
from rh.kernel.skills import Skill

LESSON_SCHEMA = "rh.lesson/1"
EVOLVE_SCHEMA = "rh.evolve/1"
REPLAY_SCHEMA = "rh.evolve_replay/1"


# --- paths and files --------------------------------------------------------


def lesson_path(project: Path, run_id: str) -> Path:
    return project / "lessons" / f"{run_id}.json"


def bundle_store(project: Path, run_id: str) -> EvidenceStore:
    return EvidenceStore(project / "lessons" / run_id / "evidence")


def _proposal_path(project: Path, evolve_id: str) -> Path:
    return project / "evolve" / evolve_id / "proposal.json"


def _replay_path(project: Path, evolve_id: str) -> Path:
    return project / "evolve" / evolve_id / "replay.json"


def _read_json(path: Path, what: str) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"no {what} at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# --- Lessons ----------------------------------------------------------------


def distill(ws: Workspace, state: RunState, kind: Kind, project: Path | None = None) -> Path:
    """Write ``<project>/lessons/<run-id>.json`` and its replay bundle; return the json path.

    ``project`` defaults to the workspace's parent. Idempotent: distilling the
    same Run again overwrites the Lesson and completes the bundle.
    """
    project = project or ws.root.parent
    failing = [r for r in state.gate_results if r.verdict is Verdict.FAIL]
    per_gate: dict[str, int] = {}
    for r in failing:
        key = f"{r.step}/{r.gate}"
        per_gate[key] = per_gate.get(key, 0) + 1
    lesson = {
        "schema": LESSON_SCHEMA,
        "run_id": state.run_id,
        "kind": state.kind,
        "goal_hash": state.goal.hash,
        "spec_hash": state.spec_hash,
        "status": state.status.value,
        "stop": encode(state.stop),
        "faults": [
            {
                "id": f.id,
                "gate": f.gate,
                "criterion": f.criterion,
                "ground": f.ground.value,
                "step": f.step,
                "checked_step": f.checked_step,
                "message": f.message,
                "evidence": list(f.evidence),
                "pass_id": f.pass_id,
                "resolved": f.resolved,
            }
            for f in state.faults
        ],
        "gate_failures": [_failure_row(r) for r in failing],
        "repairs": _repairs(state),
        "decisions": [
            {
                "id": d.id,
                "outcome": d.outcome.value if d.outcome else None,
                "reason": d.reason,
                "criterion": d.criterion,
                "stale": d.stale,
            }
            for d in state.decisions
        ],
        "budget": {
            "passes_total": state.budget.passes_total,
            "passes_used": state.passes_used,
            "per_gate_failures": per_gate,
        },
        "stall": stall_series(state),
        "skill_identities": state.skill_identities(),
        "artifact": dict(state.artifact),
        "kind_deliverable": kind.deliverable,
        "kind_statements": kind.statements,
        "spec_criteria": encode(state.spec.criteria) if state.spec else [],
        "replay": {
            "gates": [_replay_entry(state, r) for r in failing],
            "evidence_dir": f"{state.run_id}/evidence",
        },
        "at": now(),
    }
    _write_bundle(ws.evidence, state, kind, failing, bundle_store(project, state.run_id))
    path = lesson_path(project, state.run_id)
    write_json(path, lesson)
    return path


def _failure_row(r: GateResult) -> dict:
    return {
        "gate": r.gate,
        "step": r.step,
        "pass_id": r.pass_id,
        "verdict": r.verdict.value,
        "score": r.score,
        "executor": r.executor.value,
        "kind": r.kind.value,
        "ground": r.ground.value,
        "produced_by": r.produced_by,
        "findings": encode(r.findings),
    }


def _repairs(state: RunState) -> list[dict]:
    faults = {f.id: f for f in state.faults}
    out: list[dict] = []
    for p in state.passes:
        if p.role is not Role.REPAIR:
            continue
        answered = [faults[i] for i in p.faults if i in faults]
        out.append(
            {
                "pass_id": p.id,
                "step": p.step,
                "faults": list(p.faults),
                "resolved": bool(answered) and all(f.resolved for f in answered),
            }
        )
    return out


def _replay_entry(state: RunState, r: GateResult) -> dict:
    return {
        "gate": r.gate,
        "step": r.step,
        "pass_id": r.pass_id,
        "executor": r.executor.value,
        "outputs": dict(state.get_pass(r.pass_id).outputs),
        "criteria": list(r.criteria),
    }


def _safe_get(store: EvidenceStore, digest: str) -> bytes | None:
    try:
        return store.get(digest)
    except EvidenceCorrupt:
        return None


def _write_bundle(
    store: EvidenceStore, state: RunState, kind: Kind, failing: list[GateResult], bundle: EvidenceStore
) -> None:
    """Copy into the bundle every byte a replay of the failing gates needs.

    That is: the outputs of each failing pass, the Evidence its findings cite,
    the Evidence its statements point to, and the Artifact. Bytes the store
    cannot produce are skipped; replay reports the gap.
    """
    wanted: dict[str, str] = {digest: name for name, digest in state.artifact.items()}
    for r in failing:
        for f in r.findings:
            wanted.update({h: "finding" for h in f.evidence})
        outputs = state.get_pass(r.pass_id).outputs
        wanted.update({h: n for n, h in outputs.items()})
        statements_hash = outputs.get(kind.statements)
        data = _safe_get(store, statements_hash) if statements_hash else None
        if data is not None:
            statements, _ = parse_statements(data)
            wanted.update({p.hash: "pointer" for s in statements for p in s.evidence})
    bundle.init()
    for digest, name in sorted(wanted.items()):
        if bundle.has(digest):
            continue
        data = _safe_get(store, digest)
        if data is not None:
            bundle.put_bytes(data, name, state.run_id)


def stall_series(state: RunState) -> list[dict]:
    """Per (step, gate) with >= 3 failing results, the score series when it never improved."""
    series: dict[tuple[str, str], list[float | None]] = {}
    for r in state.gate_results:
        if r.verdict is Verdict.FAIL:
            series.setdefault((r.step, r.gate), []).append(r.score)
    return [
        {"step": step, "gate": gate, "scores": scores}
        for (step, gate), scores in series.items()
        if len(scores) >= 3 and not _improved(scores)
    ]


def _improved(scores: list[float | None]) -> bool:
    return any(a is not None and b is not None and b > a for a, b in pairwise(scores))


def list_lessons(project: Path) -> list[dict]:
    """One summary per Lesson, oldest first."""
    out: list[dict] = []
    for path in sorted((project / "lessons").glob("*.json")):
        lesson = json.loads(path.read_text(encoding="utf-8"))
        out.append(
            {
                "run_id": lesson["run_id"],
                "kind": lesson["kind"],
                "status": lesson["status"],
                "stop": (lesson.get("stop") or {}).get("reason"),
                "faults": len(lesson.get("faults", [])),
                "gate_failures": len(lesson.get("gate_failures", [])),
                "at": lesson.get("at", ""),
            }
        )
    return sorted(out, key=lambda s: s["at"])


def load_lesson(project: Path, run_id: str) -> dict:
    return _read_json(lesson_path(project, run_id), f"Lesson for Run {run_id!r}")


# --- evolve -----------------------------------------------------------------


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "evolve"


def propose(project: Path, target: str, lesson_ids: list[str], rationale: str, by: str | None = None) -> str:
    """Record an evolve proposal citing existing Lessons; return its id.

    ``target`` names what changes, e.g. ``gate:source-support``, ``kind:brief``,
    ``skill:brief-writer``. Every cited Lesson must exist, else ``ValueError``.
    """
    if not lesson_ids:
        raise ValueError("an evolve must cite at least one Lesson")
    for run_id in lesson_ids:
        try:
            load_lesson(project, run_id)
        except FileNotFoundError as exc:
            raise ValueError(f"unknown Lesson {run_id!r}") from exc
    evolve_id = f"{_slug(target)}-{secrets.token_hex(3)}"
    proposal = {
        "schema": EVOLVE_SCHEMA,
        "id": evolve_id,
        "target": target,
        "lessons": list(lesson_ids),
        "rationale": rationale,
        "by": by,
        "at": now(),
        "status": "proposed",
    }
    write_json(_proposal_path(project, evolve_id), proposal)
    return evolve_id


def replay(project: Path, evolve_id: str) -> dict:
    """Re-run each cited Lesson's failing gates from its bundle; write and return ``replay.json``.

    Kernel gates are recomputed from the bundle bytes: ``caught`` is whether
    the gate (as the kernel now defines it) still finds something. Agent gates
    cannot be re-run by the kernel: ``caught`` is ``None`` until ``attest``. A
    bundle missing bytes a gate needs yields ``caught=False`` with a note.
    """
    proposal = _read_json(_proposal_path(project, evolve_id), f"evolve {evolve_id!r}")
    results: list[dict] = []
    for run_id in proposal["lessons"]:
        lesson = load_lesson(project, run_id)
        bundle = EvidenceStore(project / "lessons" / lesson["replay"]["evidence_dir"])
        criteria = [decode(Criterion, c) for c in lesson.get("spec_criteria", [])]
        for entry in lesson["replay"]["gates"]:
            caught, note = _replay_gate(lesson, entry, bundle, criteria)
            results.append(
                {
                    "lesson": run_id,
                    "gate": entry["gate"],
                    "step": entry["step"],
                    "pass_id": entry["pass_id"],
                    "executor": entry["executor"],
                    "caught": caught,
                    "note": note,
                }
            )
    report = {"schema": REPLAY_SCHEMA, "evolve_id": evolve_id, "at": now(), "results": results}
    write_json(_replay_path(project, evolve_id), report)
    return report


def _replay_gate(
    lesson: dict, entry: dict, bundle: EvidenceStore, criteria: list[Criterion]
) -> tuple[bool | None, str]:
    if entry["executor"] != Executor.KERNEL.value:
        return None, "agent gate: needs a human attestation"
    gate = KERNEL_GATES.get(entry["gate"])
    if gate is None:
        return False, f"unknown kernel gate {entry['gate']!r}"
    outputs: dict[str, bytes] = {}
    missing: list[str] = []
    for name, digest in entry["outputs"].items():
        data = _safe_get(bundle, digest)
        if data is None:
            missing.append(name)
        else:
            outputs[name] = data
    if missing:
        return False, f"bundle is missing bytes for {', '.join(missing)}"
    pass_id = entry["pass_id"]
    _, _, n = pass_id.partition("#")
    ctx = GateContext(
        step=Step(id=entry["step"], skill=""),
        pass_=Pass(id=pass_id, step=entry["step"], n=int(n) if n.isdigit() else 0, role=Role.PRODUCER),
        outputs=outputs,
        criteria=[c for c in criteria if c.id in entry["criteria"] or entry["gate"] in c.gates],
        store=bundle,
        producer=Skill(name="replay", path=Path("SKILL.md"), identity="", front={}),
        deliverable=lesson["kind_deliverable"],
        statements=lesson["kind_statements"],
    )
    findings = gate.check(ctx)
    note = "; ".join(f.message for f in findings[:3]) if findings else "gate found nothing"
    return bool(findings), note


def attest(project: Path, evolve_id: str, lesson_id: str, gate: str, caught: bool, by: str) -> dict:
    """Record a human's verdict on an agent-gate replay entry; return the updated replay."""
    path = _replay_path(project, evolve_id)
    report = _read_json(path, f"replay of evolve {evolve_id!r}")
    hits = [e for e in report["results"] if e["lesson"] == lesson_id and e["gate"] == gate]
    if not hits:
        raise ValueError(f"replay of {evolve_id!r} has no entry for Lesson {lesson_id!r}, gate {gate!r}")
    if any(e["executor"] == Executor.KERNEL.value for e in hits):
        raise ValueError(f"gate {gate!r} is a kernel gate; its replay is recomputed, not attested")
    at = now()
    for e in hits:
        e.update({"caught": caught, "note": f"attested by {by}", "attested_by": by, "attested_at": at})
    write_json(path, report)
    return report


def adopt(project: Path, evolve_id: str, by: str) -> dict:
    """Accept the evolve; refused unless ``replay.json`` exists and every entry was caught."""
    proposal = _read_json(_proposal_path(project, evolve_id), f"evolve {evolve_id!r}")
    path = _replay_path(project, evolve_id)
    if not path.is_file():
        raise ValueError(f"evolve {evolve_id!r} has not been replayed")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not report["results"]:
        raise ValueError(f"evolve {evolve_id!r} cites Lessons with no failing gate; nothing to verify it against")
    blocking = [
        f"{e['lesson']}/{e['gate']}@{e['pass_id']}: caught={e['caught']}"
        for e in report["results"]
        if e["caught"] is not True
    ]
    if blocking:
        raise ValueError("adoption refused; not caught: " + "; ".join(blocking))
    proposal.update({"status": "adopted", "adopted_by": by, "adopted_at": now(), "replay_at": report["at"]})
    write_json(_proposal_path(project, evolve_id), proposal)
    return proposal
