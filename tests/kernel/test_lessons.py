"""Lessons and evolve: distill from an ended Run, replay against the bundle, adopt only when caught."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rh.kernel.evidence import EvidenceStore
from rh.kernel.gates import KERNEL_GATES
from rh.kernel.kinds import Kind
from rh.kernel.lessons import (
    EVOLVE_SCHEMA,
    LESSON_SCHEMA,
    adopt,
    attest,
    distill,
    list_lessons,
    load_lesson,
    propose,
    replay,
    stall_series,
)
from rh.kernel.records import (
    BasisEntry,
    Criterion,
    Decision,
    DecisionOutcome,
    Executor,
    Fault,
    Finding,
    GateDecl,
    GateKind,
    GateResult,
    Goal,
    Ground,
    Pass,
    PassStatus,
    Plan,
    Role,
    RunState,
    RunStatus,
    Step,
    StepStatus,
    Stop,
    StopReason,
    SuccessSpec,
    Verdict,
)
from rh.kernel.run import Workspace

RUN_ID = "brief-20260912-000000-cd34"
DRAFT = "# Brief\n\n<!-- scaffold -->\n\nTransformers dominate retrieval.\n"
FINAL = "# Brief\n\nTransformers dominate retrieval.\n"
OPTIONS = [DecisionOutcome.ACCEPT, DecisionOutcome.REJECT]


def make_kind() -> Kind:
    return Kind(
        kind="brief",
        title="One-page brief",
        deliverable="brief.md",
        statements="statements.json",
        steps=[
            Step(id="spec", skill="success-spec", produces=["success_spec.yaml"], fixed=True),
            Step(
                id="write",
                skill="brief-writer",
                consumes=["success_spec.yaml"],
                produces=["brief.md", "statements.json"],
                serves=["supported", "scaffold"],
            ),
        ],
        gates=[
            KERNEL_GATES["scaffold-absent"].declare(["write"]),
            GateDecl(
                id="source-support",
                kind=GateKind.GROUNDED,
                ground=Ground.SOURCE,
                executor=Executor.AGENT,
                serves=["supported"],
                applies_to=["write"],
                skill="source-support-prover",
            ),
        ],
    )


def make_run(root: Path) -> tuple[Workspace, RunState, Kind]:
    ws = Workspace(root / "ws")
    ws.init()
    store = ws.evidence
    source = store.put_text("Transformers dominate retrieval benchmarks.", "sources/2510.21861.md", "retrieve#1")
    spec_yaml = store.put_text("schema: rh.success_spec/1\n", "success_spec.yaml", "spec#1")
    draft = store.put_text(DRAFT, "brief.md", "write#1")
    statements = store.put_text(
        json.dumps(
            {
                "schema": "rh.statements/1",
                "statements": [
                    {
                        "id": "s1",
                        "text": "Transformers dominate retrieval.",
                        "evidence": [{"hash": source.hash, "relation": "condenses"}],
                    }
                ],
            }
        ),
        "statements.json",
        "write#1",
    )
    final = store.put_text(FINAL, "brief.md", "write#2")
    kind = make_kind()
    plan = kind.plan()
    for step_id, pass_id in (("spec", "spec#1"), ("write", "write#2")):
        plan.get(step_id).status = StepStatus.ADMITTED
        plan.get(step_id).admitted_pass = pass_id
    spec = SuccessSpec(
        criteria=[
            Criterion(
                id="c1",
                text="Every statement is supported by a source",
                kind="supported",
                ground=Ground.SOURCE,
                gates=["source-support"],
            ),
            Criterion(
                id="c2",
                text="No scaffold text remains",
                kind="scaffold",
                ground=Ground.COMPUTATION,
                gates=["scaffold-absent"],
            ),
        ]
    )
    state = RunState(
        run_id=RUN_ID,
        kind="brief",
        goal=Goal(text="Summarise retrieval.", hash="g" * 64),
        plan=plan,
        status=RunStatus.COMPLETED,
        spec=spec,
        spec_hash=spec_yaml.hash,
        passes=[
            Pass(
                id="spec#1",
                step="spec",
                n=1,
                role=Role.PRODUCER,
                skill_identity="a" * 64,
                outputs={"success_spec.yaml": spec_yaml.hash},
                status=PassStatus.VERIFIED,
            ),
            Pass(
                id="write#1",
                step="write",
                n=1,
                role=Role.PRODUCER,
                skill_identity="b" * 64,
                outputs={"brief.md": draft.hash, "statements.json": statements.hash},
                status=PassStatus.FAILED,
            ),
            Pass(
                id="write#2",
                step="write",
                n=2,
                role=Role.REPAIR,
                faults=["F1", "F2"],
                skill_identity="b" * 64,
                outputs={"brief.md": final.hash, "statements.json": statements.hash},
                status=PassStatus.VERIFIED,
            ),
        ],
        gate_results=[
            GateResult(
                gate="scaffold-absent",
                step="write",
                pass_id="write#1",
                verdict=Verdict.FAIL,
                criteria=["c2"],
                findings=[Finding("brief.md still contains the scaffold marker '<!-- scaffold -->'")],
                produced_by="kernel",
                calibration={"status": "deterministic"},
            ),
            GateResult(
                gate="source-support",
                step="write",
                pass_id="write#1",
                verdict=Verdict.FAIL,
                criteria=["c1"],
                score=0.4,
                findings=[Finding("s1 overstates the source", evidence=[source.hash], statement="s1", criterion="c1")],
                produced_by="c" * 64,
                executor=Executor.AGENT,
                kind=GateKind.GROUNDED,
                ground=Ground.SOURCE,
                calibration={"status": "unmeasured"},
            ),
            GateResult(
                gate="scaffold-absent",
                step="write",
                pass_id="write#2",
                verdict=Verdict.PASS,
                criteria=["c2"],
                produced_by="kernel",
                calibration={"status": "deterministic"},
            ),
            GateResult(
                gate="source-support",
                step="write",
                pass_id="write#2",
                verdict=Verdict.PASS,
                criteria=["c1"],
                score=0.9,
                produced_by="c" * 64,
                executor=Executor.AGENT,
                kind=GateKind.GROUNDED,
                ground=Ground.SOURCE,
                calibration={"status": "unmeasured"},
            ),
        ],
        faults=[
            Fault(
                id="F1",
                gate="scaffold-absent",
                criterion="c2",
                ground=Ground.COMPUTATION,
                step="write",
                checked_step="write",
                message="brief.md still contains the scaffold marker",
                pass_id="write#1",
                resolved=True,
            ),
            Fault(
                id="F2",
                gate="source-support",
                criterion="c1",
                ground=Ground.SOURCE,
                step="write",
                checked_step="write",
                message="s1 overstates the source",
                evidence=[source.hash],
                pass_id="write#1",
                resolved=True,
            ),
        ],
        decisions=[
            Decision(
                id="D0",
                prompt="Accept the Success Spec?",
                basis=[BasisEntry("success_spec.yaml", spec_yaml.hash)],
                options=OPTIONS,
                outcome=DecisionOutcome.ACCEPT,
                by="logic",
                at="2026-09-12T00:00:00+00:00",
            ),
            Decision(
                id="D-final",
                prompt="Accept the Artifact?",
                basis=[BasisEntry("brief.md", final.hash), BasisEntry("statements.json", statements.hash)],
                options=OPTIONS,
                outcome=DecisionOutcome.ACCEPT,
                by="logic",
                at="2026-09-12T00:10:00+00:00",
            ),
        ],
        passes_used=3,
        stop=Stop(reason=StopReason.CONVERGED, pass_id="write#2"),
        artifact={"deliverable": final.hash, "statements": statements.hash},
    )
    ws.create(state)
    return ws, state, kind


def test_distill_writes_lesson_and_bundle(tmp_path: Path) -> None:
    ws, state, kind = make_run(tmp_path)
    project = tmp_path / "project"
    path = distill(ws, state, kind, project)
    assert path == project / "lessons" / f"{RUN_ID}.json"
    lesson = load_lesson(project, RUN_ID)
    assert lesson["schema"] == LESSON_SCHEMA
    assert lesson["status"] == "completed" and lesson["stop"]["reason"] == "converged"
    assert [f["id"] for f in lesson["faults"]] == ["F1", "F2"]
    assert lesson["faults"][1]["ground"] == "source" and lesson["faults"][1]["resolved"] is True
    assert [(g["gate"], g["pass_id"]) for g in lesson["gate_failures"]] == [
        ("scaffold-absent", "write#1"),
        ("source-support", "write#1"),
    ]
    assert lesson["gate_failures"][1]["findings"][0]["statement"] == "s1"
    assert lesson["repairs"] == [{"pass_id": "write#2", "step": "write", "faults": ["F1", "F2"], "resolved": True}]
    assert [d["outcome"] for d in lesson["decisions"]] == ["accept", "accept"]
    assert lesson["budget"] == {
        "passes_total": 24,
        "passes_used": 3,
        "per_gate_failures": {"write/scaffold-absent": 1, "write/source-support": 1},
    }
    assert lesson["stall"] == []
    assert lesson["skill_identities"] == {"spec": "a" * 64, "write": "b" * 64}
    assert lesson["artifact"] == state.artifact
    assert (lesson["kind_deliverable"], lesson["kind_statements"]) == ("brief.md", "statements.json")
    assert [c["id"] for c in lesson["spec_criteria"]] == ["c1", "c2"]
    entries = lesson["replay"]["gates"]
    assert [e["gate"] for e in entries] == ["scaffold-absent", "source-support"]
    assert entries[0]["outputs"] == state.get_pass("write#1").outputs
    assert entries[0]["criteria"] == ["c2"]

    bundle = EvidenceStore(project / "lessons" / lesson["replay"]["evidence_dir"])
    draft, statements = state.get_pass("write#1").outputs.values()
    source = state.faults[1].evidence[0]
    for digest in (draft, statements, source, state.artifact["deliverable"]):
        assert bundle.has(digest), digest
    assert bundle.get_text(draft) == DRAFT

    assert distill(ws, state, kind, project) == path  # idempotent
    summaries = list_lessons(project)
    assert len(summaries) == 1
    assert summaries[0]["run_id"] == RUN_ID and summaries[0]["gate_failures"] == 2
    with pytest.raises(FileNotFoundError):
        load_lesson(project, "no-such-run")


def test_distill_defaults_to_the_workspace_parent(tmp_path: Path) -> None:
    ws, state, kind = make_run(tmp_path)
    assert distill(ws, state, kind) == tmp_path / "lessons" / f"{RUN_ID}.json"


def test_propose_requires_known_lessons(tmp_path: Path) -> None:
    project = tmp_path / "project"
    with pytest.raises(ValueError, match="at least one Lesson"):
        propose(project, "gate:scaffold-absent", [], "no basis")
    with pytest.raises(ValueError, match="unknown Lesson"):
        propose(project, "gate:scaffold-absent", ["missing-run"], "no basis")


def test_propose_replay_attest_adopt(tmp_path: Path) -> None:
    ws, state, kind = make_run(tmp_path)
    project = tmp_path / "project"
    distill(ws, state, kind, project)

    evolve_id = propose(project, "gate:scaffold-absent", [RUN_ID], "tighten the marker check", by="logic")
    assert evolve_id.startswith("gate-scaffold-absent-")
    proposal = json.loads((project / "evolve" / evolve_id / "proposal.json").read_text(encoding="utf-8"))
    assert proposal["schema"] == EVOLVE_SCHEMA
    assert proposal["status"] == "proposed" and proposal["lessons"] == [RUN_ID]

    report = replay(project, evolve_id)
    by_gate = {r["gate"]: r for r in report["results"]}
    assert by_gate["scaffold-absent"]["caught"] is True
    assert "scaffold marker" in by_gate["scaffold-absent"]["note"]
    assert by_gate["source-support"]["caught"] is None
    assert (project / "evolve" / evolve_id / "replay.json").is_file()

    with pytest.raises(ValueError, match="source-support"):
        adopt(project, evolve_id, by="logic")

    with pytest.raises(ValueError, match="kernel gate"):
        attest(project, evolve_id, RUN_ID, "scaffold-absent", caught=True, by="logic")
    with pytest.raises(ValueError, match="no entry"):
        attest(project, evolve_id, RUN_ID, "spec-coverage", caught=True, by="logic")

    attested = attest(project, evolve_id, RUN_ID, "source-support", caught=True, by="logic")
    entry = next(r for r in attested["results"] if r["gate"] == "source-support")
    assert entry["caught"] is True and entry["attested_by"] == "logic"

    adopted = adopt(project, evolve_id, by="logic")
    assert adopted["status"] == "adopted" and adopted["adopted_by"] == "logic"
    on_disk = json.loads((project / "evolve" / evolve_id / "proposal.json").read_text(encoding="utf-8"))
    assert on_disk["status"] == "adopted"


def test_adopt_requires_a_replay(tmp_path: Path) -> None:
    ws, state, kind = make_run(tmp_path)
    project = tmp_path / "project"
    distill(ws, state, kind, project)
    evolve_id = propose(project, "kind:brief", [RUN_ID], "reorder steps")
    with pytest.raises(ValueError, match="not been replayed"):
        adopt(project, evolve_id, by="logic")


def test_replay_reports_missing_bundle_bytes(tmp_path: Path) -> None:
    ws, state, kind = make_run(tmp_path)
    project = tmp_path / "project"
    distill(ws, state, kind, project)
    draft = state.get_pass("write#1").outputs["brief.md"]
    (project / "lessons" / RUN_ID / "evidence" / "objects" / draft).unlink()
    evolve_id = propose(project, "gate:scaffold-absent", [RUN_ID], "tighten the marker check")
    entry = next(r for r in replay(project, evolve_id)["results"] if r["gate"] == "scaffold-absent")
    assert entry["caught"] is False
    assert "missing bytes for brief.md" in entry["note"]


def test_replay_does_not_catch_when_the_gate_finds_nothing(tmp_path: Path) -> None:
    ws, state, kind = make_run(tmp_path)
    # Make the recorded failing pass point at the clean deliverable: the gate no longer fires.
    state.get_pass("write#1").outputs["brief.md"] = state.get_pass("write#2").outputs["brief.md"]
    project = tmp_path / "project"
    distill(ws, state, kind, project)
    evolve_id = propose(project, "gate:scaffold-absent", [RUN_ID], "loosen the marker check")
    entry = next(r for r in replay(project, evolve_id)["results"] if r["gate"] == "scaffold-absent")
    assert entry["caught"] is False and entry["note"] == "gate found nothing"


def _failing(step: str, gate: str, pass_id: str, score: float | None) -> GateResult:
    return GateResult(gate=gate, step=step, pass_id=pass_id, verdict=Verdict.FAIL, score=score)


def test_stall_series_reports_non_improving_gates() -> None:
    state = RunState(
        run_id="r",
        kind="brief",
        goal=Goal(text="g"),
        plan=Plan(steps=[Step(id="spec", skill="success-spec")]),
        gate_results=[
            _failing("write", "source-support", "write#1", 0.5),
            _failing("write", "source-support", "write#2", 0.5),
            _failing("write", "source-support", "write#3", 0.4),
            _failing("write", "spec-coverage", "write#1", 0.2),
            _failing("write", "spec-coverage", "write#2", 0.5),
            _failing("write", "spec-coverage", "write#3", 0.7),
            _failing("write", "scaffold-absent", "write#1", None),
            _failing("write", "scaffold-absent", "write#2", None),
            _failing("outline", "scaffold-absent", "outline#1", None),
            _failing("outline", "scaffold-absent", "outline#2", None),
            _failing("outline", "scaffold-absent", "outline#3", None),
        ],
    )
    assert stall_series(state) == [
        {"step": "write", "gate": "source-support", "scores": [0.5, 0.5, 0.4]},
        {"step": "outline", "gate": "scaffold-absent", "scores": [None, None, None]},
    ]
