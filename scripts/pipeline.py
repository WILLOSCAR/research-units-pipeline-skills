from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.common import (
    atomic_write_text,
    copy_tree,
    load_workspace_pipeline_spec,
    requested_delivery_formats,
    resolve_pipeline_spec_path,
    shell_quote,
    today_iso,
)
from tooling.completion import commit_unit_completion
from tooling.executor import run_one_unit
from tooling.harness import (
    build_artifact_pack_payload,
    build_doctor_payload,
    build_improvement_payload,
    build_run_audit_payload,
    build_run_audit_diff_payload,
    load_run_audit_payload,
    render_artifact_pack_report,
    render_artifact_pack_excerpt_markdown,
    render_artifact_pack_excerpt_tsv,
    render_doctor_report,
    render_improvement_report,
    render_run_audit_diff_report,
    render_run_audit_report,
    write_artifact_pack_json,
    write_artifact_pack_report,
    write_artifact_pack_excerpt_markdown,
    write_artifact_pack_excerpt_tsv,
    write_doctor_json,
    write_doctor_report,
    write_improvement_json,
    write_improvement_report,
    write_run_audit_diff_json,
    write_run_audit_diff_report,
    write_run_audit_json,
    write_run_audit_report,
)
from tooling.pipeline_spec import PipelineSpec
from tooling.run_state import (
    capture_checkpoint_review_basis,
    checkpoint_approval_recorded,
    ConcurrentInvocationError,
    ensure_run_state,
    finish_attempt,
    initialize_run_state,
    open_attempt_for_unit,
    record_human_decision,
    require_current_kernel_lock,
    RevisionLockDriftError,
    start_attempt,
    workspace_has_durable_run_evidence,
    workspace_invocation_lock,
)


LOCKED_WORKSPACE_COMMANDS = frozenset(
    {"init", "kickoff", "run-one", "run", "doctor", "audit", "improve", "pack", "approve", "mark"}
)
UNLOCKED_COMMANDS = frozenset({"audit-diff"})

def _normalize_pipeline_name(pipeline: str) -> str:
    return str(pipeline or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(prog="pipeline.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init_p = sub.add_parser("init", help="Initialize a workspace from template + pipeline units template")
    init_p.add_argument("--workspace", required=True, help="Workspace directory")
    init_p.add_argument("--pipeline", required=True, help="Pipeline name or path (e.g., arxiv-survey)")
    init_p.add_argument("--goal", default="", help="Concrete outcome request to persist in GOAL.md and the Run ledger")
    init_p.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite non-Run workspace template files; never replaces durable Run evidence",
    )
    init_p.add_argument(
        "--overwrite-units",
        action="store_true",
        help="Overwrite UNITS.csv only before durable Run evidence exists",
    )

    kickoff_p = sub.add_parser("kickoff", help="Kick off a pipeline run from a topic (init workspace + draft decisions)")
    kickoff_p.add_argument("--topic", required=True, help="Topic/goal (used to create workspace and seed queries)")
    kickoff_p.add_argument("--pipeline", default="", help="Pipeline name or path (default: auto-pick from topic)")
    kickoff_p.add_argument("--workspace", default="", help="Workspace directory (default: ./workspaces/<slug>/)")
    kickoff_p.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite non-Run workspace template files; never replaces durable Run evidence",
    )
    kickoff_p.add_argument(
        "--overwrite-units",
        action="store_true",
        help="Overwrite UNITS.csv only before durable Run evidence exists",
    )
    kickoff_p.add_argument("--run", action="store_true", help="After kickoff, run units until blocked/complete")
    kickoff_p.add_argument("--max-steps", type=int, default=999, help="Maximum units to attempt when using --run")
    kickoff_p.add_argument(
        "--strict",
        action="store_true",
        help="Enable quality-gate mode (block when outputs look like scaffolding stubs; writes output/QUALITY_GATE.md)",
    )
    kickoff_p.add_argument(
        "--auto-approve",
        action="append",
        default=[],
        help="Auto-tick approvals in DECISIONS.md (repeatable, e.g., --auto-approve C2).",
    )

    run_one_p = sub.add_parser("run-one", help="Execute exactly one runnable unit from UNITS.csv")
    run_one_p.add_argument("--workspace", required=True, help="Workspace directory")
    run_one_p.add_argument("--strict", action="store_true", help="Enable quality-gate mode (see kickoff --strict)")
    run_one_p.add_argument(
        "--auto-approve",
        action="append",
        default=[],
        help="Auto-tick approvals in DECISIONS.md (repeatable, e.g., --auto-approve C2).",
    )

    run_p = sub.add_parser("run", help="Run units until blocked or complete")
    run_p.add_argument("--workspace", required=True, help="Workspace directory")
    run_p.add_argument("--max-steps", type=int, default=999, help="Maximum units to attempt")
    run_p.add_argument("--strict", action="store_true", help="Enable quality-gate mode (see kickoff --strict)")
    run_p.add_argument("--require-planned", action="store_true", help=argparse.SUPPRESS)
    run_p.add_argument(
        "--auto-approve",
        action="append",
        default=[],
        help="Auto-tick approvals in DECISIONS.md (repeatable, e.g., --auto-approve C2).",
    )

    doctor_p = sub.add_parser(
        "doctor",
        help="Reconcile recoverable run state, then diagnose the workspace without executing units",
    )
    doctor_p.add_argument("--workspace", required=True, help="Workspace directory")
    doctor_p.add_argument(
        "--write",
        action="store_true",
        help="Write doctor artifacts to output/DOCTOR_REPORT.md and output/DOCTOR_REPORT.json",
    )

    audit_p = sub.add_parser("audit", help="Audit a workspace run ledger and target artifact coverage")
    audit_p.add_argument("--workspace", required=True, help="Workspace directory")
    audit_p.add_argument("--write", action="store_true", help="Write audit artifacts to output/RUN_AUDIT.md and output/RUN_AUDIT.json")

    improve_p = sub.add_parser("improve", help="Suggest upstream repair surfaces from doctor and run-audit evidence")
    improve_p.add_argument("--workspace", required=True, help="Workspace directory")
    improve_p.add_argument(
        "--write",
        action="store_true",
        help="Write improvement artifacts to output/IMPROVEMENT_REPORT.md and output/IMPROVEMENT_REPORT.json",
    )

    pack_p = sub.add_parser("pack", help="Create a reviewable artifact-pack manifest for a workspace")
    pack_p.add_argument("--workspace", required=True, help="Workspace directory")
    pack_p.add_argument(
        "--write",
        action="store_true",
        help="Write artifact-pack artifacts to output/ARTIFACT_PACK.md and output/ARTIFACT_PACK.json",
    )
    pack_p.add_argument(
        "--write-excerpt",
        action="store_true",
        help="Write portable excerpt artifacts to output/ARTIFACT_PACK_EXCERPT.md and output/ARTIFACT_PACK_EXCERPT.tsv",
    )

    audit_diff_p = sub.add_parser("audit-diff", help="Compare two RUN_AUDIT.json payloads")
    audit_diff_p.add_argument("--before", required=True, help="Earlier output/RUN_AUDIT.json path")
    audit_diff_p.add_argument("--after", required=True, help="Later output/RUN_AUDIT.json path")
    audit_diff_p.add_argument(
        "--write",
        action="store_true",
        help="Write diff artifacts to RUN_AUDIT_DIFF.md and RUN_AUDIT_DIFF.json beside the after payload",
    )

    approve_p = sub.add_parser("approve", help="Tick an approval checkbox in DECISIONS.md (e.g., Approve C2)")
    approve_p.add_argument("--workspace", required=True, help="Workspace directory")
    approve_p.add_argument("--checkpoint", required=True, help="Checkpoint ID (e.g., C2)")
    approve_p.add_argument(
        "--focus-cluster",
        action="append",
        default=[],
        help="Idea-brainstorm C2 focus cluster; repeat for multiple selections",
    )
    approve_p.add_argument(
        "--hard-exclusion",
        action="append",
        default=[],
        help="Idea-brainstorm C2 exclusion; repeat for multiple exclusions",
    )

    mark_p = sub.add_parser("mark", help="Commit manual completion or perform a reasoned maintainer status override")
    mark_p.add_argument("--workspace", required=True, help="Workspace directory")
    mark_p.add_argument("--unit-id", required=True, help="Unit ID (e.g., U030)")
    mark_p.add_argument("--status", required=True, help="New status (TODO|DOING|DONE|BLOCKED|SKIP)")
    mark_p.add_argument(
        "--note",
        default="",
        help="Reason or acceptance note; required for every Unit status transition",
    )

    args = parser.parse_args()
    try:
        return _dispatch_with_workspace_lock(args)
    except (ConcurrentInvocationError, RevisionLockDriftError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _dispatch_with_workspace_lock(args: argparse.Namespace) -> int:
    workspace = _workspace_for_command_lock(args)
    if workspace is None:
        return _execute_command(args)
    _preflight_workspace_command(args=args, workspace=workspace)
    with workspace_invocation_lock(workspace=workspace, operation=f"pipeline.{args.cmd}"):
        if args.cmd in {"init", "kickoff"}:
            _require_pristine_run_workspace(workspace)
        elif args.cmd in {"run-one", "run", "approve", "mark"}:
            require_current_kernel_lock(workspace=workspace, repo_root=REPO_ROOT)
        return _execute_command(args)


def _workspace_for_command_lock(args: argparse.Namespace) -> Path | None:
    if args.cmd in UNLOCKED_COMMANDS:
        return None
    if args.cmd not in LOCKED_WORKSPACE_COMMANDS:
        raise RuntimeError(
            f"Command `{args.cmd}` has no declared Workspace lock policy; register it before enabling the command."
        )
    raw_workspace = str(getattr(args, "workspace", "") or "").strip()
    if raw_workspace:
        return Path(raw_workspace).resolve()
    if args.cmd == "kickoff":
        topic = str(getattr(args, "topic", "") or "").strip()
        if topic:
            return (REPO_ROOT / "workspaces" / _slugify(topic)).resolve()
    raise RuntimeError(f"Command `{args.cmd}` requires a resolvable Workspace before execution.")


def _preflight_workspace_command(*, args: argparse.Namespace, workspace: Path) -> None:
    """Reject invalid targets before lock metadata can create Workspace paths."""

    _ensure_not_repo_root(workspace, REPO_ROOT)
    _require_no_current_harness_state(workspace)
    if args.cmd not in {"init", "kickoff"}:
        if not workspace.is_dir():
            raise SystemExit(f"Workspace not found: {workspace}")
        return

    _require_pristine_run_workspace(workspace)

    if args.cmd == "kickoff":
        topic = str(getattr(args, "topic", "") or "").strip()
        if not topic:
            raise SystemExit("--topic must be non-empty")
        pipeline_name = str(getattr(args, "pipeline", "") or "").strip() or _auto_pick_pipeline(topic)
    else:
        pipeline_name = str(getattr(args, "pipeline", "") or "").strip()
    PipelineSpec.load(_resolve_pipeline_path(REPO_ROOT, pipeline_name))


def _require_pristine_run_workspace(workspace: Path) -> None:
    """Reject Run initialization both before and after acquiring the lock."""

    if workspace_has_durable_run_evidence(workspace):
        raise SystemExit(
            f"Workspace already contains durable Run evidence: {workspace}. "
            "Choose a new Workspace; --overwrite does not replace or migrate an existing Run."
        )


def _require_no_current_harness_state(workspace: Path) -> None:
    marker = workspace / ".harness-v3"
    if marker.exists() or marker.is_symlink():
        raise SystemExit(
            "Workspace contains current ResearchHarness state (.harness-v3); "
            "the legacy pipeline CLI will not inspect or mutate it. Use "
            "`uv run python -m research_harness loop work ...`."
        )


def _require_not_inside_current_harness_workspace(target: Path) -> None:
    """Refuse a path that lies anywhere beneath a current-harness Workspace.

    `_require_no_current_harness_state` checks one directory, which is right for
    a `--workspace` argument. A write target derived from a file path can sit at
    any depth below the Workspace root, so checking a fixed number of levels
    would leave deeper paths unguarded.
    """
    resolved = target.expanduser().resolve(strict=False)
    for candidate in (resolved, *resolved.parents):
        _require_no_current_harness_state(candidate)


def _execute_command(args: argparse.Namespace) -> int:

    repo_root = REPO_ROOT

    if args.cmd == "init":
        workspace = Path(args.workspace).resolve()
        _ensure_not_repo_root(workspace, repo_root)
        pipeline_path = _resolve_pipeline_path(repo_root, args.pipeline)
        spec = PipelineSpec.load(pipeline_path)

        template_dir = repo_root / ".codex" / "skills" / "workspace-init" / "assets" / "workspace-template"
        copy_tree(template_dir, workspace, overwrite=bool(args.overwrite))

        lock_text = (
            f"pipeline: {spec.path.relative_to(repo_root)}\n"
            f"units_template: {spec.units_template}\n"
            f"locked_at: {today_iso()}\n"
        )
        atomic_write_text(workspace / "PIPELINE.lock.md", lock_text)

        units_src = repo_root / spec.units_template
        units_dst = workspace / "UNITS.csv"
        if units_dst.exists() and not args.overwrite_units:
            # The workspace template ships with a stub UNITS.csv (U001 only). Treat it as safe to overwrite.
            template_units = (template_dir / "UNITS.csv").read_text(encoding="utf-8", errors="ignore").strip()
            existing_units = units_dst.read_text(encoding="utf-8", errors="ignore").strip()
            if existing_units != template_units:
                raise SystemExit(f"UNITS.csv already exists at {units_dst} (use --overwrite-units)")
        atomic_write_text(units_dst, units_src.read_text(encoding="utf-8"))

        goal_text = str(args.goal or "").strip()
        if goal_text:
            atomic_write_text(workspace / "GOAL.md", f"# Goal\n\n{goal_text}\n")

        first_checkpoint = spec.default_checkpoints[0] if spec.default_checkpoints else "C0"
        _update_status(
            workspace / "STATUS.md",
            spec_path=str(spec.path.relative_to(repo_root)),
            checkpoint=first_checkpoint,
        )
        initialize_run_state(
            workspace=workspace,
            repo_root=repo_root,
            pipeline_path=spec.path,
            units_template=spec.units_template,
            goal_text=goal_text,
        )
        return 0

    if args.cmd == "kickoff":
        topic = str(args.topic).strip()
        if not topic:
            raise SystemExit("--topic must be non-empty")

        pipeline_name = str(args.pipeline).strip() or _auto_pick_pipeline(topic)
        workspace = (
            Path(args.workspace).resolve()
            if str(args.workspace).strip()
            else (repo_root / "workspaces" / _slugify(topic)).resolve()
        )
        _ensure_not_repo_root(workspace, repo_root)

        pipeline_path = _resolve_pipeline_path(repo_root, pipeline_name)
        spec = PipelineSpec.load(pipeline_path)

        template_dir = repo_root / ".codex" / "skills" / "workspace-init" / "assets" / "workspace-template"
        copy_tree(template_dir, workspace, overwrite=bool(args.overwrite))

        atomic_write_text(workspace / "GOAL.md", f"# Goal\n\n{topic}\n")

        lock_text = (
            f"pipeline: {spec.path.relative_to(repo_root)}\n"
            f"units_template: {spec.units_template}\n"
            f"locked_at: {today_iso()}\n"
        )
        atomic_write_text(workspace / "PIPELINE.lock.md", lock_text)

        units_src = repo_root / spec.units_template
        units_dst = workspace / "UNITS.csv"
        if units_dst.exists() and not args.overwrite_units:
            # The workspace template ships with a stub UNITS.csv (U001 only). Treat it as safe to overwrite.
            template_units = (template_dir / "UNITS.csv").read_text(encoding="utf-8", errors="ignore").strip()
            existing_units = units_dst.read_text(encoding="utf-8", errors="ignore").strip()
            if existing_units != template_units:
                raise SystemExit(f"UNITS.csv already exists at {units_dst} (use --overwrite-units)")
        atomic_write_text(units_dst, units_src.read_text(encoding="utf-8"))

        first_checkpoint = spec.default_checkpoints[0] if spec.default_checkpoints else "C0"
        _update_status(
            workspace / "STATUS.md",
            spec_path=str(spec.path.relative_to(repo_root)),
            checkpoint=first_checkpoint,
        )
        initialize_run_state(
            workspace=workspace,
            repo_root=repo_root,
            pipeline_path=spec.path,
            units_template=spec.units_template,
            goal_text=topic,
        )

        router_script = repo_root / ".codex" / "skills" / "pipeline-router" / "scripts" / "run.py"
        if router_script.exists():
            subprocess.run(
                [
                    sys.executable,
                    str(router_script),
                    "--workspace",
                    str(workspace),
                    "--checkpoint",
                    "C0",
                ],
                check=False,
            )

        print(f"Workspace ready: {workspace}")
        if args.run:
            last_result = None
            for _ in range(int(args.max_steps)):
                result = run_one_unit(
                    workspace=workspace,
                    repo_root=repo_root,
                    strict=bool(args.strict),
                    auto_approve=set(args.auto_approve or []),
                )
                last_result = result
                print(f"{result.status}: {result.unit_id or '-'} {result.message}")
                if result.status != "DONE":
                    break
            return 0 if last_result is None or last_result.status in {"DONE", "IDLE"} else 2

        print(
            f"Next: run `uv run rh run start --workspace {shell_quote(workspace)}` "
            "(it will pause if a HUMAN approval is required)"
        )
        return 0

    if args.cmd == "run-one":
        workspace = Path(args.workspace).resolve()
        result = run_one_unit(
            workspace=workspace,
            repo_root=repo_root,
            strict=bool(args.strict),
            auto_approve=set(args.auto_approve or []),
        )
        print(f"{result.status}: {result.unit_id or '-'} {result.message}")
        return 0 if result.status in {"DONE", "IDLE"} else 2

    if args.cmd == "run":
        workspace = Path(args.workspace).resolve()
        if bool(args.require_planned):
            snapshot = ensure_run_state(workspace=workspace, repo_root=repo_root)
            if str(snapshot.get("state") or "") != "PLANNED":
                print(
                    f"Run has already left PLANNED state ({snapshot.get('state') or 'unknown'}); "
                    f"use `uv run rh run resume --workspace {workspace}`.",
                    file=sys.stderr,
                )
                return 2
        last_result = None
        for _ in range(int(args.max_steps)):
            result = run_one_unit(
                workspace=workspace,
                repo_root=repo_root,
                strict=bool(args.strict),
                auto_approve=set(args.auto_approve or []),
            )
            last_result = result
            print(f"{result.status}: {result.unit_id or '-'} {result.message}")
            if result.status != "DONE":
                break
        return 0 if last_result is None or last_result.status in {"DONE", "IDLE"} else 2

    if args.cmd == "doctor":
        workspace = Path(args.workspace).resolve()
        exit_code, payload = build_doctor_payload(workspace=workspace, repo_root=repo_root)
        report = render_doctor_report(payload)
        if args.write:
            report_path = write_doctor_report(workspace=workspace, report=report)
            json_path = write_doctor_json(workspace=workspace, payload=payload)
            print(f"Wrote {report_path}")
            print(f"Wrote {json_path}")
        print(report, end="")
        return exit_code

    if args.cmd == "audit":
        workspace = Path(args.workspace).resolve()
        exit_code, payload = build_run_audit_payload(workspace=workspace, repo_root=repo_root)
        report = render_run_audit_report(payload)
        if args.write:
            report_path = write_run_audit_report(workspace=workspace, report=report)
            json_path = write_run_audit_json(workspace=workspace, payload=payload)
            print(f"Wrote {report_path}")
            print(f"Wrote {json_path}")
        print(report, end="")
        return exit_code

    if args.cmd == "improve":
        workspace = Path(args.workspace).resolve()
        exit_code, payload = build_improvement_payload(workspace=workspace, repo_root=repo_root)
        report = render_improvement_report(payload)
        if args.write:
            report_path = write_improvement_report(workspace=workspace, report=report)
            json_path = write_improvement_json(workspace=workspace, payload=payload)
            print(f"Wrote {report_path}")
            print(f"Wrote {json_path}")
        print(report, end="")
        return exit_code

    if args.cmd == "pack":
        workspace = Path(args.workspace).resolve()
        exit_code, payload = build_artifact_pack_payload(workspace=workspace, repo_root=repo_root)
        report = render_artifact_pack_report(payload)
        if args.write:
            report_path = write_artifact_pack_report(workspace=workspace, report=report)
            json_path = write_artifact_pack_json(workspace=workspace, payload=payload)
            print(f"Wrote {report_path}")
            print(f"Wrote {json_path}")
        if args.write_excerpt:
            excerpt_md = write_artifact_pack_excerpt_markdown(
                workspace=workspace,
                excerpt=render_artifact_pack_excerpt_markdown(payload),
            )
            excerpt_tsv = write_artifact_pack_excerpt_tsv(
                workspace=workspace,
                excerpt=render_artifact_pack_excerpt_tsv(payload),
            )
            print(f"Wrote {excerpt_md}")
            print(f"Wrote {excerpt_tsv}")
        print(report, end="")
        return exit_code

    if args.cmd == "audit-diff":
        before_path = Path(args.before).resolve()
        after_path = Path(args.after).resolve()
        try:
            before_payload = load_run_audit_payload(before_path)
            after_payload = load_run_audit_payload(after_path)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2

        exit_code, payload = build_run_audit_diff_payload(
            before_path=before_path,
            before_payload=before_payload,
            after_path=after_path,
            after_payload=after_payload,
        )
        report = render_run_audit_diff_report(payload)
        if args.write:
            output_dir = after_path.parent
            # `audit-diff` takes no --workspace and so skips the Workspace lock,
            # but --write still creates files next to the --after report. That
            # report can sit at any depth inside a Workspace, so walk up rather
            # than checking a fixed number of levels.
            _require_not_inside_current_harness_workspace(output_dir)
            report_path = write_run_audit_diff_report(output_dir=output_dir, report=report)
            json_path = write_run_audit_diff_json(output_dir=output_dir, payload=payload)
            print(f"Wrote {report_path}")
            print(f"Wrote {json_path}")
        print(report, end="")
        return exit_code

    if args.cmd == "approve":
        workspace = Path(args.workspace).resolve()
        checkpoint = str(args.checkpoint).strip()
        if not checkpoint:
            raise SystemExit("--checkpoint must be non-empty")

        spec = load_workspace_pipeline_spec(workspace)
        decision_note = ""
        ensure_run_state(workspace=workspace, repo_root=repo_root)
        try:
            capture_checkpoint_review_basis(workspace=workspace, checkpoint=checkpoint)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if spec is not None and spec.name == "idea-brainstorm" and checkpoint == "C2":
            from tooling.ideation import (
                parse_idea_focus_decision,
                write_idea_focus_decision,
            )

            if args.focus_cluster:
                try:
                    write_idea_focus_decision(
                        workspace / "DECISIONS.md",
                        focus_clusters=args.focus_cluster,
                        hard_exclusions=args.hard_exclusion,
                    )
                except ValueError as exc:
                    raise SystemExit(str(exc)) from exc
            selected = parse_idea_focus_decision(workspace / "DECISIONS.md").get("focus_clusters") or []
            if not selected:
                raise SystemExit(
                    "idea-brainstorm C2 approval requires a recorded focus selection; "
                    "pass --focus-cluster or edit the C2 block in DECISIONS.md."
                )
            decision_note = "focus_clusters=" + "; ".join(str(item) for item in selected)

        review_basis = capture_checkpoint_review_basis(
            workspace=workspace,
            checkpoint=checkpoint,
        )

        from tooling.common import set_decisions_approval

        set_decisions_approval(workspace / "DECISIONS.md", checkpoint, approved=True)
        record_human_decision(
            workspace=workspace,
            action="checkpoint.approved",
            subject=checkpoint,
            decision="approved",
            note=decision_note,
            review_basis=review_basis,
        )
        print(f"Approved {checkpoint} in {workspace / 'DECISIONS.md'}")
        return 0

    if args.cmd == "mark":
        workspace = Path(args.workspace).resolve()
        unit_id = str(args.unit_id).strip()
        status = str(args.status).strip().upper()
        note = str(args.note).strip()
        if not unit_id:
            raise SystemExit("--unit-id must be non-empty")
        if status not in {"TODO", "DOING", "DONE", "BLOCKED", "SKIP"}:
            raise SystemExit("--status must be one of TODO|DOING|DONE|BLOCKED|SKIP")

        from tooling.common import (
            UnitsTable,
            decisions_has_approval,
            now_iso_seconds,
            parse_semicolon_list,
            set_decisions_approval,
            update_status_log,
        )
        from tooling.executor import (  # type: ignore
            _refresh_status_checkpoint,
            downstream_unit_ids,
            invalidate_downstream_units,
        )

        units_path = workspace / "UNITS.csv"
        if not units_path.exists():
            raise SystemExit(f"Missing {units_path}")
        ensure_run_state(workspace=workspace, repo_root=repo_root)
        table = UnitsTable.load(units_path)
        selected_row: dict[str, str] | None = None
        previous_status = ""
        for row in table.rows:
            if str(row.get("unit_id") or "").strip() == unit_id:
                previous_status = str(row.get("status") or "").strip().upper()
                selected_row = row
                break
        if selected_row is None:
            raise SystemExit(f"Unit not found: {unit_id}")
        if status != previous_status and not note:
            print(
                f"Cannot change {unit_id} from {previous_status or '<blank>'} to {status} without --note; "
                "Unit transitions require an explicit reason or acceptance assertion.",
                file=sys.stderr,
            )
            return 2

        if status == "DOING" and previous_status != "DOING":
            open_attempt = open_attempt_for_unit(workspace=workspace, unit_id=unit_id)
            if not open_attempt:
                start_attempt(
                    workspace=workspace,
                    repo_root=repo_root,
                    unit_id=unit_id,
                    skill=str(selected_row.get("skill") or "").strip(),
                    inputs=parse_semicolon_list(selected_row.get("inputs")),
                )

        if status == "DONE" and previous_status != "DONE":
            checkpoint = str(selected_row.get("checkpoint") or "").strip()
            owner = str(selected_row.get("owner") or "").strip().upper()
            skill = str(selected_row.get("skill") or "").strip()
            if (
                (owner == "HUMAN" or skill == "human-checkpoint")
                and checkpoint
                and (
                    not decisions_has_approval(workspace / "DECISIONS.md", checkpoint)
                    or not checkpoint_approval_recorded(
                        workspace=workspace,
                        checkpoint=checkpoint,
                    )
                )
            ):
                print(
                    f"Cannot mark {unit_id} DONE before checkpoint {checkpoint} has an active, "
                    "Artifact-bound approval; use `pipeline.py approve`.",
                    file=sys.stderr,
                )
                return 2
            completion = commit_unit_completion(
                workspace=workspace,
                repo_root=repo_root,
                unit_id=unit_id,
                message=note,
                resolved_failure_types=("missing_outputs", "missing_skill_adapter"),
            )
            if completion.status != "DONE":
                record_human_decision(
                    workspace=workspace,
                    action="unit.completion.rejected",
                    subject=unit_id,
                    decision=f"{previous_status or '<blank>'}->{completion.status}",
                    note=completion.message,
                )
                print(completion.message, file=sys.stderr)
                return 2
            table = UnitsTable.load(units_path)
        else:
            selected_row["status"] = status

        invalidated: list[str] = []
        checkpoint_candidates: list[str] = []
        if status not in {"DONE", "SKIP"}:
            affected_scope = {unit_id, *downstream_unit_ids(table, root_unit_id=unit_id)}
            for row in table.rows:
                row_id = str(row.get("unit_id") or "").strip()
                owner = str(row.get("owner") or "").strip().upper()
                skill = str(row.get("skill") or "").strip()
                checkpoint = str(row.get("checkpoint") or "").strip()
                if (
                    row_id in affected_scope
                    and checkpoint
                    and (owner == "HUMAN" or skill == "human-checkpoint")
                    and checkpoint not in checkpoint_candidates
                ):
                    checkpoint_candidates.append(checkpoint)
            invalidated = invalidate_downstream_units(table, root_unit_id=unit_id)
        if not (status == "DONE" and previous_status != "DONE"):
            table.save(units_path)

        decisions_path = workspace / "DECISIONS.md"
        revoked_checkpoints: list[str] = []
        for checkpoint in checkpoint_candidates:
            if decisions_has_approval(decisions_path, checkpoint):
                set_decisions_approval(decisions_path, checkpoint, approved=False)
                revoked_checkpoints.append(checkpoint)
        if note:
            update_status_log(workspace / "STATUS.md", f"{now_iso_seconds()} {unit_id} NOTE {note}")
        if invalidated:
            preview = ", ".join(invalidated[:8])
            suffix = " ..." if len(invalidated) > 8 else ""
            update_status_log(
                workspace / "STATUS.md",
                f"{now_iso_seconds()} {unit_id} NOTE reset downstream to TODO: {preview}{suffix}",
            )
        if revoked_checkpoints:
            update_status_log(
                workspace / "STATUS.md",
                f"{now_iso_seconds()} {unit_id} NOTE revoked stale checkpoint approval(s): "
                + ", ".join(revoked_checkpoints),
            )
        _refresh_status_checkpoint(workspace / "STATUS.md", table)
        if previous_status == "DOING" and status not in {"DOING", "DONE"}:
            open_attempt = open_attempt_for_unit(workspace=workspace, unit_id=unit_id)
            if open_attempt:
                finish_attempt(
                    workspace=workspace,
                    attempt_id=str(open_attempt.get("attempt_id") or ""),
                    unit_id=unit_id,
                    skill=str(open_attempt.get("skill") or ""),
                    status="INTERRUPTED",
                    exit_code=None,
                    outputs=parse_semicolon_list(selected_row.get("outputs")),
                    message=note or f"Maintainer changed Unit status to {status}.",
                )
        for checkpoint in revoked_checkpoints:
            record_human_decision(
                workspace=workspace,
                action="checkpoint.approval.revoked",
                subject=checkpoint,
                decision="revoked",
                note=f"Approval basis invalidated when {unit_id} changed to {status}.",
            )
        completion_accepted = status == "DONE" and previous_status != "DONE"
        record_human_decision(
            workspace=workspace,
            action="unit.completion.accepted" if completion_accepted else "unit.status.changed",
            subject=unit_id,
            decision=f"{previous_status or '<blank>'}->{status}",
            note=note,
        )
        msg = f"Marked {unit_id} as {status} in {units_path}"
        if invalidated:
            msg += f"; reset {len(invalidated)} downstream unit(s) to TODO"
        elif previous_status == status:
            msg += "; no downstream reset needed"
        if revoked_checkpoints:
            msg += "; revoked checkpoint approval(s): " + ", ".join(revoked_checkpoints)
        print(msg)
        return 0

    raise SystemExit("unreachable")


def _resolve_pipeline_path(repo_root: Path, pipeline: str) -> Path:
    normalized = _normalize_pipeline_name(pipeline)
    path = resolve_pipeline_spec_path(repo_root=repo_root, pipeline_value=normalized)
    if path is None:
        raise SystemExit(f"Pipeline not found: {normalized}")
    return path


def _ensure_not_repo_root(workspace: Path, repo_root: Path) -> None:
    if workspace.resolve() == repo_root.resolve():
        raise SystemExit("Refusing to use repo root as workspace. Use --workspace ./workspaces/<name>/")


def _slugify(text: str) -> str:
    out: list[str] = []
    prev_dash = False
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
            continue
        if not prev_dash:
            out.append("-")
            prev_dash = True
    slug = "".join(out).strip("-")
    return slug[:64] or "run"


def _auto_pick_pipeline(topic: str) -> str:
    topic_low = topic.lower()
    specs: list[PipelineSpec] = []
    for path in sorted((REPO_ROOT / "pipelines").glob("*.pipeline.md")):
        try:
            specs.append(PipelineSpec.load(path))
        except Exception:
            continue

    for spec in specs:
        if re.search(rf"(?<![a-z0-9-]){re.escape(spec.name.lower())}(?![a-z0-9-])", topic_low):
            return spec.name

    base_specs = [spec for spec in specs if not spec.variant_of]
    if not base_specs:
        return "arxiv-survey"
    scored = [
        (_routing_score(spec, topic_low), int(spec.routing_priority), spec.name, spec)
        for spec in base_specs
    ]
    matched = [item for item in scored if item[0] > 0]
    if matched:
        matched.sort(key=lambda item: (-item[0], -item[1], item[2]))
        selected = matched[0][3]
    else:
        defaults = sorted(
            [
                (int(spec.routing_priority), spec.name, spec)
                for spec in base_specs
                if spec.routing_default
            ],
            key=lambda item: (-item[0], item[1]),
        )
        selected = defaults[0][2] if defaults else next(
            (spec for spec in base_specs if spec.name == "arxiv-survey"),
            base_specs[0],
        )

    if not {"pdf", "latex"}.intersection(requested_delivery_formats(topic)):
        return selected.name

    variants: list[tuple[float, int, str]] = []
    for spec in specs:
        if not spec.variant_of:
            continue
        base_path = resolve_pipeline_spec_path(repo_root=REPO_ROOT, pipeline_value=spec.variant_of)
        if base_path is None:
            continue
        try:
            base_name = PipelineSpec.load(base_path).name
        except Exception:
            continue
        if base_name != selected.name:
            continue
        score = _routing_score(spec, topic_low)
        if score > 0:
            variants.append((score, int(spec.routing_priority), spec.name))

    if variants:
        variants.sort(key=lambda item: (-item[0], -item[1], item[2]))
        return variants[0][2]
    return selected.name


def _routing_score(spec: PipelineSpec, topic_low: str) -> float:
    topic_normalized = " ".join(topic_low.replace("-", " ").replace("_", " ").split())
    score = 0.0
    for hint in spec.routing_hints:
        hint_low = " ".join(hint.lower().replace("-", " ").replace("_", " ").split())
        if hint_low and hint_low in topic_normalized:
            score += max(1.0, len(hint_low.split()))
    return score


def _update_status(status_path: Path, *, spec_path: str, checkpoint: str) -> None:
    if status_path.exists():
        lines = status_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = ["# Status"]

    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        if line.strip() == "## Current pipeline":
            if i + 1 < len(lines) and lines[i + 1].lstrip().startswith("-"):
                out.append(f"- `{spec_path}`")
                i += 2
                continue
            out.append(f"- `{spec_path}`")
        if line.strip() == "## Current checkpoint":
            if i + 1 < len(lines) and lines[i + 1].lstrip().startswith("-"):
                out.append(f"- `{checkpoint}`")
                i += 2
                continue
            out.append(f"- `{checkpoint}`")
        i += 1

    if "## Current pipeline" not in "\n".join(lines):
        out.extend(["", "## Current pipeline", f"- `{spec_path}`"])
    if "## Current checkpoint" not in "\n".join(lines):
        out.extend(["", "## Current checkpoint", f"- `{checkpoint}`"])

    atomic_write_text(status_path, "\n".join(out).rstrip() + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
