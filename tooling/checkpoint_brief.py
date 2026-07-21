from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


def write_checkpoint_brief(
    *,
    workspace: Path,
    checkpoint: str,
    inputs: Iterable[str] | None = None,
) -> Path:
    """Project declared Workflow Artifacts into a human review surface."""

    from tooling.common import ensure_decisions_approval_checklist, upsert_checkpoint_block

    workspace = workspace.resolve()
    checkpoint = str(checkpoint or "").strip() or "C2"
    declared_inputs = _normalize_inputs(inputs)
    decisions_path = workspace / "DECISIONS.md"
    ensure_decisions_approval_checklist(decisions_path)

    if checkpoint == "C2" and _pipeline_name(workspace) == "idea-brainstorm":
        block = _idea_focus_block(workspace, declared_inputs)
    elif checkpoint == "C2":
        block = _structure_review_block(workspace, declared_inputs)
    else:
        summaries = [_summarize_artifact(workspace, relpath) for relpath in declared_inputs]
        approval_line = (
            f"- Tick `Approve {checkpoint}` only after every declared input is present and reviewed."
            if declared_inputs
            else "- Approval is unsupported until the Unit's declared inputs are supplied."
        )
        block = "\n".join(
            [
                f"## {checkpoint} checkpoint",
                "",
                "### Reviewed declared inputs",
                _reviewed_inputs(workspace, declared_inputs),
                "",
                "### Artifact signals",
                *(summaries or ["- No declared inputs were supplied; this review cannot support approval."]),
                "",
                "Decision:",
                "- Record constraints in this block.",
                approval_line,
                "",
            ]
        )
    upsert_checkpoint_block(decisions_path, checkpoint, block)
    return decisions_path


def _normalize_inputs(inputs: Iterable[str] | None) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw_value in inputs or []:
        value = str(raw_value or "").strip().lstrip("?").strip()
        candidate = Path(value)
        if not value or candidate.is_absolute() or ".." in candidate.parts:
            continue
        relpath = candidate.as_posix()
        if relpath not in normalized:
            normalized.append(relpath)
    return tuple(normalized)


def _pipeline_name(workspace: Path) -> str:
    lock_path = workspace / "PIPELINE.lock.md"
    if not lock_path.exists():
        return ""
    for raw_line in lock_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not raw_line.startswith("pipeline:"):
            continue
        value = raw_line.split("pipeline:", 1)[1].strip()
        name = Path(value).name
        return name[: -len(".pipeline.md")] if name.endswith(".pipeline.md") else name
    return ""


def _structure_review_block(workspace: Path, declared_inputs: tuple[str, ...]) -> str:
    summaries = [_summarize_artifact(workspace, relpath) for relpath in declared_inputs]
    return "\n".join(
        [
            "## C2 review - scope + structure (NO PROSE)",
            "",
            "### Reviewed declared inputs",
            _reviewed_inputs(workspace, declared_inputs),
            "",
            "### Artifact signals",
            *(summaries or ["- No declared inputs were supplied; this review cannot support approval."]),
            "",
            "Decision:",
            "- Record scope, structure, coverage, or reroute constraints in this block.",
            "- Tick `Approve C2` above only after every declared input is present and reviewed.",
            "",
        ]
    )


def _idea_focus_block(workspace: Path, declared_inputs: tuple[str, ...]) -> str:
    summaries = [_summarize_artifact(workspace, relpath) for relpath in declared_inputs]
    taxonomy_relpath = next(
        (relpath for relpath in declared_inputs if relpath == "outline/taxonomy.yml"),
        "",
    )
    clusters = (
        _list_taxonomy_clusters(workspace / taxonomy_relpath)
        if taxonomy_relpath
        else "- (taxonomy was not declared as an input)"
    )
    return "\n".join(
        [
            "## C2 focus - choose idea-map clusters (NO PROSE)",
            "",
            "### Reviewed declared inputs",
            _reviewed_inputs(workspace, declared_inputs),
            "",
            "### Artifact signals",
            *(summaries or ["- No declared inputs were supplied; this review cannot support approval."]),
            "",
            "### Candidate clusters",
            clusters,
            "",
            "### Recorded selection",
            "- Focus clusters: (required; separate 1-2 cluster names with semicolons)",
            "- Hard exclusions: (optional; separate 2-5 exclusions with semicolons)",
            "",
            "Decision:",
            "- Choose 1-2 focus clusters and 2-5 hard exclusions.",
            "- Tick `Approve C2` above only after every declared input is present and reviewed.",
            "",
        ]
    )


def _reviewed_inputs(workspace: Path, declared_inputs: tuple[str, ...]) -> str:
    if not declared_inputs:
        return "- (none supplied; invoke the helper with the Unit's `--inputs`)"
    lines = []
    for relpath in declared_inputs:
        status = "present" if (workspace / relpath).exists() else "missing"
        lines.append(f"- `{relpath}`: {status}")
    return "\n".join(lines)


def _summarize_artifact(workspace: Path, relpath: str) -> str:
    path = workspace / relpath
    if not path.exists():
        return f"- `{relpath}`: missing"
    if relpath == "outline/taxonomy.yml":
        return _summarize_taxonomy(path, relpath)
    if relpath == "outline/chapter_skeleton.yml":
        return _summarize_chapter_skeleton(path, relpath)
    if relpath == "outline/section_bindings.jsonl":
        return _summarize_jsonl_status(path, relpath, label="section bindings")
    if relpath == "outline/section_briefs.jsonl":
        return _summarize_jsonl_status(path, relpath, label="section briefs")
    if relpath == "outline/outline.yml":
        return _summarize_outline(path, relpath)
    if relpath == "outline/mapping.tsv":
        return _summarize_mapping(workspace, path, relpath)
    if relpath == "outline/outline_state.jsonl":
        return _summarize_outline_state(path, relpath)
    if relpath == "output/REROUTE_STATE.json":
        return _summarize_reroute_state(path, relpath)
    return _summarize_generic_file(path, relpath)


def _summarize_taxonomy(path: Path, relpath: str) -> str:
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except Exception as exc:
        return f"- `{relpath}`: unreadable ({type(exc).__name__}: {exc})"
    top = len(data) if isinstance(data, list) else 0
    leaves = (
        sum(
            len(node.get("children") or [])
            for node in data
            if isinstance(node, dict) and isinstance(node.get("children") or [], list)
        )
        if isinstance(data, list)
        else 0
    )
    return f"- `{relpath}`: top-level={top}, leaf-nodes={leaves}"


def _list_taxonomy_clusters(path: Path) -> str:
    if not path.exists():
        return "- (missing taxonomy)"
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except Exception as exc:
        return f"- (unreadable taxonomy: {type(exc).__name__}: {exc})"
    if not isinstance(data, list) or not data:
        return "- (empty taxonomy)"
    lines = []
    for node in data[:12]:
        if not isinstance(node, dict):
            continue
        name = str(node.get("name") or "").strip() or "(unnamed)"
        children = node.get("children") if isinstance(node.get("children"), list) else []
        lines.append(f"- {name} (children={len(children)})")
    return "\n".join(lines) if lines else "- (no readable clusters)"


def _summarize_chapter_skeleton(path: Path, relpath: str) -> str:
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except Exception as exc:
        return f"- `{relpath}`: unreadable ({type(exc).__name__}: {exc})"
    chapters = data if isinstance(data, list) else []
    target_h3 = sum(
        int(chapter.get("target_h3_count") or 0)
        for chapter in chapters
        if isinstance(chapter, dict)
    )
    return f"- `{relpath}`: chapters={len(chapters)}, target-h3={target_h3}"


def _summarize_outline(path: Path, relpath: str) -> str:
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except Exception as exc:
        return f"- `{relpath}`: unreadable ({type(exc).__name__}: {exc})"
    sections = len(data) if isinstance(data, list) else 0
    subsections = (
        sum(
            len(section.get("subsections") or [])
            for section in data
            if isinstance(section, dict) and isinstance(section.get("subsections") or [], list)
        )
        if isinstance(data, list)
        else 0
    )
    return f"- `{relpath}`: sections={sections}, subsections={subsections}"


def _summarize_mapping(workspace: Path, path: Path, relpath: str) -> str:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
    except Exception as exc:
        return f"- `{relpath}`: unreadable ({type(exc).__name__}: {exc})"
    by_section: Counter[str] = Counter()
    for row in rows:
        section_id = str(row.get("section_id") or "").strip()
        if section_id:
            by_section[section_id] += 1
    from tooling.quality_checks.survey_policy import per_subsection

    target = per_subsection(workspace)
    covered = sum(count >= target for count in by_section.values())
    return (
        f"- `{relpath}`: target-per-subsection={target}, "
        f"subsections-meeting-target={covered}/{len(by_section)}, rows={len(rows)}"
    )


def _summarize_jsonl_status(path: Path, relpath: str, *, label: str) -> str:
    try:
        records = _read_jsonl(path)
    except (OSError, ValueError) as exc:
        return f"- `{relpath}`: unreadable ({type(exc).__name__}: {exc})"
    statuses = Counter(str(record.get("status") or "unknown").upper() for record in records)
    status_text = ", ".join(f"{key}={value}" for key, value in sorted(statuses.items())) or "none"
    return f"- `{relpath}`: {label}={len(records)}, status[{status_text}]"


def _summarize_outline_state(path: Path, relpath: str) -> str:
    try:
        records = _read_jsonl(path)
    except (OSError, ValueError) as exc:
        return f"- `{relpath}`: unreadable ({type(exc).__name__}: {exc})"
    if not records:
        return f"- `{relpath}`: empty"
    latest = records[-1]
    return f"- `{relpath}`: {_state_fields(latest)}, records={len(records)}"


def _summarize_reroute_state(path: Path, relpath: str) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return f"- `{relpath}`: unreadable ({type(exc).__name__}: {exc})"
    if not isinstance(payload, dict):
        return f"- `{relpath}`: expected an object"
    return f"- `{relpath}`: {_state_fields(payload)}"


def _state_fields(payload: dict[str, Any]) -> str:
    fields = []
    for key in (
        "status",
        "structure_phase",
        "h3_status",
        "approval_status",
        "reroute_target",
        "retry_budget_remaining",
    ):
        value = payload.get(key)
        if value not in (None, ""):
            fields.append(f"{key}={value}")
    return ", ".join(fields) or "state fields unavailable"


def _summarize_generic_file(path: Path, relpath: str) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"- `{relpath}`: unreadable ({type(exc).__name__}: {exc})"
    lines = sum(bool(line.strip()) for line in text.splitlines())
    return f"- `{relpath}`: non-empty-lines={lines}, chars={len(text)}"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"line {line_number}: expected an object")
        records.append(payload)
    return records
