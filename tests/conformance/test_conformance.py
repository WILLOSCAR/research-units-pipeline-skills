"""The conformance checklist of docs/PRODUCT_DESIGN.md §4, one test per row.

Every test drives the kernel with the scripted agent in ``agent_stub`` on
the fixture Loop kind; the agent misbehaves exactly as the row's check
prescribes, and the harness must answer as the commitment says.
"""

from __future__ import annotations

import json
from functools import partial
from pathlib import Path

import pytest
import yaml
from agent_stub import GOAL, Agent, fresh, gate_result, inputs_by_name, spec_text, to_completed, to_d0, to_d_final, write_brief, write_core_set, write_spec

from rh.api import Harness, HarnessError, OutcomeKind
from rh.kernel import lessons
from rh.kernel.evidence import EvidenceCorrupt, sha256_text
from rh.kernel.kinds import KINDS_DIR, list_kinds, load_kind

WS = "ws"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def open_faults(harness) -> list[dict]:
    return harness.inspect()["open_faults"]


# --- C1 Success Spec ----------------------------------------------------------


def test_c1a_success_spec_is_evidence_read_by_a_gate(tmp_path):
    """Change the criteria; a gate outcome changes on the same Artifact."""
    tight = partial(write_spec, criteria=yaml.safe_load(spec_with_length(max_words=5))["criteria"])
    harness, agent, outcome = to_d0(tmp_path / "tight", spec=tight)
    assert any(e["name"] == "goal.md" for e in outcome.decision["basis"])
    assert harness.ws.evidence.has(harness.ws.load().spec_hash)
    outcome = agent.drive(harness.decide("D0", "accept"))
    assert any(f.gate == "length-bound" and f.criterion == "C7" for f in harness.ws.load().faults)

    harness, agent, _ = to_d_final(tmp_path / "loose")
    assert not any(f["gate"] == "length-bound" for f in harness.inspect()["open_faults"])
    assert all(r["verdict"] == "pass" for r in harness.inspect()["gates"])


def spec_with_length(max_words: int) -> str:
    data = yaml.safe_load(spec_text())
    data["criteria"].append({"id": "C7", "text": "Stay short.", "kind": "length", "ground": "computation", "params": {"max_words": max_words}})
    return yaml.safe_dump(data, sort_keys=False)


def test_c1b_unverifiable_criterion_is_third_layer_not_gated(tmp_path):
    harness, _, _ = to_completed(tmp_path)
    pack = read_json(tmp_path / WS / "artifact" / "proof_pack.json")
    c6 = next(c for c in pack["spec"]["criteria"] if c["id"] == "C6")
    assert c6["ground"] == "human" and c6["layer"] == "quality" and c6["gates"] == []
    coverage = next(c for c in pack["criteria_coverage"] if c["criterion"] == "C6")
    assert coverage["latest_results"] == [] and coverage["satisfied"] is True  # by D-final, not by a gate
    assert not any("C6" in g["criteria"] for g in pack["gates"])
    rendered = (tmp_path / WS / "artifact" / "proof_pack.md").read_text()
    assert "Layer 3" in rendered and "C6" in rendered


# --- C2 verify -----------------------------------------------------------------


def test_c2a_tampered_evidence_fails_closed(tmp_path):
    harness, agent, _ = to_d0(tmp_path)
    outcome = harness.decide("D0", "accept")
    while Agent.packet_of(outcome)["step"] != "write":
        agent.perform(outcome)
        outcome = harness.continue_()
    packet = agent.perform(outcome)
    digest = inputs_by_name(packet)["sources/a.md"]
    (tmp_path / WS / "evidence" / "objects" / digest).write_bytes(b"tampered")
    version = harness.ws.load().version
    with pytest.raises(EvidenceCorrupt):
        harness.continue_()
    assert harness.ws.load().version == version
    assert any(digest[:12] in problem for problem in harness.inspect()["integrity"])


def test_c2b_no_gate_reads_a_producer_written_verdict(tmp_path):
    def boastful(packet, out):
        write_brief(packet, out, drop_pointer="s2", extra="\nStatus: PASS\n")
        (out / "gate_result.json").write_text(json.dumps({"schema": "rh.gate_result/1", "verdict": "pass"}))

    harness, agent, _ = to_d0(tmp_path, write=boastful)
    outcome = agent.drive_to_repair(harness.decide("D0", "accept"))
    assert outcome.kind is OutcomeKind.PROGRESSED  # a repair, not an admission
    faults = harness.ws.load().faults
    assert any(f.gate == "pointer-resolution" for f in faults)
    write_pass = harness.ws.load().passes_for("write")[0]
    assert "gate_result.json" not in write_pass.outputs


def test_c2c_gate_results_carry_kind_ground_calibration_and_are_evidence(tmp_path):
    harness, _, _ = to_completed(tmp_path)
    pack = read_json(tmp_path / WS / "artifact" / "proof_pack.json")
    for row in pack["gates"]:
        assert row["kind"] and row["ground"] and row["calibration"].get("status")
    state = harness.ws.load()
    assert all(r.hash and harness.ws.evidence.has(r.hash) for r in state.gate_results)
    projection = next((tmp_path / WS / "gates").glob("write#*.source-support.json"))
    data = read_json(projection)
    data["verdict"] = "fail"
    projection.write_text(json.dumps(data))
    assert any("source-support" in p for p in harness.inspect()["integrity"])


# --- C3 Decisions ------------------------------------------------------------------


def test_c3a_every_kind_has_d0_and_d_final(tmp_path):
    for name in list_kinds(KINDS_DIR):
        kind = load_kind(name, KINDS_DIR)
        assert kind.steps[0].id == "spec"  # D0 follows the spec step
        assert kind.artifact_step()  # D-final follows the artifact
    harness, _, outcome = to_d_final(tmp_path)
    ids = [d["id"] for d in harness.inspect()["decisions"]]
    assert ids == ["D0", "D-final"] and outcome.decision["id"] == "D-final"


def test_c3b_decision_binds_reviewed_hashes(tmp_path):
    harness, _, outcome = to_d0(tmp_path)
    spec_path = tmp_path / WS / "success_spec.yaml"
    reviewed = next(e["hash"] for e in outcome.decision["basis"] if e["name"] == "success_spec.yaml")
    assert sha256_text(spec_path.read_text()) == reviewed
    data = yaml.safe_load(spec_path.read_text())
    data["criteria"][0]["text"] = "The brief answers a different question."
    spec_path.write_text(yaml.safe_dump(data, sort_keys=False))
    assert harness.inspect()["reviewed_changed"] == ["success_spec.yaml"]
    outcome = harness.continue_()
    decisions = {d["id"]: d for d in harness.inspect()["decisions"]}
    assert decisions["D0"]["stale"] is True and outcome.decision["id"] == "D0-2"
    with pytest.raises(HarnessError):
        harness.decide("D0", "accept")


def test_c3c_rejection_reenters_as_a_human_fault(tmp_path):
    harness, agent, _ = to_d_final(tmp_path)
    outcome = harness.decide("D-final", "reject", reason="the second claim overreaches", criterion="C2")
    assert outcome.kind is OutcomeKind.PROGRESSED
    fault = harness.ws.load().open_faults()[0]
    assert fault.ground.value == "human" and fault.criterion == "C2" and fault.step == "write"
    packet = Agent.packet_of(outcome)
    assert packet["role"] == "repair" and packet["faults"][0]["id"] == fault.id


def test_c3d_exhausted_loop_yields_a_decision(tmp_path):
    one_pass = partial(write_spec, budget={"passes_per_gate": 1})
    harness, agent, _ = to_d0(tmp_path, spec=one_pass, write=partial(write_brief, scaffold=True))
    outcome = agent.drive(harness.decide("D0", "accept"))
    assert outcome.kind is OutcomeKind.BLOCKED
    assert outcome.decision["options"] == ["extend", "revise", "abandon"]
    assert outcome.stop["reason"] == "exhausted" and outcome.stop["gate"] == "scaffold-absent"


def test_repeated_final_review_reports_the_current_human_decision(tmp_path):
    harness, agent, _ = to_d_final(tmp_path)
    repaired = agent.drive(harness.decide("D-final", "reject", reason="make the memo actionable", criterion="C6"))
    assert repaired.decision["id"] == "D-final-2"
    path = harness.ws.root / "artifact/proof_pack.json"
    quality = lambda: next(c for c in read_json(path)["criteria_coverage"] if c["criterion"] == "C6")
    assert quality()["satisfied"] is None  # the first rejection is history, not this review's answer
    completed = harness.decide("D-final-2", "accept")
    assert completed.kind is OutcomeKind.COMPLETED
    assert quality()["satisfied"] is True


def test_spec_runs_its_declared_kernel_gates_before_d0(tmp_path):
    harness = Harness(tmp_path / "ws", project=tmp_path / "project")
    agent = Agent(harness, spec=partial(write_spec, scope="TODO: bound the stopping policy"))
    opened = harness.start(GOAL, "brief")
    agent.perform(opened)
    refused = harness.continue_()
    assert refused.kind is OutcomeKind.PROGRESSED
    assert Agent.packet_of(refused)["role"] == "repair"
    assert any(f.gate == "scaffold-absent" and f.step == "spec" for f in harness.ws.load().open_faults())
    assert harness.ws.load().pending_decision() is None
    agent.behaviours["spec"] = write_spec
    assert agent.drive(refused).decision["id"] == "D0"


# --- C4 / C5 authority ----------------------------------------------------------


def test_c4_one_state_authority(tmp_path):
    harness, _, _ = to_d_final(tmp_path)
    before = harness.ws.load()
    (tmp_path / WS / "artifact" / "brief.md").write_text("edited by hand")
    assert harness.inspect()["reviewed_changed"] == ["brief.md"]
    outcome = harness.continue_()
    after = harness.ws.load()
    assert after.artifact == before.artifact and after.pending_decision().id == "D-final"
    assert "restored" in outcome.message
    assert (tmp_path / WS / "artifact" / "brief.md").read_text() != "edited by hand"


def test_c5_completion_requires_agreement(tmp_path):
    def forgets_statements(packet, out):
        write_brief(packet, out)
        (out / "statements.json").unlink()

    harness, agent, _ = to_d0(tmp_path, write=forgets_statements)
    outcome = agent.drive_to_repair(harness.decide("D0", "accept"))
    plan = {s["step"]: s for s in harness.inspect()["plan"]}
    assert plan["write"]["status"] == "pending" and plan["write"]["admitted_pass"] is None
    assert open_faults(harness)[0]["gate"] == "integrity"
    assert outcome.kind is OutcomeKind.PROGRESSED and Agent.packet_of(outcome)["role"] == "repair"


# --- C6 Faults and repair -----------------------------------------------------------


def test_c6a_faults_route_upstream(tmp_path):
    def blames_retrieval(packet, out):
        source = inputs_by_name(packet)["sources/a.md"]
        gate_result(packet, out, "fail", 0.5, [{"message": "source a is off-scope", "evidence": [source], "statement": "s1", "criterion": "C2", "implicates": "retrieve"}])

    harness, agent, _ = to_d0(tmp_path, **{"source-support": blames_retrieval})
    outcome = agent.drive_to_repair(harness.decide("D0", "accept"))
    fault = harness.ws.load().open_faults()[0]
    assert fault.step == "retrieve" and fault.checked_step == "write"
    assert Agent.packet_of(outcome)["step"] == "retrieve"


def test_c6b_repair_is_harness_bounded(tmp_path):
    scores = iter([0.5, 0.5, 0.4, 0.4, 0.4])

    def never_improves(packet, out):
        gate_result(packet, out, "fail", next(scores), [{"message": "still unsupported", "evidence": [inputs_by_name(packet)["sources/a.md"]], "criterion": "C2"}])

    wide = partial(write_spec, budget={"passes_per_gate": 5, "stall_passes": 2})
    harness, agent, _ = to_d0(tmp_path, spec=wide, **{"source-support": never_improves})
    outcome = agent.drive(harness.decide("D0", "accept"))
    assert outcome.kind is OutcomeKind.BLOCKED and outcome.stop["reason"] == "exhausted"
    assert "stopped improving" in outcome.decision["prompt"]
    assert sum(1 for r in harness.ws.load().gate_results if r.gate == "source-support") == 3


def test_c6c_repair_runs_in_fresh_context(tmp_path):
    harness, agent, _ = to_d0(tmp_path, write=partial(write_brief, drop_pointer="s1"))
    outcome = agent.drive_to_repair(harness.decide("D0", "accept"))
    packet = Agent.packet_of(outcome)
    assert packet["role"] == "repair" and packet["faults"]
    failed = harness.ws.load().passes_for("write")[0]
    handed = {i["hash"] for i in packet["inputs"]} | {i["hash"] for i in packet.get("cited_evidence", [])}
    assert not handed & set(failed.outputs.values())
    assert "prior_outputs" not in packet


# --- C7 / C8 proof pack ----------------------------------------------------------------


def test_c7a_proof_pack_has_every_required_entry(tmp_path):
    harness, _, _ = to_completed(tmp_path)
    pack = read_json(tmp_path / WS / "artifact" / "proof_pack.json")
    for key in ("spec", "decisions", "integrity", "gates", "criteria_coverage", "statements", "loop", "identities", "evidence"):
        assert key in pack, key
    assert pack["integrity"]["ok"] and pack["status"] == "completed" and pack["stop"]["reason"] == "converged"
    assert pack["identities"]["steps"]["write"] and pack["statements"]["pointers_broken"] == 0


def test_c7b_every_statement_has_a_provenance_pointer(tmp_path):
    harness, agent, _ = to_d0(tmp_path, write=partial(write_brief, drop_pointer="s2"))
    agent.drive(harness.decide("D0", "accept"))
    result = next(r for r in harness.ws.load().gate_results if r.gate == "pointer-resolution")
    assert result.verdict.value == "fail" and any(f.statement == "s2" for f in result.findings)


def test_c8_layers_are_rendered_separately(tmp_path):
    _, _, _ = to_completed(tmp_path)
    rendered = (tmp_path / WS / "artifact" / "proof_pack.md").read_text()
    assert "Layer 1" in rendered and "Layer 2" in rendered and "Layer 3" in rendered
    assert "overall score" not in rendered.lower() and "aggregate" not in rendered.lower()


# --- C9 adaptivity ----------------------------------------------------------------------


def test_c9a_plan_changes_do_not_stale_d0_criteria_changes_do(tmp_path):
    harness, agent, _ = to_d0(tmp_path)
    outcome = harness.plan_skip("curate")
    assert outcome.kind is OutcomeKind.NEEDS_DECISION and outcome.decision["id"] == "D0" and not outcome.decision["stale"]
    assert harness.inspect()["plan_ops"][0]["op"] == "skip"
    outcome = agent.drive(harness.decide("D0", "accept"), until=lambda packet: packet["step"] == "write")
    assert "core_set.csv" not in {i["name"] for i in Agent.packet_of(outcome)["inputs"]}  # the skipped input is absent
    harness, _, _ = to_d0(tmp_path / "edited")
    spec_path = tmp_path / "edited" / WS / "success_spec.yaml"
    data = yaml.safe_load(spec_path.read_text())
    data["criteria"][1]["text"] = "Every statement is supported by two sources."
    spec_path.write_text(yaml.safe_dump(data, sort_keys=False))
    outcome = harness.continue_()
    assert outcome.decision["id"] == "D0-2" and {d["id"]: d["stale"] for d in harness.inspect()["decisions"]}["D0"]


def test_c9b_gates_bind_to_criteria_not_step_position(tmp_path):
    harness, agent, _ = to_d0(tmp_path, annotate=lambda packet, out: (out / "notes.csv").write_text("id,note\na,ok\n"))
    harness.plan_add(yaml.safe_dump({"id": "annotate", "skill": "curate-fixture", "consumes": ["sources/"], "produces": ["notes.csv"], "serves": ["coverage"], "after": "retrieve"}))
    order = [s["step"] for s in harness.inspect()["plan"]]
    assert order == ["spec", "retrieve", "annotate", "curate", "write"]
    outcome = agent.drive(harness.decide("D0", "accept"))
    assert outcome.decision["id"] == "D-final"
    write_gates = {g["gate"] for g in harness.inspect()["gates"] if g["step"] == "write"}
    assert write_gates == {"pointer-resolution", "provenance-present", "scaffold-absent", "schema-valid", "source-support", "spec-coverage"}


# --- C10 Lessons and evolve ------------------------------------------------------------------


def test_c10a_a_lesson_is_distilled_from_every_ended_run(tmp_path):
    project = tmp_path / "project"
    to_completed(tmp_path / "done", project)

    harness, agent, _ = to_d0(tmp_path / "dropped", project)
    outcome = harness.decide("D0", "accept")
    outcome = harness.escalate("sources unavailable")
    assert outcome.kind is OutcomeKind.BLOCKED
    assert harness.decide(outcome.decision["id"], "abandon").kind is OutcomeKind.COMPLETED

    harness, agent, _ = to_d0(tmp_path / "spent", project, spec=partial(write_spec, budget={"passes_per_gate": 1}), write=partial(write_brief, scaffold=True))
    outcome = agent.drive(harness.decide("D0", "accept"))
    assert outcome.stop["reason"] == "exhausted"
    harness.decide(outcome.decision["id"], "abandon")

    items = lessons.list_lessons(project)
    assert sorted(i["status"] for i in items) == ["abandoned", "abandoned", "completed"]
    for item in items:
        lesson = lessons.load_lesson(project, item["run_id"])
        assert lesson["artifact"].get("proof_pack")


def test_c10b_evolve_is_replay_verified_and_decision_gated(tmp_path):
    project = tmp_path / "project"
    flaky = iter(["fail", "pass", "pass"])

    def once_unsupported(packet, out):
        verdict = next(flaky)
        findings = [] if verdict == "pass" else [{"message": "s1 overreaches", "evidence": [inputs_by_name(packet)["sources/a.md"]], "statement": "s1", "criterion": "C2"}]
        gate_result(packet, out, verdict, 0.5 if findings else 1.0, findings)

    _, _, done = to_completed(tmp_path / "agent-gate", project, **{"source-support": once_unsupported})
    uncaught = lessons.propose(project, "gate:source-support", [done.run_id], "tighten the support prover")
    replayed = lessons.replay(project, uncaught)
    assert all(r["caught"] is None for r in replayed["results"])
    with pytest.raises(ValueError):
        lessons.adopt(project, uncaught, by="maintainer")

    attempts = iter([True, False, False])
    _, _, done = to_completed(tmp_path / "kernel-gate", project, write=lambda p, o: write_brief(p, o, scaffold=next(attempts)))
    caught = lessons.propose(project, "gate:scaffold-absent", [done.run_id], "the marker check stays")
    replayed = lessons.replay(project, caught)
    assert replayed["results"] and all(r["caught"] is True for r in replayed["results"])
    assert lessons._read_json(lessons._proposal_path(project, caught), "proposal")["status"] == "proposed"
    adopted = lessons.adopt(project, caught, by="maintainer")
    assert adopted["status"] == "adopted" and adopted["adopted_by"] == "maintainer"


def test_intermediate_decision_is_raised_after_its_step_and_rejection_repairs_it(tmp_path):
    harness, agent = fresh(tmp_path)
    outcome = agent.drive(harness.start(GOAL, "review-fixture"))
    outcome = agent.drive(harness.decide("D0", "accept"))
    assert outcome.kind is OutcomeKind.NEEDS_DECISION and outcome.decision["id"] == "D-sources"
    assert [e["name"] for e in outcome.decision["basis"]] == ["retrieve#1:sources/a.md", "retrieve#1:sources/b.md"]
    outcome = harness.decide("D-sources", "reject", reason="source b is off-topic")
    packet = Agent.packet_of(outcome)
    assert packet["step"] == "retrieve" and packet["role"] == "repair" and packet["faults"][0]["ground"] == "human"
    outcome = agent.drive(outcome)
    assert outcome.decision["id"] == "D-sources-2"
    outcome = agent.drive(harness.decide("D-sources-2", "accept"))
    assert outcome.decision["id"] == "D-final"


# --- surface ------------------------------------------------------------------------------------


def test_outcomes_are_exactly_the_four(tmp_path):
    harness, agent = fresh(tmp_path)
    seen = {harness.start(GOAL, "brief-fixture").kind}
    outcome = agent.drive(harness.continue_())
    seen.add(outcome.kind)
    outcome = agent.drive(harness.decide("D0", "accept"))
    seen.add(harness.decide("D-final", "accept").kind)
    assert seen == {OutcomeKind.PROGRESSED, OutcomeKind.NEEDS_DECISION, OutcomeKind.COMPLETED}
    assert {k.value for k in OutcomeKind} == {"NEEDS_DECISION", "BLOCKED", "PROGRESSED", "COMPLETED"}
    assert harness.continue_().kind is OutcomeKind.COMPLETED
    assert write_core_set  # the fixture agent's default curate behaviour stays importable
