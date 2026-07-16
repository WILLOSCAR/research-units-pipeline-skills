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
    ensure_dir,
    goal_constraints_from_request,
    load_workspace_pipeline_spec,
    now_iso_seconds,
    parse_semicolon_list,
    update_status_log,
)
from tooling.harness_contracts import HARNESS_KERNEL_PATHS


HARNESS_DIR = ".harness"
GOAL_SCHEMA = "goal-spec.v2"
RUN_SCHEMA = "run-state.v1"
LOCK_SCHEMA = "harness-lock.v1"
EVENT_SCHEMA = "run-event.v1"
ATTEMPT_SCHEMA = "unit-attempt.v1"
ARTIFACT_SCHEMA = "artifact-record.v1"
FAILURE_SCHEMA = "failure-record.v1"
EVALUATION_SCHEMA = "run-evaluation.v1"
INVOCATION_LOCK_SCHEMA = "workspace-invocation-lock.v1"
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
        _write_json(
            harness_dir / "harness.lock.json",
            _build_harness_lock(
                run_id=run_id,
                workspace=workspace,
                repo_root=repo_root,
                pipeline_path=pipeline_path,
                units_template=units_template,
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
    _append_jsonl(workspace / HARNESS_DIR / "attempts.jsonl", record)
    event_type = _attempt_terminal_event_type(status)
    _append_event(
        workspace=workspace,
        run_id=run_id,
        event_type=event_type,
        actor={"kind": "harness", "id": "unit-executor"},
        unit_id=unit_id,
        attempt_id=attempt_id,
        payload={"status": status, "exit_code": exit_code, "message": message},
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
    *, workspace: Path, action: str, subject: str, decision: str, note: str = ""
) -> dict[str, Any]:
    return record_decision(
        workspace=workspace,
        action=action,
        subject=subject,
        decision=decision,
        actor={"kind": "human", "id": "workspace-operator"},
        note=note,
    )


def record_completion_stage(
    *,
    workspace: Path,
    unit_id: str,
    attempt_id: str,
    stage: str,
    manifest_path: str,
    outputs: Iterable[str],
    recovered: bool = False,
) -> dict[str, Any]:
    if stage not in {"prepared", "committed"}:
        raise ValueError(f"Unsupported completion stage: {stage}")
    snapshot = _read_json_object(workspace / HARNESS_DIR / "run.json")
    return _append_event(
        workspace=workspace,
        run_id=str(snapshot.get("run_id") or ""),
        event_type=f"unit.completion.{stage}",
        actor={"kind": "harness", "id": "completion-protocol"},
        unit_id=unit_id,
        attempt_id=attempt_id,
        payload={
            "manifest_path": manifest_path,
            "outputs": list(outputs),
            "recovered": recovered,
        },
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
        record_completion_stage(
            workspace=workspace,
            unit_id=unit_id,
            attempt_id=attempt_id,
            stage="prepared",
            manifest_path=str(path.relative_to(workspace)),
            outputs=outputs,
            recovered=True,
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

    recovered: list[tuple[str, str, str, list[str]]] = []
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
        row["status"] = "DONE"
        recovered.append(
            (
                unit_id,
                attempt_id,
                manifest_relpath,
                [str(item.get("path") or "") for item in manifest.get("outputs") or [] if isinstance(item, dict)],
            )
        )

    if not recovered:
        return []
    table.save(units_path)
    for unit_id, attempt_id, manifest_relpath, outputs in recovered:
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
        )
        update_status_log(
            workspace / "STATUS.md",
            f"{now_iso_seconds()} {unit_id} DONE (recovered successful completion {attempt_id})",
        )
    return [unit_id for unit_id, _, _, _ in recovered]


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
    return {
        "run_id": str(run.get("run_id") or ""),
        "goal_id": str(run.get("goal_id") or ""),
        "state": str(run.get("state") or ""),
        "workflow": str(run.get("workflow") or ""),
        "harness_revision": str(repository.get("revision") or ""),
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


def inspect_run_integrity(workspace: Path) -> dict[str, Any]:
    """Check referential integrity across the durable Run evidence ledgers."""

    harness_dir = workspace / HARNESS_DIR
    run = _read_json_object(harness_dir / "run.json")
    if not run:
        return {
            "enabled": False,
            "run_id": "",
            "ledger_record_counts": {},
            "issue_count": 0,
            "issues": [],
        }

    run_id = str(run.get("run_id") or "")
    issues: list[dict[str, str]] = []
    seen_issues: set[tuple[str, str]] = set()

    def add(level: str, code: str, message: str) -> None:
        key = (code, message)
        if key in seen_issues:
            return
        seen_issues.add(key)
        issues.append({"level": level, "code": code, "message": message})

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
        records, malformed_lines = _read_jsonl_with_errors(path)
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

    observed_attempt_events = {
        (str(record.get("attempt_id") or ""), str(record.get("type") or ""))
        for record in ledgers["events"]
        if str(record.get("attempt_id") or "")
    }
    for attempt_id in starts:
        if (attempt_id, "unit.attempt.started") not in observed_attempt_events:
            add("ERROR", "attempt_start_event_missing", f"Attempt `{attempt_id}` has no started Event.")
    for attempt_id, records in finishes.items():
        event_type = _attempt_terminal_event_type(str(records[-1].get("status") or ""))
        if (attempt_id, event_type) not in observed_attempt_events:
            add("ERROR", "attempt_terminal_event_missing", f"Attempt `{attempt_id}` has no `{event_type}` Event.")

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

    for unit_id, row in units.items():
        if str(row.get("status") or "").strip().upper() != "DONE":
            continue
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
            candidates = [
                artifact
                for artifact in ledgers["artifacts"]
                if str(artifact.get("attempt_id") or "") in successful_attempts
                and str(artifact.get("path") or "") == relpath
            ]
            if not candidates:
                add("ERROR", "done_output_unregistered", f"DONE Unit `{unit_id}` output `{relpath}` has no Artifact record from a successful Attempt.")
                continue
            latest = candidates[-1]
            path = workspace / relpath
            if relpath not in MUTABLE_PROJECTION_PATHS and path.exists() and str(latest.get("sha256") or ""):
                current_sha = str(_path_fingerprint(path).get("sha256") or "")
                if current_sha != str(latest.get("sha256") or ""):
                    add("ERROR", "artifact_hash_mismatch", f"Current `{relpath}` no longer matches its latest successful Artifact record.")

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

    return {
        "enabled": True,
        "run_id": run_id,
        "ledger_record_counts": {name: len(records) for name, records in ledgers.items()},
        "issue_count": len(issues),
        "issues": issues,
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


def latest_evaluation(workspace: Path) -> dict[str, Any]:
    records = _read_jsonl(workspace / HARNESS_DIR / "evaluations" / "ledger.jsonl")
    return records[-1] if records else {}


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
) -> dict[str, Any]:
    units_path = repo_root / units_template if units_template else workspace / "UNITS.csv"
    skills: dict[str, dict[str, str]] = {}
    units = _load_units(workspace)
    for skill in sorted({str(row.get("skill") or "").strip() for row in units if row.get("skill")}):
        skill_path = repo_root / ".codex" / "skills" / skill / "SKILL.md"
        if skill_path.exists():
            implementation = _implementation_fingerprint(skill_path.parent)
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
        "repository": {"revision": revision or "unavailable", "dirty": dirty},
        "pipeline": {
            "path": _relative_or_absolute(pipeline_path, repo_root) if pipeline_path else "",
            "sha256": _file_sha256(pipeline_path) if pipeline_path and pipeline_path.exists() else "",
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


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _last_event_seq(path: Path) -> int:
    if not path.exists():
        return 0
    last = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and isinstance(record.get("seq"), int):
                last = max(last, int(record["seq"]))
    return last


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


def _implementation_fingerprint(path: Path) -> dict[str, Any]:
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


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                records.append(payload)
    return records


def _read_jsonl_with_errors(path: Path) -> tuple[list[dict[str, Any]], list[int]]:
    if not path.exists():
        return [], []
    records: list[dict[str, Any]] = []
    malformed: list[int] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                malformed.append(line_number)
                continue
            if isinstance(payload, dict):
                records.append(payload)
            else:
                malformed.append(line_number)
    return records, malformed


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
