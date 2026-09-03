from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, TextIO

from research_harness import (
    Loop,
    LoopArtifact,
    LoopFault,
    LoopInspection,
    LoopKind,
    LoopQualitySignal,
    LoopResult,
    LoopState,
    Continue,
    Decide,
    Start,
)
from research_harness.workflows import (
    WorkflowContractError,
    WorkflowDefinition,
    load_workflow_definition,
)

if TYPE_CHECKING:
    from research_harness.migration import WorkflowParityReport


_EXIT_OK = 0
_EXIT_BLOCKED = 1
_EXIT_ERROR = 2


class CLIUsageError(ValueError):
    """An argparse usage error retained for output-mode-aware rendering."""

    def __init__(self, parser: argparse.ArgumentParser, message: str) -> None:
        self.parser = parser
        super().__init__(message)


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise CLIUsageError(self, message)


def main(argv: Sequence[str] | None = None) -> int:
    """Inspect contracts or work on one Loop through the versionless Interface."""

    arguments = tuple(sys.argv[1:] if argv is None else argv)
    json_output = _json_output_requested(arguments)
    parser = _build_parser()
    try:
        args = parser.parse_args(arguments)
    except CLIUsageError as exc:
        if json_output:
            return _emit_error(exc, json_output=True)
        argparse.ArgumentParser.error(exc.parser, str(exc))
    try:
        return int(args.handler(args))
    except (LoopFault, WorkflowContractError) as exc:
        return _emit_error(exc, json_output=args.json)
    except (OSError, TypeError, ValueError) as exc:
        return _emit_error(exc, json_output=args.json)


def _build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="research-harness",
        description=(
            "Work on a challengeable research Loop or inspect private Recipe contracts. "
            "The stable rh executable remains on its guarded legacy path during migration."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    case = commands.add_parser(
        "loop",
        help="Work, decide, or read one self-correcting research Run.",
    )
    case_commands = case.add_subparsers(dest="case_command", required=True)

    work = case_commands.add_parser(
        "work",
        help="Start a Run or continue it to the next meaningful stop.",
    )
    work.add_argument("--workspace", type=Path, required=True)
    work.add_argument(
        "--goal",
        dest="question",
        metavar="GOAL",
        help="Research goal for a new Run.",
    )
    work.add_argument(
        "--kind",
        choices=tuple(kind.value for kind in LoopKind),
        help="Requested result kind for a new Run.",
    )
    work.add_argument(
        "--format",
        dest="formats",
        action="append",
        default=[],
        help="Requested result format; currently only survey pdf/latex is explicit.",
    )
    work.add_argument("--case-id", default="")
    _add_repository(work)
    _add_json(work)
    work.set_defaults(handler=_case_work)

    show = case_commands.add_parser(
        "show",
        help="Read the current Loop without mutating it or requiring the repository.",
    )
    show.add_argument("--workspace", type=Path, required=True)
    show.add_argument(
        "--details",
        action="store_true",
        help="Include bounded private-execution counts.",
    )
    _add_json(show)
    show.set_defaults(handler=_case_show)

    decide = case_commands.add_parser(
        "decide",
        help="Apply the current checked Decision basis, then continue working.",
    )
    decide.add_argument("--workspace", type=Path, required=True)
    _add_repository(decide)
    _add_json(decide)
    decide.set_defaults(handler=_case_decide)

    workflow = commands.add_parser(
        "workflow",
        help="Maintainer-only inspection of private Recipe contracts.",
    )
    workflow_commands = workflow.add_subparsers(dest="workflow_command", required=True)

    inspect = workflow_commands.add_parser(
        "inspect", help="Load, validate, and summarize one Workflow contract."
    )
    _add_workflow_source_arguments(inspect)
    inspect.set_defaults(handler=_workflow_inspect)

    parity = workflow_commands.add_parser(
        "parity", help="Compare the typed contract with the legacy read model."
    )
    _add_workflow_source_arguments(parity)
    parity.set_defaults(handler=_workflow_parity)
    return parser


def _add_repository(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repository",
        "--repo-root",
        dest="repository",
        type=Path,
        default=Path.cwd(),
        help="Research Harness source checkout (defaults to current directory).",
    )


def _add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one machine-readable JSON object.",
    )


def _add_workflow_source_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("pipeline", help="Path to a pipelines/*.pipeline.md contract.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        help="Repository root used to resolve a relative Pipeline and units_template.",
    )
    _add_json(parser)


def _case_work(args: argparse.Namespace) -> int:
    starting = any(
        (
            args.question is not None,
            args.kind is not None,
            bool(args.formats),
            bool(args.case_id),
        )
    )
    if starting and (args.question is None or args.kind is None):
        raise LoopFault(
            "invalid_request",
            "Starting a Run requires both --goal and --kind; omit all start options to continue.",
        )
    intent: Start | Continue
    if starting:
        intent = Start(
            goal=args.question,
            kind=LoopKind(args.kind),
            formats=tuple(args.formats),
            case_id=args.case_id,
        )
    else:
        intent = Continue()
    result = Loop.open(args.workspace, repository=args.repository).advance(intent)
    return _emit_case_result(result, json_output=args.json)


def _case_decide(args: argparse.Namespace) -> int:
    result = Loop.open(args.workspace, repository=args.repository).advance(Decide())
    return _emit_case_result(result, json_output=args.json)


def _case_show(args: argparse.Namespace) -> int:
    inspection = Loop.open(args.workspace).inspect(details=args.details)
    if args.json:
        _write_json(
            {
                "schema": "research-harness.case-inspection/v1",
                "ok": inspection.state is not LoopState.BLOCKED,
                "inspection": _case_inspection_payload(
                    inspection,
                    include_details=args.details,
                ),
            },
            stream=sys.stdout,
        )
    else:
        print(_render_case_inspection(inspection, include_details=args.details))
    return _EXIT_BLOCKED if inspection.state is LoopState.BLOCKED else _EXIT_OK


def _emit_case_result(result: LoopResult, *, json_output: bool) -> int:
    blocked = result.state is LoopState.BLOCKED
    if json_output:
        _write_json(
            {
                "schema": "research-harness.case-result/v1",
                "ok": not blocked,
                "state": result.state.value,
                "issues": list(result.issues),
                "inspection": _case_inspection_payload(
                    result.inspection,
                    include_details=False,
                ),
            },
            stream=sys.stdout,
        )
    else:
        print(_render_case_inspection(result.inspection, include_details=False))
    return _EXIT_BLOCKED if blocked else _EXIT_OK


def _case_inspection_payload(
    inspection: LoopInspection,
    *,
    include_details: bool,
) -> dict[str, object]:
    details: dict[str, object] | None = None
    if include_details and inspection.details is not None:
        item = inspection.details
        details = {
            "recipe": item.workflow or None,
            "engine_status": item.status or None,
            "state_version": item.version,
            "steps": {
                "total": item.steps_total,
                "completed": item.steps_completed,
                "blocked": item.steps_blocked,
            },
            "attempts": item.attempts,
            "completions": item.completions,
        }
    return {
        "workspace": str(inspection.workspace),
        "state": inspection.state.value,
        "case_id": inspection.case_id or None,
        "question": inspection.question or None,
        "kind": inspection.kind.value if inspection.kind is not None else None,
        "normalized_claims_available": inspection.normalized_claims_available,
        "quality": {
            "execution_integrity": _quality_payload(
                inspection.quality.execution_integrity
            ),
            "contract_acceptance": _quality_payload(
                inspection.quality.contract_acceptance
            ),
            "research_quality": _quality_payload(inspection.quality.research_quality),
        },
        "views": [_case_artifact_payload(item) for item in inspection.views],
        "claim_sources": [
            _case_artifact_payload(item) for item in inspection.claim_sources
        ],
        "evidence_sources": [
            _case_artifact_payload(item) for item in inspection.evidence_sources
        ],
        "decision_sources": [
            _case_artifact_payload(item) for item in inspection.decision_sources
        ],
        "pending_decision": (
            {
                "prompt": inspection.pending_decision.prompt,
                "reviewed_artifacts": [
                    _case_artifact_payload(item)
                    for item in inspection.pending_decision.reviewed_artifacts
                ],
            }
            if inspection.pending_decision is not None
            else None
        ),
        "next_action": inspection.next_action,
        "issues": list(inspection.issues),
        "details": details,
    }


def _quality_payload(signal: LoopQualitySignal) -> dict[str, str]:
    return {
        "status": signal.status.value,
        "explanation": signal.explanation,
    }


def _case_artifact_payload(artifact: LoopArtifact) -> dict[str, object]:
    return {
        "path": artifact.path,
        "role": artifact.role,
        "exists": artifact.exists,
        "sha256": artifact.sha256,
        "size": artifact.size,
    }


def _render_case_inspection(
    inspection: LoopInspection,
    *,
    include_details: bool,
) -> str:
    label = inspection.kind.value if inspection.kind is not None else "unbound"
    lines = [f"Loop {label} · {inspection.state.value}"]
    if inspection.question:
        lines.append(f"Question: {inspection.question}")
    if inspection.case_id:
        lines.append(f"Loop ID: {inspection.case_id}")
    lines.extend(
        (
            "Quality:",
            _render_quality(
                "Execution integrity", inspection.quality.execution_integrity
            ),
            _render_quality(
                "Contract acceptance", inspection.quality.contract_acceptance
            ),
            _render_quality("Research quality", inspection.quality.research_quality),
            "Normalized Claims: unavailable (projection phase)",
        )
    )
    _append_artifacts(lines, "Views", inspection.views)
    _append_artifacts(lines, "Claim sources", inspection.claim_sources)
    _append_artifacts(lines, "Evidence sources", inspection.evidence_sources)
    _append_artifacts(lines, "Decision sources", inspection.decision_sources)
    if inspection.pending_decision is not None:
        lines.append(f"Needs you: {inspection.pending_decision.prompt}")
        _append_artifacts(
            lines,
            "Review basis",
            inspection.pending_decision.reviewed_artifacts,
        )
    if inspection.issues:
        lines.append("Issues:")
        lines.extend(f"  - {issue}" for issue in inspection.issues)
    if include_details and inspection.details is not None:
        details = inspection.details
        lines.extend(
            (
                "Private execution:",
                f"  Recipe: {details.workflow or 'unknown'}",
                f"  Engine status: {details.status or 'unknown'}",
                f"  State version: {details.version}",
                "  Steps: "
                f"{details.steps_completed}/{details.steps_total} completed, "
                f"{details.steps_blocked} blocked",
                f"  Attempts / completions: {details.attempts} / {details.completions}",
            )
        )
    if inspection.pending_decision is None:
        prefix = "Needs you" if inspection.state is LoopState.NEEDS_DECISION else "Next"
        lines.append(f"{prefix}: {inspection.next_action}")
    return "\n".join(lines)


def _render_quality(label: str, signal: LoopQualitySignal) -> str:
    return f"  {label}: {signal.status.value} — {signal.explanation}"


def _append_artifacts(
    lines: list[str],
    label: str,
    artifacts: tuple[LoopArtifact, ...],
) -> None:
    if not artifacts:
        return
    lines.append(f"{label}:")
    for artifact in artifacts:
        if artifact.exists:
            digest = (artifact.sha256 or "")[:12]
            details = f"present · {digest} · {artifact.size or 0} bytes"
        else:
            details = "missing"
        lines.append(f"  - {artifact.path}: {details}")


def _workflow_inspect(args: argparse.Namespace) -> int:
    workflow = _load_workflow(args)
    if args.json:
        _write_json(_workflow_payload(workflow), stream=sys.stdout)
    else:
        print(_render_workflow_summary(workflow))
    return _EXIT_OK


def _workflow_parity(args: argparse.Namespace) -> int:
    from research_harness.migration import check_workflow_legacy_parity

    workflow = _load_workflow(args)
    report = check_workflow_legacy_parity(workflow)
    if args.json:
        _write_json(
            {
                "schema": "research-harness.workflow-parity/v1",
                "ok": report.matches,
                "workflow": report.workflow,
                "pipeline_source": str(report.pipeline_source),
                "units_source": str(report.units_source),
                "checked_fields": list(report.checked_fields),
                "matches": report.matches,
                "differences": [
                    {
                        "field": difference.field,
                        "legacy": _json_value(difference.legacy_value),
                        "typed": _json_value(difference.typed_value),
                    }
                    for difference in report.differences
                ],
            },
            stream=sys.stdout,
        )
    else:
        print(_render_parity_summary(report))
    return _EXIT_OK if report.matches else _EXIT_BLOCKED


def _load_workflow(args: argparse.Namespace) -> WorkflowDefinition:
    repo_root = args.repo_root.expanduser().resolve() if args.repo_root else None
    pipeline = Path(args.pipeline).expanduser()
    if not pipeline.is_absolute() and repo_root is not None:
        pipeline = repo_root / pipeline
    return load_workflow_definition(pipeline, repo_root=repo_root)


def _workflow_payload(workflow: WorkflowDefinition) -> dict[str, object]:
    return {
        "schema": "research-harness.workflow-inspect/v1",
        "ok": True,
        "workflow": {
            "name": workflow.name,
            "version": workflow.version,
            "profile": workflow.profile,
            "contract_model": workflow.contract_model,
            "variant_of": workflow.variant_of or None,
            "pipeline_source": str(workflow.source),
            "units_source": str(workflow.units_source),
            "units_template": workflow.units_template,
            "checkpoints": list(workflow.default_checkpoints),
            "target_artifacts": list(workflow.target_artifacts),
            "case_contract": {
                "kind": workflow.case_contract.kind,
                "views": list(workflow.case_contract.views),
                "claim_sources": list(workflow.case_contract.claim_sources),
                "evidence_sources": list(workflow.case_contract.evidence_sources),
                "decision_sources": list(workflow.case_contract.decision_sources),
            },
            "skills": list(workflow.skills),
            "checks": list(workflow.checks),
            "dag": {
                unit_id: list(dependencies)
                for unit_id, dependencies in workflow.dag.items()
            },
            "stages": [
                {
                    "id": stage.id,
                    "title": stage.title,
                    "checkpoint": stage.checkpoint,
                    "mode": stage.mode,
                    "required_skills": list(stage.required_skills),
                    "optional_skills": list(stage.optional_skills),
                    "produces": list(stage.produces),
                    "human_checkpoint": _json_value(stage.human_checkpoint),
                }
                for stage in workflow.stages
            ],
            "units": [
                {
                    "id": unit.id,
                    "title": unit.title,
                    "type": unit.type,
                    "skill": unit.skill,
                    "inputs": list(unit.inputs),
                    "outputs": list(unit.outputs),
                    "acceptance": unit.acceptance,
                    "checkpoint": unit.checkpoint,
                    "status": unit.status,
                    "depends_on": list(unit.depends_on),
                    "owner": unit.owner,
                }
                for unit in workflow.units
            ],
        },
    }


def _render_workflow_summary(workflow: WorkflowDefinition) -> str:
    edge_count = sum(len(dependencies) for dependencies in workflow.dag.values())
    lines = [
        f"Private Recipe {workflow.name} v{workflow.version}",
        f"Profile: {workflow.profile}",
        f"Pipeline: {workflow.source}",
        f"UNITS: {workflow.units_source}",
        f"Loop projection: {workflow.case_contract.kind} "
        f"({len(workflow.case_contract.views)} view(s))",
        "Checkpoints: " + ", ".join(workflow.default_checkpoints),
        f"Stages: {len(workflow.stages)}",
    ]
    lines.extend(
        f"  {stage.id} {stage.title}: {len(stage.required_skills)} required skill(s), "
        f"{len(stage.produces)} output(s)"
        for stage in workflow.stages
    )
    lines.extend(
        (
            f"Units: {len(workflow.units)} ({edge_count} dependency edge(s))",
            f"Skills ({len(workflow.skills)}): " + ", ".join(workflow.skills),
            f"Required checks ({len(workflow.checks)}): "
            + (", ".join(workflow.checks) or "none"),
            f"Target artifacts ({len(workflow.target_artifacts)}):",
        )
    )
    lines.extend(f"  {artifact}" for artifact in workflow.target_artifacts)
    return "\n".join(lines)


def _render_parity_summary(report: WorkflowParityReport) -> str:
    if report.matches:
        return (
            f"PASS {report.workflow}: legacy and typed readers match across "
            f"{len(report.checked_fields)} projections "
            f"({', '.join(report.checked_fields)})."
        )
    lines = [f"FAIL {report.workflow}: {len(report.differences)} parity difference(s)."]
    for difference in report.differences:
        legacy = json.dumps(_json_value(difference.legacy_value), ensure_ascii=False)
        typed = json.dumps(_json_value(difference.typed_value), ensure_ascii=False)
        lines.append(f"  {difference.field}: legacy={legacy} typed={typed}")
    return "\n".join(lines)


def _emit_error(error: Exception, *, json_output: bool) -> int:
    issues: list[dict[str, object]] = []
    if isinstance(error, LoopFault):
        issues.extend(
            {
                "code": error.code,
                "message": issue,
                "source": None,
                "field": None,
            }
            for issue in error.issues
        )
        if not issues:
            issues.append(
                {
                    "code": error.code,
                    "message": error.message,
                    "source": None,
                    "field": None,
                }
            )
    elif isinstance(error, WorkflowContractError):
        issues.extend(
            {
                "code": issue.code,
                "message": issue.message,
                "source": str(issue.source) if issue.source is not None else None,
                "field": issue.field or None,
            }
            for issue in error.issues
        )
    else:
        issues.append(
            {
                "code": _generic_error_code(error),
                "message": str(error),
                "source": _error_filename(error),
                "field": None,
            }
        )
    payload = {
        "schema": "research-harness.error/v1",
        "ok": False,
        "error": {
            "type": type(error).__name__,
            "code": _generic_error_code(error),
            "message": str(error),
            "issues": issues,
        },
    }
    if json_output:
        _write_json(payload, stream=sys.stdout)
    else:
        print(f"ERROR {type(error).__name__}", file=sys.stderr)
        for issue in issues:
            location = ":".join(
                str(value) for value in (issue["source"], issue["field"]) if value
            )
            prefix = f"{location}: " if location else ""
            print(
                f"  [{issue['code']}] {prefix}{issue['message']}",
                file=sys.stderr,
            )
    return _EXIT_ERROR


def _generic_error_code(error: Exception) -> str:
    if isinstance(error, LoopFault):
        return error.code
    if isinstance(error, CLIUsageError):
        return "cli_usage_error"
    if isinstance(error, FileNotFoundError):
        return "source_not_found"
    if isinstance(error, PermissionError):
        return "source_permission_denied"
    if isinstance(error, OSError):
        return "source_io_error"
    if isinstance(error, TypeError):
        return "contract_type_error"
    return "contract_value_error"


def _error_filename(error: Exception) -> str | None:
    filename = getattr(error, "filename", None)
    return str(filename) if filename else None


def _write_json(payload: Mapping[str, object], *, stream: TextIO) -> None:
    json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
    stream.write("\n")


def _json_output_requested(argv: Sequence[str]) -> bool:
    return any(argument == "--json" for argument in argv)


def _json_value(value: Any) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return [_json_value(item) for item in sorted(value, key=repr)]
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value
