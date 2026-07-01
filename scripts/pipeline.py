from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.common import atomic_write_text, copy_tree, pipeline_cli_command, resolve_pipeline_spec_path, today_iso
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

def _normalize_pipeline_name(pipeline: str) -> str:
    return str(pipeline or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(prog="pipeline.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init_p = sub.add_parser("init", help="Initialize a workspace from template + pipeline units template")
    init_p.add_argument("--workspace", required=True, help="Workspace directory")
    init_p.add_argument("--pipeline", required=True, help="Pipeline name or path (e.g., arxiv-survey)")
    init_p.add_argument("--overwrite", action="store_true", help="Overwrite existing workspace files")
    init_p.add_argument("--overwrite-units", action="store_true", help="Overwrite workspace UNITS.csv")

    kickoff_p = sub.add_parser("kickoff", help="Kick off a pipeline run from a topic (init workspace + draft decisions)")
    kickoff_p.add_argument("--topic", required=True, help="Topic/goal (used to create workspace and seed queries)")
    kickoff_p.add_argument("--pipeline", default="", help="Pipeline name or path (default: auto-pick from topic)")
    kickoff_p.add_argument("--workspace", default="", help="Workspace directory (default: ./workspaces/<slug>/)")
    kickoff_p.add_argument("--overwrite", action="store_true", help="Overwrite existing workspace files")
    kickoff_p.add_argument("--overwrite-units", action="store_true", help="Overwrite workspace UNITS.csv")
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
    run_p.add_argument(
        "--auto-approve",
        action="append",
        default=[],
        help="Auto-tick approvals in DECISIONS.md (repeatable, e.g., --auto-approve C2).",
    )

    doctor_p = sub.add_parser("doctor", help="Diagnose workspace harness state without running units")
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

    mark_p = sub.add_parser("mark", help="Manually set a unit status in UNITS.csv (e.g., after LLM work)")
    mark_p.add_argument("--workspace", required=True, help="Workspace directory")
    mark_p.add_argument("--unit-id", required=True, help="Unit ID (e.g., U030)")
    mark_p.add_argument("--status", required=True, help="New status (TODO|DOING|DONE|BLOCKED|SKIP)")
    mark_p.add_argument("--note", default="", help="Optional note to append to STATUS.md run log")

    args = parser.parse_args()

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

        first_checkpoint = spec.default_checkpoints[0] if spec.default_checkpoints else "C0"
        _update_status(
            workspace / "STATUS.md",
            spec_path=str(spec.path.relative_to(repo_root)),
            checkpoint=first_checkpoint,
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
            f"Next: run `{pipeline_cli_command('run', workspace=workspace)}` "
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

        from tooling.common import set_decisions_approval

        set_decisions_approval(workspace / "DECISIONS.md", checkpoint, approved=True)
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

        from tooling.common import UnitsTable, now_iso_seconds, update_status_log
        from tooling.executor import _refresh_status_checkpoint, invalidate_downstream_units  # type: ignore

        units_path = workspace / "UNITS.csv"
        if not units_path.exists():
            raise SystemExit(f"Missing {units_path}")
        table = UnitsTable.load(units_path)
        found = False
        previous_status = ""
        for row in table.rows:
            if str(row.get("unit_id") or "").strip() == unit_id:
                previous_status = str(row.get("status") or "").strip().upper()
                row["status"] = status
                found = True
                break
        if not found:
            raise SystemExit(f"Unit not found: {unit_id}")

        invalidated: list[str] = []
        if status not in {"DONE", "SKIP"}:
            invalidated = invalidate_downstream_units(table, root_unit_id=unit_id)
        table.save(units_path)
        if note:
            update_status_log(workspace / "STATUS.md", f"{now_iso_seconds()} {unit_id} NOTE {note}")
        if invalidated:
            preview = ", ".join(invalidated[:8])
            suffix = " ..." if len(invalidated) > 8 else ""
            update_status_log(
                workspace / "STATUS.md",
                f"{now_iso_seconds()} {unit_id} NOTE reset downstream to TODO: {preview}{suffix}",
            )
        _refresh_status_checkpoint(workspace / "STATUS.md", table)
        msg = f"Marked {unit_id} as {status} in {units_path}"
        if invalidated:
            msg += f"; reset {len(invalidated)} downstream unit(s) to TODO"
        elif previous_status == status:
            msg += "; no downstream reset needed"
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

    scored: list[tuple[float, int, str]] = []
    for spec in specs:
        score = 0.0
        for hint in spec.routing_hints:
            hint_low = hint.lower()
            if hint_low and hint_low in topic_low:
                score += max(1.0, len(hint_low.split()))
        if score > 0:
            scored.append((score, int(spec.routing_priority), spec.name))

    if scored:
        scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
        return scored[0][2]

    defaults = sorted(
        [(int(spec.routing_priority), spec.name) for spec in specs if spec.routing_default],
        key=lambda item: (-item[0], item[1]),
    )
    if defaults:
        return defaults[0][1]
    return "arxiv-survey"


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
