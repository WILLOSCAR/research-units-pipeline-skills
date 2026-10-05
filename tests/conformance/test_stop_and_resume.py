"""Stop Decisions and what a pass may cite: the corners of REBUILD_DESIGN §7.6–7.7 the checklist rows leave implicit.

Every test drives the fixture kind with the scripted agent, as ``test_conformance`` does.
"""

from __future__ import annotations

import json
from functools import partial

from agent_stub import Agent, gate_result, inputs_by_name, to_d0, write_brief, write_spec

from rh.api import OutcomeKind
from rh.kernel import steps
from rh.kernel.records import PassStatus


def test_successful_steps_stop_at_the_total_budget_and_resume_after_extension(tmp_path):
    harness, agent, _ = to_d0(tmp_path, spec=partial(write_spec, budget={"passes_total": 1}))

    blocked = harness.decide("D0", "accept")

    assert blocked.kind is OutcomeKind.BLOCKED
    assert blocked.stop["reason"] == "exhausted"
    assert blocked.decision["options"] == ["extend", "revise", "abandon"]
    before = harness.ws.load()
    assert before.passes_used == before.budget.passes_total == 1
    assert before.pending_pass is None
    assert not before.passes_for("retrieve")

    # Repeated resume calls keep the same stop and do not spend more passes.
    assert harness.continue_().decision["id"] == blocked.decision["id"]
    assert harness.ws.load().passes == before.passes
    assert len(harness.ws.load().decisions) == len(before.decisions)

    resumed = harness.decide(blocked.decision["id"], "extend", extend=3)
    assert Agent.packet_of(resumed)["pass_id"] == "retrieve#1"
    review = agent.drive(resumed)
    assert review.decision["id"] == "D-final"
    assert harness.ws.load().passes_used == harness.ws.load().budget.passes_total == 4


def test_verification_and_final_review_are_allowed_exactly_at_the_total_budget(tmp_path):
    harness, agent, _ = to_d0(tmp_path, spec=partial(write_spec, budget={"passes_total": 4}))

    review = agent.drive(harness.decide("D0", "accept"))

    assert review.kind is OutcomeKind.NEEDS_DECISION
    assert review.decision["id"] == "D-final"
    state = harness.ws.load()
    assert state.passes_used == state.budget.passes_total == 4
    assert len(state.passes) > state.passes_used  # Prover passes do not consume the production budget.
    assert not any(d.id.startswith("D-budget") for d in state.decisions)
    assert harness.decide("D-final", "accept", by="test operator").kind is OutcomeKind.COMPLETED


def to_write_repair(tmp_path):
    """A Run whose ``write`` step failed pointer-resolution and holds an open repair packet."""
    harness, agent, _ = to_d0(tmp_path, write=partial(write_brief, drop_pointer="s1"))
    outcome = agent.drive_to_repair(harness.decide("D0", "accept"))
    packet = Agent.packet_of(outcome)
    assert packet["step"] == "write" and packet["role"] == "repair"
    return harness, agent, outcome


def test_escalation_reviews_the_latest_outputs_of_the_step_in_progress(tmp_path):
    harness, agent, outcome = to_write_repair(tmp_path)
    failed = harness.ws.load().passes_for("write")[0]

    blocked = harness.escalate("the sources do not settle the question")

    assert blocked.kind is OutcomeKind.BLOCKED and blocked.stop["reason"] == "escalated"
    assert blocked.stop["pass_id"] == Agent.packet_of(outcome)["pass_id"]
    reviewed = {e["name"]: e["hash"] for e in blocked.decision["basis"]}
    assert reviewed == {f"{failed.id}:{name}": digest for name, digest in failed.outputs.items()}


def test_escalation_before_any_output_reviews_the_spec(tmp_path):
    harness, agent, _ = to_d0(tmp_path)
    outcome = harness.decide("D0", "accept")  # retrieve#1 is open; retrieve has produced nothing yet

    blocked = harness.escalate("no source is reachable")

    assert blocked.stop["pass_id"] == Agent.packet_of(outcome)["pass_id"]
    assert [e["name"] for e in blocked.decision["basis"]] == ["goal.md", "success_spec.yaml"]


def test_extend_after_an_escalation_resumes_the_open_packet(tmp_path):
    harness, agent, outcome = to_write_repair(tmp_path)
    open_id = Agent.packet_of(outcome)["pass_id"]
    before = harness.ws.load()

    blocked = harness.escalate("need a human")
    resumed = harness.decide(blocked.decision["id"], "extend", extend=2)

    assert resumed.kind is OutcomeKind.PROGRESSED and resumed.packet == outcome.packet
    after = harness.ws.load()
    assert [p.id for p in after.passes if p.status is PassStatus.OPEN] == [open_id]
    assert after.passes_used == before.passes_used
    assert after.budget.passes_total == before.budget.passes_total + 2
    assert after.status.value == "running" and after.stop is None
    agent.behaviours["write"] = write_brief  # the repair now succeeds and the Loop carries on from the same packet
    assert agent.drive(resumed).decision["id"] == "D-final"


def test_a_pass_cites_only_what_the_kernel_gave_it_not_what_its_packet_says(tmp_path):
    harness, agent, _ = to_d0(tmp_path)
    foreign = harness.ws.load().goal.hash  # in the store, never handed to `write`

    def launders(packet, out):
        write_brief(packet, out)
        statements = json.loads((out / "statements.json").read_text())
        statements["statements"][0]["evidence"][0]["hash"] = foreign
        (out / "statements.json").write_text(json.dumps(statements))
        packet["inputs"].append({"name": "goal.md", "path": "inputs/goal.md", "hash": foreign})
        (out.parent / "packet.json").write_text(json.dumps(packet))

    agent.behaviours["write"] = launders
    outcome = agent.drive_to_repair(harness.decide("D0", "accept"))

    faults = harness.inspect()["open_faults"]
    assert [f["gate"] for f in faults] == ["pointer-resolution"]
    assert f"cites evidence {foreign[:12]} the step was not given" in faults[0]["message"]
    assert Agent.packet_of(outcome)["role"] == "repair"


def test_repair_excludes_its_own_prior_outputs_even_when_a_prover_cites_them(tmp_path):
    def cite_failed_text(packet, out):
        hashes = inputs_by_name(packet)
        gate_result(packet, out, verdict="fail", score=0.5, findings=[{
            "message": "s1 overstates the cited source; re-derive it from the source.",
            "evidence": [hashes["brief.md"], hashes["statements.json"], hashes["sources/a.md"]],
            "statement": "s1", "criterion": "C2",
        }])

    harness, agent, _ = to_d0(tmp_path, **{"source-support": cite_failed_text})
    outcome = agent.drive_to_repair(harness.decide("D0", "accept"))
    packet = Agent.packet_of(outcome)
    state = harness.ws.load()
    failed = state.passes_for("write")[0]
    excluded = set(failed.outputs.values())
    source = inputs_by_name(packet)["sources/a.md"]

    assert excluded <= set(packet["faults"][0]["evidence"])
    assert packet["faults"][0]["message"].startswith("s1 overstates")
    assert {item["hash"] for item in packet["cited_evidence"]} == {source}
    evidence_dir = harness.ws.pass_dir(packet["pass_id"]) / "inputs/evidence"
    assert {p.name for p in evidence_dir.iterdir()} == {source[:16]}
    repair = state.get_pass(packet["pass_id"])
    assert not excluded & steps.given_hashes(state, repair)

    # The repaired statements cannot launder the excluded draft back into provenance.
    agent.perform(outcome)
    output = harness.ws.pass_dir(repair.id) / "outputs/statements.json"
    data = json.loads(output.read_text())
    data["statements"][0]["evidence"][0]["hash"] = failed.outputs["brief.md"]
    output.write_text(json.dumps(data))
    again = harness.continue_()
    assert Agent.packet_of(again)["role"] == "repair"
    assert any("the step was not given" in f["message"] for f in harness.inspect()["open_faults"])
    state = harness.ws.load()
    next_repair = state.get_pass(Agent.packet_of(again)["pass_id"])
    prior = {h for p in state.passes_for("write") if p.n < next_repair.n for h in p.outputs.values()}
    assert not prior & steps.given_hashes(state, next_repair)
