"""A Run cannot silently cross kernel, kind or Skill contracts (ADRs 0018/0020/0026)."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from shutil import copytree

import pytest
import yaml
from agent_stub import Agent, FIXTURES, GOAL, write_brief

from rh.api import Harness, HarnessError


def fresh_contract(root, **behaviours):
    copytree(FIXTURES / "skills", root / "skills")
    copytree(FIXTURES / "kinds", root / "kinds")
    harness = Harness(root / "ws", skills_root=root / "skills", kinds_dir=root / "kinds", project=root / "project")
    return harness, Agent(harness, **behaviours)


def tree_bytes(root: Path):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_open_writer_skill_drift_cannot_pass_old_scaffold_under_old_identity(tmp_path):
    h, agent = fresh_contract(tmp_path, write=partial(write_brief, scaffold=True))
    agent.drive(h.start(GOAL, "brief-fixture"))
    opened = agent.drive(h.decide("D0", "accept"), until=lambda p: p["step"] == "write")
    agent.perform(opened)
    path = tmp_path / "skills/writer-fixture/SKILL.md"
    original = path.read_bytes()
    path.write_bytes(original.replace(b"<!-- scaffold -->", b"<!-- changed-marker -->"))
    before = tree_bytes(h.ws.root)
    with pytest.raises(HarnessError, match="execution contract"):
        h.continue_()
    assert tree_bytes(h.ws.root) == before
    path.write_bytes(original)
    repaired = h.continue_()
    assert Agent.packet_of(repaired)["role"] == "repair"
    assert h.ws.load().latest_result("write", "scaffold-absent").verdict.value == "fail"


def test_kind_drift_cannot_remove_required_intermediate_decision(tmp_path):
    h, agent = fresh_contract(tmp_path)
    agent.drive(h.start(GOAL, "review-fixture"))
    opened = h.decide("D0", "accept")
    agent.perform(opened)
    path = tmp_path / "kinds/review-fixture.yaml"
    original = path.read_bytes()
    changed = yaml.safe_load(original)
    changed["decisions"] = []
    path.write_text(yaml.safe_dump(changed))
    before = tree_bytes(h.ws.root)
    with pytest.raises(HarnessError, match="execution contract"):
        h.continue_()
    assert tree_bytes(h.ws.root) == before
    path.write_bytes(original)
    assert h.continue_().decision["id"] == "D-sources"


def _at_d0(root):
    h, agent = fresh_contract(root)
    agent.drive(h.start(GOAL, "brief-fixture"))
    return h, agent


def _mutation(h, command):
    return {
        "continue": h.continue_,
        "decide": lambda: h.decide("D0", "accept"),
        "skip": lambda: h.plan_skip("curate"),
        "add": lambda: h.plan_add("id: extra\nskill: retrieve-fixture\nafter: retrieve\nproduces: [extra.md]\n"),
        "escalate": lambda: h.escalate("need a judgment"),
    }[command]()


@pytest.mark.parametrize("command", ["continue", "decide", "skip", "add", "escalate"])
@pytest.mark.parametrize("drift", ["kernel", "kind", "skill", "unpinned"])
def test_every_mutation_refuses_before_any_workspace_write(tmp_path, monkeypatch, command, drift):
    import json

    from rh.kernel import contracts

    h, _ = _at_d0(tmp_path)
    if drift == "kernel":
        changed = {**contracts.kernel_manifest(), "kernel/loop.py": "0" * 64}
        monkeypatch.setattr(contracts, "kernel_manifest", lambda: changed)
    elif drift == "kind":
        path = tmp_path / "kinds/brief-fixture.yaml"
        path.write_text(path.read_text() + "\n# different exact contract bytes\n")
    elif drift == "skill":
        path = tmp_path / "skills/support-prover-fixture/SKILL.md"
        path.write_text(path.read_text() + "\nChanged prover rules.\n")
    else:
        data = json.loads(h.ws.run_json.read_text())
        del data["execution_contract"]
        h.ws.run_json.write_text(json.dumps(data))
    before = tree_bytes(h.ws.root)
    with pytest.raises(HarnessError, match="execution contract"):
        _mutation(h, command)
    report = h.inspect()
    assert report["execution_contract"]["status"] == ("unpinned" if drift == "unpinned" else "drift")
    assert report["integrity"]
    assert tree_bytes(h.ws.root) == before


@pytest.mark.parametrize("target", ["kind", "producer", "prover"])
@pytest.mark.parametrize("damage", ["missing", "malformed"])
def test_inspection_uses_recorded_kind_when_current_contract_files_are_unusable(tmp_path, target, damage):
    h, agent = _at_d0(tmp_path)
    final = agent.drive(h.decide("D0", "accept"))
    assert final.decision["id"] == "D-final"
    path = {
        "kind": tmp_path / "kinds/brief-fixture.yaml",
        "producer": tmp_path / "skills/writer-fixture/SKILL.md",
        "prover": tmp_path / "skills/support-prover-fixture/SKILL.md",
    }[target]
    original = path.read_bytes()
    if damage == "missing":
        path.unlink()
    else:
        path.write_text("---\nrole: [malformed\n---\n")
    artifact_path = h.ws.artifact / "brief.md"
    artifact_path.write_text("edited projection")
    before = tree_bytes(h.ws.root)
    report = h.inspect()
    assert report["execution_contract"]["status"] == "drift"
    assert report["reviewed_changed"] == ["brief.md"]
    assert report["pending_decision"]["id"] == "D-final"
    with pytest.raises(HarnessError, match="execution contract"):
        h.decide("D-final", "accept")
    assert tree_bytes(h.ws.root) == before
    path.write_bytes(original)
    assert "restored" in h.continue_().message
    assert h.decide("D-final", "accept").kind.value == "COMPLETED"


@pytest.mark.parametrize("stage", ["producer", "prover", "repair"])
def test_resumed_process_preserves_each_pass_identity_after_skill_restoration(tmp_path, stage):
    h, agent = fresh_contract(tmp_path, write=partial(write_brief, scaffold=stage == "repair"))
    agent.drive(h.start(GOAL, "brief-fixture"))
    opened = agent.drive(h.decide("D0", "accept"), until=lambda p: p["role"] == stage if stage != "producer" else p["step"] == "write")
    packet = Agent.packet_of(opened)
    assert packet["role"] == stage
    if stage == "repair":
        agent.behaviours["write"] = write_brief
    agent.perform(opened)
    path = Path(packet["skill"]["path"])
    original = path.read_bytes()
    path.write_bytes(original + b"\nChanged contract.\n")
    resumed = Harness(h.ws.root, skills_root=h.skills.root, kinds_dir=h.kinds_dir, project=h.project)
    before = tree_bytes(h.ws.root)
    with pytest.raises(HarnessError, match="execution contract"):
        resumed.continue_()
    assert tree_bytes(h.ws.root) == before
    path.write_bytes(original)
    agent.harness = resumed
    final = agent.drive(resumed.continue_())
    assert final.decision["id"] == "D-final"
    state = resumed.ws.load()
    assert state.get_pass(packet["pass_id"]).skill_identity == packet["skill"]["identity"]
    assert not resumed.inspect()["integrity"]


def test_plan_add_pins_new_skill_without_rebinding_d0_and_skip_still_works(tmp_path):
    import json

    h, agent = _at_d0(tmp_path)
    copytree(tmp_path / "skills/curate-fixture", tmp_path / "skills/extra-skill")
    path = tmp_path / "skills/extra-skill/SKILL.md"
    path.write_text(path.read_text() + "\nAdditional curation.\n")
    before = h.ws.load()
    h.plan_skip("curate")
    h.plan_add("id: extra\nskill: extra-skill\nafter: retrieve\nconsumes: [sources/]\nproduces: [extra.md]\n")
    state = h.ws.load()
    assert state.spec_hash == before.spec_hash and not state.decision("D0").stale
    assert state.execution_contract.kernel == before.execution_contract.kernel
    assert state.execution_contract.kind_hash == before.execution_contract.kind_hash
    assert state.execution_contract.skills["extra-skill"] == h.skills.load("extra-skill").identity
    assert state.plan.ops[-1].detail["skill_identity"] == state.execution_contract.skills["extra-skill"]
    original = path.read_bytes()
    path.write_bytes(original + b"changed again")
    with pytest.raises(HarnessError, match="extra-skill"):
        h.decide("D0", "accept")
    path.write_bytes(original)
    agent.behaviours["extra"] = lambda packet, out: (out / "extra.md").write_text("Extra source notes.\n")
    final = agent.drive(h.decide("D0", "accept"))
    assert final.decision["id"] == "D-final"
    assert h.decide("D-final", "accept").kind.value == "COMPLETED"
    pack = json.loads((h.ws.artifact / "proof_pack.json").read_text())
    assert pack["identities"]["skills"]["extra-skill"] == state.execution_contract.skills["extra-skill"]
    assert pack["identities"]["kernel_files"] == state.execution_contract.kernel
    assert pack["identities"]["kind"] == state.execution_contract.kind_hash
    for pass_ in h.ws.load().passes:
        assert pack["identities"]["passes"][pass_.id] == pass_.skill_identity


def test_adding_a_step_cannot_make_prover_verify_identical_skill(tmp_path):
    h, agent = fresh_contract(tmp_path)
    path = tmp_path / "kinds/brief-fixture.yaml"
    data = yaml.safe_load(path.read_text())
    data["gates"]["agent"][0]["applies_to"] = ["all"]
    path.write_text(yaml.safe_dump(data))
    agent.drive(h.start(GOAL, "brief-fixture"))
    before = tree_bytes(h.ws.root)
    with pytest.raises(HarnessError, match="verify itself"):
        h.plan_add("id: extra\nskill: support-prover-fixture\nafter: retrieve\nproduces: [extra.md]\n")
    assert tree_bytes(h.ws.root) == before


@pytest.mark.parametrize("damage", ["schema", "kind_hash", "missing_skill_pin", "pass_identity"])
def test_malformed_or_incomplete_recorded_contract_is_not_rebound(tmp_path, damage):
    import json

    h, _ = _at_d0(tmp_path)
    data = json.loads(h.ws.run_json.read_text())
    if damage == "schema":
        data["execution_contract"]["schema"] = "rh.execution_contract/999"
    elif damage == "kind_hash":
        data["execution_contract"]["kind_hash"] = "0" * 64
    elif damage == "missing_skill_pin":
        del data["execution_contract"]["skills"]["writer-fixture"]
    else:
        data["passes"][0]["skill_identity"] = "0" * 64
    h.ws.run_json.write_text(json.dumps(data))
    before = tree_bytes(h.ws.root)
    assert h.inspect()["execution_contract"]["status"] == "drift"
    with pytest.raises(HarnessError, match="execution contract"):
        h.decide("D0", "accept")
    assert tree_bytes(h.ws.root) == before


@pytest.mark.parametrize("pin", [True, False])
def test_completed_history_remains_read_only_and_keeps_its_evidence_verdict(tmp_path, pin):
    import json

    h, agent = _at_d0(tmp_path)
    agent.drive(h.decide("D0", "accept"))
    h.decide("D-final", "accept")
    if not pin:
        data = json.loads(h.ws.run_json.read_text())
        del data["execution_contract"]
        h.ws.run_json.write_text(json.dumps(data))
    (tmp_path / "kinds/brief-fixture.yaml").unlink()
    (tmp_path / "skills/writer-fixture/SKILL.md").unlink()
    before = tree_bytes(tmp_path)
    report = h.inspect()
    assert report["status"] == "completed"
    assert report["execution_contract"]["status"] == ("drift" if pin else "unpinned")
    assert report["integrity"] == []
    assert report["artifact"] and report["decisions"][-1]["outcome"] == "accept"
    assert tree_bytes(tmp_path) == before


def test_unrelated_kind_and_skill_edits_do_not_change_selected_contract(tmp_path):
    h, agent = _at_d0(tmp_path)
    (tmp_path / "kinds/review-fixture.yaml").write_text("invalid unrelated kind")
    (tmp_path / "skills/unrelated").mkdir()
    (tmp_path / "skills/unrelated/SKILL.md").write_text("---\ninvalid: [\n---\n")
    assert h.inspect()["execution_contract"]["status"] == "match"
    assert agent.drive(h.decide("D0", "accept")).decision["id"] == "D-final"


@pytest.mark.parametrize("change", ["edit", "add", "remove"])
def test_kernel_source_manifest_fails_closed_and_restored_bytes_resume(tmp_path, monkeypatch, change):
    from rh.kernel import contracts

    copied = tmp_path / "runtime/rh"
    copytree(contracts.KERNEL_ROOT, copied)
    monkeypatch.setattr(contracts, "KERNEL_ROOT", copied)
    h, agent = _at_d0(tmp_path)
    target = copied / "kernel/loop.py"
    original = target.read_bytes()
    if change == "edit":
        target.write_bytes(original + b"\n# changed runtime\n")
    elif change == "add":
        target = copied / "kernel/new_rule.py"
        target.write_text("# newly loaded policy\n")
    else:
        target.unlink()
    before = tree_bytes(h.ws.root)
    with pytest.raises(HarnessError, match="kernel source"):
        h.decide("D0", "accept")
    assert tree_bytes(h.ws.root) == before
    assert h.inspect()["execution_contract"]["status"] == "drift"
    if change == "add":
        target.unlink()
    else:
        target.write_bytes(original)
    assert agent.drive(h.decide("D0", "accept")).decision["id"] == "D-final"


def test_kernel_identity_ignores_repository_docs_tests_and_unselected_kinds(tmp_path, monkeypatch):
    from rh.kernel import contracts

    copied = tmp_path / "repo/src/rh"
    copytree(contracts.KERNEL_ROOT, copied)
    monkeypatch.setattr(contracts, "KERNEL_ROOT", copied)
    before = contracts.kernel_manifest()
    (tmp_path / "repo/README.md").write_text("documentation edited")
    (tmp_path / "repo/tests").mkdir()
    (tmp_path / "repo/tests/test_new.py").write_text("test edits")
    (copied / "kinds/brief.yaml").write_text("kind is bound separately")
    assert contracts.kernel_manifest() == before
    assert "api.py" in before and "kernel/gates.py" in before and "kernel/contracts.py" in before


def test_sources_changed_since_import_cannot_pin_a_new_run(tmp_path, monkeypatch):
    from rh.kernel import contracts

    h, _ = fresh_contract(tmp_path)
    monkeypatch.setattr(contracts, "LOADED_KERNEL", {**contracts.LOADED_KERNEL, "kernel/loop.py": "0" * 64})
    with pytest.raises(HarnessError, match="kernel changed after import"):
        h.start(GOAL, "brief-fixture")
    assert not h.ws.root.exists()


def test_loaded_kernel_must_match_even_when_on_disk_bytes_are_restored(tmp_path, monkeypatch):
    from rh.kernel import contracts

    h, _ = _at_d0(tmp_path)
    monkeypatch.setattr(contracts, "LOADED_KERNEL", {**contracts.LOADED_KERNEL, "kernel/loop.py": "0" * 64})
    before = tree_bytes(h.ws.root)
    with pytest.raises(HarnessError, match="kernel source"):
        h.decide("D0", "accept")
    assert tree_bytes(h.ws.root) == before


@pytest.mark.parametrize("completed", [False, True])
def test_kernel_version_label_must_match_recorded_execution_identity(tmp_path, completed):
    import json

    h, agent = _at_d0(tmp_path)
    if completed:
        agent.drive(h.decide("D0", "accept"))
        h.decide("D-final", "accept")
    original = h.ws.run_json.read_bytes()
    data = json.loads(original)
    data["execution_contract"]["kernel_version"] = "not-the-runtime"
    h.ws.run_json.write_text(json.dumps(data))
    before = tree_bytes(tmp_path)
    report = h.inspect()
    assert report["execution_contract"]["status"] == "drift"
    assert any("kernel version" in problem for problem in report["execution_contract"]["problems"])
    # Completed history keeps its recorded Evidence verdict; drift describes
    # execution compatibility rather than rewriting historical acceptance.
    assert bool(report["integrity"]) is not completed
    with pytest.raises(HarnessError, match="kernel version"):
        h.continue_() if completed else h.decide("D0", "accept")
    assert tree_bytes(tmp_path) == before
    h.ws.run_json.write_bytes(original)
    assert h.inspect()["execution_contract"]["status"] == "match"
    if not completed:
        agent.drive(h.decide("D0", "accept"))
        h.decide("D-final", "accept")
    pack = json.loads((h.ws.artifact / "proof_pack.json").read_text())
    assert pack["identities"]["kernel"] == json.loads(original)["execution_contract"]["kernel_version"]
