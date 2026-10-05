"""Canonical revisions stale historical D0 records without reusing their answers."""

from copy import deepcopy

import pytest
import yaml
from agent_stub import Agent, to_d0, write_spec

from rh.api import HarnessError, OutcomeKind
from rh.kernel.records import encode


@pytest.mark.parametrize("changed", [True, False])
def test_lawful_revision_preserves_answer_and_requires_fresh_d0(tmp_path, changed):
    harness, agent, _ = to_d0(tmp_path)
    harness.decide("D0", "accept", by="synthetic test operator")
    previous = deepcopy(encode(harness.ws.load().decision("D0")))
    old_hash = harness.ws.load().spec_hash
    stopped = harness.escalate("reconsider the criteria")
    repair = harness.decide(stopped.decision["id"], "revise", reason="review the bounded question")
    assert not harness.ws.load().decision("D0").stale
    packet = agent.perform(repair)
    path = harness.ws.pass_dir(packet["pass_id"]) / "outputs/success_spec.yaml"
    if changed:
        data = yaml.safe_load(path.read_text())
        data["criteria"][0]["text"] = "Answer the revised stopping question."
        path.write_text(yaml.safe_dump(data, sort_keys=False))
    waiting = harness.continue_()
    state = harness.ws.load()
    assert (state.spec_hash != old_hash) is changed
    historical = encode(state.decision("D0"))
    assert historical.pop("stale") is changed
    previous.pop("stale")
    assert historical == previous
    assert ("Stale:" in (harness.ws.decisions / "D0.md").read_text()) is changed
    assert waiting.kind is OutcomeKind.NEEDS_DECISION
    assert waiting.decision["id"] == "D0-2"
    assert harness.continue_().decision["id"] == "D0-2"
    with pytest.raises(HarnessError, match="already answered"):
        harness.decide("D0", "accept")
    assert harness.ws.load().pending_decision().id == "D0-2"
    assert harness.decide("D0-2", "accept").kind is OutcomeKind.PROGRESSED


def test_invalid_revision_does_not_stale_accepted_d0(tmp_path):
    harness, agent, _ = to_d0(tmp_path)
    harness.decide("D0", "accept")
    stopped = harness.escalate("reconsider the criteria")
    repair = harness.decide(stopped.decision["id"], "revise", reason="review again")
    packet = Agent.packet_of(repair)
    write_spec(packet, harness.ws.pass_dir(packet["pass_id"]) / "outputs", criteria=[])
    harness.continue_()
    assert not harness.ws.load().decision("D0").stale
    assert harness.ws.load().decision("D0-2") is None
