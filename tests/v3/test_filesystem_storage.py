from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from research_harness.application import (
    ApproveCheckpoint,
    BeginAttempt,
    CompleteAttempt,
    CreateRun,
    Harness,
    InMemoryAcceptance,
)
from research_harness.domain import (
    AcceptanceEvidence,
    ArtifactEvidence,
    CompletionManifest,
    Goal,
    HarnessRevision,
    ManifestStatus,
    Owner,
    RunPlan,
    UnitPlan,
)
from research_harness.domain.model import RunAggregate
from research_harness.storage import (
    ConcurrentStorageInvocationError,
    ConcurrentStorageWriteError,
    FilesystemArtifacts,
    FilesystemRunLedger,
    InvalidArtifactPathError,
    InvalidManifestTransitionError,
    ManifestConflictError,
    StorageCorruptionError,
    StorageIdentityError,
    StorageIOError,
)


def _revision() -> HarnessRevision:
    return HarnessRevision(
        pipeline_digest="pipeline-digest",
        kernel_digest="kernel-digest",
    )


def _plan(*, run_label: str = "fixture") -> RunPlan:
    return RunPlan(
        goal=Goal(
            id=f"goal-{run_label}",
            request="Exercise durable local storage",
            workflow="fixture-workflow",
            target_artifacts=("output/report.md",),
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Write report",
                skill="writer",
                outputs=("output/report.md",),
            ),
            UnitPlan(
                id="U020",
                title="Review report",
                skill="human-checkpoint",
                depends_on=("U010",),
                inputs=("output/report.md", "DECISIONS.md"),
                outputs=("DECISIONS.md",),
                owner=Owner.HUMAN,
                checkpoint="C1",
            ),
        ),
    )


def _aggregate(run_id: str) -> RunAggregate:
    return RunAggregate.create(
        run_id=run_id, plan=_plan(run_label=run_id), revision=_revision()
    )


def _manifest(
    *,
    manifest_id: str = "manifest-1",
    run_id: str = "run-1",
    status: ManifestStatus = ManifestStatus.PREPARED,
) -> CompletionManifest:
    artifact = ArtifactEvidence(
        path="output/report.md",
        sha256=hashlib.sha256(b"report\n").hexdigest(),
        size=7,
    )
    return CompletionManifest(
        id=manifest_id,
        completion_id=f"completion-{manifest_id}",
        run_id=run_id,
        unit_id="U010",
        attempt_id=f"attempt-{manifest_id}",
        status=status,
        artifacts=(artifact,),
        acceptance=AcceptanceEvidence(passed=True, checks=("writer",)),
    )


def test_ledger_round_trips_the_full_aggregate_and_discovers_identity(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ledger = FilesystemRunLedger(workspace)
    artifacts = FilesystemArtifacts(workspace)
    harness = Harness(
        ledger=ledger,
        artifacts=artifacts,
        acceptance=InMemoryAcceptance(),
        revision=_revision(),
    )

    harness.execute(CreateRun(run_id="run-full", plan=_plan()))
    first = harness.execute(BeginAttempt(run_id="run-full", unit_id="U010"))
    (workspace / "output").mkdir()
    (workspace / "output" / "report.md").write_text("report\n", encoding="utf-8")
    harness.execute(CompleteAttempt(run_id="run-full", attempt_id=first.attempt_id))
    (workspace / "DECISIONS.md").write_text(
        "- [x] Approve C1\n"
        "<!-- BEGIN CHECKPOINT:C1 -->\nreviewed\n"
        "<!-- END CHECKPOINT:C1 -->\n",
        encoding="utf-8",
    )
    harness.execute(ApproveCheckpoint(run_id="run-full", checkpoint="C1"))
    second = harness.execute(BeginAttempt(run_id="run-full", unit_id="U020"))
    harness.execute(CompleteAttempt(run_id="run-full", attempt_id=second.attempt_id))

    restarted = FilesystemRunLedger(workspace)
    loaded = restarted.load("run-full")
    assert loaded is not None
    assert restarted.current_run_id() == "run-full"
    assert loaded.view() == harness.inspect("run-full")
    assert loaded.approvals
    assert loaded.completions
    payload = json.loads((workspace / ".harness-v3" / "state.json").read_text())
    assert payload["schema"] == "research-harness.run-aggregate/v1"
    assert not tuple((workspace / ".harness-v3").glob(".*.tmp"))


def test_ledger_enforces_one_run_and_optimistic_append_only_versions(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ledger = FilesystemRunLedger(workspace)
    first = _aggregate("run-one")
    ledger.save(first, expected_version=0)

    with pytest.raises(StorageIdentityError):
        ledger.save(_aggregate("run-two"), expected_version=0)
    with pytest.raises(StorageIdentityError):
        ledger.load("run-two")

    stale = ledger.load("run-one")
    current = ledger.load("run-one")
    assert stale is not None and current is not None
    current.begin_attempt(unit_id="U010", attempt_id="attempt-current")
    ledger.save(current, expected_version=2)
    stale.begin_attempt(unit_id="U010", attempt_id="attempt-stale")
    with pytest.raises(ConcurrentStorageWriteError):
        ledger.save(stale, expected_version=2)

    rewritten = ledger.load("run-one")
    assert rewritten is not None
    rewritten.events[0] = replace(rewritten.events[0], kind="rewritten")
    rewritten.fail_attempt(attempt_id="attempt-current", reason="retry")
    with pytest.raises(ConcurrentStorageWriteError, match="append-only"):
        ledger.save(rewritten, expected_version=3)


def test_failed_atomic_replace_preserves_the_prior_canonical_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ledger = FilesystemRunLedger(workspace)
    original = _aggregate("run-one")
    ledger.save(original, expected_version=0)
    advanced = ledger.load("run-one")
    assert advanced is not None
    advanced.begin_attempt(unit_id="U010", attempt_id="attempt-one")

    def fail_replace(source: object, destination: object) -> None:
        del source, destination
        raise OSError("injected replace failure")

    monkeypatch.setattr("research_harness.storage.filesystem.os.replace", fail_replace)
    with pytest.raises(StorageIOError, match="Atomic"):
        ledger.save(advanced, expected_version=2)

    restarted = FilesystemRunLedger(workspace)
    loaded = restarted.load("run-one")
    assert loaded is not None
    assert loaded.version == original.version
    assert loaded.attempts == []
    assert not tuple((workspace / ".harness-v3").glob("*.tmp"))


def test_workspace_lock_is_nonblocking_reentrant_and_process_scoped(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    owner = FilesystemRunLedger(workspace)
    contender = FilesystemRunLedger(workspace)

    with owner.lock("run-one", "outer"):
        with owner.lock("run-one", "inner"):
            with pytest.raises(ConcurrentStorageInvocationError):
                with contender.lock("run-one", "contender"):
                    pytest.fail("contender unexpectedly acquired the lock")

    with contender.lock("run-one", "after-release"):
        pass
    assert (workspace / ".harness-v3" / "invocation.lock").is_file()
    assert contender.current_run_id() is None


def test_corrupt_or_symlinked_canonical_state_fails_closed(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ledger = FilesystemRunLedger(workspace)
    ledger.save(_aggregate("run-one"), expected_version=0)
    state = workspace / ".harness-v3" / "state.json"
    state.write_text("{broken", encoding="utf-8")
    with pytest.raises(StorageCorruptionError):
        ledger.current_run_id()

    state.unlink()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    state.symlink_to(outside)
    with pytest.raises(StorageCorruptionError):
        ledger.current_run_id()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda payload: payload.update({"future": True}), "unexpected future"),
        (
            lambda payload: payload["attempts"][0].update({"skill": "other-skill"}),
            "Skill disagrees",
        ),
        (
            lambda payload: payload["unit_status"].update({"U010": "TODO"}),
            "must be DOING",
        ),
    ],
)
def test_codec_rejects_cross_field_and_unknown_field_corruption(
    tmp_path: Path,
    mutate: object,
    message: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ledger = FilesystemRunLedger(workspace)
    run = _aggregate("run-one")
    run.begin_attempt(unit_id="U010", attempt_id="attempt-one")
    ledger.save(run, expected_version=0)
    state = workspace / ".harness-v3" / "state.json"
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert callable(mutate)
    mutate(payload)
    state.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(StorageCorruptionError, match=message):
        ledger.current_run_id()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: payload["attempts"][0].update(
                {"status": "FAILED_RETRYABLE"}
            ),
            "requires a SUCCEEDED Attempt",
        ),
        (
            lambda payload: payload["completions"][0]["artifacts"].append(
                dict(payload["completions"][0]["artifacts"][0])
            ),
            "Artifact paths must be unique",
        ),
        (
            lambda payload: payload["events"][1]["details"].append(
                list(payload["events"][1]["details"][0])
            ),
            "detail keys must be unique",
        ),
    ],
)
def test_codec_rejects_committed_and_duplicate_evidence_corruption(
    tmp_path: Path,
    mutate: object,
    message: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ledger = FilesystemRunLedger(workspace)
    run = _aggregate("run-one")
    run.begin_attempt(unit_id="U010", attempt_id="attempt-one")
    artifact = ArtifactEvidence(
        path="output/report.md",
        sha256=hashlib.sha256(b"report\n").hexdigest(),
        size=7,
    )
    run.prepare_completion(
        completion_id="completion-one",
        attempt_id="attempt-one",
        manifest_id="manifest-one",
        artifacts=(artifact,),
        acceptance=AcceptanceEvidence(passed=True, checks=("writer",)),
    )
    run.succeed_prepared_attempt("completion-one")
    run.commit_completion("completion-one")
    ledger.save(run, expected_version=0)
    state = workspace / ".harness-v3" / "state.json"
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert callable(mutate)
    mutate(payload)
    state.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(StorageCorruptionError, match=message):
        ledger.current_run_id()


def test_manifests_are_atomic_idempotent_and_listed_by_run(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifacts = FilesystemArtifacts(workspace)
    first = _manifest()
    other = _manifest(manifest_id="manifest-2", run_id="run-2")

    artifacts.write_manifest(first)
    artifacts.write_manifest(first)
    artifacts.write_manifest(other)
    assert artifacts.read_manifest(first.id) == first
    assert artifacts.list_manifests("run-1") == (first,)
    assert artifacts.list_manifests("run-2") == (other,)

    with pytest.raises(ManifestConflictError):
        artifacts.write_manifest(replace(first, status=ManifestStatus.DONE))
    artifacts.set_manifest_status(first.id, ManifestStatus.BLOCKED)
    blocked = artifacts.read_manifest(first.id)
    assert blocked is not None and blocked.status is ManifestStatus.BLOCKED
    with pytest.raises(InvalidManifestTransitionError):
        artifacts.set_manifest_status(first.id, ManifestStatus.DONE)
    manifest_dir = workspace / ".harness-v3" / "manifests"
    assert not tuple(manifest_dir.glob("*.tmp"))


def test_manifest_encoder_rejects_invalid_in_memory_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifacts = FilesystemArtifacts(workspace)
    invalid = replace(_manifest(), run_id="")

    with pytest.raises(StorageCorruptionError, match="run_id must be non-empty"):
        artifacts.write_manifest(invalid)
    assert not (workspace / ".harness-v3" / "manifests").exists()


def test_artifact_hashing_is_deterministic_for_files_and_directories(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    output = workspace / "output"
    output.mkdir()
    (output / "b.txt").write_text("bbb", encoding="utf-8")
    (output / "a.txt").write_text("a", encoding="utf-8")
    artifacts = FilesystemArtifacts(workspace)

    file_evidence, directory_evidence = artifacts.snapshot(
        "run-one", ("output/a.txt", "output/")
    )
    assert file_evidence.sha256 == hashlib.sha256(b"a").hexdigest()
    assert file_evidence.size == 1
    assert directory_evidence.path == "output/"
    assert directory_evidence.size == 4
    assert directory_evidence.normalization == "directory-tree-sha256.v1"
    assert artifacts.snapshot("run-one", ("output/",))[0] == directory_evidence

    (output / "a.txt").write_text("changed", encoding="utf-8")
    changed = artifacts.snapshot("run-one", ("output/",))[0]
    assert changed.sha256 != directory_evidence.sha256
    assert changed.size == 10


def test_harness_storage_is_never_an_artifact(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "artifact.txt").write_text("stable", encoding="utf-8")
    artifacts = FilesystemArtifacts(workspace)
    ledger = FilesystemRunLedger(workspace)
    ledger.save(_aggregate("run-one"), expected_version=0)
    artifacts.write_manifest(_manifest(run_id="run-one"))
    with pytest.raises(InvalidArtifactPathError):
        artifacts.snapshot("run-one", (".harness-v3/state.json",))


@pytest.mark.parametrize(
    "unsafe_path",
    (".", "a/./b", "a//b", "a/../b", "output//"),
)
def test_artifact_paths_reject_raw_dot_and_empty_segments(
    tmp_path: Path, unsafe_path: str
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifacts = FilesystemArtifacts(workspace)

    with pytest.raises(InvalidArtifactPathError):
        artifacts.snapshot("run-one", (unsafe_path,))


def test_artifact_paths_and_descendant_symlinks_cannot_escape_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    artifacts = FilesystemArtifacts(workspace)

    (workspace / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(InvalidArtifactPathError):
        artifacts.snapshot("run-one", ("escape/secret.txt",))

    safe = workspace / "safe"
    safe.mkdir()
    (safe / "escape.txt").symlink_to(outside / "secret.txt")
    with pytest.raises(InvalidArtifactPathError):
        artifacts.snapshot("run-one", ("safe/",))


def test_checkpoint_basis_matches_in_memory_normalization_semantics(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    decisions = workspace / "DECISIONS.md"
    decisions.write_text(
        "- [x] Approve C1\n"
        "<!-- BEGIN CHECKPOINT:C1 -->\nreviewed v1\n"
        "<!-- END CHECKPOINT:C1 -->\n"
        "- [ ] Approve C2\n"
        "<!-- BEGIN CHECKPOINT:C2 -->\nother\n"
        "<!-- END CHECKPOINT:C2 -->\n",
        encoding="utf-8",
    )
    artifacts = FilesystemArtifacts(workspace)
    approved = artifacts.checkpoint_review_basis(
        run_id="run-one",
        checkpoint="C1",
        unit_id="U020",
        paths=("DECISIONS.md",),
    )

    decisions.write_text(
        decisions.read_text(encoding="utf-8")
        .replace("[x] Approve C1", "[ ] Approve C1")
        .replace("other", "unrelated change"),
        encoding="utf-8",
    )
    unchecked = artifacts.checkpoint_review_basis(
        run_id="run-one",
        checkpoint="C1",
        unit_id="U020",
        paths=("DECISIONS.md",),
    )
    assert approved.approved is True
    assert unchecked.approved is False
    assert approved.artifacts == unchecked.artifacts

    decisions.write_text(
        decisions.read_text(encoding="utf-8").replace("reviewed v1", "reviewed v2"),
        encoding="utf-8",
    )
    changed = artifacts.checkpoint_review_basis(
        run_id="run-one",
        checkpoint="C1",
        unit_id="U020",
        paths=("DECISIONS.md",),
    )
    assert changed.artifacts != unchecked.artifacts
