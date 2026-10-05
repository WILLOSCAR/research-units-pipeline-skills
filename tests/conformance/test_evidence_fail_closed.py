"""C2a holds at every Run transition, including acceptance and terminal resume."""

from __future__ import annotations

import json

import pytest

from agent_stub import Agent, to_completed, to_d0, to_d_final
from rh.api import OutcomeKind
from rh.kernel.evidence import EvidenceCorrupt


def _reference(state, name):
    if name == "goal":
        return state.goal.hash
    if name == "spec":
        return state.spec_hash
    if name == "source":
        return state.get_pass("retrieve#1").outputs["sources/a.md"]
    if name == "gate":
        return state.gate_results[-1].hash
    if name == "artifact":
        return state.artifact["proof_pack"]
    if name == "statements":
        return state.artifact["statements"]
    raise AssertionError(name)


def _damage(harness, digest, mode="alter"):
    path = harness.ws.evidence.objects / digest
    original = path.read_bytes()
    if mode == "alter":
        path.write_bytes(b"corrupted authoritative Evidence")
    else:
        path.unlink()
    return path, original


def _record(harness):
    """Externally visible authority and side effects must not change on refusal."""
    ws = harness.ws
    paths = [ws.run_json, ws.trace, *ws.decisions.glob("*"), *harness.project.rglob("*.json")]
    return {str(p): p.read_bytes() for p in paths if p.is_file()}


@pytest.mark.parametrize("reference", ["goal", "spec", "source", "gate", "artifact", "statements"])
@pytest.mark.parametrize("mode", ["alter", "remove"])
def test_final_acceptance_refuses_corrupt_retained_evidence(tmp_path, reference, mode):
    harness, _, _ = to_d_final(tmp_path)
    digest = _reference(harness.ws.load(), reference)
    path, original = _damage(harness, digest, mode)
    before = _record(harness)

    with pytest.raises(EvidenceCorrupt, match=digest[:12]):
        harness.decide("D-final", "accept", by="test operator")

    assert _record(harness) == before
    assert harness.ws.load().pending_decision().id == "D-final"
    assert any(digest[:12] in problem for problem in harness.inspect()["integrity"])
    path.write_bytes(original)
    assert harness.decide("D-final", "accept", by="test operator").kind is OutcomeKind.COMPLETED
    assert harness.inspect()["integrity"] == []


@pytest.mark.parametrize("operation", ["continue", "reject", "plan_add", "plan_skip", "escalate"])
def test_mutations_refuse_corruption_before_writing_state_or_projections(tmp_path, operation):
    harness, _, _ = to_d_final(tmp_path)
    digest = _reference(harness.ws.load(), "source")
    _damage(harness, digest)
    before = _record(harness)
    calls = {
        "continue": harness.continue_,
        "reject": lambda: harness.decide("D-final", "reject", reason="revise the review"),
        "plan_add": lambda: harness.plan_add("id: extra\nskill: curate-fixture\nconsumes: [sources/]\nproduces: [extra.csv]\nserves: [coverage]\nafter: retrieve\n"),
        "plan_skip": lambda: harness.plan_skip("curate"),
        "escalate": lambda: harness.escalate("operator requests a stop"),
    }
    with pytest.raises(EvidenceCorrupt, match=digest[:12]):
        calls[operation]()
    assert _record(harness) == before


@pytest.mark.parametrize("reference", ["goal", "spec"])
def test_d0_cannot_accept_corrupt_goal_or_canonical_spec(tmp_path, reference):
    harness, _, _ = to_d0(tmp_path)
    digest = _reference(harness.ws.load(), reference)
    _damage(harness, digest)
    before = _record(harness)
    with pytest.raises(EvidenceCorrupt, match=digest[:12]):
        harness.decide("D0", "accept")
    assert _record(harness) == before


def test_continuation_checks_retained_evidence_even_when_packet_does_not_consume_it(tmp_path):
    harness, agent, _ = to_d0(tmp_path)
    outcome = harness.decide("D0", "accept")
    # retrieve consumes the spec, but not goal.md; the Goal must still exist.
    packet = Agent.packet_of(outcome)
    assert "goal.md" not in {i["name"] for i in packet["inputs"]}
    agent.perform(outcome)
    digest = harness.ws.load().goal.hash
    _damage(harness, digest)
    before = _record(harness)
    with pytest.raises(EvidenceCorrupt, match=digest[:12]):
        harness.continue_()
    assert _record(harness) == before


def test_terminal_continuation_does_not_report_completion_for_corrupt_evidence(tmp_path):
    harness, _, _ = to_completed(tmp_path)
    digest = _reference(harness.ws.load(), "source")
    _damage(harness, digest)
    before = _record(harness)
    with pytest.raises(EvidenceCorrupt, match=digest[:12]):
        harness.continue_()
    assert _record(harness) == before


def test_prior_decision_basis_remains_required_after_a_revised_spec(tmp_path):
    import yaml

    harness, _, _ = to_d0(tmp_path)
    prior_spec = harness.ws.load().spec_hash
    path = harness.ws.root / "success_spec.yaml"
    candidate = yaml.safe_load(path.read_text())
    candidate["criteria"][0]["text"] = "Answer the revised bounded research question."
    path.write_text(yaml.safe_dump(candidate, sort_keys=False))
    assert harness.continue_().decision["id"] == "D0-2"
    state = harness.ws.load()
    assert state.spec_hash != prior_spec
    assert prior_spec not in {h for p in state.passes for h in p.outputs.values()}
    _damage(harness, prior_spec)
    before = _record(harness)
    with pytest.raises(EvidenceCorrupt, match=prior_spec[:12]):
        harness.decide("D0-2", "accept")
    assert _record(harness) == before
    assert any("Decision D0 basis success_spec.yaml" in p for p in harness.inspect()["integrity"])


def test_unreferenced_corruption_and_projection_edits_do_not_block_normal_recovery(tmp_path):
    harness, _, _ = to_d_final(tmp_path)
    orphan = harness.ws.evidence.put_text("uncommitted output", "unused.txt", "interrupted-write")
    _damage(harness, orphan.hash)
    artifact = harness.ws.artifact / "brief.md"
    artifact.write_text("edited projection")
    before = harness.ws.load()
    resumed = harness.continue_()
    assert resumed.decision["id"] == "D-final"
    assert "restored" in resumed.message
    assert artifact.read_text() != "edited projection"
    assert harness.ws.load().artifact == before.artifact
    assert harness.decide("D-final", "accept").kind is OutcomeKind.COMPLETED


def test_gate_projection_edit_remains_diagnostic_not_authoritative_corruption(tmp_path):
    harness, _, _ = to_d_final(tmp_path)
    path = next(harness.ws.gates.glob("*.source-support.json"))
    edited = json.loads(path.read_text())
    edited["verdict"] = "fail"
    path.write_text(json.dumps(edited))
    assert any("projection" in p for p in harness.inspect()["integrity"])
    assert harness.decide("D-final", "accept").kind is OutcomeKind.COMPLETED


@pytest.mark.parametrize("mode", ["alter", "directory"])
def test_new_outputs_cannot_adopt_a_corrupt_unreferenced_object(tmp_path, mode):
    body = "id,note\na,ok\n"
    harness, agent, _ = to_d0(tmp_path, annotate=lambda packet, out: (out / "notes.csv").write_text(body))
    harness.plan_add("id: annotate\nskill: curate-fixture\nconsumes: [sources/]\nproduces: [notes.csv]\nserves: [coverage]\nafter: retrieve\n")
    digest = harness.ws.evidence.put_text(body, "interrupted-notes.csv", "interrupted-write").hash
    path = harness.ws.evidence.objects / digest
    if mode == "alter":
        path.write_bytes(b"corrupted orphan")
    else:
        path.unlink()
        path.mkdir()
    # The orphan does not prevent unrelated progress before anything refers to it.
    outcome = harness.decide("D0", "accept")
    agent.perform(outcome)
    outcome = harness.continue_()
    assert Agent.packet_of(outcome)["step"] == "annotate"
    agent.perform(outcome)
    before = _record(harness)
    index_before = harness.ws.evidence.index_path.read_bytes()

    with pytest.raises(EvidenceCorrupt, match=digest[:12]):
        harness.continue_()

    assert _record(harness) == before
    assert harness.ws.evidence.index_path.read_bytes() == index_before
    assert harness.ws.load().plan.get("annotate").admitted_pass is None
    assert harness.ws.load().pending_pass == Agent.packet_of(outcome)["pass_id"]
    if path.is_dir():
        path.rmdir()
    path.write_text(body)
    resumed = agent.drive(harness.continue_())
    assert resumed.decision["id"] == "D-final"
    assert harness.decide("D-final", "accept").kind is OutcomeKind.COMPLETED
    assert harness.inspect()["integrity"] == []
