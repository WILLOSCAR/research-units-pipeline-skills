"""Readable projections are diagnosed without writes and recovered without losing edits."""

import json

import pytest
import yaml
from agent_stub import to_completed, to_d0, to_d_final

from rh.kernel.evidence import EvidenceCorrupt
from rh.kernel.artifact import ArtifactError
from rh.kernel.records import encode


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("ended", ["completed", "abandoned"])
@pytest.mark.parametrize("name", ["goal.md", "success_spec.yaml", "artifact/brief.md", "artifact/statements.json", "artifact/proof_pack.json", "artifact/proof_pack.md", "gate"])
@pytest.mark.parametrize("damage", ["edit", "remove"])
def test_terminal_projection_recovery_preserves_authority_and_edits(tmp_path, ended, name, damage):
    harness, _, _ = to_d_final(tmp_path)
    if ended == "completed":
        harness.decide("D-final", "accept")
    else:
        stopped = harness.escalate("synthetic test stop")
        harness.decide(stopped.decision["id"], "abandon")
    ws = harness.ws
    path = next(ws.gates.glob("*.json")) if name == "gate" else ws.root / name
    original = path.read_bytes()
    if damage == "edit":
        path.write_bytes(b"user edits retained exactly\xff")
    else:
        path.unlink()
    before = snapshot(ws.root)
    authority = encode(ws.load())
    evidence = snapshot(ws.evidence.root)
    lessons = snapshot(harness.project)
    problems = harness.inspect()["integrity"]
    assert any(str(path.relative_to(ws.root)) in p and "projection" in p for p in problems)
    assert snapshot(ws.root) == before  # inspect is read-only, even for malformed JSON
    resumed = harness.continue_()
    assert "restored" in resumed.message
    after = encode(ws.load())
    for key in ("version", "updated_at"):
        authority.pop(key)
        after.pop(key)
    assert after == authority
    assert snapshot(ws.evidence.root) == evidence
    assert snapshot(harness.project) == lessons
    if name == "gate":
        assert json.loads(path.read_bytes()) == json.loads(original)
    else:
        assert path.read_bytes() == original
    saved = list((ws.root / "projection-edits").rglob(path.name))
    assert len(saved) == (1 if damage == "edit" else 0)
    if saved:
        assert saved[0].read_bytes() == b"user edits retained exactly\xff"
    assert harness.inspect()["integrity"] == []
    harness.continue_()
    assert list((ws.root / "projection-edits").rglob(path.name)) == saved


def test_accepted_spec_projection_is_not_an_unconfirmed_revision(tmp_path):
    harness, _, _ = to_d0(tmp_path)
    harness.decide("D0", "accept")
    path = harness.ws.root / "success_spec.yaml"
    original = path.read_bytes()
    data = yaml.safe_load(original)
    data["criteria"][0]["text"] = "Unapproved replacement question"
    path.write_text(yaml.safe_dump(data))
    edited = path.read_bytes()
    harness.continue_()
    assert path.read_bytes() == original
    assert harness.ws.load().decision("D0-2") is None
    assert not harness.ws.load().decision("D0").stale
    assert any(p.read_bytes() == edited for p in (harness.ws.root / "projection-edits").rglob(path.name))


def test_pending_d0_edit_still_requests_revision_decision(tmp_path):
    harness, _, _ = to_d0(tmp_path)
    path = harness.ws.root / "success_spec.yaml"
    data = yaml.safe_load(path.read_text())
    data["criteria"][0]["text"] = "A revised bounded question"
    path.write_text(yaml.safe_dump(data))
    assert harness.continue_().decision["id"] == "D0-2"
    assert harness.ws.load().decision("D0").stale


def test_pending_final_review_edit_is_backed_up_before_restore(tmp_path):
    harness, _, _ = to_d_final(tmp_path)
    path = harness.ws.artifact / "brief.md"
    path.write_bytes(b"a human's draft changes")
    assert harness.decide("D-final", "accept").decision["id"] == "D-final"
    assert any(p.read_bytes() == b"a human's draft changes" for p in (harness.ws.root / "projection-edits").rglob(path.name))


def test_corrupt_restore_source_refuses_before_any_projection_write(tmp_path):
    harness, _, _ = to_completed(tmp_path)
    (harness.ws.root / "goal.md").write_text("edited goal")
    (harness.ws.artifact / "brief.md").write_text("edited deliverable")
    digest = harness.ws.load().artifact["deliverable"]
    (harness.ws.evidence.objects / digest).write_text("corrupt CAS")
    before = snapshot(harness.ws.root)
    with pytest.raises(EvidenceCorrupt):
        harness.continue_()
    assert snapshot(harness.ws.root) == before


def test_gate_formatting_is_not_a_semantic_edit(tmp_path):
    harness, _, _ = to_completed(tmp_path)
    path = next(harness.ws.gates.glob("*.json"))
    path.write_text(json.dumps(json.loads(path.read_text()), sort_keys=True))
    assert harness.inspect()["integrity"] == []
    harness.continue_()
    assert not (harness.ws.root / "projection-edits").exists()


@pytest.mark.parametrize("obstruction", ["file_symlink", "parent_symlink", "directory", "backup_symlink"])
def test_recovery_refuses_nonregular_paths_without_destroying_them(tmp_path, obstruction):
    harness, _, _ = to_completed(tmp_path)
    ws = harness.ws
    path = ws.artifact / "brief.md"
    outside = tmp_path / "user-files"
    outside.mkdir()
    (outside / "brief.md").write_text("external original")
    if obstruction == "file_symlink":
        path.unlink()
        path.symlink_to(outside / "brief.md")
    elif obstruction == "parent_symlink":
        ws.artifact.rename(ws.root / "saved-artifact")
        ws.artifact.symlink_to(outside, target_is_directory=True)
    elif obstruction == "directory":
        path.unlink()
        path.mkdir()
        (path / "user.txt").write_text("retain this")
    else:
        path.write_text("an edited draft")
        (ws.root / "projection-edits").symlink_to(outside, target_is_directory=True)
    before, external = snapshot(ws.root), snapshot(outside)
    assert harness.inspect()["integrity"]
    with pytest.raises(ArtifactError, match="regular"):
        harness.continue_()
    assert snapshot(ws.root) == before
    assert snapshot(outside) == external


def test_missing_pending_spec_is_restored_without_revision(tmp_path):
    harness, _, _ = to_d0(tmp_path)
    path = harness.ws.root / "success_spec.yaml"
    original = path.read_bytes()
    path.unlink()
    assert harness.continue_().decision["id"] == "D0"
    assert path.read_bytes() == original
    assert not harness.ws.load().decision("D0").stale


def test_gate_hash_field_edit_is_detected_and_restored(tmp_path):
    harness, _, _ = to_completed(tmp_path)
    path = next(harness.ws.gates.glob("*.json"))
    original = json.loads(path.read_text())
    path.write_text(json.dumps({**original, "hash": "forged"}))
    assert harness.inspect()["integrity"]
    harness.continue_()
    assert json.loads(path.read_text()) == original
