from __future__ import annotations

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
    for rec in sources:
        if not isinstance(rec, dict):
            invalid += 1
            continue
        if not rec.get("source_id") or not rec.get("kind") or not rec.get("locator") or not rec.get("label"):
            invalid += 1
            continue
    if invalid:
        return [QualityIssue(code="source_manifest_missing_fields", message=f"`{out_rel}` has {invalid} invalid source record(s).")]
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    if "example-source" in text or "replace this scaffold" in text:
        return [QualityIssue(code="source_manifest_placeholders", message=f"`{out_rel}` still contains scaffold placeholders.")]
    return []


def check_source_ingest(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    index_rel = outputs[0] if outputs else "sources/index.jsonl"
    prov_rel = outputs[1] if len(outputs) > 1 else "sources/provenance.jsonl"
    index_path = workspace / index_rel
    prov_path = workspace / prov_rel
    if not index_path.exists():
        return [QualityIssue(code="missing_source_index", message=f"`{index_rel}` does not exist.")]
    if not prov_path.exists():
        return [QualityIssue(code="missing_source_provenance", message=f"`{prov_rel}` does not exist.")]
    records = read_jsonl(index_path)
    if not records:
        return [QualityIssue(code="empty_source_index", message=f"`{index_rel}` is empty.")]
    success = 0
    bad = 0
    for rec in records:
        if not isinstance(rec, dict):
            bad += 1
            continue
        if not rec.get("source_id") or not rec.get("kind") or not rec.get("status"):
            bad += 1
            continue
        if str(rec.get("status") or "").strip() == "success":
            success += 1
    if bad:
        return [QualityIssue(code="source_index_missing_fields", message=f"`{index_rel}` has {bad} invalid record(s).")]
    if success == 0:
        return [QualityIssue(code="source_ingest_no_success", message=f"`{index_rel}` contains no successful ingests.")]
    prov_records = read_jsonl(prov_path)
    if not prov_records:
        return [QualityIssue(code="empty_source_provenance", message=f"`{prov_rel}` is empty.")]
    return []


def check_source_tutorial_spec(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/TUTORIAL_SPEC.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_source_tutorial_spec", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore")
    if has_placeholder_markers(text):
        return [QualityIssue(code="source_tutorial_spec_placeholders", message=f"`{out_rel}` contains placeholders.")]
    low = text.lower()
    needed = ["audience", "prerequisites", "learning objectives", "source scope", "running example", "delivery"]
    missing = [item for item in needed if item not in low]
    if missing:
        return [QualityIssue(code="source_tutorial_spec_missing_sections", message=f"`{out_rel}` is missing key sections: {', '.join(missing)}.")]
    return []


def check_module_source_coverage(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    out_rel = outputs[0] if outputs else "outline/source_coverage.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_source_coverage", message=f"`{out_rel}` does not exist.")]
    records = read_jsonl(path)
    if not records:
        return [QualityIssue(code="empty_source_coverage", message=f"`{out_rel}` is empty.")]
    bad = 0
    for rec in records:
        if not rec.get("module_id"):
            bad += 1
            continue
        if "source_ids" not in rec and "gaps" not in rec:
            bad += 1
    if bad:
        return [QualityIssue(code="source_coverage_missing_fields", message=f"`{out_rel}` has {bad} invalid coverage record(s).")]
    return []


def check_tutorial_context_packs(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    out_rel = outputs[0] if outputs else "outline/tutorial_context_packs.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_tutorial_context_packs", message=f"`{out_rel}` does not exist.")]
    records = read_jsonl(path)
    if not records:
        return [QualityIssue(code="empty_tutorial_context_packs", message=f"`{out_rel}` is empty.")]
    bad = 0
    for rec in records:
        if not rec.get("module_id") or not rec.get("objective"):
            bad += 1
    if bad:
        return [QualityIssue(code="tutorial_context_packs_missing_fields", message=f"`{out_rel}` has {bad} invalid context pack(s).")]
    return []


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
    return []
