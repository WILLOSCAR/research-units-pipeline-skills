from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from tooling.common import (
    UnitsTable,
    atomic_write_text,
    decisions_has_approval,
    ensure_dir,
    latest_outline_state,
    load_workspace_pipeline_spec,
    now_iso_seconds,
    parse_semicolon_list,
    pipeline_cli_command,
    set_decisions_approval,
    update_status_field,
    update_status_log,
)
from tooling.harness import write_unit_manifest


@dataclass(frozen=True)
class RunResult:
    unit_id: str | None
    status: str
    message: str


def _section_first_cutover_block_message(*, workspace: Path, outputs: list[str]) -> str | None:
    spec = load_workspace_pipeline_spec(workspace)
    if spec is None or str(spec.structure_mode or "").strip().lower() != "section_first":
        return None
    if "outline/outline_state.jsonl" not in outputs:
        return None

    latest = latest_outline_state(workspace)
    if not latest:
        return "Section-first cutover is not actionable yet: `outline/outline_state.jsonl` is missing or empty. Rerun `outline-refiner` after fixing the chapter/section layer."

    structure_phase = str(latest.get("structure_phase") or "").strip()
    h3_status = str(latest.get("h3_status") or "").strip().lower()
    reroute_target = str(latest.get("reroute_target") or "").strip()
    retry_budget = str(latest.get("retry_budget_remaining") or "").strip()
    reroute_reason = str(latest.get("reroute_reason") or "").strip()

    if structure_phase.lower() == "decomposed" and h3_status == "stable":
        return None

    missing: list[str] = []
    for key in ("structure_phase", "h3_status", "approval_status", "reroute_target", "retry_budget_remaining"):
        if key not in latest:
            missing.append(key)
            continue
        if key in {"structure_phase", "h3_status"} and not str(latest.get(key) or "").strip():
            missing.append(key)
    if missing:
        return (
            "Section-first cutover cannot advance because the latest `outline_state.jsonl` record is missing "
            f"required fields: {', '.join(missing)}."
        )

    reroute_label = reroute_target or "unknown"
    retry_label = retry_budget or "unknown"
    reason_suffix = f" Reason: {reroute_reason}." if reroute_reason else ""
    return (
        "Section-first cutover is still blocked; "
        f"latest outline state has structure_phase={structure_phase or 'missing'}, "
        f"h3_status={h3_status or 'missing'}, reroute_target={reroute_label}, "
        f"retry_budget_remaining={retry_label}.{reason_suffix} Fix the reroute target explicitly, then rerun this unit."
    )


def _append_run_error(*, workspace: Path, unit_id: str, skill: str, kind: str, message: str, log_rel: str | None) -> None:
    """Append a short failure record to `output/RUN_ERRORS.md` (workspace-local).

    This is a human-facing error sink that survives reruns and makes BLOCKED states debuggable.
    """

    try:
        ensure_dir(workspace / "output")
        out_path = workspace / "output" / "RUN_ERRORS.md"

        stamp = now_iso_seconds()
        log_hint = f" (log: `{log_rel}`)" if log_rel else ""
        line = f"- {stamp} `{unit_id}` `{skill}` `{kind}`: {message}{log_hint}"

        if out_path.exists() and out_path.stat().st_size > 0:
            prev = out_path.read_text(encoding="utf-8", errors="ignore").rstrip() + "\n"
        else:
            prev = "# Run errors\n\n"

        atomic_write_text(out_path, prev + line + "\n")
    except Exception:
        # Never let the runner crash while trying to log an error.
        return



def run_one_unit(
    *,
    workspace: Path,
    repo_root: Path,
    strict: bool = False,
    auto_approve: set[str] | None = None,
) -> RunResult:
    units_path = workspace / "UNITS.csv"
    status_path = workspace / "STATUS.md"
    if not units_path.exists():
        return RunResult(unit_id=None, status="ERROR", message=f"Missing {units_path}")

    table = UnitsTable.load(units_path)
    recovered = recover_stale_doing_units(table)
    if recovered:
        table.save(units_path)
        update_status_log(
            status_path,
            f"{now_iso_seconds()} RECOVERED stale DOING unit(s) to BLOCKED: {', '.join(recovered)}",
        )

    runnable_idx = _find_first_runnable(table)
    if runnable_idx is None:
        return RunResult(unit_id=None, status="IDLE", message="No runnable unit found")

    row = table.rows[runnable_idx]
    unit_id = row.get("unit_id", "").strip()
    skill = row.get("skill", "").strip()
    owner = row.get("owner", "").strip().upper()

    row["status"] = "DOING"
    table.save(units_path)
    update_status_log(status_path, f"{now_iso_seconds()} {unit_id} DOING {skill}")

    auto_approve_set = {str(x or "").strip().upper() for x in (auto_approve or set()) if str(x or "").strip()}

    if owner == "HUMAN":
        checkpoint = row.get("checkpoint", "").strip()
        if checkpoint and decisions_has_approval(workspace / "DECISIONS.md", checkpoint):
            row["status"] = "DONE"
            table.save(units_path)
            update_status_log(status_path, f"{now_iso_seconds()} {unit_id} DONE (HUMAN approved {checkpoint})")
            _refresh_status_checkpoint(status_path, table)
            return RunResult(unit_id=unit_id, status="DONE", message=f"HUMAN approved {checkpoint}")

        if checkpoint and checkpoint.upper() in auto_approve_set:
            set_decisions_approval(workspace / "DECISIONS.md", checkpoint, approved=True)
            row["status"] = "DONE"
            table.save(units_path)
            update_status_log(status_path, f"{now_iso_seconds()} {unit_id} DONE (AUTO approved {checkpoint})")
            _refresh_status_checkpoint(status_path, table)
            return RunResult(unit_id=unit_id, status="DONE", message=f"AUTO approved {checkpoint}")

        row["status"] = "BLOCKED"
        table.save(units_path)
        update_status_log(status_path, f"{now_iso_seconds()} {unit_id} BLOCKED (await HUMAN approval {checkpoint})")
        _refresh_status_checkpoint(status_path, table)
        return RunResult(unit_id=unit_id, status="BLOCKED", message=f"Await HUMAN approval {checkpoint} in DECISIONS.md")

    script_path = repo_root / ".codex" / "skills" / skill / "scripts" / "run.py"
    if not script_path.exists():
        row["status"] = "BLOCKED"
        table.save(units_path)
        skill_md = f".codex/skills/{skill}/SKILL.md"
        update_status_log(
            status_path,
            (
                f"{now_iso_seconds()} {unit_id} BLOCKED "
                f"(no script for {skill}; run manually per {skill_md} then mark DONE)"
            ),
        )
        _refresh_status_checkpoint(status_path, table)
        return RunResult(
            unit_id=unit_id,
            status="BLOCKED",
            message=(
                f"No executable script for skill '{skill}'. "
                f"Run it manually by following `{skill_md}`, write the required outputs, "
                f"then mark the unit DONE (e.g., `{pipeline_cli_command('mark', workspace=workspace, extra_args=('--unit-id', unit_id, '--status', 'DONE'))}`)."
            ),
        )

    inputs = parse_semicolon_list(row.get("inputs"))
    raw_outputs = parse_semicolon_list(row.get("outputs"))
    outputs = [_strip_optional_marker(rel) for rel in raw_outputs]
    required_outputs = [outputs[i] for i, rel in enumerate(raw_outputs) if not rel.strip().startswith("?")]
    checkpoint = row.get("checkpoint", "").strip()

    cmd = [
        sys.executable,
        str(script_path),
        "--workspace",
        str(workspace),
        "--unit-id",
        unit_id,
        "--inputs",
        ";".join(inputs),
        "--outputs",
        ";".join(outputs),
        "--checkpoint",
        checkpoint,
    ]

    log_rel = f"output/unit_logs/{unit_id}.{skill}.log"
    log_path = workspace / log_rel

    try:
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if completed.stdout or completed.stderr or completed.returncode != 0:
            ensure_dir(log_path.parent)
            body = [
                f"# Unit log\n",
                f"- unit_id: {unit_id}\n",
                f"- skill: {skill}\n",
                f"- exit: {completed.returncode}\n",
                f"- cmd: {' '.join(cmd)}\n",
                "\n## stdout\n\n",
                (completed.stdout or "(empty)") + "\n",
                "\n## stderr\n\n",
                (completed.stderr or "(empty)") + "\n",
            ]
            atomic_write_text(log_path, "".join(body))
    except Exception as exc:  # pragma: no cover
        row["status"] = "BLOCKED"
        table.save(units_path)
        update_status_log(status_path, f"{now_iso_seconds()} {unit_id} BLOCKED (exec error)")
        _append_run_error(
            workspace=workspace,
            unit_id=unit_id,
            skill=skill,
            kind="exec_error",
            message=f"{type(exc).__name__}: {exc}",
            log_rel=None,
        )
        _refresh_status_checkpoint(status_path, table)
        return RunResult(unit_id=unit_id, status="BLOCKED", message=str(exc))

    def record_manifest(status: str) -> None:
        try:
            write_unit_manifest(
                workspace=workspace,
                unit_id=unit_id,
                skill=skill,
                outputs=outputs,
                exit_code=int(completed.returncode),
                status=status,
            )
        except Exception as exc:  # pragma: no cover
            _append_run_error(
                workspace=workspace,
                unit_id=unit_id,
                skill=skill,
                kind="manifest_error",
                message=f"{type(exc).__name__}: {exc}",
                log_rel=log_rel if log_path.exists() else None,
            )

    missing = [rel for rel in required_outputs if rel and not (workspace / rel).exists()]
    if completed.returncode == 0 and not missing:
        if strict:
            from tooling.quality_gate import check_unit_outputs, write_quality_report
            try:
                issues = check_unit_outputs(skill=skill, workspace=workspace, outputs=outputs)
            except Exception as exc:  # pragma: no cover
                from tooling.quality_gate import QualityIssue

                issues = [
                    QualityIssue(
                        code="quality_gate_exception",
                        message=f"Quality gate crashed: {type(exc).__name__}: {exc}",
                    )
                ]
            # Avoid confusing stale QUALITY_GATE.md after a successful run.
            report_path = workspace / "output" / "QUALITY_GATE.md"
            if issues or report_path.exists():
                write_quality_report(workspace=workspace, unit_id=unit_id, skill=skill, issues=issues)
            if issues:
                row["status"] = "BLOCKED"
                table.save(units_path)
                record_manifest("BLOCKED")
                rel_report = str((workspace / "output" / "QUALITY_GATE.md").relative_to(workspace))
                update_status_log(status_path, f"{now_iso_seconds()} {unit_id} BLOCKED (quality gate: {rel_report})")
                _refresh_status_checkpoint(status_path, table)
                reroute_hint = _reroute_hint(workspace)
                return RunResult(
                    unit_id=unit_id,
                    status="BLOCKED",
                    message=f"Quality gate failed; see {rel_report}" + (f"; {reroute_hint}" if reroute_hint else ""),
                )

        cutover_block = _section_first_cutover_block_message(workspace=workspace, outputs=outputs)
        if cutover_block:
            row["status"] = "BLOCKED"
            table.save(units_path)
            record_manifest("BLOCKED")
            update_status_log(status_path, f"{now_iso_seconds()} {unit_id} BLOCKED (section-first cutover)")
            _append_run_error(
                workspace=workspace,
                unit_id=unit_id,
                skill=skill,
                kind="section_first_cutover",
                message=cutover_block,
                log_rel=log_rel if log_path.exists() else None,
            )
            _refresh_status_checkpoint(status_path, table)
            return RunResult(unit_id=unit_id, status="BLOCKED", message=cutover_block)

        row["status"] = "DONE"
        table.save(units_path)
        record_manifest("DONE")
        update_status_log(status_path, f"{now_iso_seconds()} {unit_id} DONE {skill}")
        _refresh_status_checkpoint(status_path, table)
        return RunResult(unit_id=unit_id, status="DONE", message="OK")

    row["status"] = "BLOCKED"
    table.save(units_path)
    record_manifest("BLOCKED")
    if missing:
        update_status_log(status_path, f"{now_iso_seconds()} {unit_id} BLOCKED (missing outputs: {', '.join(missing)})")
        _append_run_error(
            workspace=workspace,
            unit_id=unit_id,
            skill=skill,
            kind="missing_outputs",
            message=f"Missing outputs: {', '.join(missing)}",
            log_rel=log_rel if log_path.exists() else None,
        )
        _refresh_status_checkpoint(status_path, table)
        return RunResult(unit_id=unit_id, status="BLOCKED", message=f"Missing outputs: {', '.join(missing)}" + (f"; see {log_rel}" if log_path.exists() else ""))
    update_status_log(status_path, f"{now_iso_seconds()} {unit_id} BLOCKED (script failed)")
    _append_run_error(
        workspace=workspace,
        unit_id=unit_id,
        skill=skill,
        kind="script_failed",
        message=f"Skill script failed (exit {completed.returncode})",
        log_rel=log_rel if log_path.exists() else None,
    )
    _refresh_status_checkpoint(status_path, table)
    return RunResult(unit_id=unit_id, status="BLOCKED", message=f"Skill script failed (exit {completed.returncode})" + (f"; see {log_rel}" if log_path.exists() else ""))


def recover_stale_doing_units(table: UnitsTable) -> list[str]:
    """Move the first resumable stale `DOING` unit back into the runnable queue.

    The runner is single-unit and single-process. A persisted `DOING` usually means
    the previous harness process was interrupted after claiming the unit but before
    it could write DONE/BLOCKED. Recover only one unit per invocation so reruns stay
    auditable and downstream state is not rewritten speculatively.
    """

    status_ok = {"DONE", "SKIP"}
    unit_by_id = {row.get("unit_id", ""): row for row in table.rows}
    for row in table.rows:
        if row.get("status", "").strip().upper() != "DOING":
            continue
        deps = parse_semicolon_list(row.get("depends_on"))
        deps_done = True
        for dep_id in deps:
            dep = unit_by_id.get(dep_id)
            if not dep or dep.get("status", "").strip().upper() not in status_ok:
                deps_done = False
                break
        if not deps_done:
            return []
        row["status"] = "BLOCKED"
        unit_id = row.get("unit_id", "").strip()
        return [unit_id] if unit_id else []
    return []


def _find_first_runnable(table: UnitsTable) -> int | None:
    status_ok = {"DONE", "SKIP"}
    unit_by_id = {row.get("unit_id", ""): row for row in table.rows}
    for idx, row in enumerate(table.rows):
        if row.get("status", "").strip().upper() not in {"TODO", "BLOCKED"}:
            continue
        deps = parse_semicolon_list(row.get("depends_on"))
        if not deps:
            return idx
        deps_done = True
        for dep_id in deps:
            dep = unit_by_id.get(dep_id)
            if not dep:
                deps_done = False
                break
            if dep.get("status", "").strip().upper() not in status_ok:
                deps_done = False
                break
        if deps_done:
            return idx
    return None


def _refresh_status_checkpoint(status_path: Path, table: UnitsTable) -> None:
    checkpoint = _compute_current_checkpoint(table)
    update_status_field(status_path, "Current checkpoint", checkpoint)


def _compute_current_checkpoint(table: UnitsTable) -> str:
    for row in table.rows:
        if row.get("status", "").strip().upper() not in {"DONE", "SKIP"}:
            return (row.get("checkpoint") or "").strip() or "C0"
    return "DONE"


def invalidate_downstream_units(table: UnitsTable, *, root_unit_id: str) -> list[str]:
    """Reset all transitive downstream dependents of `root_unit_id` to TODO.

    This is used when a previously satisfied upstream unit is reopened for rerun.
    Keeping downstream units as DONE would otherwise leave stale artifacts in place
    and make later `run` invocations stop too early.
    """

    root = str(root_unit_id or "").strip()
    if not root:
        return []

    direct_children: dict[str, list[dict[str, str]]] = {}
    for row in table.rows:
        unit_id = str(row.get("unit_id") or "").strip()
        for dep in parse_semicolon_list(row.get("depends_on")):
            direct_children.setdefault(dep, []).append(row)

    affected: list[str] = []
    seen: set[str] = set()
    stack = [root]
    while stack:
        current = stack.pop()
        for child in direct_children.get(current, []):
            child_id = str(child.get("unit_id") or "").strip()
            if not child_id or child_id in seen:
                continue
            seen.add(child_id)
            if str(child.get("status") or "").strip().upper() != "TODO":
                child["status"] = "TODO"
                affected.append(child_id)
            stack.append(child_id)
    return affected


def _strip_optional_marker(relpath: str) -> str:
    relpath = (relpath or "").strip()
    if relpath.startswith("?"):
        return relpath[1:].strip()
    return relpath


def _reroute_hint(workspace: Path) -> str:
    path = workspace / "output" / "REROUTE_STATE.json"
    if not path.exists() or path.stat().st_size <= 0:
        return ""
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8", errors="ignore") or "{}")
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    target = str(data.get("reroute_target") or "").strip()
    status = str(data.get("status") or "").strip()
    phase = str(data.get("structure_phase") or "").strip()
    h3 = str(data.get("h3_status") or "").strip()
    reason = str(data.get("reroute_reason") or "").strip()
    if not any([target, status, phase, h3]):
        return ""
    parts = []
    if status:
        parts.append(f"reroute_status={status}")
    if target:
        parts.append(f"reroute_target={target}")
    if phase:
        parts.append(f"structure_phase={phase}")
    if h3:
        parts.append(f"h3_status={h3}")
    if reason:
        parts.append(f"reason={reason}")
    return ", ".join(parts)
