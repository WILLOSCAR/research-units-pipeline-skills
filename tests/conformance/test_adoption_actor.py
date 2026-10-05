"""Adoption requires a nonblank audit actor; this does not authenticate a human."""

from functools import partial

import pytest
from agent_stub import to_d0, write_brief

from rh.cli import main
from rh.kernel import lessons


def candidate(tmp_path):
    harness, agent, _ = to_d0(tmp_path, write=partial(write_brief, scaffold=True))
    repair = agent.drive_to_repair(harness.decide("D0", "accept"))
    agent.behaviours["write"] = write_brief
    final = agent.drive(repair)
    harness.decide(final.decision["id"], "accept", by="synthetic test operator")
    project = harness.project
    evolve_id = lessons.propose(project, "gate:scaffold-absent", [harness.ws.load().run_id], "synthetic replay control")
    assert all(row["caught"] is True for row in lessons.replay(project, evolve_id)["results"])
    return project, evolve_id


def snapshot(project):
    return {str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()}


@pytest.mark.parametrize("actor", ["", " ", "\t\n", "\u2003", None, 42])
def test_adoption_rejects_blank_or_nonstring_actor_without_writes(tmp_path, actor):
    project, evolve_id = candidate(tmp_path)
    before = snapshot(project)
    with pytest.raises(ValueError, match="nonblank actor"):
        lessons.adopt(project, evolve_id, by=actor)
    assert snapshot(project) == before


@pytest.mark.parametrize("actor", ["", " \t "])
def test_cli_rejects_blank_actor_without_writes(tmp_path, capsys, actor):
    project, evolve_id = candidate(tmp_path)
    before = snapshot(project)
    code = main(["--project", str(project), "lessons", "evolve", "adopt", evolve_id, "--by", actor])
    assert code == 2
    assert "nonblank actor" in capsys.readouterr().err
    assert snapshot(project) == before


def test_nonblank_actor_is_recorded_verbatim_as_a_label(tmp_path):
    project, evolve_id = candidate(tmp_path)
    actor = " synthetic test operator "
    adopted = lessons.adopt(project, evolve_id, by=actor)
    assert adopted["status"] == "adopted"
    assert adopted["adopted_by"] == actor
