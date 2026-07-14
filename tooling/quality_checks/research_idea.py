from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

from tooling.quality_checks.common import QualityIssue, has_placeholder_markers


def check_idea_brief(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    brief_rel = next(
        (path for path in outputs if path.endswith("IDEA_BRIEF.md")),
        "output/trace/IDEA_BRIEF.md",
    )
    brief_path = workspace / brief_rel
    if not brief_path.exists() or brief_path.stat().st_size == 0:
        return [QualityIssue(code="missing_idea_brief", message=f"`{brief_rel}` is missing or empty.")]

    repo_root = Path(__file__).resolve().parents[2]
    contract_path = repo_root / ".codex" / "skills" / "idea-brief" / "assets" / "brief_contract.json"
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        sections = contract.get("required_sections")
        if not isinstance(sections, list) or not sections:
            raise ValueError("required_sections is missing or empty")
        required = [
            f"## {str(section or '').strip()}"
            for section in sections
            if str(section or "").strip()
        ]
    except Exception as exc:
        return [
            QualityIssue(
                code="idea_brief_contract_unreadable",
                message=f"Failed to load `idea-brief` contract asset ({type(exc).__name__}: {exc}).",
            )
        ]

    text = brief_path.read_text(encoding="utf-8", errors="ignore")
    missing = [heading for heading in required if heading not in text]
    if missing:
        return [
            QualityIssue(
                code="idea_brief_missing_sections",
                message=f"`{brief_rel}` is missing required sections: {', '.join(missing)}",
            )
        ]

    queries_path = workspace / "queries.md"
    if not queries_path.exists() or queries_path.stat().st_size == 0:
        return [
            QualityIssue(
                code="idea_brief_missing_queries",
                message="`queries.md` is missing after `idea-brief`.",
            )
        ]
    queries = queries_path.read_text(encoding="utf-8", errors="ignore")
    profile_tokens = (
        'draft_profile: "idea_brainstorm"',
        "draft_profile: 'idea_brainstorm'",
        "draft_profile: idea_brainstorm",
    )
    if not any(token in queries for token in profile_tokens):
        return [
            QualityIssue(
                code="idea_brief_missing_draft_profile",
                message="`queries.md` should set `draft_profile: idea_brainstorm`.",
            )
        ]

    keyword_count = 0
    in_keywords = False
    for raw in queries.splitlines():
        stripped = raw.strip()
        if stripped.startswith("- keywords:"):
            in_keywords = True
            continue
        if stripped.startswith("- ") and not raw.startswith("  - "):
            if in_keywords:
                break
        if in_keywords and raw.startswith("  - ") and stripped[4:].strip():
            keyword_count += 1
    if keyword_count < 3:
        return [
            QualityIssue(
                code="idea_brief_too_few_query_buckets",
                message="`queries.md` should contain at least 3 keyword buckets for ideation retrieval.",
            )
        ]
    return []


def _sidecar_output_rel(outputs: list[str], *, filename: str) -> str:
    explicit = next((p for p in outputs if p.endswith(filename)), "")
    if explicit:
        return explicit
    target_stem = Path(filename).stem
    for output in outputs:
        p = Path(output)
        if p.suffix.lower() == ".md" and p.stem == target_stem:
            return str(p.with_suffix(".jsonl"))
    return f"output/{filename}"


def _load_idea_contract_for_quality(workspace: Path) -> tuple[dict[str, Any] | None, list[QualityIssue]]:
    from tooling.common import load_workspace_pipeline_spec
    from tooling.ideation import resolve_idea_contract

    if load_workspace_pipeline_spec(workspace) is None:
        return None, [
            QualityIssue(
                code="missing_idea_pipeline_contract",
                message="Missing or invalid active ideation pipeline contract; check `PIPELINE.lock.md` and pipeline metadata.",
            )
        ]
    try:
        return resolve_idea_contract(workspace), []
    except Exception as exc:
        return None, [
            QualityIssue(
                code="invalid_idea_pipeline_contract",
                message=f"Failed to resolve the ideation runtime contract ({type(exc).__name__}: {exc}).",
            )
        ]


def _markdown_table_data_rows(text: str, *, header_token: str) -> list[str]:
    data_rows: list[str] = []
    for ln in (text or "").splitlines():
        stripped = ln.strip()
        if not stripped.startswith("|"):
            continue
        cols = [c.strip() for c in stripped.strip("|").split("|")]
        if cols and cols[0].lower() == header_token.lower():
            continue
        is_separator = bool(cols) and all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in cols)
        if is_separator:
            continue
        data_rows.append(ln)
    return data_rows


def _missing_structured_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _load_jsonl_dict_records(workspace: Path, *, sidecar_rel: str, code_prefix: str) -> tuple[list[dict[str, Any]], list[QualityIssue]]:
    from tooling.common import read_jsonl

    sidecar_path = workspace / sidecar_rel
    if not sidecar_path.exists() or sidecar_path.stat().st_size == 0:
        return [], [QualityIssue(code=f"missing_{code_prefix}_jsonl", message=f"`{sidecar_rel}` is missing or empty.")]
    try:
        records = [r for r in read_jsonl(sidecar_path) if isinstance(r, dict)]
    except Exception as exc:
        return [], [
            QualityIssue(
                code=f"invalid_{code_prefix}_jsonl",
                message=f"`{sidecar_rel}` could not be parsed as JSONL ({type(exc).__name__}: {exc}).",
            )
        ]
    if not records:
        return [], [QualityIssue(code=f"empty_{code_prefix}_jsonl", message=f"`{sidecar_rel}` has no JSON objects.")]
    return records, []


def _audit_sidecar_records(
    *,
    records: Sequence[dict[str, Any]],
    sidecar_rel: str,
    code_prefix: str,
    required_fields: Sequence[str],
    expected_rows: int | None = None,
    id_key: str | None = None,
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    if expected_rows is not None and len(records) != int(expected_rows):
        issues.append(
            QualityIssue(
                code=f"{code_prefix}_row_mismatch",
                message=f"`{sidecar_rel}` row count ({len(records)}) should match the Markdown table row count ({expected_rows}).",
            )
        )

    bad_records = 0
    missing_fields: set[str] = set()
    for rec in records:
        missing = [field for field in required_fields if _missing_structured_value(rec.get(field))]
        if missing:
            bad_records += 1
            missing_fields.update(missing)
    if bad_records:
        issues.append(
            QualityIssue(
                code=f"{code_prefix}_missing_fields",
                message=(
                    f"`{sidecar_rel}` has {bad_records} record(s) missing required fields "
                    f"({', '.join(sorted(missing_fields))})."
                ),
            )
        )

    if id_key:
        ids = [str(rec.get(id_key) or "").strip() for rec in records if str(rec.get(id_key) or "").strip()]
        dupes = len(ids) - len(set(ids))
        if dupes:
            issues.append(
                QualityIssue(
                    code=f"{code_prefix}_duplicate_ids",
                    message=f"`{sidecar_rel}` contains duplicate `{id_key}` values ({dupes}).",
                )
            )
    return issues


def check_signal_table(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = next((p for p in outputs if p.endswith("IDEA_SIGNAL_TABLE.md")), "output/trace/IDEA_SIGNAL_TABLE.md")
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code="missing_idea_signal_table", message=f"`{out_rel}` is missing or empty.")]
    contract, issues = _load_idea_contract_for_quality(workspace)
    if issues:
        return issues
    text = path.read_text(encoding="utf-8", errors="ignore")
    if has_placeholder_markers(text) or "…" in text:
        return [QualityIssue(code="idea_signal_table_placeholders", message=f"`{out_rel}` contains placeholders/ellipsis.")]
    needed = ["Signal ID", "Cluster", "Theme", "Claim / observation", "Tension", "Missing piece", "Possible axis", "Academic value", "Confidence", "Paper IDs"]
    if not all(h.lower() in text.lower() for h in needed):
        return [QualityIssue(code="idea_signal_table_missing_columns", message=f"`{out_rel}` should expose a signal table with the expected columns.")]
    data_rows = _markdown_table_data_rows(text, header_token="Signal ID")
    min_rows = int(contract["signal_table_min"])
    if len(data_rows) < min_rows:
        return [QualityIssue(code="idea_signal_table_too_small", message=f"`{out_rel}` should contain at least {min_rows} signal rows (found {len(data_rows)}).")]
    sidecar_rel = _sidecar_output_rel(outputs, filename="IDEA_SIGNAL_TABLE.jsonl")
    records, issues = _load_jsonl_dict_records(workspace, sidecar_rel=sidecar_rel, code_prefix="idea_signal_table")
    if issues:
        return issues
    issues.extend(_audit_sidecar_records(records=records, sidecar_rel=sidecar_rel, code_prefix="idea_signal_table", required_fields=["signal_id", "cluster", "direction_type", "theme", "claim_or_observation", "tension", "missing_piece", "possible_axis", "academic_value", "evidence_confidence", "paper_ids"], expected_rows=len(data_rows), id_key="signal_id"))
    bad_pids = 0
    for rec in records:
        paper_ids = rec.get("paper_ids")
        valid = [pid for pid in (paper_ids or []) if re.fullmatch(r"P\d{4}", str(pid).strip())]
        if not isinstance(paper_ids, list) or len(valid) < 1:
            bad_pids += 1
    if bad_pids:
        issues.append(QualityIssue(code="idea_signal_table_bad_paper_ids", message=f"`{sidecar_rel}` has {bad_pids} record(s) without valid `paper_ids` lists."))
    return issues


def check_direction_pool(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = next((p for p in outputs if p.endswith("IDEA_DIRECTION_POOL.md")), "output/trace/IDEA_DIRECTION_POOL.md")
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code="missing_idea_direction_pool", message=f"`{out_rel}` is missing or empty.")]
    contract, issues = _load_idea_contract_for_quality(workspace)
    if issues:
        return issues
    text = path.read_text(encoding="utf-8", errors="ignore")
    if has_placeholder_markers(text) or "…" in text:
        return [QualityIssue(code="idea_direction_pool_placeholders", message=f"`{out_rel}` contains placeholders/ellipsis.")]
    needed = ["Direction ID", "Cluster", "Type", "Title", "One-line thesis", "Why interesting", "Missing piece", "Possible variants", "Academic value", "First probes", "Confidence", "Paper IDs"]
    if not all(h.lower() in text.lower() for h in needed):
        return [QualityIssue(code="idea_direction_pool_missing_columns", message=f"`{out_rel}` should expose a direction pool table with the expected columns.")]
    data_rows = _markdown_table_data_rows(text, header_token="Direction ID")
    pool_min = int(contract["direction_pool_min"])
    pool_max = int(contract["direction_pool_max"])
    if len(data_rows) < pool_min or len(data_rows) > pool_max:
        return [QualityIssue(code="idea_direction_pool_size_out_of_range", message=f"`{out_rel}` should contain {pool_min}-{pool_max} direction rows (found {len(data_rows)}).")]
    sidecar_rel = _sidecar_output_rel(outputs, filename="IDEA_DIRECTION_POOL.jsonl")
    records, issues = _load_jsonl_dict_records(workspace, sidecar_rel=sidecar_rel, code_prefix="idea_direction_pool")
    if issues:
        return issues
    issues.extend(_audit_sidecar_records(records=records, sidecar_rel=sidecar_rel, code_prefix="idea_direction_pool", required_fields=["direction_id", "cluster", "direction_type", "title", "focus_axis", "main_confound", "program_kind", "contribution_shape", "time_to_clarity", "one_line_thesis", "why_interesting", "literature_suggests", "missing_piece", "possible_variants", "academic_value", "first_probes", "weakness_conditions", "kill_criteria", "best_fit", "evidence_confidence", "paper_ids", "signal_ids", "anchor_reading_notes"], expected_rows=len(data_rows), id_key="direction_id"))
    return issues


def check_screening_table(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = next((p for p in outputs if p.endswith("IDEA_SCREENING_TABLE.md")), "output/trace/IDEA_SCREENING_TABLE.md")
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code="missing_idea_screening_table", message=f"`{out_rel}` is missing or empty.")]
    contract, issues = _load_idea_contract_for_quality(workspace)
    if issues:
        return issues
    text = path.read_text(encoding="utf-8", errors="ignore")
    if has_placeholder_markers(text) or "…" in text:
        return [QualityIssue(code="idea_screening_table_placeholders", message=f"`{out_rel}` contains placeholders/ellipsis.")]
    needed = ["Direction ID", "Cluster", "Type", "Title", "Total", "Discussion", "Academic value", "Evidence", "Distinctness", "First probe", "Thesis potential", "Decision", "Rationale"]
    if not all(h.lower() in text.lower() for h in needed):
        return [QualityIssue(code="idea_screening_table_missing_columns", message=f"`{out_rel}` should expose a scored screening table with the expected columns.")]
    data_rows = _markdown_table_data_rows(text, header_token="Direction ID")
    min_rows = int(contract["idea_screen_top_n"])
    if len(data_rows) < min_rows:
        return [QualityIssue(code="idea_screening_table_too_small", message=f"`{out_rel}` should contain at least {min_rows} screened directions (found {len(data_rows)}).")]
    sidecar_rel = _sidecar_output_rel(outputs, filename="IDEA_SCREENING_TABLE.jsonl")
    records, issues = _load_jsonl_dict_records(workspace, sidecar_rel=sidecar_rel, code_prefix="idea_screening_table")
    if issues:
        return issues
    issues.extend(_audit_sidecar_records(records=records, sidecar_rel=sidecar_rel, code_prefix="idea_screening_table", required_fields=["direction_id", "cluster", "direction_type", "title", "total_score", "discussion_worthiness", "academic_value_score", "evidence_grounding", "direction_distinctness", "first_probe_clarity", "thesis_potential", "recommendation", "rationale"], expected_rows=len(data_rows), id_key="direction_id"))
    decisions = [str(rec.get("recommendation") or "").strip().lower() for rec in records]
    bad = sorted({d for d in decisions if d not in {"keep", "maybe", "drop"}})
    if bad:
        issues.append(QualityIssue(code="idea_screening_table_bad_decisions", message=f"`{sidecar_rel}` contains unsupported decisions: {', '.join(bad)}."))
    keep_min = int(contract["keep_min"])
    if sum(1 for d in decisions if d == "keep") < keep_min:
        issues.append(QualityIssue(code="idea_screening_table_too_few_kept", message=f"`{sidecar_rel}` should mark at least {keep_min} candidates as `keep` for the shortlist."))
    return issues


def check_shortlist(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_workspace_pipeline_spec

    out_rel = next((p for p in outputs if p.endswith("IDEA_SHORTLIST.md")), "output/trace/IDEA_SHORTLIST.md")
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code="missing_idea_shortlist", message=f"`{out_rel}` is missing or empty.")]
    if load_workspace_pipeline_spec(workspace) is None:
        return [QualityIssue(code="missing_idea_pipeline_contract", message="Missing or invalid active ideation pipeline contract; check `PIPELINE.lock.md` and pipeline metadata.")]
    text = path.read_text(encoding="utf-8", errors="ignore")
    if has_placeholder_markers(text) or "…" in text:
        return [QualityIssue(code="idea_shortlist_placeholders", message=f"`{out_rel}` contains placeholders/ellipsis.")]
    contract, issues = _load_idea_contract_for_quality(workspace)
    if issues:
        return issues
    ideas = len(re.findall(r"(?m)^###\s+Direction\s+\d+\.", text))
    shortlist_min = int(contract["shortlist_min"])
    shortlist_max = int(contract["shortlist_max"])
    if ideas < shortlist_min or ideas > shortlist_max:
        return [QualityIssue(code="idea_shortlist_size_out_of_range", message=f"`{out_rel}` should contain {shortlist_min}-{shortlist_max} shortlisted directions (found {ideas}).")]
    expected_shortlist_size = int(contract["shortlist_size"])
    if ideas != expected_shortlist_size:
        return [QualityIssue(code="idea_shortlist_size_mismatch", message=f"`{out_rel}` should contain exactly {expected_shortlist_size} shortlisted directions for the active ideation contract (found {ideas}).")]
    required_labels = ["Focus axis:", "Program kind:", "Main confound:", "Time to clarity:", "One-line thesis:", "Why this ranks here:", "Why this is interesting:", "What the literature already suggests:", "Closest prior work and why it does not settle the question:", "What is still missing:", "Possible variants:", "Contribution shape:", "Why this could matter academically:", "First probes:", "What would count as actual insight:", "What would make this weak or unconvincing:", "Quick kill criteria:", "Best fit:", "Evidence confidence:", "Anchor papers:", "Why prioritized now:"]
    missing = [lab for lab in required_labels if lab not in text]
    if missing:
        return [QualityIssue(code="idea_shortlist_missing_fields", message=f"`{out_rel}` is missing required shortlist fields: {', '.join(missing)}")]
    sidecar_rel = _sidecar_output_rel(outputs, filename="IDEA_SHORTLIST.jsonl")
    records, issues = _load_jsonl_dict_records(workspace, sidecar_rel=sidecar_rel, code_prefix="idea_shortlist")
    if issues:
        return issues
    issues.extend(_audit_sidecar_records(records=records, sidecar_rel=sidecar_rel, code_prefix="idea_shortlist", required_fields=["rank", "direction_id", "cluster", "direction_type", "title", "focus_axis", "main_confound", "program_kind", "contribution_shape", "time_to_clarity", "one_line_thesis", "why_interesting", "literature_suggests", "closest_prior_gap", "missing_piece", "possible_variants", "academic_value", "first_probes", "what_counts_as_insight", "weakness_conditions", "kill_criteria", "best_fit", "evidence_confidence", "paper_ids", "signal_ids", "anchor_reading_notes", "why_this_ranks_here", "why_prioritized"], expected_rows=ideas, id_key="direction_id"))
    ranks = []
    bad_ranks = 0
    for rec in records:
        try:
            ranks.append(int(rec.get("rank")))
        except Exception:
            bad_ranks += 1
    if bad_ranks:
        issues.append(QualityIssue(code="idea_shortlist_bad_ranks", message=f"`{sidecar_rel}` has {bad_ranks} record(s) with non-integer `rank`."))
    elif sorted(ranks) != list(range(1, len(records) + 1)):
        issues.append(QualityIssue(code="idea_shortlist_noncontiguous_ranks", message=f"`{sidecar_rel}` should rank shortlisted directions contiguously from 1 to {len(records)}."))
    clusters = {str(rec.get("cluster") or "").strip() for rec in records if str(rec.get("cluster") or "").strip()}
    cluster_diversity_min = int(contract["cluster_diversity_min"])
    if len(clusters) < cluster_diversity_min:
        issues.append(QualityIssue(code="idea_shortlist_low_cluster_diversity", message=f"`{sidecar_rel}` should cover at least {cluster_diversity_min} clusters (found {len(clusters)})."))
    return issues


def check_report_bundle(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    report_rel = next((p for p in outputs if p.endswith("REPORT.md")), "output/REPORT.md")
    appendix_rel = next((p for p in outputs if p.endswith("APPENDIX.md")), "output/APPENDIX.md")
    json_rel = next((p for p in outputs if p.endswith("REPORT.json")), "output/REPORT.json")
    report_path = workspace / report_rel
    appendix_path = workspace / appendix_rel
    json_path = workspace / json_rel
    if not report_path.exists() or report_path.stat().st_size == 0:
        return [QualityIssue(code="missing_brainstorm_report", message=f"`{report_rel}` is missing or empty.")]
    if not appendix_path.exists() or appendix_path.stat().st_size == 0:
        return [QualityIssue(code="missing_brainstorm_appendix", message=f"`{appendix_rel}` is missing or empty.")]
    if not json_path.exists() or json_path.stat().st_size == 0:
        return [QualityIssue(code="missing_brainstorm_report_json", message=f"`{json_rel}` is missing or empty.")]
    contract, issues = _load_idea_contract_for_quality(workspace)
    if issues:
        return issues
    text = report_path.read_text(encoding="utf-8", errors="ignore")
    if has_placeholder_markers(text) or "…" in text:
        return [QualityIssue(code="brainstorm_report_placeholders", message=f"`{report_rel}` contains placeholders/ellipsis.")]
    report_top_n = int(contract["report_top_n"])
    deferred_idx = 3 + report_top_n
    discussion_idx = deferred_idx + 1
    uncertainty_idx = deferred_idx + 2
    next_idx = deferred_idx + 3
    appendix_idx = deferred_idx + 4
    required_sections = [
        "## 0. Scope and framing",
        "## 1. Big-picture takeaways",
        "## 2. Top directions at a glance",
        f"## {deferred_idx}. Other promising but not prioritized directions",
        f"## {discussion_idx}. Cross-cutting discussion questions",
        f"## {uncertainty_idx}. Uncertainty and disagreement",
        f"## {next_idx}. Suggested next reading / next discussion step",
        f"## {appendix_idx}. Appendix guide",
    ]
    missing = [h for h in required_sections if h not in text]
    if missing:
        return [QualityIssue(code="brainstorm_report_missing_sections", message=f"`{report_rel}` is missing required sections: {', '.join(missing)}")]
    appendix_text = appendix_path.read_text(encoding="utf-8", errors="ignore")
    if "Anchor paper" not in appendix_text or "Why read now" not in appendix_text or "What to extract" not in appendix_text or "Kill signal" not in appendix_text:
        return [QualityIssue(code="brainstorm_appendix_missing_reading_guide", message=f"`{appendix_rel}` should provide a paper-specific reading guide table (Anchor paper / Why read now / What to extract / Kill signal).")]
    generic_phrases = []
    if text.count("reports a meaningful gain") >= 2:
        generic_phrases.append("reports a meaningful gain")
    if "Sharper mechanism question;" in text:
        generic_phrases.append("Sharper mechanism question;")
    if appendix_text.count("read it to extract what it really attributes gains to") >= 1:
        generic_phrases.append("read it to extract what it really attributes gains to")
    if text.count("may be over-attributing progress to broad agent quality") >= 2:
        generic_phrases.append("may be over-attributing progress to broad agent quality")
    if generic_phrases:
        return [QualityIssue(code="brainstorm_report_generic_language", message=f"`{report_rel}` / `{appendix_rel}` still contain generic templated language: {', '.join(generic_phrases)}")]
    direction_sections = re.findall(r"(?m)^##\s+\d+\.\s+Direction\s+\d+\s+—\s+(.+)$", text)
    if len(direction_sections) != report_top_n:
        return [QualityIssue(code="brainstorm_report_wrong_direction_count", message=f"`{report_rel}` should contain exactly {report_top_n} expanded lead directions (found {len(direction_sections)}).")]
    if re.search(r"\bP\d{4}\b", text):
        return [QualityIssue(code="brainstorm_report_leaks_internal_ids", message=f"`{report_rel}` should not expose raw `paper_id` values in the main memo.")]
    compare_rows = _markdown_table_data_rows(text, header_token="Rank")
    if len(compare_rows) < report_top_n:
        return [QualityIssue(code="brainstorm_report_thin_snapshot", message=f"`{report_rel}` should include a top-directions comparison table with at least {report_top_n} rows.")]
    shortlist_path = workspace / "output" / "trace" / "IDEA_SHORTLIST.jsonl"
    if shortlist_path.exists() and shortlist_path.stat().st_size > 0:
        from tooling.common import read_jsonl
        shortlist = [r for r in read_jsonl(shortlist_path) if isinstance(r, dict)]
        expected_titles = [str(r.get("title") or "").strip() for r in shortlist[:report_top_n] if str(r.get("title") or "").strip()]
        if len(expected_titles) == report_top_n and direction_sections[:report_top_n] != expected_titles:
            return [QualityIssue(code="brainstorm_report_shortlist_mismatch", message=f"`{report_rel}` should expand the top {report_top_n} titles from `output/trace/IDEA_SHORTLIST.jsonl` in rank order.")]
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [QualityIssue(code="brainstorm_report_json_invalid", message=f"`{json_rel}` is not valid JSON ({type(exc).__name__}: {exc}).")]
    needed_keys = {"topic", "takeaways", "top_directions", "deferred_directions", "discussion_questions", "uncertainties", "next_steps", "trace_artifacts"}
    missing_keys = sorted(needed_keys - set(payload.keys()))
    if missing_keys:
        return [QualityIssue(code="brainstorm_report_json_missing_keys", message=f"`{json_rel}` is missing required keys: {', '.join(missing_keys)}")]
    top_directions = payload.get("top_directions") or []
    if not isinstance(top_directions, list):
        return [QualityIssue(code="brainstorm_report_json_bad_top_directions", message=f"`{json_rel}` `top_directions` should be a JSON array.")]
    if len(top_directions) != report_top_n:
        return [QualityIssue(code="brainstorm_report_json_wrong_direction_count", message=f"`{json_rel}` should contain exactly {report_top_n} top directions (found {len(top_directions)}).")]
    for idx, rec in enumerate(top_directions, start=1):
        if not isinstance(rec, dict):
            return [QualityIssue(code="brainstorm_report_json_bad_top_direction", message=f"`{json_rel}` top direction #{idx} should be a JSON object.")]
        required_rec = {"title", "focus_axis", "main_confound", "program_kind", "contribution_shape", "time_to_clarity", "one_line_thesis", "why_this_ranks_here", "literature_suggests", "closest_prior_gap", "missing_piece", "what_counts_as_insight", "first_probes", "kill_criteria", "anchor_reading_notes"}
        rec_missing = sorted(required_rec - set(rec.keys()))
        if rec_missing:
            return [QualityIssue(code="brainstorm_report_json_thin_top_direction", message=f"`{json_rel}` top direction #{idx} is missing fields: {', '.join(rec_missing)}")]
    return []
