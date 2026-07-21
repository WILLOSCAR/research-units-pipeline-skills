from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from tooling.common import (
    UnitsTable,
    load_workspace_pipeline_spec,
    now_iso_seconds,
    parse_semicolon_list,
    update_status_log,
)
from tooling.harness import write_unit_manifest
from tooling.run_state import (
    ensure_run_state,
    finish_attempt,
    open_attempt_for_unit,
    reconcile_run_state,
    record_completion_stage,
    record_evaluation,
    record_failure,
    start_attempt,
)
from tooling.scorecards import validate_scorecard


@dataclass(frozen=True)
class CompletionResult:
    unit_id: str
    attempt_id: str
    status: str
    message: str
    manifest_path: str = ""


@dataclass(frozen=True)
class DeclaredScorecard:
    relpath: str
    payload: dict[str, Any]
    validation_errors: tuple[str, ...]


def load_declared_scorecard(workspace: Path, outputs: Iterable[str]) -> DeclaredScorecard | None:
    spec = load_workspace_pipeline_spec(workspace)
    rubric = spec.quality_contract.get("semantic_rubric", {}) if spec is not None else {}
    expected_schema = str(rubric.get("schema") or "").strip()
    for relpath in outputs:
        if not str(relpath).upper().endswith("_SCORECARD.JSON"):
            continue
        path = workspace / str(relpath)
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return DeclaredScorecard(
                relpath=str(relpath),
                payload={},
                validation_errors=(f"scorecard must be valid JSON ({type(exc).__name__}: {exc})",),
            )
        if not isinstance(payload, dict):
            return DeclaredScorecard(
                relpath=str(relpath),
                payload={},
                validation_errors=("scorecard must be a JSON object",),
            )
        actual_schema = str(payload.get("schema") or "").strip()
        schema = expected_schema or actual_schema
        errors = [] if schema else ["schema must be a non-empty string"]
        if schema:
            errors.extend(validate_scorecard(payload, schema=schema))
        return DeclaredScorecard(str(relpath), payload, tuple(errors))
    return None


def scorecard_failure(scorecard: DeclaredScorecard) -> dict[str, Any] | None:
    if scorecard.validation_errors:
        return {
            "symptom": f"Scorecard `{scorecard.relpath}` is invalid: {'; '.join(scorecard.validation_errors[:3])}",
            "causal_behavior": "The declared machine-readable evaluation does not satisfy the shared scorecard contract.",
            "repair_surface": [scorecard.relpath, "tooling/scorecards.py"],
            "severity": "high",
        }
    if str(scorecard.payload.get("verdict") or "").upper() != "FAIL":
        return None

    failures = scorecard.payload.get("failures") if isinstance(scorecard.payload.get("failures"), list) else []
    messages: list[str] = []
    repair_surface: list[str] = [scorecard.relpath]
    severity = "medium"
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        failure_message = str(failure.get("message") or failure.get("code") or "").strip()
        if failure_message:
            messages.append(failure_message)
        for surface in failure.get("repair_surface") or []:
            value = str(surface or "").strip()
            if value and value not in repair_surface:
                repair_surface.append(value)
        if str(failure.get("severity") or "").strip().lower() in {"high", "critical"}:
            severity = "high"
    score = scorecard.payload.get("score")
    threshold = scorecard.payload.get("pass_score")
    summary = "; ".join(messages[:3]) or "The declared semantic scorecard did not pass."
    return {
        "symptom": f"Scorecard `{scorecard.relpath}` failed with score {score}/{threshold}. {summary}",
        "causal_behavior": "The deliverable was produced, but its structured semantic contract did not satisfy the configured rubric.",
        "repair_surface": repair_surface,
        "severity": severity,
    }


def commit_unit_completion(
    *,
    workspace: Path,
    repo_root: Path,
    unit_id: str,
    attempt_id: str | None = None,
    exit_code: int = 0,
    message: str = "OK",
    resolved_failure_types: Iterable[str] = ("missing_outputs",),
    attempt_execution: dict[str, Any] | None = None,
) -> CompletionResult:
    """Commit one verified Unit completion across Attempt, Artifact, Manifest, and UNITS projections."""

    workspace = workspace.resolve()
    ensure_run_state(workspace=workspace, repo_root=repo_root)
    units_path = workspace / "UNITS.csv"
    if not units_path.exists():
        return CompletionResult(unit_id, attempt_id or "", "ERROR", f"Missing {units_path}")

    table = UnitsTable.load(units_path)
    row = next((item for item in table.rows if str(item.get("unit_id") or "").strip() == unit_id), None)
    if row is None:
        return CompletionResult(unit_id, attempt_id or "", "ERROR", f"Unit not found: {unit_id}")

    skill = str(row.get("skill") or "").strip()
    outputs = [_strip_optional_marker(item) for item in parse_semicolon_list(row.get("outputs"))]
    required_outputs = [
        _strip_optional_marker(item)
        for item in parse_semicolon_list(row.get("outputs"))
        if not item.strip().startswith("?")
    ]

    if attempt_id is None:
        if str(row.get("status") or "").strip().upper() == "DONE":
            return CompletionResult(unit_id, "", "DONE", "Unit is already DONE")
        open_attempt = open_attempt_for_unit(workspace=workspace, unit_id=unit_id)
        if open_attempt:
            if str(open_attempt.get("skill") or "") != skill:
                return CompletionResult(
                    unit_id,
                    str(open_attempt.get("attempt_id") or ""),
                    "ERROR",
                    f"Open Attempt skill `{open_attempt.get('skill')}` does not match Unit skill `{skill}`.",
                )
            attempt_id = str(open_attempt.get("attempt_id") or "")
        else:
            attempt_id = start_attempt(
                workspace=workspace,
                repo_root=repo_root,
                unit_id=unit_id,
                skill=skill,
                inputs=parse_semicolon_list(row.get("inputs")),
            )
            row["status"] = "DOING"
            table.save(units_path)

    missing = [relpath for relpath in required_outputs if relpath and not (workspace / relpath).exists()]
    if missing:
        rejection = f"Required outputs are missing: {', '.join(missing)}"
        return _reject_completion(
            workspace=workspace,
            repo_root=repo_root,
            unit_id=unit_id,
            attempt_id=attempt_id,
            skill=skill,
            outputs=outputs,
            exit_code=exit_code,
            failure_type="missing_outputs",
            symptom=rejection,
            causal_behavior="The Unit was submitted for completion before its declared Artifact contract existed.",
            harness_mechanism="The Completion Protocol validates required outputs before committing DONE.",
            repair_surface=missing,
            attempt_execution=attempt_execution,
        )

    from tooling.quality_gate import (
        check_completion_acceptance,
        check_completion_invariants,
        completion_check_required,
        has_completion_invariant,
        write_quality_report,
    )

    invariant_issues = check_completion_invariants(skill=skill, workspace=workspace, outputs=outputs)
    if invariant_issues:
        rejection = "; ".join(str(issue.message) for issue in invariant_issues[:3])
        return _reject_completion(
            workspace=workspace,
            repo_root=repo_root,
            unit_id=unit_id,
            attempt_id=attempt_id,
            skill=skill,
            outputs=outputs,
            exit_code=exit_code,
            failure_type="section_first_cutover",
            symptom=rejection,
            causal_behavior="A Workflow-mandatory completion invariant did not pass.",
            harness_mechanism="The Completion Protocol routes mandatory checks through the Workflow-domain quality registry.",
            repair_surface=["output/REROUTE_STATE.json", f".codex/skills/{skill}/SKILL.md"],
            attempt_execution=attempt_execution,
        )

    verified_failure_types = {
        str(item or "").strip()
        for item in resolved_failure_types
        if str(item or "").strip()
    }
    verified_failure_types.add("missing_outputs")
    if has_completion_invariant(skill):
        verified_failure_types.add("section_first_cutover")

    scorecard = load_declared_scorecard(workspace, outputs)
    if scorecard is not None and not scorecard.validation_errors:
        # Evaluation is Attempt evidence even when another Workflow acceptance
        # check blocks Completion later in this transaction.
        record_evaluation(
            workspace=workspace,
            attempt_id=attempt_id,
            unit_id=unit_id,
            skill=skill,
            scorecard_path=scorecard.relpath,
            payload=scorecard.payload,
        )

    acceptance_required = completion_check_required(skill=skill, workspace=workspace)
    acceptance_issues = check_completion_acceptance(skill=skill, workspace=workspace, outputs=outputs)
    if acceptance_required:
        try:
            report_path = write_quality_report(
                workspace=workspace,
                unit_id=unit_id,
                skill=skill,
                issues=acceptance_issues,
            )
        except Exception as exc:
            rejection = f"Workflow quality report could not be written: {type(exc).__name__}: {exc}"
            return _reject_completion(
                workspace=workspace,
                repo_root=repo_root,
                unit_id=unit_id,
                attempt_id=attempt_id,
                skill=skill,
                outputs=outputs,
                exit_code=exit_code,
                failure_type="quality_report_error",
                symptom=rejection,
                causal_behavior="The acceptance result could not be persisted for review.",
                harness_mechanism="Completion fails closed when the mandatory quality report is not durable.",
                repair_surface=["output/QUALITY_GATE.md", "tooling/quality_reporting.py"],
                severity="high",
                write_manifest=False,
                attempt_execution=attempt_execution,
            )
        if acceptance_issues:
            rejection = "; ".join(str(issue.message) for issue in acceptance_issues[:3])
            rel_report = str(report_path.relative_to(workspace))
            repair_surface = [rel_report, f".codex/skills/{skill}/SKILL.md"]
            if any(issue.code == "completion_contract_unavailable" for issue in acceptance_issues):
                repair_surface = [rel_report, "PIPELINE.lock.md"]
            return _reject_completion(
                workspace=workspace,
                repo_root=repo_root,
                unit_id=unit_id,
                attempt_id=attempt_id,
                skill=skill,
                outputs=outputs,
                exit_code=exit_code,
                failure_type="acceptance_contract_failed",
                symptom=rejection,
                causal_behavior="The Skill produced its declared files, but the Workflow acceptance contract did not pass.",
                harness_mechanism="The Completion Protocol runs Workflow-required checks before committing DONE.",
                repair_surface=repair_surface,
                attempt_execution=attempt_execution,
            )
        verified_failure_types.add("acceptance_contract_failed")
        verified_failure_types.add("quality_report_error")

    if scorecard is not None:
        semantic_failure = scorecard_failure(scorecard)
        if semantic_failure is not None:
            rejection = str(semantic_failure["symptom"])
            return _reject_completion(
                workspace=workspace,
                repo_root=repo_root,
                unit_id=unit_id,
                attempt_id=attempt_id,
                skill=skill,
                outputs=outputs,
                exit_code=exit_code,
                failure_type="semantic_quality_gate_failed",
                symptom=rejection,
                causal_behavior=str(semantic_failure["causal_behavior"]),
                harness_mechanism="The Completion Protocol evaluates declared scorecards before committing DONE.",
                repair_surface=list(semantic_failure["repair_surface"]),
                severity=str(semantic_failure["severity"]),
                attempt_execution=attempt_execution,
            )
        verified_failure_types.add("semantic_quality_gate_failed")

    try:
        manifest_path = write_unit_manifest(
            workspace=workspace,
            unit_id=unit_id,
            skill=skill,
            outputs=outputs,
            exit_code=exit_code,
            status="PREPARED",
            attempt_id=attempt_id,
            repo_root=repo_root,
        )
    except Exception as exc:
        rejection = f"Completion manifest could not be written: {type(exc).__name__}: {exc}"
        return _reject_completion(
            workspace=workspace,
            repo_root=repo_root,
            unit_id=unit_id,
            attempt_id=attempt_id,
            skill=skill,
            outputs=outputs,
            exit_code=exit_code,
            failure_type="completion_manifest_error",
            symptom=rejection,
            causal_behavior="The Completion Protocol could not persist the Unit output manifest.",
            harness_mechanism="A Unit cannot become DONE until its manifest is durable.",
            repair_surface=["output/unit_logs", "tooling/completion.py"],
            severity="high",
            write_manifest=False,
            attempt_execution=attempt_execution,
        )

    manifest_relpath = str(manifest_path.relative_to(workspace))
    record_completion_stage(
        workspace=workspace,
        unit_id=unit_id,
        attempt_id=attempt_id,
        stage="prepared",
        manifest_path=manifest_relpath,
        outputs=outputs,
    )
    finish_attempt(
        workspace=workspace,
        attempt_id=attempt_id,
        unit_id=unit_id,
        skill=skill,
        status="SUCCEEDED",
        exit_code=exit_code,
        outputs=outputs,
        message=message,
        resolved_failure_types=verified_failure_types,
        execution=attempt_execution,
    )
    write_unit_manifest(
        workspace=workspace,
        unit_id=unit_id,
        skill=skill,
        outputs=outputs,
        exit_code=exit_code,
        status="DONE",
        attempt_id=attempt_id,
        repo_root=repo_root,
    )
    _set_unit_status(workspace=workspace, unit_id=unit_id, status="DONE")
    record_completion_stage(
        workspace=workspace,
        unit_id=unit_id,
        attempt_id=attempt_id,
        stage="committed",
        manifest_path=manifest_relpath,
        outputs=outputs,
    )
    update_status_log(workspace / "STATUS.md", f"{now_iso_seconds()} {unit_id} DONE ({message})")
    reconcile_run_state(workspace=workspace)
    return CompletionResult(unit_id, attempt_id, "DONE", message, manifest_relpath)


def _reject_completion(
    *,
    workspace: Path,
    repo_root: Path,
    unit_id: str,
    attempt_id: str,
    skill: str,
    outputs: list[str],
    exit_code: int,
    failure_type: str,
    symptom: str,
    causal_behavior: str,
    harness_mechanism: str,
    repair_surface: list[str],
    severity: str = "medium",
    write_manifest: bool = True,
    attempt_execution: dict[str, Any] | None = None,
) -> CompletionResult:
    _set_unit_status(workspace=workspace, unit_id=unit_id, status="BLOCKED")
    manifest_relpath = ""
    if write_manifest:
        manifest_path = write_unit_manifest(
            workspace=workspace,
            unit_id=unit_id,
            skill=skill,
            outputs=outputs,
            exit_code=exit_code,
            status="BLOCKED",
            attempt_id=attempt_id,
            repo_root=repo_root,
        )
        manifest_relpath = str(manifest_path.relative_to(workspace))
    record_failure(
        workspace=workspace,
        unit_id=unit_id,
        attempt_id=attempt_id,
        failure_type=failure_type,
        symptom=symptom,
        causal_behavior=causal_behavior,
        harness_mechanism=harness_mechanism,
        repair_surface=repair_surface,
        severity=severity,
    )
    finish_attempt(
        workspace=workspace,
        attempt_id=attempt_id,
        unit_id=unit_id,
        skill=skill,
        status="FAILED_RETRYABLE",
        exit_code=exit_code,
        outputs=outputs,
        message=symptom,
        execution=attempt_execution,
    )
    update_status_log(workspace / "STATUS.md", f"{now_iso_seconds()} {unit_id} BLOCKED ({symptom})")
    reconcile_run_state(workspace=workspace)
    return CompletionResult(unit_id, attempt_id, "BLOCKED", symptom, manifest_relpath)


def _set_unit_status(*, workspace: Path, unit_id: str, status: str) -> None:
    units_path = workspace / "UNITS.csv"
    table = UnitsTable.load(units_path)
    for row in table.rows:
        if str(row.get("unit_id") or "").strip() == unit_id:
            row["status"] = status
            table.save(units_path)
            return
    raise ValueError(f"Unit not found while committing completion: {unit_id}")


def _strip_optional_marker(relpath: str) -> str:
    value = str(relpath or "").strip()
    return value[1:].strip() if value.startswith("?") else value
