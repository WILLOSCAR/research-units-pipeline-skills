"""Artifact assembly and proof pack: built from Evidence bytes, re-verified from them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rh.kernel.artifact import (
    PROOF_PACK_SCHEMA,
    ArtifactError,
    assemble,
    deliverable,
    proof_pack,
    render_proof_pack,
    reverify,
)
from rh.kernel.gates import KERNEL_GATES
from rh.kernel.kinds import Kind
from rh.kernel.records import (
    BasisEntry,
    Criterion,
    Decision,
    DecisionOutcome,
    GateResult,
    Goal,
    Ground,
    Layer,
    Pass,
    PassStatus,
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

BRIEF = "# Brief\n\nTransformers dominate retrieval.\n"
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
                serves=["supported", "useful"],
            ),
        ],
        gates=[KERNEL_GATES["pointer-resolution"].declare(["write"])],
    )


def make_run(root: Path) -> tuple[Workspace, RunState, Kind]:
    ws = Workspace(root / "ws")
    ws.init()
    store = ws.evidence
    source = store.put_text("Transformers dominate retrieval benchmarks.", "sources/2510.21861.md", "retrieve#1")
    spec_yaml = store.put_text("schema: rh.success_spec/1\n", "success_spec.yaml", "spec#1")
    brief = store.put_text(BRIEF, "brief.md", "write#1")
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
    kind = make_kind()
    plan = kind.plan()
    for step_id, pass_id in (("spec", "spec#1"), ("write", "write#1")):
        plan.get(step_id).status = StepStatus.ADMITTED
        plan.get(step_id).admitted_pass = pass_id
    spec = SuccessSpec(
        criteria=[
            Criterion(
                id="c1",
                text="Every statement is supported by a source",
                kind="supported",
                ground=Ground.SOURCE,
                gates=["pointer-resolution"],
            ),
            Criterion(
                id="c2",
                text="The brief is useful to a newcomer",
                kind="useful",
                ground=Ground.HUMAN,
                layer=Layer.QUALITY,
            ),
        ]
    )
    state = RunState(
        run_id="brief-20260912-000000-ab12",
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
                outputs={"brief.md": brief.hash, "statements.json": statements.hash},
                status=PassStatus.VERIFIED,
            ),
        ],
        gate_results=[
            GateResult(
                gate="pointer-resolution",
                step="write",
                pass_id="write#1",
                verdict=Verdict.PASS,
                criteria=["c1"],
                produced_by="kernel",
                calibration={"status": "deterministic"},
            )
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
                basis=[BasisEntry("brief.md", brief.hash), BasisEntry("statements.json", statements.hash)],
                options=OPTIONS,
                outcome=DecisionOutcome.ACCEPT,
                by="logic",
                at="2026-09-12T00:10:00+00:00",
            ),
        ],
        passes_used=2,
        stop=Stop(reason=StopReason.CONVERGED, pass_id="write#1"),
    )
    ws.create(state)
    return ws, state, kind


def tamper(ws: Workspace, digest: str) -> None:
    (ws.evidence.objects / digest).write_bytes(b"garbage")


def test_proof_pack_has_every_section(tmp_path: Path) -> None:
    ws, state, kind = make_run(tmp_path)
    pack = proof_pack(state, kind, ws.evidence)
    assert pack["schema"] == PROOF_PACK_SCHEMA
    assert set(pack) >= {
        "goal",
        "status",
        "stop",
        "spec",
        "decisions",
        "integrity",
        "gates",
        "criteria_coverage",
        "statements",
        "loop",
        "identities",
        "evidence",
    }
    assert pack["stop"]["reason"] == "converged"
    assert pack["spec"]["hash"] == state.spec_hash
    assert [c["id"] for c in pack["spec"]["criteria"]] == ["c1", "c2"]
    assert pack["decisions"][0]["basis"] == [{"name": "success_spec.yaml", "hash": state.spec_hash}]
    assert pack["integrity"] == {"passes_verified": ["spec#1", "write#1"], "broken": [], "ok": True}
    assert pack["gates"][0]["calibration"] == {"status": "deterministic"}
    statements = pack["statements"]
    assert statements["hash"] == state.get_pass("write#1").outputs["statements.json"]
    assert (statements["count"], statements["pointers_resolving"], statements["pointers_broken"]) == (1, 1, 0)
    coverage = {c["criterion"]: c for c in pack["criteria_coverage"]}
    assert coverage["c1"]["served_by_steps"] == ["write"]
    assert coverage["c1"]["latest_results"] == [
        {"gate": "pointer-resolution", "step": "write", "verdict": "pass", "pass_id": "write#1"}
    ]
    assert coverage["c1"]["satisfied"] is True
    assert coverage["c2"]["satisfied"] is True  # D-final accepted
    assert pack["loop"]["passes_used"] == 2 and pack["loop"]["repairs"] == 0
    assert pack["identities"]["steps"] == {"spec": "a" * 64, "write": "b" * 64}
    assert pack["evidence"]["count"] == 4


def test_human_criterion_is_pending_without_d_final(tmp_path: Path) -> None:
    ws, state, kind = make_run(tmp_path)
    state.decisions = state.decisions[:1]
    coverage = {c["criterion"]: c for c in proof_pack(state, kind, ws.evidence)["criteria_coverage"]}
    assert coverage["c2"]["satisfied"] is None


def test_integrity_is_recomputed_from_bytes(tmp_path: Path) -> None:
    ws, state, kind = make_run(tmp_path)
    brief_hash = state.get_pass("write#1").outputs["brief.md"]
    tamper(ws, brief_hash)
    integrity = proof_pack(state, kind, ws.evidence)["integrity"]
    assert integrity["ok"] is False
    assert integrity["passes_verified"] == ["spec#1"]
    assert integrity["broken"] == [{"pass_id": "write#1", "output": "brief.md", "hash": brief_hash}]


def test_deliverable_requires_an_admitted_step_unless_lenient(tmp_path: Path) -> None:
    ws, state, kind = make_run(tmp_path)
    admitted = {
        "deliverable": state.get_pass("write#1").outputs["brief.md"],
        "statements": state.get_pass("write#1").outputs["statements.json"],
    }
    assert deliverable(state, kind) == admitted
    state.plan.get("write").status = StepStatus.PENDING
    state.plan.get("write").admitted_pass = None
    with pytest.raises(ArtifactError, match="not admitted"):
        deliverable(state, kind)
    # an abandoned Run's proof pack still names what the latest pass produced
    assert deliverable(state, kind, strict=False) == admitted
    del state.get_pass("write#1").outputs["statements.json"]
    assert deliverable(state, kind, strict=False) == {"deliverable": admitted["deliverable"]}


def test_lenient_deliverable_keeps_the_draft_when_a_prover_was_last(tmp_path: Path) -> None:
    ws, state, kind = make_run(tmp_path)
    expected = deliverable(state, kind)
    state.plan.get("write").status = StepStatus.PENDING
    state.plan.get("write").admitted_pass = None
    state.passes.append(Pass("write#2", "write", 2, Role.PROVER, outputs={"gate_result.json": "a" * 64}))
    assert deliverable(state, kind, strict=False) == expected


def test_assemble_writes_projections_and_returns_hashes(tmp_path: Path) -> None:
    ws, state, kind = make_run(tmp_path)
    hashes = assemble(ws, state, kind)
    assert set(hashes) == {"deliverable", "statements", "proof_pack", "proof_pack_md"}
    assert (ws.artifact / "brief.md").read_text(encoding="utf-8") == BRIEF
    assert (ws.artifact / "statements.json").is_file()
    pack = json.loads((ws.artifact / "proof_pack.json").read_text(encoding="utf-8"))
    assert pack["schema"] == PROOF_PACK_SCHEMA
    assert ws.evidence.get_text(hashes["proof_pack"]) == (ws.artifact / "proof_pack.json").read_text(encoding="utf-8")
    assert ws.evidence.producer_of(hashes["proof_pack"]) == "kernel"
    assert ws.evidence.producer_of(hashes["proof_pack_md"]) == "kernel"
    assert "## Decisions" in (ws.artifact / "proof_pack.md").read_text(encoding="utf-8")
    # assemble neither mutates nor commits the state
    assert state.artifact == {}
    assert ws.load().version == 1


def test_assemble_abandoned_run_without_admitted_step(tmp_path: Path) -> None:
    ws, state, kind = make_run(tmp_path)
    state.status = RunStatus.ABANDONED
    state.stop = Stop(reason=StopReason.EXHAUSTED, pass_id="write#1", gate="pointer-resolution")
    write = state.plan.get("write")
    write.status = StepStatus.PENDING
    write.admitted_pass = None
    del state.get_pass("write#1").outputs["brief.md"]
    hashes = assemble(ws, state, kind)
    assert "deliverable" not in hashes
    assert set(hashes) == {"statements", "proof_pack", "proof_pack_md"}
    assert not (ws.artifact / "brief.md").exists()
    pack = json.loads((ws.artifact / "proof_pack.json").read_text(encoding="utf-8"))
    assert pack["status"] == "abandoned" and pack["stop"]["reason"] == "exhausted"
    assert pack["statements"]["count"] == 1


def test_reverify_reports_a_tampered_object(tmp_path: Path) -> None:
    ws, state, kind = make_run(tmp_path)
    state.artifact = assemble(ws, state, kind)
    assert reverify(ws, state) == []
    tamper(ws, state.artifact["statements"])
    problems = reverify(ws, state)
    assert any(p.startswith("artifact statements") for p in problems)
    assert any(p.startswith("pass write#1 output statements.json") for p in problems)


def test_render_proof_pack_keeps_layers_apart(tmp_path: Path) -> None:
    ws, state, kind = make_run(tmp_path)
    md = render_proof_pack(proof_pack(state, kind, ws.evidence))
    assert md.startswith("# Proof pack: brief-20260912-000000-ab12\n")
    for heading in (
        "## Goal",
        "## Success Spec",
        "## Decisions",
        "## Layer 1: execution integrity",
        "## Layer 2: contract acceptance",
        "## Layer 3: research quality",
        "## Statement provenance",
        "## Loop trace",
        "## Identities",
        "## Evidence index",
    ):
        assert heading in md
    assert "- c2: accepted at D-final" in md
    assert "| pointer-resolution | write | write#1 | pass |" in md
