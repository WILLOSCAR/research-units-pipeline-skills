from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from tooling.quality_checks.common import QualityIssue, has_placeholder_markers
from tooling.quality_checks.survey_policy import (
    draft_profile as resolve_draft_profile,
    per_subsection as resolve_per_subsection,
    pipeline_profile_name,
    quality_contract_int,
)
from tooling.quality_checks.survey_structure import (
    section_first_artifact_issues,
    section_first_cutover_issues,
    structure_mode,
)
from tooling.quality_checks.survey_text import repeated_template_text, short_description_counts


def check_taxonomy(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    import csv

    from tooling.common import candidate_keywords, load_yaml, tokenize

    out_rel = outputs[0] if outputs else "outline/taxonomy.yml"
    path = workspace / out_rel
    if path.exists():
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if has_placeholder_markers(raw):
            return [
                QualityIssue(
                    code="taxonomy_scaffold",
                    message="Taxonomy still contains placeholder/TODO text; rewrite node names/descriptions and remove TODOs.",
                )
            ]
    data = load_yaml(path) if path.exists() else None
    if not isinstance(data, list) or not data:
        return [QualityIssue(code="invalid_taxonomy", message=f"`{out_rel}` is missing or not a YAML list.")]

    nodes = list(_iter_taxonomy_nodes(data))
    if not any(node.get("children") for node in nodes if isinstance(node, dict)):
        return [QualityIssue(code="taxonomy_depth", message="Taxonomy has no `children` (needs ≥2 levels).")]

    template_desc = 0
    template_child_names = 0
    total_desc = 0
    total_child_names = 0
    desc_values: list[str] = []

    child_name_templates = {"Overview", "Representative Approaches", "Benchmarks", "Open Problems"}

    for node in nodes:
        if not isinstance(node, dict):
            continue
        desc = str(node.get("description") or "").strip()
        if desc:
            total_desc += 1
            desc_values.append(desc)
            if desc.startswith(
                (
                    "Papers and ideas centered on '",
                    "Key aspects of '",
                    "Cluster capturing work where '",
                    "Subtopic under '",
                )
            ):
                template_desc += 1
        name = str(node.get("name") or "").strip()
        if name:
            total_child_names += 1
            if name in child_name_templates:
                template_child_names += 1

    issues: list[QualityIssue] = []
    if total_desc and template_desc / total_desc >= 0.6:
        issues.append(
            QualityIssue(
                code="taxonomy_template_descriptions",
                message="Most taxonomy descriptions look auto-templated (keyword-based); rewrite with domain-meaningful categories.",
            )
        )
    if total_child_names and template_child_names / total_child_names >= 0.6:
        issues.append(
            QualityIssue(
                code="taxonomy_template_children",
                message="Many taxonomy node names look like generic placeholders (Overview/Benchmarks/Open Problems); rename to content-based subtopics.",
            )
        )

    short, denom = short_description_counts(desc_values, min_chars=32)
    if denom and short / denom >= 0.6:
        issues.append(
            QualityIssue(
                code="taxonomy_short_descriptions",
                message="Many taxonomy node descriptions are very short; expand descriptions with concrete scope cues and representative works.",
            )
        )

    core_path = workspace / "papers" / "core_set.csv"
    if core_path.exists():
        try:
            with core_path.open("r", encoding="utf-8", newline="") as handle:
                titles = [
                    str(row.get("title") or "").strip()
                    for row in csv.DictReader(handle)
                    if str(row.get("title") or "").strip()
                ]
        except Exception:
            titles = []
        core_topics = candidate_keywords(titles, top_k=6, min_freq=max(2, len(titles) // 12))
        taxonomy_tokens = set(tokenize(" ".join(
            f"{str(node.get('name') or '')} {str(node.get('description') or '')}"
            for node in nodes
            if isinstance(node, dict)
        )))
        required_overlap = min(2, len(core_topics))
        overlap = [topic for topic in core_topics if topic in taxonomy_tokens]
        if required_overlap and len(overlap) < required_overlap:
            issues.append(
                QualityIssue(
                    code="taxonomy_domain_drift",
                    message=(
                        "Taxonomy does not reflect the core-set vocabulary: "
                        f"expected at least {required_overlap} of {core_topics}, found {overlap}. "
                        "Rebuild from the current GOAL/queries/core set; do not reuse an unrelated domain pack."
                    ),
                )
            )
    return issues


def _iter_taxonomy_nodes(items: Iterable) -> Iterable[dict]:
    for item in items:
        if not isinstance(item, dict):
            continue
        yield item
        children = item.get("children") or []
        if isinstance(children, list):
            yield from _iter_taxonomy_nodes(children)


def check_outline(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_workspace_pipeline_spec, load_yaml

    out_rel = outputs[0] if outputs else "outline/outline.yml"
    path = workspace / out_rel
    if path.exists():
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if has_placeholder_markers(raw):
            return [
                QualityIssue(
                    code="outline_scaffold",
                    message="Outline still contains placeholder/TODO bullets; rewrite each subsection with topic-specific, checkable bullets.",
                )
            ]
    outline = load_yaml(path) if path.exists() else None
    if not isinstance(outline, list) or not outline:
        return [QualityIssue(code="invalid_outline", message=f"`{out_rel}` is missing or not a YAML list.")]

    section_first_issues = section_first_artifact_issues(workspace, consumer=out_rel)
    if section_first_issues:
        return section_first_issues

    template_bullets = {
        "Define problem setting and terminology",
        "Representative approaches and design choices",
        "Benchmarks / datasets / evaluation metrics",
        "Limitations and open problems",
    }
    scaffold_re = re.compile(
        r"(?i)^(?:Scope and definitions for|Design space in|Evaluation practice for|Limitations for|Connections: how)\b"
    )

    bullets_total = 0
    bullets_template = 0
    bullets_scaffold = 0
    for section in outline:
        if not isinstance(section, dict):
            continue
        for sub in section.get("subsections") or []:
            if not isinstance(sub, dict):
                continue
            for b in sub.get("bullets") or []:
                b = str(b).strip()
                if not b:
                    continue
                bullets_total += 1
                if b in template_bullets:
                    bullets_template += 1
                if scaffold_re.match(b):
                    bullets_scaffold += 1

    if bullets_total and bullets_template / bullets_total >= 0.7:
        return [
            QualityIssue(
                code="outline_template_bullets",
                message="Outline bullets are mostly generic templates; replace with specific axes, comparisons, and concrete terms for each subsection.",
            )
        ]
    if bullets_total and bullets_scaffold / bullets_total >= 0.7:
        return [
            QualityIssue(
                code="outline_scaffold_bullets",
                message=(
                    "Outline bullets still look like scaffold prompts (scope/design space/evaluation/limitations/connections). "
                    "Rewrite each subsection with concrete mechanisms, benchmarks, and comparison axes."
                ),
            )
        ]

    # Evidence-first Stage A: require verifiable subsection metadata for survey pipelines.
    profile = pipeline_profile_name(workspace)
    if profile == "arxiv-survey":
        draft_profile = resolve_draft_profile(workspace)
        missing_meta = 0
        subs_total = 0
        for section in outline:
            if not isinstance(section, dict):
                continue
            for sub in section.get("subsections") or []:
                if not isinstance(sub, dict):
                    continue
                bullets = [str(b).strip() for b in (sub.get("bullets") or []) if str(b).strip()]
                if not bullets:
                    continue
                subs_total += 1
                has_intent = any(re.match(r"(?i)^intent\s*[:：]", b) for b in bullets)
                has_rq = any(re.match(r"(?i)^(?:rq|question)\s*[:：]", b) for b in bullets)
                has_evidence = any(re.match(r"(?i)^evidence needs\s*[:：]", b) for b in bullets)
                has_expected = any(re.match(r"(?i)^expected cites\s*[:：]", b) for b in bullets)
                if not (has_intent and has_rq and has_evidence and has_expected):
                    missing_meta += 1

        # Paper-like constraint: avoid too many H2 chapters.
        # Note: the final draft adds global H2 sections (Discussion + Conclusion) via `section-merger`,
        # so the outline itself should budget fewer H2 chapters than the final ToC target.
        sec_total = 0
        for section in outline:
            if not isinstance(section, dict):
                continue
            if str(section.get("title") or "").strip():
                sec_total += 1

        extra_global_h2 = 2  # Discussion + Conclusion are appended as global sections in C5.
        max_final_h2 = quality_contract_int(
            workspace,
            keys=("structure_policy", "max_final_h2_by_profile", draft_profile),
            default={"course_paper": 7, "deep": 9}.get(draft_profile, 8),
        )
        max_outline_h2 = max(1, max_final_h2 - extra_global_h2)

        if sec_total > max_outline_h2:
            return [
                QualityIssue(
                    code="outline_too_many_sections",
                    message=(
                        f"Outline has too many top-level sections for paper-like readability ({sec_total}). "
                        f"The final draft adds Discussion+Conclusion, so this would likely render as ~{sec_total + extra_global_h2} H2 sections. "
                        f"Prefer <= {max_final_h2} final H2 sections (Intro → Related Work → 3–4 core chapters → Discussion → Conclusion). "
                        "Merge/simplify the taxonomy so each chapter is thicker and each H3 can sustain deeper evidence-first prose. "
                        "If you already have an outline but it is over-fragmented, use `outline-budgeter` (NO PROSE) to merge/simplify, then rerun `section-mapper` → `outline-refiner`."
                    ),
                )
            ]

        # Paper-like constraint: avoid fragmenting the survey into too many tiny H3s.
        max_h3 = quality_contract_int(
            workspace,
            keys=("structure_policy", "max_h3_by_profile", draft_profile),
            default={"course_paper": 6, "deep": 12}.get(draft_profile, 10),
        )

        if subs_total > max_h3:
            return [
                QualityIssue(
                    code="outline_too_many_subsections",
                    message=(
                        f"Outline has too many subsections for survey-quality writing ({subs_total}). "
                        f"Prefer <= {max_h3} H3 subsections for this draft profile (fewer, thicker sections). "
                        "Merge/simplify the taxonomy/outline so each H3 can sustain deeper evidence-first prose. "
                        "Fix (skills-first): run `outline-budgeter` (NO PROSE) to merge adjacent H3s, then rerun `section-mapper` → `outline-refiner`."
                    ),
                )
            ]

        if subs_total and missing_meta:
            return [
                QualityIssue(
                    code="outline_missing_stage_a_fields",
                    message=(
                        f"{missing_meta}/{subs_total} subsections are missing required Stage A bullets "
                        "(Intent/RQ/Evidence needs/Expected cites). Add these fields so later mapping/claims/drafting are verifiable."
                    ),
                )
            ]
    return []


def check_mapping(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_yaml, read_tsv

    out_rel = outputs[0] if outputs else "outline/mapping.tsv"
    path = workspace / out_rel
    rows = read_tsv(path)
    if not rows:
        return [QualityIssue(code="empty_mapping", message=f"`{out_rel}` has no rows.")]

    issues: list[QualityIssue] = []
    issues.extend(section_first_artifact_issues(workspace, consumer=out_rel))

    placeholder_rows = 0
    for row in rows:
        why = str(row.get("why") or "").strip()
        title = str(row.get("section_title") or "").strip()
        low = f"{why} {title}".lower()
        if "(placeholder)" in low or "placeholder" in low:
            placeholder_rows += 1
    if placeholder_rows:
        issues.append(
            QualityIssue(
                code="mapping_contains_placeholders",
                message=f"`{out_rel}` still contains placeholder rows/rationales; regenerate mapping or edit it to cover all subsections with real rationales.",
            )
        )

    low_confidence_rows = 0
    for row in rows:
        why = str(row.get("why") or "").strip().lower()
        if any(
            marker in why
            for marker in (
                "weak lexical overlap",
                "low-confidence candidate",
                "sparse explicit term overlap",
                "based on overall similarity",
            )
        ):
            low_confidence_rows += 1
    if low_confidence_rows:
        issues.append(
            QualityIssue(
                code="mapping_low_confidence",
                message=(
                    f"`{out_rel}` contains {low_confidence_rows} low-confidence mapping row(s); "
                    "expand the evidence set, refine subsection concepts, or replace them with reviewed semantic mappings."
                ),
            )
        )

    generic_why = 0
    why_total = 0
    for row in rows:
        why = str(row.get("why") or "").strip()
        if not why:
            continue
        why_total += 1
        if why.startswith(("token_overlap=", "matched_terms=")) or "matched_terms=" in why:
            generic_why += 1

    if why_total and generic_why / why_total >= 0.8:
        issues.append(
            QualityIssue(
                code="mapping_generic_rationale",
                message="Mapping rationale looks mostly token/term overlap; add brief semantic reasons (method/task/benchmark) or refine mapping manually.",
            )
        )

    outline_path = workspace / "outline" / "outline.yml"
    outline = load_yaml(outline_path) if outline_path.exists() else None
    expected: dict[str, str] = {}
    if isinstance(outline, list):
        for section in outline:
            if not isinstance(section, dict):
                continue
            for sub in section.get("subsections") or []:
                if not isinstance(sub, dict):
                    continue
                sid = str(sub.get("id") or "").strip()
                title = str(sub.get("title") or "").strip()
                if sid and title:
                    expected[sid] = title

    if expected:
        counts: dict[str, int] = {sid: 0 for sid in expected}
        unknown = 0
        title_mismatch = 0
        for row in rows:
            sid = str(row.get("section_id") or "").strip()
            if sid in counts:
                counts[sid] += 1
                want = expected.get(sid) or ""
                got = str(row.get("section_title") or "").strip()
                if want and got:
                    want_norm = re.sub(r"\s+", " ", want).strip().lower()
                    got_norm = re.sub(r"\s+", " ", got).strip().lower()
                    if want_norm != got_norm:
                        title_mismatch += 1
            else:
                unknown += 1

        profile = pipeline_profile_name(workspace)
        per_subsection = int(resolve_per_subsection(workspace)) if profile == "arxiv-survey" else 3

        ok = sum(1 for _, c in counts.items() if c >= per_subsection)
        total = max(1, len(counts))
        required_ratio = 1.0 if profile == "arxiv-survey" else 0.8
        if ok / total < required_ratio:
            low = sorted([(sid, c) for sid, c in counts.items() if c < per_subsection], key=lambda kv: (kv[1], kv[0]))
            sample = ", ".join([f"{sid}({c})" for sid, c in low[:10]])
            suffix = "..." if len(low) > 10 else ""
            issues.append(
                QualityIssue(
                    code="mapping_low_coverage",
                    message=(
                        f"Only {ok}/{len(counts)} subsections have >= {per_subsection} mapped papers; "
                        f"low-coverage examples: {sample}{suffix}. "
                        "Increase `--per-subsection` (survey default) or refine `outline/outline.yml` so each H3 can sustain evidence-first writing."
                    ),
                )
            )
        if unknown:
            issues.append(
                QualityIssue(
                    code="mapping_unknown_sections",
                    message=f"`{out_rel}` contains {unknown} row(s) with section_id not present in `outline/outline.yml`; regenerate mapping after updating outline.",
                )
            )
        if title_mismatch / max(1, len(rows)) >= 0.3:
            issues.append(
                QualityIssue(
                    code="mapping_section_title_mismatch",
                    message="Many mapping rows have section_title not matching the outline title; ensure mapping.tsv corresponds to the current outline.",
                )
            )

    # Detect a small set of papers being repeated across many unrelated subsections.
    sections: set[str] = set()
    paper_to_sections: dict[str, set[str]] = {}
    for row in rows:
        sid = str(row.get("section_id") or "").strip()
        pid = str(row.get("paper_id") or "").strip()
        if sid:
            sections.add(sid)
        if sid and pid:
            paper_to_sections.setdefault(pid, set()).add(sid)

    if sections and paper_to_sections:
        top_pid, top_secs = max(paper_to_sections.items(), key=lambda kv: len(kv[1]))
        top_count = len(top_secs)
        if resolve_draft_profile(workspace) == "course_paper":
            import math

            threshold = max(3, math.ceil(len(sections) * 0.60))
        else:
            threshold = max(6, int(len(sections) * 0.35))
        if top_count > threshold:
            issues.append(
                QualityIssue(
                    code="mapping_repeated_papers",
                    message=(
                        f"Paper `{top_pid}` appears in {top_count}/{len(sections)} subsections; "
                        "mapping likely over-reuses a few works across unrelated sections. Diversify `outline/mapping.tsv`."
                    ),
                )
            )

    return issues


def check_paper_notes(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    out_rel = outputs[0] if outputs else "papers/paper_notes.jsonl"
    path = workspace / out_rel
    notes = read_jsonl(path)
    if not notes:
        return [QualityIssue(code="empty_paper_notes", message=f"`{out_rel}` is empty.")]

    notes = [n for n in notes if isinstance(n, dict)]
    if not notes:
        return [QualityIssue(code="invalid_paper_notes", message=f"`{out_rel}` has no JSON objects.")]

    # Intentionally keep `paper-notes` gates light: this stage is allowed to be metadata/abstract-heavy.
    # Hard requirements are about integrity (coverage + minimal schema), not “note richness”.
    issues: list[QualityIssue] = []

    seen: set[str] = set()
    dupes = 0
    missing_pid = 0
    missing_title = 0
    bad_level = 0
    missing_lims = 0
    for n in notes:
        pid = str(n.get("paper_id") or "").strip()
        title = str(n.get("title") or "").strip()
        lvl = str(n.get("evidence_level") or "").strip().lower()
        lims = n.get("limitations") or []

        if not pid:
            missing_pid += 1
            continue
        if pid in seen:
            dupes += 1
        seen.add(pid)

        if not title:
            missing_title += 1
        if lvl not in {"fulltext", "abstract", "title"}:
            bad_level += 1
        if not isinstance(lims, list) or len([x for x in lims if str(x).strip()]) < 1:
            missing_lims += 1

    if missing_pid:
        issues.append(
            QualityIssue(
                code="paper_notes_missing_paper_id",
                message=f"`{out_rel}` has {missing_pid} record(s) missing `paper_id`.",
            )
        )
    if dupes:
        issues.append(
            QualityIssue(
                code="paper_notes_duplicate_paper_id",
                message=f"`{out_rel}` has duplicate `paper_id` entries ({dupes}).",
            )
        )
    if missing_title:
        issues.append(
            QualityIssue(
                code="paper_notes_missing_title",
                message=f"`{out_rel}` has {missing_title} record(s) missing `title`.",
            )
        )
    if bad_level:
        issues.append(
            QualityIssue(
                code="paper_notes_bad_evidence_level",
                message=f"`{out_rel}` has {bad_level} record(s) with invalid `evidence_level` (expected fulltext|abstract|title).",
            )
        )
    if missing_lims:
        issues.append(
            QualityIssue(
                code="paper_notes_missing_limitations",
                message=f"`{out_rel}` has {missing_lims} record(s) missing `limitations` (need at least one item).",
            )
        )

    # Coverage check against core_set.csv if present.
    core_path = workspace / "papers" / "core_set.csv"
    if core_path.exists():
        import csv

        expected: set[str] = set()
        try:
            with core_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pid = str(row.get("paper_id") or "").strip()
                    if pid:
                        expected.add(pid)
        except Exception:
            expected = set()

        if expected:
            missing = sorted([pid for pid in expected if pid not in seen])
            if missing:
                sample = ", ".join(missing[:8])
                suffix = "..." if len(missing) > 8 else ""
                issues.append(
                    QualityIssue(
                        code="paper_notes_missing_core_coverage",
                        message=f"`{out_rel}` is missing notes for some core-set papers (e.g., {sample}{suffix}).",
                    )
                )

    # Optional: evidence bank (addressable evidence items) produced alongside notes.
    if len(outputs) >= 2:
        bank_rel = outputs[1]
        bank_path = workspace / bank_rel
        bank = read_jsonl(bank_path) if bank_path.exists() else []
        bank = [b for b in bank if isinstance(b, dict)]
        if not bank_path.exists():
            issues.append(QualityIssue(code="missing_evidence_bank", message=f"`{bank_rel}` does not exist."))
        elif not bank:
            issues.append(QualityIssue(code="empty_evidence_bank", message=f"`{bank_rel}` is empty."))
        else:
            seen_eid: set[str] = set()
            dup_eid = 0
            bad_items = 0
            pids_in_bank: set[str] = set()
            for it in bank:
                eid = str(it.get("evidence_id") or "").strip()
                pid = str(it.get("paper_id") or "").strip()
                bibkey = str(it.get("bibkey") or "").strip()
                claim_type = str(it.get("claim_type") or "").strip()
                snippet = str(it.get("snippet") or "").strip()
                locator = it.get("locator")
                lvl = str(it.get("evidence_level") or "").strip()

                if not eid or not pid or not bibkey or not claim_type or not snippet or not lvl or not isinstance(locator, dict):
                    bad_items += 1
                    continue
                src = str(locator.get("source") or "").strip()
                ptr = str(locator.get("pointer") or "").strip()
                if not src or not ptr:
                    bad_items += 1
                    continue

                if eid in seen_eid:
                    dup_eid += 1
                seen_eid.add(eid)
                pids_in_bank.add(pid)

            if dup_eid:
                issues.append(QualityIssue(code="evidence_bank_duplicate_ids", message=f"`{bank_rel}` has duplicate evidence_id entries ({dup_eid})."))
            if bad_items:
                issues.append(QualityIssue(code="evidence_bank_bad_items", message=f"`{bank_rel}` has {bad_items} malformed item(s) (missing fields/locator)."))

            missing_pid = sorted([pid for pid in seen if pid not in pids_in_bank])
            if missing_pid:
                sample = ", ".join(missing_pid[:8])
                suffix = "..." if len(missing_pid) > 8 else ""
                issues.append(
                    QualityIssue(
                        code="evidence_bank_missing_papers",
                        message=f"`{bank_rel}` has no evidence items for some papers in notes (e.g., {sample}{suffix}).",
                    )
                )
            # A150++ scaling: require a denser evidence bank for arxiv-survey pipelines so later
            # binding/packs can stay in-scope without pushing the writer into hollow prose.
            if pipeline_profile_name(workspace) == "arxiv-survey":
                items_per_paper = 4 if resolve_draft_profile(workspace) == "course_paper" else 7
                min_items = max(len(seen), int(len(seen) * items_per_paper))
                if len(bank) < min_items:
                    issues.append(
                        QualityIssue(
                            code="evidence_bank_too_small",
                            message=(
                                f"`{bank_rel}` has {len(bank)} items for {len(seen)} papers; "
                                f"The `{resolve_draft_profile(workspace)}` profile expects >= {min_items} "
                                f"(>={items_per_paper} items/paper on average)."
                            ),
                        )
                    )
            else:
                if len(bank) < len(seen):
                    issues.append(
                        QualityIssue(
                            code="evidence_bank_too_small",
                            message=f"`{bank_rel}` has only {len(bank)} items for {len(seen)} papers; expect >=1 evidence item per paper on average.",
                        )
                    )

    return issues


def check_claim_evidence_matrix(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "outline/claim_evidence_matrix.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_claim_matrix", message=f"`{out_rel}` does not exist.")]

    text = path.read_text(encoding="utf-8", errors="ignore")
    if "<!-- SCAFFOLD" in text:
        return [
            QualityIssue(
                code="claim_matrix_scaffold",
                message="Claim–evidence matrix still contains scaffold markers; rewrite claims and remove the `<!-- SCAFFOLD ... -->` line.",
            )
        ]
    if re.search(r"(?i)\b(?:TODO|TBD|FIXME)\b", text):
        return [
            QualityIssue(
                code="claim_matrix_todo",
                message="Claim–evidence matrix still contains placeholder markers (TODO/TBD/FIXME); rewrite claims into specific statements and remove placeholders.",
            )
        ]
    if "…" in text or re.search(r"(?m)\.\.\.+", text):
        return [
            QualityIssue(
                code="claim_matrix_contains_ellipsis",
                message="Claim–evidence matrix contains ellipsis, which usually indicates truncated scaffold text; rewrite into concrete, checkable claims/axes.",
            )
        ]
    if re.search(r"(?i)enumerate\s+2-4", text):
        return [
            QualityIssue(
                code="claim_matrix_scaffold_instructions",
                message="Claim–evidence matrix contains scaffold instructions like 'enumerate 2-4 ...'; replace with specific mechanisms/axes grounded in the mapped papers.",
            )
        ]
    if re.search(r"(?i)\b(?:scope and definitions for|design space in|evaluation practice for)\b", text):
        return [
            QualityIssue(
                code="claim_matrix_scaffold_phrases",
                message="Claim–evidence matrix still contains outline scaffold phrases (scope/design space/evaluation practice). Rewrite claims/axes using evidence needs + paper notes, not prompt-like bullets.",
            )
        ]
    claim_lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("- Claim:")]
    if not claim_lines:
        return [QualityIssue(code="empty_claims", message="No `- Claim:` lines found in claim–evidence matrix.")]

    templ = 0
    around_template = 0
    for ln in claim_lines:
        low = ln.lower()
        if "key approaches in **" in low and "can be compared along" in low:
            templ += 1
        if "clusters around recurring themes" in low or "trade-offs tend to show up along" in low:
            templ += 1
        if ln.split("- Claim:", 1)[-1].strip().startswith("围绕 "):
            around_template += 1
    if templ / max(1, len(claim_lines)) >= 0.7:
        return [
            QualityIssue(
                code="generic_claims",
                message="Claims are mostly generic template sentences; replace with specific, falsifiable claims grounded in the mapped papers.",
            )
        ]
    if around_template / max(1, len(claim_lines)) >= 0.8:
        return [
            QualityIssue(
                code="claim_matrix_same_template",
                message="Most claims start with the same '围绕 …' template; rewrite claims to be specific (mechanism/assumption/result) per subsection.",
            )
        ]

    # Heuristic: each subsection should list >=2 evidence items.
    blocks = re.split(r"(?m)^##\s+", text)
    low_evidence = 0
    total = 0
    for block in blocks[1:]:
        if not block.strip():
            continue
        total += 1
        evidence_lines = [ln for ln in block.splitlines() if "Evidence:" in ln]
        if len(evidence_lines) < 2:
            low_evidence += 1
    if total and (low_evidence / total) >= 0.2:
        return [
            QualityIssue(
                code="claim_matrix_too_few_evidence_items",
                message=f"Many subsections have <2 evidence items in the matrix ({low_evidence}/{total}); add mapped paper IDs + cite keys per subsection before drafting.",
            )
        ]
    return []


def check_subsection_briefs(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_yaml, read_jsonl

    out_rel = outputs[0] if outputs else "outline/subsection_briefs.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_subsection_briefs", message=f"`{out_rel}` does not exist.")]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        return [QualityIssue(code="empty_subsection_briefs", message=f"`{out_rel}` is empty.")]
    if "…" in raw:
        return [
            QualityIssue(
                code="subsection_briefs_contains_ellipsis",
                message="Subsection briefs contain unicode ellipsis (`…`), which is treated as placeholder leakage; fill axes/clusters explicitly.",
            )
        ]
    if has_placeholder_markers(raw):
        return [
            QualityIssue(
                code="subsection_briefs_placeholders",
                message="Subsection briefs contain placeholder markers (TODO/TBD/FIXME/(placeholder)/SCAFFOLD); refine briefs before writing.",
            )
        ]

    records = read_jsonl(path)
    briefs = [r for r in records if isinstance(r, dict)]
    if not briefs:
        return [QualityIssue(code="invalid_subsection_briefs", message=f"`{out_rel}` has no JSON objects.")]
    cutover_issues = section_first_artifact_issues(workspace, consumer=out_rel)
    cutover_issues.extend(section_first_cutover_issues(workspace, consumer=out_rel, require_stable_h3=True))
    if cutover_issues:
        return cutover_issues

    # Check coverage against outline subsections (best-effort).
    outline_path = workspace / "outline" / "outline.yml"
    expected_ids: set[str] = set()
    if outline_path.exists():
        try:
            outline = load_yaml(outline_path) or []
            for section in outline if isinstance(outline, list) else []:
                if not isinstance(section, dict):
                    continue
                for sub in section.get("subsections") or []:
                    if not isinstance(sub, dict):
                        continue
                    sid = str(sub.get("id") or "").strip()
                    if sid:
                        expected_ids.add(sid)
        except Exception:
            expected_ids = set()

    by_id: dict[str, dict] = {}
    dupes = 0
    for rec in briefs:
        sid = str(rec.get("sub_id") or "").strip()
        if not sid:
            continue
        if sid in by_id:
            dupes += 1
        by_id[sid] = rec

    issues: list[QualityIssue] = []
    if dupes:
        issues.append(QualityIssue(code="subsection_briefs_duplicate_ids", message=f"`{out_rel}` has duplicate `sub_id` entries ({dupes})."))

    if expected_ids:
        missing = sorted([sid for sid in expected_ids if sid not in by_id])
        if missing:
            sample = ", ".join(missing[:6])
            suffix = "..." if len(missing) > 6 else ""
            issues.append(
                QualityIssue(
                    code="subsection_briefs_missing_sections",
                    message=f"Briefs missing some subsections from `outline/outline.yml` (e.g., {sample}{suffix}).",
                )
            )

    profile = pipeline_profile_name(workspace)
    # Survey default: paragraph plans must be thick enough to prevent 1–2 paragraph stubs downstream.
    min_plan_len = (6 if resolve_draft_profile(workspace) == "course_paper" else 8) if profile == "arxiv-survey" else 2

    required_top = {
        "sub_id",
        "title",
        "section_id",
        "section_title",
        "scope_rule",
        "rq",
        "thesis",
        "tension_statement",
        "evaluation_anchor_minimal",
        "axes",
        "clusters",
        "paragraph_plan",
        "evidence_level_summary",
    }
    bad = 0
    for sid, rec in by_id.items():
        missing_top = [k for k in required_top if k not in rec]
        if missing_top:
            bad += 1
            continue

        rq = str(rec.get("rq") or "").strip()
        if len(rq) < 12:
            bad += 1
            continue

        thesis = str(rec.get("thesis") or "").strip()
        if len(thesis) < 24 or has_placeholder_markers(thesis) or "…" in thesis:
            bad += 1
            continue

        tension = str(rec.get("tension_statement") or "").strip()
        if len(tension) < 24 or has_placeholder_markers(tension) or "…" in tension:
            bad += 1
            continue

        eva = rec.get("evaluation_anchor_minimal")
        if not isinstance(eva, dict):
            bad += 1
            continue
        if not all(str(eva.get(k) or "").strip() for k in ("task", "metric", "constraint")):
            bad += 1
            continue

        axes = rec.get("axes")
        if not isinstance(axes, list) or len([a for a in axes if str(a).strip()]) < 3:
            bad += 1
            continue

        scope_rule = rec.get("scope_rule")
        if not isinstance(scope_rule, dict):
            bad += 1
            continue

        clusters = rec.get("clusters")
        if not isinstance(clusters, list) or len(clusters) < 2:
            bad += 1
            continue
        cluster_ok = 0
        for c in clusters:
            if not isinstance(c, dict):
                continue
            label = str(c.get("label") or "").strip()
            pids = c.get("paper_ids") or []
            if not label or not isinstance(pids, list) or len([p for p in pids if str(p).strip()]) < 2:
                continue
            cluster_ok += 1
        if cluster_ok < 2:
            bad += 1
            continue

        plan = rec.get("paragraph_plan")
        if not isinstance(plan, list) or len(plan) < min_plan_len:
            bad += 1
            continue
        plan_ok = 0
        sample = plan[:min_plan_len] if min_plan_len > 2 else plan[:3]
        for item in sample:
            if not isinstance(item, dict):
                continue
            intent = str(item.get("intent") or "").strip()
            role = str(item.get("argument_role") or "").strip()
            connector_to_prev = str(item.get("connector_to_prev") or "").strip()
            connector_phrase = str(item.get("connector_phrase") or "").strip()
            try:
                para_no = int(item.get("para") or 0)
            except Exception:
                para_no = 0

            if not (intent and role):
                continue
            if para_no and para_no > 1:
                if not (connector_to_prev and connector_phrase):
                    continue
                # Clause-level hint only (avoid full-sentence boilerplate leaking into prose).
                if len(connector_phrase) > 140:
                    continue
                if connector_phrase.strip().endswith((".", "?", "!")):
                    continue
                words = re.findall(r"[A-Za-z0-9]+", connector_phrase)
                if len(words) > 18:
                    continue
            plan_ok += 1
        required_ok = 4 if min_plan_len >= 6 else (3 if min_plan_len >= 4 else 2)
        if plan_ok < required_ok:
            bad += 1
            continue

        ev = rec.get("evidence_level_summary")
        if not isinstance(ev, dict):
            bad += 1
            continue

    if bad:
        issues.append(
            QualityIssue(
                code="subsection_briefs_incomplete",
                message=f"`{out_rel}` has {bad} subsection brief(s) missing required fields or lacking axes/clusters/plan depth.",
            )
        )

    from tooling.common import normalize_axis_label, subsection_brief_generic_axis_norms

    generic_axis_norms = subsection_brief_generic_axis_norms()

    generic_heavy: list[str] = []
    axis_signature_to_ids: dict[tuple[str, ...], list[str]] = {}
    for sid, rec in by_id.items():
        axes = [str(a).strip() for a in (rec.get("axes") or []) if str(a).strip()]
        norm_axes = [normalize_axis_label(a) for a in axes]
        if not norm_axes:
            continue
        generic_n = sum(1 for a in norm_axes if a in generic_axis_norms)
        if len(norm_axes) >= 4 and generic_n >= 3:
            generic_heavy.append(sid)
        sig = tuple(norm_axes[:4])
        if len(sig) >= 3:
            axis_signature_to_ids.setdefault(sig, []).append(sid)

    if generic_heavy:
        issues.append(
            QualityIssue(
                code="subsection_briefs_generic_axes",
                message=(
                    f"`{out_rel}` has subsection briefs dominated by generic axes (e.g., {', '.join(generic_heavy[:8])}"
                    f"{'...' if len(generic_heavy) > 8 else ''}); add subsection-specific mechanism/protocol/risk axes before writing."
                ),
            )
        )

    repeated_axis_sets = [ids for ids in axis_signature_to_ids.values() if len(ids) >= 3]
    if repeated_axis_sets:
        sample = ", ".join(["/".join(ids[:3]) + ("..." if len(ids) > 3 else "") for ids in repeated_axis_sets[:3]])
        issues.append(
            QualityIssue(
                code="subsection_briefs_repeated_axes",
                message=(
                    f"`{out_rel}` repeats the same leading axis sets across multiple subsections (e.g., {sample}); "
                    "make axes subsection-specific so downstream packs and prose do not collapse into the same template."
                ),
            )
        )

    # Writing-quality canary: repeated tensions almost always become repeated subsection openers later.
    # Keep this check lightweight (no semantics), but block obvious duplicates in strict runs.
    if profile == "arxiv-survey":
        def _norm_sentence(s: str) -> str:
            s = re.sub(r"\[@[^\]]+\]", "", s or "")
            s = re.sub(r"\s+", " ", s).strip().lower()
            return s

        tension_to_ids: dict[str, list[str]] = {}
        for sid, rec in by_id.items():
            t = _norm_sentence(str(rec.get("tension_statement") or ""))
            if not t:
                continue
            tension_to_ids.setdefault(t, []).append(sid)
        dup_tensions = [ids for _, ids in tension_to_ids.items() if len(ids) >= 2]
        if dup_tensions:
            sample = ", ".join([",".join(ids[:3]) + ("..." if len(ids) > 3 else "") for ids in dup_tensions[:3]])
            issues.append(
                QualityIssue(
                    code="subsection_briefs_repeated_tension",
                    message=(
                        f"`{out_rel}` contains repeated `tension_statement` across subsections (e.g., {sample}). "
                        "Rewrite tensions to be subsection-specific (this prevents repeated H3 openers / generator voice in C5)."
                    ),
                )
            )

    return issues


def check_chapter_briefs(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_yaml, read_jsonl

    out_rel = outputs[0] if outputs else "outline/chapter_briefs.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_chapter_briefs", message=f"`{out_rel}` does not exist.")]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        return [QualityIssue(code="empty_chapter_briefs", message=f"`{out_rel}` is empty.")]
    if has_placeholder_markers(raw) or "…" in raw:
        return [
            QualityIssue(
                code="chapter_briefs_placeholders",
                message="Chapter briefs contain placeholder markers/ellipsis; refine throughline/key contrasts/lead plan before writing.",
            )
        ]

    records = read_jsonl(path)
    briefs = [r for r in records if isinstance(r, dict)]
    if not briefs:
        return [QualityIssue(code="invalid_chapter_briefs", message=f"`{out_rel}` has no JSON objects.")]

    outline_path = workspace / "outline" / "outline.yml"
    expected: set[str] = set()
    if outline_path.exists():
        try:
            outline = load_yaml(outline_path) or []
            if isinstance(outline, list):
                for sec in outline:
                    if not isinstance(sec, dict):
                        continue
                    sec_id = str(sec.get("id") or "").strip()
                    subs = sec.get("subsections") or []
                    if sec_id and isinstance(subs, list) and subs:
                        expected.add(sec_id)
        except Exception:
            expected = set()

    by_id: dict[str, dict] = {}
    dupes = 0
    for rec in briefs:
        sid = str(rec.get("section_id") or "").strip()
        if not sid:
            continue
        if sid in by_id:
            dupes += 1
        by_id[sid] = rec

    issues: list[QualityIssue] = []
    if dupes:
        issues.append(
            QualityIssue(
                code="chapter_briefs_duplicate_ids",
                message=f"`{out_rel}` has duplicate `section_id` entries ({dupes}).",
            )
        )

    if expected:
        missing = sorted([sid for sid in expected if sid not in by_id])
        if missing:
            sample = ", ".join(missing[:6])
            suffix = "..." if len(missing) > 6 else ""
            issues.append(
                QualityIssue(
                    code="chapter_briefs_missing_sections",
                    message=f"Chapter briefs missing some H2 sections with subsections (e.g., {sample}{suffix}).",
                )
            )

    bad = 0
    allowed_modes = {"clusters", "timeline", "tradeoff_matrix", "case_study", "tension_resolution"}
    for sid, rec in by_id.items():
        if not str(rec.get("section_title") or "").strip():
            bad += 1
            continue
        subs = rec.get("subsections")
        if not isinstance(subs, list) or not subs:
            bad += 1
            continue
        mode = str(rec.get("synthesis_mode") or "").strip()
        preview = rec.get("synthesis_preview") or []
        if mode not in allowed_modes:
            bad += 1
            continue
        if not isinstance(preview, list) or len([t for t in preview if str(t).strip()]) < 1:
            bad += 1
            continue
        throughline = rec.get("throughline")
        if not isinstance(throughline, list) or len([t for t in throughline if str(t).strip()]) < 2:
            bad += 1
            continue
        lead_plan = rec.get("lead_paragraph_plan")
        if not isinstance(lead_plan, list) or len([t for t in lead_plan if str(t).strip()]) < 2:
            bad += 1
            continue
        bridge = rec.get("bridge_terms")
        if not isinstance(bridge, list) or len([t for t in bridge if str(t).strip()]) < 3:
            bad += 1
            continue

    if bad:
        issues.append(
            QualityIssue(
                code="chapter_briefs_incomplete",
                message=f"`{out_rel}` has {bad} chapter brief(s) missing required fields (subsections/throughline/lead plan/bridge terms).",
            )
        )

    return issues


def check_coverage_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    report_rel = outputs[0] if outputs else "outline/coverage_report.md"
    state_rel = outputs[1] if len(outputs) >= 2 else "outline/outline_state.jsonl"
    reroute_rel = outputs[2] if len(outputs) >= 3 else "output/REROUTE_STATE.json"

    report_path = workspace / report_rel
    state_path = workspace / state_rel
    reroute_path = workspace / reroute_rel

    if not report_path.exists():
        return [QualityIssue(code="missing_coverage_report", message=f"`{report_rel}` does not exist.")]
    report = report_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not report:
        return [QualityIssue(code="empty_coverage_report", message=f"`{report_rel}` is empty.")]
    if has_placeholder_markers(report) or "…" in report:
        return [QualityIssue(code="coverage_report_placeholders", message=f"`{report_rel}` contains placeholders; regenerate planner report.")]
    if "| Subsection |" not in report:
        return [QualityIssue(code="coverage_report_missing_table", message=f"`{report_rel}` is missing the per-subsection table.")]

    section_only = report
    m = re.search(r"(?s)##\s+Per-subsection\s+summary\s*(.*?)\n##\s+Per-chapter\s+sizing", report)
    if m:
        section_only = m.group(1)
    row_lines = [ln.strip() for ln in section_only.splitlines() if ln.strip().startswith("|") and not ln.strip().startswith("|---")]
    evidence_zero = 0
    axes_missing = 0
    data_rows = 0
    for ln in row_lines:
        if "Subsection" in ln and "Evidence levels" in ln:
            continue
        data_rows += 1
        if "fulltext=0, abstract=0, title=0" in ln:
            evidence_zero += 1
        if re.search(r"\|\s*[—-]\s*\|", ln):
            axes_missing += 1

    # `outline-refiner` runs at C2 before paper notes / briefs exist, so zero evidence-level counts
    # and blank axis-specificity cells are expected at this stage. Those fields become actionable only
    # after C3/C4 artifacts exist and are validated by later skills.

    if not state_path.exists():
        return [QualityIssue(code="missing_outline_state", message=f"`{state_rel}` does not exist.")]
    recs = read_jsonl(state_path)
    recs = [r for r in recs if isinstance(r, dict)]
    if not recs:
        return [QualityIssue(code="empty_outline_state", message=f"`{state_rel}` has no JSON records.")]
    cutover_issues = section_first_artifact_issues(workspace, consumer=report_rel)
    cutover_issues.extend(section_first_cutover_issues(workspace, consumer=report_rel, require_stable_h3=True))
    if cutover_issues:
        return cutover_issues
    if structure_mode(workspace) == "section_first":
        if not reroute_path.exists():
            return [QualityIssue(code="missing_reroute_state", message=f"`{reroute_rel}` does not exist.")]
        try:
            reroute_state = json.loads(reroute_path.read_text(encoding="utf-8", errors="ignore") or "{}")
        except Exception as exc:
            return [QualityIssue(code="invalid_reroute_state", message=f"`{reroute_rel}` is not valid JSON ({type(exc).__name__}: {exc}).")]
        if not isinstance(reroute_state, dict):
            return [QualityIssue(code="invalid_reroute_state", message=f"`{reroute_rel}` must be a JSON object.")]
        required = {"structure_phase", "h3_status", "reroute_target", "retry_budget_remaining", "status"}
        missing = sorted(key for key in required if key not in reroute_state)
        if missing:
            return [QualityIssue(code="reroute_state_missing_fields", message=f"`{reroute_rel}` is missing required fields: {', '.join(missing)}.")]
        latest = recs[-1]
        for key in ("structure_phase", "h3_status", "reroute_target", "retry_budget_remaining"):
            if reroute_state.get(key) != latest.get(key):
                return [QualityIssue(code="reroute_state_mismatch", message=f"`{reroute_rel}` is out of sync with latest `{state_rel}` for field `{key}`.")]
    return []


def check_evidence_drafts(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    out_rel = outputs[0] if outputs else "outline/evidence_drafts.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_evidence_drafts", message=f"`{out_rel}` does not exist.")]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        return [QualityIssue(code="empty_evidence_drafts", message=f"`{out_rel}` is empty.")]
    if "…" in raw:
        return [
            QualityIssue(
                code="evidence_drafts_contains_ellipsis",
                message="Evidence drafts contain unicode ellipsis (`…`), which is treated as placeholder leakage; rewrite evidence packs explicitly.",
            )
        ]
    if has_placeholder_markers(raw):
        return [
            QualityIssue(
                code="evidence_drafts_placeholders",
                message="Evidence drafts contain placeholder markers (TODO/TBD/FIXME/(placeholder)/SCAFFOLD); fill evidence packs before writing.",
            )
        ]

    records = read_jsonl(path)
    packs = [r for r in records if isinstance(r, dict)]
    if not packs:
        return [QualityIssue(code="invalid_evidence_drafts", message=f"`{out_rel}` has no JSON objects.")]

    # Validate citation keys against ref.bib if present.
    bib_path = workspace / "citations" / "ref.bib"
    bib_keys: set[str] = set()
    if bib_path.exists():
        bib_text = bib_path.read_text(encoding="utf-8", errors="ignore")
        bib_keys = set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text))

    def _collect_keys(citations: Any) -> set[str]:
        out: set[str] = set()
        if not isinstance(citations, list):
            return out
        for c in citations:
            c = str(c or "").strip()
            if not c:
                continue
            if c.startswith("@"):
                c = c[1:]
            # Allow inline bracket form too.
            for k in re.findall(r"[A-Za-z0-9:_-]+", c):
                if k:
                    out.add(k)
        return out

    issues: list[QualityIssue] = []
    profile = pipeline_profile_name(workspace)
    draft_profile = resolve_draft_profile(workspace)
    min_comparisons = 3
    if profile == "arxiv-survey":
        thresholds = {
            "course_paper": (3, 6, 3, 3),
            "deep": (6, 14, 6, 6),
            "survey": (4, 12, 5, 5),
        }
        min_comparisons, min_snippets, min_eval, min_fail = thresholds.get(draft_profile, thresholds["survey"])
    else:
        min_snippets = 1
        min_eval = 1
        min_fail = 1

    bad = 0
    missing_bib = 0
    blocking_missing = 0
    weak_comparisons = 0
    missing_snippets = 0
    bad_snippet_prov = 0
    weak_eval = 0
    weak_fail = 0

    for pack in packs:
        sub_id = str(pack.get("sub_id") or "").strip()
        title = str(pack.get("title") or "").strip()
        if not sub_id or not title:
            bad += 1
            continue

        miss = pack.get("blocking_missing") or []
        if isinstance(miss, list) and any(str(x).strip() for x in miss):
            blocking_missing += 1
            continue

        snippets = pack.get("evidence_snippets") or []
        if not isinstance(snippets, list) or len([s for s in snippets if isinstance(s, dict) and str(s.get("text") or "").strip()]) < min_snippets:
            missing_snippets += 1
            continue
        for snip in snippets[:6]:
            if not isinstance(snip, dict):
                continue
            prov = snip.get("provenance")
            if not isinstance(prov, dict):
                bad_snippet_prov += 1
                break
            src = str(prov.get("source") or "").strip()
            ptr = str(prov.get("pointer") or "").strip()
            if not src or not ptr:
                bad_snippet_prov += 1
                break

        comps = pack.get("concrete_comparisons") or []
        if not isinstance(comps, list) or len([c for c in comps if isinstance(c, dict)]) < min_comparisons:
            weak_comparisons += 1
            continue

        required_blocks = ["definitions_setup", "claim_candidates", "concrete_comparisons", "evaluation_protocol", "failures_limitations"]
        for name in required_blocks:
            block = pack.get(name)
            if not isinstance(block, list) or not block:
                bad += 1
                break
        else:
            eval_block = pack.get("evaluation_protocol") or []
            if not isinstance(eval_block, list) or len([x for x in eval_block if isinstance(x, dict)]) < min_eval:
                weak_eval += 1
                continue
            fail_block = pack.get("failures_limitations") or []
            if not isinstance(fail_block, list) or len([x for x in fail_block if isinstance(x, dict)]) < min_fail:
                weak_fail += 1
                continue

            # Validate citations inside blocks.
            cited: set[str] = set()
            for name in required_blocks:
                for item in pack.get(name) or []:
                    if not isinstance(item, dict):
                        continue
                    cited |= _collect_keys(item.get("citations"))

            if bib_keys:
                missing = [k for k in cited if k not in bib_keys]
                if missing:
                    missing_bib += 1
                    continue

    if blocking_missing:
        issues.append(
            QualityIssue(
                code="evidence_drafts_blocking_missing",
                message=f"{blocking_missing} evidence pack(s) declare `blocking_missing`; enrich evidence (abstract/fulltext/meta) and complete packs before writing.",
            )
        )
    if missing_snippets:
        issues.append(
            QualityIssue(
                code="evidence_drafts_missing_snippets",
                message=f"{missing_snippets} evidence pack(s) have too few `evidence_snippets` (<{min_snippets}); enrich paper notes/evidence bank before writing.",
            )
        )
    if bad_snippet_prov:
        issues.append(
            QualityIssue(
                code="evidence_drafts_bad_snippet_provenance",
                message=f"{bad_snippet_prov} evidence pack(s) have evidence snippets missing provenance `source/pointer`; fix evidence-draft provenance fields.",
            )
        )
    if weak_comparisons:
        issues.append(
            QualityIssue(
                code="evidence_drafts_too_few_comparisons",
                message=f"{weak_comparisons} evidence pack(s) have <{min_comparisons} concrete comparisons; expand comparisons per subsection before writing.",
            )
        )
    if weak_eval:
        issues.append(
            QualityIssue(
                code="evidence_drafts_thin_evaluation_protocol",
                message=f"{weak_eval} evidence pack(s) have <{min_eval} evaluation protocol items; add cite-backed protocol anchors (task/metric/constraint) before writing.",
            )
        )
    if weak_fail:
        issues.append(
            QualityIssue(
                code="evidence_drafts_thin_failures_limitations",
                message=f"{weak_fail} evidence pack(s) have <{min_fail} failures/limitations items; add cite-backed caveats so prose does not overclaim.",
            )
        )
    if missing_bib:
        issues.append(
            QualityIssue(
                code="evidence_drafts_bad_citations",
                message=f"{missing_bib} evidence pack(s) cite keys missing from `citations/ref.bib`; fix citation keys or regenerate bib.",
            )
        )
    if bad:
        issues.append(
            QualityIssue(
                code="evidence_drafts_incomplete",
                message=f"`{out_rel}` has {bad} invalid pack(s) (missing required blocks or missing sub_id/title).",
            )
        )

    return issues


def check_evidence_selfloop(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    """Recompute the prewrite STOP/OK/PASS decision from current evidence artifacts."""

    from tooling.common import read_jsonl

    report_rel = next(
        (path for path in outputs if path.endswith("EVIDENCE_SELFLOOP_TODO.md")),
        "output/EVIDENCE_SELFLOOP_TODO.md",
    )
    report_path = workspace / report_rel
    if not report_path.exists() or report_path.stat().st_size == 0:
        return [
            QualityIssue(
                code="missing_evidence_selfloop_report",
                message=f"`{report_rel}` is missing or empty.",
            )
        ]

    report = report_path.read_text(encoding="utf-8", errors="ignore")
    status_match = re.search(r"(?im)^-\s*Status:\s*(PASS|OK|FAIL)\s*$", report)
    recorded_status = status_match.group(1).upper() if status_match else ""
    if not recorded_status:
        return [
            QualityIssue(
                code="evidence_selfloop_status_missing",
                message=f"`{report_rel}` must declare `- Status: PASS`, `OK`, or `FAIL`.",
            )
        ]

    required = (
        workspace / "outline" / "subsection_briefs.jsonl",
        workspace / "outline" / "evidence_bindings.jsonl",
        workspace / "outline" / "evidence_drafts.jsonl",
    )
    missing = [
        str(path.relative_to(workspace))
        for path in required
        if not path.exists() or path.stat().st_size == 0
    ]
    if missing:
        return [
            QualityIssue(
                code="evidence_selfloop_inputs_missing",
                message=f"Evidence self-loop inputs are missing or empty: {', '.join(missing)}.",
            )
        ]

    try:
        briefs = read_jsonl(workspace / "outline" / "subsection_briefs.jsonl")
        bindings = read_jsonl(workspace / "outline" / "evidence_bindings.jsonl")
        drafts = read_jsonl(workspace / "outline" / "evidence_drafts.jsonl")
    except (json.JSONDecodeError, OSError) as exc:
        return [
            QualityIssue(
                code="evidence_selfloop_inputs_invalid",
                message=f"Evidence self-loop inputs are not readable JSONL: {type(exc).__name__}: {exc}.",
            )
        ]

    def inspect_records(
        records: list[dict[str, Any]],
        *,
        list_field: str | None = None,
    ) -> tuple[set[str], list[str]]:
        ids: list[str] = []
        problems: list[str] = []
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                problems.append(f"record {index} is not an object")
                continue
            sub_id = str(record.get("sub_id") or "").strip()
            if not sub_id:
                problems.append(f"record {index} has no sub_id")
            else:
                ids.append(sub_id)
            if list_field and not isinstance(record.get(list_field), list):
                problems.append(f"{sub_id or f'record {index}'}.{list_field} is not a list")
        duplicates = sorted({sub_id for sub_id in ids if ids.count(sub_id) > 1})
        if duplicates:
            problems.append("duplicate sub_id values: " + ", ".join(duplicates))
        return set(ids), problems

    brief_ids, brief_problems = inspect_records(briefs)
    binding_ids, binding_problems = inspect_records(bindings, list_field="binding_gaps")
    draft_ids, draft_problems = inspect_records(drafts, list_field="blocking_missing")
    schema_problems = brief_problems + binding_problems + draft_problems
    if schema_problems:
        return [
            QualityIssue(
                code="evidence_selfloop_inputs_invalid",
                message="Evidence self-loop records violate their schema: " + "; ".join(schema_problems) + ".",
            )
        ]
    if not brief_ids or brief_ids != binding_ids or brief_ids != draft_ids:
        return [
            QualityIssue(
                code="evidence_selfloop_coverage_mismatch",
                message=(
                    "Subsection IDs must match exactly across briefs, bindings, and drafts; "
                    f"briefs={sorted(brief_ids)}, bindings={sorted(binding_ids)}, drafts={sorted(draft_ids)}."
                ),
            )
        ]

    blocking_count = sum(
        1
        for record in drafts
        if any(str(item or "").strip() for item in record["blocking_missing"])
    )
    gap_count = sum(
        1
        for record in bindings
        if any(str(item or "").strip() for item in record["binding_gaps"])
    )
    expected_status = "FAIL" if blocking_count else "OK" if gap_count else "PASS"
    if expected_status == "FAIL":
        return [
            QualityIssue(
                code="evidence_selfloop_blocked",
                message=(
                    f"{blocking_count} evidence pack(s) still declare `blocking_missing`; "
                    "repair C2/C3/C4 evidence before writing."
                ),
            )
        ]
    if recorded_status != expected_status:
        return [
            QualityIssue(
                code="evidence_selfloop_status_stale",
                message=(
                    f"`{report_rel}` records {recorded_status}, but current evidence requires "
                    f"{expected_status} (binding gaps={gap_count}). Rerun `evidence-selfloop`."
                ),
            )
        ]
    if expected_status == "OK":
        missing_repairs: list[str] = []
        for record in bindings:
            sub_id = str(record.get("sub_id") or "").strip()
            gaps = [str(item or "").strip() for item in record["binding_gaps"] if str(item or "").strip()]
            if not gaps:
                continue
            section_match = re.search(
                rf"(?ims)^###\s+{re.escape(sub_id)}(?:\s+[^\n]*)?$\n(?P<body>.*?)(?=^###\s+|^##\s+|\Z)",
                report,
            )
            section = section_match.group("body") if section_match else ""
            if not section:
                missing_repairs.append(f"{sub_id}: subsection TODO")
                continue
            missing_repairs.extend(
                f"{sub_id}: {gap}"
                for gap in gaps
                if gap not in section
            )
            if "Suggested fix path:" not in section or not re.search(r"\bC[34](?:/C[34])?:", section):
                missing_repairs.append(f"{sub_id}: staged Suggested fix path")
        if missing_repairs:
            return [
                QualityIssue(
                    code="evidence_selfloop_repair_plan_missing",
                    message=(
                        f"`{report_rel}` must locate each binding gap and provide its smallest C3/C4 repair path; "
                        "missing=" + "; ".join(missing_repairs[:8]) + "."
                    ),
                )
            ]
    return []


def check_anchor_sheet(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    out_rel = outputs[0] if outputs else "outline/anchor_sheet.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_anchor_sheet", message=f"`{out_rel}` does not exist.")]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        return [QualityIssue(code="empty_anchor_sheet", message=f"`{out_rel}` is empty.")]
    if has_placeholder_markers(raw) or "(placeholder)" in raw.lower():
        return [
            QualityIssue(
                code="anchor_sheet_placeholders",
                message=f"`{out_rel}` contains placeholder markers; regenerate anchors from evidence packs.",
            )
        ]

    records = read_jsonl(path)
    items = [r for r in records if isinstance(r, dict)]
    if not items:
        return [QualityIssue(code="invalid_anchor_sheet", message=f"`{out_rel}` has no JSON objects.")]

    profile = pipeline_profile_name(workspace)
    draft_profile = resolve_draft_profile(workspace)
    if profile == "arxiv-survey":
        min_anchors = {"course_paper": 6, "deep": 12}.get(draft_profile, 10)
    else:
        min_anchors = 1

    bad = 0
    empty_anchors = 0
    for rec in items:
        sub_id = str(rec.get("sub_id") or "").strip()
        title = str(rec.get("title") or "").strip()
        anchors = rec.get("anchors")
        if not sub_id or not title:
            bad += 1
            continue
        if not isinstance(anchors, list):
            bad += 1
            continue
        if not anchors:
            empty_anchors += 1
            continue
        ok = 0
        for a in anchors:
            if not isinstance(a, dict):
                continue
            if not str(a.get("text") or "").strip():
                continue
            cites = a.get("citations") or []
            if not isinstance(cites, list):
                continue
            has_key = False
            for c in cites:
                s = str(c).strip()
                if not s:
                    continue
                if s.startswith("[@") and s.endswith("]"):
                    s = s[2:-1].strip()
                if s.startswith("@"):
                    s = s[1:].strip()
                if re.search(r"[A-Za-z0-9:_-]+", s):
                    has_key = True
                    break
            if not has_key:
                continue
            ok += 1
        if ok < int(min_anchors):
            bad += 1

    issues: list[QualityIssue] = []
    if empty_anchors:
        issues.append(
            QualityIssue(
                code="anchor_sheet_empty_anchors",
                message=f"`{out_rel}` has {empty_anchors} record(s) with empty anchors; evidence packs may be too thin or anchor extraction failed.",
            )
        )
    if bad:
        issues.append(
            QualityIssue(
                code="anchor_sheet_too_few_anchors",
                message=f"`{out_rel}` has {bad} record(s) with too few cite-backed anchors (<{min_anchors}); strengthen evidence packs and regenerate anchors.",
            )
        )

    return issues


def check_schema_normalization_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/SCHEMA_NORMALIZATION_REPORT.md"
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code="missing_schema_normalization_report", message=f"`{out_rel}` is missing or empty.")]

    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_schema_normalization_report", message=f"`{out_rel}` is empty.")]
    if has_placeholder_markers(text) or "…" in text:
        return [
            QualityIssue(
                code="schema_normalization_placeholders",
                message=f"`{out_rel}` contains placeholders/ellipsis; fix upstream JSONL artifacts and rerun schema normalization.",
            )
        ]

    m = re.search(r"(?ims)^##\s+Summary\s*\n\s*-\s*Status:\s*(\w+)\b", text)
    if m:
        status = (m.group(1) or "").strip().upper()
        if status == "PASS":
            return []
        return [
            QualityIssue(
                code="schema_normalization_not_pass",
                message=f"`{out_rel}` summary status is {status} (expected PASS).",
            )
        ]

    # Fallback: accept any PASS marker if a structured Summary block is missing.
    if re.search(r"(?im)^-\s*Status:\s*PASS\b", text):
        return []

    return [
        QualityIssue(
            code="schema_normalization_not_pass",
            message=f"`{out_rel}` does not contain a PASS status; check the report and fix schema drift.",
        )
    ]


def check_writer_context_packs(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_yaml, read_jsonl

    out_rel = outputs[0] if outputs else "outline/writer_context_packs.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_writer_context_packs", message=f"`{out_rel}` does not exist.")]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        return [QualityIssue(code="empty_writer_context_packs", message=f"`{out_rel}` is empty.")]
    if has_placeholder_markers(raw) or "(placeholder)" in raw.lower():
        return [
            QualityIssue(
                code="writer_context_packs_placeholders",
                message=f"`{out_rel}` contains placeholder markers; regenerate after fixing briefs/evidence/anchors.",
            )
        ]

    records = read_jsonl(path)
    items = [r for r in records if isinstance(r, dict)]
    if not items:
        return [QualityIssue(code="invalid_writer_context_packs", message=f"`{out_rel}` has no JSON objects.")]
    cutover_issues = section_first_artifact_issues(workspace, consumer=out_rel)
    cutover_issues.extend(section_first_cutover_issues(workspace, consumer=out_rel, require_stable_h3=True))
    if cutover_issues:
        return cutover_issues

    outline_path = workspace / "outline" / "outline.yml"
    outline = load_yaml(outline_path) if outline_path.exists() else []
    expected_subs: list[str] = []
    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            for sub in sec.get("subsections") or []:
                if not isinstance(sub, dict):
                    continue
                sid = str(sub.get("id") or "").strip()
                if sid:
                    expected_subs.append(sid)
    expected = set(expected_subs)

    profile = pipeline_profile_name(workspace)
    draft_profile = resolve_draft_profile(workspace)
    if profile == "arxiv-survey":
        min_plan = 5 if draft_profile == "course_paper" else 10
    else:
        min_plan = 4

    seen: set[str] = set()
    bad = 0
    missing_rq: list[str] = []
    missing_thesis: list[str] = []
    missing_axes: list[str] = []
    short_plan: list[str] = []
    empty_anchors: list[str] = []
    sparse_anchors: list[str] = []
    sparse_comparisons: list[str] = []
    empty_eval_proto: list[str] = []
    sparse_lim_hooks: list[str] = []
    missing_allowed_bib: list[str] = []
    missing_synthesis_mode: list[str] = []
    missing_must_use: list[str] = []

    if profile == "arxiv-survey":
        per_subsection = int(resolve_per_subsection(workspace))
        if draft_profile == "course_paper":
            min_comparisons = 3
            min_lim_hooks = 2
            min_anchors = 6
        elif draft_profile == "deep":
            min_comparisons = 6
            min_lim_hooks = 3
            min_anchors = 12
        else:
            min_comparisons = 4
            min_lim_hooks = 3
            min_anchors = 10
    else:
        min_comparisons = 1
        min_lim_hooks = 1
        min_anchors = 1
        per_subsection = 0

    for rec in items:
        sub_id = str(rec.get("sub_id") or "").strip()
        title = str(rec.get("title") or "").strip()
        sec_id = str(rec.get("section_id") or "").strip()
        sec_title = str(rec.get("section_title") or "").strip()
        if not sub_id or not title or not sec_id or not sec_title:
            bad += 1
            continue
        if expected and sub_id not in expected:
            bad += 1
            continue
        if sub_id in seen:
            bad += 1
            continue
        seen.add(sub_id)

        rq = str(rec.get("rq") or "").strip()
        thesis = str(rec.get("thesis") or "").strip()
        axes = rec.get("axes") or []
        plan = rec.get("paragraph_plan") or []
        if not rq:
            missing_rq.append(sub_id)
        if not thesis:
            missing_thesis.append(sub_id)
        if not isinstance(axes, list) or not any(str(a).strip() for a in axes):
            missing_axes.append(sub_id)
        if not isinstance(plan, list) or len([p for p in plan if str(p).strip()]) < min_plan:
            short_plan.append(sub_id)

        anchors = rec.get("anchor_facts") or []
        if not isinstance(anchors, list) or len([a for a in anchors if isinstance(a, dict) and str(a.get("text") or "").strip()]) < min_anchors:
            sparse_anchors.append(sub_id)

        comps = rec.get("comparison_cards") or []
        if not isinstance(comps, list) or len([c for c in comps if isinstance(c, dict)]) < min_comparisons:
            sparse_comparisons.append(sub_id)

        eval_proto = rec.get("evaluation_protocol") or []
        if not isinstance(eval_proto, list) or not eval_proto:
            empty_eval_proto.append(sub_id)

        lim_hooks = rec.get("limitation_hooks") or []
        if not isinstance(lim_hooks, list) or len([l for l in lim_hooks if isinstance(l, dict) and str(l.get("excerpt") or l.get("text") or "").strip()]) < min_lim_hooks:
            sparse_lim_hooks.append(sub_id)

        allowed = rec.get("allowed_bibkeys_mapped") or []
        allowed_count = len([k for k in allowed if str(k).strip()]) if isinstance(allowed, list) else 0
        if profile == "arxiv-survey":
            if allowed_count < int(per_subsection):
                missing_allowed_bib.append(sub_id)
        elif allowed_count < 1:
            missing_allowed_bib.append(sub_id)

        mode = str(rec.get("chapter_synthesis_mode") or "").strip()
        if profile == "arxiv-survey" and not mode:
            missing_synthesis_mode.append(sub_id)

        mu = rec.get("must_use")
        if profile == "arxiv-survey" and not isinstance(mu, dict):
            missing_must_use.append(sub_id)

    issues: list[QualityIssue] = []
    if expected and seen != expected:
        missing = sorted([sid for sid in expected if sid not in seen])
        extra = sorted([sid for sid in seen if sid not in expected])
        msg_parts = []
        if missing:
            msg_parts.append(f"missing: {', '.join(missing[:6])}{'...' if len(missing) > 6 else ''}")
        if extra:
            msg_parts.append(f"extra: {', '.join(extra[:6])}{'...' if len(extra) > 6 else ''}")
        issues.append(
            QualityIssue(
                code="writer_context_packs_outline_mismatch",
                message=f"`{out_rel}` does not match outline H3 set ({'; '.join(msg_parts) or 'mismatch'}).",
            )
        )
    if bad:
        issues.append(
            QualityIssue(
                code="writer_context_packs_invalid_records",
                message=f"`{out_rel}` has {bad} invalid record(s) (missing ids/titles, duplicate sub_id, or not in outline).",
            )
        )

    total = max(1, len(items))
    if missing_rq:
        issues.append(
            QualityIssue(
                code="writer_context_packs_missing_rq",
                message=(
                    f"`{out_rel}` has {len(missing_rq)}/{len(items)} record(s) with empty `rq` "
                    f"(e.g., {', '.join(missing_rq[:10])}{'...' if len(missing_rq) > 10 else ''}); "
                    "fix `subsection-briefs` and regenerate."
                ),
            )
        )
    if missing_thesis and profile == "arxiv-survey":
        issues.append(
            QualityIssue(
                code="writer_context_packs_missing_thesis",
                message=(
                    f"`{out_rel}` has {len(missing_thesis)}/{len(items)} record(s) with empty `thesis` "
                    f"(e.g., {', '.join(missing_thesis[:10])}{'...' if len(missing_thesis) > 10 else ''}); "
                    "fix `subsection-briefs` and regenerate so C5 has a central claim per H3."
                ),
            )
        )
    if missing_axes:
        issues.append(
            QualityIssue(
                code="writer_context_packs_missing_axes",
                message=(
                    f"`{out_rel}` has {len(missing_axes)}/{len(items)} record(s) with empty `axes` "
                    f"(e.g., {', '.join(missing_axes[:10])}{'...' if len(missing_axes) > 10 else ''}); "
                    "fix `subsection-briefs` and regenerate."
                ),
            )
        )
    if short_plan:
        issues.append(
            QualityIssue(
                code="writer_context_packs_short_plan",
                message=(
                    f"`{out_rel}` has {len(short_plan)}/{len(items)} record(s) with too-short `paragraph_plan` (<{min_plan}) "
                    f"(e.g., {', '.join(short_plan[:10])}{'...' if len(short_plan) > 10 else ''}); "
                    "fix `subsection-briefs` and regenerate."
                ),
            )
        )

    if missing_synthesis_mode and profile == "arxiv-survey":
        issues.append(
            QualityIssue(
                code="writer_context_packs_missing_chapter_synthesis_mode",
                message=(
                    f"Some writer context packs are missing `chapter_synthesis_mode` ({len(missing_synthesis_mode)}/{len(items)}) "
                    f"(e.g., {', '.join(missing_synthesis_mode[:10])}{'...' if len(missing_synthesis_mode) > 10 else ''}); "
                    "fix `chapter-briefs` and regenerate."
                ),
            )
        )

    if missing_must_use and profile == "arxiv-survey":
        issues.append(
            QualityIssue(
                code="writer_context_packs_missing_must_use",
                message=(
                    f"Some writer context packs are missing `must_use` contract ({len(missing_must_use)}/{len(items)}) "
                    f"(e.g., {', '.join(missing_must_use[:10])}{'...' if len(missing_must_use) > 10 else ''}); "
                    "regenerate `writer-context-pack` so C5 has explicit minima (anchors/comparisons/limitations)."
                ),
            )
        )

    # Per-subsection sanity: missing anchors/comparisons makes drafting hollow.
    if sparse_anchors and profile == "arxiv-survey":
        issues.append(
            QualityIssue(
                code="writer_context_packs_sparse_anchors",
                message=(
                    f"Some writer context packs have too few `anchor_facts` (<{min_anchors}) ({len(sparse_anchors)}/{len(items)}) "
                    f"(e.g., {', '.join(sparse_anchors[:10])}{'...' if len(sparse_anchors) > 10 else ''}); "
                    "strengthen `anchor-sheet` / evidence packs before drafting."
                ),
            )
        )
    if sparse_comparisons and profile == "arxiv-survey":
        issues.append(
            QualityIssue(
                code="writer_context_packs_sparse_comparisons",
                message=(
                    f"Some writer context packs have too few `comparison_cards` (<{min_comparisons}) ({len(sparse_comparisons)}/{len(items)}) "
                    f"(e.g., {', '.join(sparse_comparisons[:10])}{'...' if len(sparse_comparisons) > 10 else ''}); "
                    "strengthen `evidence-draft` excerpt-level comparisons (with citations) before drafting."
                ),
            )
        )
    if empty_eval_proto and profile == "arxiv-survey":
        issues.append(
            QualityIssue(
                code="writer_context_packs_missing_eval_protocol",
                message=(
                    f"Some writer context packs lack `evaluation_protocol` ({len(empty_eval_proto)}/{len(items)}) "
                    f"(e.g., {', '.join(empty_eval_proto[:10])}{'...' if len(empty_eval_proto) > 10 else ''}); "
                    "ensure each subsection has at least one cite-backed evaluation anchor in `evidence-draft`."
                ),
            )
        )
    if sparse_lim_hooks and profile == "arxiv-survey":
        issues.append(
            QualityIssue(
                code="writer_context_packs_missing_limitation_hooks",
                message=(
                    f"Some writer context packs have too few `limitation_hooks` (<{min_lim_hooks}) ({len(sparse_lim_hooks)}/{len(items)}) "
                    f"(e.g., {', '.join(sparse_lim_hooks[:10])}{'...' if len(sparse_lim_hooks) > 10 else ''}); "
                    "ensure each subsection has cite-backed limitations/failure modes in `evidence-draft` / `anchor-sheet`."
                ),
            )
        )
    if missing_allowed_bib and profile == "arxiv-survey":
        issues.append(
            QualityIssue(
                code="writer_context_packs_missing_allowed_bibkeys",
                message=(
                    f"Some writer context packs have too few `allowed_bibkeys_mapped` (<{per_subsection}) ({len(missing_allowed_bib)}/{len(items)}) "
                    f"(e.g., {', '.join(missing_allowed_bib[:10])}{'...' if len(missing_allowed_bib) > 10 else ''}); "
                    "fix `section-mapper` / `evidence-binder` so each subsection has in-scope citations."
                ),
            )
        )

    # Keep a soft heuristic for non-survey profiles.
    if profile != "arxiv-survey":
        if (len(sparse_anchors) / total) >= 0.5:
            issues.append(
                QualityIssue(
                    code="writer_context_packs_sparse_anchors",
                    message=f"Many writer context packs lack `anchor_facts` ({len(sparse_anchors)}/{len(items)}); strengthen `anchor-sheet` / evidence packs before drafting.",
                )
            )
        if (len(sparse_comparisons) / total) >= 0.5:
            issues.append(
                QualityIssue(
                    code="writer_context_packs_sparse_comparisons",
                    message=f"Many writer context packs lack `comparison_cards` ({len(sparse_comparisons)}/{len(items)}); strengthen `evidence-draft` concrete comparisons before drafting.",
                )
            )

    return issues


def check_evidence_bindings(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_yaml, read_jsonl

    out_rel = outputs[0] if outputs else "outline/evidence_bindings.jsonl"
    report_rel = outputs[1] if len(outputs) >= 2 else "outline/evidence_binding_report.md"

    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_evidence_bindings", message=f"`{out_rel}` does not exist.")]
    raw = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        return [QualityIssue(code="empty_evidence_bindings", message=f"`{out_rel}` is empty.")]
    if has_placeholder_markers(raw) or "…" in raw:
        return [QualityIssue(code="evidence_bindings_placeholders", message=f"`{out_rel}` contains placeholders; regenerate evidence bindings.")]

    records = read_jsonl(path)
    binds = [r for r in records if isinstance(r, dict)]
    if not binds:
        return [QualityIssue(code="invalid_evidence_bindings", message=f"`{out_rel}` has no JSON objects.")]

    by_sub = {str(r.get("sub_id") or "").strip(): r for r in binds if str(r.get("sub_id") or "").strip()}

    # Coverage against outline subsections (best-effort).
    expected: set[str] = set()
    outline_path = workspace / "outline" / "outline.yml"
    if outline_path.exists():
        outline = load_yaml(outline_path) or []
        for sec in outline if isinstance(outline, list) else []:
            if not isinstance(sec, dict):
                continue
            for sub in sec.get("subsections") or []:
                if not isinstance(sub, dict):
                    continue
                sid = str(sub.get("id") or "").strip()
                if sid:
                    expected.add(sid)
    if expected:
        missing = sorted([sid for sid in expected if sid not in by_sub])
        if missing:
            sample = ", ".join(missing[:6])
            suffix = "..." if len(missing) > 6 else ""
            return [QualityIssue(code="evidence_bindings_missing_sections", message=f"`{out_rel}` missing some subsections (e.g., {sample}{suffix}).")]

    # Evidence IDs must exist in the bank if present.
    bank_path = workspace / "papers" / "evidence_bank.jsonl"
    bank_ids: set[str] = set()
    if bank_path.exists():
        for it in read_jsonl(bank_path):
            if isinstance(it, dict):
                eid = str(it.get("evidence_id") or "").strip()
                if eid:
                    bank_ids.add(eid)

    profile = pipeline_profile_name(workspace)
    draft_profile = resolve_draft_profile(workspace)
    per_subsection = int(resolve_per_subsection(workspace)) if profile == "arxiv-survey" else 0
    # A150++ expectation: with wide per-H3 mapping, bindings should keep most of that breadth,
    # and select a solid subset of usable bibkeys plus enough evidence IDs to write concretely.
    min_mapped = per_subsection if per_subsection else 0
    if profile == "arxiv-survey" and draft_profile == "course_paper":
        min_ids = max(6, per_subsection - 2) if per_subsection else 6
        min_selected = max(6, int(round(per_subsection * 0.70))) if per_subsection else 6
        min_distinct_papers = max(4, int(min_ids) - 2)
    else:
        min_ids = max(10, per_subsection - 4) if per_subsection else (10 if profile == "arxiv-survey" else 6)
        min_selected = max(12, int(round(per_subsection * 0.70))) if per_subsection else (12 if profile == "arxiv-survey" else 6)
        min_distinct_papers = max(10, int(min_ids) - 6) if profile == "arxiv-survey" else 0

    bad = 0
    missing_bank = 0
    bad_samples: list[str] = []
    for sid, rec in by_sub.items():
        title = str(rec.get("title") or "").strip()
        eids = rec.get("evidence_ids") or []
        eid_count = len([e for e in eids if str(e).strip()]) if isinstance(eids, list) else 0
        mapped = rec.get("mapped_bibkeys") or []
        mapped_count = len([k for k in mapped if str(k).strip()]) if isinstance(mapped, list) else 0
        selected = rec.get("bibkeys") or []
        selected_count = len([k for k in selected if str(k).strip()]) if isinstance(selected, list) else 0

        # Prefer explicit paper_ids when present; otherwise fall back to parsing evidence_id prefixes.
        paper_ids = rec.get("paper_ids") or []
        pids = set([str(p).strip() for p in paper_ids if str(p).strip()]) if isinstance(paper_ids, list) else set()
        if isinstance(eids, list):
            for e in eids:
                m = re.match(r"^E-(P\\d+)-", str(e or "").strip())
                if m:
                    pids.add(m.group(1))

        if (
            not title
            or not isinstance(eids, list)
            or eid_count < int(min_ids)
            or (min_mapped and mapped_count < int(min_mapped))
            or (min_selected and selected_count < int(min_selected))
            or (min_distinct_papers and len(pids) < int(min_distinct_papers))
        ):
            bad += 1
            bad_samples.append(
                f"{sid}(eids={eid_count}, mapped={mapped_count}, selected={selected_count}, papers={len(pids)})"
            )
            continue
        if bank_ids and any(str(e).strip() and str(e).strip() not in bank_ids for e in eids):
            missing_bank += 1

    if bad:
        bad_samples.sort()
        sample = ", ".join(bad_samples[:8])
        suffix = "..." if len(bad_samples) > 10 else ""
        return [
            QualityIssue(
                code="evidence_bindings_incomplete",
                message=(
                    f"`{out_rel}` has {bad} record(s) failing binding density (need mapped>={min_mapped}, "
                    f"selected>={min_selected}, evidence_ids>={min_ids}, distinct_papers>={min_distinct_papers}). "
                    f"Examples: {sample}{suffix}. "
                    "Fix mapping (breadth/diversity) and rerun binder; do not rely on prose to compensate for thin bindings."
                ),
            )
        ]
    if missing_bank:
        return [QualityIssue(code="evidence_bindings_missing_bank_ids", message=f"`{out_rel}` references evidence_ids not found in `papers/evidence_bank.jsonl` ({missing_bank} subsection(s)).")]

    # Optional human-facing summary file.
    report_path = workspace / report_rel
    if report_path.exists():
        report = report_path.read_text(encoding="utf-8", errors="ignore").strip()
        if report and (has_placeholder_markers(report) or "…" in report):
            return [QualityIssue(code="evidence_binding_report_placeholders", message=f"`{report_rel}` contains placeholders; regenerate binder report.")]

    return []


def check_survey_visuals(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    # Backward compatible:
    # - legacy: outputs = tables + timeline + figures
    # - v4: outputs = timeline + figures (tables handled by `table-filler`)
    tables_rel: str | None
    timeline_rel: str
    figures_rel: str
    if outputs and len(outputs) == 2:
        tables_rel = None
        timeline_rel = outputs[0]
        figures_rel = outputs[1]
    else:
        tables_rel = outputs[0] if outputs else "outline/tables_index.md"
        timeline_rel = outputs[1] if len(outputs) >= 2 else "outline/timeline.md"
        figures_rel = outputs[2] if len(outputs) >= 3 else "outline/figures.md"

    issues: list[QualityIssue] = []

    def _read(rel: str) -> str | None:
        path = workspace / rel
        if not path.exists():
            issues.append(QualityIssue(code="missing_visuals_file", message=f"`{rel}` does not exist."))
            return None
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            issues.append(QualityIssue(code="empty_visuals_file", message=f"`{rel}` is empty."))
            return None
        if "<!-- SCAFFOLD" in text:
            issues.append(QualityIssue(code="visuals_scaffold", message=f"`{rel}` still contains scaffold markers."))
        if re.search(r"(?i)\b(?:TODO|TBD|FIXME)\b", text):
            issues.append(QualityIssue(code="visuals_todo", message=f"`{rel}` still contains placeholder markers (TODO/TBD/FIXME)."))
        if "…" in text:
            issues.append(
                QualityIssue(
                    code="visuals_contains_ellipsis",
                    message=f"`{rel}` contains unicode ellipsis (`…`), which usually indicates truncated scaffold text; rewrite into concrete table/timeline/figure content.",
                )
            )
        if re.search(r"\[@(?:Key|KEY)\d+", text):
            issues.append(QualityIssue(code="visuals_placeholder_cites", message=f"`{rel}` contains placeholder cite keys like `[@Key1]`."))
        return text

    tables = _read(tables_rel) if tables_rel is not None else None
    timeline = _read(timeline_rel)
    figures = _read(figures_rel)

    if tables is not None:
        table_seps = re.findall(r"(?m)^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", tables)
        if len(table_seps) < 2:
            issues.append(
                QualityIssue(
                    code="visuals_missing_tables",
                    message=f"`{tables_rel}` should contain at least 2 Markdown tables (found {len(table_seps)}).",
                )
            )
        if "[@" not in tables:
            issues.append(
                QualityIssue(
                    code="visuals_tables_no_cites",
                    message=f"`{tables_rel}` should include citations in table rows (e.g., `[@BibKey]`).",
                )
            )

    if timeline is not None:
        bullets = [ln.strip() for ln in timeline.splitlines() if ln.strip().startswith("- ")]
        year_bullets = [ln for ln in bullets if re.search(r"\b20\d{2}\b", ln)]
        cited = [ln for ln in year_bullets if "[@" in ln]
        if len(year_bullets) < 8:
            issues.append(
                QualityIssue(
                    code="visuals_timeline_too_short",
                    message=f"`{timeline_rel}` should include >=8 year bullets (found {len(year_bullets)}).",
                )
            )
        if year_bullets and len(cited) / len(year_bullets) < 0.8:
            issues.append(
                QualityIssue(
                    code="visuals_timeline_sparse_cites",
                    message=f"Most timeline bullets should include citations (>=80%); currently {len(cited)}/{len(year_bullets)}.",
                )
            )

    if figures is not None:
        fig_lines = [ln.strip() for ln in figures.splitlines() if ln.strip().lower().startswith(("- figure", "- fig"))]
        if len(fig_lines) < 2:
            issues.append(
                QualityIssue(
                    code="visuals_missing_figures",
                    message=f"`{figures_rel}` should include >=2 figure specs (lines starting with `- Figure ...`).",
                )
            )
        if "[@" not in figures:
            issues.append(
                QualityIssue(
                    code="visuals_figures_no_cites",
                    message=f"`{figures_rel}` should mention supporting works with citations (e.g., `[@BibKey]`).",
                )
            )

    return issues


def check_table_schema(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "outline/table_schema.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_table_schema", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_table_schema", message=f"`{out_rel}` is empty.")]
    if has_placeholder_markers(text) or "…" in text:
        return [QualityIssue(code="table_schema_placeholders", message=f"`{out_rel}` contains placeholders; fill schema with real table definitions.")]
    n = len(re.findall(r"(?m)^##\s+Table\s+[IA]\d+:", text))
    min_tables = 2 if resolve_draft_profile(workspace) == "course_paper" else 4
    if n < min_tables:
        return [QualityIssue(code="table_schema_too_few", message=f"`{out_rel}` should define >={min_tables} tables across the index and Appendix layers (found {n}).")]
    return []


def check_tables_index(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "outline/tables_index.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_tables_md", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_tables_md", message=f"`{out_rel}` is empty.")]
    if has_placeholder_markers(text) or "…" in text or re.search(r"(?m)\.\.\.+", text):
        return [
            QualityIssue(
                code="tables_placeholders",
                message=f"`{out_rel}` contains placeholders/ellipsis (including `...` truncation); fill tables from evidence packs and remove truncation markers.",
            )
        ]
    table_seps = re.findall(r"(?m)^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", text)
    min_tables = 1 if resolve_draft_profile(workspace) == "course_paper" else 2
    if len(table_seps) < min_tables:
        return [QualityIssue(code="tables_missing", message=f"`{out_rel}` should contain >={min_tables} Markdown tables (found {len(table_seps)}).")]
    if "[@" not in text:
        return [QualityIssue(code="tables_no_cites", message=f"`{out_rel}` should include citations in table rows (e.g., `[@BibKey]`).")]
    if re.search(r"\[@(?:Key|KEY)\d+", text):
        return [QualityIssue(code="tables_placeholder_cites", message=f"`{out_rel}` contains placeholder cite keys like `[@Key1]`.")]
    return []


def check_tables_appendix(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "outline/tables_appendix.md"
    expected_report = any(p.endswith("TABLES_APPENDIX_REPORT.md") for p in (outputs or []))
    report_rel = next((p for p in outputs if p.endswith("TABLES_APPENDIX_REPORT.md")), "output/TABLES_APPENDIX_REPORT.md")
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_tables_appendix", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_tables_appendix", message=f"`{out_rel}` is empty.")]
    if has_placeholder_markers(text) or "…" in text or re.search(r"(?m)\.\.\.+", text):
        return [
            QualityIssue(
                code="tables_appendix_placeholders",
                message=f"`{out_rel}` contains placeholders/ellipsis (including `...` truncation); curate clean Appendix tables and remove truncation markers.",
            )
        ]
    if any(ln.lstrip().startswith("#") for ln in text.splitlines() if ln.strip()):
        return [
            QualityIssue(
                code="tables_appendix_contains_headings",
                message=f"`{out_rel}` should not contain Markdown headings; keep it heading-free so the merger can insert it cleanly under a single Appendix heading.",
            )
        ]
    table_seps = re.findall(r"(?m)^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", text)
    min_tables = 1 if resolve_draft_profile(workspace) == "course_paper" else 2
    if len(table_seps) < min_tables:
        return [QualityIssue(code="tables_appendix_missing", message=f"`{out_rel}` should contain >={min_tables} Markdown tables (found {len(table_seps)}).")]
    if "[@" not in text:
        return [QualityIssue(code="tables_appendix_no_cites", message=f"`{out_rel}` should include citations in table rows (e.g., `[@BibKey]`).")]
    if re.search(r"\[@(?:Key|KEY)\d+", text):
        return [QualityIssue(code="tables_appendix_placeholder_cites", message=f"`{out_rel}` contains placeholder cite keys like `[@Key1]`.")]
    # Heuristic: if it looks like a subsection/axes index dump, block it (appendix tables should be reader-facing).
    if re.search(r"(?im)^\|\s*subsection\s*\|", text) and re.search(r"(?im)\|\s*axes\s*\|", text):
        return [
            QualityIssue(
                code="tables_appendix_looks_indexy",
                message=f"`{out_rel}` looks like an internal subsection/axes index table; curate reader-facing Appendix tables (methods/benchmarks/risks) instead of pasting the index.",
            )
        ]

    report_path = workspace / report_rel
    if expected_report:
        if not report_path.exists() or report_path.stat().st_size == 0:
            return [QualityIssue(code="missing_tables_appendix_report", message=f"`{report_rel}` is missing or empty.")]
        rep = report_path.read_text(encoding="utf-8", errors="ignore")
        if "- Status: PASS" not in rep:
            return [QualityIssue(code="tables_appendix_report_not_pass", message=f"`{report_rel}` is not PASS; fix Appendix tables and rerun `appendix-table-writer`.")]
    return []


def check_transitions(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "outline/transitions.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_transitions", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_transitions", message=f"`{out_rel}` is empty.")]
    if has_placeholder_markers(text) or "…" in text:
        return [QualityIssue(code="transitions_placeholders", message=f"`{out_rel}` contains placeholders; rewrite transitions into concrete, title/RQ-driven sentences.")]

    # Planner-talk leakage: transitions are injected into the draft body, so meta construction notes are high-impact.
    banned: list[tuple[str, str]] = [
        (r"(?i)\bafter\b[^\n]{0,180}\bmakes\s+the\s+bridge\s+explicit\s+via\b", "transitions_planner_talk_after_via"),
        (r"(?i)\bfollows\s+naturally\s+by\s+turning\b", "transitions_planner_talk_turning"),
        (r"(?i)\bthe\s+remaining\s+uncertainty\s+is\b", "transitions_planner_talk_remaining_uncertainty"),
        (r"(?i)\bto\s+keep\s+the\s+chapter(?:'|’)?s\b", "transitions_planner_talk_keep_chapter"),
    ]
    for pat, code in banned:
        if re.search(pat, text):
            return [
                QualityIssue(
                    code=code,
                    message=(
                        f"`{out_rel}` contains planner-talk transition phrasing ({code}); "
                        "rewrite transitions into content argument bridges (no construction notes)."
                    ),
                )
            ]

    # Avoid semicolon enumeration: it reads like a planning note once merged into the paper body.
    if re.search(r"(?m)^-\s+[^:\n]{1,80}:\s+[^\n]*;\s*[^\n]+", text):
        return [
            QualityIssue(
                code="transitions_semicolon_enumeration",
                message=(
                    f"`{out_rel}` contains semicolon-style enumerations; "
                    "rewrite each transition as a single content sentence (no list-like construction notes)."
                ),
            )
        ]

    # Slash-list axis markers (A / B / C) read like planning notes once injected into the draft.
    # We only block the high-signal triple-token form to avoid over-constraining legitimate terms.
    if re.search(
        r"\b[A-Za-z][A-Za-z0-9_-]{1,18}\s*/\s*[A-Za-z][A-Za-z0-9_-]{1,18}\s*/\s*[A-Za-z][A-Za-z0-9_-]{1,18}\b",
        text,
    ):
        return [
            QualityIssue(
                code="transitions_slash_list_axes",
                message=(
                    f"`{out_rel}` contains slash-list axis markers (A/B/C); "
                    "rewrite into natural prose (use 'and/or', avoid axis-label strings)."
                ),
            )
        ]

    # Transitions must not introduce citations.
    if "[@" in text:
        return [
            QualityIssue(
                code="transitions_has_citations",
                message=f"`{out_rel}` contains citation markers; transitions must not introduce new citations.",
            )
        ]
    if re.search(r"(?i)\bwhat\s+are\s+the\s+main\s+approaches\b", text):
        return [
            QualityIssue(
                code="transitions_scaffold_questions",
                message=(
                    f"`{out_rel}` contains template RQ phrasing ('What are the main approaches...'); "
                    "rewrite transitions into short, paper-like handoffs (no explicit RQ questions)."
                ),
            )
        ]
    bullets = [ln for ln in text.splitlines() if ln.strip().startswith("- ")]

    # Minimum transition coverage should match what will actually be injected by `section-merger`:
    # by default, only within-chapter H3->H3 transitions are inserted.
    #
    # Compute the expected number of within-chapter H3 transitions from `outline/outline.yml`
    # (sum over chapters: max(0, #H3-1)). This avoids forcing users to pad unrelated bullets.
    expected_h3 = 0
    try:
        from tooling.common import load_yaml

        outline_path = workspace / "outline" / "outline.yml"
        if outline_path.exists():
            outline = load_yaml(outline_path)
            if isinstance(outline, list):
                for sec in outline:
                    if not isinstance(sec, dict):
                        continue
                    subs = sec.get("subsections") or []
                    if isinstance(subs, list) and len(subs) >= 2:
                        expected_h3 += (len(subs) - 1)
    except Exception:
        expected_h3 = 0

    # Count only the H3->H3 transition bullets (these are the default injection format).
    h3_bullets = [
        ln
        for ln in bullets
        if re.search(r"^\-\s*\d+\.\d+\s*(?:→|->)\s*\d+\.\d+\s*:", ln.strip())
    ]

    if expected_h3 and len(h3_bullets) < expected_h3:
        return [
            QualityIssue(
                code="transitions_too_short",
                message=(
                    f"`{out_rel}` has too few within-chapter H3→H3 transitions "
                    f"(found={len(h3_bullets)}, expected>={expected_h3} from `outline/outline.yml`)."
                ),
            )
        ]
    rep = repeated_template_text(text=text, min_len=60, min_repeats=8)
    if rep:
        example, count = rep
        return [
            QualityIssue(
                code="transitions_repeated_text",
                message=f"`{out_rel}` contains repeated transition boilerplate ({count}×), e.g., `{example}`; rewrite to be more subsection-specific.",
            )
        ]
    return []
