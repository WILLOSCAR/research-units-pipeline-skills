from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tooling.common import (
    UnitsTable,
    atomic_write_text,
    ensure_dir,
    now_iso_seconds,
    parse_semicolon_list,
    pipeline_cli_command,
    resolve_pipeline_spec_path,
)


VALID_STATUSES = {"TODO", "DOING", "DONE", "BLOCKED", "SKIP"}
VALID_OWNERS = {"CODEX", "HUMAN"}
DOCTOR_REPORT_SCHEMA = "doctor-report.v1"
DOCTOR_REPORT_REQUIRED_KEYS = (
    "schema",
    "generated_at",
    "workspace",
    "repo",
    "pipeline_lock",
    "current_checkpoint",
    "units_present",
    "unit_status",
    "next_runnable",
    "resume_hint",
    "harness_issues",
    "remediation_summary",
    "recent_reports",
    "verdict",
    "exit_code",
)
RUN_AUDIT_SCHEMA = "run-audit.v1"
RUN_AUDIT_REQUIRED_KEYS = (
    "schema",
    "generated_at",
    "workspace",
    "repo",
    "pipeline_lock",
    "pipeline",
    "current_checkpoint",
    "run_ledger_files",
    "run_state",
    "unit_status",
    "target_artifacts",
    "unit_output_manifests",
    "harness_issues",
    "remediation_summary",
    "recent_reports",
    "verdict",
    "exit_code",
)
RUN_AUDIT_LEDGER_KEYS = (
    "PIPELINE.lock.md",
    "GOAL.md",
    "UNITS.csv",
    "STATUS.md",
    "CHECKPOINTS.md",
    "DECISIONS.md",
)
RUN_LEDGER_INSPECTION_PATHS = (
    "PIPELINE.lock.md",
    "GOAL.md",
    "UNITS.csv",
    "STATUS.md",
    "CHECKPOINTS.md",
    "DECISIONS.md",
    ".harness/goal.json",
    ".harness/run.json",
    ".harness/harness.lock.json",
    ".harness/events.jsonl",
    ".harness/attempts.jsonl",
    ".harness/decisions.jsonl",
    ".harness/artifacts.jsonl",
    ".harness/failures/ledger.jsonl",
    ".harness/evaluations/ledger.jsonl",
)
RUN_STATE_PHASES = {"attention", "in_progress", "complete_candidate"}
RUN_STATE_INTEGER_KEYS = (
    "units_total",
    "active_units",
    "target_artifacts_total",
    "target_artifacts_present",
    "target_artifacts_missing",
    "unit_output_manifest_count",
    "harness_issue_count",
    "error_count",
    "warn_count",
)
RUN_AUDIT_DIFF_SCHEMA = "run-audit-diff.v1"
RUN_AUDIT_DIFF_REQUIRED_KEYS = (
    "schema",
    "generated_at",
    "before_path",
    "after_path",
    "before_schema",
    "after_schema",
    "before_workspace",
    "after_workspace",
    "before_pipeline",
    "after_pipeline",
    "before_verdict",
    "after_verdict",
    "unit_status_delta",
    "target_artifact_changes",
    "manifest_counts",
    "harness_issue_counts",
    "comparison_issues",
    "verdict",
    "exit_code",
)
IMPROVEMENT_REPORT_SCHEMA = "improvement-report.v1"
IMPROVEMENT_REPORT_REQUIRED_KEYS = (
    "schema",
    "generated_at",
    "workspace",
    "repo",
    "pipeline",
    "artifact_interface_standard",
    "source_reports",
    "suggestions",
    "verdict",
    "exit_code",
)
ARTIFACT_PACK_SCHEMA = "artifact-pack.v1"
ARTIFACT_PACK_REQUIRED_KEYS = (
    "schema",
    "generated_at",
    "workspace",
    "repo",
    "pipeline",
    "artifact_interface_standard",
    "source_reports",
    "artifacts",
    "summary",
    "verdict",
    "exit_code",
)
ARTIFACT_PACK_LEDGER_PATHS = (
    "PIPELINE.lock.md",
    "GOAL.md",
    "UNITS.csv",
    "STATUS.md",
    "CHECKPOINTS.md",
    "DECISIONS.md",
    ".harness/goal.json",
    ".harness/run.json",
    ".harness/harness.lock.json",
    ".harness/events.jsonl",
    ".harness/attempts.jsonl",
    ".harness/artifacts.jsonl",
    ".harness/decisions.jsonl",
    ".harness/failures/ledger.jsonl",
    ".harness/evaluations/ledger.jsonl",
    ".harness/plan/planned.json",
    ".harness/plan/effective.json",
)
ARTIFACT_PACK_HARNESS_REPORT_PATHS = (
    "output/DOCTOR_REPORT.md",
    "output/DOCTOR_REPORT.json",
    "output/RUN_AUDIT.md",
    "output/RUN_AUDIT.json",
    "output/RUN_AUDIT_DIFF.md",
    "output/RUN_AUDIT_DIFF.json",
    "output/IMPROVEMENT_REPORT.md",
    "output/IMPROVEMENT_REPORT.json",
    "output/QUALITY_GATE.md",
    "output/CONTRACT_REPORT.md",
    "output/RUN_ERRORS.md",
)


@dataclass(frozen=True)
class HarnessIssue:
    level: str
    code: str
    message: str
    remediation_category: str = ""
    next_action: str = ""

    def __post_init__(self) -> None:
        default_category, default_action = ISSUE_REMEDIATION.get(
            self.code,
            (
                "inspect_workspace_state",
                "Inspect the workspace files named in the issue, then rerun `pipeline.py doctor`.",
            ),
        )
        if not self.remediation_category:
            object.__setattr__(self, "remediation_category", default_category)
        if not self.next_action:
            object.__setattr__(self, "next_action", default_action)


@dataclass(frozen=True)
class HarnessInspection:
    doctor_exit_code: int
    doctor: dict[str, Any]
    audit_exit_code: int
    audit: dict[str, Any]
    improvement_exit_code: int
    improvement: dict[str, Any]
    artifact_pack_exit_code: int
    artifact_pack: dict[str, Any]


@dataclass(frozen=True)
class _WorkspaceInspectionSnapshot:
    generated_at: str
    workspace: Path
    repo_root: Path
    pipeline_lock: str
    pipeline_name: str
    current_checkpoint: str
    run_identity: dict[str, Any]
    units_present: bool
    unit_status: dict[str, int]
    next_runnable: dict[str, str]
    doctor_issues: tuple[HarnessIssue, ...]
    audit_issues: tuple[HarnessIssue, ...]
    run_ledger_files: dict[str, bool]
    target_artifacts: tuple[dict[str, Any], ...]
    manifests: tuple[dict[str, Any], ...]
    declared_unit_output_paths: tuple[str, ...]
    failure_ledger_entries: tuple[dict[str, Any], ...]
    ledger_integrity: dict[str, Any]
    recent_reports: tuple[dict[str, str], ...]


ISSUE_REMEDIATION = {
    "missing_units": (
        "restore_workspace_contract",
        "Create or restore `UNITS.csv` from the selected pipeline unit template, then rerun `pipeline.py doctor`.",
    ),
    "missing_units_field": (
        "repair_units_contract",
        "Regenerate `UNITS.csv` from the selected template or add the missing column before running units.",
    ),
    "missing_unit_id": (
        "repair_units_contract",
        "Assign a stable, unique `unit_id` to every row in `UNITS.csv`.",
    ),
    "duplicate_unit_id": (
        "repair_units_contract",
        "Rename duplicate unit ids so each row can be addressed independently.",
    ),
    "invalid_status": (
        "repair_unit_status",
        "Set the unit status to one of TODO, DOING, DONE, BLOCKED, or SKIP.",
    ),
    "invalid_owner": (
        "repair_units_contract",
        "Set the unit owner to CODEX or HUMAN, or update the harness if a new owner is intentional.",
    ),
    "human_checkpoint_missing": (
        "record_human_checkpoint",
        "Add the checkpoint id that should be approved in `DECISIONS.md` before this HUMAN unit can advance.",
    ),
    "missing_dependency": (
        "repair_dependency_graph",
        "Add or restore the dependency unit, or remove the stale `depends_on` reference from `UNITS.csv`.",
    ),
    "dependency_cycle": (
        "repair_dependency_graph",
        "Break the dependency cycle in `UNITS.csv` so at least one upstream unit can run first.",
    ),
    "missing_done_output": (
        "repair_artifact_contract",
        "Restore the missing artifact, rerun the producing unit, or move the unit out of DONE before continuing.",
    ),
    "missing_target_artifact": (
        "repair_run_artifacts",
        "Finish or rerun the producing unit for this target artifact before treating the workspace as complete.",
    ),
    "done_without_successful_attempt": (
        "repair_completion_provenance",
        "Reopen the Unit and complete it through `pipeline.py run` or `pipeline.py mark` so a successful Attempt is recorded.",
    ),
    "done_without_manifest": (
        "repair_completion_provenance",
        "Reopen the Unit and recommit completion so its DONE Manifest is tied to the successful Attempt.",
    ),
    "done_output_unregistered": (
        "repair_completion_provenance",
        "Reopen and recommit the Unit so each required output receives an Artifact record.",
    ),
    "artifact_hash_mismatch": (
        "repair_completion_provenance",
        "Reopen the earliest producing Unit and regenerate downstream outputs from the current Artifact content.",
    ),
    "doing_without_open_attempt": (
        "repair_completion_provenance",
        "Inspect the Unit, then use `pipeline.py mark` with an explicit note to reopen or block it.",
    ),
    "doing_with_multiple_open_attempts": (
        "repair_completion_provenance",
        "Inspect the Attempt ledger and explicitly interrupt the superseded Attempt before continuing.",
    ),
}


def validate_units_table(table: UnitsTable) -> list[HarnessIssue]:
    issues: list[HarnessIssue] = []
    required_fields = {"unit_id", "skill", "owner", "depends_on", "checkpoint", "outputs", "status"}
    missing_fields = sorted(required_fields.difference(table.fieldnames))
    for field in missing_fields:
        issues.append(HarnessIssue("ERROR", "missing_units_field", f"`UNITS.csv` is missing `{field}`"))

    ids: list[str] = []
    duplicate_ids: set[str] = set()
    for row in table.rows:
        unit_id = _unit_id(row)
        if not unit_id:
            issues.append(HarnessIssue("ERROR", "missing_unit_id", "A unit row is missing `unit_id`"))
            continue
        if unit_id in ids:
            duplicate_ids.add(unit_id)
        ids.append(unit_id)

    for unit_id in sorted(duplicate_ids):
        issues.append(HarnessIssue("ERROR", "duplicate_unit_id", f"`{unit_id}` appears more than once"))

    unit_ids = set(ids)
    for row in table.rows:
        unit_id = _unit_id(row) or "<missing>"
        status = _status(row)
        owner = _owner(row)
        if status not in VALID_STATUSES:
            issues.append(HarnessIssue("ERROR", "invalid_status", f"`{unit_id}` has invalid status `{status or '<blank>'}`"))
        if owner not in VALID_OWNERS:
            issues.append(HarnessIssue("WARN", "invalid_owner", f"`{unit_id}` has unexpected owner `{owner or '<blank>'}`"))
        if owner == "HUMAN" and not str(row.get("checkpoint") or "").strip():
            issues.append(
                HarnessIssue("WARN", "human_checkpoint_missing", f"`{unit_id}` is HUMAN-owned but has no checkpoint")
            )
        for dep_id in parse_semicolon_list(row.get("depends_on")):
            if dep_id not in unit_ids:
                issues.append(
                    HarnessIssue("ERROR", "missing_dependency", f"`{unit_id}` depends on missing `{dep_id}`")
                )

    issues.extend(_cycle_issues(table))
    return issues


def _collect_workspace_inspection_snapshot(
    *,
    workspace: Path,
    repo_root: Path,
    include_deep_audit: bool = True,
) -> _WorkspaceInspectionSnapshot:
    """Read and reconcile facts shared by the requested inspection views.

    Doctor needs contract and implementation-freshness checks but not the full
    cross-ledger integrity pass. Audit, Improvement, and Artifact Pack share the
    deeper snapshot so composed inspection does that work only once.
    """

    from tooling.run_state import (
        ensure_run_state,
        inspect_doing_attempt_integrity,
        inspect_run_integrity,
        run_identity,
    )

    workspace = workspace.resolve()
    repo_root = repo_root.resolve()
    if (workspace / ".harness" / "run.json").exists():
        ensure_run_state(
            workspace=workspace,
            repo_root=repo_root,
            recover_stale_doing=True,
        )

    generated_at = now_iso_seconds()
    units_path = workspace / "UNITS.csv"
    lock_summary = _pipeline_lock_summary(workspace / "PIPELINE.lock.md")
    checkpoint = _current_checkpoint(workspace / "STATUS.md")
    manifests = tuple(_unit_manifest_records(workspace))
    shared_issues: list[HarnessIssue] = []
    implementation_issues: list[HarnessIssue] = []
    doctor_projection_issues: list[HarnessIssue] = []
    unit_status: dict[str, int] = {}
    next_runnable: dict[str, str] = {}
    declared_unit_output_paths: tuple[str, ...] = ()
    if not units_path.exists():
        shared_issues.append(HarnessIssue("ERROR", "missing_units", f"Missing `{units_path}`"))
    else:
        table = UnitsTable.load(units_path)
        shared_issues.extend(validate_units_table(table))
        shared_issues.extend(_workspace_artifact_issues(workspace=workspace, table=table))
        doctor_projection_issues.extend(
            HarnessIssue(
                str(record.get("level") or "ERROR"),
                str(record.get("code") or "doing_attempt_integrity_error"),
                str(record.get("message") or "DOING Unit Attempt integrity failed."),
            )
            for record in inspect_doing_attempt_integrity(workspace, unit_rows=table.rows)
        )
        implementation_issues.extend(
            _workspace_implementation_issues(
                workspace=workspace,
                table=table,
                repo_root=repo_root,
                manifests=manifests,
            )
        )
        counts = Counter(_status(row) or "<blank>" for row in table.rows)
        unit_status = {status: counts[status] for status in sorted(counts)}
        if include_deep_audit:
            declared_unit_output_paths = tuple(_declared_unit_output_paths_from_table(table))
        next_row = find_next_runnable(table)
        if next_row is not None:
            next_runnable = _next_runnable_record(next_row)

    spec = _load_locked_pipeline_spec(workspace=workspace, repo_root=repo_root) if include_deep_audit else None
    target_records: list[dict[str, Any]] = []
    target_issues: list[HarnessIssue] = []
    for relpath in tuple(spec.target_artifacts) if spec is not None else ():
        exists = (workspace / relpath).exists()
        target_records.append({"path": relpath, "exists": exists})
        if not exists:
            target_issues.append(
                HarnessIssue("ERROR", "missing_target_artifact", f"Target artifact `{relpath}` is missing")
            )

    ledger_integrity = inspect_run_integrity(workspace) if include_deep_audit else {}
    ledger_issues: list[HarnessIssue] = []
    for record in ledger_integrity.get("issues") or []:
        if not isinstance(record, dict):
            continue
        ledger_issues.append(
            HarnessIssue(
                str(record.get("level") or "ERROR"),
                str(record.get("code") or "ledger_integrity_error"),
                str(record.get("message") or "Run ledger integrity check failed."),
                remediation_category="repair_completion_provenance",
                next_action="Inspect the referenced Run ledger records, reopen the affected Unit, and recommit it through the Completion Protocol.",
            )
        )

    return _WorkspaceInspectionSnapshot(
        generated_at=generated_at,
        workspace=workspace,
        repo_root=repo_root,
        pipeline_lock=lock_summary,
        pipeline_name=spec.name if spec is not None else "",
        current_checkpoint=checkpoint,
        run_identity=run_identity(workspace),
        units_present=units_path.exists(),
        unit_status=unit_status,
        next_runnable=next_runnable,
        doctor_issues=tuple([*shared_issues, *implementation_issues, *doctor_projection_issues]),
        audit_issues=tuple([*shared_issues, *target_issues, *ledger_issues]),
        run_ledger_files=(
            {relpath: (workspace / relpath).exists() for relpath in RUN_LEDGER_INSPECTION_PATHS}
            if include_deep_audit
            else {}
        ),
        target_artifacts=tuple(target_records),
        manifests=manifests,
        declared_unit_output_paths=declared_unit_output_paths,
        failure_ledger_entries=(tuple(_failure_ledger_entries(workspace)) if include_deep_audit else ()),
        ledger_integrity=ledger_integrity,
        recent_reports=tuple(_recent_report_records(workspace)),
    )


def build_doctor_payload(*, workspace: Path, repo_root: Path) -> tuple[int, dict[str, Any]]:
    snapshot = _collect_workspace_inspection_snapshot(
        workspace=workspace,
        repo_root=repo_root,
        include_deep_audit=False,
    )
    return _build_doctor_payload_from_snapshot(snapshot)


def _build_doctor_payload_from_snapshot(
    snapshot: _WorkspaceInspectionSnapshot,
) -> tuple[int, dict[str, Any]]:
    issues = list(snapshot.doctor_issues)
    exit_code = 2 if any(issue.level == "ERROR" for issue in issues) else 0
    verdict = "PASS" if exit_code == 0 else "ATTENTION"
    remediation_counts = Counter(issue.remediation_category for issue in issues)
    payload = {
        "schema": DOCTOR_REPORT_SCHEMA,
        "generated_at": snapshot.generated_at,
        "workspace": str(snapshot.workspace),
        "repo": str(snapshot.repo_root),
        "pipeline_lock": snapshot.pipeline_lock,
        "run_identity": snapshot.run_identity,
        "current_checkpoint": snapshot.current_checkpoint,
        "units_present": snapshot.units_present,
        "unit_status": snapshot.unit_status,
        "next_runnable": snapshot.next_runnable,
        "resume_hint": _doctor_resume_hint(
            workspace=snapshot.workspace,
            next_runnable=snapshot.next_runnable,
            issues=issues,
        ),
        "harness_issues": [_issue_record(issue) for issue in issues],
        "remediation_summary": {category: remediation_counts[category] for category in sorted(remediation_counts)},
        "recent_reports": list(snapshot.recent_reports),
        "verdict": verdict,
        "exit_code": exit_code,
    }
    return exit_code, payload


def build_doctor_report(*, workspace: Path, repo_root: Path) -> tuple[int, str]:
    exit_code, payload = build_doctor_payload(workspace=workspace, repo_root=repo_root)
    return exit_code, render_doctor_report(payload)


def render_doctor_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Pipeline doctor",
        "",
        f"- Workspace: `{payload.get('workspace')}`",
        f"- Repo: `{payload.get('repo')}`",
    ]

    lock_summary = str(payload.get("pipeline_lock") or "")
    if lock_summary:
        lines.append(f"- Pipeline lock: `{lock_summary}`")
    else:
        lines.append("- Pipeline lock: missing")

    identity = payload.get("run_identity") or {}
    if identity.get("run_id"):
        lines.append(f"- Run: `{identity.get('run_id')}` ({identity.get('state') or 'unknown'})")
        lines.append(f"- Harness revision: `{identity.get('harness_revision') or 'unavailable'}`")

    lines.append(f"- Current checkpoint: `{payload.get('current_checkpoint')}`")

    if payload.get("units_present"):
        lines.extend(["", "## Unit status"])
        unit_status = payload.get("unit_status") or {}
        if unit_status:
            for status, count in unit_status.items():
                lines.append(f"- {status}: {count}")
        else:
            lines.append("- No units found")

        lines.extend(["", "## Next runnable"])
        next_runnable = payload.get("next_runnable") or {}
        if next_runnable:
            unit_id = str(next_runnable.get("unit_id") or "")
            title = str(next_runnable.get("title") or "(untitled)")
            skill = str(next_runnable.get("skill") or "(no skill)")
            status = str(next_runnable.get("status") or "").strip()
            status_suffix = f" [{status}]" if status else ""
            lines.append(f"- Next runnable: `{unit_id}` {title} (`{skill}`){status_suffix}")
        else:
            lines.append("- No runnable unit found")

    lines.extend(["", "## Resume hint"])
    resume_hint = payload.get("resume_hint") or {}
    if resume_hint:
        lines.append(f"- Kind: `{resume_hint.get('kind')}`")
        lines.append(f"- Command: `{resume_hint.get('command')}`")
        lines.append(f"- Reason: {resume_hint.get('reason')}")
    else:
        lines.append("- No resume hint available")

    lines.extend(["", "## Harness issues"])
    issues = payload.get("harness_issues") or []
    if issues:
        for issue in issues:
            lines.append(_format_issue_record(issue))
        lines.extend(["", "## Remediation summary"])
        for category, count in (payload.get("remediation_summary") or {}).items():
            lines.append(f"- `{category}`: {count}")
    else:
        lines.append("- No harness issues")

    lines.extend(["", "## Recent harness reports"])
    recent_reports = payload.get("recent_reports") or []
    if not recent_reports:
        lines.append("- No recent harness reports found")
    else:
        for report in recent_reports:
            preview = str(report.get("preview") or "")
            suffix = f": {preview}" if preview else ""
            lines.append(f"- `{report.get('path')}`{suffix}")

    return "\n".join(lines).rstrip() + "\n"


def write_doctor_report(*, workspace: Path, report: str) -> Path:
    path = workspace / "output" / "DOCTOR_REPORT.md"
    atomic_write_text(path, report)
    return path


def write_doctor_json(*, workspace: Path, payload: dict[str, Any]) -> Path:
    path = workspace / "output" / "DOCTOR_REPORT.json"
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return path


def validate_doctor_payload(payload: dict[str, Any]) -> list[str]:
    """Validate the stable shape future tooling can rely on for doctor-report.v1."""
    issues = _validate_payload_header(
        payload,
        expected_schema=DOCTOR_REPORT_SCHEMA,
        required_keys=DOCTOR_REPORT_REQUIRED_KEYS,
        string_keys=("generated_at", "workspace", "repo", "pipeline_lock", "current_checkpoint", "verdict"),
        integer_keys=("exit_code",),
        boolean_keys=("units_present",),
    )
    if not isinstance(payload, dict):
        return issues

    _validate_int_mapping(payload, key="unit_status", issues=issues)
    _validate_int_mapping(payload, key="remediation_summary", issues=issues)

    next_runnable = _validate_object_field(payload, key="next_runnable", issues=issues)
    if next_runnable is not None:
        for key in ("unit_id", "title", "skill"):
            if key in next_runnable and not isinstance(next_runnable.get(key), str):
                issues.append(f"`next_runnable.{key}` must be a string")

    resume_hint = _validate_object_field(payload, key="resume_hint", issues=issues)
    if resume_hint is not None:
        for key in ("kind", "command", "reason"):
            if key not in resume_hint:
                issues.append(f"`resume_hint.{key}` is missing")
            elif not isinstance(resume_hint.get(key), str):
                issues.append(f"`resume_hint.{key}` must be a string")

    _validate_issue_records(payload, issues=issues)
    _validate_recent_reports(payload, issues=issues)
    return issues


def validate_run_audit_payload(payload: dict[str, Any]) -> list[str]:
    """Validate the stable shape future tooling can rely on for run-audit.v1."""
    issues = _validate_payload_header(
        payload,
        expected_schema=RUN_AUDIT_SCHEMA,
        required_keys=RUN_AUDIT_REQUIRED_KEYS,
        string_keys=(
            "generated_at",
            "workspace",
            "repo",
            "pipeline_lock",
            "pipeline",
            "current_checkpoint",
            "verdict",
        ),
        integer_keys=("exit_code",),
    )
    if not isinstance(payload, dict):
        return issues

    run_ledger_files = _validate_object_field(payload, key="run_ledger_files", issues=issues)
    if run_ledger_files is not None:
        for key in RUN_AUDIT_LEDGER_KEYS:
            if key not in run_ledger_files:
                issues.append(f"`run_ledger_files.{key}` is missing")
            elif not isinstance(run_ledger_files.get(key), bool):
                issues.append(f"`run_ledger_files.{key}` must be a boolean")

    _validate_int_mapping(payload, key="unit_status", issues=issues)
    _validate_int_mapping(payload, key="remediation_summary", issues=issues)

    run_state = _validate_object_field(payload, key="run_state", issues=issues)
    if run_state is not None:
        _validate_run_state_record(run_state, field_path="run_state", issues=issues)

    target_artifacts = _validate_list_field(payload, key="target_artifacts", issues=issues)
    if target_artifacts is not None:
        for idx, item in enumerate(target_artifacts):
            if not isinstance(item, dict):
                issues.append(f"`target_artifacts[{idx}]` must be an object")
                continue
            if not isinstance(item.get("path"), str):
                issues.append(f"`target_artifacts[{idx}].path` must be a string")
            if not isinstance(item.get("exists"), bool):
                issues.append(f"`target_artifacts[{idx}].exists` must be a boolean")

    manifests = _validate_object_field(payload, key="unit_output_manifests", issues=issues)
    if manifests is not None:
        if not isinstance(manifests.get("count"), int):
            issues.append("`unit_output_manifests.count` must be an integer")
        by_status = manifests.get("by_status")
        if not isinstance(by_status, dict):
            issues.append("`unit_output_manifests.by_status` must be an object")
        else:
            for status, count in by_status.items():
                if not isinstance(status, str):
                    issues.append("`unit_output_manifests.by_status` keys must be strings")
                if not isinstance(count, int):
                    issues.append(f"`unit_output_manifests.by_status.{status}` must be an integer")
        if not isinstance(manifests.get("latest"), dict):
            issues.append("`unit_output_manifests.latest` must be an object")
        records = manifests.get("records")
        if not isinstance(records, list):
            issues.append("`unit_output_manifests.records` must be a list")
        else:
            for idx, record in enumerate(records):
                if not isinstance(record, dict):
                    issues.append(f"`unit_output_manifests.records[{idx}]` must be an object")

    if "attempts" in payload:
        _validate_attempt_summary(payload.get("attempts"), issues=issues)

    integrity = payload.get("ledger_integrity")
    if integrity is not None:
        if not isinstance(integrity, dict):
            issues.append("`ledger_integrity` must be an object")
        else:
            if not isinstance(integrity.get("enabled"), bool):
                issues.append("`ledger_integrity.enabled` must be a boolean")
            if not isinstance(integrity.get("run_id"), str):
                issues.append("`ledger_integrity.run_id` must be a string")
            if not isinstance(integrity.get("issue_count"), int):
                issues.append("`ledger_integrity.issue_count` must be an integer")
            if not isinstance(integrity.get("ledger_record_counts"), dict):
                issues.append("`ledger_integrity.ledger_record_counts` must be an object")
            if not isinstance(integrity.get("issues"), list):
                issues.append("`ledger_integrity.issues` must be a list")
            if "compatibility" in integrity:
                _validate_ledger_compatibility(integrity.get("compatibility"), issues=issues)

    _validate_issue_records(payload, issues=issues)
    _validate_recent_reports(payload, issues=issues)
    return issues


def validate_run_audit_diff_payload(payload: dict[str, Any]) -> list[str]:
    """Validate the stable shape future tooling can rely on for run-audit-diff.v1."""
    issues = _validate_payload_header(
        payload,
        expected_schema=RUN_AUDIT_DIFF_SCHEMA,
        required_keys=RUN_AUDIT_DIFF_REQUIRED_KEYS,
        string_keys=(
            "generated_at",
            "before_path",
            "after_path",
            "before_schema",
            "after_schema",
            "before_workspace",
            "after_workspace",
            "before_pipeline",
            "after_pipeline",
            "before_verdict",
            "after_verdict",
            "verdict",
        ),
        integer_keys=("exit_code",),
    )
    if not isinstance(payload, dict):
        return issues

    _validate_int_mapping(payload, key="unit_status_delta", issues=issues)
    _validate_count_delta(payload, key="manifest_counts", issues=issues)
    _validate_count_delta(payload, key="harness_issue_counts", issues=issues)
    if "attempt_comparison" in payload:
        _validate_attempt_comparison(payload.get("attempt_comparison"), issues=issues)

    changes = _validate_list_field(payload, key="target_artifact_changes", issues=issues)
    if changes is not None:
        for idx, item in enumerate(changes):
            if not isinstance(item, dict):
                issues.append(f"`target_artifact_changes[{idx}]` must be an object")
                continue
            if not isinstance(item.get("path"), str):
                issues.append(f"`target_artifact_changes[{idx}].path` must be a string")
            for key in ("before_exists", "after_exists"):
                if item.get(key) is not None and not isinstance(item.get(key), bool):
                    issues.append(f"`target_artifact_changes[{idx}].{key}` must be a boolean or null")
            if not isinstance(item.get("change"), str):
                issues.append(f"`target_artifact_changes[{idx}].change` must be a string")

    comparison_issues = _validate_list_field(payload, key="comparison_issues", issues=issues)
    if comparison_issues is not None:
        for idx, item in enumerate(comparison_issues):
            if not isinstance(item, str):
                issues.append(f"`comparison_issues[{idx}]` must be a string")

    return issues


def validate_improvement_payload(payload: dict[str, Any]) -> list[str]:
    """Validate the stable shape future tooling can rely on for improvement-report.v1."""
    issues = _validate_payload_header(
        payload,
        expected_schema=IMPROVEMENT_REPORT_SCHEMA,
        required_keys=IMPROVEMENT_REPORT_REQUIRED_KEYS,
        string_keys=(
            "generated_at",
            "workspace",
            "repo",
            "pipeline",
            "artifact_interface_standard",
            "verdict",
        ),
        integer_keys=("exit_code",),
    )
    if not isinstance(payload, dict):
        return issues

    source_reports = _validate_object_field(payload, key="source_reports", issues=issues)
    if source_reports is not None:
        for name, record in source_reports.items():
            if not isinstance(name, str):
                issues.append("`source_reports` keys must be strings")
            if not isinstance(record, dict):
                issues.append(f"`source_reports.{name}` must be an object")
                continue
            for key in ("schema", "verdict"):
                if not isinstance(record.get(key), str):
                    issues.append(f"`source_reports.{name}.{key}` must be a string")
            if not isinstance(record.get("exit_code"), int):
                issues.append(f"`source_reports.{name}.exit_code` must be an integer")

    suggestions = _validate_list_field(payload, key="suggestions", issues=issues)
    if suggestions is not None:
        required = (
            "id",
            "source_report",
            "observed_problem",
            "evidence",
            "upstream_interface",
            "repair_surface",
            "recommended_action",
            "validation",
        )
        for idx, suggestion in enumerate(suggestions):
            if not isinstance(suggestion, dict):
                issues.append(f"`suggestions[{idx}]` must be an object")
                continue
            for key in required:
                if not isinstance(suggestion.get(key), str):
                    issues.append(f"`suggestions[{idx}].{key}` must be a string")

    opportunities = payload.get("quality_opportunities", [])
    if not isinstance(opportunities, list):
        issues.append("`quality_opportunities` must be a list")
    else:
        for idx, opportunity in enumerate(opportunities):
            if not isinstance(opportunity, dict):
                issues.append(f"`quality_opportunities[{idx}]` must be an object")
                continue
            for key in ("dimension_id", "label", "evidence"):
                if not isinstance(opportunity.get(key), str):
                    issues.append(f"`quality_opportunities[{idx}].{key}` must be a string")
            for key in ("score", "max_score"):
                if not isinstance(opportunity.get(key), int):
                    issues.append(f"`quality_opportunities[{idx}].{key}` must be an integer")
            surfaces = opportunity.get("repair_surface")
            if not isinstance(surfaces, list) or any(not isinstance(item, str) for item in surfaces):
                issues.append(f"`quality_opportunities[{idx}].repair_surface` must be a list of strings")
    return issues


def validate_artifact_pack_payload(payload: dict[str, Any]) -> list[str]:
    """Validate the stable shape future tooling can rely on for artifact-pack.v1."""
    issues = _validate_payload_header(
        payload,
        expected_schema=ARTIFACT_PACK_SCHEMA,
        required_keys=ARTIFACT_PACK_REQUIRED_KEYS,
        string_keys=(
            "generated_at",
            "workspace",
            "repo",
            "pipeline",
            "artifact_interface_standard",
            "verdict",
        ),
        integer_keys=("exit_code",),
    )
    if not isinstance(payload, dict):
        return issues

    source_reports = _validate_object_field(payload, key="source_reports", issues=issues)
    if source_reports is not None:
        for name, record in source_reports.items():
            if not isinstance(name, str):
                issues.append("`source_reports` keys must be strings")
            if not isinstance(record, dict):
                issues.append(f"`source_reports.{name}` must be an object")
                continue
            for key in ("schema", "verdict"):
                if not isinstance(record.get(key), str):
                    issues.append(f"`source_reports.{name}.{key}` must be a string")
            if not isinstance(record.get("exit_code"), int):
                issues.append(f"`source_reports.{name}.exit_code` must be an integer")
            run_state = record.get("run_state")
            if run_state is not None:
                if not isinstance(run_state, dict):
                    issues.append(f"`source_reports.{name}.run_state` must be an object")
                else:
                    _validate_run_state_record(run_state, field_path=f"source_reports.{name}.run_state", issues=issues)

    artifacts = _validate_list_field(payload, key="artifacts", issues=issues)
    if artifacts is not None:
        for idx, record in enumerate(artifacts):
            if not isinstance(record, dict):
                issues.append(f"`artifacts[{idx}]` must be an object")
                continue
            for key in ("category", "path"):
                if not isinstance(record.get(key), str):
                    issues.append(f"`artifacts[{idx}].{key}` must be a string")
            if not isinstance(record.get("exists"), bool):
                issues.append(f"`artifacts[{idx}].exists` must be a boolean")

    summary = _validate_object_field(payload, key="summary", issues=issues)
    if summary is not None:
        for key in ("total", "present", "missing"):
            if not isinstance(summary.get(key), int):
                issues.append(f"`summary.{key}` must be an integer")
        by_category = summary.get("by_category")
        if not isinstance(by_category, dict):
            issues.append("`summary.by_category` must be an object")
        else:
            for category, counts in by_category.items():
                if not isinstance(category, str):
                    issues.append("`summary.by_category` keys must be strings")
                if not isinstance(counts, dict):
                    issues.append(f"`summary.by_category.{category}` must be an object")
                    continue
                for key in ("total", "present", "missing"):
                    if not isinstance(counts.get(key), int):
                        issues.append(f"`summary.by_category.{category}.{key}` must be an integer")

    return issues


def _validate_payload_header(
    payload: Any,
    *,
    expected_schema: str,
    required_keys: tuple[str, ...],
    string_keys: tuple[str, ...] = (),
    integer_keys: tuple[str, ...] = (),
    boolean_keys: tuple[str, ...] = (),
) -> list[str]:
    issues: list[str] = []
    if not isinstance(payload, dict):
        return ["payload must be a JSON object"]

    for key in required_keys:
        if key not in payload:
            issues.append(f"missing top-level key `{key}`")

    schema = payload.get("schema")
    if schema != expected_schema:
        issues.append(f"`schema` must be `{expected_schema}`")

    for key in string_keys:
        if key in payload and not isinstance(payload.get(key), str):
            issues.append(f"`{key}` must be a string")
    for key in integer_keys:
        if key in payload and not isinstance(payload.get(key), int):
            issues.append(f"`{key}` must be an integer")
    for key in boolean_keys:
        if key in payload and not isinstance(payload.get(key), bool):
            issues.append(f"`{key}` must be a boolean")
    return issues


def _validate_object_field(payload: dict[str, Any], *, key: str, issues: list[str]) -> dict[str, Any] | None:
    value = payload.get(key)
    if not isinstance(value, dict):
        issues.append(f"`{key}` must be an object")
        return None
    return value


def _validate_list_field(payload: dict[str, Any], *, key: str, issues: list[str]) -> list[Any] | None:
    value = payload.get(key)
    if not isinstance(value, list):
        issues.append(f"`{key}` must be a list")
        return None
    return value


def _validate_int_mapping(payload: dict[str, Any], *, key: str, issues: list[str]) -> None:
    value = payload.get(key)
    if not isinstance(value, dict):
        issues.append(f"`{key}` must be an object")
        return
    for item_key, item_value in value.items():
        if not isinstance(item_key, str):
            issues.append(f"`{key}` keys must be strings")
        if not isinstance(item_value, int):
            issues.append(f"`{key}.{item_key}` must be an integer")


def _validate_count_delta(payload: dict[str, Any], *, key: str, issues: list[str]) -> None:
    value = _validate_object_field(payload, key=key, issues=issues)
    if value is None:
        return
    for item_key in ("before", "after", "delta"):
        if not isinstance(value.get(item_key), int):
            issues.append(f"`{key}.{item_key}` must be an integer")


def _validate_issue_records(payload: dict[str, Any], *, issues: list[str]) -> None:
    records = payload.get("harness_issues")
    if not isinstance(records, list):
        issues.append("`harness_issues` must be a list")
        return
    required = ("level", "code", "message", "remediation_category", "next_action")
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            issues.append(f"`harness_issues[{idx}]` must be an object")
            continue
        for key in required:
            if not isinstance(record.get(key), str):
                issues.append(f"`harness_issues[{idx}].{key}` must be a string")


def _validate_recent_reports(payload: dict[str, Any], *, issues: list[str]) -> None:
    records = payload.get("recent_reports")
    if not isinstance(records, list):
        issues.append("`recent_reports` must be a list")
        return
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            issues.append(f"`recent_reports[{idx}]` must be an object")
            continue
        if not isinstance(record.get("path"), str):
            issues.append(f"`recent_reports[{idx}].path` must be a string")
        if not isinstance(record.get("preview"), str):
            issues.append(f"`recent_reports[{idx}].preview` must be a string")


def _validate_run_state_record(record: dict[str, Any], *, field_path: str, issues: list[str]) -> None:
    phase = record.get("phase")
    if not isinstance(phase, str):
        issues.append(f"`{field_path}.phase` must be a string")
    elif phase not in RUN_STATE_PHASES:
        issues.append(f"`{field_path}.phase` must be one of {', '.join(sorted(RUN_STATE_PHASES))}")
    for key in RUN_STATE_INTEGER_KEYS:
        if not isinstance(record.get(key), int):
            issues.append(f"`{field_path}.{key}` must be an integer")


def _validate_attempt_summary(value: Any, *, issues: list[str]) -> None:
    if not isinstance(value, dict):
        issues.append("`attempts` must be an object")
        return
    for key in ("started", "finished", "open", "retry_units", "extra_attempts"):
        if not isinstance(value.get(key), int):
            issues.append(f"`attempts.{key}` must be an integer")
    for key in ("by_status", "by_execution_mode"):
        mapping = value.get(key)
        if not isinstance(mapping, dict):
            issues.append(f"`attempts.{key}` must be an object")
            continue
        for item_key, item_value in mapping.items():
            if not isinstance(item_key, str):
                issues.append(f"`attempts.{key}` keys must be strings")
            if not isinstance(item_value, int):
                issues.append(f"`attempts.{key}.{item_key}` must be an integer")

    metrics = value.get("process_metrics")
    if not isinstance(metrics, dict):
        issues.append("`attempts.process_metrics` must be an object")
        return
    for key in ("measured_attempts", "stdout_chars", "stderr_chars"):
        if not isinstance(metrics.get(key), int):
            issues.append(f"`attempts.process_metrics.{key}` must be an integer")
    total = metrics.get("total_elapsed_ms")
    if not isinstance(total, (int, float)) or isinstance(total, bool):
        issues.append("`attempts.process_metrics.total_elapsed_ms` must be a number")
    for key in ("mean_elapsed_ms", "max_elapsed_ms"):
        item = metrics.get(key)
        if item is not None and (
            not isinstance(item, (int, float))
            or isinstance(item, bool)
        ):
            issues.append(f"`attempts.process_metrics.{key}` must be a number or null")


def _validate_attempt_comparison(value: Any, *, issues: list[str]) -> None:
    if not isinstance(value, dict):
        issues.append("`attempt_comparison` must be an object")
        return
    if not isinstance(value.get("available"), bool):
        issues.append("`attempt_comparison.available` must be a boolean")
    if not isinstance(value.get("note"), str):
        issues.append("`attempt_comparison.note` must be a string")

    counters = value.get("counters")
    if not isinstance(counters, dict):
        issues.append("`attempt_comparison.counters` must be an object")
    else:
        for key, record in counters.items():
            if key not in {"started", "finished", "open", "retry_units", "extra_attempts"}:
                issues.append(f"`attempt_comparison.counters.{key}` is not a supported counter")
                continue
            _validate_numeric_delta(
                record,
                field_path=f"attempt_comparison.counters.{key}",
                issues=issues,
                integer_only=True,
            )

    metrics = value.get("process_metrics")
    if not isinstance(metrics, dict):
        issues.append("`attempt_comparison.process_metrics` must be an object")
    else:
        integer_metrics = {"measured_attempts", "stdout_chars", "stderr_chars"}
        number_metrics = {"total_elapsed_ms", "mean_elapsed_ms", "max_elapsed_ms"}
        for key, record in metrics.items():
            if key not in integer_metrics | number_metrics:
                issues.append(f"`attempt_comparison.process_metrics.{key}` is not a supported metric")
                continue
            _validate_numeric_delta(
                record,
                field_path=f"attempt_comparison.process_metrics.{key}",
                issues=issues,
                integer_only=key in integer_metrics,
            )


def _validate_ledger_compatibility(value: Any, *, issues: list[str]) -> None:
    if not isinstance(value, dict):
        issues.append("`ledger_integrity.compatibility` must be an object")
        return
    for key in (
        "mode",
        "recorded_completion_protocol",
        "current_completion_protocol",
        "interpretation",
    ):
        if not isinstance(value.get(key), str):
            issues.append(f"`ledger_integrity.compatibility.{key}` must be a string")
    codes = value.get("legacy_evidence_gap_codes")
    if not isinstance(codes, list):
        issues.append("`ledger_integrity.compatibility.legacy_evidence_gap_codes` must be a list")
    else:
        for idx, code in enumerate(codes):
            if not isinstance(code, str):
                issues.append(
                    f"`ledger_integrity.compatibility.legacy_evidence_gap_codes[{idx}]` must be a string"
                )


def _validate_numeric_delta(
    value: Any,
    *,
    field_path: str,
    issues: list[str],
    integer_only: bool,
) -> None:
    if not isinstance(value, dict):
        issues.append(f"`{field_path}` must be an object")
        return
    for key in ("before", "after", "delta"):
        item = value.get(key)
        if item is None:
            continue
        valid = isinstance(item, int) and not isinstance(item, bool)
        if not integer_only:
            valid = isinstance(item, (int, float)) and not isinstance(item, bool)
        if not valid:
            expected = "an integer or null" if integer_only else "a number or null"
            issues.append(f"`{field_path}.{key}` must be {expected}")


def build_run_audit_payload(*, workspace: Path, repo_root: Path) -> tuple[int, dict[str, Any]]:
    snapshot = _collect_workspace_inspection_snapshot(workspace=workspace, repo_root=repo_root)
    return _build_run_audit_payload_from_snapshot(snapshot)


def _build_run_audit_payload_from_snapshot(
    snapshot: _WorkspaceInspectionSnapshot,
) -> tuple[int, dict[str, Any]]:
    issues = list(snapshot.audit_issues)
    manifests = list(snapshot.manifests)
    target_records = list(snapshot.target_artifacts)
    exit_code = 2 if any(issue.level == "ERROR" for issue in issues) else 0
    verdict = "PASS" if exit_code == 0 else "ATTENTION"
    manifest_status_counts = Counter(str(item.get("status") or "<blank>") for item in manifests)
    remediation_counts = Counter(issue.remediation_category for issue in issues)
    payload = {
        "schema": RUN_AUDIT_SCHEMA,
        "generated_at": snapshot.generated_at,
        "workspace": str(snapshot.workspace),
        "repo": str(snapshot.repo_root),
        "pipeline_lock": snapshot.pipeline_lock,
        "pipeline": snapshot.pipeline_name,
        "run_identity": snapshot.run_identity,
        "current_checkpoint": snapshot.current_checkpoint,
        "run_ledger_files": snapshot.run_ledger_files,
        "run_state": _run_state_record(
            unit_status=snapshot.unit_status,
            target_artifacts=target_records,
            manifests=manifests,
            issues=issues,
        ),
        "unit_status": snapshot.unit_status,
        "target_artifacts": target_records,
        "unit_output_manifests": {
            "count": len(manifests),
            "by_status": {status: manifest_status_counts[status] for status in sorted(manifest_status_counts)},
            "latest": _manifest_summary(manifests[-1]) if manifests else {},
            "records": [_manifest_summary(record) for record in manifests],
        },
        "attempts": dict(snapshot.ledger_integrity.get("attempt_summary") or {}),
        "ledger_integrity": snapshot.ledger_integrity,
        "harness_issues": [_issue_record(issue) for issue in issues],
        "remediation_summary": {category: remediation_counts[category] for category in sorted(remediation_counts)},
        "recent_reports": list(snapshot.recent_reports),
        "verdict": verdict,
        "exit_code": exit_code,
    }
    return exit_code, payload


def build_run_audit_report(*, workspace: Path, repo_root: Path) -> tuple[int, str]:
    exit_code, payload = build_run_audit_payload(workspace=workspace, repo_root=repo_root)
    return exit_code, render_run_audit_report(payload)


def render_run_audit_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Run audit",
        "",
        f"- Workspace: `{payload.get('workspace')}`",
        f"- Repo: `{payload.get('repo')}`",
        f"- Generated at: `{payload.get('generated_at')}`",
        f"- Pipeline lock: `{payload.get('pipeline_lock')}`" if payload.get("pipeline_lock") else "- Pipeline lock: missing",
        f"- Pipeline: `{payload.get('pipeline')}`" if payload.get("pipeline") else "- Pipeline: unknown",
        f"- Current checkpoint: `{payload.get('current_checkpoint')}`",
        f"- JSON sidecar: `output/RUN_AUDIT.json`",
    ]

    identity = payload.get("run_identity") or {}
    if identity.get("run_id"):
        lines.extend(
            [
                f"- Run ID: `{identity.get('run_id')}`",
                f"- Goal ID: `{identity.get('goal_id')}`",
                f"- Durable state: `{identity.get('state') or 'unknown'}`",
                f"- Harness revision: `{identity.get('harness_revision') or 'unavailable'}`",
                f"- Completion protocol: `{identity.get('completion_protocol') or 'unversioned'}`",
            ]
        )

    lines.extend(["", "## Run ledger files"])
    for relpath, exists in (payload.get("run_ledger_files") or {}).items():
        status = "present" if exists else "missing"
        lines.append(f"- `{relpath}`: {status}")

    run_state = payload.get("run_state") or {}
    lines.extend(["", "## Run state"])
    if run_state:
        lines.append(f"- Phase: `{run_state.get('phase')}`")
        lines.append(f"- Units total: {run_state.get('units_total')}")
        lines.append(f"- Active units: {run_state.get('active_units')}")
        lines.append(
            "- Target artifacts: "
            f"{run_state.get('target_artifacts_present')} present / "
            f"{run_state.get('target_artifacts_missing')} missing"
        )
        lines.append(f"- Unit output manifests: {run_state.get('unit_output_manifest_count')}")
        lines.append(
            "- Harness issues: "
            f"{run_state.get('error_count')} errors, {run_state.get('warn_count')} warnings"
        )
    else:
        lines.append("- Run state unavailable")

    attempts = payload.get("attempts") or {}
    lines.extend(["", "## Attempt execution"])
    if not attempts or not attempts.get("started"):
        lines.append("- No Attempts recorded")
    else:
        lines.append(f"- Started: {attempts.get('started', 0)}")
        lines.append(f"- Finished: {attempts.get('finished', 0)}")
        lines.append(f"- Open: {attempts.get('open', 0)}")
        lines.append(
            f"- Retries: {attempts.get('extra_attempts', 0)} extra Attempts "
            f"across {attempts.get('retry_units', 0)} Units"
        )
        status_text = ", ".join(
            f"{status}={count}" for status, count in (attempts.get("by_status") or {}).items()
        )
        mode_text = ", ".join(
            f"{mode}={count}" for mode, count in (attempts.get("by_execution_mode") or {}).items()
        )
        lines.append(f"- Terminal status: {status_text or 'none'}")
        lines.append(f"- Execution mode: {mode_text or 'unknown'}")
        metrics = attempts.get("process_metrics") or {}
        measured = int(metrics.get("measured_attempts") or 0)
        if measured:
            lines.append(
                "- Measured adapter runtime: "
                f"{measured} Attempts, {metrics.get('total_elapsed_ms')} ms total, "
                f"{metrics.get('mean_elapsed_ms')} ms mean, {metrics.get('max_elapsed_ms')} ms max"
            )
            lines.append(
                "- Captured process output: "
                f"{metrics.get('stdout_chars', 0)} stdout chars, "
                f"{metrics.get('stderr_chars', 0)} stderr chars"
            )
        else:
            lines.append("- Measured adapter runtime: unavailable for legacy or manual Attempts")

    lines.extend(["", "## Unit status"])
    unit_status = payload.get("unit_status") or {}
    if unit_status:
        for status, count in unit_status.items():
            lines.append(f"- {status}: {count}")
    else:
        if not (payload.get("run_ledger_files") or {}).get("UNITS.csv"):
            lines.append("- UNITS.csv missing")
        else:
            lines.append("- No units found")

    target_artifacts = payload.get("target_artifacts") or []
    lines.extend(["", "## Target artifacts"])
    if not target_artifacts:
        lines.append("- No target artifacts declared or pipeline spec could not be resolved")
    else:
        for item in target_artifacts:
            relpath = str(item.get("path") or "")
            status = "present" if item.get("exists") else "missing"
            lines.append(f"- `{relpath}`: {status}")

    manifest_summary = payload.get("unit_output_manifests") or {}
    lines.extend(["", "## Unit output manifests"])
    if not manifest_summary.get("count"):
        lines.append("- No unit output manifests found")
    else:
        lines.append(f"- Manifests: {manifest_summary.get('count')}")
        for status, count in (manifest_summary.get("by_status") or {}).items():
            lines.append(f"- {status}: {count}")
        latest = manifest_summary.get("latest") or {}
        if latest:
            latest_path = str(latest.get("path") or "")
            latest_unit = str(latest.get("unit_id") or "?")
            latest_skill = str(latest.get("skill") or "?")
            latest_status = str(latest.get("status") or "?")
            lines.append(f"- Latest: `{latest_path}` (`{latest_unit}` `{latest_skill}` {latest_status})")

    integrity = payload.get("ledger_integrity") or {}
    lines.extend(["", "## Ledger integrity"])
    if not integrity.get("enabled"):
        lines.append("- Legacy Workspace: machine-readable Run ledgers are not initialized")
    else:
        lines.append(f"- Run ID: `{integrity.get('run_id') or 'unknown'}`")
        lines.append(f"- Integrity issues: {integrity.get('issue_count', 0)}")
        for name, count in (integrity.get("ledger_record_counts") or {}).items():
            lines.append(f"- {name}: {count}")
        compatibility = integrity.get("compatibility") or {}
        if compatibility:
            lines.append(f"- Evidence mode: `{compatibility.get('mode') or 'unknown'}`")
            lines.append(
                "- Recorded completion protocol: "
                f"`{compatibility.get('recorded_completion_protocol') or 'unversioned'}`"
            )
            legacy_codes = compatibility.get("legacy_evidence_gap_codes") or []
            if legacy_codes:
                formatted_codes = ", ".join(f"`{code}`" for code in legacy_codes)
                lines.append(f"- Compatibility-sensitive evidence gaps: {formatted_codes}")
            lines.append(f"- Interpretation: {compatibility.get('interpretation')}")

    lines.extend(["", "## Harness issues"])
    issues = payload.get("harness_issues") or []
    if issues:
        for issue in issues:
            lines.append(_format_issue_record(issue))
        lines.extend(["", "## Remediation summary"])
        for category, count in (payload.get("remediation_summary") or {}).items():
            lines.append(f"- `{category}`: {count}")
    else:
        lines.append("- No harness issues")

    lines.extend(["", "## Recent harness reports"])
    recent_reports = payload.get("recent_reports") or []
    if not recent_reports:
        lines.append("- No recent harness reports found")
    else:
        for report in recent_reports:
            preview = str(report.get("preview") or "")
            suffix = f": {preview}" if preview else ""
            lines.append(f"- `{report.get('path')}`{suffix}")

    lines.extend(["", "## Audit verdict", f"- {payload.get('verdict') or 'ATTENTION'}"])
    return "\n".join(lines).rstrip() + "\n"


def write_run_audit_report(*, workspace: Path, report: str) -> Path:
    path = workspace / "output" / "RUN_AUDIT.md"
    atomic_write_text(path, report)
    return path


def write_run_audit_json(*, workspace: Path, payload: dict[str, Any]) -> Path:
    path = workspace / "output" / "RUN_AUDIT.json"
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return path


def load_run_audit_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Missing run audit payload: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in run audit payload `{path}`: {exc}") from exc

    issues = validate_run_audit_payload(payload)
    if issues:
        joined = "; ".join(issues)
        raise ValueError(f"`{path}` is not a valid {RUN_AUDIT_SCHEMA} payload: {joined}")
    return payload


def build_run_audit_diff_payload(
    *,
    before_path: Path,
    before_payload: dict[str, Any],
    after_path: Path,
    after_payload: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    unit_status_delta = _int_mapping_delta(
        before_payload.get("unit_status") or {},
        after_payload.get("unit_status") or {},
    )
    target_changes = _target_artifact_changes(before_payload, after_payload)
    before_manifest_count = _manifest_count(before_payload)
    after_manifest_count = _manifest_count(after_payload)
    before_issue_count = len(before_payload.get("harness_issues") or [])
    after_issue_count = len(after_payload.get("harness_issues") or [])
    attempt_comparison = _attempt_comparison(before_payload, after_payload)

    comparison_issues: list[str] = []
    if before_payload.get("pipeline") != after_payload.get("pipeline"):
        comparison_issues.append(
            f"Pipeline changed from `{before_payload.get('pipeline')}` to `{after_payload.get('pipeline')}`"
        )

    regressed_artifacts = [
        item["path"]
        for item in target_changes
        if item.get("change") in {"became_missing", "added_missing"}
    ]
    for relpath in regressed_artifacts:
        comparison_issues.append(f"Target artifact `{relpath}` is missing in the after audit")

    after_verdict = str(after_payload.get("verdict") or "")
    exit_code = 0 if after_verdict == "PASS" and not comparison_issues else 2
    verdict = "PASS" if exit_code == 0 else "ATTENTION"
    payload = {
        "schema": RUN_AUDIT_DIFF_SCHEMA,
        "generated_at": now_iso_seconds(),
        "before_path": str(before_path),
        "after_path": str(after_path),
        "before_schema": str(before_payload.get("schema") or ""),
        "after_schema": str(after_payload.get("schema") or ""),
        "before_workspace": str(before_payload.get("workspace") or ""),
        "after_workspace": str(after_payload.get("workspace") or ""),
        "before_pipeline": str(before_payload.get("pipeline") or ""),
        "after_pipeline": str(after_payload.get("pipeline") or ""),
        "before_verdict": str(before_payload.get("verdict") or ""),
        "after_verdict": after_verdict,
        "unit_status_delta": unit_status_delta,
        "target_artifact_changes": target_changes,
        "manifest_counts": {
            "before": before_manifest_count,
            "after": after_manifest_count,
            "delta": after_manifest_count - before_manifest_count,
        },
        "harness_issue_counts": {
            "before": before_issue_count,
            "after": after_issue_count,
            "delta": after_issue_count - before_issue_count,
        },
        "attempt_comparison": attempt_comparison,
        "comparison_issues": comparison_issues,
        "verdict": verdict,
        "exit_code": exit_code,
    }
    return exit_code, payload


def render_run_audit_diff_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Run audit diff",
        "",
        f"- Before: `{payload.get('before_path')}`",
        f"- After: `{payload.get('after_path')}`",
        f"- Pipeline: `{payload.get('before_pipeline')}` -> `{payload.get('after_pipeline')}`",
        f"- Workspace: `{payload.get('before_workspace')}` -> `{payload.get('after_workspace')}`",
        f"- Verdict: `{payload.get('before_verdict')}` -> `{payload.get('after_verdict')}`",
    ]

    lines.extend(["", "## Unit status delta"])
    unit_status_delta = payload.get("unit_status_delta") or {}
    if unit_status_delta:
        for status, delta in unit_status_delta.items():
            sign = "+" if int(delta) > 0 else ""
            lines.append(f"- {status}: {sign}{delta}")
    else:
        lines.append("- No unit status changes")

    lines.extend(["", "## Target artifact changes"])
    changes = payload.get("target_artifact_changes") or []
    if not changes:
        lines.append("- No target artifact changes")
    else:
        for item in changes:
            lines.append(
                f"- `{item.get('path')}`: {item.get('change')} "
                f"({item.get('before_exists')} -> {item.get('after_exists')})"
            )

    manifest_counts = payload.get("manifest_counts") or {}
    issue_counts = payload.get("harness_issue_counts") or {}
    lines.extend(
        [
            "",
            "## Run-level counters",
            _format_count_delta("Unit output manifests", manifest_counts),
            _format_count_delta("Harness issues", issue_counts),
        ]
    )

    lines.extend(["", "## Attempt changes"])
    attempt_comparison = payload.get("attempt_comparison")
    if not isinstance(attempt_comparison, dict) or not attempt_comparison.get("available"):
        note = (
            attempt_comparison.get("note")
            if isinstance(attempt_comparison, dict)
            else "One or both audits predate Attempt summaries."
        )
        lines.append(f"- Unavailable: {note}")
    else:
        counters = attempt_comparison.get("counters") or {}
        metrics = attempt_comparison.get("process_metrics") or {}
        for key, label in (
            ("started", "Started Attempts"),
            ("finished", "Finished Attempts"),
            ("open", "Open Attempts"),
            ("retry_units", "Units with retries"),
            ("extra_attempts", "Extra Attempts"),
        ):
            if key in counters:
                lines.append(_format_numeric_delta(label, counters[key]))
        for key, label in (
            ("measured_attempts", "Measured scripted Attempts"),
            ("total_elapsed_ms", "Total adapter elapsed ms"),
            ("mean_elapsed_ms", "Mean adapter elapsed ms"),
            ("max_elapsed_ms", "Max adapter elapsed ms"),
            ("stdout_chars", "Captured stdout characters"),
            ("stderr_chars", "Captured stderr characters"),
        ):
            if key in metrics:
                lines.append(_format_numeric_delta(label, metrics[key]))
        lines.append(f"- Interpretation: {attempt_comparison.get('note')}")

    lines.extend(["", "## Comparison issues"])
    comparison_issues = payload.get("comparison_issues") or []
    if comparison_issues:
        for issue in comparison_issues:
            lines.append(f"- {issue}")
    else:
        lines.append("- No comparison issues")

    lines.extend(["", "## Diff verdict", f"- {payload.get('verdict') or 'ATTENTION'}"])
    return "\n".join(lines).rstrip() + "\n"


def write_run_audit_diff_report(*, output_dir: Path, report: str) -> Path:
    path = output_dir / "RUN_AUDIT_DIFF.md"
    atomic_write_text(path, report)
    return path


def write_run_audit_diff_json(*, output_dir: Path, payload: dict[str, Any]) -> Path:
    path = output_dir / "RUN_AUDIT_DIFF.json"
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return path


def build_improvement_payload(*, workspace: Path, repo_root: Path) -> tuple[int, dict[str, Any]]:
    snapshot = _collect_workspace_inspection_snapshot(workspace=workspace, repo_root=repo_root)
    doctor_exit, doctor_payload = _build_doctor_payload_from_snapshot(snapshot)
    audit_exit, audit_payload = _build_run_audit_payload_from_snapshot(snapshot)
    return _build_improvement_payload_from_sources(
        workspace=workspace,
        repo_root=repo_root,
        doctor_result=(doctor_exit, doctor_payload),
        audit_result=(audit_exit, audit_payload),
        failure_ledger_entries=snapshot.failure_ledger_entries,
    )


def _build_improvement_payload_from_sources(
    *,
    workspace: Path,
    repo_root: Path,
    doctor_result: tuple[int, dict[str, Any]],
    audit_result: tuple[int, dict[str, Any]],
    failure_ledger_entries: tuple[dict[str, Any], ...] | None = None,
) -> tuple[int, dict[str, Any]]:
    doctor_exit, doctor_payload = doctor_result
    audit_exit, audit_payload = audit_result
    entries = list(failure_ledger_entries) if failure_ledger_entries is not None else _failure_ledger_entries(workspace)
    failures = _failure_ledger_records(workspace, entries=entries)
    repair_history = _failure_repair_history(workspace, entries=entries)
    suggestions = _improvement_suggestion_records(
        workspace=workspace,
        doctor_payload=doctor_payload,
        run_audit_payload=audit_payload,
    )
    suggestions.extend(_failure_suggestion_records(workspace=workspace, failures=failures, offset=len(suggestions)))
    from tooling.run_state import latest_evaluation

    evaluation = latest_evaluation(workspace, verdict="PASS")
    quality_opportunities = _evaluation_opportunity_records(evaluation)
    exit_code = 2 if suggestions or doctor_exit or audit_exit else 0
    source_reports = {
        "doctor": {
            "schema": str(doctor_payload.get("schema") or ""),
            "verdict": str(doctor_payload.get("verdict") or ""),
            "exit_code": int(doctor_payload.get("exit_code") or 0),
        },
        "run_audit": {
            "schema": str(audit_payload.get("schema") or ""),
            "verdict": str(audit_payload.get("verdict") or ""),
            "exit_code": int(audit_payload.get("exit_code") or 0),
        },
        "failure_ledger": {
            "schema": "failure-record.v1",
            "verdict": "ATTENTION" if failures else "PASS",
            "exit_code": 2 if failures else 0,
            "record_count": len(failures),
            "opened_count": int(repair_history["opened_count"]),
            "resolved_count": int(repair_history["resolved_count"]),
        },
    }
    if evaluation:
        source_reports["latest_passing_evaluation"] = {
            "schema": str(evaluation.get("schema") or "run-evaluation.v1"),
            "verdict": str(evaluation.get("verdict") or "UNKNOWN"),
            "exit_code": 0 if str(evaluation.get("verdict") or "").upper() == "PASS" else 2,
            "score": evaluation.get("score"),
            "workflow": str(evaluation.get("workflow") or ""),
        }
    payload = {
        "schema": IMPROVEMENT_REPORT_SCHEMA,
        "generated_at": str(doctor_payload.get("generated_at") or now_iso_seconds()),
        "workspace": str(workspace),
        "repo": str(repo_root),
        "pipeline": str(audit_payload.get("pipeline") or ""),
        "artifact_interface_standard": "docs/PROJECT_LANGUAGE.md",
        "source_reports": source_reports,
        "repair_history": repair_history,
        "suggestions": suggestions,
        "quality_opportunities": quality_opportunities,
        "verdict": "ATTENTION" if suggestions else "PASS",
        "exit_code": exit_code,
    }
    return exit_code, payload


def _evaluation_opportunity_records(evaluation: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose non-blocking scorecard headroom without turning PASS into failure."""

    if str(evaluation.get("verdict") or "").upper() != "PASS":
        return []
    opportunities: list[dict[str, Any]] = []
    dimensions = evaluation.get("dimensions")
    if not isinstance(dimensions, list):
        return opportunities
    for item in dimensions:
        if not isinstance(item, dict):
            continue
        score = item.get("score")
        max_score = item.get("max_score")
        if not isinstance(score, int) or not isinstance(max_score, int) or score >= max_score:
            continue
        surfaces = [
            str(value or "").strip()
            for value in item.get("repair_surface") or []
            if str(value or "").strip()
        ]
        opportunities.append(
            {
                "dimension_id": str(item.get("id") or "unknown"),
                "label": str(item.get("label") or item.get("id") or "Quality dimension"),
                "score": score,
                "max_score": max_score,
                "evidence": str(item.get("evidence") or "No dimension evidence recorded."),
                "repair_surface": surfaces,
            }
        )
    return opportunities


def render_improvement_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Improvement report",
        "",
        f"- Workspace: `{payload.get('workspace')}`",
        f"- Repo: `{payload.get('repo')}`",
        f"- Generated at: `{payload.get('generated_at')}`",
        f"- Pipeline: `{payload.get('pipeline')}`" if payload.get("pipeline") else "- Pipeline: unknown",
        f"- Artifact interface standard: `{payload.get('artifact_interface_standard')}`",
        f"- JSON sidecar: `output/IMPROVEMENT_REPORT.json`",
    ]

    lines.extend(["", "## Source reports"])
    source_reports = payload.get("source_reports") or {}
    if not source_reports:
        lines.append("- No source reports")
    else:
        for name, record in source_reports.items():
            lines.append(
                f"- `{name}`: {record.get('schema')} {record.get('verdict')} "
                f"(exit {record.get('exit_code')})"
            )

    lines.extend(["", "## Repair suggestions"])
    suggestions = payload.get("suggestions") or []
    if not suggestions:
        lines.append("- No repair suggestions; doctor and run audit did not surface harness issues.")
    else:
        for suggestion in suggestions:
            lines.extend(
                [
                    f"### {suggestion.get('id')} - {suggestion.get('upstream_interface')}",
                    "",
                    f"- Source report: `{suggestion.get('source_report')}`",
                    f"- Observed problem: {suggestion.get('observed_problem')}",
                    f"- Evidence: {suggestion.get('evidence')}",
                    f"- Repair surface: `{suggestion.get('repair_surface')}`",
                    f"- Recommended action: {suggestion.get('recommended_action')}",
                    f"- Validation: `{suggestion.get('validation')}`",
                    "",
                ]
            )

    lines.extend(["", "## Non-blocking quality opportunities"])
    opportunities = payload.get("quality_opportunities") or []
    if not opportunities:
        lines.append("- No passing scorecard dimension reported remaining measurable headroom.")
    else:
        for opportunity in opportunities:
            surfaces = ", ".join(f"`{value}`" for value in opportunity.get("repair_surface") or [])
            lines.append(
                f"- **{opportunity.get('label')}**: "
                f"{opportunity.get('score')}/{opportunity.get('max_score')}. "
                f"{opportunity.get('evidence')}"
                + (f" Repair surface: {surfaces}." if surfaces else "")
            )

    history = payload.get("repair_history") or {}
    lines.extend(["", "## Repair history"])
    lines.append(
        f"- Opened failures: {history.get('opened_count', 0)}; "
        f"resolved failures: {history.get('resolved_count', 0)}"
    )
    entries = history.get("entries") if isinstance(history.get("entries"), list) else []
    if entries:
        for entry in entries:
            lines.append(
                f"- `{entry.get('failure_type') or 'failure'}` on `{entry.get('unit_id') or 'unknown'}`: "
                f"attempt `{entry.get('opened_attempt_id') or 'unknown'}` -> "
                f"`{entry.get('resolved_by_attempt_id') or 'unresolved'}` ({entry.get('status')})"
            )
    else:
        lines.append("- No durable failure history recorded.")

    lines.extend(["", "## Improvement verdict", f"- {payload.get('verdict') or 'ATTENTION'}"])
    return "\n".join(lines).rstrip() + "\n"


def write_improvement_report(*, workspace: Path, report: str) -> Path:
    path = workspace / "output" / "IMPROVEMENT_REPORT.md"
    atomic_write_text(path, report)
    return path


def write_improvement_json(*, workspace: Path, payload: dict[str, Any]) -> Path:
    path = workspace / "output" / "IMPROVEMENT_REPORT.json"
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return path


def build_harness_inspection(*, workspace: Path, repo_root: Path) -> HarnessInspection:
    snapshot = _collect_workspace_inspection_snapshot(workspace=workspace, repo_root=repo_root)
    doctor_exit, doctor_payload = _build_doctor_payload_from_snapshot(snapshot)
    audit_exit, audit_payload = _build_run_audit_payload_from_snapshot(snapshot)
    improvement_exit, improvement_payload = _build_improvement_payload_from_sources(
        workspace=workspace,
        repo_root=repo_root,
        doctor_result=(doctor_exit, doctor_payload),
        audit_result=(audit_exit, audit_payload),
        failure_ledger_entries=snapshot.failure_ledger_entries,
    )
    artifact_pack_exit, artifact_pack_payload = _build_artifact_pack_payload_from_sources(
        workspace=workspace,
        repo_root=repo_root,
        doctor_result=(doctor_exit, doctor_payload),
        audit_result=(audit_exit, audit_payload),
        improvement_result=(improvement_exit, improvement_payload),
        snapshot=snapshot,
    )
    return HarnessInspection(
        doctor_exit_code=doctor_exit,
        doctor=doctor_payload,
        audit_exit_code=audit_exit,
        audit=audit_payload,
        improvement_exit_code=improvement_exit,
        improvement=improvement_payload,
        artifact_pack_exit_code=artifact_pack_exit,
        artifact_pack=artifact_pack_payload,
    )


def build_artifact_pack_payload(*, workspace: Path, repo_root: Path) -> tuple[int, dict[str, Any]]:
    inspection = build_harness_inspection(workspace=workspace, repo_root=repo_root)
    return inspection.artifact_pack_exit_code, inspection.artifact_pack


def _build_artifact_pack_payload_from_sources(
    *,
    workspace: Path,
    repo_root: Path,
    doctor_result: tuple[int, dict[str, Any]],
    audit_result: tuple[int, dict[str, Any]],
    improvement_result: tuple[int, dict[str, Any]],
    snapshot: _WorkspaceInspectionSnapshot | None = None,
) -> tuple[int, dict[str, Any]]:
    doctor_exit, doctor_payload = doctor_result
    audit_exit, audit_payload = audit_result
    improvement_exit, improvement_payload = improvement_result

    artifacts = _artifact_pack_records(
        workspace=workspace,
        audit_payload=audit_payload,
        declared_unit_output_paths=(snapshot.declared_unit_output_paths if snapshot is not None else None),
        manifests=(snapshot.manifests if snapshot is not None else None),
    )
    summary = _artifact_pack_summary(artifacts)
    exit_code = 2 if doctor_exit or audit_exit or improvement_exit else 0
    payload = {
        "schema": ARTIFACT_PACK_SCHEMA,
        "generated_at": str(doctor_payload.get("generated_at") or now_iso_seconds()),
        "workspace": str(workspace),
        "repo": str(repo_root),
        "pipeline": str(audit_payload.get("pipeline") or ""),
        "artifact_interface_standard": "docs/PROJECT_LANGUAGE.md",
        "source_reports": {
            "doctor": _source_report_record(doctor_payload),
            "run_audit": _source_report_record(audit_payload),
            "improvement_report": _source_report_record(improvement_payload),
        },
        "artifacts": artifacts,
        "summary": summary,
        "verdict": "PASS" if exit_code == 0 else "ATTENTION",
        "exit_code": exit_code,
    }
    return exit_code, payload


def render_artifact_pack_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Artifact pack",
        "",
        f"- Workspace: `{payload.get('workspace')}`",
        f"- Repo: `{payload.get('repo')}`",
        f"- Generated at: `{payload.get('generated_at')}`",
        f"- Pipeline: `{payload.get('pipeline')}`" if payload.get("pipeline") else "- Pipeline: unknown",
        f"- Artifact interface standard: `{payload.get('artifact_interface_standard')}`",
        f"- JSON sidecar: `output/ARTIFACT_PACK.json`",
    ]

    lines.extend(["", "## Source reports"])
    for name, record in (payload.get("source_reports") or {}).items():
        lines.append(
            f"- `{name}`: {record.get('schema')} {record.get('verdict')} "
            f"(exit {record.get('exit_code')})"
        )
        run_state = record.get("run_state")
        if isinstance(run_state, dict):
            lines.append(
                "  - Run state: "
                f"`{run_state.get('phase')}`; "
                f"{run_state.get('target_artifacts_present')} target artifacts present, "
                f"{run_state.get('target_artifacts_missing')} missing; "
                f"{run_state.get('error_count')} errors"
            )

    summary = payload.get("summary") or {}
    lines.extend(
        [
            "",
            "## Pack summary",
            f"- Total artifacts indexed: {summary.get('total', 0)}",
            f"- Present: {summary.get('present', 0)}",
            f"- Missing: {summary.get('missing', 0)}",
        ]
    )

    by_category = summary.get("by_category") or {}
    if by_category:
        lines.append("- By category:")
        for category, counts in by_category.items():
            lines.append(
                f"  - `{category}`: {counts.get('present', 0)}/{counts.get('total', 0)} present"
            )

    lines.extend(["", "## Artifacts"])
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in payload.get("artifacts") or []:
        category = str(record.get("category") or "uncategorized")
        grouped.setdefault(category, []).append(record)
    if not grouped:
        lines.append("- No artifacts indexed")
    else:
        for category in sorted(grouped):
            lines.extend(["", f"### {category}"])
            for record in grouped[category]:
                status = "present" if record.get("exists") else "missing"
                details = _artifact_pack_record_details(record)
                suffix = f" ({details})" if details else ""
                lines.append(f"- `{record.get('path')}`: {status}{suffix}")

    lines.extend(["", "## Pack verdict", f"- {payload.get('verdict') or 'ATTENTION'}"])
    return "\n".join(lines).rstrip() + "\n"


def render_artifact_pack_excerpt_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Artifact Pack Excerpt",
        "",
        "This portable excerpt is derived from an `artifact-pack.v1` handoff manifest. "
        "It keeps workspace-relative paths so the table can be copied into tracked "
        "fixtures or handoff notes without embedding local absolute paths.",
        "",
        "It is not a full `output/ARTIFACT_PACK.json` sidecar. The full JSON manifest "
        "remains the compatibility contract; this excerpt preserves the reader-facing "
        "shape: start from target artifacts, then trace backward through unit outputs, "
        "run ledgers, harness reports, and unit manifests.",
        "",
        "| Category | Path | Exists | Role |",
        "|---|---|---|---|",
    ]
    for record in _artifact_pack_excerpt_records(payload):
        lines.append(
            "| `{category}` | `{path}` | {exists} | {role} |".format(
                category=record["category"],
                path=record["path"],
                exists="true" if record["exists"] else "false",
                role=record["role"],
            )
        )
    lines.extend(["", f"Handoff verdict for this excerpt: `{payload.get('verdict') or 'ATTENTION'}`."])
    return "\n".join(lines).rstrip() + "\n"


def render_artifact_pack_excerpt_tsv(payload: dict[str, Any]) -> str:
    lines = ["category\tpath\texists\trole"]
    for record in _artifact_pack_excerpt_records(payload):
        lines.append(
            "{category}\t{path}\t{exists}\t{role}".format(
                category=record["category"],
                path=record["path"],
                exists="true" if record["exists"] else "false",
                role=record["role"],
            )
        )
    return "\n".join(lines) + "\n"


def write_artifact_pack_report(*, workspace: Path, report: str) -> Path:
    path = workspace / "output" / "ARTIFACT_PACK.md"
    atomic_write_text(path, report)
    return path


def write_artifact_pack_json(*, workspace: Path, payload: dict[str, Any]) -> Path:
    path = workspace / "output" / "ARTIFACT_PACK.json"
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return path


def write_artifact_pack_excerpt_markdown(*, workspace: Path, excerpt: str) -> Path:
    path = workspace / "output" / "ARTIFACT_PACK_EXCERPT.md"
    atomic_write_text(path, excerpt)
    return path


def write_artifact_pack_excerpt_tsv(*, workspace: Path, excerpt: str) -> Path:
    path = workspace / "output" / "ARTIFACT_PACK_EXCERPT.tsv"
    atomic_write_text(path, excerpt)
    return path


def _improvement_suggestion_records(
    *,
    workspace: Path,
    doctor_payload: dict[str, Any],
    run_audit_payload: dict[str, Any],
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for source_report, payload in (("doctor", doctor_payload), ("run_audit", run_audit_payload)):
        for issue in payload.get("harness_issues") or []:
            if not isinstance(issue, dict):
                continue
            code = str(issue.get("code") or "")
            message = str(issue.get("message") or "")
            key = (source_report, code, message)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "id": f"S{len(records) + 1:03d}",
                    "source_report": source_report,
                    "observed_problem": message,
                    "evidence": f"{str(issue.get('level') or 'INFO')} `{code}`",
                    "upstream_interface": _issue_upstream_interface(code),
                    "repair_surface": str(issue.get("remediation_category") or "inspect_workspace_state"),
                    "recommended_action": str(issue.get("next_action") or "Inspect the workspace state and rerun harness checks."),
                    "validation": _issue_validation_command(code, workspace),
                }
            )
    return records


def _failure_suggestion_records(
    *, workspace: Path, failures: list[dict[str, Any]], offset: int
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    latest_by_fingerprint: dict[str, dict[str, Any]] = {}
    for failure in failures:
        fingerprint = str(failure.get("fingerprint") or failure.get("failure_id") or "")
        if fingerprint:
            latest_by_fingerprint[fingerprint] = failure

    for failure in latest_by_fingerprint.values():
        repair_surface = failure.get("repair_surface") or []
        if isinstance(repair_surface, list):
            repair_text = "; ".join(str(item) for item in repair_surface if str(item).strip())
        else:
            repair_text = str(repair_surface)
        failure_type = str(failure.get("failure_type") or "unclassified_failure")
        records.append(
            {
                "id": f"S{offset + len(records) + 1:03d}",
                "source_report": "failure_ledger",
                "observed_problem": str(failure.get("observable_failure") or failure_type),
                "evidence": (
                    f"{str(failure.get('severity') or 'medium').upper()} `{failure_type}`; "
                    f"attempt `{failure.get('attempt_id') or 'unknown'}`"
                ),
                "upstream_interface": str(failure.get("harness_mechanism") or "Run attempt / skill adapter"),
                "repair_surface": repair_text or "inspect recorded attempt",
                "recommended_action": str(failure.get("causal_behavior") or "Inspect the recorded attempt and repair surface."),
                "validation": pipeline_cli_command("doctor", workspace=workspace, extra_args=("--write",)),
            }
        )
    return records


def _failure_ledger_entries(workspace: Path) -> list[dict[str, Any]]:
    path = workspace / ".harness" / "failures" / "ledger.jsonl"
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                entries.append(payload)
    return entries


def _failure_ledger_records(
    workspace: Path,
    *,
    entries: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for payload in entries if entries is not None else _failure_ledger_entries(workspace):
        failure_id = str(payload.get("failure_id") or "")
        if not failure_id:
            continue
        if payload.get("status") == "open":
            records[failure_id] = payload
        else:
            records.pop(failure_id, None)
    return list(records.values())


def _failure_repair_history(
    workspace: Path,
    *,
    entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    failures: dict[str, dict[str, Any]] = {}
    for payload in entries if entries is not None else _failure_ledger_entries(workspace):
        failure_id = str(payload.get("failure_id") or "")
        if not failure_id:
            continue
        if payload.get("status") == "open":
            failures[failure_id] = {
                "failure_id": failure_id,
                "failure_type": str(payload.get("failure_type") or ""),
                "unit_id": str(payload.get("unit_id") or ""),
                "opened_attempt_id": str(payload.get("attempt_id") or ""),
                "resolved_by_attempt_id": "",
                "status": "open",
            }
        elif failure_id in failures:
            failures[failure_id]["resolved_by_attempt_id"] = str(payload.get("resolved_by_attempt_id") or "")
            failures[failure_id]["status"] = "resolved"
    entries = list(failures.values())
    return {
        "opened_count": len(entries),
        "resolved_count": len([entry for entry in entries if entry["status"] == "resolved"]),
        "entries": entries,
    }


def _issue_upstream_interface(code: str) -> str:
    if code in {"missing_units", "missing_units_field", "missing_unit_id", "duplicate_unit_id", "invalid_owner"}:
        return "Execution ledger / UNITS.csv"
    if code == "invalid_status":
        return "Execution ledger / unit status"
    if code == "human_checkpoint_missing":
        return "Human checkpoint / DECISIONS.md"
    if code in {"missing_dependency", "dependency_cycle"}:
        return "Workflow protocol / dependency graph"
    if code == "missing_done_output":
        return "Artifact contract / unit outputs"
    if code == "missing_target_artifact":
        return "Target artifact contract"
    return "Workspace evidence surface"


def _issue_validation_command(code: str, workspace: Path) -> str:
    if code in {"missing_target_artifact", "missing_done_output"}:
        return pipeline_cli_command("audit", workspace=workspace, extra_args=("--write",))
    if code in {"missing_units", "missing_units_field", "missing_unit_id", "duplicate_unit_id", "invalid_status", "invalid_owner"}:
        return pipeline_cli_command("doctor", workspace=workspace, extra_args=("--write",))
    if code in {"missing_dependency", "dependency_cycle", "human_checkpoint_missing"}:
        return pipeline_cli_command("doctor", workspace=workspace, extra_args=("--write",))
    return pipeline_cli_command("improve", workspace=workspace, extra_args=("--write",))


def _doctor_resume_hint(
    *,
    workspace: Path,
    next_runnable: dict[str, str],
    issues: list[HarnessIssue],
) -> dict[str, str]:
    if any(issue.level == "ERROR" for issue in issues):
        return {
            "kind": "repair_first",
            "command": pipeline_cli_command("improve", workspace=workspace, extra_args=("--write",)),
            "reason": "Doctor found error-level harness issues; repair or classify them before running more units.",
        }

    if next_runnable:
        unit_id = str(next_runnable.get("unit_id") or "the next unit")
        status = str(next_runnable.get("status") or "").strip().upper()
        owner = str(next_runnable.get("owner") or "").strip().upper()
        skill = str(next_runnable.get("skill") or "").strip().lower()
        checkpoint = str(next_runnable.get("checkpoint") or "").strip()
        if (owner == "HUMAN" or skill == "human-checkpoint") and checkpoint:
            return {
                "kind": "await_human_approval",
                "command": pipeline_cli_command(
                    "approve",
                    workspace=workspace,
                    extra_args=("--checkpoint", checkpoint),
                ),
                "reason": (
                    f"Unit {unit_id} is the {checkpoint} human checkpoint; review `DECISIONS.md` "
                    "and approve it explicitly before execution continues."
                ),
            }
        if status == "BLOCKED":
            return {
                "kind": "repair_blocked_unit",
                "command": pipeline_cli_command("improve", workspace=workspace, extra_args=("--write",)),
                "reason": (
                    f"Unit {unit_id} is BLOCKED; inspect `output/QUALITY_GATE.md`, "
                    "`output/RUN_ERRORS.md`, and unit logs before rerunning it."
                ),
            }
        return {
            "kind": "run_next_unit",
            "command": pipeline_cli_command("run", workspace=workspace),
            "reason": f"Next runnable unit {unit_id} is ready.",
        }

    return {
        "kind": "audit_state",
        "command": pipeline_cli_command("audit", workspace=workspace, extra_args=("--write",)),
        "reason": "No runnable unit is currently available; audit the run state before continuing.",
    }


def _run_state_record(
    *,
    unit_status: dict[str, int],
    target_artifacts: list[dict[str, Any]],
    manifests: list[dict[str, Any]],
    issues: list[HarnessIssue],
) -> dict[str, Any]:
    level_counts = Counter(issue.level for issue in issues)
    missing_targets = sum(1 for item in target_artifacts if not item.get("exists"))
    active_units = sum(unit_status.get(status, 0) for status in ("TODO", "DOING", "BLOCKED"))
    error_count = level_counts["ERROR"]
    if error_count:
        phase = "attention"
    elif active_units:
        phase = "in_progress"
    else:
        phase = "complete_candidate"

    return {
        "phase": phase,
        "units_total": sum(unit_status.values()),
        "active_units": active_units,
        "target_artifacts_total": len(target_artifacts),
        "target_artifacts_present": len(target_artifacts) - missing_targets,
        "target_artifacts_missing": missing_targets,
        "unit_output_manifest_count": len(manifests),
        "harness_issue_count": len(issues),
        "error_count": error_count,
        "warn_count": level_counts["WARN"],
    }


def find_next_runnable(table: UnitsTable) -> dict[str, str] | None:
    status_ok = {"DONE", "SKIP"}
    unit_by_id = {_unit_id(row): row for row in table.rows if _unit_id(row)}
    for row in table.rows:
        if _status(row) not in {"TODO", "BLOCKED"}:
            continue
        deps = parse_semicolon_list(row.get("depends_on"))
        if not deps:
            return row
        if all(dep_id in unit_by_id and _status(unit_by_id[dep_id]) in status_ok for dep_id in deps):
            return row
    return None


def write_unit_manifest(
    *,
    workspace: Path,
    unit_id: str,
    skill: str,
    outputs: list[str],
    exit_code: int,
    status: str,
    attempt_id: str = "",
    repo_root: Path | None = None,
) -> Path:
    from tooling.run_state import run_identity

    manifest_name = (
        f"{unit_id}.{skill}.{attempt_id}.manifest.json"
        if attempt_id
        else f"{unit_id}.{skill}.manifest.json"
    )
    manifest_path = workspace / "output" / "unit_logs" / manifest_name
    identity = run_identity(workspace)
    payload = {
        "schema": "unit-output-manifest.v1",
        "generated_at": now_iso_seconds(),
        "run_id": identity.get("run_id") or "",
        "attempt_id": attempt_id,
        "unit_id": unit_id,
        "skill": skill,
        "status": status,
        "exit_code": exit_code,
        "outputs": [_artifact_record(workspace=workspace, relpath=rel) for rel in outputs if str(rel or "").strip()],
    }
    if repo_root is not None:
        skill_dir = repo_root / ".codex" / "skills" / skill
        if skill_dir.exists():
            payload["implementation"] = {
                "skill": _implementation_record(repo_root=repo_root, path=skill_dir),
            }
    ensure_dir(manifest_path.parent)
    atomic_write_text(manifest_path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return manifest_path


def _workspace_implementation_issues(
    *,
    workspace: Path,
    table: UnitsTable,
    repo_root: Path,
    manifests: tuple[dict[str, Any], ...] | None = None,
) -> list[HarnessIssue]:
    latest_by_unit: dict[str, dict[str, Any]] = {}
    for manifest in manifests if manifests is not None else _unit_manifest_records(workspace):
        if str(manifest.get("status") or "").upper() != "DONE":
            continue
        unit_id = str(manifest.get("unit_id") or "").strip()
        if unit_id:
            latest_by_unit[unit_id] = manifest

    stale: list[str] = []
    for row in table.rows:
        if _status(row) != "DONE":
            continue
        unit_id = _unit_id(row)
        skill = str(row.get("skill") or "").strip()
        manifest = latest_by_unit.get(unit_id)
        implementation = manifest.get("implementation") if isinstance(manifest, dict) else None
        pinned = implementation.get("skill") if isinstance(implementation, dict) else None
        pinned_sha = str(pinned.get("sha256") or "") if isinstance(pinned, dict) else ""
        if not pinned_sha:
            continue
        skill_dir = repo_root / ".codex" / "skills" / skill
        current = _implementation_record(repo_root=repo_root, path=skill_dir)
        if not current.get("exists") or str(current.get("sha256") or "") != pinned_sha:
            stale.append(f"{unit_id} ({skill})")

    if not stale:
        return []
    preview = ", ".join(stale[:8]) + (" ..." if len(stale) > 8 else "")
    return [
        HarnessIssue(
            "ERROR",
            "stale_done_implementation",
            f"DONE unit implementation changed after its latest successful attempt: {preview}. Reopen the earliest affected unit so downstream artifacts are regenerated.",
        )
    ]


def _workspace_artifact_issues(*, workspace: Path, table: UnitsTable) -> list[HarnessIssue]:
    issues: list[HarnessIssue] = []
    for row in table.rows:
        if _status(row) != "DONE":
            continue
        unit_id = _unit_id(row) or "<missing>"
        for raw_output in parse_semicolon_list(row.get("outputs")):
            if raw_output.strip().startswith("?"):
                continue
            relpath = _strip_optional_marker(raw_output)
            if relpath and not (workspace / relpath).exists():
                issues.append(
                    HarnessIssue(
                        "ERROR",
                        "missing_done_output",
                        f"`{unit_id}` is DONE but `{relpath}` is missing",
                    )
                )
    return issues


def _cycle_issues(table: UnitsTable) -> list[HarnessIssue]:
    dep_map = {_unit_id(row): parse_semicolon_list(row.get("depends_on")) for row in table.rows if _unit_id(row)}
    issues: list[HarnessIssue] = []
    temporary: set[str] = set()
    permanent: set[str] = set()
    stack: list[str] = []
    seen_cycles: set[tuple[str, ...]] = set()

    def visit(unit_id: str) -> None:
        if unit_id in permanent:
            return
        if unit_id in temporary:
            try:
                start = stack.index(unit_id)
            except ValueError:
                start = 0
            cycle = tuple(stack[start:] + [unit_id])
            if cycle not in seen_cycles:
                seen_cycles.add(cycle)
                issues.append(HarnessIssue("ERROR", "dependency_cycle", "`" + "` -> `".join(cycle) + "`"))
            return
        temporary.add(unit_id)
        stack.append(unit_id)
        for dep_id in dep_map.get(unit_id, []):
            if dep_id in dep_map:
                visit(dep_id)
        stack.pop()
        temporary.remove(unit_id)
        permanent.add(unit_id)

    for unit_id in dep_map:
        visit(unit_id)
    return issues


def _artifact_record(*, workspace: Path, relpath: str) -> dict[str, Any]:
    relpath = _strip_optional_marker(relpath)
    path = workspace / relpath
    record: dict[str, Any] = {"path": relpath, "exists": path.exists()}
    if not path.exists():
        return record
    if path.is_dir():
        files = [item for item in path.rglob("*") if item.is_file()]
        record.update({"type": "directory", "file_count": len(files)})
        return record
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    record.update({"type": "file", "size": path.stat().st_size, "sha256": digest.hexdigest()})
    return record


def _implementation_record(*, repo_root: Path, path: Path) -> dict[str, Any]:
    relpath = str(path.relative_to(repo_root)) if path.is_relative_to(repo_root) else str(path)
    record: dict[str, Any] = {"path": relpath, "exists": path.exists()}
    if not path.exists():
        return record
    if path.is_file():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        record.update({"type": "file", "size": path.stat().st_size, "sha256": digest})
        return record

    files = sorted(
        item
        for item in path.rglob("*")
        if item.is_file()
        and "__pycache__" not in item.parts
        and item.suffix not in {".pyc", ".pyo"}
    )
    digest = hashlib.sha256()
    for item in files:
        digest.update(str(item.relative_to(path)).encode("utf-8"))
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    record.update({"type": "directory", "file_count": len(files), "sha256": digest.hexdigest()})
    return record


def _artifact_pack_records(
    *,
    workspace: Path,
    audit_payload: dict[str, Any],
    declared_unit_output_paths: tuple[str, ...] | None = None,
    manifests: tuple[dict[str, Any], ...] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(category: str, relpath: str) -> None:
        relpath = _strip_optional_marker(str(relpath or "").strip())
        if not relpath:
            return
        key = (category, relpath)
        if key in seen:
            return
        seen.add(key)
        record = _artifact_record(workspace=workspace, relpath=relpath)
        record["category"] = category
        records.append(record)

    for item in audit_payload.get("target_artifacts") or []:
        if isinstance(item, dict):
            add("target_artifact", str(item.get("path") or ""))

    output_paths = (
        list(declared_unit_output_paths)
        if declared_unit_output_paths is not None
        else _declared_unit_output_paths(workspace)
    )
    for relpath in output_paths:
        add("unit_output", relpath)

    for relpath in ARTIFACT_PACK_LEDGER_PATHS:
        add("run_ledger", relpath)

    for relpath in ARTIFACT_PACK_HARNESS_REPORT_PATHS:
        add("harness_report", relpath)

    for manifest in manifests if manifests is not None else _unit_manifest_records(workspace):
        add("unit_manifest", str(manifest.get("_relpath") or ""))

    return sorted(records, key=lambda item: (str(item.get("category") or ""), str(item.get("path") or "")))


def _declared_unit_output_paths(workspace: Path) -> list[str]:
    units_path = workspace / "UNITS.csv"
    if not units_path.exists():
        return []
    try:
        table = UnitsTable.load(units_path)
    except Exception:
        return []
    return _declared_unit_output_paths_from_table(table)


def _declared_unit_output_paths_from_table(table: UnitsTable) -> list[str]:
    relpaths: list[str] = []
    seen: set[str] = set()
    for row in table.rows:
        for raw_output in parse_semicolon_list(row.get("outputs")):
            relpath = _strip_optional_marker(raw_output)
            if not relpath or relpath in seen:
                continue
            seen.add(relpath)
            relpaths.append(relpath)
    return relpaths


def _artifact_pack_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, dict[str, int]] = {}
    for record in records:
        category = str(record.get("category") or "uncategorized")
        counts = by_category.setdefault(category, {"total": 0, "present": 0, "missing": 0})
        counts["total"] += 1
        if record.get("exists"):
            counts["present"] += 1
        else:
            counts["missing"] += 1
    total = len(records)
    present = sum(1 for record in records if record.get("exists"))
    return {
        "total": total,
        "present": present,
        "missing": total - present,
        "by_category": {category: by_category[category] for category in sorted(by_category)},
    }


def _source_report_record(payload: dict[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema": str(payload.get("schema") or ""),
        "verdict": str(payload.get("verdict") or ""),
        "exit_code": int(payload.get("exit_code") or 0),
    }
    run_state = payload.get("run_state")
    if isinstance(run_state, dict):
        record["run_state"] = {
            "phase": str(run_state.get("phase") or ""),
            **{key: run_state.get(key) if isinstance(run_state.get(key), int) else 0 for key in RUN_STATE_INTEGER_KEYS},
        }
    return record


def _artifact_pack_record_details(record: dict[str, Any]) -> str:
    if record.get("type") == "file":
        size = record.get("size")
        digest = str(record.get("sha256") or "")
        digest_preview = digest[:12] if digest else ""
        if isinstance(size, int) and digest_preview:
            return f"{size} bytes, sha256 {digest_preview}"
        if isinstance(size, int):
            return f"{size} bytes"
    if record.get("type") == "directory":
        count = record.get("file_count")
        if isinstance(count, int):
            return f"{count} files"
    return ""


def _artifact_pack_excerpt_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in payload.get("artifacts") or []:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "").strip()
        path = str(item.get("path") or "").strip()
        if not category or not path:
            continue
        records.append(
            {
                "category": category,
                "path": path,
                "exists": bool(item.get("exists")),
                "role": _artifact_pack_excerpt_role(category),
            }
        )
    return sorted(records, key=lambda record: (record["category"], record["path"]))


def _artifact_pack_excerpt_role(category: str) -> str:
    return {
        "target_artifact": "final deliverable or declared target artifact",
        "unit_output": "declared unit output",
        "run_ledger": "workspace run ledger",
        "harness_report": "harness evidence report",
        "unit_manifest": "per-unit output manifest",
    }.get(category, "indexed artifact")


def _int_mapping_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    keys = sorted(set(before).union(after))
    delta: dict[str, int] = {}
    for key in keys:
        before_value = before.get(key, 0)
        after_value = after.get(key, 0)
        if not isinstance(before_value, int) or not isinstance(after_value, int):
            continue
        change = after_value - before_value
        if change:
            delta[str(key)] = change
    return delta


def _target_artifact_changes(before_payload: dict[str, Any], after_payload: dict[str, Any]) -> list[dict[str, Any]]:
    before = _target_artifact_map(before_payload)
    after = _target_artifact_map(after_payload)
    records: list[dict[str, Any]] = []
    for relpath in sorted(set(before).union(after)):
        before_exists = before.get(relpath)
        after_exists = after.get(relpath)
        change = _target_artifact_change(before_exists, after_exists)
        if change.startswith("unchanged_"):
            continue
        records.append(
            {
                "path": relpath,
                "before_exists": before_exists,
                "after_exists": after_exists,
                "change": change,
            }
        )
    return records


def _target_artifact_map(payload: dict[str, Any]) -> dict[str, bool]:
    records: dict[str, bool] = {}
    for item in payload.get("target_artifacts") or []:
        if not isinstance(item, dict):
            continue
        relpath = item.get("path")
        exists = item.get("exists")
        if isinstance(relpath, str) and isinstance(exists, bool):
            records[relpath] = exists
    return records


def _target_artifact_change(before_exists: bool | None, after_exists: bool | None) -> str:
    if before_exists is None:
        return "added_present" if after_exists else "added_missing"
    if after_exists is None:
        return "removed_present" if before_exists else "removed_missing"
    if before_exists and after_exists:
        return "unchanged_present"
    if not before_exists and not after_exists:
        return "unchanged_missing"
    return "became_present" if after_exists else "became_missing"


def _manifest_count(payload: dict[str, Any]) -> int:
    manifests = payload.get("unit_output_manifests") or {}
    count = manifests.get("count") if isinstance(manifests, dict) else 0
    return count if isinstance(count, int) else 0


def _attempt_comparison(
    before_payload: dict[str, Any],
    after_payload: dict[str, Any],
) -> dict[str, Any]:
    before = before_payload.get("attempts")
    after = after_payload.get("attempts")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return {
            "available": False,
            "counters": {},
            "process_metrics": {},
            "note": "One or both audits predate Attempt summaries.",
        }

    counter_keys = ("started", "finished", "open", "retry_units", "extra_attempts")
    before_metrics = before.get("process_metrics")
    after_metrics = after.get("process_metrics")
    if not isinstance(before_metrics, dict) or not isinstance(after_metrics, dict):
        return {
            "available": False,
            "counters": {},
            "process_metrics": {},
            "note": "One or both audits lack process metrics.",
        }

    counters = {
        key: _numeric_delta(before.get(key), after.get(key), integer_only=True)
        for key in counter_keys
    }
    metric_keys = (
        "measured_attempts",
        "total_elapsed_ms",
        "mean_elapsed_ms",
        "max_elapsed_ms",
        "stdout_chars",
        "stderr_chars",
    )
    process_metrics = {
        key: _numeric_delta(
            before_metrics.get(key),
            after_metrics.get(key),
            integer_only=key in {"measured_attempts", "stdout_chars", "stderr_chars"},
        )
        for key in metric_keys
    }
    return {
        "available": True,
        "counters": counters,
        "process_metrics": process_metrics,
        "note": "Descriptive evidence only; Attempt and runtime deltas do not affect the diff verdict.",
    }


def _numeric_delta(before: Any, after: Any, *, integer_only: bool) -> dict[str, int | float | None]:
    def normalize(value: Any) -> int | float | None:
        if isinstance(value, bool):
            return None
        if integer_only:
            return value if isinstance(value, int) else None
        return value if isinstance(value, (int, float)) else None

    before_value = normalize(before)
    after_value = normalize(after)
    delta = None
    if before_value is not None and after_value is not None:
        delta = after_value - before_value
    return {
        "before": before_value,
        "after": after_value,
        "delta": delta,
    }


def _format_count_delta(label: str, counts: dict[str, Any]) -> str:
    before = int(counts.get("before") or 0)
    after = int(counts.get("after") or 0)
    delta = int(counts.get("delta") or 0)
    sign = "+" if delta > 0 else ""
    return f"- {label}: {before} -> {after} ({sign}{delta})"


def _format_numeric_delta(label: str, values: dict[str, Any]) -> str:
    before = values.get("before")
    after = values.get("after")
    delta = values.get("delta")
    if before is None or after is None or delta is None:
        return f"- {label}: unavailable"
    sign = "+" if delta > 0 else ""
    return f"- {label}: {before} -> {after} ({sign}{delta})"


def _recent_report_summaries(workspace: Path) -> list[str]:
    report_paths = [
        workspace / "output" / "RUN_ERRORS.md",
        workspace / "output" / "QUALITY_GATE.md",
        workspace / "output" / "CONTRACT_REPORT.md",
    ]
    lines: list[str] = ["", "## Recent harness reports"]
    found = False
    for path in report_paths:
        if not path.exists() or path.stat().st_size == 0:
            continue
        found = True
        preview = _first_nonempty_content_line(path)
        rel = path.relative_to(workspace)
        suffix = f": {preview}" if preview else ""
        lines.append(f"- `{rel}`{suffix}")
    if not found:
        lines.append("- No recent harness reports found")
    return lines


def _first_nonempty_content_line(path: Path) -> str:
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        return line[:160]
    return ""


def _pipeline_lock_summary(path: Path) -> str:
    if not path.exists():
        return ""
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if line:
            return line
    return ""


def _pipeline_lock_fields(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    if not path.exists():
        return fields
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        if key:
            fields[key] = value.strip()
    return fields


def _load_locked_pipeline_spec(*, workspace: Path, repo_root: Path):
    from tooling.pipeline_spec import PipelineSpec

    pipeline_value = _pipeline_lock_fields(workspace / "PIPELINE.lock.md").get("pipeline", "")
    if not pipeline_value:
        return None
    spec_path = resolve_pipeline_spec_path(repo_root=repo_root, pipeline_value=pipeline_value)
    if spec_path is None:
        return None
    try:
        return PipelineSpec.load(spec_path)
    except Exception:
        return None


def _current_checkpoint(path: Path) -> str:
    if not path.exists():
        return "unknown"
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for idx, line in enumerate(lines):
        if line.strip() != "## Current checkpoint":
            continue
        for candidate in lines[idx + 1 :]:
            value = candidate.strip()
            if not value:
                continue
            if value.startswith("#"):
                break
            return value.lstrip("- ").strip().strip("`") or "unknown"
    return "unknown"


def _format_issue(issue: HarnessIssue) -> str:
    return (
        f"- {issue.level} `{issue.code}`: {issue.message}\n"
        f"  Remediation: `{issue.remediation_category}`\n"
        f"  Next action: {issue.next_action}"
    )


def _issue_record(issue: HarnessIssue) -> dict[str, str]:
    return {
        "level": issue.level,
        "code": issue.code,
        "message": issue.message,
        "remediation_category": issue.remediation_category,
        "next_action": issue.next_action,
    }


def _next_runnable_record(row: dict[str, str]) -> dict[str, str]:
    return {
        "unit_id": _unit_id(row),
        "title": str(row.get("title") or "").strip() or "(untitled)",
        "skill": str(row.get("skill") or "").strip() or "(no skill)",
        "owner": str(row.get("owner") or "").strip(),
        "checkpoint": str(row.get("checkpoint") or "").strip(),
        "status": _status(row),
    }


def _format_issue_record(issue: dict[str, Any]) -> str:
    return (
        f"- {issue.get('level')} `{issue.get('code')}`: {issue.get('message')}\n"
        f"  Remediation: `{issue.get('remediation_category')}`\n"
        f"  Next action: {issue.get('next_action')}"
    )


def _manifest_summary(record: dict[str, Any]) -> dict[str, Any]:
    outputs = record.get("outputs") if isinstance(record.get("outputs"), list) else []
    return {
        "path": str(record.get("_relpath") or ""),
        "run_id": str(record.get("run_id") or ""),
        "attempt_id": str(record.get("attempt_id") or ""),
        "unit_id": str(record.get("unit_id") or ""),
        "skill": str(record.get("skill") or ""),
        "status": str(record.get("status") or ""),
        "exit_code": record.get("exit_code"),
        "generated_at": str(record.get("generated_at") or ""),
        "outputs": outputs,
    }


def _unit_manifest_records(workspace: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted((workspace / "output" / "unit_logs").glob("*.manifest.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(record, dict):
            continue
        record["_relpath"] = str(path.relative_to(workspace))
        record["_mtime_ns"] = path.stat().st_mtime_ns
        records.append(record)
    return sorted(
        records,
        key=lambda item: (
            str(item.get("generated_at") or ""),
            int(item.get("_mtime_ns") or 0),
            str(item.get("_relpath") or ""),
        ),
    )


def _recent_report_records(workspace: Path) -> list[dict[str, str]]:
    report_paths = [
        workspace / "output" / "RUN_ERRORS.md",
        workspace / "output" / "QUALITY_GATE.md",
        workspace / "output" / "CONTRACT_REPORT.md",
    ]
    records: list[dict[str, str]] = []
    for path in report_paths:
        if not path.exists() or path.stat().st_size == 0:
            continue
        records.append(
            {
                "path": str(path.relative_to(workspace)),
                "preview": _first_nonempty_content_line(path),
            }
        )
    return records


def _unit_id(row: dict[str, str]) -> str:
    return str(row.get("unit_id") or "").strip()


def _status(row: dict[str, str]) -> str:
    return str(row.get("status") or "").strip().upper()


def _owner(row: dict[str, str]) -> str:
    return str(row.get("owner") or "").strip().upper()


def _strip_optional_marker(relpath: str) -> str:
    relpath = str(relpath or "").strip()
    if relpath.startswith("?"):
        return relpath[1:].strip()
    return relpath
