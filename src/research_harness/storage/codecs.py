from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any, TypeVar

from research_harness.domain.errors import HarnessError
from research_harness.domain.model import (
    AcceptanceEvidence,
    ArtifactEvidence,
    AttemptStatus,
    AttemptView,
    CheckpointApprovalView,
    CheckpointReviewBasis,
    CompletionManifest,
    CompletionPhase,
    CompletionView,
    EventView,
    Goal,
    HarnessRevision,
    ManifestStatus,
    Owner,
    RunAggregate,
    RunPlan,
    UnitPlan,
    UnitStatus,
    validate_run_contract,
)

from .errors import StorageCodecError


RUN_AGGREGATE_SCHEMA = "research-harness.run-aggregate/v1"
COMPLETION_MANIFEST_SCHEMA = "research-harness.completion-manifest/v1"

_EnumT = TypeVar("_EnumT", bound=Enum)


def encode_run_aggregate(run: RunAggregate) -> dict[str, object]:
    """Encode every canonical Run field into an explicit versioned JSON object."""

    if not isinstance(run, RunAggregate):
        raise TypeError("run must be a RunAggregate")
    _validate_aggregate(run)
    payload: dict[str, object] = {
        "schema": RUN_AGGREGATE_SCHEMA,
        "id": run.id,
        "plan": _encode_plan(run.plan),
        "revision": _encode_revision(run.revision),
        "unit_status": {
            unit_id: status.value for unit_id, status in sorted(run.unit_status.items())
        },
        "attempts": [_encode_attempt(attempt) for attempt in run.attempts],
        "completions": [
            _encode_completion(completion) for completion in run.completions
        ],
        "approvals": [_encode_approval(approval) for approval in run.approvals],
        "events": [_encode_event(event) for event in run.events],
        "active_attempt_id": run.active_attempt_id,
    }
    decode_run_aggregate(payload)
    return payload


def decode_run_aggregate(payload: Mapping[str, object]) -> RunAggregate:
    """Decode and integrity-check one canonical Run aggregate."""

    obj = _mapping(payload, "Run aggregate")
    _require_schema(obj, RUN_AGGREGATE_SCHEMA, "Run aggregate")
    _require_exact_keys(
        obj,
        {
            "schema",
            "id",
            "plan",
            "revision",
            "unit_status",
            "attempts",
            "completions",
            "approvals",
            "events",
            "active_attempt_id",
        },
        "Run aggregate",
    )
    active_attempt_raw = obj.get("active_attempt_id")
    if active_attempt_raw is not None and not isinstance(active_attempt_raw, str):
        raise StorageCodecError(
            "Run aggregate active_attempt_id must be a string or null."
        )
    status_obj = _mapping(_required(obj, "unit_status"), "unit_status")
    run = RunAggregate(
        id=_string(_required(obj, "id"), "id"),
        plan=_decode_plan(_required(obj, "plan")),
        revision=_decode_revision(_required(obj, "revision")),
        unit_status={
            _string(unit_id, "unit_status key"): _enum(
                UnitStatus, value, f"unit_status[{unit_id!r}]"
            )
            for unit_id, value in status_obj.items()
        },
        attempts=[
            _decode_attempt(value)
            for value in _array(_required(obj, "attempts"), "attempts")
        ],
        completions=[
            _decode_completion(value)
            for value in _array(_required(obj, "completions"), "completions")
        ],
        approvals=[
            _decode_approval(value)
            for value in _array(_required(obj, "approvals"), "approvals")
        ],
        events=[
            _decode_event(value) for value in _array(_required(obj, "events"), "events")
        ],
        active_attempt_id=active_attempt_raw,
    )
    _validate_aggregate(run)
    return run


def encode_completion_manifest(manifest: CompletionManifest) -> dict[str, object]:
    """Encode a Completion Manifest without relying on dataclass internals."""

    if not isinstance(manifest, CompletionManifest):
        raise TypeError("manifest must be a CompletionManifest")
    payload: dict[str, object] = {
        "schema": COMPLETION_MANIFEST_SCHEMA,
        "id": manifest.id,
        "completion_id": manifest.completion_id,
        "run_id": manifest.run_id,
        "unit_id": manifest.unit_id,
        "attempt_id": manifest.attempt_id,
        "status": manifest.status.value,
        "artifacts": [_encode_artifact(item) for item in manifest.artifacts],
        "acceptance": _encode_acceptance(manifest.acceptance),
    }
    decode_completion_manifest(payload)
    return payload


def decode_completion_manifest(payload: Mapping[str, object]) -> CompletionManifest:
    """Decode one versioned Completion Manifest."""

    obj = _mapping(payload, "Completion Manifest")
    _require_schema(obj, COMPLETION_MANIFEST_SCHEMA, "Completion Manifest")
    _require_exact_keys(
        obj,
        {
            "schema",
            "id",
            "completion_id",
            "run_id",
            "unit_id",
            "attempt_id",
            "status",
            "artifacts",
            "acceptance",
        },
        "Completion Manifest",
    )
    manifest = CompletionManifest(
        id=_nonempty_string(_required(obj, "id"), "id"),
        completion_id=_nonempty_string(
            _required(obj, "completion_id"), "completion_id"
        ),
        run_id=_nonempty_string(_required(obj, "run_id"), "run_id"),
        unit_id=_nonempty_string(_required(obj, "unit_id"), "unit_id"),
        attempt_id=_nonempty_string(_required(obj, "attempt_id"), "attempt_id"),
        status=_enum(ManifestStatus, _required(obj, "status"), "status"),
        artifacts=tuple(
            _decode_artifact(value)
            for value in _array(_required(obj, "artifacts"), "artifacts")
        ),
        acceptance=_decode_acceptance(_required(obj, "acceptance")),
    )
    _require_unique(
        (item.path for item in manifest.artifacts), "Manifest Artifact paths"
    )
    return manifest


def _encode_revision(revision: HarnessRevision) -> dict[str, object]:
    return {
        "pipeline_digest": revision.pipeline_digest,
        "kernel_digest": revision.kernel_digest,
        "completion_protocol": revision.completion_protocol,
    }


def _decode_revision(value: object) -> HarnessRevision:
    obj = _mapping(value, "revision")
    return HarnessRevision(
        pipeline_digest=_nonempty_string(
            _required(obj, "pipeline_digest"), "revision.pipeline_digest"
        ),
        kernel_digest=_nonempty_string(
            _required(obj, "kernel_digest"), "revision.kernel_digest"
        ),
        completion_protocol=_nonempty_string(
            _required(obj, "completion_protocol"), "revision.completion_protocol"
        ),
    )


def _encode_goal(goal: Goal) -> dict[str, object]:
    return {
        "id": goal.id,
        "request": goal.request,
        "workflow": goal.workflow,
        "constraints": list(goal.constraints),
        "target_artifacts": list(goal.target_artifacts),
        "success_criteria": list(goal.success_criteria),
        "required_checks": list(goal.required_checks),
    }


def _decode_goal(value: object) -> Goal:
    obj = _mapping(value, "goal")
    return Goal(
        id=_nonempty_string(_required(obj, "id"), "goal.id"),
        request=_string(_required(obj, "request"), "goal.request"),
        workflow=_nonempty_string(_required(obj, "workflow"), "goal.workflow"),
        constraints=_strings(_required(obj, "constraints"), "goal.constraints"),
        target_artifacts=_strings(
            _required(obj, "target_artifacts"), "goal.target_artifacts"
        ),
        success_criteria=_strings(
            _required(obj, "success_criteria"), "goal.success_criteria"
        ),
        required_checks=_strings(
            _required(obj, "required_checks"), "goal.required_checks"
        ),
    )


def _encode_unit(unit: UnitPlan) -> dict[str, object]:
    return {
        "id": unit.id,
        "title": unit.title,
        "skill": unit.skill,
        "depends_on": list(unit.depends_on),
        "inputs": list(unit.inputs),
        "outputs": list(unit.outputs),
        "owner": unit.owner.value,
        "checkpoint": unit.checkpoint,
        "workflow_type": unit.workflow_type,
        "acceptance": unit.acceptance,
    }


def _decode_unit(value: object) -> UnitPlan:
    obj = _mapping(value, "Unit")
    return UnitPlan(
        id=_nonempty_string(_required(obj, "id"), "Unit.id"),
        title=_string(_required(obj, "title"), "Unit.title"),
        skill=_nonempty_string(_required(obj, "skill"), "Unit.skill"),
        depends_on=_strings(_required(obj, "depends_on"), "Unit.depends_on"),
        inputs=_strings(_required(obj, "inputs"), "Unit.inputs"),
        outputs=_strings(_required(obj, "outputs"), "Unit.outputs"),
        owner=_enum(Owner, _required(obj, "owner"), "Unit.owner"),
        checkpoint=_string(_required(obj, "checkpoint"), "Unit.checkpoint"),
        workflow_type=_string(_required(obj, "workflow_type"), "Unit.workflow_type"),
        acceptance=_string(_required(obj, "acceptance"), "Unit.acceptance"),
    )


def _encode_plan(plan: RunPlan) -> dict[str, object]:
    return {
        "goal": _encode_goal(plan.goal),
        "units": [_encode_unit(unit) for unit in plan.units],
    }


def _decode_plan(value: object) -> RunPlan:
    obj = _mapping(value, "plan")
    return RunPlan(
        goal=_decode_goal(_required(obj, "goal")),
        units=tuple(
            _decode_unit(unit) for unit in _array(_required(obj, "units"), "plan.units")
        ),
    )


def _encode_artifact(artifact: ArtifactEvidence) -> dict[str, object]:
    return {
        "path": artifact.path,
        "sha256": artifact.sha256,
        "size": artifact.size,
        "normalization": artifact.normalization,
    }


def _decode_artifact(value: object) -> ArtifactEvidence:
    obj = _mapping(value, "Artifact evidence")
    size = _integer(_required(obj, "size"), "Artifact.size")
    if size < 0:
        raise StorageCodecError("Artifact.size must not be negative.")
    digest = _nonempty_string(_required(obj, "sha256"), "Artifact.sha256")
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise StorageCodecError("Artifact.sha256 must be a lowercase SHA-256 digest.")
    return ArtifactEvidence(
        path=_nonempty_string(_required(obj, "path"), "Artifact.path"),
        sha256=digest,
        size=size,
        normalization=_nonempty_string(
            _required(obj, "normalization"), "Artifact.normalization"
        ),
    )


def _encode_review_basis(basis: CheckpointReviewBasis) -> dict[str, object]:
    return {
        "schema": basis.schema,
        "checkpoint": basis.checkpoint,
        "unit_id": basis.unit_id,
        "artifacts": [_encode_artifact(item) for item in basis.artifacts],
        "approved": basis.approved,
    }


def _decode_review_basis(value: object) -> CheckpointReviewBasis:
    obj = _mapping(value, "Checkpoint review basis")
    approved = _boolean(_required(obj, "approved"), "review_basis.approved")
    return CheckpointReviewBasis(
        schema=_nonempty_string(_required(obj, "schema"), "review_basis.schema"),
        checkpoint=_nonempty_string(
            _required(obj, "checkpoint"), "review_basis.checkpoint"
        ),
        unit_id=_nonempty_string(_required(obj, "unit_id"), "review_basis.unit_id"),
        artifacts=tuple(
            _decode_artifact(item)
            for item in _array(_required(obj, "artifacts"), "review_basis.artifacts")
        ),
        approved=approved,
    )


def _encode_acceptance(acceptance: AcceptanceEvidence) -> dict[str, object]:
    return {
        "passed": acceptance.passed,
        "checks": list(acceptance.checks),
        "issues": list(acceptance.issues),
    }


def _decode_acceptance(value: object) -> AcceptanceEvidence:
    obj = _mapping(value, "Acceptance evidence")
    return AcceptanceEvidence(
        passed=_boolean(_required(obj, "passed"), "acceptance.passed"),
        checks=_strings(_required(obj, "checks"), "acceptance.checks"),
        issues=_strings(_required(obj, "issues"), "acceptance.issues"),
    )


def _encode_attempt(attempt: AttemptView) -> dict[str, object]:
    return {
        "id": attempt.id,
        "unit_id": attempt.unit_id,
        "skill": attempt.skill,
        "status": attempt.status.value,
        "started_sequence": attempt.started_sequence,
        "finished_sequence": attempt.finished_sequence,
        "message": attempt.message,
    }


def _decode_attempt(value: object) -> AttemptView:
    obj = _mapping(value, "Attempt")
    finished_raw = obj.get("finished_sequence")
    finished = (
        None
        if finished_raw is None
        else _integer(finished_raw, "Attempt.finished_sequence")
    )
    return AttemptView(
        id=_nonempty_string(_required(obj, "id"), "Attempt.id"),
        unit_id=_nonempty_string(_required(obj, "unit_id"), "Attempt.unit_id"),
        skill=_nonempty_string(_required(obj, "skill"), "Attempt.skill"),
        status=_enum(AttemptStatus, _required(obj, "status"), "Attempt.status"),
        started_sequence=_integer(
            _required(obj, "started_sequence"), "Attempt.started_sequence"
        ),
        finished_sequence=finished,
        message=_string(_required(obj, "message"), "Attempt.message"),
    )


def _encode_completion(completion: CompletionView) -> dict[str, object]:
    return {
        "id": completion.id,
        "unit_id": completion.unit_id,
        "attempt_id": completion.attempt_id,
        "manifest_id": completion.manifest_id,
        "phase": completion.phase.value,
        "artifacts": [_encode_artifact(item) for item in completion.artifacts],
        "acceptance": _encode_acceptance(completion.acceptance),
    }


def _decode_completion(value: object) -> CompletionView:
    obj = _mapping(value, "Completion")
    return CompletionView(
        id=_nonempty_string(_required(obj, "id"), "Completion.id"),
        unit_id=_nonempty_string(_required(obj, "unit_id"), "Completion.unit_id"),
        attempt_id=_nonempty_string(
            _required(obj, "attempt_id"), "Completion.attempt_id"
        ),
        manifest_id=_nonempty_string(
            _required(obj, "manifest_id"), "Completion.manifest_id"
        ),
        phase=_enum(CompletionPhase, _required(obj, "phase"), "Completion.phase"),
        artifacts=tuple(
            _decode_artifact(item)
            for item in _array(_required(obj, "artifacts"), "Completion.artifacts")
        ),
        acceptance=_decode_acceptance(_required(obj, "acceptance")),
    )


def _encode_approval(approval: CheckpointApprovalView) -> dict[str, object]:
    return {
        "id": approval.id,
        "checkpoint": approval.checkpoint,
        "unit_id": approval.unit_id,
        "review_basis": _encode_review_basis(approval.review_basis),
        "active": approval.active,
        "sequence": approval.sequence,
    }


def _decode_approval(value: object) -> CheckpointApprovalView:
    obj = _mapping(value, "Checkpoint approval")
    return CheckpointApprovalView(
        id=_nonempty_string(_required(obj, "id"), "Approval.id"),
        checkpoint=_nonempty_string(
            _required(obj, "checkpoint"), "Approval.checkpoint"
        ),
        unit_id=_nonempty_string(_required(obj, "unit_id"), "Approval.unit_id"),
        review_basis=_decode_review_basis(_required(obj, "review_basis")),
        active=_boolean(_required(obj, "active"), "Approval.active"),
        sequence=_integer(_required(obj, "sequence"), "Approval.sequence"),
    )


def _encode_event(event: EventView) -> dict[str, object]:
    return {
        "sequence": event.sequence,
        "kind": event.kind,
        "unit_id": event.unit_id,
        "attempt_id": event.attempt_id,
        "details": [[key, value] for key, value in event.details],
    }


def _decode_event(value: object) -> EventView:
    obj = _mapping(value, "Event")
    details: list[tuple[str, str]] = []
    for index, item in enumerate(_array(_required(obj, "details"), "Event.details")):
        pair = _array(item, f"Event.details[{index}]")
        if len(pair) != 2:
            raise StorageCodecError(f"Event.details[{index}] must contain two strings.")
        details.append(
            (
                _string(pair[0], f"Event.details[{index}][0]"),
                _string(pair[1], f"Event.details[{index}][1]"),
            )
        )
    return EventView(
        sequence=_integer(_required(obj, "sequence"), "Event.sequence"),
        kind=_nonempty_string(_required(obj, "kind"), "Event.kind"),
        unit_id=_string(_required(obj, "unit_id"), "Event.unit_id"),
        attempt_id=_string(_required(obj, "attempt_id"), "Event.attempt_id"),
        details=tuple(details),
    )


def _validate_aggregate(run: RunAggregate) -> None:
    try:
        validate_run_contract(run_id=run.id, plan=run.plan, revision=run.revision)
    except HarnessError as exc:
        raise StorageCodecError(
            f"Run aggregate contract is invalid: {exc.message}"
        ) from exc

    unit_ids = {unit.id for unit in run.plan.units}
    if set(run.unit_status) != unit_ids:
        raise StorageCodecError("Run aggregate unit_status keys do not match its plan.")
    if [event.sequence for event in run.events] != list(range(1, len(run.events) + 1)):
        raise StorageCodecError(
            "Run aggregate Event sequences must be contiguous from one."
        )
    _require_unique((attempt.id for attempt in run.attempts), "Attempt IDs")
    _require_unique((completion.id for completion in run.completions), "Completion IDs")
    _require_unique(
        (completion.manifest_id for completion in run.completions), "Manifest IDs"
    )
    _require_unique((approval.id for approval in run.approvals), "Approval IDs")

    attempt_by_id = {attempt.id: attempt for attempt in run.attempts}
    unit_by_id = {unit.id: unit for unit in run.plan.units}
    version = run.version
    for attempt in run.attempts:
        if attempt.unit_id not in unit_ids:
            raise StorageCodecError(f"Attempt {attempt.id} references an unknown Unit.")
        if attempt.skill != unit_by_id[attempt.unit_id].skill:
            raise StorageCodecError(
                f"Attempt {attempt.id} Skill disagrees with its Unit plan."
            )
        if not 1 <= attempt.started_sequence <= version:
            raise StorageCodecError(
                f"Attempt {attempt.id} has an invalid start sequence."
            )
        if attempt.status is AttemptStatus.RUNNING:
            if attempt.finished_sequence is not None:
                raise StorageCodecError(
                    f"RUNNING Attempt {attempt.id} is already finished."
                )
        elif attempt.finished_sequence is None or not (
            attempt.started_sequence <= attempt.finished_sequence <= version
        ):
            raise StorageCodecError(
                f"Terminal Attempt {attempt.id} has no valid finish sequence."
            )

    running = [
        attempt.id
        for attempt in run.attempts
        if attempt.status is AttemptStatus.RUNNING
    ]
    if len(running) > 1:
        raise StorageCodecError("Run aggregate contains more than one RUNNING Attempt.")
    if run.active_attempt_id is not None:
        active = attempt_by_id.get(run.active_attempt_id)
        if active is None or active.status is not AttemptStatus.RUNNING:
            raise StorageCodecError(
                "active_attempt_id does not identify a RUNNING Attempt."
            )
        if run.unit_status[active.unit_id] is not UnitStatus.DOING:
            raise StorageCodecError("The active Attempt Unit must be DOING.")
    elif running:
        raise StorageCodecError("A RUNNING Attempt is missing active_attempt_id.")

    for completion in run.completions:
        attempt = attempt_by_id.get(completion.attempt_id)
        if attempt is None or attempt.unit_id != completion.unit_id:
            raise StorageCodecError(
                f"Completion {completion.id} does not match a known Attempt."
            )
        if (
            completion.phase is CompletionPhase.COMMITTED
            and attempt.status is not AttemptStatus.SUCCEEDED
        ):
            raise StorageCodecError(
                f"COMMITTED Completion {completion.id} requires a SUCCEEDED Attempt."
            )
        _require_unique(
            (artifact.path for artifact in completion.artifacts),
            f"Completion {completion.id} Artifact paths",
        )
    for approval in run.approvals:
        if approval.unit_id not in unit_ids:
            raise StorageCodecError(
                f"Approval {approval.id} references an unknown Unit."
            )
        if not 1 <= approval.sequence <= version:
            raise StorageCodecError(f"Approval {approval.id} has an invalid sequence.")
        _require_unique(
            (artifact.path for artifact in approval.review_basis.artifacts),
            f"Approval {approval.id} Artifact paths",
        )
    for event in run.events:
        _require_unique(
            (key for key, _ in event.details),
            f"Event {event.sequence} detail keys",
        )


def _require_schema(obj: Mapping[str, object], expected: str, label: str) -> None:
    actual = obj.get("schema")
    if actual != expected:
        raise StorageCodecError(f"{label} schema must be {expected!r}, not {actual!r}.")


def _require_exact_keys(
    obj: Mapping[str, object], expected: set[str], label: str
) -> None:
    actual = set(obj)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unexpected:
            details.append("unexpected " + ", ".join(unexpected))
        raise StorageCodecError(f"{label} fields are invalid: {'; '.join(details)}.")


def _required(obj: Mapping[str, object], key: str) -> object:
    if key not in obj:
        raise StorageCodecError(f"Persisted JSON is missing required field {key!r}.")
    return obj[key]


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise StorageCodecError(f"{label} must be a JSON object.")
    return value


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise StorageCodecError(f"{label} must be a JSON array.")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise StorageCodecError(f"{label} must be a string.")
    return value


def _nonempty_string(value: object, label: str) -> str:
    result = _string(value, label)
    if not result.strip():
        raise StorageCodecError(f"{label} must be non-empty.")
    return result


def _strings(value: object, label: str) -> tuple[str, ...]:
    return tuple(
        _string(item, f"{label}[{index}]")
        for index, item in enumerate(_array(value, label))
    )


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise StorageCodecError(f"{label} must be an integer.")
    return value


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise StorageCodecError(f"{label} must be a boolean.")
    return value


def _enum(enum_type: type[_EnumT], value: object, label: str) -> _EnumT:
    raw = _string(value, label)
    try:
        return enum_type(raw)
    except ValueError as exc:
        raise StorageCodecError(f"{label} has unsupported value {raw!r}.") from exc


def _require_unique(values: Any, label: str) -> None:
    materialized = list(values)
    if len(materialized) != len(set(materialized)):
        raise StorageCodecError(f"{label} must be unique.")
