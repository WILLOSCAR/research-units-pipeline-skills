from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tooling.quality_checks.common import QualityIssue, has_placeholder_markers


class _InvalidJsonl(ValueError):
    def __init__(self, path: Path, line_number: int, detail: str) -> None:
        location = f" line {line_number}" if line_number else ""
        super().__init__(f"`{path.as_posix()}`{location} is invalid JSONL: {detail}")


def _read_jsonl_records(path: Path) -> list[Any]:
    if not path.exists():
        return []
    records: list[Any] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise _InvalidJsonl(path, 0, f"{type(exc).__name__}: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise _InvalidJsonl(path, line_number, exc.msg) from exc
    return records


def _resolve_workspace_path(workspace: Path, value: object) -> Path | None:
    raw = str(value or "").strip()
    candidate = Path(raw)
    if not raw or candidate.is_absolute():
        return None
    resolved = (workspace / candidate).resolve()
    if not resolved.is_relative_to(workspace.resolve()) or not resolved.exists():
        return None
    return resolved


def _provenance_path_matches_index(index_path: Path, provenance_path: Path) -> bool:
    if index_path.is_dir():
        return provenance_path == index_path or provenance_path.is_relative_to(index_path)
    return provenance_path == index_path


def _source_grounding(workspace: Path) -> dict[str, dict[str, object]]:
    """Return sources whose index identity and provenance paths form a valid join."""

    indexed: dict[str, Path] = {}
    for record in _read_jsonl_records(workspace / "sources" / "index.jsonl"):
        if not isinstance(record, dict):
            continue
        source_id = str(record.get("source_id") or "").strip()
        index_path = _resolve_workspace_path(workspace, record.get("local_path"))
        if (
            str(record.get("status") or "").strip() == "success"
            and source_id
            and index_path is not None
        ):
            indexed[source_id] = index_path

    pointers: dict[str, dict[str, Path]] = {}
    for record in _read_jsonl_records(workspace / "sources" / "provenance.jsonl"):
        if not isinstance(record, dict):
            continue
        source_id = str(record.get("source_id") or "").strip()
        pointer = str(record.get("pointer") or "").strip()
        origin = str(record.get("origin_url_or_path") or "").strip()
        provenance_path = _resolve_workspace_path(workspace, record.get("local_path"))
        index_path = indexed.get(source_id)
        if (
            source_id
            and pointer
            and origin
            and provenance_path is not None
            and index_path is not None
            and _provenance_path_matches_index(index_path, provenance_path)
        ):
            pointers.setdefault(source_id, {})[pointer] = provenance_path

    return {
        source_id: {"index_path": index_path, "pointers": pointers[source_id]}
        for source_id, index_path in indexed.items()
        if pointers.get(source_id)
    }


def _backed_source_ids(workspace: Path) -> set[str]:
    """Return source IDs joined across successful index and usable provenance."""

    return set(_source_grounding(workspace))


def _snippet_grounding_issue(
    *,
    workspace: Path,
    snippet: dict[str, object],
    grounding: dict[str, dict[str, object]],
    source_text_cache: dict[Path, str] | None = None,
) -> str:
    source_id = str(snippet.get("source_id") or "").strip()
    pointer = str(snippet.get("pointer") or "").strip()
    text = str(snippet.get("snippet") or "").strip()
    source = grounding.get(source_id)
    if source is None:
        return "source"
    pointer_paths = source.get("pointers")
    if not isinstance(pointer_paths, dict) or pointer not in pointer_paths:
        return "pointer"
    provenance_path = pointer_paths[pointer]
    if not isinstance(provenance_path, Path) or not provenance_path.is_file() or not text:
        return "content"
    cache = source_text_cache if source_text_cache is not None else {}
    normalized_source = cache.get(provenance_path)
    if normalized_source is None:
        source_text = provenance_path.read_text(encoding="utf-8", errors="ignore")
        normalized_source = re.sub(r"\s+", " ", source_text).strip().casefold()
        cache[provenance_path] = normalized_source
    normalized_snippet = re.sub(r"\s+", " ", text).strip().casefold()
    return "" if normalized_snippet and normalized_snippet in normalized_source else "content"


def check_source_manifest(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from collections import Counter

    from tooling.common import load_yaml

    out_rel = outputs[0] if outputs else "sources/manifest.yml"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_source_manifest", message=f"`{out_rel}` does not exist.")]
    try:
        data = load_yaml(path)
    except Exception as exc:
        return [QualityIssue(code="invalid_source_manifest_yaml", message=f"`{out_rel}` is not valid YAML ({type(exc).__name__}: {exc}).")]
    sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(sources, list) or not sources:
        return [QualityIssue(code="empty_source_manifest", message=f"`{out_rel}` must contain a non-empty `sources` list.")]
    invalid = 0
    source_ids: list[str] = []
    for rec in sources:
        if not isinstance(rec, dict):
            invalid += 1
            continue
        if not rec.get("source_id") or not rec.get("kind") or not rec.get("locator") or not rec.get("label"):
            invalid += 1
            continue
        source_ids.append(str(rec.get("source_id")).strip())
    if invalid:
        return [QualityIssue(code="source_manifest_missing_fields", message=f"`{out_rel}` has {invalid} invalid source record(s).")]
    duplicate_ids = sorted(source_id for source_id, count in Counter(source_ids).items() if count > 1)
    if duplicate_ids:
        return [QualityIssue(code="source_manifest_duplicate_ids", message=f"`{out_rel}` repeats source IDs: {', '.join(duplicate_ids)}.")]
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    if "example-source" in text or "replace this scaffold" in text:
        return [QualityIssue(code="source_manifest_placeholders", message=f"`{out_rel}` still contains scaffold placeholders.")]
    return []


def check_source_ingest(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from collections import Counter

    from tooling.common import load_yaml

    index_rel = outputs[0] if outputs else "sources/index.jsonl"
    prov_rel = outputs[1] if len(outputs) > 1 else "sources/provenance.jsonl"
    index_path = workspace / index_rel
    prov_path = workspace / prov_rel
    if not index_path.exists():
        return [QualityIssue(code="missing_source_index", message=f"`{index_rel}` does not exist.")]
    if not prov_path.exists():
        return [QualityIssue(code="missing_source_provenance", message=f"`{prov_rel}` does not exist.")]
    manifest_path = workspace / "sources" / "manifest.yml"
    try:
        manifest = load_yaml(manifest_path)
    except Exception as exc:
        return [QualityIssue(code="invalid_source_manifest_yaml", message=f"`sources/manifest.yml` could not be loaded ({type(exc).__name__}: {exc}).")]
    manifest_rows = manifest.get("sources") if isinstance(manifest, dict) else None
    if not isinstance(manifest_rows, list) or not manifest_rows:
        return [QualityIssue(code="empty_source_manifest", message="`sources/manifest.yml` has no source records.")]
    manifest_by_id = {
        str(rec.get("source_id") or "").strip(): rec
        for rec in manifest_rows
        if isinstance(rec, dict) and str(rec.get("source_id") or "").strip()
    }

    try:
        records = _read_jsonl_records(index_path)
    except _InvalidJsonl as exc:
        return [QualityIssue(code="source_index_invalid_jsonl", message=str(exc))]
    if not records:
        return [QualityIssue(code="empty_source_index", message=f"`{index_rel}` is empty.")]
    issues: list[QualityIssue] = []
    success = 0
    bad = 0
    index_ids: list[str] = []
    index_by_id: dict[str, dict[str, object]] = {}
    invalid_local_paths: list[str] = []
    for rec in records:
        if not isinstance(rec, dict):
            bad += 1
            continue
        source_id = str(rec.get("source_id") or "").strip()
        if not source_id or not rec.get("kind") or not rec.get("status"):
            bad += 1
            continue
        index_ids.append(source_id)
        index_by_id[source_id] = rec
        if str(rec.get("status") or "").strip() == "success":
            success += 1
            local_value = str(rec.get("local_path") or "").strip()
            candidate = Path(local_value)
            local_path = (workspace / candidate).resolve() if local_value and not candidate.is_absolute() else candidate
            if (
                not local_value
                or candidate.is_absolute()
                or not local_path.is_relative_to(workspace.resolve())
                or not local_path.exists()
            ):
                invalid_local_paths.append(source_id)
    if bad:
        issues.append(QualityIssue(code="source_index_missing_fields", message=f"`{index_rel}` has {bad} invalid record(s)."))
    duplicate_index_ids = sorted(source_id for source_id, count in Counter(index_ids).items() if count > 1)
    if duplicate_index_ids:
        issues.append(QualityIssue(code="source_index_duplicate_ids", message=f"`{index_rel}` repeats source IDs: {', '.join(duplicate_index_ids)}."))
    manifest_ids = set(manifest_by_id)
    indexed_ids = set(index_ids)
    if manifest_ids != indexed_ids:
        issues.append(
            QualityIssue(
                code="source_index_manifest_mismatch",
                message=(
                    "Source index IDs must exactly match the manifest; "
                    f"missing={sorted(manifest_ids - indexed_ids)}, unexpected={sorted(indexed_ids - manifest_ids)}."
                ),
            )
        )
    if invalid_local_paths:
        issues.append(
            QualityIssue(
                code="source_index_local_path_invalid",
                message="Successful sources have missing or unsafe local paths: " + ", ".join(sorted(invalid_local_paths)) + ".",
            )
        )
    if success == 0:
        issues.append(QualityIssue(code="source_ingest_no_success", message=f"`{index_rel}` contains no successful ingests."))
    failed_required_ids = sorted(
        source_id
        for source_id, source in manifest_by_id.items()
        if source.get("required") is True
        and str(index_by_id.get(source_id, {}).get("status") or "").strip() != "success"
    )
    if failed_required_ids:
        issues.append(
            QualityIssue(
                code="required_source_ingest_failed",
                message=(
                    "Required sources did not ingest successfully: "
                    + ", ".join(sorted(failed_required_ids))
                    + "."
                ),
            )
        )
    try:
        prov_records = _read_jsonl_records(prov_path)
    except _InvalidJsonl as exc:
        issues.append(QualityIssue(code="source_provenance_invalid_jsonl", message=str(exc)))
        return issues
    if not prov_records:
        issues.append(QualityIssue(code="empty_source_provenance", message=f"`{prov_rel}` is empty."))
        return issues
    provenance_ids = {
        str(rec.get("source_id") or "").strip()
        for rec in prov_records
        if isinstance(rec, dict) and str(rec.get("source_id") or "").strip()
    }
    successful_ids = {
        source_id
        for source_id, rec in index_by_id.items()
        if str(rec.get("status") or "").strip() == "success"
    }
    missing_provenance = sorted(successful_ids - provenance_ids)
    unexpected_provenance = sorted(provenance_ids - indexed_ids)
    if missing_provenance or unexpected_provenance:
        issues.append(
            QualityIssue(
                code="source_provenance_index_mismatch",
                message=(
                    "Provenance must cover every successful indexed source and no unknown source; "
                    f"missing={missing_provenance}, unexpected={unexpected_provenance}."
                ),
            )
        )
    invalid_provenance: list[str] = []
    mismatched_provenance_paths: list[str] = []
    for rec in prov_records:
        if not isinstance(rec, dict):
            invalid_provenance.append("<invalid-record>")
            continue
        source_id = str(rec.get("source_id") or "").strip()
        if source_id not in successful_ids:
            continue
        pointer = str(rec.get("pointer") or "").strip()
        origin = str(rec.get("origin_url_or_path") or "").strip()
        local_value = str(rec.get("local_path") or "").strip()
        candidate = Path(local_value)
        local_path = (workspace / candidate).resolve() if local_value and not candidate.is_absolute() else candidate
        if (
            not pointer
            or not origin
            or not local_value
            or candidate.is_absolute()
            or not local_path.is_relative_to(workspace.resolve())
            or not local_path.exists()
        ):
            invalid_provenance.append(source_id or "<missing-source-id>")
            continue
        index_local_path = _resolve_workspace_path(
            workspace,
            index_by_id.get(source_id, {}).get("local_path"),
        )
        if index_local_path is not None and not _provenance_path_matches_index(index_local_path, local_path):
            mismatched_provenance_paths.append(source_id)
    if invalid_provenance:
        issues.append(
            QualityIssue(
                code="source_provenance_missing_fields",
                message=(
                    "Successful source provenance requires pointer, origin_url_or_path, and a safe existing "
                    "local_path: " + ", ".join(sorted(set(invalid_provenance))) + "."
                ),
            )
        )
    if mismatched_provenance_paths:
        issues.append(
            QualityIssue(
                code="source_provenance_path_mismatch",
                message=(
                    "Provenance local paths must equal the indexed file or remain inside the indexed source directory: "
                    + ", ".join(sorted(set(mismatched_provenance_paths)))
                    + "."
                ),
            )
        )
    return issues


def check_source_tutorial_spec(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/TUTORIAL_SPEC.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_source_tutorial_spec", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore")
    if has_placeholder_markers(text):
        return [QualityIssue(code="source_tutorial_spec_placeholders", message=f"`{out_rel}` contains placeholders.")]
    required_headings = [
        "## Audience",
        "## Prerequisites",
        "## Learning objectives",
        "## Non-goals",
        "## Source scope",
        "## Running example policy",
        "## Delivery shape",
        "## Structured data",
    ]
    missing = [heading for heading in required_headings if heading not in text]
    if missing:
        return [QualityIssue(code="source_tutorial_spec_missing_sections", message=f"`{out_rel}` is missing key sections: {', '.join(missing)}.")]
    try:
        from tooling.tutorial_workflows import load_source_tutorial_spec_data

        data = load_source_tutorial_spec_data(path)
    except Exception as exc:
        return [QualityIssue(code="source_tutorial_spec_invalid_data", message=f"`{out_rel}` has no readable structured contract ({type(exc).__name__}: {exc}).")]
    required_values = ("audience", "prerequisites", "learning_objectives", "non_goals", "source_scope", "delivery_shape")
    empty_values = [key for key in required_values if not data.get(key)]
    if empty_values:
        return [QualityIssue(code="source_tutorial_spec_empty_fields", message=f"`{out_rel}` has empty structured fields: {', '.join(empty_values)}.")]
    return []


def check_module_source_coverage(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from collections import Counter

    from tooling.common import load_yaml

    out_rel = outputs[0] if outputs else "outline/source_coverage.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_source_coverage", message=f"`{out_rel}` does not exist.")]
    try:
        records = _read_jsonl_records(path)
    except _InvalidJsonl as exc:
        return [QualityIssue(code="source_coverage_invalid_jsonl", message=str(exc))]
    if not records:
        return [QualityIssue(code="empty_source_coverage", message=f"`{out_rel}` is empty.")]
    try:
        grounding = _source_grounding(workspace)
    except _InvalidJsonl as exc:
        return [QualityIssue(code="source_coverage_grounding_invalid_jsonl", message=str(exc))]
    backed_source_ids = set(grounding)

    bad = 0
    unknown_sources: set[str] = set()
    record_ids: list[str] = []
    for rec in records:
        if not isinstance(rec, dict) or not rec.get("module_id"):
            bad += 1
            continue
        record_ids.append(str(rec.get("module_id")))
        source_ids = rec.get("source_ids")
        gaps = rec.get("gaps")
        if not isinstance(source_ids, list) or not isinstance(gaps, list):
            bad += 1
            continue
        normalized_sources = [str(item or "").strip() for item in source_ids if str(item or "").strip()]
        normalized_gaps = [str(item or "").strip() for item in gaps if str(item or "").strip()]
        if not normalized_sources and not normalized_gaps:
            bad += 1
        unknown_sources.update(source_id for source_id in normalized_sources if source_id not in backed_source_ids)
    issues: list[QualityIssue] = []
    if bad:
        issues.append(QualityIssue(code="source_coverage_missing_fields", message=f"`{out_rel}` has {bad} invalid coverage record(s)."))
    duplicate_ids = sorted(module_id for module_id, count in Counter(record_ids).items() if count > 1)
    if duplicate_ids:
        issues.append(QualityIssue(code="source_coverage_duplicate_modules", message=f"`{out_rel}` repeats modules: {', '.join(duplicate_ids)}."))
    if unknown_sources:
        issues.append(
            QualityIssue(
                code="source_coverage_unresolved_sources",
                message=(
                    "Coverage references sources without a successful index/provenance join: "
                    + ", ".join(sorted(unknown_sources))
                    + "."
                ),
            )
        )
    plan_path = workspace / "outline" / "module_plan.yml"
    if not plan_path.exists() or plan_path.stat().st_size == 0:
        issues.append(
            QualityIssue(
                code="source_coverage_plan_missing",
                message="Missing or empty `outline/module_plan.yml` for source coverage checks.",
            )
        )
        return issues
    try:
        plan = load_yaml(plan_path)
    except Exception as exc:
        issues.append(
            QualityIssue(
                code="source_coverage_plan_invalid",
                message=f"Invalid `outline/module_plan.yml`: {type(exc).__name__}: {exc}.",
            )
        )
        return issues
    plan_ids = {
        str(module.get("id") or module.get("module_id") or "").strip()
        for module in (plan.get("modules") or [])
        if isinstance(module, dict) and str(module.get("id") or module.get("module_id") or "").strip()
    } if isinstance(plan, dict) else set()
    coverage_ids = set(record_ids)
    if not plan_ids or coverage_ids != plan_ids:
        issues.append(
            QualityIssue(
                code="source_coverage_module_mismatch",
                message=f"Coverage modules must equal the module plan; missing={sorted(plan_ids - coverage_ids)}, unexpected={sorted(coverage_ids - plan_ids)}.",
            )
        )
    return issues


def check_tutorial_context_packs(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from collections import Counter

    from tooling.common import load_yaml

    out_rel = outputs[0] if outputs else "outline/tutorial_context_packs.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_tutorial_context_packs", message=f"`{out_rel}` does not exist.")]
    try:
        records = _read_jsonl_records(path)
    except _InvalidJsonl as exc:
        return [QualityIssue(code="tutorial_context_packs_invalid_jsonl", message=str(exc))]
    if not records:
        return [QualityIssue(code="empty_tutorial_context_packs", message=f"`{out_rel}` is empty.")]
    try:
        coverage_records = _read_jsonl_records(workspace / "outline" / "source_coverage.jsonl")
    except _InvalidJsonl as exc:
        return [QualityIssue(code="tutorial_context_packs_coverage_invalid_jsonl", message=str(exc))]
    coverage_by_id = {
        str(record.get("module_id") or "").strip(): record
        for record in coverage_records
        if isinstance(record, dict) and str(record.get("module_id") or "").strip()
    }
    try:
        grounding = _source_grounding(workspace)
    except _InvalidJsonl as exc:
        return [QualityIssue(code="tutorial_context_packs_grounding_invalid_jsonl", message=str(exc))]
    backed_source_ids = set(grounding)
    bad = 0
    ungrounded = 0
    coverage_mismatches: list[str] = []
    unresolved_sources: set[str] = set()
    missing_snippet_sources: list[str] = []
    unexpected_snippet_sources: list[str] = []
    pointer_mismatches: list[str] = []
    content_mismatches: list[str] = []
    source_text_cache: dict[Path, str] = {}
    record_ids: list[str] = []
    for rec in records:
        if not isinstance(rec, dict) or not rec.get("module_id") or not rec.get("objective"):
            bad += 1
            continue
        module_id = str(rec.get("module_id")).strip()
        record_ids.append(module_id)
        raw_source_ids = rec.get("source_ids")
        snippets = rec.get("source_snippets")
        if not isinstance(raw_source_ids, list) or not isinstance(snippets, list):
            bad += 1
            continue
        source_ids = {
            str(item or "").strip()
            for item in raw_source_ids
            if str(item or "").strip()
        }
        coverage_values = (coverage_by_id.get(module_id) or {}).get("source_ids")
        coverage_source_ids = {
            str(item or "").strip()
            for item in coverage_values
            if str(item or "").strip()
        } if isinstance(coverage_values, list) else set()
        if source_ids != coverage_source_ids:
            coverage_mismatches.append(module_id)
        unresolved_sources.update(source_ids - backed_source_ids)
        valid_snippets: list[dict[str, object]] = []
        for snippet in snippets:
            if not isinstance(snippet, dict):
                continue
            snippet_source_id = str(snippet.get("source_id") or "").strip()
            if snippet_source_id not in source_ids:
                if snippet_source_id:
                    unexpected_snippet_sources.append(f"{module_id}:{snippet_source_id}")
                continue
            if snippet_source_id not in backed_source_ids:
                continue
            grounding_issue = _snippet_grounding_issue(
                workspace=workspace,
                snippet=snippet,
                grounding=grounding,
                source_text_cache=source_text_cache,
            )
            if grounding_issue == "pointer":
                pointer_mismatches.append(f"{module_id}:{snippet_source_id}")
            elif grounding_issue == "content":
                content_mismatches.append(f"{module_id}:{snippet_source_id}")
            else:
                valid_snippets.append(snippet)
        snippet_source_ids = {
            str(snippet.get("source_id") or "").strip()
            for snippet in valid_snippets
        }
        if source_ids - snippet_source_ids:
            missing_snippet_sources.append(module_id)
        if not source_ids or source_ids != snippet_source_ids:
            ungrounded += 1
    issues = check_module_source_coverage(workspace, ["outline/source_coverage.jsonl"])
    if bad:
        issues.append(QualityIssue(code="tutorial_context_packs_missing_fields", message=f"`{out_rel}` has {bad} invalid context pack(s)."))
    if ungrounded:
        issues.append(
            QualityIssue(
                code="tutorial_context_packs_ungrounded",
                message=f"`{out_rel}` has {ungrounded} pack(s) without source-backed snippets and pointers.",
            )
        )
    if coverage_mismatches:
        issues.append(
            QualityIssue(
                code="tutorial_context_packs_coverage_mismatch",
                message=(
                    "Context-pack source IDs must exactly match approved module coverage: "
                    + ", ".join(sorted(set(coverage_mismatches)))
                    + "."
                ),
            )
        )
    if unresolved_sources:
        issues.append(
            QualityIssue(
                code="tutorial_context_packs_unresolved_sources",
                message=(
                    "Context packs reference sources without a successful index/provenance join: "
                    + ", ".join(sorted(unresolved_sources))
                    + "."
                ),
            )
        )
    if missing_snippet_sources:
        issues.append(
            QualityIssue(
                code="tutorial_context_packs_incomplete_snippets",
                message=(
                    "Every approved module source needs a non-empty snippet and pointer: "
                    + ", ".join(sorted(set(missing_snippet_sources)))
                    + "."
                ),
            )
        )
    if unexpected_snippet_sources:
        issues.append(
            QualityIssue(
                code="tutorial_context_packs_unapproved_snippets",
                message=(
                    "Context packs contain snippets from sources outside approved module coverage: "
                    + ", ".join(sorted(set(unexpected_snippet_sources)))
                    + "."
                ),
            )
        )
    if pointer_mismatches:
        issues.append(
            QualityIssue(
                code="tutorial_context_packs_pointer_mismatch",
                message=(
                    "Context-pack pointers must match provenance pointers for their source: "
                    + ", ".join(sorted(set(pointer_mismatches)))
                    + "."
                ),
            )
        )
    if content_mismatches:
        issues.append(
            QualityIssue(
                code="tutorial_context_packs_snippet_content_mismatch",
                message=(
                    "Context-pack snippets must occur in the provenance file selected by their pointer: "
                    + ", ".join(sorted(set(content_mismatches)))
                    + "."
                ),
            )
        )
    duplicate_ids = sorted(module_id for module_id, count in Counter(record_ids).items() if count > 1)
    if duplicate_ids:
        issues.append(QualityIssue(code="tutorial_context_packs_duplicate_modules", message=f"`{out_rel}` repeats modules: {', '.join(duplicate_ids)}."))
    plan_path = workspace / "outline" / "module_plan.yml"
    if not plan_path.exists() or plan_path.stat().st_size == 0:
        issues.append(
            QualityIssue(
                code="tutorial_context_packs_plan_missing",
                message="Missing or empty `outline/module_plan.yml` for context-pack checks.",
            )
        )
        return issues
    try:
        plan = load_yaml(plan_path)
    except Exception as exc:
        issues.append(
            QualityIssue(
                code="tutorial_context_packs_plan_invalid",
                message=f"Invalid `outline/module_plan.yml`: {type(exc).__name__}: {exc}.",
            )
        )
        return issues
    plan_ids = {
        str(module.get("id") or module.get("module_id") or "").strip()
        for module in (plan.get("modules") or [])
        if isinstance(module, dict) and str(module.get("id") or module.get("module_id") or "").strip()
    } if isinstance(plan, dict) else set()
    pack_ids = set(record_ids)
    if not plan_ids or pack_ids != plan_ids:
        issues.append(
            QualityIssue(
                code="tutorial_context_packs_module_mismatch",
                message=f"Context-pack modules must equal the module plan; missing={sorted(plan_ids - pack_ids)}, unexpected={sorted(pack_ids - plan_ids)}.",
            )
        )
    return issues


TUTORIAL_PREFACE_GROUPS = (
    ("who this is for", "受众"),
    ("prerequisites", "先修"),
    ("what you will learn", "学习目标"),
)
TUTORIAL_MODULE_REQUIREMENTS = (
    ("why it matters", "为什么重要"),
    ("key idea", "核心概念"),
    ("worked example", "示例"),
    ("check yourself", "练习"),
    ("source notes", "来源"),
)


def tutorial_structure_issues(path: Path) -> list[str]:
    if not path.exists() or path.stat().st_size == 0:
        return ["Missing `output/TUTORIAL.md`."]
    text = path.read_text(encoding="utf-8", errors="ignore")
    low = text.lower()
    issues = [
        f"Tutorial is missing the reader-orientation section for `{en}`."
        for en, zh in TUTORIAL_PREFACE_GROUPS
        if en not in low and zh not in text
    ]
    sections: list[tuple[str, str]] = []
    matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", text))
    for index, match in enumerate(matches):
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[body_start:body_end].strip()))
    orientation = {"who this is for", "prerequisites", "what you will learn", "how to use this tutorial", "further reading"}
    modules = [(title, body) for title, body in sections if title.casefold() not in orientation]
    if not modules:
        issues.append("Tutorial has no real modules (`## ...`) beyond orientation sections.")
    for title, body in modules:
        block = body.casefold()
        missing = [label for label, zh in TUTORIAL_MODULE_REQUIREMENTS if label not in block and zh not in body]
        if missing:
            issues.append(f"Module `{title}` is missing teaching sections: {', '.join(missing)}.")
    return issues


def tutorial_contract_issues(workspace: Path) -> list[str]:
    """Validate the current tutorial against its approved plan and context packs."""

    from tooling.common import load_yaml

    tutorial_path = workspace / "output" / "TUTORIAL.md"
    issues = tutorial_structure_issues(tutorial_path)
    if not tutorial_path.exists() or tutorial_path.stat().st_size == 0:
        return issues

    context_issues = check_tutorial_context_packs(
        workspace,
        ["outline/tutorial_context_packs.jsonl"],
    )
    issues.extend(
        f"Context-pack contract `{issue.code}` failed: {issue.message}"
        for issue in context_issues
    )

    plan_path = workspace / "outline" / "module_plan.yml"
    if not plan_path.exists() or plan_path.stat().st_size == 0:
        issues.append("Missing or empty `outline/module_plan.yml` for tutorial fidelity checks.")
        return issues
    try:
        plan = load_yaml(plan_path)
    except Exception as exc:
        issues.append(f"Invalid `outline/module_plan.yml`: {type(exc).__name__}: {exc}.")
        return issues
    modules = [
        module
        for module in (plan.get("modules") or [])
        if isinstance(module, dict)
    ] if isinstance(plan, dict) else []
    if not modules:
        issues.append("Missing or empty `outline/module_plan.yml` for tutorial fidelity checks.")
        return issues

    text = tutorial_path.read_text(encoding="utf-8", errors="ignore")
    sections: list[tuple[str, str]] = []
    matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", text))
    for index, match in enumerate(matches):
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[body_start:body_end].strip()))
    orientation = {"who this is for", "prerequisites", "what you will learn", "how to use this tutorial", "further reading"}
    tutorial_modules = [(title, body) for title, body in sections if title.casefold() not in orientation]
    expected_titles = [
        f"Module {index}: {str(module.get('title') or module.get('id') or '').strip()}"
        for index, module in enumerate(modules, start=1)
    ]
    actual_titles = [title for title, _ in tutorial_modules]
    if actual_titles != expected_titles:
        issues.append(
            "Tutorial module order/titles do not match `outline/module_plan.yml`: "
            f"expected={expected_titles}, actual={actual_titles}."
        )
        return issues

    try:
        packs = _read_jsonl_records(workspace / "outline" / "tutorial_context_packs.jsonl")
    except _InvalidJsonl as exc:
        issues.append(f"Context-pack contract `tutorial_context_packs_invalid_jsonl` failed: {exc}")
        return issues
    packs_by_id = {
        str(pack.get("module_id") or "").strip(): pack
        for pack in packs
        if isinstance(pack, dict) and str(pack.get("module_id") or "").strip()
    }
    for module, (_, body) in zip(modules, tutorial_modules):
        module_id = str(module.get("id") or module.get("module_id") or "").strip()
        pack = packs_by_id.get(module_id, {})
        source_ids = [
            str(item or "").strip()
            for item in pack.get("source_ids") or []
            if str(item or "").strip()
        ]
        source_notes_match = re.search(
            r"(?ims)^###\s+Source notes\s*$\n(?P<body>.*?)(?=^###\s+|\Z)",
            body,
        )
        source_notes = source_notes_match.group("body") if source_notes_match else ""
        snippets = pack.get("source_snippets") if isinstance(pack, dict) else []
        pointers_by_source: dict[str, set[str]] = {}
        for snippet in snippets if isinstance(snippets, list) else []:
            if not isinstance(snippet, dict):
                continue
            source_id = str(snippet.get("source_id") or "").strip()
            pointer = str(snippet.get("pointer") or "").strip()
            if source_id and pointer:
                pointers_by_source.setdefault(source_id, set()).add(pointer)
        missing_sources = [source_id for source_id in source_ids if f"`{source_id}`" not in source_notes]
        missing_pointers = [
            pointer
            for source_id in source_ids
            for pointer in sorted(pointers_by_source.get(source_id, set()))
            if pointer not in source_notes
        ]
        if not source_ids or missing_sources or missing_pointers:
            issues.append(
                f"Module `{module_id}` Source notes do not preserve every approved source and pointer; "
                f"missing_sources={missing_sources}, missing_pointers={missing_pointers}."
            )
    return issues


def check_tutorial_selfloop_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/TUTORIAL_SELFLOOP_TODO.md"
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code="missing_tutorial_selfloop_report", message=f"`{out_rel}` is missing or empty.")]
    text = path.read_text(encoding="utf-8", errors="ignore")
    if has_placeholder_markers(text) or "…" in text:
        return [QualityIssue(code="tutorial_selfloop_placeholders", message=f"`{out_rel}` contains placeholders/ellipsis.")]
    if "- Status: PASS" not in text:
        return [QualityIssue(code="tutorial_selfloop_not_pass", message=f"`{out_rel}` is not PASS.")]
    structure_issues = tutorial_contract_issues(workspace)
    if structure_issues:
        return [
            QualityIssue(
                code="tutorial_selfloop_stale_or_invalid",
                message="The PASS report does not match the current tutorial: " + structure_issues[0],
            )
        ]
    return []
