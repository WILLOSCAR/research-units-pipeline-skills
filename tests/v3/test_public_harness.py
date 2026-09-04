from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import research_harness
import research_harness.case as case_module
import research_harness.harness as harness_module
from research_harness import (
    Loop,
    LoopFault,
    LoopKind,
    LoopQualityState,
    LoopState,
    Continue,
    Decide,
    Start,
)
from research_harness.application import InMemoryAcceptance
from research_harness.domain import Goal, HarnessRevision, RunPlan, RunStatus, UnitPlan
from research_harness.engine import AdvanceRun, CreateLocalRun, LocalRunEngine
from research_harness.harness import (
    Advance as InternalAdvance,
    Approve as InternalApprove,
    Create as InternalCreate,
    ResearchHarness as InternalResearchHarness,
)
from research_harness.skills import InMemorySkillAdapter, SkillContext
from tooling.product_cli import main as legacy_cli_main


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_audit_payload(workspace: Path) -> dict:
    """Build a schema-valid run-audit.v2 payload for `workspace`.

    Hand-writing one is impractical — the schema has a deeply nested required
    shape, and an invalid payload makes `audit-diff` exit before it reaches the
    write path, which would make the guard look effective when it is not.
    """
    from tooling.harness import build_run_audit_payload, validate_run_audit_payload

    _, payload = build_run_audit_payload(workspace=workspace, repo_root=REPO_ROOT)
    assert validate_run_audit_payload(payload) == [], "fixture payload must be valid"
    return payload


def _create_current_case(
    workspace: Path,
    *,
    workflow: str = "paper-review",
    case_id: str = "current-case",
) -> None:
    InternalResearchHarness.open(workspace, repository=REPO_ROOT).execute(
        InternalCreate(
            workflow=workflow,
            goal="Review the supplied manuscript",
            run_id=case_id,
        )
    )


def _create_completed_case(
    workspace: Path,
    *,
    fail_once: bool = False,
    leave_active: bool = False,
) -> None:
    workspace.mkdir()
    outputs = (
        "output/VIEW.md",
        "output/SOURCES.jsonl",
        "output/REQUIRED.json",
        "DECISIONS.md",
    )
    target_artifacts = (*outputs, "output/FINAL.md") if leave_active else outputs
    units = [
        UnitPlan(
            id="U010",
            title="Build Loop",
            skill="fixture-writer",
            outputs=outputs,
        )
    ]
    if leave_active:
        units.append(
            UnitPlan(
                id="U020",
                title="Finalize Loop",
                skill="fixture-writer",
                depends_on=("U010",),
                outputs=("output/FINAL.md",),
            )
        )
    plan = RunPlan(
        goal=Goal(
            id="goal-completed-case",
            request="Exercise completed Loop freshness",
            workflow="fixture-recipe",
            target_artifacts=target_artifacts,
        ),
        units=tuple(units),
    )

    calls = 0

    def write(context: SkillContext) -> None:
        nonlocal calls
        calls += 1
        if fail_once and calls == 1:
            raise RuntimeError("transient fixture failure")
        for raw_path in context.outputs:
            path = workspace / raw_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"evidence for {raw_path}\n", encoding="utf-8")

    engine = LocalRunEngine.for_workspace(
        workspace,
        skill_adapters={
            "fixture-writer": InMemorySkillAdapter(
                handler=write,
                adapter="fixture:writer",
            )
        },
        acceptance=InMemoryAcceptance(),
        revision=HarnessRevision(
            pipeline_digest="fixture-pipeline",
            kernel_digest="fixture-kernel",
        ),
    )
    engine.execute(CreateLocalRun(plan=plan, run_id="completed-case"))
    engine.execute(AdvanceRun(unit_id="U010"))
    if fail_once:
        engine.execute(AdvanceRun())
    contracts = workspace / ".harness-v3" / "contracts"
    contracts.mkdir()
    (contracts / "workflow.json").write_text(
        json.dumps(
            {
                "schema": "research-harness.workflow-snapshot/v2",
                "name": "fixture-recipe",
                "target_artifacts": list(target_artifacts),
                "case_contract": {
                    "kind": "review",
                    "views": ["output/VIEW.md"],
                    "claim_sources": ["output/SOURCES.jsonl"],
                    "evidence_sources": ["output/SOURCES.jsonl"],
                    "decision_sources": ["DECISIONS.md"],
                },
            }
        ),
        encoding="utf-8",
    )


class _DeterministicStopHarness:
    """Run only Create, then emulate the next engine-level meaningful stop."""

    def __init__(self, workspace: Path) -> None:
        self._delegate = InternalResearchHarness.open(
            workspace,
            repository=REPO_ROOT,
        )
        self.current = self._delegate.inspect()
        self.commands: list[object] = []

    def inspect(self):
        return self.current

    def execute(self, command):
        self.commands.append(command)
        if isinstance(command, InternalCreate):
            created = self._delegate.execute(command)
            self.current = created.inspection
            return SimpleNamespace(issues=created.issues)
        if isinstance(command, InternalAdvance):
            assert self.current.run is not None
            self.current = replace(
                self.current,
                run=replace(self.current.run, status=RunStatus.BLOCKED),
                issues=(
                    "Skill adapter 'private' failed with SkillProcessError. "
                    "exit_code=1 stderr='A manuscript is required.\\n'",
                ),
            )
            return SimpleNamespace(issues=self.current.issues)
        raise AssertionError(type(command).__name__)


def test_package_exports_only_the_case_first_interface() -> None:
    assert set(research_harness.__all__) == {
        "Loop",
        "LoopArtifact",
        "LoopDetails",
        "LoopFault",
        "LoopInspection",
        "LoopKind",
        "LoopQuality",
        "LoopQualitySignal",
        "LoopQualityState",
        "LoopResult",
        "LoopState",
        "Continue",
        "Decide",
        "PendingDecision",
        "Start",
    }
    assert not hasattr(research_harness, "ResearchHarness")
    assert not hasattr(research_harness, "Advance")
    assert not hasattr(research_harness, "Recover")


def test_inspecting_an_absent_workspace_is_read_only_and_empty(tmp_path: Path) -> None:
    workspace = tmp_path / "not-created"

    inspection = Loop.open(workspace).inspect()

    assert inspection.state is LoopState.EMPTY
    assert inspection.case_id == ""
    assert inspection.details is None
    assert inspection.normalized_claims_available is False
    assert inspection.quality.execution_integrity.status is LoopQualityState.UNVERIFIED
    assert inspection.quality.contract_acceptance.status is LoopQualityState.PENDING
    assert inspection.quality.research_quality.status is LoopQualityState.NOT_EVALUATED
    assert not workspace.exists()


def test_start_creates_then_works_until_a_meaningful_stop(tmp_path: Path) -> None:
    workspace = tmp_path / "review"
    case = Loop.open(workspace, repository=REPO_ROOT)
    harness = _DeterministicStopHarness(workspace)
    case._harness = harness

    result = case.advance(
        Start(
            goal="Review the supplied manuscript",
            kind=LoopKind.REVIEW,
            case_id="case-first",
        )
    )

    assert result.state is LoopState.BLOCKED
    assert result.inspection.case_id == "case-first"
    assert result.inspection.kind is LoopKind.REVIEW
    assert result.inspection.details is None
    expanded = case.inspect(details=True)
    assert expanded.details is not None
    assert expanded.details.workflow == "paper-review"
    assert expanded.details.attempts == 0
    assert result.inspection.normalized_claims_available is False
    assert (
        result.inspection.quality.execution_integrity.status
        is LoopQualityState.VERIFIED
    )
    assert (
        result.inspection.quality.contract_acceptance.status is LoopQualityState.BLOCKED
    )
    assert (
        result.inspection.quality.research_quality.status
        is LoopQualityState.NOT_EVALUATED
    )
    assert not hasattr(result, "unit_ids")
    assert not hasattr(result, "attempt_ids")
    assert not hasattr(result, "recovered")
    assert all("adapter" not in issue.lower() for issue in result.issues)
    assert result.issues == (
        "A private Recipe step stopped: A manuscript is required.",
    )
    assert [type(command) for command in harness.commands] == [
        InternalCreate,
        InternalAdvance,
    ]


def test_continue_advances_to_a_meaningful_stop_without_unit_input(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "review"
    _create_current_case(workspace, case_id="continue-case")
    case = Loop.open(workspace, repository=REPO_ROOT)
    harness = _DeterministicStopHarness(workspace)
    case._harness = harness

    result = case.advance(Continue())

    assert result.state is LoopState.BLOCKED
    assert result.inspection.details is None
    expanded = case.inspect(details=True)
    assert expanded.details is not None
    assert expanded.details.attempts == 0
    assert result.issues == (
        "A private Recipe step stopped: A manuscript is required.",
    )
    assert [type(command) for command in harness.commands] == [InternalAdvance]


def test_formats_are_narrow_and_never_silently_ignored(tmp_path: Path) -> None:
    with pytest.raises(LoopFault) as non_survey:
        Loop.open(tmp_path / "review", repository=REPO_ROOT).advance(
            Start("Review", LoopKind.REVIEW, formats=("pdf",))
        )
    assert non_survey.value.code == "invalid_formats"
    assert not (tmp_path / "review").exists()

    with pytest.raises(LoopFault) as unknown:
        Loop.open(tmp_path / "survey", repository=REPO_ROOT).advance(
            Start("Survey", LoopKind.SURVEY, formats=("docx",))
        )
    assert unknown.value.code == "invalid_formats"
    assert not (tmp_path / "survey").exists()


def test_survey_pdf_selects_the_existing_latex_workflow(tmp_path: Path) -> None:
    workspace = tmp_path / "survey"
    case = Loop.open(workspace, repository=REPO_ROOT)
    harness = _DeterministicStopHarness(workspace)
    case._harness = harness

    result = case.advance(
        Start(
            "Survey retrieval-augmented generation",
            LoopKind.SURVEY,
            formats=("pdf",),
            case_id="latex-case",
        )
    )

    assert result.inspection.kind is LoopKind.SURVEY
    assert result.inspection.details is None
    expanded = case.inspect(details=True)
    assert expanded.details is not None
    assert expanded.details.workflow == "arxiv-survey-latex"
    assert result.state is LoopState.BLOCKED
    assert isinstance(harness.commands[0], InternalCreate)
    assert harness.commands[0].workflow == "arxiv-survey-latex"
    assert isinstance(harness.commands[1], InternalAdvance)


def test_case_projects_pinned_artifacts_with_role_digest_and_size(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "review"
    _create_current_case(workspace, case_id="artifact-case")
    view = workspace / "output" / "REVIEW.md"
    view.parent.mkdir(parents=True, exist_ok=True)
    content = b"# Review\n\nEvidence-backed finding.\n"
    view.write_bytes(content)

    inspection = Loop.open(workspace).inspect()

    assert inspection.state is LoopState.WORKING
    assert inspection.kind is LoopKind.REVIEW
    assert inspection.views == (
        research_harness.LoopArtifact(
            path="output/REVIEW.md",
            role="views",
            exists=True,
            sha256=hashlib.sha256(content).hexdigest(),
            size=len(content),
        ),
    )
    assert inspection.claim_sources[0].role == "claim_sources"
    assert inspection.claim_sources[0].exists is False
    assert inspection.evidence_sources[0].role == "evidence_sources"
    assert inspection.decision_sources[0].role == "decision_sources"
    assert inspection.normalized_claims_available is False
    assert inspection.quality.execution_integrity.status is LoopQualityState.VERIFIED


def test_artifact_projection_refuses_symbolic_links(tmp_path: Path) -> None:
    workspace = tmp_path / "review"
    _create_current_case(workspace, case_id="artifact-link")
    outside = tmp_path / "outside.md"
    outside.write_text("not Loop Evidence", encoding="utf-8")
    projected = workspace / "output" / "REVIEW.md"
    projected.parent.mkdir(parents=True, exist_ok=True)
    projected.symlink_to(outside)

    with pytest.raises(LoopFault) as caught:
        Loop.open(workspace).inspect()

    assert caught.value.code == "unsafe_artifact"


@pytest.mark.parametrize(
    "removed",
    ("output/VIEW.md", "output/REQUIRED.json", "manifest"),
)
def test_completed_case_rechecks_all_committed_evidence_and_manifests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    removed: str,
) -> None:
    workspace = tmp_path / "completed"
    _create_completed_case(workspace)
    monkeypatch.setattr(harness_module, "inspection_contract_issues", lambda **_: ())
    monkeypatch.setattr(case_module, "inspection_contract_issues", lambda **_: ())
    case = Loop.open(workspace)

    ready = case.inspect()
    assert ready.state is LoopState.READY
    assert ready.quality.execution_integrity.status is LoopQualityState.VERIFIED
    assert ready.quality.contract_acceptance.status is LoopQualityState.PASSED

    if removed == "manifest":
        next((workspace / ".harness-v3" / "manifests").glob("*.json")).unlink()
    else:
        (workspace / removed).unlink()

    stale = case.inspect()
    assert stale.state is LoopState.BLOCKED
    assert stale.quality.execution_integrity.status is LoopQualityState.UNVERIFIED
    assert stale.quality.contract_acceptance.status is LoopQualityState.BLOCKED
    assert stale.issues


def test_recovered_attempt_history_does_not_block_a_completed_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "recovered"
    _create_completed_case(workspace, fail_once=True)
    monkeypatch.setattr(harness_module, "inspection_contract_issues", lambda **_: ())
    monkeypatch.setattr(case_module, "inspection_contract_issues", lambda **_: ())

    inspection = Loop.open(workspace).inspect()

    assert inspection.state is LoopState.READY
    assert inspection.issues == ()


def test_active_case_still_verifies_existing_completion_manifests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "active"
    _create_completed_case(workspace, leave_active=True)
    monkeypatch.setattr(harness_module, "inspection_contract_issues", lambda **_: ())
    monkeypatch.setattr(case_module, "inspection_contract_issues", lambda **_: ())
    case = Loop.open(workspace)
    assert case.inspect().state is LoopState.WORKING

    next((workspace / ".harness-v3" / "manifests").glob("*.json")).unlink()

    inspection = case.inspect()
    assert inspection.state is LoopState.BLOCKED
    assert inspection.quality.execution_integrity.status is LoopQualityState.UNVERIFIED
    assert any("Manifest" in issue for issue in inspection.issues)


def test_case_reports_detached_manifest_recovery_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "orphan"
    _create_completed_case(workspace)
    monkeypatch.setattr(harness_module, "inspection_contract_issues", lambda **_: ())
    monkeypatch.setattr(case_module, "inspection_contract_issues", lambda **_: ())
    manifests = workspace / ".harness-v3" / "manifests"
    payload = json.loads(next(manifests.glob("*.json")).read_text(encoding="utf-8"))
    payload["id"] = "detached-manifest"
    payload["status"] = "PREPARED"
    (manifests / "detached-manifest.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    inspection = Loop.open(workspace).inspect()

    assert inspection.state is LoopState.BLOCKED
    assert inspection.quality.execution_integrity.status is LoopQualityState.UNVERIFIED
    assert any("detached Completion Manifest" in issue for issue in inspection.issues)


@pytest.mark.parametrize(
    ("mutation", "expected_issue"),
    (
        ("v1", "does not support"),
        ("undeclared", "undeclared target"),
        ("wrong-kind", "disagrees"),
    ),
)
def test_case_reader_revalidates_pinned_projection_semantics(
    tmp_path: Path,
    mutation: str,
    expected_issue: str,
) -> None:
    workspace = tmp_path / mutation
    contracts = workspace / ".harness-v3" / "contracts"
    contracts.mkdir(parents=True)
    payload = {
        "schema": "research-harness.workflow-snapshot/v2",
        "name": "paper-review",
        "target_artifacts": ["output/VIEW.md"],
        "case_contract": {
            "kind": "review",
            "views": ["output/VIEW.md"],
            "claim_sources": ["output/VIEW.md"],
            "evidence_sources": ["output/VIEW.md"],
            "decision_sources": ["output/VIEW.md"],
        },
    }
    if mutation == "v1":
        payload["schema"] = "research-harness.workflow-snapshot/v1"
    elif mutation == "undeclared":
        payload["case_contract"]["views"] = ["output/OTHER.md"]
    else:
        payload["case_contract"]["kind"] = "tutorial"
    (contracts / "workflow.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    contract, issues = case_module._read_case_contract(
        workspace,
        expected_workflow="paper-review",
    )

    assert contract is None
    assert any(expected_issue in issue for issue in issues)


def test_case_reader_preserves_a_question_style_decision_prompt(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "question-decision"
    contracts = workspace / ".harness-v3" / "contracts"
    contracts.mkdir(parents=True)
    (contracts / "workflow.json").write_text(
        json.dumps(
            {
                "schema": "research-harness.workflow-snapshot/v2",
                "name": "paper-review",
                "target_artifacts": ["DECISIONS.md"],
                "case_contract": {
                    "kind": "review",
                    "views": ["DECISIONS.md"],
                    "claim_sources": ["DECISIONS.md"],
                    "evidence_sources": ["DECISIONS.md"],
                    "decision_sources": ["DECISIONS.md"],
                },
                "stages": [
                    {
                        "checkpoint": "C1",
                        "human_checkpoint": {
                            "question": "Does the evidence support this scope?",
                            "write_to": "DECISIONS.md",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    contract, issues = case_module._read_case_contract(
        workspace,
        expected_workflow="paper-review",
        waiting_checkpoint="C1",
    )

    assert issues == ()
    assert contract is not None
    assert contract.decision_prompt == "Does the evidence support this scope?"


def test_mixed_current_and_legacy_authorities_fail_closed(tmp_path: Path) -> None:
    workspace = tmp_path / "mixed"
    _create_current_case(workspace, case_id="current")
    legacy = workspace / ".harness"
    legacy.mkdir()
    (legacy / "run.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(LoopFault) as caught:
        Loop.open(workspace).inspect()

    assert caught.value.code == "mixed_state_authority"


def test_workspace_symbolic_link_fails_closed_without_creating_state(
    tmp_path: Path,
) -> None:
    target = tmp_path / "redirected"
    target.mkdir()
    workspace = tmp_path / "case-link"
    workspace.symlink_to(target, target_is_directory=True)

    with pytest.raises(LoopFault) as caught:
        Loop.open(workspace).inspect()

    assert caught.value.code == "unsafe_workspace"
    assert not (target / ".harness-v3").exists()


def test_contract_issue_blocks_before_a_waiting_decision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "review"
    _create_current_case(workspace, case_id="issue-before-decision")
    case = Loop.open(workspace)
    base = case._base_inspection()
    waiting_with_issue = replace(
        base,
        waiting_checkpoint="C2",
        issues=("Pinned contract evidence is inconsistent.",),
    )
    monkeypatch.setattr(case, "_base_inspection", lambda: waiting_with_issue)

    inspection = case.inspect()

    assert inspection.state is LoopState.BLOCKED
    assert inspection.quality.contract_acceptance.status is LoopQualityState.BLOCKED


def test_decide_infers_the_only_waiting_decision_and_continues(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "review"
    _create_current_case(
        workspace,
        workflow="research-brief",
        case_id="decision-case",
    )
    case = Loop.open(workspace)
    base = case._base_inspection()
    waiting = replace(base, waiting_checkpoint="C2")
    working = replace(base, waiting_checkpoint="")
    assert working.run is not None
    blocked = replace(working, run=replace(working.run, status=RunStatus.BLOCKED))

    class _FakeHarness:
        def __init__(self) -> None:
            self.current = waiting
            self.calls: list[str] = []

        def inspect(self):
            return self.current

        def execute(self, command):
            if isinstance(command, InternalApprove):
                self.calls.append(command.checkpoint)
                self.current = working
            elif isinstance(command, InternalAdvance):
                self.calls.append("continue")
                self.current = blocked
            else:  # pragma: no cover - guards the internal test Adapter.
                raise AssertionError(type(command).__name__)
            return SimpleNamespace(issues=())

    fake = _FakeHarness()
    case._harness = fake

    pending = case.inspect()
    assert pending.state is LoopState.NEEDS_DECISION
    assert pending.pending_decision is not None
    assert pending.pending_decision.prompt == 'Confirm "scope + outline" and continue?'
    assert all(
        artifact.role == "decision_basis"
        for artifact in pending.pending_decision.reviewed_artifacts
    )

    result = case.advance(Decide())

    assert fake.calls == ["C2", "continue"]
    assert result.state is LoopState.BLOCKED


def test_legacy_workspace_is_read_only_and_has_no_normalized_claims(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "legacy"
    legacy = workspace / ".harness"
    legacy.mkdir(parents=True)
    (legacy / "harness.lock.json").write_text(
        json.dumps(
            {
                "schema": "harness-lock.v2",
                "run_id": "legacy-run",
                "workflow": "paper-review",
            }
        ),
        encoding="utf-8",
    )
    (legacy / "run.json").write_text(
        json.dumps(
            {
                "schema": "run-state.v1",
                "run_id": "legacy-run",
                "workflow": "paper-review",
                "state": "BLOCKED",
            }
        ),
        encoding="utf-8",
    )
    before = {path.name: path.read_bytes() for path in legacy.iterdir()}
    case = Loop.open(workspace)

    inspection = case.inspect()

    assert inspection.state is LoopState.LEGACY_READ_ONLY
    assert inspection.case_id == "legacy-run"
    assert inspection.normalized_claims_available is False
    assert inspection.views == ()
    assert inspection.quality.execution_integrity.status is LoopQualityState.UNVERIFIED
    assert any("claims" in issue.lower() for issue in inspection.issues)
    with pytest.raises(LoopFault) as start_caught:
        case.advance(Start("Do not overwrite legacy evidence", LoopKind.REVIEW))
    assert start_caught.value.code == "legacy_read_only"
    assert "new Workspace" in start_caught.value.message
    with pytest.raises(LoopFault) as caught:
        case.advance(Continue())
    assert caught.value.code == "legacy_read_only"
    assert {path.name: path.read_bytes() for path in legacy.iterdir()} == before
    assert not (workspace / ".harness-v3").exists()


def test_legacy_product_cli_refuses_a_current_workspace(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "current"
    _create_current_case(workspace, case_id="one-state")
    state = workspace / ".harness-v3" / "state.json"
    before = state.read_bytes()

    exit_code = legacy_cli_main(
        ["run", "resume", "--workspace", str(workspace), "--max-steps", "1"]
    )

    assert exit_code == 2
    assert "legacy rh CLI will not inspect or mutate it" in capsys.readouterr().err
    assert state.read_bytes() == before
    assert not (workspace / ".harness").exists()

    direct = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "pipeline.py"),
            "run",
            "--workspace",
            str(workspace),
            "--max-steps",
            "1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert direct.returncode == 1
    assert "legacy pipeline CLI will not inspect or mutate it" in direct.stderr
    assert state.read_bytes() == before
    assert not (workspace / ".harness").exists()


# The guard is six independently written copies of the same condition, one per
# legacy subcommand that touches a Workspace. Testing only one of them would let
# a copy-paste omission in any of the other five through with a green suite.
@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["goal", "create", "--goal", "a topic", "--workspace"], id="goal-create"),
        pytest.param(["run", "start", "--workspace"], id="run-start"),
        pytest.param(["run", "resume", "--workspace"], id="run-resume"),
        pytest.param(["run", "status", "--workspace"], id="run-status"),
        pytest.param(
            ["run", "approve", "--checkpoint", "C0", "--workspace"], id="run-approve"
        ),
        pytest.param(["evidence", "inspect", "--workspace"], id="evidence-inspect"),
        pytest.param(["improve", "diagnose", "--workspace"], id="improve-diagnose"),
    ],
)
def test_every_legacy_subcommand_refuses_a_current_workspace(
    tmp_path: Path,
    argv: list[str],
) -> None:
    workspace = tmp_path / "current"
    _create_current_case(workspace, case_id="guard-case")
    state = workspace / ".harness-v3" / "state.json"
    before = state.read_bytes()

    exit_code = legacy_cli_main([*argv, str(workspace)])

    assert exit_code == 2, argv
    assert state.read_bytes() == before, argv
    assert not (workspace / ".harness").exists(), argv


def test_audit_diff_write_refuses_a_current_workspace(tmp_path: Path) -> None:
    """`audit-diff` skips the Workspace lock, so its --write needs its own guard.

    It is the one command outside `LOCKED_WORKSPACE_COMMANDS`, and it derives its
    output directory from the --after report rather than a --workspace flag. Both
    reports are written into `<workspace>/output`, so without an explicit check
    the unlocked command writes into a Workspace every locked command refuses.
    """
    workspace = tmp_path / "current"
    _create_current_case(workspace, case_id="audit-diff-case")
    output = workspace / "output"
    output.mkdir(parents=True, exist_ok=True)

    payload_path = output / "RUN_AUDIT.json"
    before_path = tmp_path / "before.json"
    sample = _run_audit_payload(workspace)
    payload_path.write_text(json.dumps(sample), encoding="utf-8")
    before_path.write_text(json.dumps(sample), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "pipeline.py"),
            "audit-diff",
            "--before",
            str(before_path),
            "--after",
            str(payload_path),
            "--write",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1, result.stdout
    assert "legacy pipeline CLI will not inspect or mutate it" in result.stderr
    assert not (output / "RUN_AUDIT_DIFF.md").exists()
    assert not (output / "RUN_AUDIT_DIFF.json").exists()


# The three quality signals answer different questions and must not be conflated:
# execution integrity is whether the Run did what it said, contract acceptance is
# whether the declared result contract is met, and research quality is whether the
# work is any good. Only the first two are mechanically derivable, so the harness
# reports research quality as NOT_EVALUATED from every state rather than letting a
# completed Run imply a sound result. These tests pin that separation, which the
# surrounding suite otherwise only asserted incidentally.
@pytest.mark.parametrize("state", list(LoopState))
@pytest.mark.parametrize("execution_verified", [True, False])
def test_research_quality_is_never_derived_from_execution(
    state: LoopState,
    execution_verified: bool,
) -> None:
    quality = case_module._quality(state=state, execution_verified=execution_verified)

    assert quality.research_quality.status is LoopQualityState.NOT_EVALUATED, state
    assert "independent Evaluation" in quality.research_quality.explanation


def test_ready_and_verified_execution_still_withholds_research_quality() -> None:
    """The strongest mechanical result available must not imply research quality."""
    quality = case_module._quality(state=LoopState.READY, execution_verified=True)

    # READY with verified execution is the strongest mechanical result the
    # harness can reach: both derivable signals are affirmative here.
    assert quality.execution_integrity.status is LoopQualityState.VERIFIED
    assert quality.contract_acceptance.status is not LoopQualityState.NOT_EVALUATED
    # Research quality is still withheld.
    assert quality.research_quality.status is LoopQualityState.NOT_EVALUATED
