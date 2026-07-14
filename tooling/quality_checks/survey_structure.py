from __future__ import annotations

from pathlib import Path
from typing import Any

from tooling.quality_checks.common import QualityIssue


def structure_mode(workspace: Path) -> str:
    from tooling.common import load_workspace_pipeline_spec

    spec = load_workspace_pipeline_spec(workspace)
    if spec is None:
        return ""
    return str(spec.structure_mode or "").strip().lower()


def section_first_artifact_issues(workspace: Path, *, consumer: str) -> list[QualityIssue]:
    if structure_mode(workspace) != "section_first":
        return []

    required = [
        "outline/chapter_skeleton.yml",
        "outline/section_bindings.jsonl",
        "outline/section_binding_report.md",
        "outline/section_briefs.jsonl",
    ]
    missing: list[str] = []
    empty: list[str] = []
    for rel in required:
        path = workspace / rel
        if not path.exists():
            missing.append(rel)
            continue
        if path.stat().st_size <= 0:
            empty.append(rel)

    issues: list[QualityIssue] = []
    if missing:
        issues.append(
            QualityIssue(
                code="section_first_missing_artifacts",
                message=(
                    f"`{consumer}` requires the section-first C2 artifacts before H3-level validation can proceed; "
                    f"missing: {', '.join(missing)}."
                ),
            )
        )
    if empty:
        issues.append(
            QualityIssue(
                code="section_first_empty_artifacts",
                message=(
                    f"`{consumer}` requires non-empty section-first C2 artifacts before H3-level validation can proceed; "
                    f"empty: {', '.join(empty)}."
                ),
            )
        )
    return issues


def _parse_section_binding_report_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        if cells[0].lower() == "section" and cells[2].lower() == "status":
            continue
        rows.append(
            {
                "section": cells[0],
                "coverage": cells[1],
                "status": cells[2].upper(),
                "recommendation": cells[3],
            }
        )
    return rows


def section_first_cutover_issues(workspace: Path, *, consumer: str, require_stable_h3: bool) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    if structure_mode(workspace) != "section_first":
        return []

    state_rel = "outline/outline_state.jsonl"
    state_path = workspace / state_rel
    if not state_path.exists():
        return [
            QualityIssue(
                code="section_first_missing_outline_state",
                message=f"`{consumer}` requires `{state_rel}` to record section-first cutover state.",
            )
        ]
    records = [r for r in read_jsonl(state_path) if isinstance(r, dict)]
    if not records:
        return [
            QualityIssue(
                code="section_first_empty_outline_state",
                message=f"`{consumer}` requires `{state_rel}` to contain at least one cutover-state record.",
            )
        ]

    latest = records[-1]
    required_fields = [
        "structure_phase",
        "h3_status",
        "approval_status",
        "reroute_target",
        "retry_budget_remaining",
    ]
    nonempty_fields = {
        "structure_phase",
        "h3_status",
        "approval_status",
    }
    missing_fields: list[str] = []
    for key in required_fields:
        if key not in latest:
            missing_fields.append(key)
            continue
        value = latest.get(key)
        if key in nonempty_fields and isinstance(value, str) and not value.strip():
            missing_fields.append(key)
    issues: list[QualityIssue] = []
    if missing_fields:
        issues.append(
            QualityIssue(
                code="section_first_outline_state_missing_fields",
                message=(
                    f"`{state_rel}` is missing section-first cutover fields for `{consumer}`: "
                    f"{', '.join(missing_fields)}."
                ),
            )
        )

    structure_phase = str(latest.get("structure_phase") or "").strip().lower()
    h3_status = str(latest.get("h3_status") or "").strip().lower()
    approval_status = str(latest.get("approval_status") or "").strip().lower()
    reroute_target = str(latest.get("reroute_target") or "").strip()
    reroute_reason = str(latest.get("reroute_reason") or "").strip()
    retry_budget_raw = latest.get("retry_budget_remaining")
    retry_budget_text = str(retry_budget_raw or "").strip()
    retry_budget_value: int | None = None
    if structure_phase in {"binding_blocked", "binding_reroute"}:
        if not reroute_target:
            issues.append(
                QualityIssue(
                    code="section_first_reroute_target_missing",
                    message=(
                        f"`{state_rel}` reports structure_phase={structure_phase} for `{consumer}` but leaves `reroute_target` empty."
                    ),
                )
            )
        if retry_budget_text:
            try:
                retry_budget_value = int(retry_budget_text)
            except Exception:
                issues.append(
                    QualityIssue(
                        code="section_first_retry_budget_invalid",
                        message=(
                            f"`{state_rel}` should record an integer `retry_budget_remaining` for `{consumer}` when section bindings block/reroute "
                            f"(found {retry_budget_text!r})."
                        ),
                    )
                )
            else:
                if retry_budget_value < 0:
                    issues.append(
                        QualityIssue(
                            code="section_first_retry_budget_invalid",
                            message=(
                                f"`{state_rel}` reports a negative `retry_budget_remaining` for `{consumer}` "
                                f"(found {retry_budget_value})."
                            ),
                        )
                    )
        else:
            issues.append(
                QualityIssue(
                    code="section_first_retry_budget_missing",
                    message=(
                        f"`{state_rel}` should record `retry_budget_remaining` for `{consumer}` when section bindings block/reroute."
                    ),
                )
            )
        if approval_status == "approved":
            issues.append(
                QualityIssue(
                    code="section_first_approval_state_inconsistent",
                    message=(
                        f"`{state_rel}` marks `{consumer}` as approved while structure_phase={structure_phase}; approval should not stay effective through a binding block/reroute."
                    ),
                )
            )

    if require_stable_h3:
        if structure_phase == "binding_blocked":
            issues.append(
                QualityIssue(
                    code="section_first_binding_blocked",
                    message=(
                        f"`{consumer}` is blocked by the section-binding gate; latest `outline_state.jsonl` has "
                        f"structure_phase=binding_blocked, reroute_target={reroute_target or '(empty)'}, "
                        f"retry_budget_remaining={retry_budget_text or '(empty)'}"
                        + (f", reroute_reason={reroute_reason}" if reroute_reason else ".")
                    ),
                )
            )
        elif structure_phase == "binding_reroute":
            issues.append(
                QualityIssue(
                    code="section_first_binding_reroute",
                    message=(
                        f"`{consumer}` is waiting on a section-binding reroute; latest `outline_state.jsonl` has "
                        f"structure_phase=binding_reroute, reroute_target={reroute_target or '(empty)'}, "
                        f"retry_budget_remaining={retry_budget_text or '(empty)'}"
                        + (f", reroute_reason={reroute_reason}" if reroute_reason else ".")
                    ),
                )
            )
        elif structure_phase != "decomposed" or h3_status != "stable":
            issues.append(
                QualityIssue(
                    code="section_first_h3_not_stable",
                    message=(
                        f"`{consumer}` requires section-first cutover to be complete before H3-level artifacts are accepted; "
                        f"latest `outline_state.jsonl` has structure_phase={structure_phase or '(empty)'} "
                        f"and h3_status={h3_status or '(empty)'}, expected `decomposed` + `stable`."
                    ),
                )
            )
    return issues



def check_chapter_skeleton(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_yaml

    out_rel = outputs[0] if outputs else "outline/chapter_skeleton.yml"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_chapter_skeleton", message=f"`{out_rel}` does not exist.")]
    data = load_yaml(path)
    if not isinstance(data, list) or not data:
        return [QualityIssue(code="invalid_chapter_skeleton", message=f"`{out_rel}` must be a non-empty YAML list.")]
    missing = 0
    for rec in data:
        if not isinstance(rec, dict):
            missing += 1
            continue
        required = ("id", "title", "rationale", "seed_topics", "target_h3_count")
        if any(not rec.get(key) for key in required):
            missing += 1
            continue
        if not isinstance(rec.get("seed_topics"), list):
            missing += 1
            continue
    if missing:
        return [QualityIssue(code="chapter_skeleton_missing_fields", message=f"`{out_rel}` has {missing} invalid chapter skeleton record(s).")]
    return []


def check_section_bindings(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    bindings_rel = outputs[0] if outputs else "outline/section_bindings.jsonl"
    report_rel = outputs[1] if len(outputs) >= 2 else "outline/section_binding_report.md"
    bindings_path = workspace / bindings_rel
    report_path = workspace / report_rel
    if not bindings_path.exists():
        return [QualityIssue(code="missing_section_bindings", message=f"`{bindings_rel}` does not exist.")]
    records = [r for r in read_jsonl(bindings_path) if isinstance(r, dict)]
    if not records:
        return [QualityIssue(code="invalid_section_bindings", message=f"`{bindings_rel}` has no JSON objects.")]
    missing = 0
    invalid_status = 0
    invalid_semantics = 0
    derived_records: list[dict[str, Any]] = []
    for rec in records:
        required = ("section_id", "section_title", "paper_ids_primary", "paper_ids_support", "coverage_count", "status", "blocking_gaps", "decomposition_recommendation")
        if any(key not in rec for key in required):
            missing += 1
            continue
        if not isinstance(rec.get("paper_ids_primary"), list) or not isinstance(rec.get("paper_ids_support"), list):
            missing += 1
            continue
        if not isinstance(rec.get("blocking_gaps"), list):
            missing += 1
            continue
        status = str(rec.get("status") or "").strip().upper()
        binding_status = str(rec.get("binding_status") or "").strip().upper()
        recommendation = str(rec.get("decomposition_recommendation") or "").strip().lower()
        blocking_gaps = rec.get("blocking_gaps") or []
        if status not in {"PASS", "BLOCKED", "REROUTE"}:
            invalid_status += 1
            continue
        if binding_status and binding_status not in {"PASS", "BLOCKED", "REROUTE"}:
            invalid_status += 1
            continue
        if binding_status and binding_status != status:
            invalid_semantics += 1
            continue
        if recommendation not in {"decompose", "hold_or_merge"}:
            invalid_semantics += 1
            continue
        if status == "PASS" and (blocking_gaps or recommendation != "decompose"):
            invalid_semantics += 1
            continue
        if status == "BLOCKED" and not blocking_gaps:
            invalid_semantics += 1
            continue
        if status == "REROUTE" and (blocking_gaps or recommendation == "decompose"):
            invalid_semantics += 1
            continue
        derived_records.append(
            {
                "section_id": str(rec.get("section_id") or "").strip(),
                "binding_status": binding_status or status,
                "decomposition_recommendation": recommendation,
                "blocking_gaps": list(blocking_gaps),
            }
        )
    if missing:
        return [QualityIssue(code="section_bindings_missing_fields", message=f"`{bindings_rel}` has {missing} invalid section-binding record(s).")]
    if invalid_status:
        return [QualityIssue(code="section_bindings_invalid_status", message=f"`{bindings_rel}` has {invalid_status} record(s) with unknown binding status (expected PASS/BLOCKED/REROUTE).")]
    if invalid_semantics:
        return [QualityIssue(code="section_bindings_invalid_semantics", message=f"`{bindings_rel}` has {invalid_semantics} record(s) where status, blocking_gaps, and decomposition_recommendation disagree.")]
    if not report_path.exists():
        return [QualityIssue(code="missing_section_binding_report", message=f"`{report_rel}` does not exist.")]
    report = report_path.read_text(encoding="utf-8", errors="ignore")
    rows = _parse_section_binding_report_rows(report)
    if "| Section |" not in report or "| Status |" not in report or not rows:
        return [QualityIssue(code="invalid_section_binding_report", message=f"`{report_rel}` is missing the section binding summary table.")]
    by_section_id: dict[str, dict[str, Any]] = {}
    for rec in derived_records:
        section_id = str(rec.get("section_id") or "").strip()
        if section_id:
            by_section_id[section_id] = rec
    if len(rows) != len(derived_records):
        return [
            QualityIssue(
                code="section_binding_report_row_mismatch",
                message=(
                    f"`{report_rel}` should report one status row per section binding "
                    f"(report rows={len(rows)}, binding rows={len(derived_records)})."
                ),
            )
        ]
    bad_statuses = sorted({str(row.get("status") or "").strip().upper() for row in rows if str(row.get("status") or "").strip().upper() not in {"PASS", "BLOCKED", "REROUTE"}})
    if bad_statuses:
        return [
            QualityIssue(
                code="section_binding_report_bad_status",
                message=f"`{report_rel}` contains unsupported binding statuses: {', '.join(bad_statuses)}.",
            )
        ]
    inconsistent: list[str] = []
    for row in rows:
        label = str(row.get("section") or "").strip()
        section_id = label.split(" ", 1)[0].strip()
        rec = by_section_id.get(section_id) or {}
        binding_status = str(rec.get("binding_status") or "").strip().upper()
        report_status = str(row.get("status") or "").strip().upper()
        recommendation = str(rec.get("decomposition_recommendation") or "").strip().lower()
        blocking_gaps = rec.get("blocking_gaps") or []
        if binding_status != report_status:
            inconsistent.append(f"{section_id}: report={report_status} jsonl={binding_status or 'missing'}")
            continue
        if report_status == "PASS" and (blocking_gaps or recommendation != "decompose"):
            inconsistent.append(f"{section_id}: PASS with non-decompose semantics")
        if report_status == "BLOCKED" and not blocking_gaps:
            inconsistent.append(f"{section_id}: BLOCKED without blocking_gaps")
        if report_status == "REROUTE" and (blocking_gaps or recommendation == "decompose"):
            inconsistent.append(f"{section_id}: REROUTE without hold_or_merge semantics")
    if inconsistent:
        return [
            QualityIssue(
                code="section_binding_report_drift",
                message=(
                    f"`{bindings_rel}` and `{report_rel}` disagree about section-binding gate state: "
                    f"{', '.join(inconsistent[:6])}."
                ),
            )
        ]
    return []


def check_section_briefs(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    out_rel = outputs[0] if outputs else "outline/section_briefs.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_section_briefs", message=f"`{out_rel}` does not exist.")]
    records = [r for r in read_jsonl(path) if isinstance(r, dict)]
    if not records:
        return [QualityIssue(code="invalid_section_briefs", message=f"`{out_rel}` has no JSON objects.")]
    missing = 0
    for rec in records:
        required = ("section_id", "section_title", "section_rationale", "contrast_lens", "must_cover", "target_h3_count", "subsection_seeds", "status", "decomposition_recommendation", "blocking_gaps")
        if any(key not in rec for key in required):
            missing += 1
            continue
        if not isinstance(rec.get("contrast_lens"), list) or not isinstance(rec.get("must_cover"), list) or not isinstance(rec.get("subsection_seeds"), list) or not isinstance(rec.get("blocking_gaps"), list):
            missing += 1
            continue
        status = str(rec.get("status") or "").strip().upper()
        binding_status = str(rec.get("binding_status") or "").strip().upper()
        recommendation = str(rec.get("decomposition_recommendation") or "").strip().lower()
        blocking_gaps = rec.get("blocking_gaps") or []
        if status not in {"PASS", "BLOCKED", "REROUTE"}:
            missing += 1
            continue
        if binding_status and binding_status not in {"PASS", "BLOCKED", "REROUTE"}:
            missing += 1
            continue
        if binding_status and status != binding_status:
            missing += 1
            continue
        if recommendation not in {"decompose", "hold_or_merge"}:
            missing += 1
            continue
        if status == "PASS" and (blocking_gaps or recommendation != "decompose"):
            missing += 1
            continue
        if status == "BLOCKED" and not blocking_gaps:
            missing += 1
            continue
        if status == "REROUTE" and (blocking_gaps or recommendation == "decompose"):
            missing += 1
            continue
    if missing:
        return [QualityIssue(code="section_briefs_missing_fields", message=f"`{out_rel}` has {missing} invalid section brief record(s).")]
    return []
