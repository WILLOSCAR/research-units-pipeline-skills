from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from tooling.common import (
    UnitsTable,
    atomic_write_text,
    decisions_has_approval,
    ensure_dir,
    now_iso_seconds,
    parse_semicolon_list,
    pipeline_cli_command,
    set_decisions_approval,
    update_status_field,
    update_status_log,
)
from tooling.completion import (
    commit_unit_completion,
    load_declared_scorecard,
    scorecard_failure as declared_scorecard_failure,
)
from tooling.harness import write_unit_manifest
from tooling.run_state import (
    capture_checkpoint_review_basis,
    checkpoint_completion_approval_issue,
    checkpoint_approval_recorded,
    checkpoint_approval_status,
    ensure_run_state,
    finish_attempt,
    record_failure,
    record_decision,
    revoke_checkpoint_approval,
    start_attempt,
)


@dataclass(frozen=True)
class RunResult:
    unit_id: str | None
    status: str
    message: str


def _file_generation_marker(path: Path) -> tuple[int, int, int, int] | None:
    if not path.is_file():
        return None
    stat = path.stat()
    return (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _pinned_pipeline_contract_expected(workspace: Path) -> bool:
    """Distinguish a tampered v2 contract from a legacy contract-free Workspace."""

    lock_path = workspace / ".harness" / "harness.lock.json"
    if not lock_path.exists():
        return False
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True
    if not isinstance(lock, dict) or lock.get("schema") != "harness-lock.v2":
        return False
    pipeline = lock.get("pipeline")
    if not isinstance(pipeline, dict):
        return True
    return any(
        str(pipeline.get(key) or "").strip()
        for key in ("path", "sha256", "snapshot_path", "snapshot_sha256")
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

    ensure_run_state(workspace=workspace, repo_root=repo_root, recover_stale_doing=True)
    table = UnitsTable.load(units_path)
    _reopen_stale_checkpoint_units(workspace=workspace, table=table)

    runnable_idx = _find_first_runnable(table)
    if runnable_idx is None:
        return RunResult(unit_id=None, status="IDLE", message="No runnable unit found")

    row = table.rows[runnable_idx]
    unit_id = row.get("unit_id", "").strip()
    skill = row.get("skill", "").strip()
    owner = row.get("owner", "").strip().upper()
    inputs = parse_semicolon_list(row.get("inputs"))

    attempt_id = start_attempt(
        workspace=workspace,
        repo_root=repo_root,
        unit_id=unit_id,
        skill=skill,
        inputs=inputs,
        execution_mode="process",
    )
    row["status"] = "DOING"
    table.save(units_path)
    update_status_log(status_path, f"{now_iso_seconds()} {unit_id} DOING {skill}")

    auto_approve_set = {str(x or "").strip().upper() for x in (auto_approve or set()) if str(x or "").strip()}

    if owner == "HUMAN":
        checkpoint = row.get("checkpoint", "").strip()
        auto_approval_error = ""
        if (
            checkpoint
            and decisions_has_approval(workspace / "DECISIONS.md", checkpoint)
            and checkpoint_approval_recorded(workspace=workspace, checkpoint=checkpoint)
        ):
            completion = commit_unit_completion(
                workspace=workspace,
                repo_root=repo_root,
                unit_id=unit_id,
                attempt_id=attempt_id,
                exit_code=0,
                message=f"HUMAN approved {checkpoint}",
            )
            _refresh_status_checkpoint(status_path, UnitsTable.load(units_path))
            return RunResult(unit_id=unit_id, status=completion.status, message=completion.message)

        auto_approval_allowed = True
        if checkpoint and checkpoint.upper() in auto_approve_set:
            from tooling.common import load_workspace_pipeline_spec

            active_spec = load_workspace_pipeline_spec(workspace)
            if active_spec is None and _pinned_pipeline_contract_expected(workspace):
                auto_approval_allowed = False
                auto_approval_error = "the pinned Pipeline contract is unavailable or invalid"
            elif (
                active_spec is not None
                and active_spec.name == "idea-brainstorm"
                and checkpoint.upper() == "C2"
            ):
                auto_approval_allowed = False

        if checkpoint and checkpoint.upper() in auto_approve_set and auto_approval_allowed:
            try:
                review_basis = capture_checkpoint_review_basis(
                    workspace=workspace,
                    checkpoint=checkpoint,
                )
            except ValueError as exc:
                review_basis = None
                auto_approval_allowed = False
                auto_approval_error = str(exc)
            else:
                auto_approval_error = ""

        if checkpoint and checkpoint.upper() in auto_approve_set and auto_approval_allowed:
            set_decisions_approval(workspace / "DECISIONS.md", checkpoint, approved=True)
            record_decision(
                workspace=workspace,
                action="checkpoint.auto_approved",
                subject=checkpoint,
                decision="approved",
                actor={"kind": "harness", "id": "auto-approval"},
                note=f"Auto-approved while executing {unit_id}.",
                review_basis=review_basis,
            )
            completion = commit_unit_completion(
                workspace=workspace,
                repo_root=repo_root,
                unit_id=unit_id,
                attempt_id=attempt_id,
                exit_code=0,
                message=f"AUTO approved {checkpoint}",
            )
            _refresh_status_checkpoint(status_path, UnitsTable.load(units_path))
            return RunResult(unit_id=unit_id, status=completion.status, message=completion.message)

        row["status"] = "BLOCKED"
        table.save(units_path)
        update_status_log(status_path, f"{now_iso_seconds()} {unit_id} BLOCKED (await HUMAN approval {checkpoint})")
        _refresh_status_checkpoint(status_path, table)
        finish_attempt(
            workspace=workspace,
            attempt_id=attempt_id,
            unit_id=unit_id,
            skill=skill,
            status="WAITING_HUMAN",
            exit_code=None,
            message=f"Await HUMAN approval {checkpoint}",
        )
        suffix = (
            " with an explicit focus selection; idea-brainstorm C2 cannot be auto-approved"
            if checkpoint and checkpoint.upper() in auto_approve_set and not auto_approval_allowed
            else ""
        )
        if checkpoint and checkpoint.upper() in auto_approve_set and not auto_approval_allowed and auto_approval_error:
            suffix = f"; auto-approval review basis is invalid: {auto_approval_error}"
        return RunResult(
            unit_id=unit_id,
            status="BLOCKED",
            message=f"Await HUMAN approval {checkpoint}{suffix} in DECISIONS.md",
        )

    script_path = repo_root / ".codex" / "skills" / skill / "scripts" / "run.py"
    if not script_path.exists():
        row["status"] = "BLOCKED"
        table.save(units_path)
        skill_md = f".codex/skills/{skill}/SKILL.md"
        update_status_log(
            status_path,
            (
                f"{now_iso_seconds()} {unit_id} BLOCKED "
                f"(no script for {skill}; run manually per {skill_md}, then commit with pipeline.py mark)"
            ),
        )
        _refresh_status_checkpoint(status_path, table)
        record_failure(
            workspace=workspace,
            unit_id=unit_id,
            attempt_id=attempt_id,
            failure_type="missing_skill_adapter",
            symptom=f"Unit cannot execute automatically because `{skill}` has no run.py adapter.",
            causal_behavior="The unit entered execution but no deterministic skill adapter was available.",
            harness_mechanism="The executor dispatches scripted skills through `.codex/skills/<skill>/scripts/run.py`.",
            repair_surface=[skill_md, "UNITS.csv"],
        )
        finish_attempt(
            workspace=workspace,
            attempt_id=attempt_id,
            unit_id=unit_id,
            skill=skill,
            status="FAILED_TERMINAL",
            exit_code=None,
            message=f"No executable script for skill '{skill}'.",
        )
        return RunResult(
            unit_id=unit_id,
            status="BLOCKED",
            message=(
                f"No executable script for skill '{skill}'. "
                f"Run it manually by following `{skill_md}`, write the required outputs, "
                f"then mark the unit DONE (e.g., `{pipeline_cli_command('mark', workspace=workspace, extra_args=('--unit-id', unit_id, '--status', 'DONE'))}`)."
            ),
        )

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

    log_rel = f"output/unit_logs/{unit_id}.{skill}.{attempt_id}.log"
    log_path = workspace / log_rel
    adapter_rel = str(script_path.relative_to(repo_root))
    scorecard_markers_before = {
        relpath: _file_generation_marker(workspace / relpath)
        for relpath in outputs
        if relpath.upper().endswith("_SCORECARD.JSON")
    }
    process_started = time.perf_counter()

    try:
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
        elapsed_ms = (time.perf_counter() - process_started) * 1000
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
        elapsed_ms = (time.perf_counter() - process_started) * 1000
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
        record_failure(
            workspace=workspace,
            unit_id=unit_id,
            attempt_id=attempt_id,
            failure_type="exec_error",
            symptom=f"The skill process could not be started: {type(exc).__name__}: {exc}",
            causal_behavior="The executor failed before a process result was available.",
            harness_mechanism="The local subprocess adapter raised while dispatching the skill script.",
            repair_surface=["tooling/executor.py", f".codex/skills/{skill}/scripts/run.py"],
            severity="high",
        )
        finish_attempt(
            workspace=workspace,
            attempt_id=attempt_id,
            unit_id=unit_id,
            skill=skill,
            status="FAILED_TERMINAL",
            exit_code=None,
            message=str(exc),
            execution={
                "adapter": adapter_rel,
                "elapsed_ms": elapsed_ms,
            },
        )
        return RunResult(unit_id=unit_id, status="BLOCKED", message=str(exc))

    execution = {
        "adapter": adapter_rel,
        "elapsed_ms": elapsed_ms,
        "stdout_chars": len(completed.stdout or ""),
        "stderr_chars": len(completed.stderr or ""),
        "log_path": log_rel if log_path.exists() else "",
    }

    def record_manifest(status: str) -> None:
        try:
            write_unit_manifest(
                workspace=workspace,
                unit_id=unit_id,
                skill=skill,
                outputs=outputs,
                exit_code=int(completed.returncode),
                status=status,
                attempt_id=attempt_id,
                repo_root=repo_root,
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
    scorecard = load_declared_scorecard(workspace, outputs)
    scorecard_failure = None
    scorecard_is_fresh = False
    if scorecard:
        scorecard_relpath = scorecard.relpath
        scorecard_payload = scorecard.payload
        scorecard_is_fresh = (
            _file_generation_marker(workspace / scorecard_relpath)
            != scorecard_markers_before.get(scorecard_relpath)
        )
        if not scorecard_is_fresh:
            scorecard_failure = {
                "failure_type": "stale_scorecard_output",
                "symptom": (
                    f"Declared scorecard `{scorecard_relpath}` was not created or refreshed by "
                    f"Attempt `{attempt_id}`."
                ),
                "causal_behavior": (
                    "The executor found a scorecard left by an earlier Attempt after the current "
                    "adapter returned."
                ),
                "repair_surface": [
                    scorecard_relpath,
                    f".codex/skills/{skill}/scripts/run.py",
                    "tooling/executor.py",
                ],
                "severity": "high",
            }
        else:
            scorecard_failure = declared_scorecard_failure(scorecard)
        if (
            scorecard_is_fresh
            and not scorecard.validation_errors
            and (completed.returncode != 0 or scorecard_failure is not None)
        ):
            from tooling.run_state import record_evaluation

            record_evaluation(
                workspace=workspace,
                attempt_id=attempt_id,
                unit_id=unit_id,
                skill=skill,
                scorecard_path=scorecard_relpath,
                payload=scorecard_payload,
            )
    if completed.returncode == 0 and not missing and scorecard_failure is None:
        if strict:
            from tooling.quality_gate import (
                check_unit_outputs,
                completion_check_required,
                write_quality_report,
            )
            # Workflow-required checks are owned by the Completion Protocol so
            # default, strict, and manual completion share one commit boundary.
            # Strict mode adds checks for registered Skills that the Workflow
            # has not promoted into its mandatory completion policy.
            if completion_check_required(skill=skill, workspace=workspace):
                issues = []
            else:
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
                record_failure(
                    workspace=workspace,
                    unit_id=unit_id,
                    attempt_id=attempt_id,
                    failure_type="quality_gate_failed",
                    symptom=f"Strict output validation blocked the unit; see `{rel_report}`.",
                    causal_behavior="The skill produced files, but one or more acceptance checks failed.",
                    harness_mechanism="Strict mode evaluates declared outputs before committing the unit as DONE.",
                    repair_surface=[rel_report, f".codex/skills/{skill}/SKILL.md", "tooling/quality_gate.py"],
                )
                finish_attempt(
                    workspace=workspace,
                    attempt_id=attempt_id,
                    unit_id=unit_id,
                    skill=skill,
                    status="FAILED_RETRYABLE",
                    exit_code=int(completed.returncode),
                    outputs=outputs,
                    message=f"Quality gate failed; see {rel_report}",
                    execution=execution,
                )
                reroute_hint = _reroute_hint(workspace)
                return RunResult(
                    unit_id=unit_id,
                    status="BLOCKED",
                    message=f"Quality gate failed; see {rel_report}" + (f"; {reroute_hint}" if reroute_hint else ""),
                )

        resolved_failure_types = {
            "exec_error",
            "missing_outputs",
            "missing_skill_adapter",
            "script_failed",
            "stale_scorecard_output",
        }
        if strict:
            resolved_failure_types.add("quality_gate_failed")
        completion = commit_unit_completion(
            workspace=workspace,
            repo_root=repo_root,
            unit_id=unit_id,
            attempt_id=attempt_id,
            exit_code=int(completed.returncode),
            message="OK",
            resolved_failure_types=resolved_failure_types,
            attempt_execution=execution,
        )
        _refresh_status_checkpoint(status_path, UnitsTable.load(units_path))
        return RunResult(unit_id=unit_id, status=completion.status, message=completion.message)

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
        record_failure(
            workspace=workspace,
            unit_id=unit_id,
            attempt_id=attempt_id,
            failure_type="missing_outputs",
            symptom=f"Required outputs were not produced: {', '.join(missing)}",
            causal_behavior="The skill process exited, but its declared artifact contract was incomplete.",
            harness_mechanism="The executor checks declared outputs before delegating success to the Completion Protocol.",
            repair_surface=[f".codex/skills/{skill}/scripts/run.py", "UNITS.csv"],
        )
        finish_attempt(
            workspace=workspace,
            attempt_id=attempt_id,
            unit_id=unit_id,
            skill=skill,
            status="FAILED_RETRYABLE",
            exit_code=int(completed.returncode),
            outputs=outputs,
            message=f"Missing outputs: {', '.join(missing)}",
            execution=execution,
        )
        return RunResult(unit_id=unit_id, status="BLOCKED", message=f"Missing outputs: {', '.join(missing)}" + (f"; see {log_rel}" if log_path.exists() else ""))
    failure_label = "declared scorecard failed" if scorecard_failure else "script failed"
    failure_message = (
        str(scorecard_failure["symptom"])
        if scorecard_failure
        else f"Skill script failed (exit {completed.returncode})"
    )
    update_status_log(status_path, f"{now_iso_seconds()} {unit_id} BLOCKED ({failure_label})")
    scorecard_failure_type = (
        str(scorecard_failure.get("failure_type") or "semantic_quality_gate_failed")
        if scorecard_failure
        else "script_failed"
    )
    _append_run_error(
        workspace=workspace,
        unit_id=unit_id,
        skill=skill,
        kind=scorecard_failure_type,
        message=failure_message,
        log_rel=log_rel if log_path.exists() else None,
    )
    _refresh_status_checkpoint(status_path, table)
    record_failure(
        workspace=workspace,
        unit_id=unit_id,
        attempt_id=attempt_id,
        failure_type=scorecard_failure_type,
        symptom=str(scorecard_failure["symptom"]) if scorecard_failure else f"Skill process exited with code {completed.returncode}.",
        causal_behavior=str(scorecard_failure["causal_behavior"]) if scorecard_failure else "The skill adapter returned a non-zero process result.",
        harness_mechanism="The executor reads declared scorecard failures before classifying a non-zero skill exit." if scorecard_failure else "The executor treats non-zero skill exits as blocked attempts.",
        repair_surface=list(scorecard_failure["repair_surface"]) if scorecard_failure else [f".codex/skills/{skill}/scripts/run.py", log_rel],
        severity=str(scorecard_failure["severity"]) if scorecard_failure else "high",
    )
    finish_attempt(
        workspace=workspace,
        attempt_id=attempt_id,
        unit_id=unit_id,
        skill=skill,
        status="FAILED_RETRYABLE",
        exit_code=int(completed.returncode),
        outputs=outputs,
        message=failure_message,
        execution=execution,
    )
    return RunResult(unit_id=unit_id, status="BLOCKED", message=failure_message + (f"; see {log_rel}" if log_path.exists() else ""))


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


def _reopen_stale_checkpoint_units(*, workspace: Path, table: UnitsTable) -> list[str]:
    """Reopen stale HUMAN gates and invalidate every dependent Unit projection."""

    reopened: list[str] = []
    downstream: list[str] = []
    for row in table.rows:
        if str(row.get("status") or "").strip().upper() != "DONE":
            continue
        issue = checkpoint_completion_approval_issue(workspace=workspace, row=row)
        if not issue:
            continue
        unit_id = str(row.get("unit_id") or "").strip()
        checkpoint = str(row.get("checkpoint") or "").strip()
        approval_status = checkpoint_approval_status(
            workspace=workspace,
            checkpoint=checkpoint,
        )
        row["status"] = "BLOCKED"
        reopened.append(unit_id)
        downstream.extend(invalidate_downstream_units(table, root_unit_id=unit_id))
        table.save(workspace / "UNITS.csv")
        revoke_checkpoint_approval(
            workspace=workspace,
            checkpoint=checkpoint,
            actor_id="approval-revalidator",
            note=(
                f"Reopened {unit_id} before downstream execution because approval was {approval_status}. "
                f"{issue}"
            ),
        )
        update_status_log(
            workspace / "STATUS.md",
            f"{now_iso_seconds()} {unit_id} BLOCKED (checkpoint approval {approval_status}; downstream invalidated)",
        )
    if reopened:
        table.save(workspace / "UNITS.csv")
        _refresh_status_checkpoint(workspace / "STATUS.md", table)
    return [*reopened, *downstream]


def _refresh_status_checkpoint(status_path: Path, table: UnitsTable) -> None:
    checkpoint = _compute_current_checkpoint(table)
    update_status_field(status_path, "Current checkpoint", checkpoint)


def _compute_current_checkpoint(table: UnitsTable) -> str:
    for row in table.rows:
        if row.get("status", "").strip().upper() not in {"DONE", "SKIP"}:
            return (row.get("checkpoint") or "").strip() or "C0"
    return "DONE"


def downstream_unit_ids(table: UnitsTable, *, root_unit_id: str) -> list[str]:
    """Return all transitive downstream dependents of `root_unit_id` in traversal order."""

    root = str(root_unit_id or "").strip()
    if not root:
        return []

    direct_children: dict[str, list[str]] = {}
    for row in table.rows:
        unit_id = str(row.get("unit_id") or "").strip()
        if not unit_id:
            continue
        for dep in parse_semicolon_list(row.get("depends_on")):
            direct_children.setdefault(dep, []).append(unit_id)

    downstream: list[str] = []
    seen: set[str] = set()
    stack = [root]
    while stack:
        current = stack.pop()
        for child_id in direct_children.get(current, []):
            if child_id in seen:
                continue
            seen.add(child_id)
            downstream.append(child_id)
            stack.append(child_id)
    return downstream


def invalidate_downstream_units(table: UnitsTable, *, root_unit_id: str) -> list[str]:
    """Reset all transitive downstream dependents of `root_unit_id` to TODO.

    This is used when a previously satisfied upstream unit is reopened for rerun.
    Keeping downstream units as DONE would otherwise leave stale artifacts in place
    and make later `run` invocations stop too early.
    """

    downstream = set(downstream_unit_ids(table, root_unit_id=root_unit_id))
    affected: list[str] = []
    for row in table.rows:
        unit_id = str(row.get("unit_id") or "").strip()
        if unit_id not in downstream:
            continue
        if str(row.get("status") or "").strip().upper() != "TODO":
            row["status"] = "TODO"
            affected.append(unit_id)
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
