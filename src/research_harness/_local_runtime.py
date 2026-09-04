"""Repository composition for the next local engine.

This module is intentionally private.  It turns a validated Workflow into one
workspace-bound engine without exposing bootstrap, hashing, storage, Skill, or
acceptance construction to CLI callers.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from research_harness.acceptance import build_repository_acceptance_policy
from research_harness.application import AcceptAll, plan_from_workflow
from research_harness.domain import HarnessRevision, Owner, RunPlan
from research_harness.domain.model import RunAggregate
from research_harness.engine import (
    CreateLocalRun,
    EngineError,
    EngineErrorCode,
    EngineResult,
    LocalRunEngine,
)
from research_harness.engine._execution_snapshot import (
    materialize_execution_snapshot,
)
from research_harness.skills import SkillAdapter, SubprocessSkillAdapter
from research_harness.storage import FilesystemArtifacts, FilesystemRunLedger
from research_harness.workflows import WorkflowDefinition, load_workflow_definition


_STATE_DIR = ".harness-v3"
_WORKFLOW_SNAPSHOT_SCHEMA = "research-harness.workflow-snapshot/v2"
_SUPPORTED_WORKFLOW_SNAPSHOT_SCHEMAS = frozenset(
    {"research-harness.workflow-snapshot/v1", _WORKFLOW_SNAPSHOT_SCHEMA}
)
_IDENTITY_SCHEMA = "research-harness.local-identity/v1"


def initialize_repository_run(
    *,
    workspace: Path,
    repo_root: Path,
    pipeline: Path | str,
    request: str,
    run_id: str = "",
) -> tuple[EngineResult, WorkflowDefinition]:
    """Bootstrap a pristine Workspace and create its sole canonical Run."""

    root = _repository_root(repo_root)
    workflow = load_workflow_definition(
        _pipeline_path(pipeline, repo_root=root),
        repo_root=root,
        validate_capabilities="required",
    )
    request = str(request).strip()
    if not request:
        raise ValueError("request must be non-empty")

    plan = plan_from_workflow(
        workflow,
        goal_id=f"goal_{uuid4().hex}",
        request=request,
    )
    _validate_repository_execution_roots(workflow, repo_root=root)
    published_workspace = _new_workspace_target(workspace, repo_root=root)
    snapshot = _workflow_snapshot(workflow, repo_root=root)
    revision, identity = _revision_and_identity(
        workflow=workflow,
        repo_root=root,
        snapshot=snapshot,
        plan=plan,
    )
    staging = _create_staging_workspace(published_workspace)
    published = False
    try:
        target = _prepare_workspace(staging, repo_root=root)
        _materialize_workspace_contract(
            workspace=target,
            repo_root=root,
            workflow=workflow,
            request=request,
            snapshot=snapshot,
            identity=identity,
        )

        engine = _compose_engine(
            workspace=target,
            repo_root=root,
            workflow=workflow,
            revision=revision,
            identity=identity,
            skills=(unit.skill for unit in plan.units if unit.owner is Owner.CODEX),
        )
        result = engine.execute(CreateLocalRun(plan=plan, run_id=run_id))
        _publish_staged_workspace(staging, published_workspace)
        published = True
        return (
            replace(
                result,
                inspection=replace(
                    result.inspection,
                    workspace=published_workspace,
                ),
            ),
            workflow,
        )
    finally:
        if not published and staging.exists():
            _remove_staged_workspace(staging)


def compose_repository_engine(
    *,
    workspace: Path,
    repo_root: Path,
) -> LocalRunEngine:
    """Compose mutation dependencies from the canonical Run and current repo."""

    target = _existing_workspace(workspace)
    ledger = FilesystemRunLedger(target)
    run_id = ledger.current_run_id()
    if run_id is None:
        return _inspection_engine(target, ledger=ledger)
    aggregate = ledger.load(run_id)
    if aggregate is None:  # pragma: no cover - guarded by current_run_id.
        return _inspection_engine(target, ledger=ledger)

    root = _repository_root(repo_root)
    workflow = _load_bound_workflow(
        workspace=target,
        repo_root=root,
        workflow_name=aggregate.plan.goal.workflow,
    )
    _validate_repository_execution_roots(workflow, repo_root=root)
    expected_plan = plan_from_workflow(
        workflow,
        goal_id=aggregate.plan.goal.id,
        request=aggregate.plan.goal.request,
    )
    snapshot = _workflow_snapshot(workflow, repo_root=root)
    revision, identity = _revision_and_identity(
        workflow=workflow,
        repo_root=root,
        snapshot=snapshot,
        plan=expected_plan,
    )
    if revision != aggregate.revision:
        raise EngineError(
            EngineErrorCode.REVISION_DRIFT,
            "Active Run does not match the current Pipeline/Kernel revision.",
            run_id=aggregate.id,
        )
    if expected_plan != aggregate.plan:
        raise EngineError(
            EngineErrorCode.INTEGRITY_VIOLATION,
            "Canonical Run plan disagrees with its pinned Workflow contract.",
            run_id=aggregate.id,
        )
    bundle_issues = _pinned_bundle_issues(target, aggregate)
    if bundle_issues:
        raise EngineError(
            EngineErrorCode.INTEGRITY_VIOLATION,
            "Pinned contract evidence is incomplete or inconsistent.",
            run_id=aggregate.id,
            issues=bundle_issues,
        )
    if not _bundle_matches_live_contract(
        target,
        workflow=workflow,
        snapshot=snapshot,
        identity=identity,
    ):
        raise EngineError(
            EngineErrorCode.INTEGRITY_VIOLATION,
            "Pinned contract evidence disagrees with the current revision.",
            run_id=aggregate.id,
        )
    return _compose_engine(
        workspace=target,
        repo_root=root,
        workflow=workflow,
        revision=revision,
        identity=identity,
        skills=(
            unit.skill for unit in aggregate.plan.units if unit.owner is Owner.CODEX
        ),
    )


def compose_inspection_engine(*, workspace: Path) -> LocalRunEngine:
    """Compose a read-only-capable engine without consulting the live repo."""

    target = _existing_workspace(workspace)
    ledger = FilesystemRunLedger(target)
    return _inspection_engine(target, ledger=ledger)


def inspection_contract_issues(*, workspace: Path) -> tuple[str, ...]:
    """Return bounded contract-bundle issues without consulting the live repo."""

    target = _existing_workspace(workspace)
    ledger = FilesystemRunLedger(target)
    run_id = ledger.current_run_id()
    if run_id is None:
        return ()
    aggregate = ledger.load(run_id)
    return _pinned_bundle_issues(target, aggregate) if aggregate is not None else ()


def _inspection_engine(
    workspace: Path,
    *,
    ledger: FilesystemRunLedger,
) -> LocalRunEngine:
    run_id = ledger.current_run_id()
    aggregate = ledger.load(run_id) if run_id is not None else None
    revision = (
        aggregate.revision
        if aggregate is not None
        else HarnessRevision(
            pipeline_digest="inspection-only",
            kernel_digest="inspection-only",
        )
    )
    return LocalRunEngine(
        workspace,
        ledger=ledger,
        artifacts=FilesystemArtifacts(workspace),
        skill_adapters={},
        acceptance=AcceptAll(),
        revision=revision,
    )


def _compose_engine(
    *,
    workspace: Path,
    repo_root: Path,
    workflow: WorkflowDefinition,
    revision: HarnessRevision,
    identity: Mapping[str, object],
    skills: Iterable[str],
) -> LocalRunEngine:
    execution_root = materialize_execution_snapshot(
        workspace=workspace,
        repo_root=repo_root,
        revision_id=revision.kernel_digest,
        components=identity.get("components"),
    )
    adapters: dict[str, SkillAdapter] = {}
    for skill in dict.fromkeys(skills):
        if skill == "human-checkpoint":
            continue
        adapters[skill] = SubprocessSkillAdapter.for_repo_skill(
            repo_root=execution_root,
            skill=skill,
        )

    def workspace_for_run(candidate: str) -> Path:
        if not str(candidate).strip():
            raise ValueError("run identity must be non-empty")
        return workspace

    acceptance = build_repository_acceptance_policy(
        workflows=(workflow,),
        workspace_for_run=workspace_for_run,
    )
    return LocalRunEngine.for_workspace(
        workspace,
        skill_adapters=adapters,
        acceptance=acceptance,
        revision=revision,
    )


def _prepare_workspace(workspace: Path, *, repo_root: Path) -> Path:
    candidate = Path(workspace).expanduser().resolve(strict=False)
    if candidate == repo_root:
        raise ValueError("The repository root cannot be used as a Run Workspace.")
    if candidate.exists() and not candidate.is_dir():
        raise ValueError("Workspace must be a directory.")

    protected = (
        "GOAL.md",
        "UNITS.csv",
        "PIPELINE.lock.md",
        ".harness",
        _STATE_DIR,
    )
    collisions = tuple(
        name
        for name in protected
        if (candidate / name).exists() or (candidate / name).is_symlink()
    )
    if collisions:
        raise ValueError(
            "Workspace already contains managed Run files: " + ", ".join(collisions)
        )

    template = _workspace_template_root(repo_root)
    sources = tuple(sorted(template.rglob("*")))
    unsafe = tuple(
        source.relative_to(template).as_posix()
        for source in sources
        if source.is_symlink() or (not source.is_dir() and not source.is_file())
    )
    if unsafe:
        raise ValueError(
            "Workspace template contains unsafe entries: " + ", ".join(unsafe)
        )
    candidate.mkdir(parents=True, exist_ok=True)
    template_collisions = tuple(
        source.relative_to(template).as_posix()
        for source in sources
        if _unsafe_template_destination(
            candidate,
            source.relative_to(template),
            directory=source.is_dir(),
        )
    )
    if template_collisions:
        raise ValueError(
            "Workspace template destinations are unsafe or would overwrite: "
            + ", ".join(template_collisions)
        )

    _copy_template_tree_no_follow(
        template=template,
        destination=candidate,
        sources=sources,
    )
    return candidate.resolve(strict=True)


def _new_workspace_target(workspace: Path, *, repo_root: Path) -> Path:
    raw = Path(workspace).expanduser()
    if raw.is_symlink():
        raise ValueError("A new Workspace must not be a symbolic link.")
    candidate = raw.resolve(strict=False)
    if candidate == repo_root:
        raise ValueError("The repository root cannot be used as a Run Workspace.")
    if candidate.exists() or candidate.is_symlink():
        raise ValueError("Initialization requires a new Workspace path.")
    return candidate


def _create_staging_workspace(target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise ValueError("Initialization requires a new Workspace path.")
    return Path(
        tempfile.mkdtemp(
            prefix=f".{target.name}.",
            suffix=".staging",
            dir=target.parent,
        )
    )


def _publish_staged_workspace(staging: Path, target: Path) -> None:
    if staging.parent != target.parent or staging.is_symlink() or not staging.is_dir():
        raise ValueError("Staged Workspace is unavailable or unsafe.")
    if target.exists() or target.is_symlink():
        raise ValueError("Workspace path changed during initialization.")
    renamed = False
    try:
        os.rename(staging, target)
        renamed = True
        directory = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as exc:
        if renamed and target.is_dir() and not target.is_symlink():
            _remove_staged_workspace(target)
        raise ValueError("Workspace could not be published atomically.") from exc


def _remove_staged_workspace(staging: Path) -> None:
    for directory, directories, files in os.walk(
        staging,
        topdown=False,
        followlinks=False,
    ):
        root = Path(directory)
        for name in files:
            path = root / name
            if not path.is_symlink():
                path.chmod(0o600)
        for name in directories:
            path = root / name
            if not path.is_symlink():
                path.chmod(0o700)
        root.chmod(0o700)
    shutil.rmtree(staging)


def _unsafe_template_destination(
    workspace: Path,
    relative: Path,
    *,
    directory: bool,
) -> bool:
    """Reject pre-existing links, non-directory ancestors, and file collisions."""

    current = workspace
    for index, part in enumerate(relative.parts):
        current = current / part
        leaf = index == len(relative.parts) - 1
        if current.is_symlink():
            return True
        if not current.exists():
            continue
        if not current.is_dir():
            return True
        if leaf and not directory:
            return True
    return False


def _copy_template_tree_no_follow(
    *,
    template: Path,
    destination: Path,
    sources: tuple[Path, ...],
) -> None:
    """Copy a trusted template without following Workspace-side symlinks."""

    directory_flags = os.O_RDONLY | os.O_DIRECTORY
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    root_fd = os.open(destination, directory_flags | no_follow)
    try:
        for source in sources:
            relative = source.relative_to(template)
            if source.is_dir():
                directory_fd = _open_relative_directory(
                    root_fd,
                    relative,
                    create=True,
                )
                os.close(directory_fd)
                continue

            parent_fd = _open_relative_directory(
                root_fd,
                relative.parent,
                create=True,
            )
            try:
                source_stat = source.stat(follow_symlinks=False)
                output_fd = os.open(
                    relative.name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | no_follow,
                    source_stat.st_mode & 0o777,
                    dir_fd=parent_fd,
                )
                try:
                    with (
                        source.open("rb") as input_file,
                        os.fdopen(
                            output_fd,
                            "wb",
                            closefd=False,
                        ) as output_file,
                    ):
                        shutil.copyfileobj(input_file, output_file)
                        output_file.flush()
                        os.fsync(output_fd)
                finally:
                    os.close(output_fd)
            except FileExistsError as exc:
                raise ValueError(
                    "Workspace template destination changed during initialization: "
                    + relative.as_posix()
                ) from exc
            finally:
                os.close(parent_fd)
    except OSError as exc:
        raise ValueError(
            "Workspace template destination changed or became unsafe during "
            "initialization."
        ) from exc
    finally:
        os.close(root_fd)


def _open_relative_directory(
    root_fd: int,
    relative: Path,
    *,
    create: bool,
) -> int:
    """Open a relative directory chain while refusing every symbolic link."""

    directory_flags = os.O_RDONLY | os.O_DIRECTORY
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    current_fd = os.dup(root_fd)
    try:
        for part in relative.parts:
            if part in {"", ".", ".."}:
                raise ValueError("Template paths must be normalized and relative.")
            if create:
                try:
                    os.mkdir(part, mode=0o755, dir_fd=current_fd)
                except FileExistsError:
                    pass
            next_fd = os.open(
                part,
                directory_flags | no_follow,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _materialize_workspace_contract(
    *,
    workspace: Path,
    repo_root: Path,
    workflow: WorkflowDefinition,
    request: str,
    snapshot: Mapping[str, object],
    identity: Mapping[str, object],
) -> None:
    pipeline_display = _display_path(workflow.source, root=repo_root)
    lock = (
        f"pipeline: {pipeline_display}\n"
        f"units_template: {workflow.units_template}\n"
        "runtime: research-harness-v3\n"
    )
    _atomic_write_text(workspace / "PIPELINE.lock.md", lock)
    _atomic_write_bytes(workspace / "UNITS.csv", workflow.units_source.read_bytes())
    _atomic_write_text(workspace / "GOAL.md", f"# Goal\n\n{request}\n")

    contracts = workspace / _STATE_DIR / "contracts"
    contracts.mkdir(parents=True, exist_ok=False)
    _atomic_write_bytes(contracts / "pipeline.md", workflow.source.read_bytes())
    _atomic_write_bytes(contracts / "units.csv", workflow.units_source.read_bytes())
    _atomic_write_json(contracts / "workflow.json", snapshot)
    _atomic_write_json(contracts / "identity.json", identity)


def _load_bound_workflow(
    *,
    workspace: Path,
    repo_root: Path,
    workflow_name: str,
) -> WorkflowDefinition:
    declared = ""
    lock = workspace / "PIPELINE.lock.md"
    if lock.is_file():
        for raw_line in lock.read_text(encoding="utf-8", errors="replace").splitlines():
            if raw_line.strip().startswith("pipeline:"):
                declared = raw_line.split(":", 1)[1].strip()
                break
    pipeline = declared or f"pipelines/{workflow_name}.pipeline.md"
    workflow = load_workflow_definition(
        _pipeline_path(pipeline, repo_root=repo_root),
        repo_root=repo_root,
        validate_capabilities="required",
    )
    if workflow.name != workflow_name:
        raise ValueError(
            f"Workspace binds Workflow {workflow_name!r}, not {workflow.name!r}."
        )
    return workflow


def _pipeline_path(pipeline: Path | str, *, repo_root: Path) -> Path:
    value = Path(str(pipeline)).expanduser()
    if not value.suffix and len(value.parts) == 1:
        value = Path("pipelines") / f"{value.name}.pipeline.md"
    candidate = value if value.is_absolute() else repo_root / value
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError("Pipeline must remain inside the repository root.") from exc
    return resolved


def _repository_root(repo_root: Path) -> Path:
    root = Path(repo_root).expanduser().resolve(strict=True)
    if not root.is_dir() or not (root / ".codex" / "skills").is_dir():
        raise ValueError("repo_root is not a Research Harness source checkout.")
    return root


def _existing_workspace(workspace: Path) -> Path:
    candidate = Path(workspace).expanduser().resolve(strict=True)
    if not candidate.is_dir():
        raise ValueError("Workspace must be an existing directory.")
    return candidate


def _workflow_snapshot(
    workflow: WorkflowDefinition,
    *,
    repo_root: Path,
) -> dict[str, object]:
    stages = [
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
    ]
    units = [
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
    ]
    return {
        "schema": _WORKFLOW_SNAPSHOT_SCHEMA,
        "name": workflow.name,
        "version": workflow.version,
        "profile": workflow.profile,
        "contract_model": workflow.contract_model,
        "variant_of": workflow.variant_of,
        "source": _display_path(workflow.source, root=repo_root),
        "source_sha256": _file_sha256(workflow.source),
        "units_source": _display_path(workflow.units_source, root=repo_root),
        "units_sha256": _file_sha256(workflow.units_source),
        "units_template": workflow.units_template,
        "default_checkpoints": list(workflow.default_checkpoints),
        "target_artifacts": list(workflow.target_artifacts),
        "case_contract": {
            "kind": workflow.case_contract.kind,
            "views": list(workflow.case_contract.views),
            "claim_sources": list(workflow.case_contract.claim_sources),
            "evidence_sources": list(workflow.case_contract.evidence_sources),
            "decision_sources": list(workflow.case_contract.decision_sources),
        },
        "quality_contract": _json_value(workflow.quality_contract),
        "stages": stages,
        "units": units,
    }


def _revision_and_identity(
    *,
    workflow: WorkflowDefinition,
    repo_root: Path,
    snapshot: Mapping[str, object],
    plan: RunPlan,
) -> tuple[HarnessRevision, dict[str, object]]:
    snapshot_bytes = _canonical_json(snapshot)
    pipeline_digest = hashlib.sha256(snapshot_bytes).hexdigest()
    component_paths: list[Path] = [
        repo_root / "AGENTS.md",
        repo_root / "pyproject.toml",
        repo_root / "src" / "research_harness",
        repo_root / "tooling",
        # tooling/source_text_hygiene.py loads this policy asset at import/use
        # time via <repo_root>/assets/limitation-signals.json; skills that call
        # has_limitation_signal (paper-notes, evidence-draft, writer-context-pack)
        # execute from the immutable snapshot, so the asset must be pinned into
        # it or those skills crash with FileNotFoundError under the snapshot.
        repo_root / "assets" / "limitation-signals.json",
        workflow.source,
        workflow.units_source,
    ]
    component_paths.extend(
        repo_root / ".codex" / "skills" / skill for skill in workflow.skills
    )
    records = _component_records(component_paths, repo_root=repo_root)
    kernel_digest = hashlib.sha256(_canonical_json(records)).hexdigest()
    revision = HarnessRevision(
        pipeline_digest=pipeline_digest,
        kernel_digest=kernel_digest,
    )
    identity = {
        "schema": _IDENTITY_SCHEMA,
        "workflow": workflow.name,
        "plan_sha256": _plan_sha256(plan),
        "revision": {
            "pipeline_digest": revision.pipeline_digest,
            "kernel_digest": revision.kernel_digest,
            "completion_protocol": revision.completion_protocol,
        },
        "components": records,
    }
    return revision, identity


def _pinned_bundle_issues(
    workspace: Path,
    aggregate: RunAggregate,
) -> tuple[str, ...]:
    contracts = workspace / _STATE_DIR / "contracts"
    if contracts.is_symlink() or not contracts.is_dir():
        return ("Pinned contract directory is missing or unsafe.",)
    paths = {
        "pipeline": contracts / "pipeline.md",
        "units": contracts / "units.csv",
        "workflow": contracts / "workflow.json",
        "identity": contracts / "identity.json",
    }
    if any(path.is_symlink() or not path.is_file() for path in paths.values()):
        return ("One or more pinned contract files are missing or unsafe.",)
    try:
        snapshot = json.loads(paths["workflow"].read_text(encoding="utf-8"))
        identity = json.loads(paths["identity"].read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ("Pinned contract JSON cannot be decoded.",)
    if not isinstance(snapshot, dict) or not isinstance(identity, dict):
        return ("Pinned contract JSON must contain objects.",)

    issues: list[str] = []
    if snapshot.get("schema") not in _SUPPORTED_WORKFLOW_SNAPSHOT_SCHEMAS:
        issues.append("Pinned Workflow snapshot schema is unsupported.")
    if identity.get("schema") != _IDENTITY_SCHEMA:
        issues.append("Pinned local identity schema is unsupported.")
    if (
        hashlib.sha256(_canonical_json(snapshot)).hexdigest()
        != aggregate.revision.pipeline_digest
    ):
        issues.append("Pinned Workflow snapshot does not match the Run revision.")
    if identity.get("workflow") != aggregate.plan.goal.workflow:
        issues.append("Pinned identity names a different Workflow.")
    if identity.get("plan_sha256") != _plan_sha256(aggregate.plan):
        issues.append("Pinned identity does not match the canonical Run plan.")
    expected_revision = {
        "pipeline_digest": aggregate.revision.pipeline_digest,
        "kernel_digest": aggregate.revision.kernel_digest,
        "completion_protocol": aggregate.revision.completion_protocol,
    }
    if identity.get("revision") != expected_revision:
        issues.append("Pinned identity does not match the Run revision.")
    components = identity.get("components")
    if (
        not isinstance(components, list)
        or hashlib.sha256(_canonical_json(components)).hexdigest()
        != aggregate.revision.kernel_digest
    ):
        issues.append("Pinned runtime components do not match the Kernel revision.")
    if _file_sha256(paths["pipeline"]) != snapshot.get("source_sha256"):
        issues.append("Pinned Pipeline source bytes do not match the snapshot.")
    if _file_sha256(paths["units"]) != snapshot.get("units_sha256"):
        issues.append("Pinned Unit-table bytes do not match the snapshot.")
    return tuple(dict.fromkeys(issues))


def _bundle_matches_live_contract(
    workspace: Path,
    *,
    workflow: WorkflowDefinition,
    snapshot: Mapping[str, object],
    identity: Mapping[str, object],
) -> bool:
    contracts = workspace / _STATE_DIR / "contracts"
    try:
        pinned_snapshot = json.loads(
            (contracts / "workflow.json").read_text(encoding="utf-8")
        )
        pinned_identity = json.loads(
            (contracts / "identity.json").read_text(encoding="utf-8")
        )
        return (
            pinned_snapshot == snapshot
            and pinned_identity == identity
            and (contracts / "pipeline.md").read_bytes() == workflow.source.read_bytes()
            and (contracts / "units.csv").read_bytes()
            == workflow.units_source.read_bytes()
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False


def _plan_sha256(plan: RunPlan) -> str:
    return hashlib.sha256(_canonical_json(_plan_payload(plan))).hexdigest()


def _plan_payload(plan: RunPlan) -> dict[str, object]:
    goal = plan.goal
    return {
        "goal": {
            "id": goal.id,
            "request": goal.request,
            "workflow": goal.workflow,
            "constraints": list(goal.constraints),
            "target_artifacts": list(goal.target_artifacts),
            "success_criteria": list(goal.success_criteria),
            "required_checks": list(goal.required_checks),
        },
        "units": [
            {
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
            for unit in plan.units
        ],
    }


def _component_records(
    roots: Iterable[Path],
    *,
    repo_root: Path,
) -> list[dict[str, object]]:
    files: dict[str, Path] = {}
    for root in roots:
        if root.is_symlink():
            raise ValueError("Pinned runtime component root must not be a link.")
        if not root.exists():
            raise ValueError("Pinned runtime component root is missing.")
        try:
            root.resolve(strict=True).relative_to(repo_root)
        except ValueError as exc:
            raise ValueError(
                "Pinned runtime component root escapes the repository."
            ) from exc
        candidates = (root,) if root.is_file() else root.rglob("*")
        for candidate in candidates:
            if candidate.is_symlink():
                raise ValueError("Pinned runtime components must not contain links.")
            if not candidate.is_file():
                continue
            if "__pycache__" in candidate.parts or candidate.suffix in {".pyc", ".pyo"}:
                continue
            relative = candidate.relative_to(repo_root).as_posix()
            files[relative] = candidate
    return [
        {
            "path": relative,
            "sha256": _file_sha256(path),
            "size": path.stat().st_size,
        }
        for relative, path in sorted(files.items())
    ]


def _validate_repository_execution_roots(
    workflow: WorkflowDefinition,
    *,
    repo_root: Path,
) -> None:
    for skill in dict.fromkeys(workflow.skills):
        _confined_repository_directory(
            repo_root / ".codex" / "skills" / skill,
            repo_root=repo_root,
            label=f"Repository Skill {skill!r}",
        )
    _workspace_template_root(repo_root)


def _workspace_template_root(repo_root: Path) -> Path:
    return _confined_repository_directory(
        repo_root
        / ".codex"
        / "skills"
        / "workspace-init"
        / "assets"
        / "workspace-template",
        repo_root=repo_root,
        label="Repository workspace template",
    )


def _confined_repository_directory(
    path: Path,
    *,
    repo_root: Path,
    label: str,
) -> Path:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symbolic link.")
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(repo_root)
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError(f"{label} is unavailable or outside repo_root.") from exc
    if not resolved.is_dir():
        raise ValueError(f"{label} must be a directory.")
    return resolved


def _display_path(path: Path, *, root: Path) -> str:
    try:
        return path.resolve(strict=True).relative_to(root).as_posix()
    except ValueError:
        return path.resolve(strict=True).as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    _atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _atomic_write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = -1
    temporary = ""
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = ""
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
