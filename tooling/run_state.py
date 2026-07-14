from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from tooling.common import UnitsTable, atomic_write_text, ensure_dir, goal_constraints_from_request, load_workspace_pipeline_spec, now_iso_seconds


HARNESS_DIR = ".harness"
GOAL_SCHEMA = "goal-spec.v2"
RUN_SCHEMA = "run-state.v1"
LOCK_SCHEMA = "harness-lock.v1"
EVENT_SCHEMA = "run-event.v1"
ATTEMPT_SCHEMA = "unit-attempt.v1"
ARTIFACT_SCHEMA = "artifact-record.v1"
FAILURE_SCHEMA = "failure-record.v1"
EVALUATION_SCHEMA = "run-evaluation.v1"


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


def ensure_run_state(*, workspace: Path, repo_root: Path) -> dict[str, Any]:
    existing = _read_json_object(workspace / HARNESS_DIR / "run.json")
    if existing:
        return existing

    pipeline_path: Path | None = None
    units_template = ""
    try:
        spec = load_workspace_pipeline_spec(workspace)
        pipeline_path = spec.path
        units_template = str(spec.units_template)
    except Exception:
        pass
    return initialize_run_state(
        workspace=workspace,
        repo_root=repo_root,
        pipeline_path=pipeline_path,
        units_template=units_template,
    )


def start_attempt(
    *,
    workspace: Path,
    repo_root: Path,
    unit_id: str,
    skill: str,
    inputs: Iterable[str],
) -> str:
    snapshot = ensure_run_state(workspace=workspace, repo_root=repo_root)
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
    }
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
) -> list[dict[str, Any]]:
    snapshot = _read_json_object(workspace / HARNESS_DIR / "run.json")
    run_id = str(snapshot.get("run_id") or "")
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
    event_type = {
        "SUCCEEDED": "unit.attempt.succeeded",
        "WAITING_HUMAN": "run.waiting_human",
        "INTERRUPTED": "unit.attempt.interrupted",
    }.get(status, "unit.attempt.failed")
    _append_event(
        workspace=workspace,
        run_id=run_id,
        event_type=event_type,
        actor={"kind": "harness", "id": "unit-executor"},
        unit_id=unit_id,
        attempt_id=attempt_id,
        payload={"status": status, "exit_code": exit_code, "message": message},
    )
    if status == "SUCCEEDED":
        _resolve_open_failures(workspace=workspace, unit_id=unit_id, attempt_id=attempt_id, run_id=run_id)
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


def _resolve_open_failures(*, workspace: Path, unit_id: str, attempt_id: str, run_id: str) -> None:
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


def record_human_decision(
    *, workspace: Path, action: str, subject: str, decision: str, note: str = ""
) -> dict[str, Any]:
    snapshot = _read_json_object(workspace / HARNESS_DIR / "run.json")
    previous_state = str(snapshot.get("state") or "")
    record = {
        "schema": "run-decision.v1",
        "decision_id": _new_id("decision"),
        "run_id": str(snapshot.get("run_id") or ""),
        "recorded_at": now_iso_seconds(),
        "actor": {"kind": "human", "id": "workspace-operator"},
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


def record_recovered_interruption(*, workspace: Path, unit_id: str) -> None:
    snapshot = _read_json_object(workspace / HARNESS_DIR / "run.json")
    attempt_id = str(snapshot.get("active_attempt_id") or _new_id("attempt"))
    finish_attempt(
        workspace=workspace,
        attempt_id=attempt_id,
        unit_id=unit_id,
        skill="unknown",
        status="INTERRUPTED",
        exit_code=None,
        message="Recovered stale DOING state from a previous process.",
    )


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
    for raw_path in outputs:
        relpath = str(raw_path or "").strip().lstrip("?").strip()
        if not relpath:
            continue
        path = workspace / relpath
        if not path.exists():
            continue
        record = {
            "schema": ARTIFACT_SCHEMA,
            "artifact_id": _new_id("artifact"),
            "run_id": run_id,
            "attempt_id": attempt_id,
            "unit_id": unit_id,
            "path": relpath,
            "registered_at": now_iso_seconds(),
            **_path_fingerprint(path),
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
            record = {
                "path": _relative_or_absolute(skill_path, repo_root),
                "sha256": _file_sha256(skill_path),
            }
            script_path = skill_path.parent / "scripts" / "run.py"
            if script_path.exists():
                record["script_path"] = _relative_or_absolute(script_path, repo_root)
                record["script_sha256"] = _file_sha256(script_path)
            skills[skill] = record

    kernel_paths = (
        "scripts/pipeline.py",
        "tooling/executor.py",
        "tooling/harness.py",
        "tooling/quality_gate.py",
        "tooling/run_state.py",
        "tooling/brief_evaluation.py",
        "tooling/evidence_review_evaluation.py",
        "tooling/idea_evaluation.py",
        "tooling/review_evaluation.py",
    )
    kernel = {
        relpath: _file_sha256(repo_root / relpath)
        for relpath in kernel_paths
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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
