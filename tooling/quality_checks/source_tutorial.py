from __future__ import annotations

import re
from pathlib import Path

from tooling.quality_checks.common import QualityIssue, has_placeholder_markers


def check_tutorial_spec(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/TUTORIAL_SPEC.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_tutorial_spec", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore")

    issues: list[QualityIssue] = []
    if has_placeholder_markers(text):
        issues.append(
            QualityIssue(
                code="tutorial_spec_placeholders",
                message="Tutorial spec contains placeholder markers (TODO/TBD/FIXME); fill target audience/prereqs/objectives/running example.",
            )
        )

    low = text.lower()
    required = [
        ("audience", "受众"),
        ("prereq", "先修"),
        ("objective", "学习目标"),
        ("running example", "运行示例"),
    ]
    missing = [en for en, zh in required if (en not in low and zh not in text)]
    if missing:
        issues.append(
            QualityIssue(
                code="tutorial_spec_missing_sections",
                message=f"Tutorial spec is missing key sections: {', '.join(missing)}.",
            )
        )
    return issues


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

    from tooling.common import load_yaml, read_jsonl

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

    records = read_jsonl(index_path)
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
    prov_records = read_jsonl(prov_path)
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

    from tooling.common import load_yaml, read_jsonl

    out_rel = outputs[0] if outputs else "outline/source_coverage.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_source_coverage", message=f"`{out_rel}` does not exist.")]
    records = read_jsonl(path)
    if not records:
        return [QualityIssue(code="empty_source_coverage", message=f"`{out_rel}` is empty.")]
    bad = 0
    record_ids: list[str] = []
    for rec in records:
        if not rec.get("module_id"):
            bad += 1
            continue
        record_ids.append(str(rec.get("module_id")))
        if "source_ids" not in rec and "gaps" not in rec:
            bad += 1
    issues: list[QualityIssue] = []
    if bad:
        issues.append(QualityIssue(code="source_coverage_missing_fields", message=f"`{out_rel}` has {bad} invalid coverage record(s)."))
    duplicate_ids = sorted(module_id for module_id, count in Counter(record_ids).items() if count > 1)
    if duplicate_ids:
        issues.append(QualityIssue(code="source_coverage_duplicate_modules", message=f"`{out_rel}` repeats modules: {', '.join(duplicate_ids)}."))
    plan = load_yaml(workspace / "outline" / "module_plan.yml")
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

    from tooling.common import load_yaml, read_jsonl

    out_rel = outputs[0] if outputs else "outline/tutorial_context_packs.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_tutorial_context_packs", message=f"`{out_rel}` does not exist.")]
    records = read_jsonl(path)
    if not records:
        return [QualityIssue(code="empty_tutorial_context_packs", message=f"`{out_rel}` is empty.")]
    bad = 0
    record_ids: list[str] = []
    for rec in records:
        if not rec.get("module_id") or not rec.get("objective"):
            bad += 1
            continue
        record_ids.append(str(rec.get("module_id")))
    issues: list[QualityIssue] = []
    if bad:
        issues.append(QualityIssue(code="tutorial_context_packs_missing_fields", message=f"`{out_rel}` has {bad} invalid context pack(s)."))
    duplicate_ids = sorted(module_id for module_id, count in Counter(record_ids).items() if count > 1)
    if duplicate_ids:
        issues.append(QualityIssue(code="tutorial_context_packs_duplicate_modules", message=f"`{out_rel}` repeats modules: {', '.join(duplicate_ids)}."))
    plan = load_yaml(workspace / "outline" / "module_plan.yml")
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
    structure_issues = tutorial_structure_issues(workspace / "output" / "TUTORIAL.md")
    if structure_issues:
        return [
            QualityIssue(
                code="tutorial_selfloop_stale_or_invalid",
                message="The PASS report does not match the current tutorial: " + structure_issues[0],
            )
        ]
    return []
