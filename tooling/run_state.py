"""Durable Run state and provenance primitives.

These mutation helpers are internal Harness APIs. A complete user operation
must hold `workspace_invocation_lock` once at its outermost CLI or product
boundary; internal helpers must not shell back into another command for the same
Workspace. The lock is deliberately not reacquired inside each primitive so a
Completion transaction remains one uninterrupted critical section.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import uuid
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

try:
    import fcntl
except ImportError:  # pragma: no cover - the local Harness currently targets POSIX runtimes.
    fcntl = None  # type: ignore[assignment]

from tooling.common import (
    UnitsTable,
    atomic_write_text,
    decisions_has_approval,
    ensure_dir,
    goal_constraints_from_request,
    load_workspace_pipeline_spec,
    now_iso_seconds,
    parse_semicolon_list,
    set_decisions_approval,
    update_status_log,
)
from tooling.harness_contracts import HARNESS_KERNEL_PATHS
from tooling.pipeline_snapshot import inspect_pipeline_snapshot_bundle
from tooling.run_state_io import (
    _append_jsonl,
    _last_event_seq,
    _read_json_object,
    _read_jsonl,
    _write_json,
    read_jsonl_with_errors,
)


HARNESS_DIR = ".harness"
GOAL_SCHEMA = "goal-spec.v2"
RUN_SCHEMA = "run-state.v1"
LOCK_SCHEMA = "harness-lock.v2"
RUN_PLAN_SCHEMA = "run-plan.v1"
EVENT_SCHEMA = "run-event.v1"
ATTEMPT_SCHEMA = "unit-attempt.v1"
ARTIFACT_SCHEMA = "artifact-record.v1"
FAILURE_SCHEMA = "failure-record.v1"
EVALUATION_SCHEMA = "run-evaluation.v1"
INVOCATION_LOCK_SCHEMA = "workspace-invocation-lock.v1"
COMPLETION_PROTOCOL = "recoverable-provenance.v2"
MIGRATABLE_COMPLETION_PROTOCOLS = {"recoverable-provenance.v1"}
RECOVERABLE_COMPLETION_FAILURE_TYPES = {
    "acceptance_recovery_failed",
    "completion_manifest_error",
}
CHECKPOINT_REVIEW_BASIS_SCHEMA = "checkpoint-review-basis.v1"
LEGACY_COMPLETION_EVIDENCE_CODES = {
    "attempt_artifact_missing",
    "attempt_start_event_missing",
    "attempt_terminal_event_missing",
    "done_output_unregistered",
    "done_without_manifest",
    "done_without_successful_attempt",
    "failure_resolution_type_mismatch",
    "failure_resolution_unverified",
    "manifest_artifact_hash_mismatch",
    "manifest_artifact_missing",
}
MUTABLE_PROJECTION_PATHS = {
    "STATUS.md",
    "UNITS.csv",
    "CHECKPOINTS.md",
    "DECISIONS.md",
    "output/QUALITY_GATE.md",
    "output/RUN_ERRORS.md",
    "output/CONTRACT_REPORT.md",
    "output/DOCTOR_REPORT.md",
    "output/DOCTOR_REPORT.json",
    "output/RUN_AUDIT.md",
    "output/RUN_AUDIT.json",
    "output/IMPROVEMENT_REPORT.md",
    "output/IMPROVEMENT_REPORT.json",
    "output/ARTIFACT_PACK.md",
    "output/ARTIFACT_PACK.json",
}


class ConcurrentInvocationError(RuntimeError):
    """Raised when another process already owns the Workspace mutation boundary."""


class RevisionLockDriftError(RuntimeError):
    """Raised when an active Run no longer matches its pinned Harness Kernel."""


def _durable_run_evidence_files(workspace: Path) -> tuple[Path, ...]:
    harness_dir = workspace / HARNESS_DIR
    if not harness_dir.is_dir():
        return ()
    return tuple(
        path
        for path in harness_dir.rglob("*")
        if path.is_file()
        and path.relative_to(harness_dir).as_posix() != "invocation.lock"
        and not path.relative_to(harness_dir).as_posix().startswith("tmp/")
    )


def workspace_has_durable_run_evidence(workspace: Path) -> bool:
    """Return whether a Workspace already contains evidence owned by a Run."""

    return bool(_durable_run_evidence_files(workspace))


def _run_identity_differences(workspace: Path) -> tuple[bool, list[str], list[str]]:
    """Return durable-evidence presence plus missing and inconsistent identity paths."""

    harness_dir = workspace / HARNESS_DIR
    durable_files = _durable_run_evidence_files(workspace)
    if not durable_files:
        return False, [], []

    missing: list[str] = []
    drifted: list[str] = []

    def label(relpath: str) -> str:
        return f"{HARNESS_DIR}/{relpath}"

    def require_file(relpath: str) -> Path | None:
        path = harness_dir / relpath
        if not path.is_file():
            missing.append(label(relpath))
            return None
        return path

    run_path = require_file("run.json")
    lock_path = require_file("harness.lock.json")
    goal_path = require_file("goal.json")
    run = _read_json_object(run_path) if run_path else {}
    lock = _read_json_object(lock_path) if lock_path else {}
    goal = _read_json_object(goal_path) if goal_path else {}

    run_id = str(run.get("run_id") or "")
    goal_id = str(run.get("goal_id") or "")
    if (
        str(run.get("schema") or "") != RUN_SCHEMA
        or not run_id
        or not goal_id
    ) and run_path:
        drifted.append(label("run.json"))
    if (
        str(lock.get("schema") or "") != LOCK_SCHEMA
        or not run_id
        or str(lock.get("run_id") or "") != run_id
    ) and lock_path:
        drifted.append(label("harness.lock.json"))
    if (
        str(goal.get("schema") or "") != GOAL_SCHEMA
        or not run_id
        or str(goal.get("run_id") or "") != run_id
        or not goal_id
        or str(goal.get("goal_id") or "") != goal_id
        or str(goal.get("workflow") or "") != str(run.get("workflow") or "")
    ) and goal_path:
        drifted.append(label("goal.json"))

    for relpath in ("plan/planned.json", "plan/effective.json"):
        path = require_file(relpath)
        payload = _read_json_object(path) if path else {}
        if path and (
            str(payload.get("schema") or "") != RUN_PLAN_SCHEMA
            or not run_id
            or str(payload.get("run_id") or "") != run_id
        ):
            drifted.append(label(relpath))

    for relpath in (
        "events.jsonl",
        "attempts.jsonl",
        "artifacts.jsonl",
        "decisions.jsonl",
        "failures/ledger.jsonl",
        "evaluations/ledger.jsonl",
    ):
        path = require_file(relpath)
        if path is None:
            continue
        records, malformed_lines = read_jsonl_with_errors(path)
        if malformed_lines or any(
            not run_id or str(record.get("run_id") or "") != run_id
            for record in records
        ):
            drifted.append(label(relpath))

    return True, sorted(set(missing)), sorted(set(drifted))


def inspect_kernel_lock(*, workspace: Path, repo_root: Path | None = None) -> dict[str, Any]:
    """Validate an existing Run lock against the executing repository.

    Read-only tools can still interpret historical locks. Mutation fails closed
    for every Workspace with durable Run evidence unless its v2 Run, Goal,
    lock, plans, ledgers, and current Kernel agree. This prevents missing,
    corrupted, downgraded, cross-Run, or stale identity from becoming a bypass.
    """

    root = (repo_root or Path(__file__).resolve().parents[1]).resolve()
    lock_path = workspace / HARNESS_DIR / "harness.lock.json"
    has_run_evidence, identity_missing, identity_drifted = (
        _run_identity_differences(workspace)
    )
    if not has_run_evidence:
        return {
            "status": "NOT_APPLICABLE",
            "locked_file_count": 0,
            "current_file_count": 0,
            "matched_file_count": 0,
            "missing_paths": [],
            "unexpected_paths": [],
            "drifted_paths": [],
        }

    lock = _read_json_object(lock_path)
    lock_schema = str(lock.get("schema") or "")

    if lock_schema != LOCK_SCHEMA:
        return {
            "status": "DRIFT",
            "locked_file_count": 0,
            "current_file_count": sum(
                1 for relpath in HARNESS_KERNEL_PATHS if (root / relpath).is_file()
            ),
            "matched_file_count": 0,
            "missing_paths": identity_missing,
            "unexpected_paths": [],
            "drifted_paths": identity_drifted,
        }

    raw_kernel = lock.get("kernel")
    kernel = raw_kernel if isinstance(raw_kernel, dict) else {}
    current_paths = {
        relpath for relpath in HARNESS_KERNEL_PATHS if (root / relpath).is_file()
    }
    locked_paths = {
        str(relpath)
        for relpath, digest in kernel.items()
        if isinstance(relpath, str) and isinstance(digest, str)
    }
    missing_paths = sorted({*identity_missing, *(current_paths - locked_paths)})
    unexpected_paths = sorted(locked_paths - current_paths)
    drifted_paths: list[str] = list(identity_drifted)
    matched_file_count = 0
    for relpath in sorted(current_paths & locked_paths):
        expected = str(kernel.get(relpath) or "").strip().lower()
        if re.fullmatch(r"[0-9a-f]{64}", expected) and _file_sha256(root / relpath) == expected:
            matched_file_count += 1
        else:
            drifted_paths.append(relpath)

    status = "PASS"
    drifted_paths = sorted(set(drifted_paths))
    if not isinstance(raw_kernel, dict) or missing_paths or unexpected_paths or drifted_paths:
        status = "DRIFT"
    return {
        "status": status,
        "locked_file_count": len(locked_paths),
        "current_file_count": len(current_paths),
        "matched_file_count": matched_file_count,
        "missing_paths": missing_paths,
        "unexpected_paths": unexpected_paths,
        "drifted_paths": drifted_paths,
    }


def require_current_kernel_lock(*, workspace: Path, repo_root: Path | None = None) -> None:
    """Refuse active execution when the pinned Harness Kernel has drifted."""

    inspection = inspect_kernel_lock(workspace=workspace, repo_root=repo_root)
    if inspection["status"] != "DRIFT":
        return
    affected = [
        *inspection["missing_paths"],
        *inspection["unexpected_paths"],
        *inspection["drifted_paths"],
    ]
    preview = ", ".join(f"`{path}`" for path in affected[:6]) or "the v2 Kernel manifest"
    suffix = " ..." if len(affected) > 6 else ""
    raise RevisionLockDriftError(
        "Harness Kernel drift detected for this Run: "
        f"{preview}{suffix}. Start a new Run under the current revision; "
        "do not continue an existing Run across Kernel implementations."
    )


@contextmanager
def workspace_invocation_lock(*, workspace: Path, operation: str) -> Iterator[dict[str, Any]]:
    """Reject concurrent Harness commands against one Workspace.

    The lock is advisory and process-scoped. `flock` releases it automatically
    when the process exits, so a crashed command cannot leave a stale lease that
    must be cleared manually. The JSON file is diagnostic metadata; file
    existence alone never means the Workspace is locked.
    """

    if fcntl is None:
        raise RuntimeError("Workspace invocation locking requires a POSIX runtime with `fcntl` support.")

    workspace = workspace.resolve()
    harness_dir = workspace / HARNESS_DIR
    ensure_dir(harness_dir)
    lock_path = harness_dir / "invocation.lock"
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.seek(0)
            raw_owner = handle.read().strip()
            try:
                owner = json.loads(raw_owner) if raw_owner else {}
            except json.JSONDecodeError:
                owner = {}
            owner_detail = ""
            if isinstance(owner, dict) and owner:
                owner_detail = (
                    f" (operation={owner.get('operation') or 'unknown'}, "
                    f"pid={owner.get('pid') or 'unknown'}, host={owner.get('host') or 'unknown'})"
                )
            raise ConcurrentInvocationError(
                f"Workspace is busy: another Harness command holds `{lock_path}`{owner_detail}. "
                "Wait for that command to finish, then retry."
            ) from exc

        owner = {
            "schema": INVOCATION_LOCK_SCHEMA,
            "workspace": str(workspace),
            "operation": str(operation or "unknown"),
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "acquired_at": now_iso_seconds(),
        }
        handle.seek(0)
        handle.truncate()
        json.dump(owner, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        yield owner
    finally:
        try:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def initialize_run_state(
    *,
    workspace: Path,
    repo_root: Path,
    pipeline_path: Path | None,
    units_template: str,
    goal_text: str = "",
) -> dict[str, Any]:
    """Create the machine-readable run ledger without replacing human-readable files."""

    workspace = workspace.resolve()
    harness_dir = workspace / HARNESS_DIR
    ensure_dir(harness_dir / "plan")
    ensure_dir(harness_dir / "failures")
    ensure_dir(harness_dir / "context")
    ensure_dir(harness_dir / "evaluations")
    ensure_dir(harness_dir / "workers")
    ensure_dir(harness_dir / "tmp")
    for ledger in (
        harness_dir / "attempts.jsonl",
        harness_dir / "decisions.jsonl",
        harness_dir / "artifacts.jsonl",
        harness_dir / "failures" / "ledger.jsonl",
        harness_dir / "evaluations" / "ledger.jsonl",
    ):
        if not ledger.exists():
            atomic_write_text(ledger, "")

    run_path = harness_dir / "run.json"
    existing = _read_json_object(run_path)
    run_id = str(existing.get("run_id") or _new_id("run"))
    goal_id = str(existing.get("goal_id") or _new_id("goal"))
    created_at = str(existing.get("created_at") or now_iso_seconds())

    pipeline_rel = _relative_or_absolute(pipeline_path, repo_root) if pipeline_path else ""
    existing_goal = _read_json_object(harness_dir / "goal.json")
    workflow = (
        pipeline_path.name.removesuffix(".pipeline.md")
        if pipeline_path
        else str(existing.get("workflow") or existing_goal.get("workflow") or "unknown")
    )
    request = (
        goal_text.strip()
        or _goal_request_from_markdown(workspace / "GOAL.md")
        or str(existing_goal.get("request") or "")
    )

    existing_criteria = existing_goal.get("success_criteria")
    existing_targets = (
        list(existing_criteria)
        if isinstance(existing_criteria, list)
        else list((existing_criteria or {}).get("required_artifacts") or [])
        if isinstance(existing_criteria, dict)
        else []
    )
    target_artifacts = _pipeline_targets(pipeline_path) or existing_targets
    constraints = dict(existing_goal.get("constraints") or {})
    constraints.update(goal_constraints_from_request(request))
    goal_payload = {
        "schema": GOAL_SCHEMA,
        "goal_id": goal_id,
        "run_id": run_id,
        "request": request,
        "workflow": workflow,
        "constraints": constraints,
        "target_artifacts": target_artifacts,
        "success_criteria": {
            "required_artifacts": target_artifacts,
            "constraints": constraints,
        },
        "updated_at": now_iso_seconds(),
    }
    _write_json(harness_dir / "goal.json", goal_payload)

    if not (harness_dir / "harness.lock.json").exists():
        pipeline_snapshot = _materialize_pipeline_contract_snapshot(
            workspace=workspace,
            repo_root=repo_root,
            pipeline_path=pipeline_path,
        )
        _write_json(
            harness_dir / "harness.lock.json",
            _build_harness_lock(
                run_id=run_id,
                workspace=workspace,
                repo_root=repo_root,
                pipeline_path=pipeline_path,
                units_template=units_template,
                pipeline_snapshot=pipeline_snapshot,
            ),
        )

    plan = _build_plan_snapshot(workspace=workspace, run_id=run_id, workflow=workflow)
    if not (harness_dir / "plan" / "planned.json").exists():
        _write_json(harness_dir / "plan" / "planned.json", plan)
    if not (harness_dir / "plan" / "effective.json").exists():
        _write_json(harness_dir / "plan" / "effective.json", plan)

    if not (harness_dir / "events.jsonl").exists():
        _append_event(
            workspace=workspace,
            run_id=run_id,
            event_type="run.created",
            actor={"kind": "harness", "id": "workspace-init"},
            payload={"goal_id": goal_id, "workflow": workflow},
        )
        _append_event(
            workspace=workspace,
            run_id=run_id,
            event_type="run.planned",
            actor={"kind": "harness", "id": "workspace-init"},
            payload={"unit_count": len(plan["units"])},
        )

    snapshot = {
        "schema": RUN_SCHEMA,
        "run_id": run_id,
        "goal_id": goal_id,
        "workflow": workflow,
        "state": str(existing.get("state") or "PLANNED"),
        "created_at": created_at,
        "updated_at": now_iso_seconds(),
        "active_attempt_id": existing.get("active_attempt_id"),
        "current_unit_id": existing.get("current_unit_id"),
        "unit_status": _unit_status_counts(workspace),
        "last_event_seq": _last_event_seq(harness_dir / "events.jsonl"),
    }
    _write_json(run_path, snapshot)
    return snapshot


def ensure_run_state(
    *,
    workspace: Path,
    repo_root: Path,
    recover_stale_doing: bool = False,
) -> dict[str, Any]:
    existing = _read_json_object(workspace / HARNESS_DIR / "run.json")
    if existing:
        snapshot = reconcile_run_state(workspace=workspace)
    else:
        pipeline_path: Path | None = None
        units_template = ""
        try:
            spec = load_workspace_pipeline_spec(workspace)
            pipeline_path = spec.path
            units_template = str(spec.units_template)
        except Exception:
            pass
        snapshot = initialize_run_state(
            workspace=workspace,
            repo_root=repo_root,
            pipeline_path=pipeline_path,
            units_template=units_template,
        )

    if not recover_stale_doing:
        return snapshot

    units_path = workspace / "UNITS.csv"
    if not units_path.exists():
        return snapshot
    try:
        table = UnitsTable.load(units_path)
    except Exception:
        return snapshot
    recovered = recover_stale_doing_units(
        table,
        eligible_unit_ids=_stale_doing_unit_ids(workspace=workspace, table=table),
    )
    if not recovered:
        return snapshot

    table.save(units_path)
    for unit_id in recovered:
        record_recovered_interruption(
            workspace=workspace,
            repo_root=repo_root,
            unit_id=unit_id,
        )
    update_status_log(
        workspace / "STATUS.md",
        f"{now_iso_seconds()} RECOVERED stale DOING unit(s) to BLOCKED: {', '.join(recovered)}",
    )
    return reconcile_run_state(workspace=workspace)


def start_attempt(
    *,
    workspace: Path,
    repo_root: Path,
    unit_id: str,
    skill: str,
    inputs: Iterable[str],
    execution_mode: str = "manual",
    owner_pid: int | None = None,
) -> str:
    if execution_mode not in {"manual", "process", "recovery"}:
        raise ValueError(f"Unsupported Attempt execution mode: {execution_mode}")
    snapshot = ensure_run_state(workspace=workspace, repo_root=repo_root)
    existing_attempt = open_attempt_for_unit(workspace=workspace, unit_id=unit_id)
    if existing_attempt:
        raise ValueError(
            f"Unit {unit_id} already has open Attempt {existing_attempt.get('attempt_id')}; "
            "finish or interrupt it before starting another."
        )
    attempt_id = _new_id("attempt")
    input_paths = list(inputs)
    record = {
        "schema": ATTEMPT_SCHEMA,
        "record_type": "started",
        "run_id": snapshot["run_id"],
        "attempt_id": attempt_id,
        "unit_id": unit_id,
        "skill": skill,
        "status": "RUNNING",
        "started_at": now_iso_seconds(),
        "inputs": input_paths,
        "execution_mode": execution_mode,
    }
    if execution_mode == "process":
        record["owner_pid"] = owner_pid if owner_pid is not None else os.getpid()
        record["owner_host"] = socket.gethostname()
    _append_jsonl(workspace / HARNESS_DIR / "attempts.jsonl", record)
    _append_event(
        workspace=workspace,
        run_id=str(snapshot["run_id"]),
        event_type="unit.attempt.started",
        actor={"kind": "agent", "id": skill or "unknown-skill"},
        unit_id=unit_id,
        attempt_id=attempt_id,
        payload={"inputs": input_paths},
    )
    _update_run_snapshot(
        workspace=workspace,
        state="RUNNING",
        active_attempt_id=attempt_id,
        current_unit_id=unit_id,
    )
    return attempt_id


def open_attempt_for_unit(*, workspace: Path, unit_id: str) -> dict[str, Any]:
    records = _read_jsonl(workspace / HARNESS_DIR / "attempts.jsonl")
    finished_ids = {
        str(record.get("attempt_id") or "")
        for record in records
        if record.get("record_type") == "finished"
    }
    for record in reversed(records):
        if (
            record.get("record_type") == "started"
            and str(record.get("unit_id") or "") == unit_id
            and str(record.get("attempt_id") or "") not in finished_ids
        ):
            return record
    return {}


def finish_attempt(
    *,
    workspace: Path,
    attempt_id: str,
    unit_id: str,
    skill: str,
    status: str,
    exit_code: int | None,
    outputs: Iterable[str] = (),
    message: str = "",
    resolved_failure_types: Iterable[str] = (),
    execution: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    attempt_records = _read_jsonl(workspace / HARNESS_DIR / "attempts.jsonl")
    started = [
        record
        for record in attempt_records
        if record.get("record_type") == "started" and str(record.get("attempt_id") or "") == attempt_id
    ]
    if not started:
        raise ValueError(f"Attempt {attempt_id} cannot finish without a matching start record.")
    started_record = started[-1]
    if str(started_record.get("unit_id") or "") != unit_id or str(started_record.get("skill") or "") != skill:
        raise ValueError(
            f"Attempt {attempt_id} started for Unit {started_record.get('unit_id')} "
            f"and Skill {started_record.get('skill')}; finish identity cannot be changed."
        )

    finished = [
        record
        for record in attempt_records
        if record.get("record_type") == "finished" and str(record.get("attempt_id") or "") == attempt_id
    ]
    if finished:
        previous = finished[-1]
        if str(previous.get("status") or "") != status:
            raise ValueError(
                f"Attempt {attempt_id} already finished as {previous.get('status')}; cannot finish it as {status}."
            )
        if str(previous.get("unit_id") or "") != unit_id or str(previous.get("skill") or "") != skill:
            raise ValueError(
                f"Attempt {attempt_id} is already bound to Unit {previous.get('unit_id')} "
                f"and Skill {previous.get('skill')}; completion identity cannot be changed."
            )
        artifact_ids = {str(item) for item in previous.get("artifact_ids") or []}
        return [
            record
            for record in _read_jsonl(workspace / HARNESS_DIR / "artifacts.jsonl")
            if str(record.get("artifact_id") or "") in artifact_ids
        ]

    snapshot = _read_json_object(workspace / HARNESS_DIR / "run.json")
    run_id = str(snapshot.get("run_id") or "")
    if str(started_record.get("run_id") or "") != run_id:
        raise ValueError(f"Attempt {attempt_id} does not belong to the current Run {run_id}.")
    artifacts = register_artifacts(
        workspace=workspace,
        run_id=run_id,
        attempt_id=attempt_id,
        unit_id=unit_id,
        outputs=outputs,
    )
    record = {
        "schema": ATTEMPT_SCHEMA,
        "record_type": "finished",
        "run_id": run_id,
        "attempt_id": attempt_id,
        "unit_id": unit_id,
        "skill": skill,
        "status": status,
        "finished_at": now_iso_seconds(),
        "exit_code": exit_code,
        "artifact_ids": [item["artifact_id"] for item in artifacts],
        "message": message,
    }
    execution_record = _normalize_attempt_execution(execution)
    if execution_record:
        record["execution"] = execution_record
    _append_jsonl(workspace / HARNESS_DIR / "attempts.jsonl", record)
    event_type = _attempt_terminal_event_type(status)
    event_payload = {"status": status, "exit_code": exit_code, "message": message}
    if execution_record:
        event_payload["execution"] = execution_record
    _append_event(
        workspace=workspace,
        run_id=run_id,
        event_type=event_type,
        actor={"kind": "harness", "id": "unit-executor"},
        unit_id=unit_id,
        attempt_id=attempt_id,
        payload=event_payload,
    )
    verified_failure_types = {
        str(item or "").strip() for item in resolved_failure_types if str(item or "").strip()
    }
    if status == "SUCCEEDED" and verified_failure_types:
        _resolve_open_failures(
            workspace=workspace,
            unit_id=unit_id,
            attempt_id=attempt_id,
            run_id=run_id,
            failure_types=verified_failure_types,
        )
    next_state = _project_run_state(workspace, attempt_status=status)
    _update_run_snapshot(
        workspace=workspace,
        state=next_state,
        active_attempt_id=None,
        current_unit_id=None,
    )
    if next_state == "COMPLETED":
        _append_event(
            workspace=workspace,
            run_id=run_id,
            event_type="run.completed",
            actor={"kind": "harness", "id": "unit-executor"},
            payload={"unit_status": _unit_status_counts(workspace)},
        )
        _update_run_snapshot(workspace=workspace, state="COMPLETED")
    return artifacts


def _normalize_attempt_execution(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    record: dict[str, Any] = {}
    for key in ("adapter", "log_path"):
        text = str(value.get(key) or "").strip()
        if text:
            record[key] = text

    elapsed_ms = value.get("elapsed_ms")
    if (
        isinstance(elapsed_ms, (int, float))
        and not isinstance(elapsed_ms, bool)
        and elapsed_ms >= 0
    ):
        record["elapsed_ms"] = round(float(elapsed_ms), 3)

    for key in ("stdout_chars", "stderr_chars"):
        count = value.get(key)
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            record[key] = count
    return record


def _attempt_execution_validation_messages(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, dict):
        return ["must be an object"]

    issues: list[str] = []
    for field in ("adapter", "log_path"):
        if field in value and not isinstance(value.get(field), str):
            issues.append(f"`{field}` must be a string")
    elapsed_ms = value.get("elapsed_ms")
    if elapsed_ms is not None and (
        not isinstance(elapsed_ms, (int, float))
        or isinstance(elapsed_ms, bool)
        or elapsed_ms < 0
    ):
        issues.append("`elapsed_ms` must be a non-negative number")
    for field in ("stdout_chars", "stderr_chars"):
        count = value.get(field)
        if count is not None and (
            not isinstance(count, int)
            or isinstance(count, bool)
            or count < 0
        ):
            issues.append(f"`{field}` must be a non-negative integer")
    return issues


def _attempt_terminal_event_type(status: str) -> str:
    return {
        "SUCCEEDED": "unit.attempt.succeeded",
        "WAITING_HUMAN": "run.waiting_human",
        "INTERRUPTED": "unit.attempt.interrupted",
    }.get(status, "unit.attempt.failed")


def record_failure(
    *,
    workspace: Path,
    unit_id: str,
    attempt_id: str,
    failure_type: str,
    symptom: str,
    causal_behavior: str,
    harness_mechanism: str,
    repair_surface: Iterable[str],
    severity: str = "medium",
) -> dict[str, Any]:
    snapshot = _read_json_object(workspace / HARNESS_DIR / "run.json")
    record = {
        "schema": FAILURE_SCHEMA,
        "record_type": "opened",
        "failure_id": _new_id("failure"),
        "run_id": str(snapshot.get("run_id") or ""),
        "unit_id": unit_id,
        "attempt_id": attempt_id,
        "failure_type": failure_type,
        "severity": severity,
        "observable_failure": symptom,
        "causal_behavior": causal_behavior,
        "harness_mechanism": harness_mechanism,
        "repair_surface": list(repair_surface),
        "fingerprint": f"{unit_id}:{failure_type}",
        "status": "open",
        "recorded_at": now_iso_seconds(),
    }
    _append_jsonl(workspace / HARNESS_DIR / "failures" / "ledger.jsonl", record)
    _append_event(
        workspace=workspace,
        run_id=record["run_id"],
        event_type="failure.recorded",
        actor={"kind": "harness", "id": "unit-executor"},
        unit_id=unit_id,
        attempt_id=attempt_id,
        payload={"failure_id": record["failure_id"], "failure_type": failure_type},
    )
    return record


def _resolve_open_failures(
    *,
    workspace: Path,
    unit_id: str,
    attempt_id: str,
    run_id: str,
    failure_types: set[str],
) -> None:
    ledger_path = workspace / HARNESS_DIR / "failures" / "ledger.jsonl"
    active: dict[str, dict[str, Any]] = {}
    if ledger_path.exists():
        with ledger_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                failure_id = str(record.get("failure_id") or "")
                if not failure_id:
                    continue
                if record.get("status") == "open":
                    active[failure_id] = record
                else:
                    active.pop(failure_id, None)

    for failure in active.values():
        if str(failure.get("unit_id") or "") != unit_id:
            continue
        failure_type = str(failure.get("failure_type") or "")
        if failure_type not in failure_types:
            continue
        resolution = {
            "schema": FAILURE_SCHEMA,
            "record_type": "resolved",
            "failure_id": failure["failure_id"],
            "run_id": run_id,
            "unit_id": unit_id,
            "attempt_id": str(failure.get("attempt_id") or ""),
            "fingerprint": str(failure.get("fingerprint") or ""),
            "status": "resolved",
            "resolved_by_attempt_id": attempt_id,
            "verification": {
                "kind": "successful_attempt",
                "failure_type": failure_type,
            },
            "recorded_at": now_iso_seconds(),
        }
        _append_jsonl(ledger_path, resolution)
        _append_event(
            workspace=workspace,
            run_id=run_id,
            event_type="failure.resolved",
            actor={"kind": "harness", "id": "unit-executor"},
            unit_id=unit_id,
            attempt_id=attempt_id,
            payload={"failure_id": failure["failure_id"]},
        )


def record_decision(
    *,
    workspace: Path,
    action: str,
    subject: str,
    decision: str,
    actor: dict[str, str],
    note: str = "",
    review_basis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = _read_json_object(workspace / HARNESS_DIR / "run.json")
    previous_state = str(snapshot.get("state") or "")
    record = {
        "schema": "run-decision.v1",
        "decision_id": _new_id("decision"),
        "run_id": str(snapshot.get("run_id") or ""),
        "recorded_at": now_iso_seconds(),
        "actor": actor,
        "action": action,
        "subject": subject,
        "decision": decision,
        "note": note,
    }
    if review_basis is not None:
        record["review_basis"] = review_basis
    _append_jsonl(workspace / HARNESS_DIR / "decisions.jsonl", record)
    _append_event(
        workspace=workspace,
        run_id=record["run_id"],
        event_type="decision.recorded",
        actor=record["actor"],
        payload={"decision_id": record["decision_id"], "action": action, "subject": subject},
    )
    _refresh_effective_plan(workspace)
    next_state = _project_run_state(workspace)
    _update_run_snapshot(workspace=workspace, state=next_state)
    if next_state == "COMPLETED" and previous_state != "COMPLETED":
        _append_event(
            workspace=workspace,
            run_id=record["run_id"],
            event_type="run.completed",
            actor=record["actor"],
            payload={"unit_status": _unit_status_counts(workspace), "via": action},
        )
        _update_run_snapshot(workspace=workspace, state="COMPLETED")
    return record


def record_human_decision(
    *,
    workspace: Path,
    action: str,
    subject: str,
    decision: str,
    note: str = "",
    review_basis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return record_decision(
        workspace=workspace,
        action=action,
        subject=subject,
        decision=decision,
        actor={"kind": "human", "id": "workspace-operator"},
        note=note,
        review_basis=review_basis,
    )


def capture_checkpoint_review_basis(
    *,
    workspace: Path,
    checkpoint: str,
    require_active: bool = True,
) -> dict[str, Any]:
    """Fingerprint the artifacts a Checkpoint approval is expected to review."""

    workspace = workspace.resolve()
    checkpoint = str(checkpoint or "").strip()
    if not checkpoint:
        raise ValueError("Checkpoint must be non-empty.")
    units_path = workspace / "UNITS.csv"
    if not units_path.exists():
        raise ValueError(f"Checkpoint {checkpoint} has no UNITS.csv review contract.")
    table = UnitsTable.load(units_path)
    unit_by_id = {
        str(row.get("unit_id") or "").strip(): row
        for row in table.rows
        if str(row.get("unit_id") or "").strip()
    }
    candidates = [
        row
        for row in table.rows
        if str(row.get("checkpoint") or "").strip() == checkpoint
        and (
            str(row.get("owner") or "").strip().upper() == "HUMAN"
            or str(row.get("skill") or "").strip() == "human-checkpoint"
        )
    ]
    eligible: list[dict[str, str]] = []
    for row in candidates:
        status = str(row.get("status") or "").strip().upper()
        dependencies_ready = all(
            dependency in unit_by_id
            and str(unit_by_id[dependency].get("status") or "").strip().upper() in {"DONE", "SKIP"}
            for dependency in parse_semicolon_list(row.get("depends_on"))
        )
        active = status in {"TODO", "DOING", "BLOCKED"} and dependencies_ready
        if (require_active and active) or (not require_active and dependencies_ready):
            eligible.append(row)
    if len(eligible) != 1:
        qualifier = "active " if require_active else ""
        raise ValueError(
            f"Checkpoint {checkpoint} must resolve to exactly one {qualifier}HUMAN Unit; "
            f"found {len(eligible)}."
        )

    row = eligible[0]
    declared_paths: dict[str, bool] = {}

    def add_paths(value: object) -> None:
        for raw_path in parse_semicolon_list(value):
            optional = raw_path.startswith("?")
            relpath = raw_path[1:] if optional else raw_path
            relpath = relpath.strip()
            if relpath and relpath not in {"STATUS.md", "UNITS.csv", "CHECKPOINTS.md"}:
                declared_paths[relpath] = declared_paths.get(relpath, False) or not optional

    add_paths(row.get("inputs"))
    for dependency in parse_semicolon_list(row.get("depends_on")):
        dependency_row = unit_by_id.get(dependency)
        if dependency_row is None:
            continue
        add_paths(dependency_row.get("inputs"))
        add_paths(dependency_row.get("outputs"))

    artifacts: list[dict[str, Any]] = []
    missing: list[str] = []
    for relpath, required in sorted(declared_paths.items()):
        path = (workspace / relpath).resolve()
        try:
            path.relative_to(workspace)
        except ValueError:
            raise ValueError(f"Checkpoint {checkpoint} review path escapes the Workspace: {relpath}") from None
        if not path.exists():
            if required:
                missing.append(relpath)
            continue
        if relpath == "DECISIONS.md" and not _checkpoint_decisions_projection(
            path.read_text(encoding="utf-8", errors="replace"),
            checkpoint=checkpoint,
        ):
            continue
        fingerprint = _checkpoint_artifact_fingerprint(
            path=path,
            relpath=relpath,
            checkpoint=checkpoint,
        )
        artifacts.append({"path": relpath, **fingerprint})
    if missing:
        raise ValueError(
            f"Checkpoint {checkpoint} review basis is incomplete; missing: {', '.join(missing)}"
        )
    if not artifacts:
        raise ValueError(
            f"Checkpoint {checkpoint} has no review Artifacts; declare the evidence to review "
            "as Unit inputs or dependency inputs/outputs before approval."
        )
    return {
        "schema": CHECKPOINT_REVIEW_BASIS_SCHEMA,
        "checkpoint": checkpoint,
        "unit_id": str(row.get("unit_id") or "").strip(),
        "artifacts": artifacts,
    }


def checkpoint_approval_status(*, workspace: Path, checkpoint: str) -> str:
    """Classify the latest durable approval against the current review basis."""

    checkpoint = str(checkpoint or "").strip()
    if not checkpoint:
        return "missing"
    approval: dict[str, Any] | None = None
    for record in _read_jsonl(workspace / HARNESS_DIR / "decisions.jsonl"):
        if str(record.get("subject") or "").strip() != checkpoint:
            continue
        action = str(record.get("action") or "").strip()
        decision = str(record.get("decision") or "").strip().lower()
        if action in {"checkpoint.approved", "checkpoint.auto_approved"}:
            approval = record if decision == "approved" else None
        elif action == "checkpoint.approval.revoked":
            approval = None
    if approval is None or not isinstance(approval.get("review_basis"), dict):
        return "legacy" if approval is not None else "missing"
    try:
        current_basis = capture_checkpoint_review_basis(
            workspace=workspace,
            checkpoint=checkpoint,
            require_active=False,
        )
    except ValueError:
        return "unavailable"
    return "active" if approval["review_basis"] == current_basis else "stale"


def checkpoint_approval_recorded(*, workspace: Path, checkpoint: str) -> bool:
    """Return whether one Checkpoint has current artifact-bound approval."""

    return checkpoint_approval_status(workspace=workspace, checkpoint=checkpoint) == "active"


def checkpoint_completion_approval_issue(*, workspace: Path, row: dict[str, Any]) -> str:
    """Explain why a HUMAN Checkpoint cannot be completed against current Artifacts."""

    owner = str(row.get("owner") or "").strip().upper()
    skill = str(row.get("skill") or "").strip()
    checkpoint = str(row.get("checkpoint") or "").strip()
    if (owner != "HUMAN" and skill != "human-checkpoint") or not checkpoint:
        return ""
    readable_approval = decisions_has_approval(workspace / "DECISIONS.md", checkpoint)
    approval_status = checkpoint_approval_status(workspace=workspace, checkpoint=checkpoint)
    if readable_approval and approval_status == "active":
        return ""
    detail = {
        "legacy": " The existing approval predates artifact-bound review and must be recorded again.",
        "stale": " The reviewed Artifacts changed after approval and must be reviewed again.",
        "unavailable": " The current Unit contract does not expose a complete review basis.",
        "missing": " No durable artifact-bound approval is recorded.",
    }.get(approval_status, "")
    if not readable_approval:
        detail += " The readable approval checkbox is not checked."
    return (
        f"Checkpoint {checkpoint} requires an active approval bound to the current review Artifacts."
        f"{detail}"
    )


def revoke_checkpoint_approval(
    *,
    workspace: Path,
    checkpoint: str,
    actor_id: str,
    note: str,
) -> bool:
    """Clear stale readable approval and append one durable revocation Decision."""

    checkpoint = str(checkpoint or "").strip()
    if not checkpoint:
        return False
    readable_approval = decisions_has_approval(workspace / "DECISIONS.md", checkpoint)
    approval_status = checkpoint_approval_status(workspace=workspace, checkpoint=checkpoint)
    if not readable_approval and approval_status == "missing":
        return False
    set_decisions_approval(workspace / "DECISIONS.md", checkpoint, approved=False)
    record_decision(
        workspace=workspace,
        action="checkpoint.approval.revoked",
        subject=checkpoint,
        decision="revoked",
        actor={"kind": "harness", "id": actor_id},
        note=f"{note} Previous approval status: {approval_status}.",
    )
    return True


def record_completion_stage(
    *,
    workspace: Path,
    unit_id: str,
    attempt_id: str,
    stage: str,
    manifest_path: str,
    outputs: Iterable[str],
    recovered: bool = False,
    acceptance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if stage not in {"prepared", "committed"}:
        raise ValueError(f"Unsupported completion stage: {stage}")
    snapshot = _read_json_object(workspace / HARNESS_DIR / "run.json")
    payload: dict[str, Any] = {
        "manifest_path": manifest_path,
        "outputs": list(outputs),
        "recovered": recovered,
    }
    if isinstance(acceptance, dict):
        payload["acceptance"] = dict(acceptance)
    return _append_event(
        workspace=workspace,
        run_id=str(snapshot.get("run_id") or ""),
        event_type=f"unit.completion.{stage}",
        actor={"kind": "harness", "id": "completion-protocol"},
        unit_id=unit_id,
        attempt_id=attempt_id,
        payload=payload,
    )


def reconcile_run_state(*, workspace: Path) -> dict[str, Any]:
    """Reconcile mutable projections with durable Attempt and Manifest evidence."""

    run_path = workspace / HARNESS_DIR / "run.json"
    snapshot = _read_json_object(run_path)
    if not snapshot:
        return {}

    run_id = str(snapshot.get("run_id") or "")
    _recover_unannounced_prepared_manifests(workspace=workspace, run_id=run_id)
    _recover_prepared_completions(workspace=workspace, run_id=run_id)
    _recover_orphan_open_attempts(workspace=workspace)
    _ensure_attempt_events(workspace=workspace, run_id=run_id)
    recovered = _recover_successful_doing_units(workspace=workspace, run_id=run_id)
    attempts = _read_jsonl(workspace / HARNESS_DIR / "attempts.jsonl")
    finished_attempt_ids = {
        str(record.get("attempt_id") or "")
        for record in attempts
        if record.get("record_type") == "finished"
    }
    unit_status = {
        str(row.get("unit_id") or "").strip(): str(row.get("status") or "").strip().upper()
        for row in _load_units(workspace)
    }
    active_attempt_id = snapshot.get("active_attempt_id")
    current_unit_id = str(snapshot.get("current_unit_id") or "")
    if str(active_attempt_id or "") in finished_attempt_ids or unit_status.get(current_unit_id) != "DOING":
        active_attempt_id = None
        current_unit_id = ""

    previous_state = str(snapshot.get("state") or "")
    projected_state = _project_run_state(workspace)
    _update_run_snapshot(
        workspace=workspace,
        state=projected_state,
        active_attempt_id=active_attempt_id,
        current_unit_id=current_unit_id or None,
    )
    if projected_state == "COMPLETED" and previous_state != "COMPLETED":
        _append_event(
            workspace=workspace,
            run_id=str(snapshot.get("run_id") or ""),
            event_type="run.completed",
            actor={"kind": "harness", "id": "run-reconciler"},
            payload={"unit_status": _unit_status_counts(workspace), "recovered_units": recovered},
        )
        _update_run_snapshot(workspace=workspace, state="COMPLETED")
    return _read_json_object(run_path)


def _recover_unannounced_prepared_manifests(*, workspace: Path, run_id: str) -> list[str]:
    """Recover the write boundary between a PREPARED Manifest and its Event."""

    units = {
        str(row.get("unit_id") or "").strip(): row
        for row in _load_units(workspace)
    }
    attempts = _read_jsonl(workspace / HARNESS_DIR / "attempts.jsonl")
    starts = {
        str(record.get("attempt_id") or ""): record
        for record in attempts
        if record.get("record_type") == "started"
    }
    finishes = {
        str(record.get("attempt_id") or ""): record
        for record in attempts
        if record.get("record_type") == "finished"
    }
    latest_started_by_unit: dict[str, str] = {}
    for record in attempts:
        if record.get("record_type") != "started":
            continue
        unit_id = str(record.get("unit_id") or "")
        attempt_id = str(record.get("attempt_id") or "")
        if unit_id and attempt_id:
            latest_started_by_unit[unit_id] = attempt_id
    announced_attempt_ids = {
        str(event.get("attempt_id") or "")
        for event in _read_jsonl(workspace / HARNESS_DIR / "events.jsonl")
        if event.get("type") == "unit.completion.prepared"
    }
    recovered: list[str] = []
    for path in sorted((workspace / "output" / "unit_logs").glob("*.manifest.json")):
        manifest = _read_json_object(path)
        if str(manifest.get("status") or "").upper() != "PREPARED":
            continue
        attempt_id = str(manifest.get("attempt_id") or "")
        unit_id = str(manifest.get("unit_id") or "")
        started = starts.get(attempt_id)
        finished = finishes.get(attempt_id)
        row = units.get(unit_id)
        if (
            not attempt_id
            or attempt_id in announced_attempt_ids
            or started is None
            or row is None
            or latest_started_by_unit.get(unit_id) != attempt_id
        ):
            continue
        if finished is not None and str(finished.get("status") or "") != "SUCCEEDED":
            continue
        if (
            str(manifest.get("run_id") or "") != run_id
            or str(started.get("run_id") or "") != run_id
            or str(started.get("unit_id") or "") != unit_id
            or str(started.get("skill") or "") != str(manifest.get("skill") or "")
            or str(row.get("status") or "").strip().upper() not in {"DOING", "DONE"}
            or not _manifest_matches_workspace(workspace=workspace, row=row, manifest=manifest)
        ):
            continue
        outputs = [
            str(item.get("path") or "")
            for item in manifest.get("outputs") or []
            if isinstance(item, dict) and str(item.get("path") or "")
        ]
        recovery_issues = _completion_recovery_acceptance_issues(
            workspace=workspace,
            row=row,
            manifest=manifest,
            manifest_path=path,
            outputs=outputs,
        )
        if recovery_issues:
            _block_recovery_acceptance_failure(
                workspace=workspace,
                row=row,
                attempt_id=attempt_id,
                manifest_path=str(path.relative_to(workspace)),
                issues=recovery_issues,
            )
            continue
        record_completion_stage(
            workspace=workspace,
            unit_id=unit_id,
            attempt_id=attempt_id,
            stage="prepared",
            manifest_path=str(path.relative_to(workspace)),
            outputs=outputs,
            recovered=True,
            acceptance=(
                manifest.get("acceptance")
                if isinstance(manifest.get("acceptance"), dict)
                else None
            ),
        )
        announced_attempt_ids.add(attempt_id)
        recovered.append(attempt_id)
    return recovered


def _recover_prepared_completions(*, workspace: Path, run_id: str) -> list[str]:
    """Finish a completion transaction that crashed after its PREPARED Manifest."""

    units = {
        str(row.get("unit_id") or "").strip(): row
        for row in _load_units(workspace)
    }
    attempts = _read_jsonl(workspace / HARNESS_DIR / "attempts.jsonl")
    starts = {
        str(record.get("attempt_id") or ""): record
        for record in attempts
        if record.get("record_type") == "started"
    }
    finishes = {
        str(record.get("attempt_id") or ""): record
        for record in attempts
        if record.get("record_type") == "finished"
    }
    latest_started_by_unit: dict[str, str] = {}
    for record in attempts:
        if record.get("record_type") != "started":
            continue
        unit_id = str(record.get("unit_id") or "")
        attempt_id = str(record.get("attempt_id") or "")
        if unit_id and attempt_id:
            latest_started_by_unit[unit_id] = attempt_id
    events = _read_jsonl(workspace / HARNESS_DIR / "events.jsonl")
    committed_attempt_ids = {
        str(event.get("attempt_id") or "")
        for event in events
        if event.get("type") == "unit.completion.committed"
    }
    recovered: list[str] = []
    for event in events:
        if event.get("type") != "unit.completion.prepared":
            continue
        attempt_id = str(event.get("attempt_id") or "")
        unit_id = str(event.get("unit_id") or "")
        row = units.get(unit_id)
        started = starts.get(attempt_id)
        if (
            not attempt_id
            or attempt_id in committed_attempt_ids
            or row is None
            or started is None
            or latest_started_by_unit.get(unit_id) != attempt_id
        ):
            continue
        unit_status = str(row.get("status") or "").strip().upper()
        if unit_status not in {"DOING", "DONE"}:
            continue
        if str(started.get("run_id") or "") != run_id or str(started.get("unit_id") or "") != unit_id:
            continue

        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        manifest_relpath = str(payload.get("manifest_path") or "")
        manifest_path = (workspace / manifest_relpath).resolve()
        try:
            manifest_path.relative_to(workspace.resolve())
        except ValueError:
            continue
        manifest = _read_json_object(manifest_path)
        if str(manifest.get("status") or "").upper() not in {"PREPARED", "DONE"}:
            continue
        if (
            str(manifest.get("run_id") or "") != run_id
            or str(manifest.get("attempt_id") or "") != attempt_id
            or str(manifest.get("unit_id") or "") != unit_id
            or not _manifest_matches_workspace(workspace=workspace, row=row, manifest=manifest)
        ):
            continue

        finished = finishes.get(attempt_id)
        if finished is not None and str(finished.get("status") or "") != "SUCCEEDED":
            continue
        outputs = [
            str(item.get("path") or "")
            for item in manifest.get("outputs") or []
            if isinstance(item, dict) and str(item.get("path") or "")
        ]
        recovery_acceptance_issues = _completion_recovery_acceptance_issues(
            workspace=workspace,
            row=row,
            manifest=manifest,
            manifest_path=manifest_path,
            outputs=outputs,
            event_acceptance=(
                payload.get("acceptance")
                if isinstance(payload.get("acceptance"), dict)
                else None
            ),
            require_event_match=True,
        )
        if recovery_acceptance_issues:
            _block_recovery_acceptance_failure(
                workspace=workspace,
                row=row,
                attempt_id=attempt_id,
                manifest_path=manifest_relpath,
                issues=recovery_acceptance_issues,
            )
            continue
        if finished is None:
            finish_attempt(
                workspace=workspace,
                attempt_id=attempt_id,
                unit_id=unit_id,
                skill=str(started.get("skill") or ""),
                status="SUCCEEDED",
                exit_code=manifest.get("exit_code") if isinstance(manifest.get("exit_code"), int) else 0,
                outputs=outputs,
                message="Recovered a prepared completion transaction.",
            )
            finished = next(
                (
                    record
                    for record in reversed(_read_jsonl(workspace / HARNESS_DIR / "attempts.jsonl"))
                    if record.get("record_type") == "finished"
                    and str(record.get("attempt_id") or "") == attempt_id
                ),
                None,
            )
        if finished is None or not _attempt_artifacts_match_manifest(
            workspace=workspace,
            attempt_id=attempt_id,
            finished=finished,
            manifest=manifest,
        ):
            continue
        if str(manifest.get("status") or "").upper() != "DONE":
            manifest["status"] = "DONE"
            manifest["finalized_at"] = now_iso_seconds()
            _write_json(manifest_path, manifest)
        if unit_status == "DONE" and attempt_id not in committed_attempt_ids:
            record_completion_stage(
                workspace=workspace,
                unit_id=unit_id,
                attempt_id=attempt_id,
                stage="committed",
                manifest_path=manifest_relpath,
                outputs=outputs,
                recovered=True,
                acceptance=(
                    manifest.get("acceptance")
                    if isinstance(manifest.get("acceptance"), dict)
                    else None
                ),
            )
            committed_attempt_ids.add(attempt_id)
        recovered.append(attempt_id)
    return recovered


def _ensure_attempt_events(*, workspace: Path, run_id: str) -> None:
    """Backfill transition Events when a process stopped after an Attempt record append."""

    events = _read_jsonl(workspace / HARNESS_DIR / "events.jsonl")
    observed = {
        (str(event.get("attempt_id") or ""), str(event.get("type") or ""))
        for event in events
        if str(event.get("attempt_id") or "")
    }
    for record in _read_jsonl(workspace / HARNESS_DIR / "attempts.jsonl"):
        attempt_id = str(record.get("attempt_id") or "")
        unit_id = str(record.get("unit_id") or "")
        if not attempt_id:
            continue
        if record.get("record_type") == "started":
            event_type = "unit.attempt.started"
            payload = {"inputs": list(record.get("inputs") or []), "recovered": True}
        elif record.get("record_type") == "finished":
            event_type = _attempt_terminal_event_type(str(record.get("status") or ""))
            payload = {
                "status": str(record.get("status") or ""),
                "exit_code": record.get("exit_code"),
                "message": str(record.get("message") or ""),
                "recovered": True,
            }
            execution = _normalize_attempt_execution(
                record.get("execution") if isinstance(record.get("execution"), dict) else None
            )
            if execution:
                payload["execution"] = execution
        else:
            continue
        if (attempt_id, event_type) in observed:
            continue
        _append_event(
            workspace=workspace,
            run_id=run_id,
            event_type=event_type,
            actor={"kind": "harness", "id": "run-reconciler"},
            unit_id=unit_id,
            attempt_id=attempt_id,
            payload=payload,
        )
        observed.add((attempt_id, event_type))


def record_recovered_interruption(*, workspace: Path, repo_root: Path, unit_id: str) -> None:
    snapshot = _read_json_object(workspace / HARNESS_DIR / "run.json")
    active_attempt_id = str(snapshot.get("active_attempt_id") or "")
    started = open_attempt_for_unit(workspace=workspace, unit_id=unit_id)
    if started and active_attempt_id and str(started.get("attempt_id") or "") != active_attempt_id:
        active_record = next(
            (
                record
                for record in _read_jsonl(workspace / HARNESS_DIR / "attempts.jsonl")
                if record.get("record_type") == "started"
                and str(record.get("attempt_id") or "") == active_attempt_id
                and str(record.get("unit_id") or "") == unit_id
            ),
            None,
        )
        if active_record is not None:
            started = active_record
    if not started:
        row = next(
            (record for record in _load_units(workspace) if str(record.get("unit_id") or "") == unit_id),
            {},
        )
        skill = str(row.get("skill") or "unknown")
        attempt_id = start_attempt(
            workspace=workspace,
            repo_root=repo_root,
            unit_id=unit_id,
            skill=skill,
            inputs=parse_semicolon_list(row.get("inputs")),
            execution_mode="recovery",
        )
    else:
        attempt_id = str(started.get("attempt_id") or "")
        skill = str(started.get("skill") or "unknown")
    finish_attempt(
        workspace=workspace,
        attempt_id=attempt_id,
        unit_id=unit_id,
        skill=skill,
        status="INTERRUPTED",
        exit_code=None,
        message="Recovered stale DOING state from a previous process.",
    )


def recover_stale_doing_units(
    table: UnitsTable,
    *,
    eligible_unit_ids: set[str] | None = None,
) -> list[str]:
    """Move the first resumable stale `DOING` Unit back into the runnable queue.

    Eligibility is computed separately from process ownership. Recover only one
    Unit per reconciliation so the transition remains auditable and downstream
    state is not rewritten speculatively.
    """

    status_ok = {"DONE", "SKIP"}
    unit_by_id = {row.get("unit_id", ""): row for row in table.rows}
    for row in table.rows:
        if row.get("status", "").strip().upper() != "DOING":
            continue
        unit_id = row.get("unit_id", "").strip()
        if eligible_unit_ids is not None and unit_id not in eligible_unit_ids:
            continue
        deps = parse_semicolon_list(row.get("depends_on"))
        if any(
            not (dep := unit_by_id.get(dep_id))
            or dep.get("status", "").strip().upper() not in status_ok
            for dep_id in deps
        ):
            return []
        row["status"] = "BLOCKED"
        return [unit_id] if unit_id else []
    return []


def _stale_doing_unit_ids(*, workspace: Path, table: UnitsTable) -> set[str]:
    """Identify DOING Units whose process-scoped Attempt owner no longer exists."""

    records = _read_jsonl(workspace / HARNESS_DIR / "attempts.jsonl")
    finished_ids = {
        str(record.get("attempt_id") or "")
        for record in records
        if record.get("record_type") == "finished"
    }
    open_by_unit: dict[str, dict[str, Any]] = {}
    for record in reversed(records):
        attempt_id = str(record.get("attempt_id") or "")
        unit_id = str(record.get("unit_id") or "")
        if (
            record.get("record_type") == "started"
            and attempt_id
            and attempt_id not in finished_ids
            and unit_id
            and unit_id not in open_by_unit
        ):
            open_by_unit[unit_id] = record

    stale: set[str] = set()
    current_host = socket.gethostname()
    for row in table.rows:
        if str(row.get("status") or "").strip().upper() != "DOING":
            continue
        unit_id = str(row.get("unit_id") or "").strip()
        attempt = open_by_unit.get(unit_id)
        if attempt is None:
            continue
        if str(attempt.get("execution_mode") or "") != "process":
            continue
        if str(attempt.get("owner_host") or "") != current_host:
            continue
        try:
            pid = int(attempt.get("owner_pid"))
        except (TypeError, ValueError):
            continue
        if not _process_is_alive(pid):
            stale.add(unit_id)
    return stale


def _process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _recover_orphan_open_attempts(*, workspace: Path) -> list[str]:
    """Close an open Attempt whose Unit no longer projects active execution."""

    unit_rows = {
        str(row.get("unit_id") or "").strip(): row
        for row in _load_units(workspace)
        if str(row.get("unit_id") or "").strip()
    }
    records = _read_jsonl(workspace / HARNESS_DIR / "attempts.jsonl")
    finished_ids = {
        str(record.get("attempt_id") or "")
        for record in records
        if record.get("record_type") == "finished"
    }
    recovered: list[str] = []
    for record in records:
        if record.get("record_type") != "started":
            continue
        attempt_id = str(record.get("attempt_id") or "")
        unit_id = str(record.get("unit_id") or "")
        row = unit_rows.get(unit_id, {})
        unit_status = str(row.get("status") or "").strip().upper()
        if not attempt_id or attempt_id in finished_ids or unit_status == "DOING":
            continue
        finish_attempt(
            workspace=workspace,
            attempt_id=attempt_id,
            unit_id=unit_id,
            skill=str(record.get("skill") or ""),
            status="INTERRUPTED",
            exit_code=None,
            outputs=(),
            message=(
                "Reconciled an open Attempt after its Unit projection changed "
                f"to {unit_status or '<missing>'}."
            ),
        )
        finished_ids.add(attempt_id)
        recovered.append(attempt_id)
    return recovered


def _recover_successful_doing_units(*, workspace: Path, run_id: str) -> list[str]:
    units_path = workspace / "UNITS.csv"
    if not units_path.exists():
        return []
    try:
        table = UnitsTable.load(units_path)
    except Exception:
        return []

    attempts = _read_jsonl(workspace / HARNESS_DIR / "attempts.jsonl")
    latest_started_by_unit: dict[str, str] = {}
    successful_attempts: dict[str, dict[str, Any]] = {}
    for record in attempts:
        unit_id = str(record.get("unit_id") or "")
        attempt_id = str(record.get("attempt_id") or "")
        if record.get("record_type") == "started" and unit_id and attempt_id:
            latest_started_by_unit[unit_id] = attempt_id
        if record.get("record_type") == "finished" and record.get("status") == "SUCCEEDED" and attempt_id:
            successful_attempts[attempt_id] = record

    manifests: dict[str, tuple[dict[str, Any], str]] = {}
    for path in sorted((workspace / "output" / "unit_logs").glob("*.manifest.json")):
        payload = _read_json_object(path)
        attempt_id = str(payload.get("attempt_id") or "")
        if attempt_id and str(payload.get("status") or "").upper() == "DONE":
            manifests[attempt_id] = (payload, str(path.relative_to(workspace)))

    recovered: list[tuple[str, str, str, list[str], dict[str, Any] | None]] = []
    for row in table.rows:
        if str(row.get("status") or "").strip().upper() != "DOING":
            continue
        unit_id = str(row.get("unit_id") or "").strip()
        attempt_id = latest_started_by_unit.get(unit_id, "")
        finished = successful_attempts.get(attempt_id)
        manifest_entry = manifests.get(attempt_id)
        if not attempt_id or not finished or not manifest_entry:
            continue
        manifest, manifest_relpath = manifest_entry
        if str(finished.get("run_id") or "") != run_id or str(manifest.get("run_id") or "") != run_id:
            continue
        if str(finished.get("unit_id") or "") != unit_id or str(manifest.get("unit_id") or "") != unit_id:
            continue
        if not _manifest_matches_workspace(workspace=workspace, row=row, manifest=manifest):
            continue
        if not _attempt_artifacts_match_manifest(
            workspace=workspace,
            attempt_id=attempt_id,
            finished=finished,
            manifest=manifest,
        ):
            continue
        recovery_issues = _completion_recovery_acceptance_issues(
            workspace=workspace,
            row=row,
            manifest=manifest,
            manifest_path=workspace / manifest_relpath,
            outputs=[
                str(item.get("path") or "")
                for item in manifest.get("outputs") or []
                if isinstance(item, dict) and str(item.get("path") or "")
            ],
        )
        if recovery_issues:
            _block_recovery_acceptance_failure(
                workspace=workspace,
                row=row,
                attempt_id=attempt_id,
                manifest_path=manifest_relpath,
                issues=recovery_issues,
            )
            continue
        row["status"] = "DONE"
        recovered.append(
            (
                unit_id,
                attempt_id,
                manifest_relpath,
                [str(item.get("path") or "") for item in manifest.get("outputs") or [] if isinstance(item, dict)],
                (
                    dict(manifest["acceptance"])
                    if isinstance(manifest.get("acceptance"), dict)
                    else None
                ),
            )
        )

    if not recovered:
        return []
    table.save(units_path)
    for unit_id, attempt_id, manifest_relpath, outputs, acceptance in recovered:
        _append_event(
            workspace=workspace,
            run_id=run_id,
            event_type="unit.completion.recovered",
            actor={"kind": "harness", "id": "run-reconciler"},
            unit_id=unit_id,
            attempt_id=attempt_id,
            payload={"manifest_path": manifest_relpath, "outputs": outputs},
        )
        record_completion_stage(
            workspace=workspace,
            unit_id=unit_id,
            attempt_id=attempt_id,
            stage="committed",
            manifest_path=manifest_relpath,
            outputs=outputs,
            recovered=True,
            acceptance=acceptance,
        )
        update_status_log(
            workspace / "STATUS.md",
            f"{now_iso_seconds()} {unit_id} DONE (recovered successful completion {attempt_id})",
        )
    return [unit_id for unit_id, _, _, _, _ in recovered]


def _completion_recovery_acceptance_issues(
    *,
    workspace: Path,
    row: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path,
    outputs: list[str],
    event_acceptance: dict[str, Any] | None = None,
    require_event_match: bool = False,
) -> list[str]:
    """Fail closed when recovery cannot re-establish mandatory acceptance."""

    from tooling.quality_gate import (
        check_completion_acceptance,
        completion_check_required,
        write_quality_report,
    )

    skill = str(row.get("skill") or "").strip()
    issues: list[str] = []
    approval_issue = checkpoint_completion_approval_issue(workspace=workspace, row=row)
    if approval_issue:
        issues.append(approval_issue)
    if not completion_check_required(skill=skill, workspace=workspace):
        return issues
    checker_issues = check_completion_acceptance(
        skill=skill,
        workspace=workspace,
        outputs=outputs,
    )
    recorded_protocol = _recorded_completion_protocol(workspace)
    manifest_acceptance = manifest.get("acceptance")
    if (
        not isinstance(manifest_acceptance, dict)
        and recorded_protocol in MIGRATABLE_COMPLETION_PROTOCOLS
        and not checker_issues
    ):
        try:
            report_path = write_quality_report(
                workspace=workspace,
                unit_id=str(row.get("unit_id") or ""),
                skill=skill,
                issues=[],
            )
        except Exception as exc:
            issues.append(
                "Legacy acceptance evidence could not be migrated because the quality "
                f"report failed: {type(exc).__name__}: {exc}"
            )
        else:
            manifest_acceptance = {
                "required": True,
                "skill": skill,
                "status": "PASS",
                "report_path": str(report_path.relative_to(workspace)),
                "issue_codes": [],
                "migrated_from": recorded_protocol,
            }
            manifest["acceptance"] = manifest_acceptance
            _write_json(manifest_path, manifest)
    if not isinstance(manifest_acceptance, dict):
        issues.append("DONE recovery requires acceptance evidence in the prepared Manifest.")
    else:
        if manifest_acceptance.get("required") is not True:
            issues.append("Prepared Manifest does not mark Workflow acceptance as required.")
        if str(manifest_acceptance.get("status") or "").strip().upper() != "PASS":
            issues.append("Prepared Manifest does not record a PASS acceptance result.")
        if str(manifest_acceptance.get("skill") or "").strip() != skill:
            issues.append("Prepared Manifest acceptance evidence names a different Skill.")
    legacy_event_without_acceptance = (
        recorded_protocol in MIGRATABLE_COMPLETION_PROTOCOLS
        and event_acceptance is None
    )
    if (
        require_event_match
        and manifest_acceptance != event_acceptance
        and not legacy_event_without_acceptance
    ):
        issues.append("Prepared Manifest and Completion Event acceptance evidence disagree.")
    if checker_issues:
        try:
            write_quality_report(
                workspace=workspace,
                unit_id=str(row.get("unit_id") or ""),
                skill=skill,
                issues=checker_issues,
            )
        except Exception as exc:
            issues.append(
                f"Recovery quality report failed: {type(exc).__name__}: {exc}"
            )
    issues.extend(f"{issue.code}: {issue.message}" for issue in checker_issues)
    return issues


def _recorded_completion_protocol(workspace: Path) -> str:
    lock = _read_json_object(workspace / HARNESS_DIR / "harness.lock.json")
    protocols = lock.get("protocols") if isinstance(lock.get("protocols"), dict) else {}
    return str(protocols.get("completion") or "unversioned")


def _block_recovery_acceptance_failure(
    *,
    workspace: Path,
    row: dict[str, Any],
    attempt_id: str,
    manifest_path: str,
    issues: list[str],
) -> None:
    """Turn an unrecoverable Completion proof gap into durable repair evidence."""

    unit_id = str(row.get("unit_id") or "").strip()
    skill = str(row.get("skill") or "").strip()
    checkpoint = str(row.get("checkpoint") or "").strip()
    symptom = "; ".join(issues[:3]) or "Completion acceptance could not be recovered."
    if checkpoint_completion_approval_issue(workspace=workspace, row=row):
        revoke_checkpoint_approval(
            workspace=workspace,
            checkpoint=checkpoint,
            actor_id="completion-reconciler",
            note=f"Revoked while recovery blocked {unit_id}: {symptom}",
        )
    record_failure(
        workspace=workspace,
        unit_id=unit_id,
        attempt_id=attempt_id,
        failure_type="acceptance_recovery_failed",
        symptom=symptom,
        causal_behavior="Recovery could not re-establish the Workflow acceptance proof required for DONE.",
        harness_mechanism="Completion recovery fails closed and preserves a bounded repair surface.",
        repair_surface=[manifest_path, "output/QUALITY_GATE.md", f".codex/skills/{skill}/SKILL.md"],
        severity="high",
    )
    row["status"] = "BLOCKED"
    table = UnitsTable.load(workspace / "UNITS.csv")
    for candidate in table.rows:
        if str(candidate.get("unit_id") or "").strip() == unit_id:
            candidate["status"] = "BLOCKED"
            break
    table.save(workspace / "UNITS.csv")
    open_attempt = open_attempt_for_unit(workspace=workspace, unit_id=unit_id)
    if open_attempt and str(open_attempt.get("attempt_id") or "") == attempt_id:
        finish_attempt(
            workspace=workspace,
            attempt_id=attempt_id,
            unit_id=unit_id,
            skill=skill,
            status="FAILED_RETRYABLE",
            exit_code=2,
            outputs=(),
            message=symptom,
        )
    update_status_log(
        workspace / "STATUS.md",
        f"{now_iso_seconds()} {unit_id} BLOCKED (acceptance recovery failed)",
    )


def _manifest_matches_workspace(*, workspace: Path, row: dict[str, str], manifest: dict[str, Any]) -> bool:
    outputs = manifest.get("outputs") if isinstance(manifest.get("outputs"), list) else []
    by_path = {
        str(item.get("path") or ""): item
        for item in outputs
        if isinstance(item, dict) and str(item.get("path") or "")
    }
    for raw_path in parse_semicolon_list(row.get("outputs")):
        if raw_path.strip().startswith("?"):
            continue
        relpath = raw_path.strip().lstrip("?").strip()
        if not relpath or relpath not in by_path:
            return False
        path = workspace / relpath
        record = by_path[relpath]
        if not path.exists() or record.get("exists") is False:
            return False
        expected_sha = str(record.get("sha256") or "")
        if expected_sha and _path_fingerprint(path).get("sha256") != expected_sha:
            return False
    return True


def _attempt_artifacts_match_manifest(
    *,
    workspace: Path,
    attempt_id: str,
    finished: dict[str, Any],
    manifest: dict[str, Any],
) -> bool:
    declared_artifact_ids = {str(item) for item in finished.get("artifact_ids") or []}
    artifacts = [
        record
        for record in _read_jsonl(workspace / HARNESS_DIR / "artifacts.jsonl")
        if str(record.get("attempt_id") or "") == attempt_id
        and str(record.get("artifact_id") or "") in declared_artifact_ids
    ]
    by_path = {str(record.get("path") or ""): record for record in artifacts}
    for output in manifest.get("outputs") or []:
        if not isinstance(output, dict) or output.get("exists") is False:
            continue
        relpath = str(output.get("path") or "")
        artifact = by_path.get(relpath)
        if not relpath or artifact is None:
            return False
        manifest_sha = str(output.get("sha256") or "")
        artifact_sha = str(artifact.get("sha256") or "")
        if manifest_sha and manifest_sha != artifact_sha:
            return False
    return True


def run_identity(workspace: Path) -> dict[str, Any]:
    run = _read_json_object(workspace / HARNESS_DIR / "run.json")
    lock = _read_json_object(workspace / HARNESS_DIR / "harness.lock.json")
    repository = lock.get("repository") if isinstance(lock.get("repository"), dict) else {}
    protocols = lock.get("protocols") if isinstance(lock.get("protocols"), dict) else {}
    return {
        "run_id": str(run.get("run_id") or ""),
        "goal_id": str(run.get("goal_id") or ""),
        "state": str(run.get("state") or ""),
        "workflow": str(run.get("workflow") or ""),
        "harness_revision": str(repository.get("revision") or ""),
        "completion_protocol": str(protocols.get("completion") or "unversioned"),
    }


def inspect_doing_attempt_integrity(
    workspace: Path,
    *,
    unit_rows: Iterable[dict[str, Any]] | None = None,
    attempt_records: Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Report DOING projections that have no unique open Attempt evidence."""

    rows = list(unit_rows) if unit_rows is not None else _load_units(workspace)
    records = (
        list(attempt_records)
        if attempt_records is not None
        else _read_jsonl(workspace / HARNESS_DIR / "attempts.jsonl")
    )
    finished_ids = {
        str(record.get("attempt_id") or "")
        for record in records
        if record.get("record_type") == "finished"
    }
    open_by_unit: dict[str, list[str]] = {}
    for record in records:
        attempt_id = str(record.get("attempt_id") or "")
        unit_id = str(record.get("unit_id") or "")
        if (
            record.get("record_type") == "started"
            and attempt_id
            and attempt_id not in finished_ids
            and unit_id
        ):
            open_by_unit.setdefault(unit_id, []).append(attempt_id)

    issues: list[dict[str, str]] = []
    for row in rows:
        if str(row.get("status") or "").strip().upper() != "DOING":
            continue
        unit_id = str(row.get("unit_id") or "").strip() or "<missing>"
        open_attempt_ids = open_by_unit.get(unit_id, [])
        if not open_attempt_ids:
            issues.append(
                {
                    "level": "ERROR",
                    "code": "doing_without_open_attempt",
                    "message": f"DOING Unit `{unit_id}` has no open Attempt; ownership cannot be inferred safely.",
                }
            )
        elif len(open_attempt_ids) > 1:
            issues.append(
                {
                    "level": "ERROR",
                    "code": "doing_with_multiple_open_attempts",
                    "message": (
                        f"DOING Unit `{unit_id}` has multiple open Attempts: "
                        f"{', '.join(open_attempt_ids)}."
                    ),
                }
            )
    return issues


def inspect_run_integrity(workspace: Path, *, repo_root: Path | None = None) -> dict[str, Any]:
    """Check referential integrity across the durable Run evidence ledgers."""

    harness_dir = workspace / HARNESS_DIR
    run = _read_json_object(harness_dir / "run.json")
    lock = _read_json_object(harness_dir / "harness.lock.json")
    if not run:
        return {
            "enabled": False,
            "run_id": "",
            "kernel_lock": inspect_kernel_lock(workspace=workspace, repo_root=repo_root),
            "ledger_record_counts": {},
            "attempt_summary": _summarize_attempt_records(()),
            "completion_acceptance_by_attempt": {},
            "compatibility": _completion_protocol_compatibility(lock=lock, issue_codes=()),
            "issue_count": 0,
            "issues": [],
        }

    run_id = str(run.get("run_id") or "")
    kernel_lock = inspect_kernel_lock(workspace=workspace, repo_root=repo_root)
    issues: list[dict[str, str]] = []
    seen_issues: set[tuple[str, str]] = set()

    def add(level: str, code: str, message: str) -> None:
        key = (code, message)
        if key in seen_issues:
            return
        seen_issues.add(key)
        issues.append({"level": level, "code": code, "message": message})

    if kernel_lock["status"] == "DRIFT" and str(run.get("state") or "").upper() != "COMPLETED":
        affected = [
            *kernel_lock["missing_paths"],
            *kernel_lock["unexpected_paths"],
            *kernel_lock["drifted_paths"],
        ]
        add(
            "ERROR",
            "harness_kernel_drift",
            "Active Run no longer matches its pinned Harness Kernel: "
            + (", ".join(affected) if affected else "invalid v2 Kernel manifest"),
        )

    protocols = lock.get("protocols") if isinstance(lock.get("protocols"), dict) else {}
    recorded_completion_protocol = str(protocols.get("completion") or "unversioned")
    if recorded_completion_protocol not in {
        COMPLETION_PROTOCOL,
        "unversioned",
        *MIGRATABLE_COMPLETION_PROTOCOLS,
    }:
        add(
            "ERROR",
            "unknown_completion_protocol",
            (
                f"Run declares unsupported Completion Protocol `{recorded_completion_protocol}`; "
                "this Harness cannot validate its completion evidence safely."
            ),
        )

    ledger_paths = {
        "events": harness_dir / "events.jsonl",
        "attempts": harness_dir / "attempts.jsonl",
        "artifacts": harness_dir / "artifacts.jsonl",
        "decisions": harness_dir / "decisions.jsonl",
        "failures": harness_dir / "failures" / "ledger.jsonl",
        "evaluations": harness_dir / "evaluations" / "ledger.jsonl",
    }
    ledgers: dict[str, list[dict[str, Any]]] = {}
    for name, path in ledger_paths.items():
        records, malformed_lines = read_jsonl_with_errors(path)
        ledgers[name] = records
        for line_number in malformed_lines:
            add("ERROR", "malformed_ledger_record", f"`{path.relative_to(workspace)}` line {line_number} is not valid JSON.")
        for index, record in enumerate(records, start=1):
            record_run_id = str(record.get("run_id") or "")
            if record_run_id and record_run_id != run_id:
                add(
                    "ERROR",
                    "run_id_mismatch",
                    f"`{path.relative_to(workspace)}` record {index} belongs to `{record_run_id}`, expected `{run_id}`.",
                )

    for relpath in ("goal.json", "harness.lock.json"):
        payload = _read_json_object(harness_dir / relpath)
        payload_run_id = str(payload.get("run_id") or "")
        if payload and payload_run_id != run_id:
            add("ERROR", "run_id_mismatch", f"`.harness/{relpath}` belongs to `{payload_run_id}`, expected `{run_id}`.")

    if str(lock.get("schema") or "") == LOCK_SCHEMA:
        pipeline_lock = lock.get("pipeline") if isinstance(lock.get("pipeline"), dict) else {}
        snapshot_value = str(pipeline_lock.get("snapshot_path") or "").strip()
        source_value = str(pipeline_lock.get("path") or "").strip()
        declared_value = ""
        pipeline_projection = workspace / "PIPELINE.lock.md"
        if pipeline_projection.exists():
            for raw_line in pipeline_projection.read_text(encoding="utf-8", errors="ignore").splitlines():
                if raw_line.strip().startswith("pipeline:"):
                    declared_value = raw_line.split(":", 1)[1].strip()
                    break
        if source_value and declared_value != source_value:
            add(
                "ERROR",
                "pipeline_lock_projection_mismatch",
                f"`PIPELINE.lock.md` declares `{declared_value or '<missing>'}`, but the Harness lock binds `{source_value}`.",
            )
        if source_value or snapshot_value:
            inspection = inspect_pipeline_snapshot_bundle(
                workspace=workspace,
                pipeline_lock=pipeline_lock,
            )
            for issue in inspection.issues:
                add("ERROR", issue.code, issue.message)

    event_sequences = [record.get("seq") for record in ledgers["events"]]
    if event_sequences and event_sequences != list(range(1, len(event_sequences) + 1)):
        add("ERROR", "event_sequence_invalid", "`.harness/events.jsonl` sequence numbers are duplicated, missing, or out of order.")

    starts: dict[str, list[dict[str, Any]]] = {}
    finishes: dict[str, list[dict[str, Any]]] = {}
    for record in ledgers["attempts"]:
        attempt_id = str(record.get("attempt_id") or "")
        if not attempt_id:
            add("ERROR", "attempt_id_missing", "An Attempt record has no `attempt_id`.")
            continue
        target = starts if record.get("record_type") == "started" else finishes if record.get("record_type") == "finished" else None
        if target is None:
            add("ERROR", "attempt_record_type_invalid", f"Attempt `{attempt_id}` has invalid record_type `{record.get('record_type')}`.")
            continue
        target.setdefault(attempt_id, []).append(record)

    for attempt_id, records in starts.items():
        if len(records) != 1:
            add("ERROR", "attempt_start_duplicate", f"Attempt `{attempt_id}` has {len(records)} start records.")
    for attempt_id, records in finishes.items():
        if attempt_id not in starts:
            add("ERROR", "attempt_finish_orphan", f"Attempt `{attempt_id}` finished without a matching start record.")
        if len(records) != 1:
            add("ERROR", "attempt_finish_duplicate", f"Attempt `{attempt_id}` has {len(records)} finish records.")
        if attempt_id in starts:
            started = starts[attempt_id][-1]
            finished = records[-1]
            for field in ("run_id", "unit_id", "skill"):
                if str(started.get(field) or "") != str(finished.get(field) or ""):
                    add(
                        "ERROR",
                        "attempt_identity_mismatch",
                        f"Attempt `{attempt_id}` start and finish records disagree on `{field}`.",
                    )
            for message in _attempt_execution_validation_messages(finished.get("execution")):
                add(
                    "ERROR",
                    "attempt_execution_invalid",
                    f"Attempt `{attempt_id}` execution {message}.",
                )

    attempt_events = {
        (str(record.get("attempt_id") or ""), str(record.get("type") or "")): record
        for record in ledgers["events"]
        if str(record.get("attempt_id") or "")
    }
    committed_completion_events = {
        str(record.get("attempt_id") or ""): record
        for record in ledgers["events"]
        if record.get("type") == "unit.completion.committed"
        and str(record.get("attempt_id") or "")
    }
    observed_attempt_events = set(attempt_events)
    for attempt_id in starts:
        if (attempt_id, "unit.attempt.started") not in observed_attempt_events:
            add("ERROR", "attempt_start_event_missing", f"Attempt `{attempt_id}` has no started Event.")
    for attempt_id, records in finishes.items():
        event_type = _attempt_terminal_event_type(str(records[-1].get("status") or ""))
        if (attempt_id, event_type) not in observed_attempt_events:
            add("ERROR", "attempt_terminal_event_missing", f"Attempt `{attempt_id}` has no `{event_type}` Event.")
            continue
        event = attempt_events[(attempt_id, event_type)]
        event_payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        event_execution = event_payload.get("execution")
        for message in _attempt_execution_validation_messages(event_execution):
            add(
                "ERROR",
                "attempt_event_execution_invalid",
                f"Attempt `{attempt_id}` terminal Event execution {message}.",
            )
        attempt_execution = records[-1].get("execution")
        normalized_attempt = _normalize_attempt_execution(
            attempt_execution if isinstance(attempt_execution, dict) else None
        )
        normalized_event = _normalize_attempt_execution(
            event_execution if isinstance(event_execution, dict) else None
        )
        if normalized_attempt != normalized_event:
            add(
                "ERROR",
                "attempt_execution_event_mismatch",
                f"Attempt `{attempt_id}` and its `{event_type}` Event disagree on execution telemetry.",
            )

    units = {str(row.get("unit_id") or "").strip(): row for row in _load_units(workspace)}
    for record in inspect_doing_attempt_integrity(
        workspace,
        unit_rows=units.values(),
        attempt_records=ledgers["attempts"],
    ):
        add(str(record["level"]), str(record["code"]), str(record["message"]))
    for attempt_id, records in starts.items():
        if attempt_id in finishes:
            continue
        unit_id = str(records[-1].get("unit_id") or "")
        if str(units.get(unit_id, {}).get("status") or "").strip().upper() != "DOING":
            add("ERROR", "unfinished_attempt", f"Attempt `{attempt_id}` is unfinished but Unit `{unit_id}` is not DOING.")

    artifacts_by_id: dict[str, dict[str, Any]] = {}
    artifacts_by_attempt: dict[str, list[dict[str, Any]]] = {}
    for record in ledgers["artifacts"]:
        artifact_id = str(record.get("artifact_id") or "")
        attempt_id = str(record.get("attempt_id") or "")
        if not artifact_id:
            add("ERROR", "artifact_id_missing", "An Artifact record has no `artifact_id`.")
            continue
        if artifact_id in artifacts_by_id:
            add("ERROR", "artifact_id_duplicate", f"Artifact id `{artifact_id}` appears more than once.")
        artifacts_by_id[artifact_id] = record
        artifacts_by_attempt.setdefault(attempt_id, []).append(record)
        if attempt_id not in finishes:
            add("ERROR", "artifact_attempt_orphan", f"Artifact `{artifact_id}` references unfinished or missing Attempt `{attempt_id}`.")
        elif str(record.get("unit_id") or "") != str(finishes[attempt_id][-1].get("unit_id") or ""):
            add("ERROR", "artifact_unit_mismatch", f"Artifact `{artifact_id}` disagrees with Attempt `{attempt_id}` on Unit identity.")

    for attempt_id, records in finishes.items():
        finished = records[-1]
        for artifact_id in finished.get("artifact_ids") or []:
            artifact = artifacts_by_id.get(str(artifact_id))
            if artifact is None:
                add("ERROR", "attempt_artifact_missing", f"Attempt `{attempt_id}` references missing Artifact `{artifact_id}`.")
            elif str(artifact.get("attempt_id") or "") != attempt_id:
                add("ERROR", "attempt_artifact_mismatch", f"Artifact `{artifact_id}` does not belong to Attempt `{attempt_id}`.")

    manifests: list[dict[str, Any]] = []
    for path in sorted((workspace / "output" / "unit_logs").glob("*.manifest.json")):
        payload = _read_json_object(path)
        if not payload:
            add("ERROR", "manifest_invalid", f"`{path.relative_to(workspace)}` is not a valid Manifest object.")
            continue
        payload["_relpath"] = str(path.relative_to(workspace))
        manifests.append(payload)
        attempt_id = str(payload.get("attempt_id") or "")
        if str(payload.get("run_id") or "") != run_id:
            add("ERROR", "manifest_run_mismatch", f"`{path.relative_to(workspace)}` does not belong to Run `{run_id}`.")
        if not attempt_id:
            add("ERROR", "manifest_attempt_missing", f"`{path.relative_to(workspace)}` has no Attempt reference.")
            continue
        finished_records = finishes.get(attempt_id)
        if not finished_records:
            add("ERROR", "manifest_attempt_orphan", f"`{path.relative_to(workspace)}` references unfinished or missing Attempt `{attempt_id}`.")
            continue
        finished = finished_records[-1]
        if str(payload.get("unit_id") or "") != str(finished.get("unit_id") or ""):
            add("ERROR", "manifest_unit_mismatch", f"`{path.relative_to(workspace)}` disagrees with Attempt `{attempt_id}` on Unit identity.")
        manifest_status = str(payload.get("status") or "").upper()
        if manifest_status == "DONE" and str(finished.get("status") or "") != "SUCCEEDED":
            add("ERROR", "manifest_status_mismatch", f"DONE Manifest `{path.relative_to(workspace)}` points to non-successful Attempt `{attempt_id}`.")
        if manifest_status == "DONE":
            event = committed_completion_events.get(attempt_id, {})
            event_payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            manifest_acceptance = payload.get("acceptance")
            event_acceptance = event_payload.get("acceptance")
            if isinstance(manifest_acceptance, dict) != isinstance(event_acceptance, dict) or (
                isinstance(manifest_acceptance, dict)
                and isinstance(event_acceptance, dict)
                and manifest_acceptance != event_acceptance
            ):
                add(
                    "ERROR",
                    "completion_acceptance_mismatch",
                    f"DONE Manifest `{path.relative_to(workspace)}` and its committed Completion Event disagree on Workflow acceptance evidence.",
                )
        for output in payload.get("outputs") or []:
            if not isinstance(output, dict) or output.get("exists") is False:
                continue
            relpath = str(output.get("path") or "")
            if not relpath:
                continue
            artifact = next(
                (
                    candidate
                    for candidate in artifacts_by_attempt.get(attempt_id, [])
                    if str(candidate.get("path") or "") == relpath
                ),
                None,
            )
            if artifact is None:
                add(
                    "ERROR",
                    "manifest_artifact_missing",
                    f"Manifest `{path.relative_to(workspace)}` output `{relpath}` has no matching Artifact record.",
                )
                continue
            manifest_sha = str(output.get("sha256") or "")
            artifact_sha = str(artifact.get("sha256") or "")
            if manifest_sha and artifact_sha and manifest_sha != artifact_sha:
                add(
                    "ERROR",
                    "manifest_artifact_hash_mismatch",
                    f"Manifest `{path.relative_to(workspace)}` and Artifact `{artifact.get('artifact_id')}` disagree on `{relpath}` hash.",
                )

    successful_by_unit: dict[str, set[str]] = {}
    for attempt_id, records in finishes.items():
        finished = records[-1]
        if str(finished.get("status") or "") == "SUCCEEDED":
            successful_by_unit.setdefault(str(finished.get("unit_id") or ""), set()).add(attempt_id)
    done_manifests_by_unit: dict[str, list[dict[str, Any]]] = {}
    for manifest in manifests:
        if str(manifest.get("status") or "").upper() == "DONE":
            done_manifests_by_unit.setdefault(str(manifest.get("unit_id") or ""), []).append(manifest)

    declared_done_outputs: set[tuple[str, str]] = set()
    for unit_id, row in units.items():
        if str(row.get("status") or "").strip().upper() != "DONE":
            continue
        approval_issue = checkpoint_completion_approval_issue(workspace=workspace, row=row)
        if approval_issue:
            approval_status = checkpoint_approval_status(
                workspace=workspace,
                checkpoint=str(row.get("checkpoint") or "").strip(),
            )
            code = (
                "done_checkpoint_approval_stale"
                if approval_status == "stale"
                else "done_checkpoint_approval_invalid"
            )
            add("ERROR", code, f"DONE Unit `{unit_id}` is not currently approved: {approval_issue}")
        successful_attempts = successful_by_unit.get(unit_id, set())
        if not successful_attempts:
            add("ERROR", "done_without_successful_attempt", f"DONE Unit `{unit_id}` has no successful Attempt.")
        matching_manifests = [
            manifest
            for manifest in done_manifests_by_unit.get(unit_id, [])
            if str(manifest.get("attempt_id") or "") in successful_attempts
        ]
        if not matching_manifests:
            add("ERROR", "done_without_manifest", f"DONE Unit `{unit_id}` has no DONE Manifest tied to a successful Attempt.")
        for raw_path in parse_semicolon_list(row.get("outputs")):
            if raw_path.strip().startswith("?"):
                continue
            relpath = raw_path.strip().lstrip("?").strip()
            if not relpath:
                continue
            declared_done_outputs.add((unit_id, relpath))
            candidates = [
                artifact
                for artifact in ledgers["artifacts"]
                if str(artifact.get("attempt_id") or "") in successful_attempts
                and str(artifact.get("path") or "") == relpath
            ]
            if not candidates:
                add("ERROR", "done_output_unregistered", f"DONE Unit `{unit_id}` output `{relpath}` has no Artifact record from a successful Attempt.")

    # A reader-facing Artifact may have several declared producer/mutator Units
    # (for example section-merger -> citation-injector -> draft-polisher). Each
    # Unit still needs its own Manifest and matching Artifact record above, but
    # immutability must compare the current path with the latest successful
    # record across the whole Run. Comparing with every earlier producer makes
    # a legitimate downstream rewrite indistinguishable from post-completion
    # drift and prevents a naturally completed Run from auditing cleanly.
    done_unit_ids = {
        unit_id
        for unit_id, row in units.items()
        if str(row.get("status") or "").strip().upper() == "DONE"
    }
    successful_attempt_ids = {
        attempt_id
        for attempt_ids in successful_by_unit.values()
        for attempt_id in attempt_ids
    }
    latest_successful_artifact_by_path: dict[str, dict[str, Any]] = {}
    for artifact in ledgers["artifacts"]:
        relpath = str(artifact.get("path") or "").strip()
        if (
            relpath
            and str(artifact.get("attempt_id") or "") in successful_attempt_ids
            and str(artifact.get("unit_id") or "") in done_unit_ids
            and (str(artifact.get("unit_id") or ""), relpath) in declared_done_outputs
        ):
            latest_successful_artifact_by_path[relpath] = artifact

    for relpath, latest in latest_successful_artifact_by_path.items():
        path = workspace / relpath
        expected_sha = str(latest.get("sha256") or "")
        if relpath in MUTABLE_PROJECTION_PATHS or not path.exists() or not expected_sha:
            continue
        current_sha = str(_path_fingerprint(path).get("sha256") or "")
        if current_sha != expected_sha:
            add(
                "ERROR",
                "artifact_hash_mismatch",
                f"Current `{relpath}` no longer matches its latest successful Artifact record.",
            )

    for ledger_name in ("decisions", "failures", "evaluations"):
        for record in ledgers[ledger_name]:
            attempt_id = str(record.get("attempt_id") or "")
            if attempt_id and attempt_id not in starts:
                add("ERROR", f"{ledger_name[:-1]}_attempt_orphan", f"A {ledger_name[:-1]} record references missing Attempt `{attempt_id}`.")
            elif attempt_id:
                record_unit_id = str(record.get("unit_id") or "")
                started_unit_id = str(starts[attempt_id][-1].get("unit_id") or "")
                if record_unit_id and record_unit_id != started_unit_id:
                    add(
                        "ERROR",
                        f"{ledger_name[:-1]}_unit_mismatch",
                        f"A {ledger_name[:-1]} record disagrees with Attempt `{attempt_id}` on Unit identity.",
                    )
            resolved_by = str(record.get("resolved_by_attempt_id") or "")
            if resolved_by and not any(
                str(item.get("status") or "") == "SUCCEEDED" for item in finishes.get(resolved_by, [])
            ):
                add("ERROR", "failure_resolution_unverified", f"Failure resolution references non-successful Attempt `{resolved_by}`.")

    opened_failures = {
        str(record.get("failure_id") or ""): record
        for record in ledgers["failures"]
        if record.get("record_type") == "opened" and str(record.get("failure_id") or "")
    }
    for record in ledgers["failures"]:
        if record.get("record_type") != "resolved":
            continue
        failure_id = str(record.get("failure_id") or "")
        opened = opened_failures.get(failure_id)
        if opened is None:
            add("ERROR", "failure_resolution_orphan", f"Failure resolution `{failure_id}` has no matching opened record.")
            continue
        verification = record.get("verification") if isinstance(record.get("verification"), dict) else {}
        if verification.get("kind") != "successful_attempt":
            add("ERROR", "failure_resolution_unverified", f"Failure resolution `{failure_id}` has no successful-Attempt verification.")
        if str(verification.get("failure_type") or "") != str(opened.get("failure_type") or ""):
            add("ERROR", "failure_resolution_type_mismatch", f"Failure resolution `{failure_id}` did not verify its opened failure type.")

    compatibility = _completion_protocol_compatibility(
        lock=lock,
        issue_codes=(str(issue.get("code") or "") for issue in issues),
    )
    return {
        "enabled": True,
        "run_id": run_id,
        "kernel_lock": kernel_lock,
        "ledger_record_counts": {name: len(records) for name, records in ledgers.items()},
        "attempt_summary": _summarize_attempt_records(ledgers["attempts"]),
        "completion_acceptance_by_attempt": {
            attempt_id: dict(acceptance)
            for attempt_id, event in committed_completion_events.items()
            if isinstance(event.get("payload"), dict)
            and isinstance((acceptance := event["payload"].get("acceptance")), dict)
        },
        "compatibility": compatibility,
        "issue_count": len(issues),
        "issues": issues,
    }


def _summarize_attempt_records(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = list(records)
    starts = [record for record in items if record.get("record_type") == "started"]
    finishes = [record for record in items if record.get("record_type") == "finished"]
    finished_ids = {str(record.get("attempt_id") or "") for record in finishes}
    starts_by_unit = Counter(str(record.get("unit_id") or "") for record in starts)
    retry_counts = [count for unit_id, count in starts_by_unit.items() if unit_id and count > 1]

    statuses = Counter(str(record.get("status") or "UNKNOWN") for record in finishes)
    modes = Counter(str(record.get("execution_mode") or "legacy") for record in starts)
    measured: list[dict[str, Any]] = []
    for record in finishes:
        execution = record.get("execution")
        if not isinstance(execution, dict):
            continue
        elapsed_ms = execution.get("elapsed_ms")
        if (
            isinstance(elapsed_ms, (int, float))
            and not isinstance(elapsed_ms, bool)
            and elapsed_ms >= 0
        ):
            measured.append(execution)

    elapsed_values = [float(record["elapsed_ms"]) for record in measured]

    def measured_chars(record: dict[str, Any], key: str) -> int:
        value = record.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0

    return {
        "started": len(starts),
        "finished": len(finishes),
        "open": sum(
            1
            for record in starts
            if str(record.get("attempt_id") or "") not in finished_ids
        ),
        "retry_units": len(retry_counts),
        "extra_attempts": sum(count - 1 for count in retry_counts),
        "by_status": {status: statuses[status] for status in sorted(statuses)},
        "by_execution_mode": {mode: modes[mode] for mode in sorted(modes)},
        "process_metrics": {
            "measured_attempts": len(measured),
            "total_elapsed_ms": round(sum(elapsed_values), 3),
            "mean_elapsed_ms": (
                round(sum(elapsed_values) / len(elapsed_values), 3)
                if elapsed_values
                else None
            ),
            "max_elapsed_ms": round(max(elapsed_values), 3) if elapsed_values else None,
            "stdout_chars": sum(measured_chars(record, "stdout_chars") for record in measured),
            "stderr_chars": sum(measured_chars(record, "stderr_chars") for record in measured),
        },
    }


def record_evaluation(
    *,
    workspace: Path,
    attempt_id: str,
    unit_id: str,
    skill: str,
    scorecard_path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Append one Workflow-local scorecard result to the common Run ledger."""

    snapshot = _read_json_object(workspace / HARNESS_DIR / "run.json")
    failures = payload.get("failures") if isinstance(payload.get("failures"), list) else []
    repair_surfaces: list[str] = []
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        for surface in failure.get("repair_surface") or []:
            value = str(surface or "").strip()
            if value and value not in repair_surfaces:
                repair_surfaces.append(value)
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    record = {
        "schema": EVALUATION_SCHEMA,
        "evaluation_id": _new_id("evaluation"),
        "run_id": str(snapshot.get("run_id") or ""),
        "attempt_id": attempt_id,
        "unit_id": unit_id,
        "skill": skill,
        "workflow": str(payload.get("workflow") or snapshot.get("workflow") or "unknown"),
        "evaluator_id": str(payload.get("schema") or "unknown"),
        "recorded_at": now_iso_seconds(),
        "scorecard_path": scorecard_path,
        "verdict": str(payload.get("verdict") or "UNKNOWN").upper(),
        "score": payload.get("score"),
        "pass_score": payload.get("pass_score"),
        "dimensions": list(payload.get("dimensions") or []),
        "repair_surface": repair_surfaces,
        "metrics": {
            "model": metrics.get("model"),
            "input_tokens": metrics.get("input_tokens"),
            "output_tokens": metrics.get("output_tokens"),
            "cost": metrics.get("cost"),
            "latency_ms": metrics.get("latency_ms"),
        },
    }
    _append_jsonl(workspace / HARNESS_DIR / "evaluations" / "ledger.jsonl", record)
    _append_event(
        workspace=workspace,
        run_id=record["run_id"],
        event_type="evaluation.recorded",
        actor={"kind": "harness", "id": "evaluation-recorder"},
        unit_id=unit_id,
        attempt_id=attempt_id,
        payload={
            "evaluation_id": record["evaluation_id"],
            "evaluator_id": record["evaluator_id"],
            "verdict": record["verdict"],
            "score": record["score"],
        },
    )
    return record


def latest_evaluation(workspace: Path, *, verdict: str | None = None) -> dict[str, Any]:
    records = _read_jsonl(workspace / HARNESS_DIR / "evaluations" / "ledger.jsonl")
    expected = str(verdict or "").strip().upper()
    if not expected:
        return records[-1] if records else {}
    return next(
        (
            record
            for record in reversed(records)
            if str(record.get("verdict") or "").strip().upper() == expected
        ),
        {},
    )


def register_artifacts(
    *,
    workspace: Path,
    run_id: str,
    attempt_id: str,
    unit_id: str,
    outputs: Iterable[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    existing = {
        (str(record.get("attempt_id") or ""), str(record.get("path") or "")): record
        for record in _read_jsonl(workspace / HARNESS_DIR / "artifacts.jsonl")
    }
    for raw_path in outputs:
        relpath = str(raw_path or "").strip().lstrip("?").strip()
        if not relpath:
            continue
        path = workspace / relpath
        if not path.exists():
            continue
        fingerprint = _path_fingerprint(path)
        previous = existing.get((attempt_id, relpath))
        if previous is not None:
            if str(previous.get("sha256") or "") != str(fingerprint.get("sha256") or ""):
                raise ValueError(f"Artifact {relpath} changed while attempt {attempt_id} was being finalized.")
            records.append(previous)
            continue
        record = {
            "schema": ARTIFACT_SCHEMA,
            "artifact_id": _new_id("artifact"),
            "run_id": run_id,
            "attempt_id": attempt_id,
            "unit_id": unit_id,
            "path": relpath,
            "registered_at": now_iso_seconds(),
            **fingerprint,
        }
        _append_jsonl(workspace / HARNESS_DIR / "artifacts.jsonl", record)
        _append_event(
            workspace=workspace,
            run_id=run_id,
            event_type="artifact.registered",
            actor={"kind": "harness", "id": "artifact-recorder"},
            unit_id=unit_id,
            attempt_id=attempt_id,
            payload={"artifact_id": record["artifact_id"], "path": relpath},
        )
        records.append(record)
    return records


def _build_harness_lock(
    *,
    run_id: str,
    workspace: Path,
    repo_root: Path,
    pipeline_path: Path | None,
    units_template: str,
    pipeline_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    units_path = repo_root / units_template if units_template else workspace / "UNITS.csv"
    skills: dict[str, dict[str, str]] = {}
    units = _load_units(workspace)
    for skill in sorted({str(row.get("skill") or "").strip() for row in units if row.get("skill")}):
        skill_path = repo_root / ".codex" / "skills" / skill / "SKILL.md"
        if skill_path.exists():
            implementation = implementation_fingerprint(skill_path.parent)
            record = {
                "path": _relative_or_absolute(skill_path, repo_root),
                "sha256": _file_sha256(skill_path),
                "implementation_path": _relative_or_absolute(skill_path.parent, repo_root),
                "implementation_sha256": implementation["sha256"],
                "implementation_file_count": implementation["file_count"],
            }
            script_path = skill_path.parent / "scripts" / "run.py"
            if script_path.exists():
                record["script_path"] = _relative_or_absolute(script_path, repo_root)
                record["script_sha256"] = _file_sha256(script_path)
            skills[skill] = record

    kernel = {
        relpath: _file_sha256(repo_root / relpath)
        for relpath in HARNESS_KERNEL_PATHS
        if (repo_root / relpath).exists()
    }
    revision = _git_output(repo_root, "rev-parse", "HEAD")
    dirty = bool(_git_output(repo_root, "status", "--porcelain"))
    return {
        "schema": LOCK_SCHEMA,
        "run_id": run_id,
        "created_at": now_iso_seconds(),
        "protocols": {"completion": COMPLETION_PROTOCOL},
        "repository": {"revision": revision or "unavailable", "dirty": dirty},
        "pipeline": {
            "path": _relative_or_absolute(pipeline_path, repo_root) if pipeline_path else "",
            "sha256": _file_sha256(pipeline_path) if pipeline_path and pipeline_path.exists() else "",
            **dict(pipeline_snapshot or {}),
        },
        "units_template": {
            "path": _relative_or_absolute(units_path, repo_root),
            "sha256": _file_sha256(units_path) if units_path.exists() else "",
        },
        "skills": skills,
        "kernel": kernel,
        "model": {"status": "not_captured_by_local_cli"},
        "governance": {"status": "external_promotion_not_implemented"},
    }


def _materialize_pipeline_contract_snapshot(
    *,
    workspace: Path,
    repo_root: Path,
    pipeline_path: Path | None,
) -> dict[str, Any]:
    """Freeze the selected Pipeline and local inheritance surface inside the Run."""

    if pipeline_path is None or not pipeline_path.exists():
        return {}

    snapshot_dir = workspace / HARNESS_DIR / "contracts" / "pipelines"
    ensure_dir(snapshot_dir)
    snapshot_files: dict[str, str] = {}
    sources: list[Path] = []
    parents: dict[Path, Path] = {}
    current = pipeline_path.resolve()
    seen: set[Path] = set()
    while current not in seen:
        seen.add(current)
        sources.append(current)
        from tooling.pipeline_spec import PipelineSpec, resolve_pipeline_variant_path

        spec = PipelineSpec.load(current)
        if not spec.variant_of:
            break
        try:
            parent = resolve_pipeline_variant_path(current, spec.variant_of)
        except ValueError:
            raise ValueError(f"Could not snapshot Pipeline parent `{spec.variant_of}` for {current}.")
        parent = parent.resolve()
        parents[current] = parent
        current = parent

    resolved_repo_root = repo_root.resolve()
    targets: dict[Path, Path] = {}
    for source in sources:
        try:
            relative = source.relative_to(resolved_repo_root)
        except ValueError:
            namespace = hashlib.sha256(str(source.parent).encode("utf-8")).hexdigest()[:16]
            relative = Path("_external") / namespace / source.name
        targets[source] = snapshot_dir / relative

    for source in reversed(sources):
        target = targets[source]
        text = source.read_text(encoding="utf-8")
        parent = parents.get(source)
        if parent is not None and (
            Path(PipelineSpec.load(source).variant_of).is_absolute()
            or not source.is_relative_to(resolved_repo_root)
            or not parent.is_relative_to(resolved_repo_root)
        ):
            relative_parent = Path(
                os.path.relpath(targets[parent], start=target.parent)
            ).as_posix()
            text = _rewrite_pipeline_variant_reference(text, relative_parent, source=source)
        ensure_dir(target.parent)
        atomic_write_text(target, text)
        key = target.relative_to(snapshot_dir).as_posix()
        snapshot_files[key] = _file_sha256(target)

    selected = targets[pipeline_path.resolve()]
    return {
        "snapshot_root": _relative_or_absolute(snapshot_dir, workspace),
        "snapshot_path": _relative_or_absolute(selected, workspace),
        "snapshot_sha256": _file_sha256(selected),
        "snapshot_files": snapshot_files,
    }


def _rewrite_pipeline_variant_reference(text: str, reference: str, *, source: Path) -> str:
    """Point a copied variant at its copied parent without touching the live source."""

    lines = text.splitlines(keepends=True)
    in_frontmatter = False
    for index, line in enumerate(lines):
        if index == 0 and line.strip() == "---":
            in_frontmatter = True
            continue
        if in_frontmatter and line.strip() == "---":
            break
        if in_frontmatter and re.match(r"^variant_of\s*:", line):
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = f"variant_of: {json.dumps(reference)}{newline}"
            return "".join(lines)
    raise ValueError(f"Could not rewrite Pipeline parent reference in {source}.")


def _completion_protocol_compatibility(
    *,
    lock: dict[str, Any],
    issue_codes: Iterable[str],
) -> dict[str, Any]:
    protocols = lock.get("protocols") if isinstance(lock.get("protocols"), dict) else {}
    recorded = str(protocols.get("completion") or "unversioned")
    codes = {str(code) for code in issue_codes if str(code)}
    if recorded == COMPLETION_PROTOCOL:
        return {
            "mode": "current",
            "recorded_completion_protocol": recorded,
            "current_completion_protocol": COMPLETION_PROTOCOL,
            "legacy_evidence_gap_codes": [],
            "interpretation": (
                "The Run declares the current Completion Protocol; integrity issues are current-protocol violations."
            ),
        }
    if recorded == "unversioned":
        legacy_codes = sorted(codes.intersection(LEGACY_COMPLETION_EVIDENCE_CODES))
        return {
            "mode": "legacy_unversioned",
            "recorded_completion_protocol": recorded,
            "current_completion_protocol": COMPLETION_PROTOCOL,
            "legacy_evidence_gap_codes": legacy_codes,
            "interpretation": (
                "The Run predates an explicit Completion Protocol marker. Listed legacy evidence gaps may reflect "
                "an older evidence shape, but they remain audit errors and are not treated as PASS."
            ),
        }
    if recorded in MIGRATABLE_COMPLETION_PROTOCOLS:
        return {
            "mode": "legacy_versioned",
            "recorded_completion_protocol": recorded,
            "current_completion_protocol": COMPLETION_PROTOCOL,
            "legacy_evidence_gap_codes": [],
            "interpretation": (
                "The Run uses a recognized earlier Completion Protocol. PREPARED transactions may be "
                "migrated only by re-running current Workflow acceptance checks; historical DONE evidence "
                "remains explicit rather than inferred."
            ),
        }
    return {
        "mode": "unknown_protocol",
        "recorded_completion_protocol": recorded,
        "current_completion_protocol": COMPLETION_PROTOCOL,
        "legacy_evidence_gap_codes": [],
        "interpretation": (
            "The Run declares a Completion Protocol this Harness does not recognize; integrity results require "
            "protocol-aware review."
        ),
    }


def _build_plan_snapshot(*, workspace: Path, run_id: str, workflow: str) -> dict[str, Any]:
    return {
        "schema": "run-plan.v1",
        "run_id": run_id,
        "workflow": workflow,
        "generated_at": now_iso_seconds(),
        "units": _load_units(workspace),
    }


def _refresh_effective_plan(workspace: Path) -> None:
    snapshot = _read_json_object(workspace / HARNESS_DIR / "run.json")
    plan = _build_plan_snapshot(
        workspace=workspace,
        run_id=str(snapshot.get("run_id") or ""),
        workflow=str(snapshot.get("workflow") or "unknown"),
    )
    _write_json(workspace / HARNESS_DIR / "plan" / "effective.json", plan)


def _project_run_state(workspace: Path, *, attempt_status: str = "") -> str:
    counts = _unit_status_counts(workspace)
    total = sum(counts.values())
    if total and counts.get("DONE", 0) + counts.get("SKIP", 0) == total:
        return "COMPLETED"
    if attempt_status == "WAITING_HUMAN":
        return "WAITING_HUMAN"
    if attempt_status in {"FAILED_RETRYABLE", "FAILED_TERMINAL", "BLOCKED", "INTERRUPTED"}:
        return "BLOCKED"
    if counts.get("DOING", 0):
        return "RUNNING"
    if counts.get("BLOCKED", 0):
        terminal_attempts = [
            record
            for record in _read_jsonl(workspace / HARNESS_DIR / "attempts.jsonl")
            if record.get("record_type") == "finished"
        ]
        if terminal_attempts:
            latest = terminal_attempts[-1]
            latest_unit = str(latest.get("unit_id") or "")
            latest_unit_status = next(
                (
                    str(row.get("status") or "").strip().upper()
                    for row in _load_units(workspace)
                    if str(row.get("unit_id") or "").strip() == latest_unit
                ),
                "",
            )
            if str(latest.get("status") or "") == "WAITING_HUMAN" and latest_unit_status == "BLOCKED":
                return "WAITING_HUMAN"
        return "BLOCKED"
    if counts.get("DONE", 0) or counts.get("SKIP", 0):
        return "RUNNING"
    return "PLANNED"


def _update_run_snapshot(
    *,
    workspace: Path,
    state: str,
    active_attempt_id: str | None | object = ...,
    current_unit_id: str | None | object = ...,
) -> None:
    path = workspace / HARNESS_DIR / "run.json"
    payload = _read_json_object(path)
    if not payload:
        return
    payload["state"] = state
    payload["updated_at"] = now_iso_seconds()
    payload["unit_status"] = _unit_status_counts(workspace)
    payload["last_event_seq"] = _last_event_seq(workspace / HARNESS_DIR / "events.jsonl")
    if active_attempt_id is not ...:
        payload["active_attempt_id"] = active_attempt_id
    if current_unit_id is not ...:
        payload["current_unit_id"] = current_unit_id
    _write_json(path, payload)


def _append_event(
    *,
    workspace: Path,
    run_id: str,
    event_type: str,
    actor: dict[str, str],
    payload: dict[str, Any],
    unit_id: str = "",
    attempt_id: str = "",
) -> dict[str, Any]:
    events_path = workspace / HARNESS_DIR / "events.jsonl"
    record = {
        "schema": EVENT_SCHEMA,
        "seq": _last_event_seq(events_path) + 1,
        "event_id": _new_id("event"),
        "run_id": run_id,
        "timestamp": now_iso_seconds(),
        "type": event_type,
        "actor": actor,
        "payload": payload,
    }
    if unit_id:
        record["unit_id"] = unit_id
    if attempt_id:
        record["attempt_id"] = attempt_id
    _append_jsonl(events_path, record)
    return record


def _load_units(workspace: Path) -> list[dict[str, str]]:
    path = workspace / "UNITS.csv"
    if not path.exists():
        return []
    try:
        return UnitsTable.load(path).rows
    except Exception:
        return []


def _unit_status_counts(workspace: Path) -> dict[str, int]:
    counts = Counter(str(row.get("status") or "").strip().upper() or "<BLANK>" for row in _load_units(workspace))
    return {key: counts[key] for key in sorted(counts)}


def _pipeline_targets(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    try:
        from tooling.pipeline_spec import PipelineSpec

        return list(PipelineSpec.load(path).target_artifacts)
    except Exception:
        return []


def _goal_request_from_markdown(path: Path) -> str:
    if not path.exists():
        return ""
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()]
    return " ".join(line.lstrip("- ") for line in lines if line and not line.startswith("#")).strip()


def _path_fingerprint(path: Path) -> dict[str, Any]:
    if path.is_dir():
        files = sorted(item for item in path.rglob("*") if item.is_file())
        digest = hashlib.sha256()
        for item in files:
            digest.update(str(item.relative_to(path)).encode("utf-8"))
            digest.update(_file_sha256(item).encode("ascii"))
        return {"type": "directory", "file_count": len(files), "sha256": digest.hexdigest()}
    return {"type": "file", "size": path.stat().st_size, "sha256": _file_sha256(path)}


def _checkpoint_artifact_fingerprint(
    *,
    path: Path,
    relpath: str,
    checkpoint: str,
) -> dict[str, Any]:
    if relpath != "DECISIONS.md" or not path.is_file():
        return _path_fingerprint(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    normalized = _checkpoint_decisions_projection(text, checkpoint=checkpoint).encode("utf-8")
    return {
        "type": "file",
        "size": len(normalized),
        "sha256": hashlib.sha256(normalized).hexdigest(),
        "normalization": "checkpoint-block-and-approval-checkbox-insensitive",
    }


def _checkpoint_decisions_projection(text: str, *, checkpoint: str) -> str:
    """Project only one Checkpoint block so later Decisions do not stale earlier approval."""

    block_match = re.search(
        rf"<!-- BEGIN CHECKPOINT:{re.escape(checkpoint)} -->(.*?)<!-- END CHECKPOINT:{re.escape(checkpoint)} -->",
        text,
        flags=re.DOTALL,
    )
    if block_match is None:
        return ""
    approval_match = re.search(
        rf"^(\s*-\s*)\[[ xX]\](\s*(?:Approve\s+)?{re.escape(checkpoint)}\b.*)$",
        text,
        flags=re.MULTILINE,
    )
    approval = ""
    if approval_match is not None:
        approval = f"{approval_match.group(1)}[ ]{approval_match.group(2)}"
    return f"{approval}\n{block_match.group(0).strip()}\n"


def implementation_fingerprint(path: Path) -> dict[str, Any]:
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
        digest.update(bytes.fromhex(_file_sha256(item)))
    return {"file_count": len(files), "sha256": digest.hexdigest()}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_output(repo_root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _relative_or_absolute(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
