"""Improvement-report synthesis and rendering.

These are the helpers the Harness uses to fold Doctor and Run Audit findings,
plus the durable failure ledger, into an ``improvement-report.v1`` payload: the
source-driven payload builder, the non-blocking evaluation-opportunity
projection, the Markdown renderer, the durable writers, and the leaf helpers
they build on (diagnostic and failure suggestion records, failure ledger
reading/collapsing/repair-history, and the issue -> upstream-interface /
validation-command mappings). They hold no shared mutable state and depend only
on the filesystem, the standard library, and a couple of leaf helpers in
``tooling.common`` (plus the lazily imported ``latest_evaluation`` projection),
so they are kept separate from the god-module in ``tooling.harness`` (which
re-exports them to preserve its public surface). The ``improvement-report.v1``
schema validator stays in ``tooling.harness`` because it shares the generic
payload-validation helpers with the other report validators.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tooling.common import atomic_write_text, now_iso_seconds, pipeline_cli_command


IMPROVEMENT_REPORT_SCHEMA = "improvement-report.v1"


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
    diagnostic_suggestions = _improvement_suggestion_records(
        workspace=workspace,
        doctor_payload=doctor_payload,
        run_audit_payload=audit_payload,
    )
    failure_suggestions = _failure_suggestion_records(
        workspace=workspace,
        failures=failures,
    )
    suggestions = [*failure_suggestions, *diagnostic_suggestions]
    for index, suggestion in enumerate(suggestions, start=1):
        suggestion["id"] = f"S{index:03d}"
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
        "artifact_interface_standard": "CONTEXT.md",
        "source_reports": source_reports,
        "repair_history": repair_history,
        "suggestions": suggestions,
        "quality_opportunities": quality_opportunities,
        "verdict": "ATTENTION" if exit_code else "PASS",
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
    *, workspace: Path, failures: list[dict[str, Any]]
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
                "id": f"S{len(records) + 1:03d}",
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
