from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tooling.pipeline_spec import resolve_pipeline_variant_chain


@dataclass(frozen=True)
class PipelineSnapshotIssue:
    code: str
    message: str


@dataclass(frozen=True)
class PipelineSnapshotInspection:
    selected_path: Path | None
    issues: tuple[PipelineSnapshotIssue, ...]

    @property
    def valid(self) -> bool:
        return self.selected_path is not None and not self.issues


def inspect_pipeline_snapshot_bundle(
    *,
    workspace: Path,
    pipeline_lock: dict[str, Any],
) -> PipelineSnapshotInspection:
    """Validate the selected Pipeline and every pinned inheritance dependency."""

    workspace_root = workspace.resolve()
    snapshot_value = str(pipeline_lock.get("snapshot_path") or "").strip()
    expected_sha = str(pipeline_lock.get("snapshot_sha256") or "").strip()
    issues: list[PipelineSnapshotIssue] = []

    if not snapshot_value:
        issues.append(
            PipelineSnapshotIssue(
                "pipeline_snapshot_missing",
                "The v2 Harness lock has no Pipeline contract snapshot.",
            )
        )
        return PipelineSnapshotInspection(None, tuple(issues))

    candidate = Path(snapshot_value)
    if candidate.is_absolute():
        issues.append(
            PipelineSnapshotIssue(
                "pipeline_snapshot_path_invalid",
                "The Pipeline snapshot path must be Workspace-relative.",
            )
        )
        return PipelineSnapshotInspection(None, tuple(issues))

    snapshot_path = (workspace_root / candidate).resolve()
    if not snapshot_path.is_relative_to(workspace_root):
        issues.append(
            PipelineSnapshotIssue(
                "pipeline_snapshot_path_invalid",
                "The Pipeline snapshot path escapes the Workspace.",
            )
        )
        return PipelineSnapshotInspection(None, tuple(issues))

    if not snapshot_path.is_file():
        issues.append(
            PipelineSnapshotIssue(
                "pipeline_snapshot_missing",
                f"Pinned Pipeline snapshot `{snapshot_value}` is missing.",
            )
        )
    elif not expected_sha or _file_sha256(snapshot_path) != expected_sha:
        issues.append(
            PipelineSnapshotIssue(
                "pipeline_snapshot_hash_mismatch",
                f"Pinned Pipeline snapshot `{snapshot_value}` does not match its lock hash.",
            )
        )

    snapshot_files = pipeline_lock.get("snapshot_files")
    if not isinstance(snapshot_files, dict) or not snapshot_files:
        issues.append(
            PipelineSnapshotIssue(
                "pipeline_snapshot_bundle_missing",
                "The v2 Pipeline snapshot has no inheritance bundle manifest.",
            )
        )
        return PipelineSnapshotInspection(None, tuple(issues))

    root_value = str(pipeline_lock.get("snapshot_root") or "").strip()
    root_candidate = Path(root_value) if root_value else candidate.parent
    if root_candidate.is_absolute():
        issues.append(
            PipelineSnapshotIssue(
                "pipeline_snapshot_root_invalid",
                "The Pipeline snapshot root must be Workspace-relative.",
            )
        )
        return PipelineSnapshotInspection(None, tuple(issues))
    snapshot_dir = (workspace_root / root_candidate).resolve()
    if not snapshot_dir.is_relative_to(workspace_root) or not snapshot_path.is_relative_to(snapshot_dir):
        issues.append(
            PipelineSnapshotIssue(
                "pipeline_snapshot_root_invalid",
                "The selected Pipeline snapshot is outside its declared bundle root.",
            )
        )
        return PipelineSnapshotInspection(None, tuple(issues))

    selected_key = snapshot_path.relative_to(snapshot_dir).as_posix()
    if selected_key not in snapshot_files:
        issues.append(
            PipelineSnapshotIssue(
                "pipeline_snapshot_selected_unlisted",
                f"Selected Pipeline snapshot `{selected_key}` is not pinned in the bundle manifest.",
            )
        )

    for filename, digest in sorted(snapshot_files.items()):
        relative = Path(str(filename or ""))
        dependency = (snapshot_dir / relative).resolve()
        if (
            not str(filename or "").strip()
            or relative.is_absolute()
            or not dependency.is_relative_to(snapshot_dir.resolve())
        ):
            issues.append(
                PipelineSnapshotIssue(
                    "pipeline_snapshot_dependency_path_invalid",
                    f"Pinned Pipeline dependency `{filename}` escapes the snapshot bundle.",
                )
            )
        elif not dependency.is_file():
            issues.append(
                PipelineSnapshotIssue(
                    "pipeline_snapshot_dependency_missing",
                    f"Pinned Pipeline dependency `{filename}` is missing.",
                )
            )
        elif not str(digest or "").strip() or _file_sha256(dependency) != str(digest):
            issues.append(
                PipelineSnapshotIssue(
                    "pipeline_snapshot_dependency_hash_mismatch",
                    f"Pinned Pipeline dependency `{filename}` does not match its lock hash.",
                )
            )

    if snapshot_path.is_file():
        try:
            inheritance_chain = resolve_pipeline_variant_chain(snapshot_path)
        except (OSError, ValueError) as exc:
            issues.append(
                PipelineSnapshotIssue(
                    "pipeline_snapshot_inheritance_invalid",
                    f"Pinned Pipeline inheritance cannot be resolved inside the snapshot bundle: {exc}",
                )
            )
        else:
            for dependency in inheritance_chain:
                if not dependency.is_relative_to(snapshot_dir):
                    issues.append(
                        PipelineSnapshotIssue(
                            "pipeline_snapshot_parent_path_invalid",
                            f"Resolved Pipeline parent `{dependency}` is outside the snapshot bundle.",
                        )
                    )
                    continue
                dependency_key = dependency.relative_to(snapshot_dir).as_posix()
                if dependency_key not in snapshot_files:
                    issues.append(
                        PipelineSnapshotIssue(
                            "pipeline_snapshot_parent_unlisted",
                            f"Resolved Pipeline parent `{dependency_key}` is not pinned in the bundle manifest.",
                        )
                    )

    return PipelineSnapshotInspection(
        snapshot_path if not issues else None,
        tuple(issues),
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
