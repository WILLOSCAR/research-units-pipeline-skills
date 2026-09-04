from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from research_harness.acceptance import (
    AcceptanceRequest,
    LegacyToolingQualityProvider,
    WorkflowAcceptancePolicy,
    build_repository_acceptance_policy,
)
from research_harness.application import (
    BeginAttempt,
    CompleteAttempt,
    CreateRun,
    Harness,
    InMemoryArtifacts,
    InMemoryRunLedger,
    ReconcileRun,
    ResultOutcome,
)
from research_harness.domain import (
    AcceptanceEvidence,
    ArtifactEvidence,
    AttemptStatus,
    CompletionPhase,
    ErrorCode,
    Goal,
    HarnessError,
    HarnessRevision,
    ManifestStatus,
    RunPlan,
    RunStatus,
    RunView,
    UnitPlan,
    UnitStatus,
    UnitView,
)


@dataclass
class _RecordingEvaluator:
    result: AcceptanceEvidence

    def __post_init__(self) -> None:
        self.requests: list[AcceptanceRequest] = []

    def evaluate(self, request: AcceptanceRequest) -> AcceptanceEvidence:
        self.requests.append(request)
        return self.result


class _CrashingEvaluator:
    def evaluate(self, request: AcceptanceRequest) -> AcceptanceEvidence:
        del request
        raise RuntimeError("workspace secret must not escape")


class _MalformedEvaluator:
    def evaluate(self, request: AcceptanceRequest) -> AcceptanceEvidence:
        del request
        return object()  # type: ignore[return-value]


@dataclass
class _ArtifactMutatingAcceptance:
    artifacts: InMemoryArtifacts
    run_id: str
    path: str
    replacement: str
    mutate: bool = True

    def __post_init__(self) -> None:
        self.observed_paths: tuple[str, ...] = ()

    def evaluate(
        self,
        *,
        run: RunView,
        unit: UnitPlan,
        artifacts: tuple[ArtifactEvidence, ...],
    ) -> AcceptanceEvidence:
        del run
        self.observed_paths = tuple(artifact.path for artifact in artifacts)
        if self.mutate:
            self.artifacts.put(self.run_id, self.path, self.replacement)
        return AcceptanceEvidence(passed=True, checks=(unit.skill,))


def _run(
    *,
    workflow: str = "paper-review",
    skill: str = "paper-review-auditor",
    required: tuple[str, ...],
    outputs: tuple[str, ...] = (),
) -> RunView:
    unit = UnitPlan(id="U010", title="Check", skill=skill, outputs=outputs)
    return RunView(
        id="run_acceptance",
        goal=Goal(
            id="goal_acceptance",
            request="Review a paper",
            workflow=workflow,
            required_checks=required,
        ),
        revision=HarnessRevision(
            pipeline_digest="pipeline-fixture",
            kernel_digest="kernel-fixture",
        ),
        status=RunStatus.RUNNING,
        units=(UnitView(plan=unit, status=UnitStatus.DOING),),
        attempts=(),
        completions=(),
        checkpoint_approvals=(),
        events=(),
        active_attempt_id=None,
        version=1,
    )


def test_missing_required_checker_fails_closed() -> None:
    run = _run(required=("paper-review-auditor",))
    unit = run.units[0].plan
    policy = WorkflowAcceptancePolicy(evaluators={})

    evidence = policy.evaluate(run=run, unit=unit, artifacts=())

    assert not evidence.passed
    assert evidence.checks == ()
    assert evidence.issues == (
        "Required checker paper-review-auditor has no configured acceptance evaluator.",
    )


def test_required_checker_preserves_artifact_order_and_only_self_attests() -> None:
    run = _run(required=("paper-review-auditor",))
    unit = run.units[0].plan
    evaluator = _RecordingEvaluator(
        AcceptanceEvidence(
            passed=True,
            checks=("another-checker", "paper-review-auditor"),
        )
    )
    policy = WorkflowAcceptancePolicy(
        evaluators={("paper-review", "paper-review-auditor"): evaluator},
    )
    artifacts = (
        ArtifactEvidence(path="output/review.md", sha256="a" * 64, size=10),
        ArtifactEvidence(path="input/paper.pdf", sha256="b" * 64, size=20),
    )

    evidence = policy.evaluate(run=run, unit=unit, artifacts=artifacts)

    assert evaluator.requests[0].artifacts is artifacts
    assert tuple(item.path for item in evaluator.requests[0].artifacts) == (
        "output/review.md",
        "input/paper.pdf",
    )
    assert evidence == AcceptanceEvidence(
        passed=True,
        checks=("paper-review-auditor",),
    )


def test_passing_required_evaluator_without_exact_self_attestation_is_rejected() -> (
    None
):
    run = _run(required=("paper-review-auditor",))
    unit = run.units[0].plan
    evaluator = _RecordingEvaluator(
        AcceptanceEvidence(passed=True, checks=("paper-review-auditor:v1",))
    )
    policy = WorkflowAcceptancePolicy(
        evaluators={("paper-review", "paper-review-auditor"): evaluator},
    )

    evidence = policy.evaluate(run=run, unit=unit, artifacts=())

    assert not evidence.passed
    assert evidence.checks == ()
    assert evidence.issues == (
        "Required checker paper-review-auditor did not exactly self-attest.",
    )


def test_invalid_evaluator_is_rejected_at_composition() -> None:
    with pytest.raises(TypeError, match="must implement evaluate"):
        WorkflowAcceptancePolicy(
            evaluators={("paper-review", "paper-review-auditor"): object()},  # type: ignore[dict-item]
        )


def test_evaluator_exception_becomes_bounded_rejection() -> None:
    run = _run(required=("paper-review-auditor",))
    unit = run.units[0].plan
    policy = WorkflowAcceptancePolicy(
        evaluators={("paper-review", "paper-review-auditor"): _CrashingEvaluator()},
    )

    evidence = policy.evaluate(run=run, unit=unit, artifacts=())

    assert evidence == AcceptanceEvidence(
        passed=False,
        issues=(
            "Acceptance evaluator for paper-review/paper-review-auditor failed with "
            "RuntimeError.",
        ),
    )
    assert "secret" not in evidence.issues[0]


def test_unbound_non_required_skill_passes_without_attestation() -> None:
    run = _run(required=())
    unit = run.units[0].plan
    policy = WorkflowAcceptancePolicy(evaluators={})

    evidence = policy.evaluate(run=run, unit=unit, artifacts=())

    assert evidence == AcceptanceEvidence(passed=True)


def test_malformed_evaluator_result_fails_closed() -> None:
    run = _run(required=("paper-review-auditor",))
    unit = run.units[0].plan
    policy = WorkflowAcceptancePolicy(
        evaluators={("paper-review", "paper-review-auditor"): _MalformedEvaluator()},
    )

    evidence = policy.evaluate(run=run, unit=unit, artifacts=())

    assert evidence == AcceptanceEvidence(
        passed=False,
        issues=(
            "Acceptance evaluator for paper-review/paper-review-auditor returned an "
            "invalid result.",
        ),
    )


def test_evaluator_issues_are_path_safe_secret_safe_and_bounded() -> None:
    run = _run(
        required=("paper-review-auditor",),
        outputs=("audit.md",),
    )
    unit = run.units[0].plan
    raw_issues = tuple(
        (
            f"quality_{index}: failed at "
            f"'/Users/example/Documents/private repo/output/{index}.json' "
            f"token=tok-{index} password: 'pw-{index}' "
            f'api_key="key-{index}" secret=secret-{index} ' + "x" * 1_200
        )
        for index in range(20)
    )
    evaluator = _RecordingEvaluator(AcceptanceEvidence(passed=False, issues=raw_issues))
    policy = WorkflowAcceptancePolicy(
        evaluators={("paper-review", "paper-review-auditor"): evaluator},
    )

    evidence = policy.evaluate(run=run, unit=unit, artifacts=())

    assert not evidence.passed
    assert len(evidence.issues) == 16
    assert all(len(issue) <= 1_000 for issue in evidence.issues)
    assert evidence.issues[0].startswith("quality_0:")
    joined = "\n".join(evidence.issues)
    assert "/Users/example" not in joined
    assert "tok-" not in joined
    assert "pw-" not in joined
    assert "key-" not in joined
    assert "secret-" not in joined
    assert "<path>" in joined
    assert "<redacted>" in joined

    harness_artifacts = InMemoryArtifacts()
    harness = Harness(
        ledger=InMemoryRunLedger(),
        artifacts=harness_artifacts,
        acceptance=policy,
        revision=run.revision,
    )
    harness.execute(
        CreateRun(
            run_id="run_sanitized_state",
            plan=RunPlan(goal=run.goal, units=(unit,)),
        )
    )
    attempt = harness.execute(
        BeginAttempt(run_id="run_sanitized_state", unit_id=unit.id)
    )
    harness_artifacts.put("run_sanitized_state", "audit.md", "audit")
    blocked = harness.execute(
        CompleteAttempt(
            run_id="run_sanitized_state",
            attempt_id=attempt.attempt_id,
        )
    )
    persisted = blocked.run.attempts[-1].message
    assert "/Users/example" not in persisted
    assert all(value not in persisted for value in ("tok-", "pw-", "key-", "secret-"))
    assert len(persisted) <= 16 * 1_002


def test_completion_rejects_artifact_changes_during_acceptance() -> None:
    run_id = "run_acceptance_race"
    plan = RunPlan(
        goal=Goal(
            id="goal_acceptance_race",
            request="Bind exact acceptance evidence",
            workflow="paper-review",
            target_artifacts=("final.md",),
            required_checks=("paper-review-auditor",),
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Audit",
                skill="paper-review-auditor",
                inputs=("source.md",),
                outputs=("check.md",),
            ),
        ),
    )
    artifacts = InMemoryArtifacts()
    acceptance = _ArtifactMutatingAcceptance(
        artifacts=artifacts,
        run_id=run_id,
        path="source.md",
        replacement="source-v2",
    )
    harness = Harness(
        ledger=InMemoryRunLedger(),
        artifacts=artifacts,
        acceptance=acceptance,
        revision=HarnessRevision(
            pipeline_digest="pipeline-fixture",
            kernel_digest="kernel-fixture",
        ),
    )
    harness.execute(CreateRun(run_id=run_id, plan=plan))
    attempt = harness.execute(BeginAttempt(run_id=run_id, unit_id="U010"))
    artifacts.put(run_id, "source.md", "source-v1")
    artifacts.put(run_id, "check.md", "PASS")
    artifacts.put(run_id, "final.md", "final-v1")

    completed = harness.execute(
        CompleteAttempt(run_id=run_id, attempt_id=attempt.attempt_id)
    )

    assert acceptance.observed_paths == ("source.md", "check.md", "final.md")
    assert completed.outcome is ResultOutcome.BLOCKED
    assert completed.message == (
        "Artifact evidence changed during acceptance evaluation; retry the Unit "
        "against a stable Workspace."
    )
    assert completed.run.attempts[-1].status is AttemptStatus.FAILED_RETRYABLE
    assert completed.run.completions == ()
    assert artifacts.list_manifests(run_id) == ()


def test_recovery_rejects_artifact_changes_during_acceptance() -> None:
    run_id = "run_acceptance_recovery_race"
    plan = RunPlan(
        goal=Goal(
            id="goal_acceptance_recovery_race",
            request="Recover only exact acceptance evidence",
            workflow="paper-review",
            target_artifacts=("check.md",),
            required_checks=("paper-review-auditor",),
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Audit",
                skill="paper-review-auditor",
                inputs=("source.md",),
                outputs=("check.md",),
            ),
        ),
    )
    artifacts = InMemoryArtifacts()
    acceptance = _ArtifactMutatingAcceptance(
        artifacts=artifacts,
        run_id=run_id,
        path="source.md",
        replacement="source-v2",
        mutate=False,
    )
    harness = Harness(
        ledger=InMemoryRunLedger(),
        artifacts=artifacts,
        acceptance=acceptance,
        revision=HarnessRevision(
            pipeline_digest="pipeline-fixture",
            kernel_digest="kernel-fixture",
        ),
    )
    harness.execute(CreateRun(run_id=run_id, plan=plan))
    attempt = harness.execute(BeginAttempt(run_id=run_id, unit_id="U010"))
    artifacts.put(run_id, "source.md", "source-v1")
    artifacts.put(run_id, "check.md", "PASS")
    artifacts.fail_next_finalize()
    with pytest.raises(HarnessError) as caught:
        harness.execute(CompleteAttempt(run_id=run_id, attempt_id=attempt.attempt_id))
    assert caught.value.code is ErrorCode.ADAPTER_FAILURE
    assert harness.inspect(run_id).completions[-1].phase is CompletionPhase.PREPARED

    acceptance.mutate = True
    recovered = harness.execute(ReconcileRun(run_id=run_id))

    assert recovered.outcome is ResultOutcome.BLOCKED
    assert "Artifact evidence changed during acceptance evaluation" in recovered.message
    assert (
        "Prepared Artifact fingerprints changed before Completion committed"
        in recovered.message
    )
    assert recovered.run.completions[-1].phase is CompletionPhase.ABORTED
    assert artifacts.list_manifests(run_id)[0].status is ManifestStatus.BLOCKED


def test_failed_current_acceptance_retains_prior_checker_freshness_issue() -> None:
    run_id = "run_prior_freshness"
    plan = RunPlan(
        goal=Goal(
            id="goal_prior_freshness",
            request="Keep prior freshness diagnostics",
            workflow="audit-workflow",
            target_artifacts=("report.md",),
            required_checks=("checker-a", "checker-b"),
        ),
        units=(
            UnitPlan(
                id="U010",
                title="Produce source",
                skill="producer",
                outputs=("source.md",),
            ),
            UnitPlan(
                id="U020",
                title="Check A",
                skill="checker-a",
                depends_on=("U010",),
                inputs=("source.md",),
                outputs=("check-a.md",),
            ),
            UnitPlan(
                id="U030",
                title="Check B and deliver",
                skill="checker-b",
                depends_on=("U020",),
                inputs=("source.md",),
                outputs=("report.md",),
            ),
        ),
    )
    artifacts = InMemoryArtifacts()
    policy = WorkflowAcceptancePolicy(
        evaluators={
            ("audit-workflow", "checker-a"): _RecordingEvaluator(
                AcceptanceEvidence(passed=True, checks=("checker-a",))
            )
        },
    )
    harness = Harness(
        ledger=InMemoryRunLedger(),
        artifacts=artifacts,
        acceptance=policy,
        revision=HarnessRevision(
            pipeline_digest="pipeline-fixture",
            kernel_digest="kernel-fixture",
        ),
    )
    harness.execute(CreateRun(run_id=run_id, plan=plan))
    producer = harness.execute(BeginAttempt(run_id=run_id, unit_id="U010"))
    artifacts.put(run_id, "source.md", "source-v1")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=producer.attempt_id))
    checker_a = harness.execute(BeginAttempt(run_id=run_id, unit_id="U020"))
    artifacts.put(run_id, "check-a.md", "PASS")
    harness.execute(CompleteAttempt(run_id=run_id, attempt_id=checker_a.attempt_id))

    artifacts.put(run_id, "source.md", "source-v2")
    checker_b = harness.execute(BeginAttempt(run_id=run_id, unit_id="U030"))
    artifacts.put(run_id, "report.md", "report")
    blocked = harness.execute(
        CompleteAttempt(run_id=run_id, attempt_id=checker_b.attempt_id)
    )

    assert blocked.outcome is ResultOutcome.BLOCKED
    assert (
        "Required checker checker-b has no configured acceptance evaluator."
        in blocked.message
    )
    assert "Required check checker-a is stale" in blocked.message
    assert "Mandatory check checker-b" not in blocked.message
    assert "committed/current coverage: checker-b" not in blocked.message


def test_repository_evaluator_maps_quality_issues_without_legacy_run_state(
    monkeypatch, tmp_path: Path
) -> None:
    from research_harness.workflows import load_workflow_definition
    from tooling.quality_checks.common import QualityIssue
    from tooling import quality_gate

    repo_root = Path(__file__).resolve().parents[2]
    workflow = load_workflow_definition(
        repo_root / "pipelines" / "paper-review.pipeline.md",
        repo_root=repo_root,
    )
    workspace = tmp_path / "run"
    workspace.mkdir()
    calls: list[tuple[str, Path, tuple[str, ...]]] = []

    def invariants(*, skill: str, workspace: Path, outputs: list[str]):
        calls.append((f"invariant:{skill}", workspace, tuple(outputs)))
        return [QualityIssue(code="invariant_failed", message="unsafe outline")]

    def outputs(*, skill: str, workspace: Path, outputs: list[str]):
        calls.append((f"outputs:{skill}", workspace, tuple(outputs)))
        return [QualityIssue(code="quality_failed", message="missing evidence")]

    monkeypatch.setattr(quality_gate, "check_completion_invariants", invariants)
    monkeypatch.setattr(quality_gate, "check_unit_outputs", outputs)
    monkeypatch.setattr(
        quality_gate,
        "required_completion_checks",
        lambda workspace: (_ for _ in ()).throw(
            AssertionError("legacy required-check lookup must not run")
        ),
    )
    monkeypatch.setattr(
        quality_gate,
        "completion_contract_issue",
        lambda workspace: (_ for _ in ()).throw(
            AssertionError("legacy Run contract lookup must not run")
        ),
    )
    policy = build_repository_acceptance_policy(
        workflows=(workflow,),
        workspace_for_run=lambda run_id: workspace,
        provider=LegacyToolingQualityProvider(),
    )
    run = _run(
        skill="claims-extractor",
        required=workflow.checks,
        outputs=("output/CLAIMS.md",),
    )
    artifacts = (
        ArtifactEvidence(path="input/paper.pdf", sha256="a" * 64, size=10),
        ArtifactEvidence(path="output/CLAIMS.md", sha256="b" * 64, size=20),
    )

    evidence = policy.evaluate(
        run=run,
        unit=run.units[0].plan,
        artifacts=artifacts,
    )

    assert calls == [
        ("invariant:claims-extractor", workspace, ("output/CLAIMS.md",)),
        ("outputs:claims-extractor", workspace, ("output/CLAIMS.md",)),
    ]
    assert evidence == AcceptanceEvidence(
        passed=False,
        issues=(
            "invariant_failed: unsafe outline",
            "quality_failed: missing evidence",
        ),
    )


def test_repository_factory_binds_registered_non_required_skill(
    monkeypatch, tmp_path: Path
) -> None:
    from research_harness.workflows import load_workflow_definition
    from tooling import quality_gate

    repo_root = Path(__file__).resolve().parents[2]
    workflow = load_workflow_definition(
        repo_root / "pipelines" / "research-brief.pipeline.md",
        repo_root=repo_root,
    )
    monkeypatch.setattr(
        quality_gate, "check_completion_invariants", lambda **kwargs: []
    )
    monkeypatch.setattr(quality_gate, "check_unit_outputs", lambda **kwargs: [])
    policy = build_repository_acceptance_policy(
        workflows=(workflow,),
        workspace_for_run=lambda run_id: tmp_path,
        provider=LegacyToolingQualityProvider(),
    )
    run = _run(
        workflow="research-brief",
        skill="prose-writer",
        required=workflow.checks,
        outputs=("DRAFT.md",),
    )

    evidence = policy.evaluate(
        run=run,
        unit=run.units[0].plan,
        artifacts=(ArtifactEvidence(path="DRAFT.md", sha256="c" * 64, size=30),),
    )

    assert evidence == AcceptanceEvidence(
        passed=True,
        checks=("prose-writer",),
    )


def test_repository_factory_rejects_uncovered_required_skill(
    monkeypatch, tmp_path: Path
) -> None:
    from research_harness.workflows import load_workflow_definition
    from tooling import quality_gate

    repo_root = Path(__file__).resolve().parents[2]
    workflow = load_workflow_definition(
        repo_root / "pipelines" / "paper-review.pipeline.md",
        repo_root=repo_root,
    )
    # `claims-extractor` carries no completion invariant by default, so an
    # empty registry alone makes it an uncovered required Skill.
    monkeypatch.setattr(quality_gate, "registered_quality_skills", lambda: frozenset())

    with pytest.raises(ValueError, match="claims-extractor"):
        build_repository_acceptance_policy(
            workflows=(workflow,),
            workspace_for_run=lambda run_id: tmp_path,
            provider=LegacyToolingQualityProvider(),
        )


def test_repository_quality_diagnostics_are_deterministically_bounded(
    monkeypatch, tmp_path: Path
) -> None:
    from research_harness.workflows import load_workflow_definition
    from tooling.quality_checks.common import QualityIssue
    from tooling import quality_gate

    repo_root = Path(__file__).resolve().parents[2]
    workflow = load_workflow_definition(
        repo_root / "pipelines" / "paper-review.pipeline.md",
        repo_root=repo_root,
    )
    issues = [
        QualityIssue(
            code=f"issue_{index}_" + "x" * 120,
            message=f"message {index}\n" + "y" * 700,
        )
        for index in range(20)
    ]
    monkeypatch.setattr(
        quality_gate, "check_completion_invariants", lambda **kwargs: issues
    )
    policy = build_repository_acceptance_policy(
        workflows=(workflow,),
        workspace_for_run=lambda run_id: tmp_path,
    )
    run = _run(
        skill="claims-extractor",
        required=workflow.checks,
        outputs=("output/CLAIMS.md",),
    )

    evidence = policy.evaluate(
        run=run,
        unit=run.units[0].plan,
        artifacts=(
            ArtifactEvidence(path="output/CLAIMS.md", sha256="d" * 64, size=40),
        ),
    )

    assert not evidence.passed
    assert len(evidence.issues) == 16
    assert all(len(issue) <= 610 for issue in evidence.issues)
    assert all("\n" not in issue for issue in evidence.issues)
    assert evidence.issues[0].startswith("issue_0_")
    assert evidence.issues[-1].startswith("issue_15_")


def test_all_validated_workflows_have_repository_acceptance_coverage(
    tmp_path: Path,
) -> None:
    from research_harness.workflows import load_workflow_definition

    repo_root = Path(__file__).resolve().parents[2]
    names = (
        "arxiv-survey-latex",
        "arxiv-survey",
        "evidence-review",
        "idea-brainstorm",
        "paper-review",
        "research-brief",
        "source-tutorial",
    )
    workflows = tuple(
        load_workflow_definition(
            repo_root / "pipelines" / f"{name}.pipeline.md",
            repo_root=repo_root,
        )
        for name in names
    )

    policy = build_repository_acceptance_policy(
        workflows=workflows,
        workspace_for_run=lambda run_id: tmp_path,
    )

    assert isinstance(policy, WorkflowAcceptancePolicy)


def test_native_and_legacy_policies_are_identical_across_all_workflows(
    tmp_path: Path,
) -> None:
    """Cutover-safety at the orchestration level.

    Building the repository acceptance policy with the native provider vs the
    legacy provider must yield identical ``(workflow, skill)`` bindings for
    every real workflow, and evaluating a bound unit through each policy must
    yield byte-identical ``AcceptanceEvidence``.  The orchestration
    concatenates completion-invariant + unit-output issues, then bounds and
    sanitizes them -- provider-agnostic in principle, but here proven
    end-to-end so the default flip cannot silently change an acceptance
    outcome.
    """
    from research_harness.acceptance import NativeQualityProvider
    from research_harness.workflows import load_workflow_definition

    repo_root = Path(__file__).resolve().parents[2]
    names = (
        "arxiv-survey-latex",
        "arxiv-survey",
        "evidence-review",
        "idea-brainstorm",
        "paper-review",
        "research-brief",
        "source-tutorial",
    )
    workflows = tuple(
        load_workflow_definition(
            repo_root / "pipelines" / f"{name}.pipeline.md",
            repo_root=repo_root,
        )
        for name in names
    )

    native_policy = build_repository_acceptance_policy(
        workflows=workflows,
        workspace_for_run=lambda run_id: tmp_path,
        provider=NativeQualityProvider(),
    )
    legacy_policy = build_repository_acceptance_policy(
        workflows=workflows,
        workspace_for_run=lambda run_id: tmp_path,
        provider=LegacyToolingQualityProvider(),
    )

    # Evaluating every Skill in every real workflow through both policies on an
    # empty workspace yields identical AcceptanceEvidence -- proving both the
    # (workflow, skill) bindings (an unbound Skill passes on both, a bound one
    # runs the same checks) and the issue mapping are byte-identical.
    for workflow in workflows:
        for skill in workflow.skills:
            run = _run(workflow=workflow.name, skill=skill, required=(), outputs=())
            unit = run.units[0].plan
            native_ev = native_policy.evaluate(run=run, unit=unit, artifacts=())
            legacy_ev = legacy_policy.evaluate(run=run, unit=unit, artifacts=())
            assert native_ev == legacy_ev, (
                f"{workflow.name}/{skill}: native={native_ev!r} legacy={legacy_ev!r}"
            )


def test_harness_blocks_completion_when_required_checker_is_not_configured() -> None:
    run = _run(required=("paper-review-auditor",), outputs=("audit.md",))
    unit = run.units[0].plan
    plan = RunPlan(goal=run.goal, units=(unit,))
    artifacts = InMemoryArtifacts()
    harness = Harness(
        ledger=InMemoryRunLedger(),
        artifacts=artifacts,
        acceptance=WorkflowAcceptancePolicy(evaluators={}),
        revision=run.revision,
    )
    harness.execute(CreateRun(run_id=run.id, plan=plan))
    attempt = harness.execute(BeginAttempt(run_id=run.id, unit_id=unit.id))
    artifacts.put(run.id, "audit.md", "looks plausible")

    completed = harness.execute(
        CompleteAttempt(run_id=run.id, attempt_id=attempt.attempt_id)
    )

    assert completed.outcome is ResultOutcome.BLOCKED
    assert completed.message == (
        "Required checker paper-review-auditor has no configured acceptance evaluator."
    )
    assert "did not explicitly attest" not in completed.message
    assert "lack committed/current coverage" not in completed.message
    assert artifacts.list_manifests(run.id) == ()


# `WorkflowAcceptancePolicy.evaluate` has several ways to refuse a unit, and the
# tests above already cover them -- but by comparing whole AcceptanceEvidence
# objects, so they also fail for incidental reasons and do not say which property
# broke. These isolate one property per test, and add an assertion the older ones
# do not make: a raised evaluator's own message must not reach the issue list.
class _RejectingEvaluator:
    def evaluate(self, request: AcceptanceRequest) -> AcceptanceEvidence:
        return AcceptanceEvidence(
            passed=False, issues=("the deliverable contradicts its own evidence",)
        )


class _RaisingEvaluator:
    def evaluate(self, request: AcceptanceRequest) -> AcceptanceEvidence:
        raise RuntimeError("evaluator exploded")


class _InvalidResultEvaluator:
    def evaluate(self, request: AcceptanceRequest) -> AcceptanceEvidence:
        return "looks fine to me"  # type: ignore[return-value]


def _policy_with(evaluator: object, *, skill: str) -> WorkflowAcceptancePolicy:
    return WorkflowAcceptancePolicy(evaluators={("paper-review", skill): evaluator})


def test_evaluator_rejection_is_reported_with_its_issue() -> None:
    run = _run(required=("paper-review-auditor",))
    policy = _policy_with(_RejectingEvaluator(), skill="paper-review-auditor")

    evidence = policy.evaluate(run=run, unit=run.units[0].plan, artifacts=())

    assert evidence.passed is False
    assert any("contradicts its own evidence" in issue for issue in evidence.issues)


def test_evaluator_that_raises_fails_closed_without_leaking_the_exception() -> None:
    """A crashing evaluator must not be read as acceptance."""
    run = _run(required=("paper-review-auditor",))
    policy = _policy_with(_RaisingEvaluator(), skill="paper-review-auditor")

    evidence = policy.evaluate(run=run, unit=run.units[0].plan, artifacts=())

    assert evidence.passed is False
    joined = "\n".join(evidence.issues)
    assert "RuntimeError" in joined
    # The message text is the evaluator's, not the harness's, so it is named by
    # type only -- a raised string could carry anything.
    assert "evaluator exploded" not in joined


def test_evaluator_returning_a_non_evidence_value_fails_closed() -> None:
    run = _run(required=("paper-review-auditor",))
    policy = _policy_with(_InvalidResultEvaluator(), skill="paper-review-auditor")

    evidence = policy.evaluate(run=run, unit=run.units[0].plan, artifacts=())

    assert evidence.passed is False
    assert any("invalid result" in issue for issue in evidence.issues)


def test_unrequired_skill_without_an_evaluator_is_allowed() -> None:
    """The allow path: a non-required Skill needs no evaluator to pass."""
    run = _run(skill="opener-variator", required=("paper-review-auditor",))
    policy = WorkflowAcceptancePolicy(evaluators={})

    evidence = policy.evaluate(run=run, unit=run.units[0].plan, artifacts=())

    assert evidence.passed is True
    assert evidence.issues == ()
