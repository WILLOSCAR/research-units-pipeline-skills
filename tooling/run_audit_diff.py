"""Run-audit diff computation and rendering.

These are the pure comparison helpers the Harness uses to diff two
``run-audit.v2`` payloads into a ``run-audit-diff.v1`` report: the payload
builder, the Markdown renderer, the durable writers, and the leaf-level delta
primitives they build on (unit-status/int-mapping deltas, target-artifact
change classification, manifest counting, Attempt comparison, and numeric/count
delta formatting). They hold no shared mutable state and depend only on the
filesystem, the standard library, and a couple of leaf helpers in
``tooling.common``, so they are kept separate from the god-module in
``tooling.harness`` (which re-exports them to preserve its public surface). The
``run-audit-diff.v1`` schema validator stays in ``tooling.harness`` because it
shares the generic payload-validation helpers with the other report validators.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tooling.common import atomic_write_text, now_iso_seconds


RUN_AUDIT_DIFF_SCHEMA = "run-audit-diff.v1"


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
