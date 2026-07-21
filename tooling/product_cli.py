from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from tooling.run_state import ConcurrentInvocationError, workspace_invocation_lock


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_CLI = REPO_ROOT / "scripts" / "pipeline.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rh",
        description="Outcome-first interface for Goal -> Run -> Evidence -> Improve.",
    )
    stages = parser.add_subparsers(dest="stage", required=True)

    goal = stages.add_parser("goal", help="Create a durable research goal and workspace")
    goal_actions = goal.add_subparsers(dest="action", required=True)
    goal_create = goal_actions.add_parser("create", help="Create a topic-seeded goal and select its Workflow")
    goal_create.add_argument("--topic", required=True, help="Research topic or bounded question")
    goal_create.add_argument("--workflow", default="", help="Workflow slug; omit to route from the Goal text")
    goal_create.add_argument("--workspace", default="", help="Workspace path; defaults to a generated path under workspaces/")
    goal_create.add_argument("--run", action="store_true", help="Start the run immediately")
    goal_create.add_argument(
        "--strict",
        action="store_true",
        help="Add registered diagnostics beyond the Workflow's mandatory completion checks",
    )

    run = stages.add_parser("run", help="Start, inspect, or resume a run")
    run_actions = run.add_subparsers(dest="action", required=True)
    for action in ("start", "resume"):
        help_text = (
            "Start unit execution"
            if action == "start"
            else "Reconcile persisted state and continue unit execution"
        )
        action_parser = run_actions.add_parser(action, help=help_text)
        action_parser.add_argument("--workspace", required=True)
        action_parser.add_argument("--max-steps", type=int, default=999, help="Maximum Units to attempt in this command")
        action_parser.add_argument(
            "--strict",
            action="store_true",
            help="Add registered diagnostics beyond the Workflow's mandatory completion checks",
        )
    run_status = run_actions.add_parser(
        "status",
        help="Reconcile recoverable run state, then inspect it without executing units",
    )
    run_status.add_argument("--workspace", required=True)
    run_approve = run_actions.add_parser(
        "approve",
        help="Record a human checkpoint decision before resuming the Run",
    )
    run_approve.add_argument("--workspace", required=True)
    run_approve.add_argument("--checkpoint", required=True, help="Checkpoint ID shown by run status, such as C2")
    run_approve.add_argument(
        "--focus-cluster",
        action="append",
        default=[],
        help="Idea-brainstorm C2 focus cluster; repeat for multiple selections",
    )
    run_approve.add_argument(
        "--hard-exclusion",
        action="append",
        default=[],
        help="Idea-brainstorm C2 exclusion; repeat for multiple exclusions",
    )

    evidence = stages.add_parser("evidence", help="Inspect Run evidence and index Workflow-local research artifacts")
    evidence_actions = evidence.add_subparsers(dest="action", required=True)
    evidence_inspect = evidence_actions.add_parser(
        "inspect",
        help="Write Run Audit and Artifact-index views; research semantics remain Workflow-local",
    )
    evidence_inspect.add_argument("--workspace", required=True)
    evidence_inspect.add_argument("--excerpt", action="store_true", help="Write portable Markdown and TSV excerpts")

    improve = stages.add_parser("improve", help="Diagnose a weak or blocked run")
    improve_actions = improve.add_subparsers(dest="action", required=True)
    improve_diagnose = improve_actions.add_parser("diagnose", help="Map observed defects to repair surfaces")
    improve_diagnose.add_argument("--workspace", required=True)

    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except ConcurrentInvocationError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _dispatch(args: argparse.Namespace) -> int:
    if (args.stage, args.action) == ("goal", "create"):
        command = ["kickoff", "--topic", args.topic]
        if args.workflow:
            command.extend(["--pipeline", args.workflow])
        if args.workspace:
            command.extend(["--workspace", args.workspace])
        if args.run:
            command.append("--run")
        if args.strict:
            command.append("--strict")
        return _run_pipeline(*command)

    if args.stage == "run" and args.action in {"start", "resume"}:
        if not _workspace_exists(args.workspace):
            return 2
        command = ["run", "--workspace", args.workspace, "--max-steps", str(args.max_steps)]
        if args.action == "start":
            command.append("--require-planned")
        if args.strict:
            command.append("--strict")
        return _run_pipeline(*command)

    if (args.stage, args.action) == ("run", "status"):
        if not _workspace_exists(args.workspace):
            return 2
        workspace = Path(args.workspace).resolve()
        with workspace_invocation_lock(workspace=workspace, operation="rh.run.status"):
            return _run_status(workspace)

    if (args.stage, args.action) == ("run", "approve"):
        if not _workspace_exists(args.workspace):
            return 2
        command = [
            "approve",
            "--workspace",
            args.workspace,
            "--checkpoint",
            args.checkpoint,
        ]
        for item in args.focus_cluster:
            command.extend(["--focus-cluster", item])
        for item in args.hard_exclusion:
            command.extend(["--hard-exclusion", item])
        return _run_pipeline(*command)

    if (args.stage, args.action) == ("evidence", "inspect"):
        if not _workspace_exists(args.workspace):
            return 2
        workspace = Path(args.workspace).resolve()
        with workspace_invocation_lock(workspace=workspace, operation="rh.evidence.inspect"):
            return _inspect_evidence(workspace, write_excerpt=bool(args.excerpt))

    if (args.stage, args.action) == ("improve", "diagnose"):
        if not _workspace_exists(args.workspace):
            return 2
        workspace = Path(args.workspace).resolve()
        with workspace_invocation_lock(workspace=workspace, operation="rh.improve.diagnose"):
            return _diagnose_improvement(workspace)

    raise SystemExit("Unsupported product command")


def _run_pipeline(*args: str) -> int:
    if not PIPELINE_CLI.exists():
        print(
            "This rh command requires a Research Harness source checkout with "
            "scripts/, pipelines/, templates/, and .codex/skills/. Run it from the cloned repository; "
            "the current Python wheel is not a standalone Harness distribution.",
            file=sys.stderr,
        )
        return 2
    completed = subprocess.run([sys.executable, str(PIPELINE_CLI), *args], cwd=REPO_ROOT, check=False)
    return int(completed.returncode)


def _workspace_exists(value: str) -> bool:
    workspace = Path(value).resolve()
    if workspace.exists():
        return True
    print(f"Workspace not found: {workspace}", file=sys.stderr)
    return False


def _run_status(workspace: Path) -> int:
    from tooling.harness import build_doctor_payload

    if not workspace.exists():
        print(f"Workspace not found: {workspace}", file=sys.stderr)
        return 2

    exit_code, payload = build_doctor_payload(workspace=workspace, repo_root=REPO_ROOT)

    identity = payload.get("run_identity") or {}
    next_unit = payload.get("next_runnable") or {}
    issues = payload.get("harness_issues") or []
    print(f"Run: {identity.get('run_id') or workspace.name}")
    print(f"State: {identity.get('state') or 'legacy workspace'}")
    print(f"Checkpoint: {payload.get('current_checkpoint') or 'unknown'}")
    if next_unit:
        print(
            "Next: "
            f"{next_unit.get('unit_id')} {next_unit.get('title')} "
            f"[{next_unit.get('status') or 'unknown'}]"
        )
        if next_unit.get("owner") == "HUMAN" and next_unit.get("checkpoint"):
            print(
                "Approve: uv run rh run approve "
                f"--workspace {workspace} --checkpoint {next_unit.get('checkpoint')}"
            )
    else:
        print("Next: no runnable Unit")
    print(f"Issues: {len(issues)}")
    if next_unit and not issues:
        print(f"Resume: uv run rh run resume --workspace {workspace}")
    else:
        print(f"Inspect: uv run python scripts/pipeline.py doctor --workspace {workspace} --write")
    return int(exit_code)


def _inspect_evidence(workspace: Path, *, write_excerpt: bool) -> int:
    from tooling.harness import (
        build_harness_inspection,
        render_artifact_pack_excerpt_markdown,
        render_artifact_pack_excerpt_tsv,
        render_artifact_pack_report,
        render_run_audit_report,
        write_artifact_pack_excerpt_markdown,
        write_artifact_pack_excerpt_tsv,
        write_artifact_pack_json,
        write_artifact_pack_report,
        write_run_audit_json,
        write_run_audit_report,
    )

    if not workspace.exists():
        print(f"Workspace not found: {workspace}", file=sys.stderr)
        return 2

    inspection = build_harness_inspection(workspace=workspace, repo_root=REPO_ROOT)
    audit_code, audit = inspection.audit_exit_code, inspection.audit
    write_run_audit_report(workspace=workspace, report=render_run_audit_report(audit))
    write_run_audit_json(workspace=workspace, payload=audit)
    pack_code, pack = inspection.artifact_pack_exit_code, inspection.artifact_pack
    write_artifact_pack_report(workspace=workspace, report=render_artifact_pack_report(pack))
    write_artifact_pack_json(workspace=workspace, payload=pack)
    if write_excerpt:
        write_artifact_pack_excerpt_markdown(
            workspace=workspace,
            excerpt=render_artifact_pack_excerpt_markdown(pack),
        )
        write_artifact_pack_excerpt_tsv(
            workspace=workspace,
            excerpt=render_artifact_pack_excerpt_tsv(pack),
        )

    run_state = audit.get("run_state") or {}
    summary = pack.get("summary") or {}
    print(f"Run evidence: {audit.get('verdict') or 'ATTENTION'}")
    print("Research evidence: indexed as Workflow-local Artifacts (not normalized across Workflows)")
    print(
        "Targets: "
        f"{run_state.get('target_artifacts_present', 0)}/{run_state.get('target_artifacts_total', 0)}"
    )
    print(f"Artifact index: {summary.get('present', 0)}/{summary.get('total', 0)} present")
    required_missing, optional_diagnostics = _artifact_pack_missing_paths(pack)
    if required_missing:
        print(f"Required evidence missing: {len(required_missing)}")
    else:
        print("Required evidence: complete")
    if optional_diagnostics:
        print(f"Optional diagnostics absent: {len(optional_diagnostics)}")
    attempts = audit.get("attempts") or {}
    if attempts.get("started"):
        print(
            "Attempts: "
            f"{attempts.get('finished', 0)}/{attempts.get('started', 0)} finished, "
            f"{attempts.get('extra_attempts', 0)} retries"
        )
    from tooling.run_state import latest_evaluation

    evaluation = latest_evaluation(workspace)
    if evaluation:
        print(
            f"Scorecard: {evaluation.get('verdict') or 'unknown'} "
            f"{evaluation.get('score', '?')}/100 "
            f"[{evaluation.get('workflow') or 'unknown'}]"
        )
    else:
        scorecards = sorted((workspace / "output").glob("*_SCORECARD.json"))
        if scorecards:
            try:
                scorecard = json.loads(scorecards[-1].read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                scorecard = {}
            if isinstance(scorecard, dict):
                print(
                    f"Scorecard: {scorecard.get('verdict') or 'unknown'} "
                    f"{scorecard.get('score', '?')}/100"
                )
    print(f"Inspect: {workspace / 'output' / 'ARTIFACT_PACK.md'}")
    return max(int(audit_code), int(pack_code))


def _artifact_pack_missing_paths(pack: dict[str, object]) -> tuple[set[str], set[str]]:
    artifacts = pack.get("artifacts")
    if not isinstance(artifacts, list):
        return set(), set()

    required_categories = {"target_artifact", "unit_output", "run_ledger", "unit_manifest"}
    required_paths = {
        str(record.get("path") or "")
        for record in artifacts
        if isinstance(record, dict)
        and str(record.get("category") or "") in required_categories
    }
    required_missing = {
        str(record.get("path") or "")
        for record in artifacts
        if isinstance(record, dict)
        and not record.get("exists")
        and str(record.get("category") or "") in required_categories
        and str(record.get("path") or "")
    }
    optional_diagnostics = {
        str(record.get("path") or "")
        for record in artifacts
        if isinstance(record, dict)
        and not record.get("exists")
        and str(record.get("category") or "") == "harness_report"
        and str(record.get("path") or "")
        and str(record.get("path") or "") not in required_paths
    }
    return required_missing, optional_diagnostics


def _diagnose_improvement(workspace: Path) -> int:
    from tooling.harness import (
        build_improvement_payload,
        render_improvement_report,
        write_improvement_json,
        write_improvement_report,
    )

    if not workspace.exists():
        print(f"Workspace not found: {workspace}", file=sys.stderr)
        return 2

    exit_code, payload = build_improvement_payload(workspace=workspace, repo_root=REPO_ROOT)
    write_improvement_report(workspace=workspace, report=render_improvement_report(payload))
    write_improvement_json(workspace=workspace, payload=payload)
    suggestions = payload.get("suggestions") if isinstance(payload.get("suggestions"), list) else []
    history = payload.get("repair_history") if isinstance(payload.get("repair_history"), dict) else {}
    opportunities = (
        payload.get("quality_opportunities")
        if isinstance(payload.get("quality_opportunities"), list)
        else []
    )
    print(f"Improve: {payload.get('verdict') or 'ATTENTION'}")
    print(f"Open repairs: {len(suggestions)}")
    print(f"Non-blocking quality opportunities: {len(opportunities)}")
    print(f"Resolved repairs: {history.get('resolved_count', 0)}")
    if suggestions:
        first = suggestions[0] if isinstance(suggestions[0], dict) else {}
        print(f"First repair: {first.get('repair_surface') or 'inspect report'}")
    print(f"Inspect: {workspace / 'output' / 'IMPROVEMENT_REPORT.md'}")
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
