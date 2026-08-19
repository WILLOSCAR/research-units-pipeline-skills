from __future__ import annotations

import csv
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import MappingProxyType
from typing import Any, Literal

import yaml

from .definition import (
    LoopContract,
    StageDefinition,
    UnitDefinition,
    WorkflowDefinition,
)
from .errors import (
    WorkflowContractIssue,
    WorkflowSourceError,
    WorkflowSyntaxError,
    WorkflowValidationError,
)


_CONTRACT_MODEL = "pipeline.frontmatter/v1"
_UNIT_ID = re.compile(r"^U\d{3,}$")
_UNIT_TYPES = frozenset(
    {
        "RETRIEVE",
        "CURATE",
        "STRUCTURE",
        "EVIDENCE",
        "WRITE",
        "CITE",
        "LATEX",
        "QA",
        "META",
        "IDEA",
    }
)
_UNIT_STATUSES = frozenset({"TODO", "DOING", "BLOCKED", "DONE", "SKIP"})
_UNIT_OWNERS = frozenset({"HUMAN", "CODEX"})
_STAGE_MODES = frozenset({"no_prose", "short_prose_ok", "prose_allowed"})
_CASE_CONTRACT_FIELDS = (
    "kind",
    "views",
    "claim_sources",
    "evidence_sources",
    "decision_sources",
)
_CASE_KINDS = (
    "brief",
    "review",
    "evidence-synthesis",
    "survey",
    "ideas",
    "tutorial",
)
CASE_KIND_BY_WORKFLOW = {
    "arxiv-survey": "survey",
    "arxiv-survey-latex": "survey",
    "evidence-review": "evidence-synthesis",
    "idea-brainstorm": "ideas",
    "paper-review": "review",
    "research-brief": "brief",
    "source-tutorial": "tutorial",
}
# Backwards-compatible private alias for existing loader call sites.
_CASE_KIND_BY_WORKFLOW = CASE_KIND_BY_WORKFLOW
_MAX_CASE_KIND_CHARS = 64
_UNIT_COLUMNS = (
    "unit_id",
    "title",
    "type",
    "skill",
    "inputs",
    "outputs",
    "acceptance",
    "checkpoint",
    "status",
    "depends_on",
    "owner",
)


def load_workflow_definition(
    pipeline_path: Path | str,
    *,
    repo_root: Path | str | None = None,
    units_path: Path | str | None = None,
    allowed_root: Path | str | None = None,
    skill_catalog: Iterable[str] | None = None,
    quality_check_catalog: Iterable[str] | None = None,
    validate_capabilities: Literal["auto", "required", "structural"] = "auto",
) -> WorkflowDefinition:
    """Load and compile one Pipeline frontmatter plus one UNITS CSV contract.

    ``repo_root`` confines the selected Pipeline, its variant chain, and an
    automatically resolved ``units_template`` to one repository. ``units_path``
    is the explicit adapter for snapshot-backed Runs and may live outside that
    repository. Callers that also pass ``allowed_root`` explicitly confine the
    Pipeline/variant chain (when no ``repo_root`` is supplied) and every
    explicit ``units_path`` after symlink resolution.

    Repository loads validate Skills against ``repo_root/.codex/skills`` and
    completion checks against the authoritative Harness registry. Isolated
    callers may inject ``skill_catalog`` and ``quality_check_catalog`` without
    introducing a repository dependency. Capability mode ``auto`` validates
    every available catalog and is explicitly structural-only when no
    ``repo_root`` or injected catalog exists. ``required`` fails unless both
    catalogs are available. ``structural`` documents an intentional catalog-free
    isolated/snapshot load and cannot be combined with repository/catalog inputs.
    """

    source = Path(pipeline_path).expanduser().resolve()
    root = Path(repo_root).expanduser().resolve() if repo_root is not None else None
    explicit_allowed_root = (
        Path(allowed_root).expanduser().resolve() if allowed_root is not None else None
    )
    contract_root = root if root is not None else explicit_allowed_root
    _validate_capability_mode(
        validate_capabilities,
        source=source,
        repo_root=root,
        skill_catalog=skill_catalog,
        quality_check_catalog=quality_check_catalog,
    )
    _require_path_within(
        source,
        contract_root,
        code="pipeline_outside_allowed_root",
        message="selected Pipeline is outside the allowed contract root",
        field="pipeline_path",
    )
    _, frontmatter = _load_effective_frontmatter(source, allowed_root=contract_root)
    issues: list[WorkflowContractIssue] = []

    name = _required_text(frontmatter, "name", source=source, issues=issues)
    version = _required_text(frontmatter, "version", source=source, issues=issues)
    profile = _required_text(frontmatter, "profile", source=source, issues=issues)
    contract_model = _required_text(
        frontmatter, "contract_model", source=source, issues=issues
    )
    units_template = _required_text(
        frontmatter, "units_template", source=source, issues=issues
    )
    default_checkpoints = _string_tuple(
        frontmatter.get("default_checkpoints"),
        field="default_checkpoints",
        source=source,
        issues=issues,
        required=True,
    )
    target_artifacts = _string_tuple(
        frontmatter.get("target_artifacts"),
        field="target_artifacts",
        source=source,
        issues=issues,
        required=True,
    )
    case_contract = _parse_case_contract(
        frontmatter.get("case_contract"),
        target_artifacts=target_artifacts,
        source=source,
        issues=issues,
    )
    expected_case_kind = _CASE_KIND_BY_WORKFLOW.get(name)
    if (
        expected_case_kind is not None
        and case_contract.kind
        and case_contract.kind != expected_case_kind
    ):
        issues.append(
            _issue(
                "case_kind_workflow_drift",
                f"Workflow `{name}` must project as Loop kind `{expected_case_kind}`",
                source,
                "case_contract.kind",
            )
        )
    stages = _parse_stages(frontmatter.get("stages"), source=source, issues=issues)
    quality_contract, required_checks = _parse_quality_contract(
        frontmatter.get("quality_contract"), source=source, issues=issues
    )

    if contract_model and contract_model != _CONTRACT_MODEL:
        issues.append(
            _issue(
                "unsupported_contract_model",
                f"expected `{_CONTRACT_MODEL}`, got `{contract_model}`",
                source,
                "contract_model",
            )
        )
    _report_duplicates(default_checkpoints, "default_checkpoints", source, issues)
    _report_duplicates(target_artifacts, "target_artifacts", source, issues)
    _validate_artifact_paths(
        target_artifacts, field="target_artifacts", source=source, issues=issues
    )

    if issues:
        raise WorkflowValidationError(issues)

    resolved_units_path = _resolve_units_source(
        pipeline_source=source,
        units_template=units_template,
        repo_root=root,
        explicit_units_path=units_path,
        allowed_root=explicit_allowed_root,
    )
    units = _load_units(resolved_units_path)
    issues.extend(
        _validate_contract(
            source=source,
            units_source=resolved_units_path,
            default_checkpoints=default_checkpoints,
            target_artifacts=target_artifacts,
            stages=stages,
            units=units,
            required_checks=required_checks,
        )
    )
    declared_skills = {
        skill
        for stage in stages
        for skill in (*stage.required_skills, *stage.optional_skills)
    }
    declared_skills.update(unit.skill for unit in units)
    structural_only = validate_capabilities == "structural" or (
        validate_capabilities == "auto"
        and root is None
        and skill_catalog is None
        and quality_check_catalog is None
    )
    resolved_skill_catalog = (
        None
        if structural_only
        else _resolve_skill_catalog(repo_root=root, injected=skill_catalog)
    )
    resolved_quality_checks = (
        None
        if structural_only
        else _resolve_quality_check_catalog(
            repo_root=root,
            injected=quality_check_catalog,
        )
    )
    if validate_capabilities == "required":
        if resolved_skill_catalog is None:
            issues.append(
                _issue(
                    "skill_catalog_unavailable",
                    "capability validation requires a repository or injected Skill catalog",
                    source,
                    "skill_catalog",
                )
            )
        if resolved_quality_checks is None:
            issues.append(
                _issue(
                    "quality_check_catalog_unavailable",
                    "capability validation requires a repository or injected quality-check catalog",
                    source,
                    "quality_check_catalog",
                )
            )
    if resolved_skill_catalog is not None:
        missing_skills = sorted(declared_skills - resolved_skill_catalog)
        if missing_skills:
            issues.append(
                _issue(
                    "unknown_workflow_skill",
                    "Workflow references Skill(s) missing from the catalog: "
                    + ", ".join(missing_skills),
                    source,
                    "stages/units.skill",
                )
            )
    if resolved_quality_checks is not None:
        missing_checks = sorted(set(required_checks) - resolved_quality_checks)
        if missing_checks:
            issues.append(
                _issue(
                    "unregistered_quality_check",
                    "required completion check(s) have no registered Harness checker: "
                    + ", ".join(missing_checks),
                    source,
                    "quality_contract.completion_policy.required_checks",
                )
            )
    if issues:
        raise WorkflowValidationError(issues)

    return WorkflowDefinition(
        source=source,
        units_source=resolved_units_path,
        name=name,
        version=version,
        profile=profile,
        contract_model=contract_model,
        units_template=units_template,
        default_checkpoints=default_checkpoints,
        target_artifacts=target_artifacts,
        case_contract=case_contract,
        stages=stages,
        units=units,
        quality_contract=quality_contract,
        variant_of=str(frontmatter.get("variant_of") or "").strip(),
    )


class _DuplicateYamlKey(yaml.YAMLError):
    def __init__(self, key: object, line: int) -> None:
        self.key = key
        self.line = line
        super().__init__(f"duplicate YAML key {key!r} at line {line}")


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[object, object]:
    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found unhashable key ({exc})",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise _DuplicateYamlKey(key, key_node.start_mark.line + 2)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _parse_frontmatter(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise WorkflowSourceError(
            [_issue("pipeline_not_found", "Pipeline file does not exist", path)]
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise WorkflowSourceError(
            [
                _issue(
                    "pipeline_unreadable",
                    f"cannot read Pipeline: {type(exc).__name__}: {exc}",
                    path,
                )
            ]
        ) from exc

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise WorkflowSyntaxError(
            [
                _issue(
                    "missing_frontmatter",
                    "Pipeline must start with YAML frontmatter `---`",
                    path,
                )
            ]
        )
    end_index = next(
        (
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        ),
        None,
    )
    if end_index is None:
        raise WorkflowSyntaxError(
            [
                _issue(
                    "unterminated_frontmatter",
                    "missing closing frontmatter `---`",
                    path,
                )
            ]
        )
    raw = "\n".join(lines[1:end_index])
    try:
        parsed = yaml.load(raw, Loader=_UniqueKeyLoader) or {}
    except _DuplicateYamlKey as exc:
        raise WorkflowSyntaxError(
            [
                _issue(
                    "duplicate_yaml_key",
                    f"duplicate key `{exc.key}` (frontmatter line {exc.line})",
                    path,
                )
            ]
        ) from exc
    except yaml.YAMLError as exc:
        problem = getattr(exc, "problem", None) or str(exc)
        mark = getattr(exc, "problem_mark", None)
        suffix = f" at frontmatter line {mark.line + 2}" if mark is not None else ""
        raise WorkflowSyntaxError(
            [_issue("invalid_yaml", f"{problem}{suffix}", path)]
        ) from exc
    if not isinstance(parsed, dict):
        raise WorkflowSyntaxError(
            [
                _issue(
                    "frontmatter_not_mapping",
                    "Pipeline frontmatter must be a mapping",
                    path,
                )
            ]
        )
    non_string_keys = [key for key in parsed if not isinstance(key, str)]
    if non_string_keys:
        raise WorkflowSyntaxError(
            [
                _issue(
                    "non_string_yaml_key",
                    f"top-level key must be a string, got {key!r}",
                    path,
                )
                for key in non_string_keys
            ]
        )
    return parsed


def _load_effective_frontmatter(
    path: Path,
    *,
    active: tuple[Path, ...] = (),
    allowed_root: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = path.resolve()
    _require_path_within(
        source,
        allowed_root,
        code="variant_outside_allowed_root",
        message="Pipeline variant dependency is outside the allowed contract root",
        field="variant_of",
    )
    if source in active:
        chain = " -> ".join(str(item) for item in (*active, source))
        raise WorkflowValidationError(
            [
                _issue(
                    "cyclic_variant",
                    f"cyclic `variant_of` chain: {chain}",
                    source,
                    "variant_of",
                )
            ]
        )
    raw = _parse_frontmatter(source)
    variant_of = str(raw.get("variant_of") or "").strip()
    if not variant_of:
        return raw, dict(raw)

    allowed = {"name", "version", "variant_of", "variant_overrides"}
    extra = sorted(key for key in raw if key not in allowed)
    variant_issues: list[WorkflowContractIssue] = []
    if extra:
        variant_issues.append(
            _issue(
                "variant_top_level_drift",
                "variant behavior must live under `variant_overrides`; unexpected keys: "
                + ", ".join(extra),
                source,
            )
        )
    overrides = raw.get("variant_overrides")
    if not isinstance(overrides, dict):
        variant_issues.append(
            _issue(
                "invalid_variant_overrides",
                "`variant_overrides` must be a mapping",
                source,
                "variant_overrides",
            )
        )
    if variant_issues:
        raise WorkflowValidationError(variant_issues)

    base_source = _resolve_variant_reference(
        source,
        variant_of,
        allowed_root=allowed_root,
    )
    _, base = _load_effective_frontmatter(
        base_source,
        active=(*active, source),
        allowed_root=allowed_root,
    )
    identity = {key: raw[key] for key in ("name", "version") if key in raw}
    effective = _deep_merge(base, identity, source=source, field="")
    effective = _deep_merge(
        effective, overrides, source=source, field="variant_overrides"
    )
    effective["variant_of"] = variant_of
    return raw, effective


def _resolve_variant_reference(
    source: Path,
    reference: str,
    *,
    allowed_root: Path | None,
) -> Path:
    candidate = Path(reference)
    candidates: list[Path] = []
    if candidate.is_absolute():
        candidates.append(candidate)
    else:
        probable_root = source.parent.parent
        candidates.extend(
            (
                source.parent / candidate,
                probable_root / candidate,
                probable_root / "pipelines" / candidate,
            )
        )
        stem = candidate.name
        if stem.endswith(".pipeline.md"):
            stem = stem[: -len(".pipeline.md")]
        if stem:
            candidates.extend(
                (
                    source.parent / f"{stem}.pipeline.md",
                    probable_root / "pipelines" / f"{stem}.pipeline.md",
                )
            )
    for path in candidates:
        if path.is_file():
            resolved = path.resolve()
            _require_path_within(
                resolved,
                allowed_root,
                code="variant_outside_allowed_root",
                message="resolved `variant_of` parent is outside the allowed contract root",
                field="variant_of",
            )
            return resolved
    raise WorkflowSourceError(
        [
            _issue(
                "variant_not_found",
                f"cannot resolve `variant_of: {reference}` from Pipeline directory",
                source,
                "variant_of",
            )
        ]
    )


def _deep_merge(base: Any, override: Any, *, source: Path, field: str) -> Any:
    if (
        isinstance(base, list)
        and isinstance(override, dict)
        and any(str(key).startswith("__") for key in override)
    ):
        return _apply_list_patch(base, override, source=source, field=field)
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for key, value in override.items():
            child_field = f"{field}.{key}".strip(".")
            merged[key] = (
                _deep_merge(merged[key], value, source=source, field=child_field)
                if key in merged
                else value
            )
        return merged
    return override


def _apply_list_patch(
    base: list[Any], override: dict[str, Any], *, source: Path, field: str
) -> list[Any]:
    allowed = {"__append__", "__prepend__", "__remove__", "__replace__"}
    unknown = sorted(str(key) for key in override if key not in allowed)
    issues: list[WorkflowContractIssue] = []
    if unknown:
        issues.append(
            _issue(
                "unknown_list_patch",
                "unsupported list patch operator(s): " + ", ".join(unknown),
                source,
                field,
            )
        )
    for operator, value in override.items():
        if operator in allowed and not isinstance(value, list):
            issues.append(
                _issue(
                    "invalid_list_patch",
                    f"`{operator}` must contain a YAML list",
                    source,
                    field,
                )
            )
    if issues:
        raise WorkflowValidationError(issues)
    if "__replace__" in override:
        return list(override["__replace__"])
    current = [item for item in base if item not in override.get("__remove__", [])]
    return [*override.get("__prepend__", []), *current, *override.get("__append__", [])]


def _required_text(
    mapping: Mapping[str, Any],
    key: str,
    *,
    source: Path,
    issues: list[WorkflowContractIssue],
) -> str:
    value = mapping.get(key)
    text = str(value).strip() if value is not None else ""
    if not text:
        issues.append(
            _issue("missing_pipeline_field", "required field is empty", source, key)
        )
    return text


def _string_tuple(
    value: Any,
    *,
    field: str,
    source: Path,
    issues: list[WorkflowContractIssue],
    required: bool,
) -> tuple[str, ...]:
    if value is None:
        if required:
            issues.append(
                _issue(
                    "missing_pipeline_field", "required list is missing", source, field
                )
            )
        return ()
    if not isinstance(value, list):
        issues.append(
            _issue("invalid_pipeline_list", "must be a YAML list", source, field)
        )
        return ()
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            issues.append(
                _issue(
                    "invalid_pipeline_list_item",
                    "items must be non-empty strings",
                    source,
                    f"{field}[{index}]",
                )
            )
            continue
        result.append(item.strip())
    if required and not result:
        issues.append(
            _issue(
                "empty_pipeline_list", "must contain at least one item", source, field
            )
        )
    return tuple(result)


def _parse_case_contract(
    value: Any,
    *,
    target_artifacts: tuple[str, ...],
    source: Path,
    issues: list[WorkflowContractIssue],
) -> LoopContract:
    field = "case_contract"
    if value is None:
        issues.append(
            _issue(
                "missing_pipeline_field",
                "required Loop projection contract is missing",
                source,
                field,
            )
        )
        mapping: Mapping[str, Any] = {}
    elif not isinstance(value, dict):
        issues.append(
            _issue(
                "invalid_case_contract",
                "must be a mapping",
                source,
                field,
            )
        )
        mapping = {}
    else:
        mapping = value

    unknown = sorted(str(key) for key in mapping if key not in _CASE_CONTRACT_FIELDS)
    if unknown:
        issues.append(
            _issue(
                "unexpected_case_contract_field",
                "unexpected field(s): " + ", ".join(unknown),
                source,
                field,
            )
        )

    raw_kind = mapping.get("kind")
    if raw_kind is None:
        issues.append(
            _issue(
                "missing_pipeline_field",
                "required field is missing",
                source,
                f"{field}.kind",
            )
        )
        kind = ""
    elif not isinstance(raw_kind, str):
        issues.append(
            _issue(
                "invalid_case_kind",
                "must be non-empty text of at most 64 characters",
                source,
                f"{field}.kind",
            )
        )
        kind = ""
    else:
        kind = raw_kind.strip()
        if (
            not kind
            or len(kind) > _MAX_CASE_KIND_CHARS
            or _contains_control_character(kind)
        ):
            issues.append(
                _issue(
                    "invalid_case_kind",
                    "must be non-empty single-line text of at most 64 characters",
                    source,
                    f"{field}.kind",
                )
            )
        elif kind not in _CASE_KINDS:
            issues.append(
                _issue(
                    "invalid_case_kind",
                    "must be one of: " + ", ".join(_CASE_KINDS),
                    source,
                    f"{field}.kind",
                )
            )

    target_set = set(target_artifacts)
    parsed_paths: dict[str, tuple[str, ...]] = {}
    for name in _CASE_CONTRACT_FIELDS[1:]:
        path_field = f"{field}.{name}"
        paths = _string_tuple(
            mapping.get(name),
            field=path_field,
            source=source,
            issues=issues,
            required=True,
        )
        _report_duplicates(paths, path_field, source, issues)
        _validate_artifact_paths(
            paths,
            field=path_field,
            source=source,
            issues=issues,
        )
        missing_targets = tuple(path for path in paths if path not in target_set)
        if missing_targets:
            issues.append(
                _issue(
                    "case_contract_target_drift",
                    "path(s) are not effective target_artifacts: "
                    + ", ".join(missing_targets),
                    source,
                    path_field,
                )
            )
        parsed_paths[name] = paths

    return LoopContract(
        kind=kind,
        views=parsed_paths["views"],
        claim_sources=parsed_paths["claim_sources"],
        evidence_sources=parsed_paths["evidence_sources"],
        decision_sources=parsed_paths["decision_sources"],
    )


def _parse_stages(
    value: Any, *, source: Path, issues: list[WorkflowContractIssue]
) -> tuple[StageDefinition, ...]:
    if value is None:
        issues.append(
            _issue(
                "missing_pipeline_field",
                "required stage mapping is missing",
                source,
                "stages",
            )
        )
        return ()

    raw_stages: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        raw_stages = [(str(stage_id).strip(), item) for stage_id, item in value.items()]
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                issues.append(
                    _issue(
                        "invalid_stage",
                        "stage must be a mapping",
                        source,
                        f"stages[{index}]",
                    )
                )
                continue
            stage_id = str(item.get("id") or item.get("stage") or "").strip()
            raw_stages.append((stage_id, item))
    else:
        issues.append(
            _issue("invalid_stages", "must be a mapping or list", source, "stages")
        )
        return ()

    definitions: list[StageDefinition] = []
    for index, (stage_id, item) in enumerate(raw_stages):
        field = f"stages.{stage_id}" if stage_id else f"stages[{index}]"
        if not stage_id:
            issues.append(
                _issue("missing_stage_id", "stage id is empty", source, field)
            )
            continue
        if not isinstance(item, dict):
            issues.append(
                _issue("invalid_stage", "stage must be a mapping", source, field)
            )
            continue
        required_skills = _string_tuple(
            item.get("required_skills"),
            field=f"{field}.required_skills",
            source=source,
            issues=issues,
            required=True,
        )
        optional_skills = _string_tuple(
            item.get("optional_skills"),
            field=f"{field}.optional_skills",
            source=source,
            issues=issues,
            required=False,
        )
        produces = _string_tuple(
            item.get("produces"),
            field=f"{field}.produces",
            source=source,
            issues=issues,
            required=True,
        )
        checkpoint = str(item.get("checkpoint") or stage_id).strip()
        mode = str(item.get("mode") or "").strip()
        human_checkpoint = item.get("human_checkpoint")
        if human_checkpoint is None:
            human_checkpoint = {}
        elif not isinstance(human_checkpoint, dict):
            issues.append(
                _issue(
                    "invalid_human_checkpoint",
                    "must be a mapping",
                    source,
                    f"{field}.human_checkpoint",
                )
            )
            human_checkpoint = {}

        _report_duplicates(required_skills, f"{field}.required_skills", source, issues)
        _report_duplicates(optional_skills, f"{field}.optional_skills", source, issues)
        _report_duplicates(produces, f"{field}.produces", source, issues)
        overlap = sorted(set(required_skills).intersection(optional_skills))
        if overlap:
            issues.append(
                _issue(
                    "duplicate_stage_skill_role",
                    "skill is both required and optional: " + ", ".join(overlap),
                    source,
                    field,
                )
            )
        if mode not in _STAGE_MODES:
            issues.append(
                _issue(
                    "invalid_stage_mode",
                    "expected one of " + ", ".join(sorted(_STAGE_MODES)),
                    source,
                    f"{field}.mode",
                )
            )
        _validate_artifact_paths(
            produces, field=f"{field}.produces", source=source, issues=issues
        )
        definitions.append(
            StageDefinition(
                id=stage_id,
                title=str(item.get("title") or stage_id).strip() or stage_id,
                checkpoint=checkpoint,
                mode=mode,
                required_skills=required_skills,
                optional_skills=optional_skills,
                produces=produces,
                human_checkpoint=_freeze_mapping(human_checkpoint),
            )
        )
    _report_duplicates(
        tuple(stage.id for stage in definitions), "stages", source, issues
    )
    if not definitions:
        issues.append(
            _issue("empty_stages", "must declare at least one stage", source, "stages")
        )
    return tuple(definitions)


def _parse_quality_contract(
    value: Any, *, source: Path, issues: list[WorkflowContractIssue]
) -> tuple[Mapping[str, Any], tuple[str, ...]]:
    if value is None:
        issues.append(
            _issue(
                "missing_required_checks",
                "quality contract must declare a non-empty `required_checks` list",
                source,
                "quality_contract.completion_policy.required_checks",
            )
        )
        return MappingProxyType({}), ()
    if not isinstance(value, dict):
        issues.append(
            _issue(
                "invalid_quality_contract",
                "must be a mapping",
                source,
                "quality_contract",
            )
        )
        return MappingProxyType({}), ()
    completion = value.get("completion_policy")
    if completion is None:
        issues.append(
            _issue(
                "missing_required_checks",
                "completion policy must declare a non-empty `required_checks` list",
                source,
                "quality_contract.completion_policy.required_checks",
            )
        )
        checks: tuple[str, ...] = ()
    elif not isinstance(completion, dict):
        issues.append(
            _issue(
                "invalid_completion_policy",
                "must be a mapping",
                source,
                "quality_contract.completion_policy",
            )
        )
        checks = ()
    else:
        checks = _string_tuple(
            completion.get("required_checks"),
            field="quality_contract.completion_policy.required_checks",
            source=source,
            issues=issues,
            required=True,
        )
        _report_duplicates(
            checks,
            "quality_contract.completion_policy.required_checks",
            source,
            issues,
        )
    return _freeze_mapping(value), checks


def _resolve_units_source(
    *,
    pipeline_source: Path,
    units_template: str,
    repo_root: Path | None,
    explicit_units_path: Path | str | None,
    allowed_root: Path | None,
) -> Path:
    if explicit_units_path is not None:
        selected = Path(explicit_units_path).expanduser().resolve()
        _require_path_within(
            selected,
            allowed_root,
            code="units_outside_allowed_root",
            message="explicit UNITS file is outside the allowed root",
            field="units_path",
        )
        if selected.is_file():
            return selected
        raise WorkflowSourceError(
            [_issue("units_not_found", "explicit UNITS file does not exist", selected)]
        )

    relative = Path(units_template)
    if relative.is_absolute() or ".." in relative.parts:
        raise WorkflowValidationError(
            [
                _issue(
                    "unsafe_units_template",
                    "`units_template` must be a repository-relative path without `..`",
                    pipeline_source,
                    "units_template",
                )
            ]
        )
    candidates: list[Path] = []
    if repo_root is not None:
        candidates.append(repo_root / relative)
    elif allowed_root is not None:
        candidates.append(allowed_root / relative)
    else:
        candidates.extend(parent / relative for parent in pipeline_source.parents)
    for candidate in candidates:
        if candidate.is_file():
            resolved = candidate.resolve()
            confinement_root = repo_root if repo_root is not None else allowed_root
            _require_path_within(
                resolved,
                confinement_root,
                code="units_outside_allowed_root",
                message="resolved `units_template` is outside the allowed contract root",
                field="units_template",
            )
            return resolved
    searched = ", ".join(str(path) for path in candidates[:4])
    raise WorkflowSourceError(
        [
            _issue(
                "units_not_found",
                f"cannot resolve `{units_template}`"
                + (f"; searched: {searched}" if searched else ""),
                pipeline_source,
                "units_template",
            )
        ]
    )


def _require_path_within(
    path: Path,
    allowed_root: Path | None,
    *,
    code: str,
    message: str,
    field: str,
) -> None:
    if allowed_root is None or path.is_relative_to(allowed_root):
        return
    raise WorkflowValidationError(
        [
            _issue(
                code,
                f"{message}: `{path}` is not inside `{allowed_root}`",
                path,
                field,
            )
        ]
    )


def _validate_capability_mode(
    mode: str,
    *,
    source: Path,
    repo_root: Path | None,
    skill_catalog: Iterable[str] | None,
    quality_check_catalog: Iterable[str] | None,
) -> None:
    if mode not in {"auto", "required", "structural"}:
        raise WorkflowValidationError(
            [
                _issue(
                    "invalid_capability_validation_mode",
                    "expected `auto`, `required`, or `structural`",
                    source,
                    "validate_capabilities",
                )
            ]
        )
    if mode == "structural" and (
        repo_root is not None
        or skill_catalog is not None
        or quality_check_catalog is not None
    ):
        raise WorkflowValidationError(
            [
                _issue(
                    "structural_capability_mode_conflict",
                    "structural-only mode cannot ignore a repository or injected capability catalog",
                    source,
                    "validate_capabilities",
                )
            ]
        )


def _resolve_skill_catalog(
    *,
    repo_root: Path | None,
    injected: Iterable[str] | None,
) -> frozenset[str] | None:
    if injected is not None:
        return _normalized_catalog(injected)
    if repo_root is None:
        return None
    skills_root = repo_root / ".codex" / "skills"
    if not skills_root.is_dir():
        return frozenset()
    return frozenset(
        child.name
        for child in skills_root.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    )


def _resolve_quality_check_catalog(
    *,
    repo_root: Path | None,
    injected: Iterable[str] | None,
) -> frozenset[str] | None:
    if injected is not None:
        return _normalized_catalog(injected)
    if repo_root is None:
        return None

    # Transitional adapter: this is the authoritative registry until quality
    # checks move behind the typed acceptance seam. The import stays lazy so isolated Workflow
    # parsing remains independent of the legacy Harness implementation.
    from tooling.quality_gate import registered_quality_skills

    return frozenset(registered_quality_skills())


def _normalized_catalog(values: Iterable[str]) -> frozenset[str]:
    return frozenset(text for value in values if (text := str(value or "").strip()))


def _load_units(source: Path) -> tuple[UnitDefinition, ...]:
    try:
        with source.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle, strict=True))
    except FileNotFoundError as exc:
        raise WorkflowSourceError(
            [_issue("units_not_found", "UNITS CSV does not exist", source)]
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise WorkflowSourceError(
            [
                _issue(
                    "units_unreadable",
                    f"cannot read UNITS CSV: {type(exc).__name__}: {exc}",
                    source,
                )
            ]
        ) from exc
    except csv.Error as exc:
        raise WorkflowSyntaxError(
            [_issue("invalid_units_csv", str(exc), source)]
        ) from exc

    if not rows:
        raise WorkflowSyntaxError(
            [_issue("empty_units_csv", "UNITS CSV is empty", source)]
        )
    header = tuple(cell.strip() for cell in rows[0])
    header_counts = Counter(header)
    duplicates = sorted(
        name for name, count in header_counts.items() if name and count > 1
    )
    syntax_issues: list[WorkflowContractIssue] = []
    if duplicates:
        syntax_issues.append(
            _issue(
                "duplicate_units_column",
                "duplicate column(s): " + ", ".join(duplicates),
                source,
                "header",
            )
        )
    missing = [column for column in _UNIT_COLUMNS if column not in header]
    unexpected = [column for column in header if column not in _UNIT_COLUMNS]
    if missing:
        syntax_issues.append(
            _issue(
                "missing_units_column",
                "missing required column(s): " + ", ".join(missing),
                source,
                "header",
            )
        )
    if unexpected:
        syntax_issues.append(
            _issue(
                "unexpected_units_column",
                "unexpected column(s): " + ", ".join(unexpected),
                source,
                "header",
            )
        )
    if syntax_issues:
        raise WorkflowSyntaxError(syntax_issues)

    issues: list[WorkflowContractIssue] = []
    definitions: list[UnitDefinition] = []
    for line_number, raw_row in enumerate(rows[1:], start=2):
        if not raw_row or all(not cell.strip() for cell in raw_row):
            continue
        if len(raw_row) != len(header):
            issues.append(
                _issue(
                    "units_row_width",
                    f"expected {len(header)} cells, got {len(raw_row)}",
                    source,
                    f"row {line_number}",
                )
            )
            continue
        row = {name: value.strip() for name, value in zip(header, raw_row, strict=True)}
        unit_id = row["unit_id"]
        field = f"row {line_number}"
        for column in (
            "unit_id",
            "title",
            "type",
            "skill",
            "acceptance",
            "checkpoint",
            "status",
            "owner",
        ):
            if not row[column]:
                issues.append(
                    _issue(
                        "empty_unit_field",
                        "required value is empty",
                        source,
                        f"{field}.{column}",
                    )
                )
        inputs = _semicolon_tuple(row["inputs"])
        outputs = _semicolon_tuple(row["outputs"])
        depends_on = _semicolon_tuple(row["depends_on"])
        for column, values in (
            ("inputs", inputs),
            ("outputs", outputs),
            ("depends_on", depends_on),
        ):
            _report_duplicates(values, f"{field}.{column}", source, issues)
        if any(output == "?" for output in outputs):
            issues.append(
                _issue(
                    "empty_optional_output",
                    "optional output marker `?` must prefix a path",
                    source,
                    f"{field}.outputs",
                )
            )
        _validate_artifact_paths(
            inputs,
            field=f"{field}.inputs",
            source=source,
            issues=issues,
            allow_directory=True,
        )
        _validate_artifact_paths(
            tuple(value.removeprefix("?") for value in outputs),
            field=f"{field}.outputs",
            source=source,
            issues=issues,
        )
        definitions.append(
            UnitDefinition(
                id=unit_id,
                title=row["title"],
                type=row["type"],
                skill=row["skill"],
                inputs=inputs,
                outputs=outputs,
                acceptance=row["acceptance"],
                checkpoint=row["checkpoint"],
                status=row["status"],
                depends_on=depends_on,
                owner=row["owner"],
            )
        )
    if not definitions:
        issues.append(
            _issue("empty_units", "UNITS CSV must contain at least one Unit", source)
        )
    if issues:
        raise WorkflowValidationError(issues)
    return tuple(definitions)


def _validate_contract(
    *,
    source: Path,
    units_source: Path,
    default_checkpoints: tuple[str, ...],
    target_artifacts: tuple[str, ...],
    stages: tuple[StageDefinition, ...],
    units: tuple[UnitDefinition, ...],
    required_checks: tuple[str, ...],
) -> list[WorkflowContractIssue]:
    issues: list[WorkflowContractIssue] = []
    stage_ids = tuple(stage.id for stage in stages)
    if default_checkpoints != stage_ids:
        issues.append(
            _issue(
                "checkpoint_stage_drift",
                f"default_checkpoints {default_checkpoints!r} do not match ordered stage ids {stage_ids!r}",
                source,
                "default_checkpoints",
            )
        )
    for stage in stages:
        if stage.checkpoint != stage.id:
            issues.append(
                _issue(
                    "stage_checkpoint_drift",
                    f"stage checkpoint `{stage.checkpoint}` does not match stage id `{stage.id}`",
                    source,
                    f"stages.{stage.id}.checkpoint",
                )
            )

    unit_counts = Counter(unit.id for unit in units)
    duplicate_ids = sorted(
        unit_id for unit_id, count in unit_counts.items() if count > 1
    )
    if duplicate_ids:
        issues.append(
            _issue(
                "duplicate_unit_id",
                "duplicate Unit id(s): " + ", ".join(duplicate_ids),
                units_source,
                "unit_id",
            )
        )

    stage_by_checkpoint = {stage.checkpoint: stage for stage in stages}
    for unit in units:
        unit_field = f"unit {unit.id or '<empty>'}"
        if not _UNIT_ID.fullmatch(unit.id):
            issues.append(
                _issue(
                    "invalid_unit_id",
                    "expected `U` followed by at least three digits (for example `U001`)",
                    units_source,
                    f"{unit_field}.unit_id",
                )
            )
        if unit.type not in _UNIT_TYPES:
            issues.append(
                _issue(
                    "invalid_unit_type",
                    "expected one of " + ", ".join(sorted(_UNIT_TYPES)),
                    units_source,
                    f"{unit_field}.type",
                )
            )
        if unit.status not in _UNIT_STATUSES:
            issues.append(
                _issue(
                    "invalid_unit_status",
                    "expected one of " + ", ".join(sorted(_UNIT_STATUSES)),
                    units_source,
                    f"{unit_field}.status",
                )
            )
        if unit.owner not in _UNIT_OWNERS:
            issues.append(
                _issue(
                    "invalid_unit_owner",
                    "expected HUMAN or CODEX",
                    units_source,
                    f"{unit_field}.owner",
                )
            )
        stage = stage_by_checkpoint.get(unit.checkpoint)
        if stage is None:
            issues.append(
                _issue(
                    "unknown_unit_checkpoint",
                    f"checkpoint `{unit.checkpoint}` is not declared by the Pipeline",
                    units_source,
                    f"{unit_field}.checkpoint",
                )
            )
            continue
        declared_skills = set((*stage.required_skills, *stage.optional_skills))
        if unit.skill not in declared_skills:
            issues.append(
                _issue(
                    "unit_skill_stage_drift",
                    f"skill `{unit.skill}` is not required or optional in stage `{stage.id}`",
                    units_source,
                    f"{unit_field}.skill",
                )
            )
        declared_outputs = set(stage.produces)
        for output in unit.outputs:
            normalized = output.removeprefix("?")
            if normalized not in declared_outputs:
                issues.append(
                    _issue(
                        "unit_output_stage_drift",
                        f"output `{normalized}` is not produced by stage `{stage.id}`",
                        units_source,
                        f"{unit_field}.outputs",
                    )
                )

    issues.extend(_validate_stage_unit_projection(source, units_source, stages, units))
    issues.extend(_validate_dag(units_source, units))

    produced = {artifact for stage in stages for artifact in stage.produces}
    for target in target_artifacts:
        if target not in produced:
            issues.append(
                _issue(
                    "target_artifact_not_produced",
                    f"target artifact `{target}` is absent from all stage outputs",
                    source,
                    "target_artifacts",
                )
            )

    required_skills = {skill for stage in stages for skill in stage.required_skills}
    for check in required_checks:
        if check not in required_skills:
            issues.append(
                _issue(
                    "required_check_skill_drift",
                    f"completion check `{check}` is not a required Workflow skill",
                    source,
                    "quality_contract.completion_policy.required_checks",
                )
            )
    issues.extend(_validate_human_checkpoints(source, units_source, stages, units))
    return issues


def _validate_stage_unit_projection(
    source: Path,
    units_source: Path,
    stages: tuple[StageDefinition, ...],
    units: tuple[UnitDefinition, ...],
) -> list[WorkflowContractIssue]:
    issues: list[WorkflowContractIssue] = []
    for stage in stages:
        stage_units = tuple(
            unit for unit in units if unit.checkpoint == stage.checkpoint
        )
        unit_skills = {unit.skill for unit in stage_units}
        unit_outputs = {
            output.removeprefix("?") for unit in stage_units for output in unit.outputs
        }
        for skill in stage.required_skills:
            if skill not in unit_skills:
                issues.append(
                    _issue(
                        "stage_skill_units_drift",
                        f"required skill `{skill}` has no Unit in checkpoint `{stage.checkpoint}`",
                        source,
                        f"stages.{stage.id}.required_skills",
                    )
                )
        for output in stage.produces:
            if output not in unit_outputs:
                issues.append(
                    _issue(
                        "stage_output_units_drift",
                        f"stage output `{output}` has no producing Unit in checkpoint `{stage.checkpoint}`",
                        units_source,
                        f"checkpoint {stage.checkpoint}",
                    )
                )
    return issues


def _validate_dag(
    source: Path, units: tuple[UnitDefinition, ...]
) -> list[WorkflowContractIssue]:
    issues: list[WorkflowContractIssue] = []
    unit_ids = {unit.id for unit in units}
    graph: dict[str, tuple[str, ...]] = {}
    for unit in units:
        graph.setdefault(unit.id, unit.depends_on)
        for dependency in unit.depends_on:
            if dependency == unit.id:
                issues.append(
                    _issue(
                        "unit_self_dependency",
                        "Unit cannot depend on itself",
                        source,
                        f"unit {unit.id}.depends_on",
                    )
                )
            elif dependency not in unit_ids:
                issues.append(
                    _issue(
                        "unknown_unit_dependency",
                        f"dependency `{dependency}` is not a declared Unit",
                        source,
                        f"unit {unit.id}.depends_on",
                    )
                )

    state: dict[str, int] = {}
    stack: list[str] = []
    reported: set[frozenset[str]] = set()

    def visit(unit_id: str) -> None:
        state[unit_id] = 1
        stack.append(unit_id)
        for dependency in graph.get(unit_id, ()):
            if dependency not in graph or dependency == unit_id:
                continue
            dependency_state = state.get(dependency, 0)
            if dependency_state == 0:
                visit(dependency)
            elif dependency_state == 1:
                start = stack.index(dependency)
                cycle = (*stack[start:], dependency)
                identity = frozenset(cycle)
                if identity not in reported:
                    reported.add(identity)
                    issues.append(
                        _issue(
                            "unit_dependency_cycle",
                            "dependency cycle: " + " -> ".join(cycle),
                            source,
                            "depends_on",
                        )
                    )
        stack.pop()
        state[unit_id] = 2

    for unit_id in graph:
        if state.get(unit_id, 0) == 0:
            visit(unit_id)
    return issues


def _validate_human_checkpoints(
    pipeline_source: Path,
    units_source: Path,
    stages: tuple[StageDefinition, ...],
    units: tuple[UnitDefinition, ...],
) -> list[WorkflowContractIssue]:
    issues: list[WorkflowContractIssue] = []
    for stage in stages:
        stage_units = tuple(
            unit for unit in units if unit.checkpoint == stage.checkpoint
        )
        hitl_implied = "human-checkpoint" in stage.required_skills or any(
            unit.owner == "HUMAN" or unit.skill == "human-checkpoint"
            for unit in stage_units
        )
        if not stage.human_checkpoint and not hitl_implied:
            continue
        field = f"stages.{stage.id}.human_checkpoint"
        if not stage.human_checkpoint:
            issues.append(
                _issue(
                    "human_checkpoint_contract_missing",
                    "stage contains human-controlled work but has no `human_checkpoint` mapping",
                    pipeline_source,
                    field,
                )
            )
        prompt = stage.human_checkpoint.get("approve") or stage.human_checkpoint.get(
            "question"
        )
        if not isinstance(prompt, str) or not prompt.strip():
            issues.append(
                _issue(
                    "human_checkpoint_prompt_missing",
                    "human checkpoint must define a non-empty `approve` or `question`",
                    pipeline_source,
                    field,
                )
            )
        if stage.human_checkpoint.get("write_to") != "DECISIONS.md":
            issues.append(
                _issue(
                    "human_checkpoint_decision_drift",
                    "human checkpoint must set `write_to: DECISIONS.md`",
                    pipeline_source,
                    field,
                )
            )
        human_units = tuple(unit for unit in stage_units if unit.owner == "HUMAN")
        if not human_units:
            issues.append(
                _issue(
                    "human_checkpoint_unit_drift",
                    "human checkpoint stage has no HUMAN-owned Unit",
                    units_source,
                    f"checkpoint {stage.checkpoint}",
                )
            )
        for unit in human_units:
            if "DECISIONS.md" not in unit.inputs or "DECISIONS.md" not in unit.outputs:
                issues.append(
                    _issue(
                        "human_checkpoint_artifact_drift",
                        "human checkpoint Unit must read and write DECISIONS.md",
                        units_source,
                        f"unit {unit.id}",
                    )
                )
    return issues


def _validate_artifact_paths(
    values: Iterable[str],
    *,
    field: str,
    source: Path,
    issues: list[WorkflowContractIssue],
    allow_directory: bool = False,
) -> None:
    for value in values:
        posix_path = PurePosixPath(value)
        windows_path = PureWindowsPath(value)
        raw_parts = value.split("/")
        unsafe = (
            not value
            or value == "."
            or value.startswith("?")
            or posix_path.is_absolute()
            or windows_path.is_absolute()
            or bool(windows_path.drive)
            or any(part in {".", ".."} for part in raw_parts)
            or "\\" in value
            or ";" in value
            or _contains_control_character(value)
            or (value.endswith("/") and not allow_directory)
        )
        if unsafe:
            expected = "Workspace path" if allow_directory else "file path"
            issues.append(
                _issue(
                    "unsafe_artifact_path",
                    f"artifact must be a portable relative {expected}: `{value}`",
                    source,
                    field,
                )
            )


def _contains_control_character(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _report_duplicates(
    values: Sequence[str],
    field: str,
    source: Path,
    issues: list[WorkflowContractIssue],
) -> None:
    counts = Counter(values)
    duplicates = sorted(value for value, count in counts.items() if count > 1)
    if duplicates:
        issues.append(
            _issue(
                "duplicate_contract_value",
                "duplicate value(s): " + ", ".join(duplicates),
                source,
                field,
            )
        )


def _semicolon_tuple(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(";") if item.strip())


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _issue(
    code: str,
    message: str,
    source: Path | None = None,
    field: str = "",
) -> WorkflowContractIssue:
    return WorkflowContractIssue(code=code, message=message, source=source, field=field)
