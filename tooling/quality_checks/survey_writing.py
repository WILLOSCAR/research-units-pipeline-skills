from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from tooling.quality_checks.common import QualityIssue, has_placeholder_markers
from tooling.quality_checks.survey_policy import (
    core_size,
    draft_profile as resolve_draft_profile,
    global_citation_min_subsections,
    pipeline_profile_name,
    quality_contract_int,
)
from tooling.quality_checks.survey_text import (
    extract_section_body,
    repeated_sentences,
    repeated_template_text,
    split_h3_blocks,
)
from tooling.quality_checks.template_residue import (
    check_subsection_template_residue,
    check_template_residue_documents,
)


def section_files_newer_than(workspace: Path, reference: Path) -> list[str]:
    """Return section Markdown files changed after a certification report."""

    if not reference.exists():
        return []
    reference_mtime = reference.stat().st_mtime_ns
    return [
        str(path.relative_to(workspace))
        for path in sorted((workspace / "sections").rglob("*.md"))
        if path.is_file() and path.stat().st_mtime_ns > reference_mtime
    ]


def section_tree_sha256(workspace: Path) -> str:
    """Fingerprint the reader-facing section tree for a certification marker."""

    digest = hashlib.sha256()
    for path in sorted((workspace / "sections").rglob("*.md")):
        if not path.is_file():
            continue
        digest.update(str(path.relative_to(workspace)).encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def check_writer_selfloop(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/WRITER_SELFLOOP_TODO.md"
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code="missing_writer_selfloop_report", message=f"`{out_rel}` is missing or empty.")]

    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_writer_selfloop_report", message=f"`{out_rel}` is empty.")]

    # This file is explicitly a TODO plan, so do NOT treat the word "TODO" as placeholder leakage.
    # We still reject obvious scaffold markers / ellipsis since this is a report-class artifact.
    if "<!--" in text and "scaffold" in text.lower():
        return [
            QualityIssue(
                code="writer_selfloop_scaffold_markers",
                message=f"`{out_rel}` contains scaffold markers; regenerate the self-loop report.",
            )
        ]
    if "…" in text:
        return [
            QualityIssue(
                code="writer_selfloop_contains_ellipsis",
                message=f"`{out_rel}` contains unicode ellipsis (`…`); regenerate the report without truncation markers.",
            )
        ]

    if re.search(r"(?im)^-\s*Status:\s*PASS\b", text):
        return []

    return [
        QualityIssue(
            code="writer_selfloop_not_pass",
            message=f"`{out_rel}` is not PASS; fix the listed failing `sections/*.md` files and rerun `writer-selfloop`.",
        )
    ]


def check_front_matter_writer(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    """Reject provisional front-matter bootstrap prose before U095 can commit.

    The final whole-draft auditor remains authoritative. This earlier check
    gives the CODEX-owned writer Unit the same repair boundary as H3 drafting,
    so deterministic front matter is rewritten and provenance-committed before
    downstream merge Units consume it.
    """

    report_rel = next(
        (item for item in outputs if item.endswith("FRONT_MATTER_REPORT.md")),
        "output/FRONT_MATTER_REPORT.md",
    )
    report_path = workspace / report_rel
    issues: list[QualityIssue] = []
    if not report_path.is_file() or report_path.stat().st_size <= 0:
        issues.append(
            QualityIssue(
                code="missing_front_matter_report",
                message=f"`{report_rel}` is missing or empty.",
            )
        )
    elif not re.search(
        r"(?im)^\s*(?:[-*]\s*)?(?:status\s*:\s*)?PASS\s*$",
        report_path.read_text(encoding="utf-8", errors="ignore"),
    ):
        issues.append(
            QualityIssue(
                code="front_matter_report_not_pass",
                message=f"`{report_rel}` is not PASS.",
            )
        )

    prose_relpaths = [
        item
        for item in outputs
        if item.startswith("sections/") and item.endswith(".md")
    ] or [
        "sections/abstract.md",
        "sections/S1.md",
        "sections/S2.md",
        "sections/discussion.md",
        "sections/conclusion.md",
    ]
    missing = [relpath for relpath in prose_relpaths if not (workspace / relpath).is_file()]
    if missing:
        issues.append(
            QualityIssue(
                code="front_matter_files_missing",
                message="Missing front-matter prose: " + ", ".join(missing),
            )
        )
    documents = [
        (relpath, (workspace / relpath).read_text(encoding="utf-8", errors="ignore"))
        for relpath in prose_relpaths
        if (workspace / relpath).is_file()
    ]
    issues.extend(
        check_template_residue_documents(workspace=workspace, documents=documents)
    )
    return issues


def check_eval_anchor_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/EVAL_ANCHOR_REPORT.md"
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code="missing_eval_anchor_report", message=f"`{out_rel}` is missing or empty.")]

    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_eval_anchor_report", message=f"`{out_rel}` is empty.")]

    checked_match = re.search(r"(?im)^-\s*Files checked:\s*(\d+)\b", text)
    if not checked_match:
        return [
            QualityIssue(
                code="eval_anchor_report_missing_counts",
                message=f"`{out_rel}` is missing the `Files checked` summary; rerun `evaluation-anchor-checker`.",
            )
        ]

    if int(checked_match.group(1)) <= 0:
        return [
            QualityIssue(
                code="eval_anchor_report_zero_files",
                message=f"`{out_rel}` reports zero checked files; ensure subsection files exist, then rerun `evaluation-anchor-checker`.",
            )
        ]

    return []


def _expected_h3_ids(workspace: Path) -> list[str]:
    from tooling.common import load_yaml

    outline_path = workspace / "outline" / "outline.yml"
    outline = load_yaml(outline_path) if outline_path.exists() else []
    expected: list[str] = []
    if not isinstance(outline, list):
        return expected
    for section in outline:
        if not isinstance(section, dict):
            continue
        for subsection in section.get("subsections") or []:
            if not isinstance(subsection, dict):
                continue
            sub_id = str(subsection.get("id") or "").strip()
            if sub_id:
                expected.append(sub_id)
    return expected


def _section_path_for_id(sub_id: str) -> str:
    safe = "".join(char if char.isalnum() else "_" for char in str(sub_id or "")).strip("_")
    return f"sections/S{safe}.md"


def check_paragraph_curator(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    report_rel = next((item for item in outputs if item.endswith("PARAGRAPH_CURATION_REPORT.md")), "output/PARAGRAPH_CURATION_REPORT.md")
    marker_rel = next((item for item in outputs if item.endswith(".refined.ok")), "sections/paragraphs_curated.refined.ok")
    report_path = workspace / report_rel
    marker_path = workspace / marker_rel
    if not report_path.exists():
        return [QualityIssue(code="missing_paragraph_curation_report", message=f"`{report_rel}` does not exist.")]

    issues: list[QualityIssue] = []
    report = report_path.read_text(encoding="utf-8", errors="ignore")
    if not re.search(r"(?im)^-\s*Status:\s*PASS\s*$", report):
        issues.append(QualityIssue(code="paragraph_curation_not_pass", message=f"`{report_rel}` does not report PASS."))
    if not marker_path.exists():
        issues.append(QualityIssue(code="paragraph_curation_marker_missing", message=f"`{marker_rel}` does not exist."))

    profile = resolve_draft_profile(workspace)
    minimum, maximum = {
        "course_paper": (5, 7),
        "survey": (10, 12),
        "deep": (11, 13),
    }.get(profile, (1, 14))
    off_budget: list[str] = []
    for sub_id in _expected_h3_ids(workspace):
        relpath = _section_path_for_id(sub_id)
        path = workspace / relpath
        if not path.exists():
            off_budget.append(f"{sub_id}=missing")
            continue
        count = len([part for part in re.split(r"\n\s*\n", path.read_text(encoding="utf-8", errors="ignore").strip()) if part.strip()])
        if count < minimum or count > maximum:
            off_budget.append(f"{sub_id}={count}")
    if off_budget:
        issues.append(
            QualityIssue(
                code="paragraph_curation_outside_profile_budget",
                message=f"H3 paragraph counts fall outside the `{profile}` budget {minimum}-{maximum}: {', '.join(off_budget[:8])}.",
            )
        )
    return issues


def check_argument_snapshot(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    todo_rel = next((item for item in outputs if item.endswith("ARGUMENT_SELFLOOP_TODO.md")), "output/ARGUMENT_SELFLOOP_TODO.md")
    summaries_rel = next((item for item in outputs if item.endswith("SECTION_ARGUMENT_SUMMARIES.jsonl")), "output/SECTION_ARGUMENT_SUMMARIES.jsonl")
    skeleton_rel = next((item for item in outputs if item.endswith("ARGUMENT_SKELETON.md")), "output/ARGUMENT_SKELETON.md")
    manifest_rel = next((item for item in outputs if item.endswith("sections_manifest.jsonl")), "sections/sections_manifest.jsonl")
    required = [todo_rel, summaries_rel, skeleton_rel, manifest_rel]
    missing = [relpath for relpath in required if not (workspace / relpath).exists()]
    if missing:
        return [QualityIssue(code="argument_snapshot_missing_outputs", message=f"Argument snapshot is missing: {', '.join(missing)}.")]

    issues: list[QualityIssue] = []
    report = (workspace / todo_rel).read_text(encoding="utf-8", errors="ignore")
    if not re.search(r"(?im)^-\s*Status:\s*PASS\s*$", report):
        issues.append(QualityIssue(code="argument_snapshot_not_pass", message=f"`{todo_rel}` does not report PASS."))

    skeleton = (workspace / skeleton_rel).read_text(encoding="utf-8", errors="ignore")
    if not re.search(r"(?im)^##\s+Consistency Contract\s*$", skeleton):
        issues.append(QualityIssue(code="argument_snapshot_missing_contract", message=f"`{skeleton_rel}` lacks `## Consistency Contract`."))

    allowed_moves = {"setup", "thesis", "contrast", "evidence", "evaluation", "limitation", "synthesis", "takeaway"}
    summaries = [record for record in read_jsonl(workspace / summaries_rel) if isinstance(record, dict)]
    by_id = {str(record.get("id") or "").strip(): record for record in summaries if str(record.get("id") or "").strip()}
    incomplete: list[str] = []
    for sub_id in _expected_h3_ids(workspace):
        record = by_id.get(sub_id)
        paragraphs = record.get("paragraphs") if isinstance(record, dict) else None
        if not isinstance(paragraphs, list) or not paragraphs:
            incomplete.append(sub_id)
            continue
        for paragraph in paragraphs:
            moves = paragraph.get("moves") if isinstance(paragraph, dict) else None
            if not isinstance(moves, list) or not moves or any(str(move) not in allowed_moves for move in moves):
                incomplete.append(sub_id)
                break
    if incomplete:
        issues.append(
            QualityIssue(
                code="argument_snapshot_incomplete_moves",
                message=f"Argument summaries are missing valid paragraph moves for: {', '.join(dict.fromkeys(incomplete))}.",
            )
        )

    manifest = [record for record in read_jsonl(workspace / manifest_rel) if isinstance(record, dict)]
    manifest_by_path = {str(record.get("path") or "").strip(): record for record in manifest}
    stale: list[str] = []
    for sub_id in _expected_h3_ids(workspace):
        relpath = _section_path_for_id(sub_id)
        path = workspace / relpath
        record = manifest_by_path.get(relpath)
        if not path.exists() or not isinstance(record, dict):
            stale.append(relpath)
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if str(record.get("sha256") or "") != digest or int(record.get("bytes") or 0) != path.stat().st_size:
            stale.append(relpath)
    if stale:
        issues.append(
            QualityIssue(
                code="sections_manifest_stale",
                message=f"`{manifest_rel}` does not fingerprint the current section content: {', '.join(stale[:8])}.",
            )
        )
    return issues


def check_sections_manifest_index(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    """Minimal manifest check for `subsection-writer`.

    Rationale: `subsection-writer` is LLM-first and its script only materializes
    `sections/sections_manifest.jsonl`. The strict "writing is good enough" gate
    is enforced by the explicit self-loop unit (`writer-selfloop`), which
    produces a report and blocks until sections meet the draft profile thresholds.
    """

    from tooling.common import load_yaml, read_jsonl

    out_rel = outputs[0] if outputs else "sections/sections_manifest.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_sections_manifest", message=f"`{out_rel}` does not exist.")]

    records = read_jsonl(path)
    items = [r for r in records if isinstance(r, dict)]
    if not items:
        return [QualityIssue(code="empty_sections_manifest", message=f"`{out_rel}` is empty or has no JSON objects.")]

    # Build expected paths from the outline (and required global section files).
    outline_path = workspace / "outline" / "outline.yml"
    outline = load_yaml(outline_path) if outline_path.exists() else []

    def _slug_unit_id(unit_id: str) -> str:
        raw = str(unit_id or "").strip()
        out: list[str] = []
        for ch in raw:
            out.append(ch if ch.isalnum() else "_")
        safe = "".join(out).strip("_")
        return f"S{safe}" if safe else "S"

    expected: set[str] = {"sections/abstract.md", "sections/discussion.md", "sections/conclusion.md"}
    expected_h3: set[str] = set()

    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            sec_id = str(sec.get("id") or "").strip()
            subs = sec.get("subsections") or []
            if isinstance(subs, list) and subs:
                if sec_id:
                    expected.add(f"sections/{_slug_unit_id(sec_id)}_lead.md")
                for sub in subs:
                    if not isinstance(sub, dict):
                        continue
                    sub_id = str(sub.get("id") or "").strip()
                    if sub_id:
                        relpath = f"sections/{_slug_unit_id(sub_id)}.md"
                        expected.add(relpath)
                        expected_h3.add(relpath)
            else:
                if sec_id:
                    expected.add(f"sections/{_slug_unit_id(sec_id)}.md")

    by_path: dict[str, dict[str, Any]] = {}
    dupes = 0
    for rec in items:
        rel = str(rec.get("path") or "").strip()
        if not rel:
            continue
        if rel in by_path:
            dupes += 1
        by_path[rel] = rec

    issues: list[QualityIssue] = []
    if dupes:
        issues.append(QualityIssue(code="sections_manifest_duplicate_paths", message=f"`{out_rel}` contains duplicate `path` entries ({dupes})."))

    missing = sorted([p for p in expected if p not in by_path])
    if missing:
        sample = ", ".join(missing[:8])
        suffix = "..." if len(missing) > 8 else ""
        issues.append(
            QualityIssue(
                code="sections_manifest_missing_expected_paths",
                message=f"`{out_rel}` is missing some expected entries (e.g., {sample}{suffix}). Regenerate the manifest from the current outline.",
            )
        )

    # Minimal writing gate: require that the expected per-section files exist and are non-empty.
    # Deeper quality thresholds (length/citations/scope) are enforced by `writer-selfloop`.
    missing_files: list[str] = []
    for rel in sorted(expected):
        p = workspace / rel
        if not p.exists() or p.stat().st_size <= 0:
            missing_files.append(rel)
    if missing_files:
        sample = ", ".join(missing_files[:8])
        suffix = "..." if len(missing_files) > 8 else ""
        issues.append(
            QualityIssue(
                code="sections_missing_files",
                message=f"Missing per-section files under `sections/` (e.g., {sample}{suffix}).",
            )
        )

    marker_rel = next(
        (item for item in outputs if item.endswith(".refined.ok")),
        "sections/h3_bodies.refined.ok",
    )
    if (workspace / marker_rel).exists():
        issues.extend(
            check_subsection_template_residue(
                workspace=workspace,
                relpaths=sorted(expected_h3),
            )
        )

    return issues


def check_sections_manifest(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_yaml, read_jsonl

    out_rel = outputs[0] if outputs else "sections/sections_manifest.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_sections_manifest", message=f"`{out_rel}` does not exist.")]

    records = read_jsonl(path)
    if not records:
        return [QualityIssue(code="empty_sections_manifest", message=f"`{out_rel}` is empty.")]

    base_dir = Path(out_rel).parent

    def _slug_unit_id(unit_id: str) -> str:
        raw = str(unit_id or "").strip()
        out: list[str] = []
        for ch in raw:
            if ch.isalnum():
                out.append(ch)
            else:
                out.append("_")
        safe = "".join(out).strip("_")
        return f"S{safe}" if safe else "S"

    outline_path = workspace / "outline" / "outline.yml"
    outline = load_yaml(outline_path) if outline_path.exists() else []

    expected_units: list[dict[str, str]] = []
    expected_leads: list[dict[str, str]] = []
    sub_to_section: dict[str, str] = {}
    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            sec_id = str(sec.get("id") or "").strip()
            sec_title = str(sec.get("title") or "").strip()
            subs = sec.get("subsections") or []
            if subs and isinstance(subs, list):
                # Require a short H2 lead paragraph block for each chapter with H3 subsections.
                # This increases coherence without inflating the ToC (no new headings).
                if sec_id and sec_title:
                    expected_leads.append({"kind": "h2_lead", "id": sec_id, "title": sec_title})
                for sub in subs:
                    if not isinstance(sub, dict):
                        continue
                    sub_id = str(sub.get("id") or "").strip()
                    sub_title = str(sub.get("title") or "").strip()
                    if sub_id and sub_title:
                        expected_units.append(
                            {
                                "kind": "h3",
                                "id": sub_id,
                                "title": sub_title,
                                "section_id": sec_id,
                                "section_title": sec_title,
                            }
                        )
                        if sec_id:
                            sub_to_section[sub_id] = sec_id
            else:
                if sec_id and sec_title:
                    expected_units.append({"kind": "h2", "id": sec_id, "title": sec_title, "section_title": sec_title})

    # Title-aware H2 classification (avoid hard-coding numeric section ids like 1/2).
    h2_title_by_id: dict[str, str] = {}
    ordered_h2_ids: list[str] = []
    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            sec_id = str(sec.get("id") or "").strip()
            sec_title = str(sec.get("title") or "").strip()
            if sec_id and sec_title:
                h2_title_by_id[sec_id] = sec_title
                ordered_h2_ids.append(sec_id)

    # Required global sections (kept outside outline for consistency).
    required_globals = [
        ("abstract", "Abstract", base_dir / "abstract.md"),
        ("discussion", "Discussion", base_dir / "discussion.md"),
        ("conclusion", "Conclusion", base_dir / "conclusion.md"),
    ]
    optional_globals: list[tuple[str, str, Path]] = []

    expected_files: list[tuple[str, str, str]] = []
    for gid, title, rel in required_globals:
        expected_files.append(("global", gid, rel.as_posix()))
    for gid, title, rel in optional_globals:
        expected_files.append(("global_optional", gid, rel.as_posix()))
    for u in expected_leads:
        rel = (base_dir / f"{_slug_unit_id(u['id'])}_lead.md").as_posix()
        expected_files.append((u["kind"], u["id"], rel))
    for u in expected_units:
        rel = (base_dir / f"{_slug_unit_id(u['id'])}.md").as_posix()
        expected_files.append((u["kind"], u["id"], rel))

    issues: list[QualityIssue] = []

    # Basic existence.
    missing_required: list[str] = []
    for kind, uid, rel in expected_files:
        p = workspace / rel
        if kind == "global_optional":
            continue
        if not p.exists() or p.stat().st_size <= 0:
            missing_required.append(rel)
    if missing_required:
        sample = ", ".join(missing_required[:8])
        suffix = "..." if len(missing_required) > 8 else ""
        issues.append(
            QualityIssue(
                code="sections_missing_files",
                message=f"Missing per-section files under `{base_dir.as_posix()}` (e.g., {sample}{suffix}).",
            )
        )

    issues.extend(
        check_subsection_template_residue(
            workspace=workspace,
            relpaths=[rel for kind, _, rel in expected_files if kind == "h3"],
        )
    )

    # Load bibliography keys for cite hygiene.
    bib_path = workspace / "citations" / "ref.bib"
    bib_keys: set[str] = set()
    if bib_path.exists():
        bib_text = bib_path.read_text(encoding="utf-8", errors="ignore")
        bib_keys = set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text))

    # Load evidence bindings to enforce subsection-scoped citations.
    bindings_path = workspace / "outline" / "evidence_bindings.jsonl"
    mapped_by_sub: dict[str, set[str]] = {}
    if bindings_path.exists():
        for rec in read_jsonl(bindings_path):
            if not isinstance(rec, dict):
                continue
            sid = str(rec.get("sub_id") or "").strip()
            mapped = rec.get("mapped_bibkeys") or []
            if sid and isinstance(mapped, list):
                mapped_by_sub[sid] = set(str(x).strip() for x in mapped if str(x).strip())
    else:
        issues.append(
            QualityIssue(
                code="missing_evidence_bindings",
                message="Missing `outline/evidence_bindings.jsonl`; run `evidence-binder` before subsection writing so citations can be scoped per H3.",
                )
            )

    # Allow limited “chapter-scoped” citation reuse: any bibkey mapped to a sibling H3 in the same H2 chapter
    # is considered in-scope (prevents unnecessary BLOCKED loops when mapping is slightly under-specified),
    # but each H3 should still cite some subsection-specific papers.
    mapped_by_section: dict[str, set[str]] = {}
    for sub_id, sec_id in sub_to_section.items():
        allowed = mapped_by_sub.get(sub_id)
        if not allowed or not sec_id:
            continue
        bucket = mapped_by_section.setdefault(sec_id, set())
        bucket.update(allowed)

    # Some papers are legitimately cross-cutting (foundations/benchmarks/surveys) and may be mapped to many subsections.
    # Treat bibkeys mapped to multiple subsections as globally in-scope to reduce unnecessary writer BLOCKED loops.
    mapped_counts: dict[str, int] = {}
    for keys in mapped_by_sub.values():
        for k in keys:
            mapped_counts[k] = mapped_counts.get(k, 0) + 1
    global_threshold = global_citation_min_subsections(workspace)
    mapped_global = {k for k, n in mapped_counts.items() if n >= global_threshold}

    def _extract_keys(text: str) -> set[str]:
        keys: set[str] = set()
        for m in re.finditer(r"\[@([^\]]+)\]", text):
            inside = (m.group(1) or "").strip()
            for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
                if k:
                    keys.add(k)
        return keys

    # Evidence-aware numeric anchors: if the evidence pack contains quantitative snippets for a subsection,
    # require the prose to include at least one cited numeric anchor (prevents “generic prose” drift).
    numeric_available: set[str] = set()
    packs_path = workspace / "outline" / "evidence_drafts.jsonl"
    if packs_path.exists() and packs_path.stat().st_size > 0:
        try:
            for rec in read_jsonl(packs_path):
                if not isinstance(rec, dict):
                    continue
                sid = str(rec.get("sub_id") or "").strip()
                if not sid:
                    continue
                blob_parts: list[str] = []
                for sn in rec.get("evidence_snippets") or []:
                    if isinstance(sn, dict):
                        blob_parts.append(str(sn.get("text") or ""))
                for comp in rec.get("concrete_comparisons") or []:
                    if not isinstance(comp, dict):
                        continue
                    for hl in comp.get("A_highlights") or []:
                        if isinstance(hl, dict):
                            blob_parts.append(str(hl.get("excerpt") or ""))
                    for hl in comp.get("B_highlights") or []:
                        if isinstance(hl, dict):
                            blob_parts.append(str(hl.get("excerpt") or ""))
                blob = " ".join([p for p in blob_parts if p]).strip()
                if blob and re.search(r"\d", blob):
                    numeric_available.add(sid)
        except Exception:
            # Non-fatal: skip this check if evidence packs are unreadable.
            numeric_available = set()

    # Content checks per file.
    for kind, uid, rel in expected_files:
        p = workspace / rel
        if not p.exists() or p.stat().st_size <= 0:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if has_placeholder_markers(text) or "…" in text or re.search(r"(?m)\.\.\.+", text):
            issues.append(
                QualityIssue(
                    code="sections_contains_placeholders",
                    message=f"`{rel}` contains placeholders/ellipsis (`TODO`/`…`/`...`); rewrite this unit into complete, checkable prose.",
                )
            )
            break
        if re.search(
            r"(?im)^(?:intent|rq|question|scope cues|evidence needs|expected cites|concrete comparisons|evaluation anchors|comparison axes)\s*[:：]",
            text,
        ):
            issues.append(
                QualityIssue(
                    code="sections_contains_outline_meta",
                    message=(
                        f"`{rel}` contains outline/brief meta markers (Intent/RQ/Evidence needs/etc.). "
                        "These belong in `outline/outline.yml` or briefs, not in final prose; rewrite to remove meta prefixes."
                    ),
                )
            )
            break
        if (
            re.search(r"(?i)\babstracts are treated as verification targets\b", text)
            or re.search(r"(?i)\bthe main axes we track are\b", text)
            or re.search(r"(?i)\bevidence\s+packs?\b", text)
        ):
            issues.append(
                QualityIssue(
                    code="sections_contains_pipeline_voice",
                    message=f"`{rel}` contains pipeline-style boilerplate; rewrite to be subsection-specific and avoid repeated template sentences.",
                )
            )
        # Citation embedding: avoid stand-alone citation lines (label-style citations).
        if re.search(r"(?m)^\\[@[^\\]]+\\]\\s*$", text):
            issues.append(
                QualityIssue(
                    code="sections_citation_dump_line",
                    message=(
                        f"`{rel}` contains a stand-alone citation line (e.g., a line that is only `[@...]`). "
                        "Embed citations into the sentence they support (system name + claim), not as end-of-paragraph tags."
                    ),
                )
            )
            break

            break

        # H3 body files must not contain headings.
        if kind == "h3":
            for ln in text.splitlines():
                if ln.strip().startswith("#"):
                    issues.append(
                        QualityIssue(
                            code="sections_h3_has_headings",
                            message=f"`{rel}` should be body-only (no `#`/`##`/`###` headings); headings are added by `section-merger`.",
                        )
                    )
                    break

            cite_keys = _extract_keys(text)
            profile = pipeline_profile_name(workspace)
            draft_profile = resolve_draft_profile(workspace)
            if profile == "arxiv-survey":
                # Survey H3s should stay evidence-dense, but local floors must not force
                # citation-padding or template-only breadth paragraphs. Use a lower local
                # floor here and rely on the global citation target later in the pipeline.
                min_cites = 4 if draft_profile == "course_paper" else (8 if draft_profile == "deep" else 6)
                if len(cite_keys) < min_cites:
                    issues.append(
                        QualityIssue(
                            code="sections_h3_sparse_citations",
                            message=f"`{rel}` has <{min_cites} unique citations ({len(cite_keys)}); each H3 should be evidence-first for survey-quality runs.",
                        )
                    )

            if profile == "arxiv-survey":
                if draft_profile == "course_paper":
                    min_paragraphs = 5
                    min_chars = 1600
                elif draft_profile == "deep":
                    min_paragraphs = 9
                    # Keep sections "thick" without forcing filler; prefer argument-move checks over raw length.
                    # This is a post-citation length floor (citations removed) used as a readability proxy.
                    min_chars = 4300
                else:
                    min_paragraphs = 8
                    min_chars = 3300

                paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
                # Paper voice: block narration templates that read like outline commentary
                # ("This subsection ...", "In this subsection ...") and slide-like navigation.
                first_para = paragraphs[0] if paragraphs else ""
                first_no_cites = re.sub(r"\[@[^\]]+\]", "", first_para)
                first_no_cites = re.sub(r"\s+", " ", first_no_cites).strip()
                if re.search(
                    r"(?i)\b(?:this\s+(?:section|subsection)\s+(?:surveys|reviews|discusses|covers|presents|introduces|outlines|summarizes|describes|argues|shows|highlights|demonstrates|contends)|in\s+this\s+(?:section|subsection))\b",
                    first_no_cites,
                ):
                    issues.append(
                        QualityIssue(
                            code="sections_h3_narration_template_opener",
                            message=(
                                f"`{rel}` starts with narration-style template phrasing (e.g., 'This subsection ...'). "
                                "Rewrite paragraph 1 as a content claim (tension/decision/lens) and end with the thesis."
                            ),
                        )
                    )
                if re.search(
                    r"(?i)\b(?:next,\s+we\s+move\s+from|we\s+now\s+(?:turn|move)\s+to|in\s+the\s+next\s+(?:section|subsection))\b",
                    text,
                ):
                    issues.append(
                        QualityIssue(
                            code="sections_h3_slide_narration",
                            message=(
                                f"`{rel}` contains slide-like navigation narration (e.g., 'We now turn to ...'). "
                                "Rewrite as argument bridges (no navigation commentary)."
                            ),
                        )
                    )
                # Evidence-policy disclaimers belong once in front matter, not repeated across H3s.
                if re.search(
                    r"(?i)\b(?:abstract(?:-|\s+)(?:only|level)\s+evidence|title(?:-|\s+)only\s+evidence|claims?\s+remain\s+provisional\s+under\s+abstract(?:-|\s+)(?:only|level)\s+evidence)\b",
                    text,
                ):
                    issues.append(
                        QualityIssue(
                            code="sections_h3_evidence_policy_disclaimer_spam",
                            message=(
                                f"`{rel}` repeats evidence-policy/disclaimer phrasing (abstract/title-only/provisional claims). "
                                "Keep evidence policy once in front matter (Intro/Related Work) and avoid repeating it in H3 bodies."
                            ),
                        )
                    )
                if re.search(r"(?i)\bsurvey\s+(?:synthesis|comparisons?)\s+should\b", text):
                    issues.append(
                        QualityIssue(
                            code="sections_h3_meta_survey_guidance",
                            message=(
                                f"`{rel}` contains meta survey-guidance phrasing ('survey ... should ...'). "
                                "Rewrite as literature-facing observations grounded in cited work (no new facts)."
                            ),
                        )
                    )
                stock_template_patterns = [
                    r"(?i)\bread together,\s+.+?\bdiverge less on headline performance\b",
                    r"(?i)\bwhat matters operationally in\b",
                    r"(?i)\bthe comparison only becomes actionable after\b",
                    r"(?i)\bthe relevant implementation split in\b",
                    r"(?i)\bthe evaluation story for\b",
                    r"(?i)\bby contrast, another strand in\b",
                    r"(?i)\bthe subsection-level contrast between\b",
                    r"(?i)\bacross those neighboring studies,\b",
                    r"(?i)\bthose mapped papers still tie\b",
                    r"(?i)\bthese gains remain provisional because\b",
                ]
                stock_template_hits = sum(len(re.findall(pattern, text)) for pattern in stock_template_patterns)
                if stock_template_hits >= 5:
                    issues.append(
                        QualityIssue(
                            code="sections_h3_template_density",
                            message=(
                                f"`{rel}` still contains too many stock subsection-writer stems ({stock_template_hits} hits). "
                                "Reduce scaffold phrasing and replace repeated bridge sentences with section-specific synthesis."
                            ),
                        )
                    )
                if len(paragraphs) < min_paragraphs:
                    issues.append(
                        QualityIssue(
                            code="sections_h3_too_few_paragraphs",
                            message=f"`{rel}` has too few paragraphs ({len(paragraphs)}); aim for {min_paragraphs}–{max(min_paragraphs, 12)} paragraphs per H3 for this draft profile.",
                        )
                    )
                # Citation embedding: discourage paragraphs where citations appear only as a trailing dump.
                dump_paras = 0
                for para in paragraphs:
                    m = re.search(r"\[@([^\]]+)\]\s*$", para)
                    if not m:
                        continue
                    # Only consider paragraphs with >=3 cited keys to avoid over-blocking.
                    keys_in_tail = set(re.findall(r"[A-Za-z0-9:_-]+", m.group(1) or ""))
                    if len(keys_in_tail) < 3:
                        continue
                    if para.count("[@") != 1:
                        continue
                    dump_paras += 1
                if dump_paras:
                    issues.append(
                        QualityIssue(
                            code="sections_h3_citation_dump_paragraphs",
                            message=(
                                f"`{rel}` has {dump_paras} paragraph(s) where citations appear only as a trailing dump (e.g., ending with `[@a; @b; @c]`). "
                                "Embed citations into the sentence they support (system name + claim), rather than tagging the paragraph at the end."
                            ),
                        )
                    )


                content = re.sub(r"\[@[^\]]+\]", "", text)
                content = re.sub(r"\s+", " ", content).strip()
                if len(content) < min_chars:
                    issues.append(
                        QualityIssue(
                            code="sections_h3_too_short",
                            message=(
                                f"`{rel}` looks too short ({len(content)} chars after removing citations; min={min_chars}). "
                                "Expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack."
                            ),
                        )
                    )

                has_multi_cite = any(len(_extract_keys(p)) >= 2 for p in paragraphs)
                if not has_multi_cite:
                    issues.append(
                        QualityIssue(
                            code="sections_h3_no_multi_cite_paragraph",
                            message=f"`{rel}` has no paragraph with >=2 citations; add at least one cross-paper synthesis paragraph (contrast A vs B with multiple cites).",
                        )
                    )

                # “Grad paragraph” micro-structure signals: contrast + evaluation anchor + limitation.
                # Density (not just presence) helps prevent long-but-hollow prose.
                contrast_re = r"(?i)\b(?:whereas|however|in\s+contrast|by\s+contrast|versus|vs\.)\b|相比|不同于|相较|对比|反之"
                eval_re = (
                    r"(?i)\b(?:benchmark|dataset|datasets|metric|metrics|evaluation|eval\.|protocol|human|ablation|"
                    r"latency|cost|budget|token|tokens|throughput|compute)\b|评测|基准|数据集|指标|协议|人工|实验|成本|预算|延迟"
                )
                limitation_re = r"(?i)\b(?:limitations?|limited|provisional|unclear|sensitive|caveat|downside|failure|risk|open\s+question|remains)\b|受限|尚不明确|缺乏|需要核验|局限|失败|风险|待验证"

                if uid in numeric_available:
                    has_cited_numeric = any(re.search(r"\d", p) and "[@" in p for p in paragraphs)
                    if not has_cited_numeric:
                        issues.append(
                            QualityIssue(
                                code="sections_h3_missing_cited_numeric",
                                message=(
                                    f"`{rel}` has no cited numeric anchor (no digit in the same paragraph as a citation). "
                                    "Evidence packs for this subsection contain quantitative snippets; include at least one concrete number/result with citations."
                                ),
                            )
                        )

                if draft_profile == "course_paper":
                    min_contrast = 1
                    min_eval = 1
                    min_lim = 1
                    min_anchor_paras = 2
                elif draft_profile == "deep":
                    min_contrast = 3
                    min_eval = 3
                    min_lim = 2
                    min_anchor_paras = 4
                else:
                    min_contrast = 2
                    min_eval = 2
                    min_lim = 1
                    min_anchor_paras = 3

                contrast_n = len(re.findall(contrast_re, text))
                eval_n = len(re.findall(eval_re, text))
                lim_n = len(re.findall(limitation_re, text))

                if contrast_n < min_contrast:
                    issues.append(
                        QualityIssue(
                            code="sections_h3_missing_contrast",
                            message=(
                                f"`{rel}` lacks explicit contrast phrasing (need >= {min_contrast}; found {contrast_n}). "
                                "Use whereas/in contrast/相比/不同于 to compare routes, not only summarize."
                            ),
                        )
                    )
                if eval_n < min_eval:
                    issues.append(
                        QualityIssue(
                            code="sections_h3_missing_eval_anchor",
                            message=(
                                f"`{rel}` lacks evaluation anchors (need >= {min_eval}; found {eval_n}). "
                                "Include benchmark/dataset/metric/protocol/评测 even at abstract level."
                            ),
                        )
                    )
                if lim_n < min_lim:
                    issues.append(
                        QualityIssue(
                            code="sections_h3_missing_limitation",
                            message=(
                                f"`{rel}` lacks limitation/provisional signals (need >= {min_lim}; found {lim_n}). "
                                "Add explicit caveats (limited/unclear/受限/待验证) to avoid overclaiming."
                            ),
                        )
                    )

                # Evidence-consumption proxy: count paragraphs that are both cited and anchored
                # (digit OR evaluation token OR limitation token). Helps prevent long-but-generic prose.
                anchored_paras = 0
                for p in paragraphs:
                    if "[@" not in p:
                        continue
                    if re.search(r"\d", p) or re.search(eval_re, p) or re.search(limitation_re, p):
                        anchored_paras += 1
                if anchored_paras < min_anchor_paras:
                    issues.append(
                        QualityIssue(
                            code="sections_h3_weak_anchor_density",
                            message=(
                                f"`{rel}` has too few anchored+cited paragraphs ({anchored_paras}; min={min_anchor_paras}). "
                                "Ensure multiple paragraphs include citations along with numbers, evaluation anchors, or concrete limitations."
                            ),
                        )
                    )
            if bib_keys:
                missing = sorted([k for k in cite_keys if k not in bib_keys])
                if missing:
                    sample = ", ".join(missing[:8])
                    suffix = "..." if len(missing) > 8 else ""
                    issues.append(
                        QualityIssue(
                            code="sections_cites_missing_in_bib",
                            message=f"`{rel}` cites keys missing from `citations/ref.bib` (e.g., {sample}{suffix}).",
                        )
                    )
            if mapped_by_sub.get(uid):
                allowed_sub = mapped_by_sub.get(uid) or set()
                sec_id = sub_to_section.get(uid) or ""
                allowed_chapter = mapped_by_section.get(sec_id, set()) if sec_id else set()

                profile = pipeline_profile_name(workspace)
                if profile == "arxiv-survey":
                    sub_specific = {k for k in cite_keys if k in allowed_sub}
                    min_sub_specific = 2 if draft_profile == "course_paper" else 3
                    if len(sub_specific) < min_sub_specific:
                        issues.append(
                            QualityIssue(
                                code="sections_h3_sparse_subsection_cites",
                                message=(
                                    f"`{rel}` cites too few subsection-specific papers ({len(sub_specific)}). "
                                    f"Chapter-scoped reuse is allowed, but each H3 should still ground itself in >={min_sub_specific} papers mapped to that subsection."
                                ),
                            )
                        )

                outside = sorted([k for k in cite_keys if k not in allowed_sub and k not in allowed_chapter and k not in mapped_global])
                if outside:
                    sample = ", ".join(outside[:8])
                    suffix = "..." if len(outside) > 8 else ""
                    issues.append(
                        QualityIssue(
                            code="sections_cites_outside_mapping",
                            message=(
                                f"`{rel}` cites keys not mapped to subsection {uid}"
                                + (f" (or its chapter {sec_id})" if sec_id else "")
                                + f" (e.g., {sample}{suffix}); keep citations subsection- or chapter-scoped (or fix mapping/bindings)."
                            ),
                        )
                    )
        elif kind == "h2_lead":
            # H2 lead blocks should be body-only and citation-grounded.
            for ln in text.splitlines():
                if ln.strip().startswith("#"):
                    issues.append(
                        QualityIssue(
                            code="sections_h2_lead_has_headings",
                            message=f"`{rel}` should be body-only (no headings); it is injected under the chapter H2 heading by `section-merger`.",
                        )
                    )
                    break
            cite_keys = _extract_keys(text)
            if pipeline_profile_name(workspace) == "arxiv-survey" and len(cite_keys) < 2:
                issues.append(
                    QualityIssue(
                        code="sections_h2_lead_sparse_citations",
                        message=f"`{rel}` has too few citations ({len(cite_keys)}); chapter leads should be grounded (>=2) to avoid generic glue text.",
                    )
                )

        elif kind == "global":
            # Minimal heading sanity for required global sections.
            if uid == "abstract" and not re.search(r"(?im)^##\s+(abstract|摘要)\b", text):
                issues.append(
                    QualityIssue(
                        code="sections_abstract_missing_heading",
                        message=f"`{rel}` should start with `## Abstract` (or `## 摘要`).",
                    )
                )
            if uid == "discussion" and not re.search(r"(?im)^##\s+(discussion|discussion and future work|discussion & future work|讨论|讨论与未来工作|讨论与未来方向)\b", text):
                issues.append(
                    QualityIssue(
                        code="sections_discussion_missing_heading",
                        message=f"`{rel}` should include an `## Discussion` heading (or equivalent).",
                    )
                )
            if uid == "conclusion" and not re.search(r"(?im)^##\s+(conclusion|结论)\b", text):
                issues.append(
                    QualityIssue(
                        code="sections_conclusion_missing_heading",
                        message=f"`{rel}` should include an `## Conclusion/结论` heading.",
                    )
                )
        else:
            # H2 body files.
            if kind == "h2":
                cite_keys = _extract_keys(text)
                if "[@" not in text:
                    issues.append(
                        QualityIssue(
                            code="sections_h2_no_citations",
                            message=f"`{rel}` contains no citations; H2 sections should be grounded with citations (or keep claims purely structural).",
                        )
                    )

                # Front-matter strength (Intro + Related Work) is a common weak point: enforce cite density + depth.
                sec_title = h2_title_by_id.get(uid, "")
                t_norm = re.sub(r"\s+", " ", (sec_title or "")).strip().lower()
                is_intro = bool(re.search(r"\b(introduction|intro)\b", t_norm) or re.search(r"(引言|简介|概述)", sec_title))
                is_related = bool(
                    re.search(r"\b(related work|related works|literature review|prior work|related surveys)\b", t_norm)
                    or re.search(r"(相关工作|文献综述)", sec_title)
                )
                # Fallback: treat the first two H2 sections as front matter when titles are customized.
                if ordered_h2_ids:
                    if uid == ordered_h2_ids[0]:
                        is_intro = True
                    if len(ordered_h2_ids) > 1 and uid == ordered_h2_ids[1]:
                        is_related = True

                if pipeline_profile_name(workspace) == "arxiv-survey" and (is_intro or is_related):
                    draft_profile = resolve_draft_profile(workspace)
                    front_kind = "introduction" if is_intro else "related_work"
                    default_front = (
                        {"min_cites": 6, "min_paras": 3, "min_chars": 1200}
                        if draft_profile == "course_paper" and is_intro
                        else {"min_cites": 8, "min_paras": 3, "min_chars": 1400}
                        if draft_profile == "course_paper"
                        else {"min_cites": 40, "min_paras": 3, "min_chars": 3600}
                        if draft_profile == "deep" and is_intro
                        else {"min_cites": 55, "min_paras": 2, "min_chars": 4200}
                        if draft_profile == "deep"
                        else {"min_cites": 35, "min_paras": 2, "min_chars": 3200}
                        if is_intro
                        else {"min_cites": 50, "min_paras": 1, "min_chars": 3800}
                    )
                    min_cites = quality_contract_int(
                        workspace,
                        keys=("front_matter_policy", draft_profile, front_kind, "min_cites"),
                        default=default_front["min_cites"],
                    )
                    min_paras = quality_contract_int(
                        workspace,
                        keys=("front_matter_policy", draft_profile, front_kind, "min_paras"),
                        default=default_front["min_paras"],
                    )
                    min_chars = quality_contract_int(
                        workspace,
                        keys=("front_matter_policy", draft_profile, front_kind, "min_chars"),
                        default=default_front["min_chars"],
                    )

                    if is_intro:
                        front_fix = (
                            "Fix: expand motivation + scope boundary + one evidence-policy paragraph + organization preview; "
                            "keep paper voice (avoid outline narration like 'This subsection...')."
                        )
                    else:
                        front_fix = (
                            "Fix: expand positioning vs adjacent lines of work + survey coverage + one evidence-policy paragraph + organization preview; "
                            "avoid a dedicated 'Prior Surveys' mini-section by default; keep third-person academic voice (avoid 'this/current survey' deictic phrasing)."
                        )

                    content = re.sub(r"\[@[^\]]+\]", "", text)
                    content = re.sub(r"\s+", " ", content).strip()

                    paras = [p.strip() for p in re.split(r"\n\s*\n", re.sub(r"\[@[^\]]+\]", "", text)) if p.strip()]
                    long_paras = [
                        p
                        for p in paras
                        if len(re.sub(r"\s+", " ", p).strip()) >= 200 and not p.lstrip().startswith(("-", "*", "|", "```"))
                    ]

                    if len(set(cite_keys)) < min_cites:
                        code = "sections_intro_sparse_citations" if is_intro else "sections_related_work_sparse_citations"
                        label = sec_title or ("Introduction" if is_intro else "Related Work")
                        issues.append(
                            QualityIssue(
                                code=code,
                                message=(
                                    f"`{rel}` ({label}) cites too few unique papers ({len(set(cite_keys))}; min={min_cites}). "
                                    f"Increase concrete, cite-grounded positioning and coverage. {front_fix}"
                                ),
                            )
                        )
                    if len(content) < min_chars:
                        code = "sections_intro_too_short" if is_intro else "sections_related_work_too_short"
                        label = sec_title or ("Introduction" if is_intro else "Related Work")
                        issues.append(
                            QualityIssue(
                                code=code,
                                message=(
                                    f"`{rel}` ({label}) looks too short ({len(content)} chars after removing citations; min={min_chars}). "
                                    f"Expand motivation/scope/contributions and keep claims citation-grounded. {front_fix}"
                                ),
                            )
                        )
                    if len(long_paras) < min_paras:
                        code = "sections_intro_too_few_paragraphs" if is_intro else "sections_related_work_too_few_paragraphs"
                        label = sec_title or ("Introduction" if is_intro else "Related Work")
                        issues.append(
                            QualityIssue(
                                code=code,
                                message=(
                                    f"`{rel}` ({label}) has too few substantive paragraphs ({len(long_paras)}; min={min_paras}). "
                                    f"Avoid bullet-only structure; write full paragraphs with citations. {front_fix}"
                                ),
                            )
                        )

    return issues


def check_section_logic_polisher(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    """Logic-level polish gate (thesis + connector density) for H3 files under `sections/`.

    This is intended to run after drafting and before merge.

    Runtime semantics:
    - block on a FAIL report (the checker only fails on thesis / template-opener problems)
    - keep connector counts diagnostic-only
    """

    report_rel = outputs[0] if outputs else "output/SECTION_LOGIC_REPORT.md"
    report_path = workspace / report_rel
    if not report_path.exists():
        return [QualityIssue(code="missing_section_logic_report", message=f"`{report_rel}` does not exist.")]
    report = report_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not report:
        return [QualityIssue(code="empty_section_logic_report", message=f"`{report_rel}` is empty.")]
    if has_placeholder_markers(report) or "…" in report:
        return [
            QualityIssue(
                code="section_logic_report_placeholders",
                message=f"`{report_rel}` contains placeholders/ellipsis; regenerate the report after fixing section files.",
            )
        ]

    if "- Status: PASS" not in report:
        return [
            QualityIssue(
                code="section_logic_report_not_pass",
                message=(
                    f"`{report_rel}` is not PASS; fix paragraph-1 thesis / template-opener issues in the flagged "
                    "H3 files and rerun `section-logic-polisher`."
                ),
            )
        ]

    return []


def check_merge_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    draft_rel = outputs[0] if outputs else "output/DRAFT.md"
    report_rel = outputs[1] if len(outputs) > 1 else "output/MERGE_REPORT.md"

    report_path = workspace / report_rel
    if not report_path.exists():
        return [QualityIssue(code="missing_merge_report", message=f"`{report_rel}` does not exist.")]
    report = report_path.read_text(encoding="utf-8", errors="ignore")
    if "- Status: PASS" not in report:
        return [QualityIssue(code="merge_not_pass", message=f"`{report_rel}` is not PASS; fix missing section files and rerun merge.")]

    draft_path = workspace / draft_rel
    if not draft_path.exists():
        return [QualityIssue(code="missing_merged_draft", message=f"`{draft_rel}` does not exist.")]
    draft = draft_path.read_text(encoding="utf-8", errors="ignore")
    if re.search(r"(?m)^TODO:\s+MISSING\s+`", draft):
        return [
            QualityIssue(
                code="merge_contains_missing_markers",
                message="Merged draft still contains `TODO: MISSING ...` markers; write the missing `sections/*.md` units and merge again.",
            )
        ]
    return []


def check_audit_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/AUDIT_REPORT.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_audit_report", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_audit_report", message=f"`{out_rel}` is empty.")]
    if "- Status: PASS" not in text:
        return [QualityIssue(code="audit_report_not_pass", message=f"`{out_rel}` does not report PASS; fix issues and rerun auditor.")]

    draft_rel = "output/DRAFT.md"
    draft_path = workspace / draft_rel
    if not draft_path.exists():
        return [QualityIssue(code="missing_audited_draft", message=f"`{draft_rel}` does not exist.")]
    draft = draft_path.read_text(encoding="utf-8", errors="ignore")
    return check_template_residue_documents(
        workspace=workspace,
        documents=[(draft_rel, draft)],
    )


def check_draft(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import reader_request_leakage

    out_rel = outputs[0] if outputs else "output/DRAFT.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_draft", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore")

    issues: list[QualityIssue] = []
    request_leaks = reader_request_leakage(text)
    if request_leaks:
        issues.append(
            QualityIssue(
                code="draft_delivery_request_leakage",
                message=(
                    "Draft contains user delivery instructions instead of a reader-facing research subject "
                    f"({', '.join(request_leaks)}). Normalize the paper title/front matter from `GOAL.md` before merging."
                ),
            )
        )
    if re.search(r"\bTODO\b", text):
        issues.append(QualityIssue(code="draft_contains_todo", message="Draft still contains `TODO` placeholders."))
    if re.search(r"(?i)\b(?:TBD|FIXME)\b", text):
        issues.append(QualityIssue(code="draft_contains_placeholders", message="Draft still contains `TBD/FIXME` placeholders."))
    if "<!-- SCAFFOLD" in text:
        issues.append(
            QualityIssue(code="draft_contains_scaffold", message="Draft still contains `<!-- SCAFFOLD ... -->` markers.")
        )
    if "[@" not in text:
        issues.append(QualityIssue(code="draft_no_citations", message="Draft contains no citation markers like `[@BibKey]`."))

    if re.search(r"\[@(?:Key|KEY)\d+", text):
        issues.append(
            QualityIssue(
                code="draft_placeholder_cites",
                message="Draft still contains placeholder citation keys like `[@Key1]`; replace with real keys from `citations/ref.bib`.",
            )
        )

    profile = pipeline_profile_name(workspace)
    if "…" in text:
        issues.append(
            QualityIssue(
                code="draft_contains_ellipsis_placeholders",
                message="Draft contains unicode ellipsis (`…`), which is treated as a hard failure signal (usually truncated scaffold text); regenerate after fixing outline/claims/visuals.",
            )
        )
    if re.search(r"(?m)\.\.\.+", text):
        issues.append(
            QualityIssue(
                code="draft_contains_truncation_dots",
                message="Draft contains `...` truncation markers, which read as scaffold leakage; remove truncation and rewrite into complete sentences/cells.",
            )
        )
    if re.search(r"(?i)enumerate\s+2-4\s+recurring", text):
        issues.append(
            QualityIssue(
                code="draft_scaffold_instructions",
                message="Draft still contains scaffold instructions like 'enumerate 2-4 recurring ...'; rewrite outline/claims into concrete content before drafting.",
            )
        )
    if re.search(r"(?i)\b(?:scope and definitions for|design space in|evaluation practice for)\b", text):
        issues.append(
            QualityIssue(
                code="draft_scaffold_phrases",
                message="Draft still contains outline scaffold phrases (scope/design space/evaluation practice). Replace with subsection-specific content grounded in evidence fields and mapped papers.",
            )
        )
    if re.search(r"(?i)\babstracts are treated as verification targets\b", text):
        issues.append(
            QualityIssue(
                code="draft_pipeline_voice_abstract_only",
                message=(
                    "Draft contains pipeline-style evidence-mode boilerplate ('abstracts are treated as verification targets'). "
                    "Move evidence caveats into a single, short evidence-policy paragraph (once, in front matter), and keep subsections focused on concrete comparisons."
                ),
            )
        )
    if re.search(r"(?i)\bthe main axes we track are\b", text):
        issues.append(
            QualityIssue(
                code="draft_pipeline_voice_axes_template",
                message=(
                    "Draft contains the repeated axes template ('The main axes we track are ...'), which reads as scaffolding. "
                    "Use subsection-specific axes from `outline/subsection_briefs.jsonl` / `outline/evidence_drafts.jsonl` and avoid repeating a global template sentence."
                ),
            )
        )

    dangling_numeric_caveats = re.findall(
        r"(?i)\b(?:that number|the cited number|this numeric margin|the numeric margin)\b",
        text,
    )
    if dangling_numeric_caveats:
        issues.append(
            QualityIssue(
                code="draft_dangling_numeric_caveat",
                message=(
                    "Draft contains anaphoric numeric caveats after the underlying number was removed "
                    f"({len(dangling_numeric_caveats)} occurrence(s)). Rewrite each caveat as a standalone, "
                    "evidence-bounded claim about the cited setup."
                ),
            )
        )

    # If a BibTeX file exists, ensure every cited key is present (prevents LaTeX undefined-citation warnings).
    bib_path = workspace / "citations" / "ref.bib"
    if bib_path.exists():
        bib_text = bib_path.read_text(encoding="utf-8", errors="ignore")
        bib_keys = set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text))
        cited: set[str] = set()
        for m in re.finditer(r"\[@([^\]]+)\]", text):
            inside = (m.group(1) or "").strip()
            for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
                if k:
                    cited.add(k)
        missing = sorted([k for k in cited if k not in bib_keys])
        if missing:
            sample = ", ".join(missing[:8])
            suffix = "..." if len(missing) > 8 else ""
            issues.append(
                QualityIssue(
                    code="draft_cites_missing_in_bib",
                    message=f"Draft cites keys that are missing from `citations/ref.bib` (e.g., {sample}{suffix}).",
                )
            )
        if profile == "arxiv-survey":
            min_bib = int(core_size(workspace)) or 150
            if len(bib_keys) < min_bib:
                issues.append(
                    QualityIssue(
                        code="draft_bib_too_small",
                        message=f"`citations/ref.bib` has {len(bib_keys)} entries; target >= {min_bib} for survey-quality coverage.",
                    )
                )

    # Citation-shape hygiene (reader-facing quality):
    # - disallow adjacent citation blocks like `... [@a] [@b]`
    # - disallow duplicate keys inside one citation block like `[@a; @a]`
    # - keep a minimum mid-sentence citation ratio per subsection (avoid tail-only cite style)
    adj_cite_pat = r"\[@[^\]]+\]\s*\[@[^\]]+\]"
    adj_hits = len(re.findall(adj_cite_pat, text))
    if adj_hits:
        issues.append(
            QualityIssue(
                code="draft_adjacent_citation_blocks",
                message=(
                    f"Draft contains adjacent citation blocks ({adj_hits}×, e.g., `[@a] [@b]`); "
                    "merge same-sentence citations into a single citation block."
                ),
            )
        )

    dup_in_block = 0
    for m in re.finditer(r"\[@([^\]]+)\]", text):
        keys = [k for k in re.findall(r"[A-Za-z0-9:_-]+", (m.group(1) or "")) if k]
        if keys and len(set(keys)) != len(keys):
            dup_in_block += 1
    if dup_in_block:
        issues.append(
            QualityIssue(
                code="draft_duplicate_keys_in_citation_block",
                message=(
                    f"Draft contains citation blocks with duplicate keys ({dup_in_block}×, e.g., `[@x; @x]`); "
                    "deduplicate keys inside each citation block."
                ),
            )
        )

    if profile == "arxiv-survey":
        h3_blocks = split_h3_blocks(text)
        floor = 0.30 if resolve_draft_profile(workspace) in {"survey", "deep"} else 0.20
        low_ratio: list[str] = []
        for title, body in h3_blocks:
            paras = [p.strip() for p in re.split(r"\n\s*\n", body or "") if p.strip()]
            cited = 0
            mid = 0
            for para in paras:
                if "[@" not in para:
                    continue
                cited += 1
                cites = list(re.finditer(r"\[@[^\]]+\]", para))
                if any(m.start() < max(0, len(para) - 45) for m in cites):
                    mid += 1
            if cited < 4:
                continue
            ratio = mid / max(1, cited)
            if ratio < floor:
                short = title[:48] + ("..." if len(title) > 48 else "")
                low_ratio.append(f"{short} ({mid}/{cited}={ratio:.0%})")
        if low_ratio:
            issues.append(
                QualityIssue(
                    code="draft_low_mid_sentence_citation_ratio",
                    message=(
                        f"Some subsections have low mid-sentence citation ratio (<{int(floor * 100)}%): "
                        + "; ".join(low_ratio[:8])
                        + ". Move some citations into the claim sentences they support (not only paragraph tails)."
                    ),
                )
            )

    # Detect repeated "open problems" boilerplate across subsections.
    open_lines = [ln.strip() for ln in text.splitlines() if ln.strip().lower().startswith(("open problems:", "开放问题："))]
    if open_lines:
        counts: dict[str, int] = {}
        for ln in open_lines:
            counts[ln] = counts.get(ln, 0) + 1
        top_line, top_count = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        if top_count >= 5 and top_count / len(open_lines) >= 0.6:
            issues.append(
                QualityIssue(
                    code="draft_repeated_open_problems",
                    message=f"Open-problems text repeats across sections (e.g., `{top_line}`); make it subsection-specific and concrete.",
                )
            )

    # Detect repeated takeaways boilerplate.
    take_lines = [ln.strip() for ln in text.splitlines() if ln.strip().lower().startswith(("takeaways:", "takeaway:", "小结："))]
    if take_lines:
        counts: dict[str, int] = {}
        for ln in take_lines:
            counts[ln] = counts.get(ln, 0) + 1
        top_line, top_count = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        if top_count >= 5 and top_count / len(take_lines) >= 0.6:
            issues.append(
                QualityIssue(
                    code="draft_repeated_takeaways",
                    message=f"Takeaways text repeats across sections (e.g., `{top_line}`); rewrite to reflect subsection-specific synthesis.",
                )
            )

    template_phrases = [
        "Representative works:",
        "Discussion: 当前证据主要来自标题/摘要级信息",
        "本节围绕",
        "本小节围绕",
        "本小节聚焦",
        "从可复核的对比维度出发",
        "总结主要趋势与挑战",
        "对比维度（按已批准的 outline）包括：",
        "小结：综合这些工作，主要权衡通常落在以下维度：",
        "Takeaways: 综合这些工作，主要权衡通常落在以下维度：",
        "是 LLM 智能体系统中的一个关键维度",
        "We use the following working claim to guide synthesis:",
        "Across representative works, the dominant trade-offs",
        "This section summarizes the main design patterns and empirical lessons",
        "is best understood by comparing how adjacent designs trade off competing requirements",
        "The subsection therefore asks",
        "That is why the subsection returns to",
        "What survives synthesis is a bounded conclusion",
        "Beyond the central comparison cards",
        "One useful contrast in",
        "One concrete anchor in",
        "A recurring limitation is that",
    ]
    template_hits = sum(text.count(p) for p in template_phrases)
    if template_hits >= 3:
        issues.append(
            QualityIssue(
                code="draft_template_text",
                message="Draft still contains repeated template boilerplate; rewrite into paragraph-style synthesis grounded in notes/evidence.",
            )
        )

    if profile == "arxiv-survey":
        paras_all = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        content_paras = 0
        uncited_paras = 0
        for para in paras_all:
            if para.startswith(("#", "|", "```")):
                continue
            # Skip short paragraphs (titles, captions, etc.).
            if len(para) < 240:
                continue
            # Tables are handled separately by other checks.
            if "\n|" in para:
                continue
            content_paras += 1
            if "[@" not in para:
                uncited_paras += 1
        if content_paras and (uncited_paras / content_paras) > 0.25:
            issues.append(
                QualityIssue(
                    code="draft_too_many_uncited_paragraphs",
                    message=f"Too many content paragraphs lack citations ({uncited_paras}/{content_paras}); survey drafting should be evidence-first with paragraph-level cites.",
                )
            )

    # Heuristic: each subsection should have some body and at least one citation.
    blocks = re.split(r"\n###\s+", text)
    subsection_blocks = blocks[1:] if len(blocks) > 1 else []
    if subsection_blocks:
        draft_profile = resolve_draft_profile(workspace)
        min_h3_cites = quality_contract_int(
            workspace,
            keys=("subsection_policy", draft_profile, "min_unique_citations"),
            default={"course_paper": 4, "deep": 14}.get(draft_profile, 12),
        )
        min_h3_chars = quality_contract_int(
            workspace,
            keys=("subsection_policy", draft_profile, "min_chars"),
            default={"course_paper": 1600, "deep": 6000}.get(draft_profile, 5000),
        )
        no_cite = 0
        too_short = 0
        low_cite_density = 0
        for block in subsection_blocks:
            lines = [ln for ln in block.splitlines() if ln.strip()]
            # Robustness: do not use line-count as a proxy for section length.
            # Many writers use 1 line per paragraph, which makes "short section" detection brittle.
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            body = re.sub(r"\[@[^\]]+\]", "", body)
            if len(body) < min_h3_chars:
                too_short += 1
            if "[@" not in block:
                no_cite += 1
            if profile == "arxiv-survey":
                cite_keys: set[str] = set()
                for m in re.finditer(r"\[@([^\]]+)\]", block):
                    inside = (m.group(1) or "").strip()
                    for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
                        if k:
                            cite_keys.add(k)
                if len(cite_keys) < min_h3_cites:
                    low_cite_density += 1

        total = max(1, len(subsection_blocks))
        if no_cite / total >= 0.5:
            issues.append(
                QualityIssue(
                    code="draft_sparse_citations",
                    message="Many subsections have no citations; ensure each subsection cites representative works from `citations/ref.bib`.",
                )
            )
        if too_short / total >= 0.5:
            issues.append(
                QualityIssue(
                    code="draft_sections_too_short",
                    message=f"Many subsections are very short (<~{min_h3_chars} chars sans citations); expand with concrete comparisons, evaluation anchors, synthesis paragraphs, and limitations from evidence packs/paper notes.",
                )
            )
        if profile == "arxiv-survey" and low_cite_density / total >= 0.2:
            issues.append(
                QualityIssue(
                    code="draft_sparse_subsection_citations",
                    message=f"Many subsections have <{min_h3_cites} unique citations ({low_cite_density}/{len(subsection_blocks)}); increase section-level evidence binding and cite density.",
                )
            )

        # Heuristic: encourage cross-paper synthesis (not per-paper summaries).
        def _cite_keys(block_text: str) -> set[str]:
            keys: set[str] = set()
            for m in re.finditer(r"\[@([^\]]+)\]", block_text):
                inside = (m.group(1) or "").strip()
                for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
                    if k:
                        keys.add(k)
            return keys

        def _has_multi_cite_paragraph(block_text: str) -> bool:
            for para in re.split(r"\n\s*\n", block_text):
                para = para.strip()
                if not para:
                    continue
                pkeys = _cite_keys(para)
                if len(pkeys) >= 2:
                    return True
            return False

        synth_total = 0
        synth_missing = 0
        for block in subsection_blocks:
            # Only enforce synthesis when a subsection cites multiple works.
            if len(_cite_keys(block)) < 3:
                continue
            synth_total += 1
            if not _has_multi_cite_paragraph(block):
                synth_missing += 1

        if synth_total and synth_missing / synth_total >= 0.4:
            issues.append(
                QualityIssue(
                    code="draft_low_cross_paper_synthesis",
                    message=(
                        "Many cite-rich subsections still read like per-paper summaries; "
                        "ensure each subsection has at least one paragraph that compares multiple works (>=2 citations in the same paragraph)."
                        f" Missing synthesis in {synth_missing}/{synth_total} subsections."
                    ),
                )
            )

    # Require Introduction + Conclusion headings.
    if not re.search(r"(?im)^##\s+(introduction|引言)\b", text):
        issues.append(QualityIssue(code="draft_missing_introduction", message="Draft is missing an `Introduction/引言` section."))
    if not re.search(r"(?im)^##\s+(conclusion|结论)\b", text):
        issues.append(QualityIssue(code="draft_missing_conclusion", message="Draft is missing a `Conclusion/结论` section."))
    if not re.search(r"(?im)^##\s+(discussion|discussion and future work|discussion & future work|讨论|讨论与未来工作|讨论与未来方向)\b", text):
        issues.append(
            QualityIssue(
                code="draft_missing_discussion",
                message="Draft is missing a `Discussion` (or `Discussion & Future Work`) section.",
            )
        )

    # Introduction should not be a few sentences only.
    intro = extract_section_body(text, heading_re=r"(?im)^##\s+(introduction|引言)\b")
    if intro is not None:
        words = len(re.findall(r"\b\w+\b", intro))
        if words and words < 180:
            issues.append(
                QualityIssue(
                    code="draft_intro_too_short",
                    message="Introduction looks too short (<~180 words); expand motivation, scope, contributions, and positioning vs. related work.",
                )
            )

    # Detect repeated long paragraphs (beyond single-line open-problems/takeaways boilerplate).
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    para_norm_counts: dict[str, int] = {}
    para_example: dict[str, str] = {}
    for para in paras:
        # Skip tables/code-ish blocks.
        if para.startswith("|") or "\n|" in para or para.startswith("```"):
            continue
        if len(para) < 220:
            continue
        norm = re.sub(r"\[@[^\]]+\]", "", para)
        norm = re.sub(r"\s+", " ", norm).strip().lower()
        if len(norm) < 180:
            continue
        para_norm_counts[norm] = para_norm_counts.get(norm, 0) + 1
        para_example.setdefault(norm, para)

    if para_norm_counts:
        top_norm, top_count = sorted(para_norm_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        if top_count >= 3:
            example = para_example.get(top_norm, "")[:140].replace("\n", " ").strip()
            issues.append(
                QualityIssue(
                    code="draft_repeated_paragraphs",
                    message=f"Draft contains repeated long paragraphs (e.g., `{example}...`); rewrite to be subsection-specific and avoid copy-paste boilerplate.",
                )
            )
    repeated = repeated_template_text(text=text, min_len=48, min_repeats=10)
    if repeated is not None:
        example, count = repeated
        issues.append(
            QualityIssue(
                code="draft_repeated_lines",
                message=f"Draft contains repeated template-like lines ({count}×), e.g., `{example}...`; rewrite to be section-specific.",
            )
        )
    repeated_sent = repeated_sentences(text=text, min_len=90, min_repeats=6)
    if repeated_sent is not None:
        example, count = repeated_sent
        issues.append(
            QualityIssue(
                code="draft_repeated_sentences",
                message=f"Draft contains repeated boilerplate sentences ({count}×), e.g., `{example}`; remove template repetition and make each subsection's thesis/comparisons specific.",
            )
        )
    return issues


def _draft_h3_cite_sets(text: str) -> dict[str, set[str]]:
    # Map `### <title>` → set(cite_keys in that H3 block).
    def _extract_keys(block: str) -> set[str]:
        keys: set[str] = set()
        for m in re.finditer(r"\[@([^\]]+)\]", block or ""):
            inside = (m.group(1) or "").strip()
            for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
                if k:
                    keys.add(k)
        return keys

    out: dict[str, set[str]] = {}
    cur_title = ""
    cur_lines: list[str] = []

    def _flush() -> None:
        nonlocal cur_title, cur_lines
        if not cur_title:
            return
        out[cur_title] = _extract_keys("\n".join(cur_lines))

    for raw in (text or "").splitlines():
        if raw.startswith("### "):
            _flush()
            cur_title = raw[4:].strip()
            cur_lines = []
            continue
        if raw.startswith("## "):
            _flush()
            cur_title = ""
            cur_lines = []
            continue
        if cur_title:
            cur_lines.append(raw)

    _flush()
    return out


def check_citation_anchoring(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    # Detect “polish drift”: citations moved across H3 subsections after polishing.
    #
    # Baseline is captured once by `draft-polisher` into:
    # - `output/citation_anchors.prepolish.jsonl`
    #
    # Policy: citations may be moved within a subsection (sentence/paragraph), but the
    # set of cite keys per H3 should not change (no cross-subsection migration).
    from tooling.common import read_jsonl

    draft_rel = outputs[0] if outputs else "output/DRAFT.md"
    baseline_rel = "output/citation_anchors.prepolish.jsonl"
    baseline_path = workspace / baseline_rel
    draft_path = workspace / draft_rel

    if not baseline_path.exists():
        return []
    if not draft_path.exists():
        return []

    baseline_records = [r for r in read_jsonl(baseline_path) if isinstance(r, dict)]
    baseline_map: dict[str, set[str]] = {}
    for rec in baseline_records:
        if str(rec.get("kind") or "").strip() != "h3":
            continue
        title = str(rec.get("title") or "").strip()
        keys = rec.get("cite_keys") or []
        if not title or not isinstance(keys, list):
            continue
        baseline_map[title] = set(str(k).strip() for k in keys if str(k).strip())

    if not baseline_map:
        return [
            QualityIssue(
                code="citation_anchors_empty",
                message=f"`{baseline_rel}` exists but has no H3 citation anchors; delete it and rerun `draft-polisher` to regenerate a baseline.",
            )
        ]

    draft_text = draft_path.read_text(encoding="utf-8", errors="ignore")
    current_map = _draft_h3_cite_sets(draft_text)

    issues: list[QualityIssue] = []
    for title, before_keys in baseline_map.items():
        after_keys = current_map.get(title)
        if after_keys is None:
            issues.append(
                QualityIssue(
                    code="citation_anchor_missing_h3",
                    message=f"After polishing, H3 heading `{title}` is missing or renamed; keep headings stable (or delete `{baseline_rel}` to reset the baseline).",
                )
            )
            continue
        if before_keys != after_keys:
            removed = sorted([k for k in before_keys if k not in after_keys])
            added = sorted([k for k in after_keys if k not in before_keys])
            sample_removed = ", ".join(removed[:6])
            sample_added = ", ".join(added[:6])
            issues.append(
                QualityIssue(
                    code="citation_anchoring_drift",
                    message=(
                        f"Citation anchoring drift in H3 `{title}`: "
                        f"removed {{{sample_removed}}}, added {{{sample_added}}}. "
                        f"Polishing must not move citations across subsections; keep cite keys in the same H3, "
                        f"or delete `{baseline_rel}` to intentionally reset."
                    ).rstrip(),
                )
            )

    return issues


def check_global_review(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    report_rel = outputs[0] if outputs else "output/GLOBAL_REVIEW.md"
    report_path = workspace / report_rel
    if not report_path.exists():
        return [QualityIssue(code="missing_global_review", message=f"`{report_rel}` does not exist.")]
    text = report_path.read_text(encoding="utf-8", errors="ignore")

    issues: list[QualityIssue] = []
    if has_placeholder_markers(text):
        issues.append(
            QualityIssue(
                code="global_review_placeholders",
                message="Global review still contains placeholder markers (TODO/TBD/FIXME/(placeholder)); fill the review and set `Status: PASS`.",
            )
        )
    if not re.search(r"(?im)^-\s*Status:\s*(PASS|OK)\b", text):
        issues.append(
            QualityIssue(
                code="global_review_status_missing",
                message="Global review should include a bullet like `- Status: PASS` once issues are addressed.",
            )
        )
    bullets = [ln for ln in text.splitlines() if ln.strip().startswith("- ")]
    if len(bullets) < 12:
        issues.append(
            QualityIssue(
                code="global_review_too_short",
                message="Global review looks too short; include top issues + glossary + ready-for-LaTeX checklist (>=12 bullets).",
            )
        )

    # Evidence-first audit sections (A–E) for writer failure modes.
    required = ["A.", "B.", "C.", "D.", "E."]
    missing = [k for k in required if not re.search(rf"(?m)^##\s+{re.escape(k)}", text)]
    if missing:
        issues.append(
            QualityIssue(
                code="global_review_missing_audit_sections",
                message=f"Global review is missing required audit sections: {', '.join(missing)} (add A–E to cover input integrity, narrative, scope, citations, and tables).",
            )
        )

    # Re-run draft checks as part of the global pass.
    issues.extend(check_draft(workspace, ["output/DRAFT.md"]))
    return issues
