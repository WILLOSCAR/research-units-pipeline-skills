from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from tooling.common import (
    UnitsTable,
    decisions_has_approval,
    now_iso_seconds,
    parse_semicolon_list,
    set_decisions_approval,
    update_status_field,
    update_status_log,
)


@dataclass(frozen=True)
class RunResult:
    unit_id: str | None
    status: str
    message: str


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
                f"then mark the unit DONE (e.g., `python scripts/pipeline.py mark --workspace {workspace} --unit-id {unit_id} --status DONE`)."
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

    try:
        completed = subprocess.run(cmd, check=False)
    except Exception as exc:  # pragma: no cover
        row["status"] = "BLOCKED"
        table.save(units_path)
        update_status_log(status_path, f"{now_iso_seconds()} {unit_id} BLOCKED (exec error)")
        return RunResult(unit_id=unit_id, status="BLOCKED", message=str(exc))

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
                rel_report = str((workspace / "output" / "QUALITY_GATE.md").relative_to(workspace))
                update_status_log(status_path, f"{now_iso_seconds()} {unit_id} BLOCKED (quality gate: {rel_report})")
                _refresh_status_checkpoint(status_path, table)
                return RunResult(
                    unit_id=unit_id,
                    status="BLOCKED",
                    message=f"Quality gate failed; see {rel_report}",
                )

        row["status"] = "DONE"
        table.save(units_path)
        update_status_log(status_path, f"{now_iso_seconds()} {unit_id} DONE {skill}")
        _refresh_status_checkpoint(status_path, table)
        return RunResult(unit_id=unit_id, status="DONE", message="OK")

    row["status"] = "BLOCKED"
    table.save(units_path)
    if missing:
        update_status_log(status_path, f"{now_iso_seconds()} {unit_id} BLOCKED (missing outputs: {', '.join(missing)})")
        _refresh_status_checkpoint(status_path, table)
        return RunResult(unit_id=unit_id, status="BLOCKED", message=f"Missing outputs: {', '.join(missing)}")
    update_status_log(status_path, f"{now_iso_seconds()} {unit_id} BLOCKED (script failed)")
    _refresh_status_checkpoint(status_path, table)
    return RunResult(unit_id=unit_id, status="BLOCKED", message=f"Skill script failed (exit {completed.returncode})")


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


def _strip_optional_marker(relpath: str) -> str:
    relpath = (relpath or "").strip()
    if relpath.startswith("?"):
        return relpath[1:].strip()
    return relpath
