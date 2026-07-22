from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class PipelineStage:
    id: str
    title: str
    checkpoint: str
    mode: str
    required_skills: tuple[str, ...]
    optional_skills: tuple[str, ...]
    produces: tuple[str, ...]
    human_checkpoint: dict[str, Any]

    @staticmethod
    def from_mapping(stage_id: str, data: Any, *, path: Path) -> "PipelineStage":
        if not isinstance(data, dict):
            raise ValueError(f"`stages.{stage_id}` must be a mapping in {path}")
        return PipelineStage(
            id=str(stage_id or "").strip(),
            title=str(data.get("title") or stage_id).strip() or str(stage_id),
            checkpoint=str(data.get("checkpoint") or stage_id).strip() or str(stage_id),
            mode=str(data.get("mode") or "").strip(),
            required_skills=_string_tuple(data.get("required_skills"), field_name=f"stages.{stage_id}.required_skills", path=path),
            optional_skills=_string_tuple(data.get("optional_skills"), field_name=f"stages.{stage_id}.optional_skills", path=path),
            produces=_string_tuple(data.get("produces"), field_name=f"stages.{stage_id}.produces", path=path),
            human_checkpoint=_mapping(data.get("human_checkpoint"), field_name=f"stages.{stage_id}.human_checkpoint", path=path, required=False),
        )


@dataclass(frozen=True)
class PipelineSpec:
    path: Path
    name: str
    version: str
    units_template: str
    default_checkpoints: tuple[str, ...]
    profile: str
    routing_hints: tuple[str, ...]
    routing_default: bool
    routing_priority: int
    docs_hidden: bool
    target_artifacts: tuple[str, ...]
    contract_model: str
    structure_mode: str
    pre_retrieval_shell: dict[str, Any]
    binding_layers: tuple[str, ...]
    core_chapter_h3_target: int
    query_defaults: dict[str, Any]
    overridable_query_fields: tuple[str, ...]
    quality_contract: dict[str, Any]
    loop_policy: dict[str, Any]
    stages: dict[str, PipelineStage]
    variant_of: str
    variant_overrides: dict[str, Any]

    @staticmethod
    def load(path: Path) -> "PipelineSpec":
        resolved = path.resolve()
        raw_frontmatter, frontmatter = _load_variant_aware_frontmatter(resolved)
        name = str(frontmatter.get("name") or path.stem.replace(".pipeline", ""))
        units_template = str(frontmatter.get("units_template") or "")
        version = str(frontmatter.get("version") or "")
        default_checkpoints = _string_tuple(frontmatter.get("default_checkpoints"), field_name="default_checkpoints", path=resolved)
        profile = str(frontmatter.get("profile") or "default").strip() or "default"
        routing_hints = _string_tuple(frontmatter.get("routing_hints"), field_name="routing_hints", path=resolved)
        routing_default = bool(frontmatter.get("routing_default"))
        try:
            routing_priority = int(frontmatter.get("routing_priority") or 0)
        except Exception:
            routing_priority = 0
        docs_hidden = bool(frontmatter.get("docs_hidden"))
        target_artifacts = _string_tuple(frontmatter.get("target_artifacts"), field_name="target_artifacts", path=resolved)
        contract_model = str(frontmatter.get("contract_model") or "").strip()
        structure_mode = str(frontmatter.get("structure_mode") or "").strip()
        pre_retrieval_shell = _mapping(frontmatter.get("pre_retrieval_shell"), field_name="pre_retrieval_shell", path=resolved, required=False)
        binding_layers = _string_tuple(frontmatter.get("binding_layers"), field_name="binding_layers", path=resolved)
        try:
            core_chapter_h3_target = int(frontmatter.get("core_chapter_h3_target") or 0)
        except Exception:
            core_chapter_h3_target = 0
        query_defaults = _mapping(frontmatter.get("query_defaults"), field_name="query_defaults", path=resolved, required=False)
        overridable_query_fields = _string_tuple(
            frontmatter.get("overridable_query_fields"),
            field_name="overridable_query_fields",
            path=resolved,
        )
        quality_contract = _mapping(frontmatter.get("quality_contract"), field_name="quality_contract", path=resolved, required=False)
        loop_policy = _mapping(frontmatter.get("loop_policy"), field_name="loop_policy", path=resolved, required=False)
        stages = _parse_stages(frontmatter.get("stages"), path=resolved)
        variant_of = str(raw_frontmatter.get("variant_of") or "").strip()
        variant_overrides = _mapping(raw_frontmatter.get("variant_overrides"), field_name="variant_overrides", path=resolved, required=False)
        if not units_template:
            raise ValueError(f"Missing units_template in pipeline front matter: {resolved}")
        return PipelineSpec(
            path=resolved,
            name=name,
            version=version,
            units_template=units_template,
            default_checkpoints=default_checkpoints,
            profile=profile,
            routing_hints=routing_hints,
            routing_default=routing_default,
            routing_priority=routing_priority,
            docs_hidden=docs_hidden,
            target_artifacts=target_artifacts,
            contract_model=contract_model,
            structure_mode=structure_mode,
            pre_retrieval_shell=pre_retrieval_shell,
            binding_layers=binding_layers,
            core_chapter_h3_target=core_chapter_h3_target,
            query_defaults=query_defaults,
            overridable_query_fields=overridable_query_fields,
            quality_contract=quality_contract,
            loop_policy=loop_policy,
            stages=stages,
            variant_of=variant_of,
            variant_overrides=variant_overrides,
        )

    def query_default(self, key: str, default: Any = None) -> Any:
        return self.query_defaults.get(str(key or "").strip(), default)

    def allows_query_override(self, key: str) -> bool:
        return str(key or "").strip() in set(self.overridable_query_fields)


def _parse_frontmatter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Pipeline file must start with YAML front matter '---'")
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        raise ValueError("Unterminated YAML front matter (missing closing '---')")
    raw = "\n".join(lines[1:end_idx])
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise ValueError("Pipeline YAML front matter must be a mapping")
    return data


def _load_variant_aware_frontmatter(path: Path, seen: set[Path] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved = path.resolve()
    active = set(seen or set())
    if resolved in active:
        chain = " -> ".join(str(p) for p in [*active, resolved])
        raise ValueError(f"Cyclic `variant_of` chain detected: {chain}")
    active.add(resolved)

    text = resolved.read_text(encoding="utf-8")
    raw = _parse_frontmatter(text)
    variant_of = str(raw.get("variant_of") or "").strip()
    if not variant_of:
        return raw, dict(raw)
    _validate_raw_variant_frontmatter(raw, path=resolved)

    base_path = _resolve_pipeline_reference(resolved, variant_of)
    _, base_effective = _load_variant_aware_frontmatter(base_path, seen=active)

    current = {key: raw[key] for key in ("name", "version") if key in raw}
    merged = _deep_merge(base_effective, current)
    merged = _deep_merge(
        merged,
        _mapping(raw.get("variant_overrides"), field_name="variant_overrides", path=resolved, required=False),
    )
    merged["variant_of"] = variant_of
    merged["variant_overrides"] = raw.get("variant_overrides") or {}
    return raw, merged


def _validate_raw_variant_frontmatter(raw: dict[str, Any], *, path: Path) -> None:
    allowed_raw_keys = {"name", "version", "variant_of", "variant_overrides"}
    extra_keys = sorted(str(key) for key in raw.keys() if str(key) not in allowed_raw_keys)
    if extra_keys:
        raise ValueError(
            "Variant pipeline files may only keep top-level keys "
            "`name`, `version`, `variant_of`, `variant_overrides`; "
            f"move the rest under `variant_overrides` in {path}: {', '.join(extra_keys)}"
        )


def _resolve_pipeline_reference(path: Path, ref: str) -> Path:
    value = str(ref or "").strip()
    if not value:
        raise ValueError(f"Empty `variant_of` reference in {path}")

    candidate = Path(value)
    if candidate.is_absolute() and candidate.exists():
        return candidate.resolve()

    repo_root = path.parent.parent
    for base in (path.parent, repo_root, repo_root / "pipelines"):
        direct = (base / value).resolve()
        if direct.exists():
            return direct

    stem = Path(value).name
    if stem.endswith(".pipeline.md"):
        stem = stem[: -len(".pipeline.md")]
    if stem:
        for base in (path.parent, repo_root / "pipelines"):
            direct = (base / f"{stem}.pipeline.md").resolve()
            if direct.exists():
                return direct

    raise ValueError(f"Could not resolve `variant_of: {value}` from {path}")


def resolve_pipeline_variant_path(path: Path, ref: str) -> Path:
    """Resolve one variant parent with the same rules used by `PipelineSpec.load`."""

    return _resolve_pipeline_reference(path.resolve(), ref)


def resolve_pipeline_variant_chain(path: Path) -> tuple[Path, ...]:
    """Return the selected Pipeline followed by every resolved variant parent."""

    chain: list[Path] = []
    seen: set[Path] = set()
    current = path.resolve()
    while True:
        if current in seen:
            rendered = " -> ".join(str(item) for item in [*chain, current])
            raise ValueError(f"Cyclic `variant_of` chain detected: {rendered}")
        seen.add(current)
        chain.append(current)
        raw = _parse_frontmatter(current.read_text(encoding="utf-8"))
        variant_of = str(raw.get("variant_of") or "").strip()
        if not variant_of:
            return tuple(chain)
        current = resolve_pipeline_variant_path(current, variant_of)


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, list) and isinstance(override, dict) and any(str(key).startswith("__") for key in override.keys()):
        return _apply_list_patch(base, override)
    if isinstance(base, dict) and isinstance(override, dict):
        merged: dict[str, Any] = {str(k): v for k, v in base.items()}
        for key, value in override.items():
            if key in merged:
                merged[key] = _deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
    return override


def _apply_list_patch(base: list[Any], override: dict[str, Any]) -> list[Any]:
    allowed_keys = {"__append__", "__prepend__", "__remove__", "__replace__"}
    bad_keys = sorted(str(key) for key in override.keys() if str(key) not in allowed_keys)
    if bad_keys:
        raise ValueError(
            "List patch overrides only support "
            "`__append__`, `__prepend__`, `__remove__`, `__replace__`; "
            f"got: {', '.join(bad_keys)}"
        )

    if "__replace__" in override:
        replacement = override.get("__replace__")
        if not isinstance(replacement, list):
            raise ValueError("List patch `__replace__` must be a YAML list")
        return list(replacement)

    current = list(base)
    remove_values = override.get("__remove__", [])
    prepend_values = override.get("__prepend__", [])
    append_values = override.get("__append__", [])
    for field_name, value in (
        ("__remove__", remove_values),
        ("__prepend__", prepend_values),
        ("__append__", append_values),
    ):
        if not isinstance(value, list):
            raise ValueError(f"List patch `{field_name}` must be a YAML list")

    if remove_values:
        current = [item for item in current if item not in remove_values]
    if prepend_values:
        current = list(prepend_values) + current
    if append_values:
        current = current + list(append_values)
    return current


def _mapping(value: Any, *, field_name: str, path: Path, required: bool) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"`{field_name}` must be a mapping in {path}")
    return {str(key): item for key, item in value.items()}


def _string_tuple(value: Any, *, field_name: str, path: Path) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"`{field_name}` must be a YAML list in {path}")
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return tuple(out)


def _parse_stages(value: Any, *, path: Path) -> dict[str, PipelineStage]:
    if value is None:
        return {}

    items: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        items = [(str(stage_id or "").strip(), data) for stage_id, data in value.items()]
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            if not isinstance(item, dict):
                raise ValueError(f"`stages[{idx}]` must be a mapping in {path}")
            stage_id = str(item.get("id") or item.get("stage") or "").strip()
            if not stage_id:
                raise ValueError(f"`stages[{idx}]` is missing `id` in {path}")
            items.append((stage_id, item))
    else:
        raise ValueError(f"`stages` must be a mapping or list in {path}")

    stages: dict[str, PipelineStage] = {}
    for stage_id, data in items:
        stage = PipelineStage.from_mapping(stage_id, data, path=path)
        if not stage.id:
            raise ValueError(f"`stages` contains an empty stage id in {path}")
        stages[stage.id] = stage
    return stages
