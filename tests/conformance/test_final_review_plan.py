"""The plan cannot change behind a final Artifact Decision or after a Run ends."""

from __future__ import annotations

import pytest
import yaml

from agent_stub import to_d0, to_d_final

from rh.api import HarnessError, OutcomeKind


def annotation_step() -> str:
    return yaml.safe_dump({
        "id": "annotate",
        "skill": "curate-fixture",
        "consumes": ["sources/"],
        "produces": ["notes.csv"],
        "serves": ["coverage"],
        "after": "retrieve",
    })


def test_adding_a_step_during_final_review_is_refused_without_changing_the_run(tmp_path):
    harness, _, review = to_d_final(tmp_path)
    before = harness.ws.run_json.read_bytes()
    trace = harness.ws.trace.read_bytes()

    with pytest.raises(HarnessError, match="final review"):
        harness.plan_add(annotation_step())

    assert harness.ws.run_json.read_bytes() == before
    assert harness.ws.trace.read_bytes() == trace
    assert harness.inspect()["pending_decision"]["id"] == review.decision["id"]
    assert harness.decide(review.decision["id"], "accept").kind is OutcomeKind.COMPLETED


def test_rejecting_final_review_reopens_the_plan_for_bounded_changes(tmp_path):
    harness, _, review = to_d_final(tmp_path)
    harness.decide(review.decision["id"], "reject", reason="Add source annotations before revising the brief.")

    outcome = harness.plan_add(annotation_step())

    assert outcome.kind is OutcomeKind.PROGRESSED
    assert harness.ws.load().plan.get("annotate").status.value == "pending"
    assert harness.ws.load().pending_decision() is None


def test_repeated_final_review_also_refuses_plan_changes(tmp_path):
    harness, agent, review = to_d_final(tmp_path)
    repair = harness.decide(review.decision["id"], "reject", reason="Review the wording once more.")
    review = agent.drive(repair)
    assert review.decision["id"] == "D-final-2"
    before = harness.ws.run_json.read_bytes()

    with pytest.raises(HarnessError, match="reject D-final-2"):
        harness.plan_add(annotation_step())

    assert harness.ws.run_json.read_bytes() == before


@pytest.mark.parametrize("ending", ["completed", "abandoned"])
def test_an_ended_run_refuses_new_plan_steps(tmp_path, ending):
    if ending == "completed":
        harness, _, review = to_d_final(tmp_path)
        harness.decide(review.decision["id"], "accept")
    else:
        harness, _, _ = to_d0(tmp_path)
        harness.decide("D0", "accept")
        blocked = harness.escalate("Stop this validation Run.")
        harness.decide(blocked.decision["id"], "abandon")
    before = harness.ws.run_json.read_bytes()

    with pytest.raises(HarnessError, match="plan cannot be changed"):
        harness.plan_add(annotation_step())

    assert harness.ws.run_json.read_bytes() == before


def test_an_abandoned_run_refuses_skipping_an_unworked_step(tmp_path):
    harness, _, _ = to_d0(tmp_path)
    harness.decide("D0", "accept")
    blocked = harness.escalate("Stop before curating sources.")
    harness.decide(blocked.decision["id"], "abandon")
    before = harness.ws.run_json.read_bytes()
    assert harness.ws.load().plan.get("curate").status.value == "pending"

    with pytest.raises(HarnessError, match="plan cannot be changed"):
        harness.plan_skip("curate")

    assert harness.ws.run_json.read_bytes() == before
