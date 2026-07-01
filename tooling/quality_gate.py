from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence


@dataclass(frozen=True)
class QualityIssue:
    code: str
    message: str


def _pipeline_profile(workspace: Path) -> str:
    from tooling.common import pipeline_profile
    return pipeline_profile(workspace)


def _draft_profile(workspace: Path) -> str:
    """Return the draft strictness profile from `queries.md` (best-effort).

    Supported values: `survey`, `deep` (default: `survey` for arxiv-survey pipelines).
    """
    from tooling.common import pipeline_query_default

    profile = _pipeline_profile(workspace)
    default = str(pipeline_query_default(workspace, "draft_profile", "" if profile != "arxiv-survey" else "survey") or "").strip().lower()
    if default not in {"survey", "deep"}:
        default = "survey" if profile == "arxiv-survey" else "default"

    queries_path = workspace / "queries.md"
    if not queries_path.exists():
        return default

    try:
        for raw in queries_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            if key != "draft_profile":
                continue
            value = value.split("#", 1)[0].strip().strip('"').strip("'").strip().lower()
            if value in {"survey", "deep"}:
                return value
            return default
    except Exception:
        return default
    return default


def _citation_target(workspace: Path) -> str:
    """Return the global citation target policy from `queries.md` (best-effort).

    Supported values:
    - `recommended`: converge to the recommended unique-citation target (A150++ default)
    - `hard`: only enforce the hard minimum target

    Config (queries.md):
    - `- citation_target: recommended|hard`

    Notes:
    - This is a *policy switch* that affects the citation self-loop behavior:
      `citation-diversifier` (budget sizing) + `citation-injector` (target enforced).
    """
    from tooling.common import pipeline_query_default

    profile = _pipeline_profile(workspace)
    default = str(pipeline_query_default(workspace, "citation_target", "" if profile != "arxiv-survey" else "recommended") or "").strip().lower()
    if default not in {"recommended", "hard"}:
        default = "recommended" if profile == "arxiv-survey" else "hard"

    queries_path = workspace / "queries.md"
    if not queries_path.exists():
        return default

    try:
        for raw in queries_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            if key != "citation_target":
                continue
            value = value.split("#", 1)[0].strip().strip('"').strip("'").strip().lower()
            if value in {"recommended", "rec"}:
                return "recommended"
            if value in {"hard", "min", "minimum"}:
                return "hard"
            return default
    except Exception:
        return default
    return default


def _global_citation_min_subsections(workspace: Path) -> int:
    """Return the minimum subsection-mapping count for treating a bibkey as globally in-scope.

    Config (queries.md): `- global_citation_min_subsections: <int>`

    Rationale: some works are legitimately cross-cutting (foundations/benchmarks/surveys).
    This threshold lets the pipeline stay strict by default while allowing controlled flexibility.
    """

    from tooling.common import pipeline_query_default

    default = int(pipeline_query_default(workspace, "global_citation_min_subsections", 4) or 4)
    queries_path = workspace / "queries.md"
    if not queries_path.exists():
        return default

    try:
        for raw in queries_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            if key != "global_citation_min_subsections":
                continue
            value = value.split("#", 1)[0].strip().strip('"').strip("'").strip()
            if not value:
                return default
            try:
                n = int(value)
            except Exception:
                return default
            if n <= 0:
                return default
            return n
    except Exception:
        return default
    return default


def _query_int(workspace: Path, *, keys: set[str], default: int) -> int:
    """Best-effort read an int value from `queries.md`."""
    queries_path = workspace / "queries.md"
    if not queries_path.exists():
        return int(default)

    try:
        for raw in queries_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            if key not in keys:
                continue
            value = value.split("#", 1)[0].strip().strip('"').strip("'").strip()
            if not value:
                return int(default)
            try:
                n = int(value)
            except Exception:
                return int(default)
            return n if n > 0 else int(default)
    except Exception:
        return int(default)
    return int(default)


def _core_size(workspace: Path) -> int:
    """Core set size contract (default: A150++ = 300 for arxiv-survey pipelines)."""
    from tooling.common import pipeline_query_default

    profile = _pipeline_profile(workspace)
    default = int(pipeline_query_default(workspace, "core_size", 300 if profile == "arxiv-survey" else 0) or 0)
    return _query_int(workspace, keys={"core_size"}, default=default)


def _per_subsection(workspace: Path) -> int:
    """Per-H3 mapping contract (default: A150++ = 28 for arxiv-survey pipelines)."""
    from tooling.common import pipeline_query_default

    profile = _pipeline_profile(workspace)
    default = int(pipeline_query_default(workspace, "per_subsection", 28 if profile == "arxiv-survey" else 3) or 0)
    return _query_int(workspace, keys={"per_subsection"}, default=default)


def _structure_mode(workspace: Path) -> str:
    from tooling.common import load_workspace_pipeline_spec

    spec = load_workspace_pipeline_spec(workspace)
    if spec is None:
        return ""
    return str(spec.structure_mode or "").strip().lower()


def _section_first_artifact_issues(workspace: Path, *, consumer: str) -> list[QualityIssue]:
    if _structure_mode(workspace) != "section_first":
        return []

    required = [
        "outline/chapter_skeleton.yml",
        "outline/section_bindings.jsonl",
        "outline/section_binding_report.md",
        "outline/section_briefs.jsonl",
    ]
    missing: list[str] = []
    empty: list[str] = []
    for rel in required:
        path = workspace / rel
        if not path.exists():
            missing.append(rel)
            continue
        if path.stat().st_size <= 0:
            empty.append(rel)

    issues: list[QualityIssue] = []
    if missing:
        issues.append(
            QualityIssue(
                code="section_first_missing_artifacts",
                message=(
                    f"`{consumer}` requires the section-first C2 artifacts before H3-level validation can proceed; "
                    f"missing: {', '.join(missing)}."
                ),
            )
        )
    if empty:
        issues.append(
            QualityIssue(
                code="section_first_empty_artifacts",
                message=(
                    f"`{consumer}` requires non-empty section-first C2 artifacts before H3-level validation can proceed; "
                    f"empty: {', '.join(empty)}."
                ),
            )
        )
    return issues


def _parse_section_binding_report_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        if cells[0].lower() == "section" and cells[2].lower() == "status":
            continue
        rows.append(
            {
                "section": cells[0],
                "coverage": cells[1],
                "status": cells[2].upper(),
                "recommendation": cells[3],
            }
        )
    return rows


def _section_first_cutover_issues(workspace: Path, *, consumer: str, require_stable_h3: bool) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    if _structure_mode(workspace) != "section_first":
        return []

    state_rel = "outline/outline_state.jsonl"
    state_path = workspace / state_rel
    if not state_path.exists():
        return [
            QualityIssue(
                code="section_first_missing_outline_state",
                message=f"`{consumer}` requires `{state_rel}` to record section-first cutover state.",
            )
        ]
    records = [r for r in read_jsonl(state_path) if isinstance(r, dict)]
    if not records:
        return [
            QualityIssue(
                code="section_first_empty_outline_state",
                message=f"`{consumer}` requires `{state_rel}` to contain at least one cutover-state record.",
            )
        ]

    latest = records[-1]
    required_fields = [
        "structure_phase",
        "h3_status",
        "approval_status",
        "reroute_target",
        "retry_budget_remaining",
    ]
    nonempty_fields = {
        "structure_phase",
        "h3_status",
        "approval_status",
    }
    missing_fields: list[str] = []
    for key in required_fields:
        if key not in latest:
            missing_fields.append(key)
            continue
        value = latest.get(key)
        if key in nonempty_fields and isinstance(value, str) and not value.strip():
            missing_fields.append(key)
    issues: list[QualityIssue] = []
    if missing_fields:
        issues.append(
            QualityIssue(
                code="section_first_outline_state_missing_fields",
                message=(
                    f"`{state_rel}` is missing section-first cutover fields for `{consumer}`: "
                    f"{', '.join(missing_fields)}."
                ),
            )
        )

    structure_phase = str(latest.get("structure_phase") or "").strip().lower()
    h3_status = str(latest.get("h3_status") or "").strip().lower()
    approval_status = str(latest.get("approval_status") or "").strip().lower()
    reroute_target = str(latest.get("reroute_target") or "").strip()
    reroute_reason = str(latest.get("reroute_reason") or "").strip()
    retry_budget_raw = latest.get("retry_budget_remaining")
    retry_budget_text = str(retry_budget_raw or "").strip()
    retry_budget_value: int | None = None
    if structure_phase in {"binding_blocked", "binding_reroute"}:
        if not reroute_target:
            issues.append(
                QualityIssue(
                    code="section_first_reroute_target_missing",
                    message=(
                        f"`{state_rel}` reports structure_phase={structure_phase} for `{consumer}` but leaves `reroute_target` empty."
                    ),
                )
            )
        if retry_budget_text:
            try:
                retry_budget_value = int(retry_budget_text)
            except Exception:
                issues.append(
                    QualityIssue(
                        code="section_first_retry_budget_invalid",
                        message=(
                            f"`{state_rel}` should record an integer `retry_budget_remaining` for `{consumer}` when section bindings block/reroute "
                            f"(found {retry_budget_text!r})."
                        ),
                    )
                )
            else:
                if retry_budget_value < 0:
                    issues.append(
                        QualityIssue(
                            code="section_first_retry_budget_invalid",
                            message=(
                                f"`{state_rel}` reports a negative `retry_budget_remaining` for `{consumer}` "
                                f"(found {retry_budget_value})."
                            ),
                        )
                    )
        else:
            issues.append(
                QualityIssue(
                    code="section_first_retry_budget_missing",
                    message=(
                        f"`{state_rel}` should record `retry_budget_remaining` for `{consumer}` when section bindings block/reroute."
                    ),
                )
            )
        if approval_status == "approved":
            issues.append(
                QualityIssue(
                    code="section_first_approval_state_inconsistent",
                    message=(
                        f"`{state_rel}` marks `{consumer}` as approved while structure_phase={structure_phase}; approval should not stay effective through a binding block/reroute."
                    ),
                )
            )

    if require_stable_h3:
        if structure_phase == "binding_blocked":
            issues.append(
                QualityIssue(
                    code="section_first_binding_blocked",
                    message=(
                        f"`{consumer}` is blocked by the section-binding gate; latest `outline_state.jsonl` has "
                        f"structure_phase=binding_blocked, reroute_target={reroute_target or '(empty)'}, "
                        f"retry_budget_remaining={retry_budget_text or '(empty)'}"
                        + (f", reroute_reason={reroute_reason}" if reroute_reason else ".")
                    ),
                )
            )
        elif structure_phase == "binding_reroute":
            issues.append(
                QualityIssue(
                    code="section_first_binding_reroute",
                    message=(
                        f"`{consumer}` is waiting on a section-binding reroute; latest `outline_state.jsonl` has "
                        f"structure_phase=binding_reroute, reroute_target={reroute_target or '(empty)'}, "
                        f"retry_budget_remaining={retry_budget_text or '(empty)'}"
                        + (f", reroute_reason={reroute_reason}" if reroute_reason else ".")
                    ),
                )
            )
        elif structure_phase != "decomposed" or h3_status != "stable":
            issues.append(
                QualityIssue(
                    code="section_first_h3_not_stable",
                    message=(
                        f"`{consumer}` requires section-first cutover to be complete before H3-level artifacts are accepted; "
                        f"latest `outline_state.jsonl` has structure_phase={structure_phase or '(empty)'} "
                        f"and h3_status={h3_status or '(empty)'}, expected `decomposed` + `stable`."
                    ),
                )
            )
    return issues


def _quality_contract_int(workspace: Path, *, keys: tuple[str, ...], default: int) -> int:
    from tooling.common import pipeline_quality_contract_value

    value = pipeline_quality_contract_value(workspace, *keys, default=default)
    try:
        parsed = int(value)
    except Exception:
        return int(default)
    return parsed if parsed > 0 else int(default)


def _evidence_mode(workspace: Path) -> str:
    from tooling.common import pipeline_query_default

    default = str(pipeline_query_default(workspace, "evidence_mode", "abstract") or "").strip().lower()
    if default not in {"abstract", "fulltext"}:
        default = "abstract"

    queries_path = workspace / "queries.md"
    if not queries_path.exists():
        return default

    try:
        for raw in queries_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            if key != "evidence_mode":
                continue
            value = value.split("#", 1)[0].strip().strip('"').strip("'").strip().lower()
            if value in {"abstract", "fulltext"}:
                return value
            return default
    except Exception:
        return default
    return default


def _check_placeholder_markers(text: str) -> bool:
    if not text:
        return False
    if re.search(r"(?i)\b(?:TODO|TBD|FIXME)\b", text):
        return True
    low = text.lower()
    if "(placeholder)" in low:
        return True
    if "<!-- scaffold" in low:
        return True
    return False


def _check_short_descriptions(values: Sequence[str], *, min_chars: int) -> tuple[int, int]:
    total = 0
    short = 0
    for v in values:
        v = str(v or "").strip()
        if not v:
            continue
        total += 1
        if len(v) < int(min_chars):
            short += 1
    return short, total


def _check_repeated_template_text(*, text: str, min_len: int = 32, min_repeats: int = 6) -> tuple[str, int] | None:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    counts: dict[str, int] = {}
    for ln in lines:
        if len(ln) < int(min_len):
            continue
        # Normalize citations to reduce false negatives.
        norm = re.sub(r"\[@[^\]]+\]", "", ln)
        norm = re.sub(r"\s+", " ", norm).strip().lower()
        if len(norm) < int(min_len):
            continue
        counts[norm] = counts.get(norm, 0) + 1
    if not counts:
        return None
    top_norm, top_count = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    if top_count >= int(min_repeats):
        example = top_norm[:120]
        return example, top_count
    return None


def _check_repeated_sentences(*, text: str, min_len: int = 80, min_repeats: int = 6) -> tuple[str, int] | None:
    """Detect repeated sentence-level boilerplate (robust to hard line-wrapping)."""
    raw = (text or "").strip()
    if not raw:
        return None

    # Remove citations and collapse whitespace so wrapped lines don't defeat the check.
    compact = re.sub(r"\[@[^\]]+\]", "", raw)
    compact = re.sub(r"\s+", " ", compact).strip()
    if not compact:
        return None

    # Cheap sentence splitting; good enough for boilerplate detection.
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", compact) if s.strip()]
    counts: dict[str, int] = {}
    for s in sents:
        if len(s) < int(min_len):
            continue
        norm = re.sub(r"\s+", " ", s).strip().lower()
        if len(norm) < int(min_len):
            continue
        counts[norm] = counts.get(norm, 0) + 1
    if not counts:
        return None

    top_norm, top_count = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    if top_count >= int(min_repeats):
        return top_norm[:140], top_count
    return None


def _check_keyword_expansion(workspace: Path) -> list[QualityIssue]:
    queries_path = workspace / "queries.md"
    if not queries_path.exists():
        return [QualityIssue(code="missing_queries", message="Missing `queries.md`; expected keyword list for retrieval.")]

    text = queries_path.read_text(encoding="utf-8", errors="ignore")
    if _check_placeholder_markers(text):
        # Only treat placeholder markers as blocking if they appear in the query lists themselves.
        pass

    mode: str | None = None
    keywords: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("- keywords:"):
            mode = "keywords"
            continue
        if line.startswith("- exclude:"):
            mode = "exclude"
            continue
        if not line.startswith("- "):
            continue
        if mode != "keywords":
            continue
        value = line[2:].split("#", 1)[0].strip().strip('"').strip("'")
        if value:
            keywords.append(value)

    if not keywords:
        return [
            QualityIssue(
                code="queries_missing_keywords",
                message="`queries.md` has no non-empty `keywords` entries; fill keywords (or use offline import).",
            )
        ]
    # Soft heuristic: 1 keyword often means low coverage; require >1 only for online runs (checked by caller).
    if len(keywords) == 1 and len(keywords[0]) < 6:
        return [
            QualityIssue(
                code="queries_keywords_too_generic",
                message="`queries.md` keyword list looks too weak; add synonyms/acronyms or use `keyword-expansion` before retrieval.",
            )
        ]
    return []


def check_unit_outputs(*, skill: str, workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    if skill == "idea-brief":
        return _check_idea_brief(workspace, outputs)
    if skill == "literature-engineer":
        return _check_literature_engineer(workspace, outputs)
    if skill == "arxiv-search":
        return _check_arxiv_search(workspace, outputs)
    if skill == "dedupe-rank":
        return _check_dedupe_rank(workspace, outputs)
    if skill == "citation-verifier":
        return _check_citations(workspace, outputs)
    if skill == "outline-refiner":
        return _check_coverage_report(workspace, outputs)
    if skill == "pdf-text-extractor":
        return _check_pdf_text_extractor(workspace, outputs)
    if skill == "taxonomy-builder":
        return _check_taxonomy(workspace, outputs)
    if skill == "chapter-skeleton":
        return _check_chapter_skeleton(workspace, outputs)
    if skill == "section-bindings":
        return _check_section_bindings(workspace, outputs)
    if skill == "section-briefs":
        return _check_section_briefs(workspace, outputs)
    if skill == "outline-builder":
        return _check_outline(workspace, outputs)
    if skill == "section-mapper":
        return _check_mapping(workspace, outputs)
    if skill == "paper-notes":
        return _check_paper_notes(workspace, outputs)
    if skill == "claim-evidence-matrix":
        return _check_claim_evidence_matrix(workspace, outputs)
    if skill == "claim-matrix-rewriter":
        return _check_claim_evidence_matrix(workspace, outputs)
    if skill == "table-schema":
        return _check_table_schema(workspace, outputs)
    if skill == "table-filler":
        return _check_tables_index_md(workspace, outputs)
    if skill == "appendix-table-writer":
        return _check_tables_appendix_md(workspace, outputs)
    if skill == "subsection-briefs":
        return _check_subsection_briefs(workspace, outputs)
    if skill == "chapter-briefs":
        return _check_chapter_briefs(workspace, outputs)
    if skill == "evidence-binder":
        return _check_evidence_bindings(workspace, outputs)
    if skill == "evidence-draft":
        return _check_evidence_drafts(workspace, outputs)
    if skill == "anchor-sheet":
        return _check_anchor_sheet(workspace, outputs)
    if skill == "schema-normalizer":
        return _check_schema_normalization_report(workspace, outputs)
    if skill == "writer-context-pack":
        return _check_writer_context_packs(workspace, outputs)
    if skill == "survey-visuals":
        return _check_survey_visuals(workspace, outputs)
    if skill == "transition-weaver":
        return _check_transitions(workspace, outputs)
    if skill == "subsection-writer":
        # The subsection-writer unit is LLM-first. Its script is responsible for
        # generating the expected file manifest, but the strict writing gate is
        # enforced by the explicit writing self-loop unit (`writer-selfloop`).
        return _check_sections_manifest_index(workspace, outputs)
    if skill == "writer-selfloop":
        return _check_writer_selfloop(workspace, outputs)
    if skill == "evaluation-anchor-checker":
        return _check_eval_anchor_report(workspace, outputs)
    if skill == "section-logic-polisher":
        return _check_section_logic_polisher(workspace, outputs)
    if skill == "section-merger":
        return _check_merge_report(workspace, outputs)
    if skill == "citation-injector":
        return _check_citation_injection(workspace, outputs)
    if skill == "prose-writer":
        return _check_draft(workspace, outputs)
    if skill == "draft-polisher":
        issues = _check_draft(workspace, outputs)
        issues.extend(_check_citation_anchoring(workspace, outputs))
        return issues
    if skill == "global-reviewer":
        return _check_global_review(workspace, outputs)
    if skill == "pipeline-auditor":
        return _check_audit_report(workspace, outputs)
    if skill == "latex-scaffold":
        return _check_latex_scaffold(workspace, outputs)
    if skill == "latex-compile-qa":
        return _check_latex_compile_qa(workspace, outputs)
    if skill == "beamer-scaffold":
        return _check_beamer_scaffold(workspace, outputs)
    if skill == "beamer-compile-qa":
        return _check_beamer_compile_qa(workspace, outputs)
    if skill == "artifact-contract-auditor":
        return _check_contract_report(workspace, outputs)
    if skill == "protocol-writer":
        return _check_protocol(workspace, outputs)
    if skill == "source-manifest":
        return _check_source_manifest(workspace, outputs)
    if skill == "source-ingest":
        return _check_source_ingest(workspace, outputs)
    if skill == "source-tutorial-spec":
        return _check_source_tutorial_spec(workspace, outputs)
    if skill == "module-source-coverage":
        return _check_module_source_coverage(workspace, outputs)
    if skill == "tutorial-context-pack":
        return _check_tutorial_context_packs(workspace, outputs)
    if skill == "tutorial-spec":
        return _check_tutorial_spec(workspace, outputs)
    if skill == "tutorial-selfloop":
        return _check_tutorial_selfloop_report(workspace, outputs)
    if skill == "idea-signal-mapper":
        return _check_idea_signal_table(workspace, outputs)
    if skill == "idea-direction-generator":
        return _check_idea_direction_pool(workspace, outputs)
    if skill == "idea-screener":
        return _check_idea_screening_table(workspace, outputs)
    if skill == "idea-shortlist-curator":
        return _check_idea_shortlist(workspace, outputs)
    if skill == "idea-memo-writer":
        return _check_brainstorm_report_bundle(workspace, outputs)
    if skill == "deliverable-selfloop":
        return _check_deliverable_selfloop_report(workspace, outputs)
    return []


def _check_chapter_skeleton(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_yaml

    out_rel = outputs[0] if outputs else "outline/chapter_skeleton.yml"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_chapter_skeleton", message=f"`{out_rel}` does not exist.")]
    data = load_yaml(path)
    if not isinstance(data, list) or not data:
        return [QualityIssue(code="invalid_chapter_skeleton", message=f"`{out_rel}` must be a non-empty YAML list.")]
    missing = 0
    for rec in data:
        if not isinstance(rec, dict):
            missing += 1
            continue
        required = ("id", "title", "rationale", "seed_topics", "target_h3_count")
        if any(not rec.get(key) for key in required):
            missing += 1
            continue
        if not isinstance(rec.get("seed_topics"), list):
            missing += 1
            continue
    if missing:
        return [QualityIssue(code="chapter_skeleton_missing_fields", message=f"`{out_rel}` has {missing} invalid chapter skeleton record(s).")]
    return []


def _check_section_bindings(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    bindings_rel = outputs[0] if outputs else "outline/section_bindings.jsonl"
    report_rel = outputs[1] if len(outputs) >= 2 else "outline/section_binding_report.md"
    bindings_path = workspace / bindings_rel
    report_path = workspace / report_rel
    if not bindings_path.exists():
        return [QualityIssue(code="missing_section_bindings", message=f"`{bindings_rel}` does not exist.")]
    records = [r for r in read_jsonl(bindings_path) if isinstance(r, dict)]
    if not records:
        return [QualityIssue(code="invalid_section_bindings", message=f"`{bindings_rel}` has no JSON objects.")]
    missing = 0
    invalid_status = 0
    invalid_semantics = 0
    derived_records: list[dict[str, Any]] = []
    for rec in records:
        required = ("section_id", "section_title", "paper_ids_primary", "paper_ids_support", "coverage_count", "status", "blocking_gaps", "decomposition_recommendation")
        if any(key not in rec for key in required):
            missing += 1
            continue
        if not isinstance(rec.get("paper_ids_primary"), list) or not isinstance(rec.get("paper_ids_support"), list):
            missing += 1
            continue
        if not isinstance(rec.get("blocking_gaps"), list):
            missing += 1
            continue
        status = str(rec.get("status") or "").strip().upper()
        binding_status = str(rec.get("binding_status") or "").strip().upper()
        recommendation = str(rec.get("decomposition_recommendation") or "").strip().lower()
        blocking_gaps = rec.get("blocking_gaps") or []
        if status not in {"PASS", "BLOCKED", "REROUTE"}:
            invalid_status += 1
            continue
        if binding_status and binding_status not in {"PASS", "BLOCKED", "REROUTE"}:
            invalid_status += 1
            continue
        if binding_status and binding_status != status:
            invalid_semantics += 1
            continue
        if recommendation not in {"decompose", "hold_or_merge"}:
            invalid_semantics += 1
            continue
        if status == "PASS" and (blocking_gaps or recommendation != "decompose"):
            invalid_semantics += 1
            continue
        if status == "BLOCKED" and not blocking_gaps:
            invalid_semantics += 1
            continue
        if status == "REROUTE" and (blocking_gaps or recommendation == "decompose"):
            invalid_semantics += 1
            continue
        derived_records.append(
            {
                "section_id": str(rec.get("section_id") or "").strip(),
                "binding_status": binding_status or status,
                "decomposition_recommendation": recommendation,
                "blocking_gaps": list(blocking_gaps),
            }
        )
    if missing:
        return [QualityIssue(code="section_bindings_missing_fields", message=f"`{bindings_rel}` has {missing} invalid section-binding record(s).")]
    if invalid_status:
        return [QualityIssue(code="section_bindings_invalid_status", message=f"`{bindings_rel}` has {invalid_status} record(s) with unknown binding status (expected PASS/BLOCKED/REROUTE).")]
    if invalid_semantics:
        return [QualityIssue(code="section_bindings_invalid_semantics", message=f"`{bindings_rel}` has {invalid_semantics} record(s) where status, blocking_gaps, and decomposition_recommendation disagree.")]
    if not report_path.exists():
        return [QualityIssue(code="missing_section_binding_report", message=f"`{report_rel}` does not exist.")]
    report = report_path.read_text(encoding="utf-8", errors="ignore")
    rows = _parse_section_binding_report_rows(report)
    if "| Section |" not in report or "| Status |" not in report or not rows:
        return [QualityIssue(code="invalid_section_binding_report", message=f"`{report_rel}` is missing the section binding summary table.")]
    by_section_id: dict[str, dict[str, Any]] = {}
    for rec in derived_records:
        section_id = str(rec.get("section_id") or "").strip()
        if section_id:
            by_section_id[section_id] = rec
    if len(rows) != len(derived_records):
        return [
            QualityIssue(
                code="section_binding_report_row_mismatch",
                message=(
                    f"`{report_rel}` should report one status row per section binding "
                    f"(report rows={len(rows)}, binding rows={len(derived_records)})."
                ),
            )
        ]
    bad_statuses = sorted({str(row.get("status") or "").strip().upper() for row in rows if str(row.get("status") or "").strip().upper() not in {"PASS", "BLOCKED", "REROUTE"}})
    if bad_statuses:
        return [
            QualityIssue(
                code="section_binding_report_bad_status",
                message=f"`{report_rel}` contains unsupported binding statuses: {', '.join(bad_statuses)}.",
            )
        ]
    inconsistent: list[str] = []
    for row in rows:
        label = str(row.get("section") or "").strip()
        section_id = label.split(" ", 1)[0].strip()
        rec = by_section_id.get(section_id) or {}
        binding_status = str(rec.get("binding_status") or "").strip().upper()
        report_status = str(row.get("status") or "").strip().upper()
        recommendation = str(rec.get("decomposition_recommendation") or "").strip().lower()
        blocking_gaps = rec.get("blocking_gaps") or []
        if binding_status != report_status:
            inconsistent.append(f"{section_id}: report={report_status} jsonl={binding_status or 'missing'}")
            continue
        if report_status == "PASS" and (blocking_gaps or recommendation != "decompose"):
            inconsistent.append(f"{section_id}: PASS with non-decompose semantics")
        if report_status == "BLOCKED" and not blocking_gaps:
            inconsistent.append(f"{section_id}: BLOCKED without blocking_gaps")
        if report_status == "REROUTE" and (blocking_gaps or recommendation == "decompose"):
            inconsistent.append(f"{section_id}: REROUTE without hold_or_merge semantics")
    if inconsistent:
        return [
            QualityIssue(
                code="section_binding_report_drift",
                message=(
                    f"`{bindings_rel}` and `{report_rel}` disagree about section-binding gate state: "
                    f"{', '.join(inconsistent[:6])}."
                ),
            )
        ]
    return []


def _check_section_briefs(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    out_rel = outputs[0] if outputs else "outline/section_briefs.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_section_briefs", message=f"`{out_rel}` does not exist.")]
    records = [r for r in read_jsonl(path) if isinstance(r, dict)]
    if not records:
        return [QualityIssue(code="invalid_section_briefs", message=f"`{out_rel}` has no JSON objects.")]
    missing = 0
    for rec in records:
        required = ("section_id", "section_title", "section_rationale", "contrast_lens", "must_cover", "target_h3_count", "subsection_seeds", "status", "decomposition_recommendation", "blocking_gaps")
        if any(key not in rec for key in required):
            missing += 1
            continue
        if not isinstance(rec.get("contrast_lens"), list) or not isinstance(rec.get("must_cover"), list) or not isinstance(rec.get("subsection_seeds"), list) or not isinstance(rec.get("blocking_gaps"), list):
            missing += 1
            continue
        status = str(rec.get("status") or "").strip().upper()
        binding_status = str(rec.get("binding_status") or "").strip().upper()
        recommendation = str(rec.get("decomposition_recommendation") or "").strip().lower()
        blocking_gaps = rec.get("blocking_gaps") or []
        if status not in {"PASS", "BLOCKED", "REROUTE"}:
            missing += 1
            continue
        if binding_status and binding_status not in {"PASS", "BLOCKED", "REROUTE"}:
            missing += 1
            continue
        if binding_status and status != binding_status:
            missing += 1
            continue
        if recommendation not in {"decompose", "hold_or_merge"}:
            missing += 1
            continue
        if status == "PASS" and (blocking_gaps or recommendation != "decompose"):
            missing += 1
            continue
        if status == "BLOCKED" and not blocking_gaps:
            missing += 1
            continue
        if status == "REROUTE" and (blocking_gaps or recommendation == "decompose"):
            missing += 1
            continue
    if missing:
        return [QualityIssue(code="section_briefs_missing_fields", message=f"`{out_rel}` has {missing} invalid section brief record(s).")]
    return []


def _check_idea_brief(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    def _required_sections() -> list[str]:
        repo_root = Path(__file__).resolve().parents[1]
        asset_path = repo_root / ".codex" / "skills" / "idea-brief" / "assets" / "brief_contract.json"
        data = json.loads(asset_path.read_text(encoding="utf-8"))
        sections = data.get("required_sections")
        if not isinstance(sections, list) or not sections:
            raise ValueError("idea-brief required_sections is missing or empty")
        return [f"## {str(section or '').strip()}" for section in sections if str(section or "").strip()]

    brief_rel = next((p for p in outputs if p.endswith("IDEA_BRIEF.md")), "output/trace/IDEA_BRIEF.md")
    path = workspace / brief_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code="missing_idea_brief", message=f"`{brief_rel}` is missing or empty.")]
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        required = _required_sections()
    except Exception as exc:
        return [QualityIssue(code="idea_brief_contract_unreadable", message=f"Failed to load `idea-brief` contract asset ({type(exc).__name__}: {exc}).")]
    missing = [h for h in required if h not in text]
    if missing:
        return [QualityIssue(code="idea_brief_missing_sections", message=f"`{brief_rel}` is missing required sections: {', '.join(missing)}")]
    queries_path = workspace / "queries.md"
    if not queries_path.exists() or queries_path.stat().st_size == 0:
        return [QualityIssue(code="idea_brief_missing_queries", message="`queries.md` is missing after `idea-brief`.")]
    q = queries_path.read_text(encoding="utf-8", errors="ignore")
    if "draft_profile: \"idea_brainstorm\"" not in q and "draft_profile: 'idea_brainstorm'" not in q and "draft_profile: idea_brainstorm" not in q:
        return [QualityIssue(code="idea_brief_missing_draft_profile", message="`queries.md` should set `draft_profile: idea_brainstorm`.")]
    kw_n = 0
    in_keywords = False
    for raw in q.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith('- keywords:'):
            in_keywords = True
            continue
        if stripped.startswith('- ') and not line.startswith('  - '):
            if in_keywords:
                break
        if in_keywords and line.startswith('  - ') and stripped[4:].strip():
            kw_n += 1
    if kw_n < 3:
        return [QualityIssue(code="idea_brief_too_few_query_buckets", message="`queries.md` should contain at least 3 keyword buckets for ideation retrieval.")]
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



def _check_idea_signal_table(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = next((p for p in outputs if p.endswith("IDEA_SIGNAL_TABLE.md")), "output/trace/IDEA_SIGNAL_TABLE.md")
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code="missing_idea_signal_table", message=f"`{out_rel}` is missing or empty.")]
    contract, issues = _load_idea_contract_for_quality(workspace)
    if issues:
        return issues
    text = path.read_text(encoding="utf-8", errors="ignore")
    if _check_placeholder_markers(text) or "…" in text:
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


def _check_idea_direction_pool(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = next((p for p in outputs if p.endswith("IDEA_DIRECTION_POOL.md")), "output/trace/IDEA_DIRECTION_POOL.md")
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code="missing_idea_direction_pool", message=f"`{out_rel}` is missing or empty.")]
    contract, issues = _load_idea_contract_for_quality(workspace)
    if issues:
        return issues
    text = path.read_text(encoding="utf-8", errors="ignore")
    if _check_placeholder_markers(text) or "…" in text:
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


def _check_idea_screening_table(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = next((p for p in outputs if p.endswith("IDEA_SCREENING_TABLE.md")), "output/trace/IDEA_SCREENING_TABLE.md")
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code="missing_idea_screening_table", message=f"`{out_rel}` is missing or empty.")]
    contract, issues = _load_idea_contract_for_quality(workspace)
    if issues:
        return issues
    text = path.read_text(encoding="utf-8", errors="ignore")
    if _check_placeholder_markers(text) or "…" in text:
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


def _check_idea_shortlist(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_workspace_pipeline_spec

    out_rel = next((p for p in outputs if p.endswith("IDEA_SHORTLIST.md")), "output/trace/IDEA_SHORTLIST.md")
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code="missing_idea_shortlist", message=f"`{out_rel}` is missing or empty.")]
    if load_workspace_pipeline_spec(workspace) is None:
        return [QualityIssue(code="missing_idea_pipeline_contract", message="Missing or invalid active ideation pipeline contract; check `PIPELINE.lock.md` and pipeline metadata.")]
    text = path.read_text(encoding="utf-8", errors="ignore")
    if _check_placeholder_markers(text) or "…" in text:
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


def _check_brainstorm_report_bundle(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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
    if _check_placeholder_markers(text) or "…" in text:
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


def _check_deliverable_selfloop_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    report_rel = next((p for p in outputs if p.endswith("DELIVERABLE_SELFLOOP_TODO.md")), "output/DELIVERABLE_SELFLOOP_TODO.md")
    report_path = workspace / report_rel
    if not report_path.exists() or report_path.stat().st_size == 0:
        return [QualityIssue(code="missing_deliverable_selfloop_report", message=f"`{report_rel}` is missing or empty.")]
    text = report_path.read_text(encoding="utf-8", errors="ignore")
    if _check_placeholder_markers(text) or "…" in text:
        return [QualityIssue(code="deliverable_selfloop_placeholders", message=f"`{report_rel}` contains placeholders/ellipsis.")]
    if "- Status: PASS" not in text:
        return [QualityIssue(code="deliverable_selfloop_not_pass", message=f"`{report_rel}` is not PASS.")]
    return []


def _check_citation_injection(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    report_rel = next((p for p in outputs if p.endswith("CITATION_INJECTION_REPORT.md")), "output/CITATION_INJECTION_REPORT.md")
    report_path = workspace / report_rel
    if not report_path.exists() or report_path.stat().st_size == 0:
        return [QualityIssue(code="missing_citation_injection_report", message=f"`{report_rel}` is missing or empty.")]

    text = report_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_citation_injection_report", message=f"`{report_rel}` is empty.")]
    if _check_placeholder_markers(text) or "…" in text:
        return [
            QualityIssue(
                code="citation_injection_report_placeholders",
                message=f"`{report_rel}` contains placeholders/ellipsis; regenerate after fixing the injection step.",
            )
        ]
    if re.search(r"(?im)^-\s*Status:\s*PASS\b", text):
        return []
    return [
        QualityIssue(
            code="citation_injection_failed",
            message=f"`{report_rel}` is not PASS; add more in-scope unused citations (or expand C1/C2 mapping), then rerun citation injection.",
        )
    ]


def _check_pdf_text_extractor(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    out_rel = outputs[0] if outputs else "papers/fulltext_index.jsonl"
    path = workspace / out_rel
    records = read_jsonl(path) if path.exists() else []
    if not records:
        return [QualityIssue(code="empty_fulltext_index", message=f"`{out_rel}` is missing or empty.")]

    mode = _evidence_mode(workspace)
    if mode != "fulltext":
        # Abstract/snippet mode: do not require extracted text coverage.
        return []

    ok = 0
    missing_url = 0
    for rec in records:
        if not isinstance(rec, dict):
            continue
        status = str(rec.get("status") or "").strip()
        pdf_url = str(rec.get("pdf_url") or "").strip()
        chars = int(rec.get("chars_extracted") or 0)
        if not pdf_url:
            missing_url += 1
        if status.startswith("ok") and chars >= 1500:
            ok += 1

    total = max(1, len([r for r in records if isinstance(r, dict)]))
    # In strict mode, we want at least some real full-text extraction before synthesis.
    min_ok = 5 if total >= 10 else 1
    if ok < min_ok:
        hint = "Run with network access, or reduce scope, or provide PDFs manually under `papers/pdfs/`."
        return [
            QualityIssue(
                code="fulltext_too_few",
                message=f"Only {ok}/{total} papers have extracted text (>=1500 chars). {hint}",
            )
        ]
    if missing_url / total >= 0.7:
        return [
            QualityIssue(
                code="fulltext_missing_pdf_urls",
                message="Most records have empty `pdf_url`; ensure `core_set.csv` includes `pdf_url`/`arxiv_id` or use arXiv online mode.",
            )
        ]
    return []


def write_quality_report(*, workspace: Path, unit_id: str, skill: str, issues: list[QualityIssue]) -> Path:
    from tooling.common import atomic_write_text, ensure_dir

    ensure_dir(workspace / "output")
    report_path = workspace / "output" / "QUALITY_GATE.md"

    now = datetime.now().replace(microsecond=0).isoformat()
    status = "PASS" if not issues else "FAIL"
    lines: list[str] = [
        "# Quality gate report",
        "",
        f"- Timestamp: `{now}`",
        f"- Unit: `{unit_id}`",
        f"- Skill: `{skill}`",
        "",
        "## Status",
        "",
        f"- {status}",
        "",
        "## Issues",
        "",
    ]
    if issues:
        for issue in issues:
            lines.append(f"- `{issue.code}`: {issue.message}")
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("## Next action")
    lines.append("")
    if issues:
        for ln in _next_action_lines(skill=skill, unit_id=unit_id):
            lines.append(ln)
    else:
        lines.append("- Proceed to the next unit.")
    lines.append("")

    entry = "\n".join(lines).rstrip() + "\n"

    # Append-only by default: keep a history of quality-gate outcomes in the workspace.
    # This makes failures debuggable without rerunning (and preserves context across retries).
    if report_path.exists() and report_path.stat().st_size > 0:
        prev = report_path.read_text(encoding="utf-8", errors="ignore").rstrip() + "\n\n---\n\n"
        atomic_write_text(report_path, prev + entry)
    else:
        atomic_write_text(report_path, entry)
    return report_path


def _next_action_lines(*, skill: str, unit_id: str) -> list[str]:
    skill_md = f".codex/skills/{skill}/SKILL.md"
    common = [
        "- Treat the current outputs as a starting point (often a scaffold).",
        f"- Follow `{skill_md}` to refine the required artifacts until the issues above no longer apply.",
        f"- Then mark `{unit_id}` as `DONE` in `UNITS.csv` (or run `uv run python scripts/pipeline.py mark --workspace <workspace> --unit-id {unit_id} --status DONE --note \"LLM refined\"`, replacing `<workspace>` with the run directory).",
    ]

    by_skill: dict[str, list[str]] = {
        "literature-engineer": [
            "- Provide multiple offline exports under `papers/imports/` (different queries/routes) to reach a large candidate pool (survey target: >=200).",
            "- Ensure most records contain stable IDs (`arxiv_id`/`doi`) and non-empty `url`; prefer arXiv/OpenReview/ACL exports with IDs.",
            "- If network is available, rerun with `--online` (and optionally `--snowball`) to expand coverage via arXiv API and citation graph.",
        ],
        "dedupe-rank": [
            "- Inspect `papers/papers_raw.jsonl`: ensure `title/year/url/authors` are present and not empty; fix/replace the offline export if needed.",
            "- Rerun dedupe with an appropriate `--core-size` to get a usable `papers/core_set.csv` (with stable `paper_id`).",
        ],
        "taxonomy-builder": [
            "- Edit `outline/taxonomy.yml`: replace all `TODO` / placeholder text with domain-meaningful node names and 1–2 sentence descriptions.",
            "- Ensure taxonomy has ≥2 levels (uses `children`) and avoids generic buckets like “Overview/Benchmarks/Open Problems”.",
        ],
        "outline-builder": [
            "- Edit `outline/outline.yml`: rewrite every `TODO` bullet into topic-specific, checkable bullets (axes, comparisons, evaluation setups, failure modes).",
            "- Keep it bullets-only (no prose paragraphs).",
        ],
        "section-mapper": [
            "- Edit `outline/mapping.tsv`: diversify mapped papers per subsection and reduce over-reuse of a few papers across unrelated sections.",
            "- Replace generic `why` (e.g., `matched_terms=...`) with a short semantic rationale (mechanism/task/benchmark/safety angle).",
            "- Use `outline/mapping_report.md` to find hotspots and weak-signal subsections.",
        ],
        "paper-notes": [
            "- Edit `papers/paper_notes.jsonl`: fully enrich `priority=high` papers (method, key_results, concrete limitations) and remove all `TODO`s.",
            "- Long-tail papers can remain abstract-level, but avoid copy-pasted limitation boilerplate across many records.",
        ],
        "claim-evidence-matrix": [
            "- Edit `outline/claim_evidence_matrix.md`: rewrite template-y claims into specific, falsifiable claims per subsection.",
            "- For each claim, keep ≥2 evidence sources (paper IDs) and add caveats when evidence is abstract-only.",
        ],
        "pdf-text-extractor": [
            "- If you want to avoid downloads, keep `evidence_mode: \"abstract\"` in `queries.md` (it will emit skip records).",
            "- For full-text evidence: set `evidence_mode: \"fulltext\"`, ensure `papers/core_set.csv` has `pdf_url`/`arxiv_id`, or provide PDFs under `papers/pdfs/`.",
            "- Consider `--local-pdfs-only` and add a small set of PDFs manually to unblock strict mode.",
        ],
        "citation-verifier": [
            "- Ensure every `papers/paper_notes.jsonl` record has a stable `bibkey`, `title`, and canonical `url`.",
            "- Regenerate `citations/ref.bib` + `citations/verified.jsonl` and ensure every bibkey has a verification record with `url/date/title`.",
            "- If offline, use `verification_status=offline_generated` and plan a later `--verify-only` pass when network is available.",
        ],
        "survey-visuals": [
            "- Tables are handled by table skills: `table-schema` (schema) → `table-filler` (index: `outline/tables_index.md`) → `appendix-table-writer` (reader tables: `outline/tables_appendix.md`).",
            "- Fill `outline/timeline.md` with ≥8 milestone bullets (year + cited works).",
            "- Fill `outline/figures.md` with ≥2 figure specs (purpose, elements, supporting citations).",
        ],
        "subsection-writer": [
            "- Write per-unit prose files under `sections/` (small, verifiable units):",
            "  - `sections/abstract.md` (`## Abstract`), `sections/discussion.md`, `sections/conclusion.md`.",
            "  - `sections/S<section_id>.md` for H2 sections without H3 (body only).",
            "  - `sections/S<sub_id>.md` for each H3 (body only; no headings).",
            "- Each H3 file should have >=3 unique citations and avoid ellipsis/TODO/template boilerplate.",
            "- Keep H3 citations subsection-first: cite keys mapped in `outline/evidence_bindings.jsonl` for that H3; limited reuse from sibling H3s in the same H2 chapter is allowed; avoid cross-chapter “free cite”.",
            "- After files exist, run `writer-selfloop` to enforce draft-profile depth/scope and to generate an actionable fix plan (`output/WRITER_SELFLOOP_TODO.md`).",
        ],
        "writer-selfloop": [
            "- Open `output/WRITER_SELFLOOP_TODO.md` and fix only the failing `sections/*.md` files listed there (do not rewrite everything).",
            "- Keep citations in-scope (per `outline/evidence_bindings.jsonl` / writer packs) and avoid narration templates (`This subsection ...`, `Next, we ...`).",
            "- Rerun the `writer-selfloop` script until the report shows `- Status: PASS`, then proceed to the next unit.",
            "- If the failures point to thin evidence (missing anchors/comparisons/limitations), loop upstream: `paper-notes` → `evidence-binder` → `evidence-draft` → `anchor-sheet` → `writer-context-pack`.",
        ],
        "evaluation-anchor-checker": [
            "- Open `output/EVAL_ANCHOR_REPORT.md` and confirm it reports a non-zero `Files checked` count.",
            "- Keep numbers only when the same sentence carries enough task/metric/constraint context; otherwise weaken the claim without changing citation keys.",
            "- If later section-level rewrites touch the same H3 files, rerun `evaluation-anchor-checker` before merge instead of waiting for `pipeline-auditor`.",
        ],
        "section-merger": [
            "- Ensure all required `sections/*.md` exist (see `output/MERGE_REPORT.md` for missing paths), then rerun merge.",
            "- After merge, polish/review the combined `output/DRAFT.md` (then run `pipeline-auditor` before LaTeX).",
        ],
        "post-merge-voice-gate": [
            "- Open `output/POST_MERGE_VOICE_REPORT.md` and fix the earliest responsible artifact it points to.",
            "- If the report says `source: transitions`: rewrite `outline/transitions.md` as content-bearing argument bridges (no planner talk, no A/B/C slash labels), then rerun `section-merger` and this gate.",
            "- If the report says `source: draft`: route to `writer-selfloop` / `subsection-polisher` / `draft-polisher` for the flagged section, then rerun `section-merger` and this gate.",
        ],
        "prose-writer": [
            "- Treat any leaked scaffold text (`…`, `enumerate 2-4 ...`, 'Scope and definitions ...') as a HARD FAIL: fix outline/claims first, then draft.",
            "- For each subsection, write a unique thesis + 2 contrast sentences (A vs B) + 1 failure mode, each backed by citations.",
            "- Use concrete axes (datasets/metrics/compute/training/sampling/failure modes), not generic \"design space\" prose.",
            "- Keep citations evidence-first: paragraph-level cites; keys must exist in `citations/ref.bib`.",
            "- Ensure paper-like structure exists: Introduction, (optional) Related Work, 3–4 core chapters, Discussion/Future Work, Conclusion.",
        ],
        "latex-scaffold": [
            "- Edit `latex/main.tex`: remove any leaked markdown (`##`, `**`, `[@...]`) and ensure bibliography points to `../citations/ref.bib`.",
        ],
        "latex-compile-qa": [
            "- Open `output/LATEX_BUILD_REPORT.md` and fix the first compile error (missing package, missing bib, bad cite key).",
            "- Ensure `latexmk` is installed and `latex/main.tex` references `../citations/ref.bib`.",
        ],
        "arxiv-search": [
            "- Ensure `papers/papers_raw.jsonl` contains real records (not placeholders) and rerun the unit if needed.",
        ],
    }

    out: list[str] = []
    out.extend(by_skill.get(skill, []))
    out.extend(common)
    return out


def _check_arxiv_search(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    out_rel = outputs[0] if outputs else "papers/papers_raw.jsonl"
    path = workspace / out_rel
    records = read_jsonl(path)
    if not records:
        return [QualityIssue(code="empty_raw", message=f"No records found in `{out_rel}`.")]

    placeholders = 0
    arxiv_sources = 0
    id_fetch = 0
    for rec in records:
        title = str(rec.get("title") or "").strip()
        url = str(rec.get("url") or rec.get("id") or "").strip()
        if title.lower().startswith("(placeholder)") or "0000.00000" in url:
            placeholders += 1
        if str(rec.get("source") or "").strip().lower() == "arxiv":
            arxiv_sources += 1
        q = rec.get("query")
        if isinstance(q, list) and len(q) == 1:
            v = str(q[0] or "").strip()
            if re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", v) or re.fullmatch(r"[a-z-]+(?:\.[a-z-]+)?/\d{7}(?:v\d+)?", v):
                id_fetch += 1
    if placeholders:
        return [
            QualityIssue(
                code="placeholder_records",
                message=f"`{out_rel}` contains placeholder/demo records ({placeholders}); workspace template should start empty.",
            )
        ]
    # Only enforce keyword hygiene when this looks like an online arXiv retrieval.
    if arxiv_sources:
        # If the run is a direct id_list fetch, queries.md keywords are optional.
        if id_fetch:
            return []
        return _check_keyword_expansion(workspace)
    return []


def _check_literature_engineer(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    out_rel = outputs[0] if outputs else "papers/papers_raw.jsonl"
    report_rel = outputs[1] if len(outputs) >= 2 else "papers/retrieval_report.md"

    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_raw", message=f"`{out_rel}` does not exist.")]
    records = read_jsonl(path)
    if not records:
        return [QualityIssue(code="empty_raw", message=f"No records found in `{out_rel}`.")]

    report_path = workspace / report_rel
    if not report_path.exists():
        return [QualityIssue(code="missing_retrieval_report", message=f"`{report_rel}` does not exist.")]
    report = report_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not report or "Retrieval report" not in report:
        return [QualityIssue(code="bad_retrieval_report", message=f"`{report_rel}` is empty or not a retrieval report.")]

    total = len([r for r in records if isinstance(r, dict)])
    missing_title = 0
    missing_url = 0
    missing_year = 0
    missing_authors = 0
    missing_abstract = 0
    missing_stable_id = 0
    missing_prov = 0
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if not str(rec.get("title") or "").strip():
            missing_title += 1
        if not str(rec.get("url") or rec.get("id") or "").strip():
            missing_url += 1
        year = str(rec.get("year") or "").strip()
        if not year:
            missing_year += 1
        authors = rec.get("authors") or []
        if not isinstance(authors, list) or not [a for a in authors if str(a).strip()]:
            missing_authors += 1
        if not str(rec.get("abstract") or "").strip():
            missing_abstract += 1
        if not str(rec.get("arxiv_id") or "").strip() and not str(rec.get("doi") or "").strip():
            missing_stable_id += 1
        prov = rec.get("provenance")
        if not isinstance(prov, list) or len([p for p in prov if isinstance(p, dict)]) == 0:
            missing_prov += 1

    issues: list[QualityIssue] = []
    if missing_title:
        issues.append(QualityIssue(code="raw_missing_titles", message=f"`{out_rel}` has {missing_title} record(s) missing `title`."))
    if missing_url:
        issues.append(QualityIssue(code="raw_missing_urls", message=f"`{out_rel}` has {missing_url} record(s) missing `url`."))
    if missing_year / max(1, total) >= 0.25:
        issues.append(
            QualityIssue(
                code="raw_missing_years",
                message=f"Many records are missing `year` ({missing_year}/{total}); prefer richer exports or enable online metadata backfill.",
            )
        )
    if missing_authors / max(1, total) >= 0.25:
        issues.append(
            QualityIssue(
                code="raw_missing_authors",
                message=f"Many records are missing `authors` ({missing_authors}/{total}); prefer richer exports or enable online metadata backfill.",
            )
        )
    if missing_prov / max(1, total) >= 0.1:
        issues.append(
            QualityIssue(
                code="raw_missing_provenance",
                message=f"Many records are missing `provenance` ({missing_prov}/{total}); ensure imports are labeled and provenance is preserved through dedupe.",
            )
        )

    profile = _pipeline_profile(workspace)
    if profile == "arxiv-survey":
        min_raw = max(200, int(_core_size(workspace)) * 4)
        if total < min_raw:
            issues.append(
                QualityIssue(
                    code="raw_too_small",
                    message=f"`{out_rel}` has {total} records; target >= {min_raw} for survey-quality runs (expand queries/imports/snowballing; raise `max_results` and add more buckets).",
                )
            )
        if missing_stable_id / max(1, total) >= 0.2:
            issues.append(
                QualityIssue(
                    code="raw_missing_stable_ids",
                    message=f"Too many records lack stable IDs (arxiv_id/doi) ({missing_stable_id}/{total}); filter bad exports or enrich metadata before citations.",
                )
            )
        # Evidence-first: if we're not extracting full text, we need abstracts for non-hallucinated notes/drafting.
        evidence_mode = _evidence_mode(workspace)
        if evidence_mode != "fulltext" and missing_abstract / max(1, total) >= 0.7:
            issues.append(
                QualityIssue(
                    code="raw_missing_abstracts",
                    message=(
                        f"Most records are missing `abstract` ({missing_abstract}/{total}); "
                        "provide richer exports (e.g., Semantic Scholar/OpenAlex JSONL/CSV, Zotero export with abstracts) "
                        "or enable online metadata enrichment, otherwise notes/claims/draft will collapse into title-only templates."
                    ),
                )
            )

    return issues


def _check_dedupe_rank(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    dedup_rel = outputs[0] if outputs else "papers/papers_dedup.jsonl"
    core_rel = outputs[1] if len(outputs) >= 2 else "papers/core_set.csv"
    path = workspace / core_rel
    if not path.exists():
        return [QualityIssue(code="missing_core_set", message=f"`{core_rel}` does not exist.")]

    try:
        import csv

        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = [row for row in reader]
    except Exception as exc:
        return [QualityIssue(code="invalid_core_set", message=f"Failed to read `{core_rel}`: {exc}")]

    if not rows:
        return [QualityIssue(code="empty_core_set", message=f"`{core_rel}` has no rows.")]

    missing_id = 0
    missing_title = 0
    ids: list[str] = []
    for row in rows:
        pid = str(row.get("paper_id") or "").strip()
        title = str(row.get("title") or "").strip()
        if not pid:
            missing_id += 1
        else:
            ids.append(pid)
        if not title:
            missing_title += 1

    issues: list[QualityIssue] = []
    if missing_id:
        issues.append(
            QualityIssue(
                code="core_set_missing_paper_id",
                message=f"`{core_rel}` has {missing_id} row(s) missing `paper_id`; ensure stable IDs for downstream mapping/citations.",
            )
        )
    if missing_title:
        issues.append(
            QualityIssue(
                code="core_set_missing_title",
                message=f"`{core_rel}` has {missing_title} row(s) missing `title`; fix upstream normalization/dedupe.",
            )
        )
    if ids and len(set(ids)) != len(ids):
        issues.append(QualityIssue(code="core_set_duplicate_ids", message=f"`{core_rel}` contains duplicate `paper_id` values."))

    profile = _pipeline_profile(workspace)
    if profile == "arxiv-survey":
        min_core = int(_core_size(workspace))
        if len(rows) < min_core:
            issues.append(
                QualityIssue(
                    code="core_set_too_small",
                    message=f"`{core_rel}` has {len(rows)} rows; target >= {min_core} for survey-quality coverage (increase candidate pool and set `core_size`).",
                )
            )

        # Scope drift heuristic (evidence-first): if the goal says text-to-image but the core set is heavy on video,
        # block early so the C2 scope decision can be tightened (exclude terms) or the goal can be widened explicitly.
        goal_path = workspace / "GOAL.md"
        goal = ""
        if goal_path.exists():
            for raw in goal_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith(("-", ">", "<!--")):
                    continue
                low = line.lower()
                if "写一句话描述" in line or "fill" in low:
                    continue
                goal = line
                break
        goal_low = goal.lower()
        if goal_low and ("text-to-image" in goal_low or "text to image" in goal_low or "t2i" in goal_low):
            # Only flag drift when video isn't explicitly part of the goal.
            if "video" not in goal_low and "text-to-video" not in goal_low and "text to video" not in goal_low and "t2v" not in goal_low:
                video_titles = sum(1 for r in rows if "video" in str(r.get("title") or "").lower())
                audio_titles = sum(1 for r in rows if "audio" in str(r.get("title") or "").lower())
                denom = max(1, len(rows))
                if video_titles >= 10 and (video_titles / denom) >= 0.15:
                    issues.append(
                        QualityIssue(
                            code="scope_drift_video",
                            message=(
                                f"GOAL suggests text-to-image, but {video_titles}/{len(rows)} core papers mention video "
                                f"(audio={audio_titles}). Tighten `queries.md` excludes / filters, or explicitly broaden scope at C2."
                            ),
                        )
                    )
        dedup_path = workspace / dedup_rel
        dedup = read_jsonl(dedup_path)
        min_dedup = max(200, int(min_core) * 4) if min_core else 200
        if len([r for r in dedup if isinstance(r, dict)]) < min_dedup:
            issues.append(
                QualityIssue(
                    code="dedup_pool_too_small",
                    message=f"`{dedup_rel}` has too few deduplicated records for a survey run; target >= {min_dedup} (expand retrieval/snowballing first).",
                )
            )
    return issues


def _check_citations(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    bib_rel = outputs[0] if outputs else "citations/ref.bib"
    verified_rel = outputs[1] if len(outputs) >= 2 else "citations/verified.jsonl"

    bib_path = workspace / bib_rel
    verified_path = workspace / verified_rel

    if not bib_path.exists():
        return [QualityIssue(code="missing_ref_bib", message=f"`{bib_rel}` does not exist.")]
    if not verified_path.exists():
        return [QualityIssue(code="missing_verified_jsonl", message=f"`{verified_rel}` does not exist.")]

    bib_text = bib_path.read_text(encoding="utf-8", errors="ignore")
    bib_keys = re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text)
    if not bib_keys:
        return [QualityIssue(code="empty_ref_bib", message=f"`{bib_rel}` has no BibTeX entries.")]

    dupes = len(bib_keys) - len(set(bib_keys))
    if dupes:
        return [
            QualityIssue(
                code="citations_duplicate_bibkeys",
                message=f"`{bib_rel}` has duplicate BibTeX keys ({dupes}); dedupe/rename keys before compiling LaTeX.",
            )
        ]

    profile = _pipeline_profile(workspace)
    if profile == "arxiv-survey":
        min_bib = int(_core_size(workspace)) or 150
        if len(bib_keys) < min_bib:
            return [
                QualityIssue(
                    code="citations_too_few_entries",
                    message=f"`{bib_rel}` has only {len(bib_keys)} entries; target >= {min_bib} for a survey-quality run (expand retrieval / snowball / imports).",
                )
            ]

    records = read_jsonl(verified_path)
    recs = [r for r in records if isinstance(r, dict)]
    if not recs:
        return [QualityIssue(code="empty_verified_jsonl", message=f"`{verified_rel}` is empty.")]

    by_key: dict[str, dict] = {}
    for rec in recs:
        key = str(rec.get("bibkey") or "").strip()
        if key:
            by_key[key] = rec

    missing = [k for k in bib_keys if k not in by_key]
    if missing:
        sample = ", ".join(missing[:5])
        suffix = "..." if len(missing) > 5 else ""
        return [
            QualityIssue(
                code="citations_missing_verification_records",
                message=f"Some BibTeX keys have no matching verification record in `{verified_rel}` (e.g., {sample}{suffix}).",
            )
        ]

    bad_fields = 0
    for k in bib_keys:
        rec = by_key.get(k) or {}
        title = str(rec.get("title") or "").strip()
        url = str(rec.get("url") or "").strip()
        date = str(rec.get("date") or "").strip()
        if not title or not url or not date:
            bad_fields += 1
            continue
        status = str(rec.get("verification_status") or "").strip()
        if status and status not in {"verified_online", "offline_generated", "verify_failed", "needs_manual_verification"}:
            bad_fields += 1

    if bad_fields:
        return [
            QualityIssue(
                code="citations_invalid_verification_records",
                message=f"`{verified_rel}` has {bad_fields} record(s) missing required fields or with unknown `verification_status`.",
            )
        ]
    return []


def _check_taxonomy(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_yaml

    out_rel = outputs[0] if outputs else "outline/taxonomy.yml"
    path = workspace / out_rel
    if path.exists():
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if _check_placeholder_markers(raw):
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
            if desc.startswith("Papers and ideas centered on '") or desc.startswith("Key aspects of '"):
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

    short, denom = _check_short_descriptions(desc_values, min_chars=32)
    if denom and short / denom >= 0.6:
        issues.append(
            QualityIssue(
                code="taxonomy_short_descriptions",
                message="Many taxonomy node descriptions are very short; expand descriptions with concrete scope cues and representative works.",
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


def _check_outline(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_workspace_pipeline_spec, load_yaml

    out_rel = outputs[0] if outputs else "outline/outline.yml"
    path = workspace / out_rel
    if path.exists():
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if _check_placeholder_markers(raw):
            return [
                QualityIssue(
                    code="outline_scaffold",
                    message="Outline still contains placeholder/TODO bullets; rewrite each subsection with topic-specific, checkable bullets.",
                )
            ]
    outline = load_yaml(path) if path.exists() else None
    if not isinstance(outline, list) or not outline:
        return [QualityIssue(code="invalid_outline", message=f"`{out_rel}` is missing or not a YAML list.")]

    section_first_issues = _section_first_artifact_issues(workspace, consumer=out_rel)
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
    profile = _pipeline_profile(workspace)
    if profile == "arxiv-survey":
        draft_profile = _draft_profile(workspace)
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
        max_final_h2 = _quality_contract_int(
            workspace,
            keys=("structure_policy", "max_final_h2_by_profile", draft_profile),
            default=9 if draft_profile == "deep" else 8,
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
        max_h3 = _quality_contract_int(
            workspace,
            keys=("structure_policy", "max_h3_by_profile", draft_profile),
            default=12 if draft_profile == "deep" else 10,
        )

        spec = load_workspace_pipeline_spec(workspace)
        if spec is not None and str(spec.structure_mode or "").strip().lower() == "section_first":
            core_sections = 0
            for section in outline:
                if not isinstance(section, dict):
                    continue
                title = str(section.get("title") or "").strip().lower()
                subs = section.get("subsections") or []
                if title in {"introduction", "related work"}:
                    continue
                if isinstance(subs, list) and subs:
                    core_sections += 1
            target_h3 = int(getattr(spec, "core_chapter_h3_target", 0) or 0)
            if core_sections > 0 and target_h3 > 0:
                # The explicit section-first contract should not be self-contradictory:
                # if the pipeline declares a target H3 budget per core chapter, the
                # global survey H3 cap must allow that chapter plan to materialize.
                max_h3 = max(max_h3, core_sections * target_h3)

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


def _check_mapping(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_yaml, read_tsv

    out_rel = outputs[0] if outputs else "outline/mapping.tsv"
    path = workspace / out_rel
    rows = read_tsv(path)
    if not rows:
        return [QualityIssue(code="empty_mapping", message=f"`{out_rel}` has no rows.")]

    issues: list[QualityIssue] = []
    issues.extend(_section_first_artifact_issues(workspace, consumer=out_rel))

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

        profile = _pipeline_profile(workspace)
        per_subsection = int(_per_subsection(workspace)) if profile == "arxiv-survey" else 3

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


def _check_paper_notes(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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
            if _pipeline_profile(workspace) == "arxiv-survey":
                # Default contract: >=7 addressable evidence items per paper on average.
                min_items = max(len(seen), int(len(seen) * 7))
                if len(bank) < min_items:
                    issues.append(
                        QualityIssue(
                            code="evidence_bank_too_small",
                            message=(
                                f"`{bank_rel}` has {len(bank)} items for {len(seen)} papers; "
                                f"A150++ expects >= {min_items} (>=7 items/paper on average)."
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


def _check_claim_evidence_matrix(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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


def _check_subsection_briefs(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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
    if _check_placeholder_markers(raw):
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
    cutover_issues = _section_first_artifact_issues(workspace, consumer=out_rel)
    cutover_issues.extend(_section_first_cutover_issues(workspace, consumer=out_rel, require_stable_h3=True))
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

    profile = _pipeline_profile(workspace)
    # Survey default: paragraph plans must be thick enough to prevent 1–2 paragraph stubs downstream.
    min_plan_len = 8 if profile == "arxiv-survey" else 2

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
        if len(thesis) < 24 or _check_placeholder_markers(thesis) or "…" in thesis:
            bad += 1
            continue

        tension = str(rec.get("tension_statement") or "").strip()
        if len(tension) < 24 or _check_placeholder_markers(tension) or "…" in tension:
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


def _check_chapter_briefs(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_yaml, read_jsonl

    out_rel = outputs[0] if outputs else "outline/chapter_briefs.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_chapter_briefs", message=f"`{out_rel}` does not exist.")]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        return [QualityIssue(code="empty_chapter_briefs", message=f"`{out_rel}` is empty.")]
    if _check_placeholder_markers(raw) or "…" in raw:
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


def _check_coverage_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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
    if _check_placeholder_markers(report) or "…" in report:
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
    cutover_issues = _section_first_artifact_issues(workspace, consumer=report_rel)
    cutover_issues.extend(_section_first_cutover_issues(workspace, consumer=report_rel, require_stable_h3=True))
    if cutover_issues:
        return cutover_issues
    if _structure_mode(workspace) == "section_first":
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


def _check_evidence_drafts(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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
    if _check_placeholder_markers(raw):
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
    profile = _pipeline_profile(workspace)
    draft_profile = _draft_profile(workspace)
    min_comparisons = 3
    if profile == "arxiv-survey":
        min_comparisons = 6 if draft_profile == "deep" else 4
        min_snippets = 14 if draft_profile == "deep" else 12
        min_eval = 6 if draft_profile == "deep" else 5
        min_fail = 6 if draft_profile == "deep" else 5
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


def _check_anchor_sheet(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    out_rel = outputs[0] if outputs else "outline/anchor_sheet.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_anchor_sheet", message=f"`{out_rel}` does not exist.")]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        return [QualityIssue(code="empty_anchor_sheet", message=f"`{out_rel}` is empty.")]
    if _check_placeholder_markers(raw) or "(placeholder)" in raw.lower():
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

    profile = _pipeline_profile(workspace)
    draft_profile = _draft_profile(workspace)
    if profile == "arxiv-survey":
        min_anchors = 12 if draft_profile == "deep" else 10
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




def _check_schema_normalization_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/SCHEMA_NORMALIZATION_REPORT.md"
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code="missing_schema_normalization_report", message=f"`{out_rel}` is missing or empty.")]

    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_schema_normalization_report", message=f"`{out_rel}` is empty.")]
    if _check_placeholder_markers(text) or "…" in text:
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
def _check_writer_context_packs(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_yaml, read_jsonl

    out_rel = outputs[0] if outputs else "outline/writer_context_packs.jsonl"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_writer_context_packs", message=f"`{out_rel}` does not exist.")]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if not raw.strip():
        return [QualityIssue(code="empty_writer_context_packs", message=f"`{out_rel}` is empty.")]
    if _check_placeholder_markers(raw) or "(placeholder)" in raw.lower():
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
    cutover_issues = _section_first_artifact_issues(workspace, consumer=out_rel)
    cutover_issues.extend(_section_first_cutover_issues(workspace, consumer=out_rel, require_stable_h3=True))
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

    profile = _pipeline_profile(workspace)
    draft_profile = _draft_profile(workspace)
    if profile == "arxiv-survey":
        min_plan = 10
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
        per_subsection = int(_per_subsection(workspace))
        if draft_profile == "deep":
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


def _check_evidence_bindings(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import load_yaml, read_jsonl

    out_rel = outputs[0] if outputs else "outline/evidence_bindings.jsonl"
    report_rel = outputs[1] if len(outputs) >= 2 else "outline/evidence_binding_report.md"

    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_evidence_bindings", message=f"`{out_rel}` does not exist.")]
    raw = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        return [QualityIssue(code="empty_evidence_bindings", message=f"`{out_rel}` is empty.")]
    if _check_placeholder_markers(raw) or "…" in raw:
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

    profile = _pipeline_profile(workspace)
    per_subsection = int(_per_subsection(workspace)) if profile == "arxiv-survey" else 0
    # A150++ expectation: with wide per-H3 mapping, bindings should keep most of that breadth,
    # and select a solid subset of usable bibkeys plus enough evidence IDs to write concretely.
    min_mapped = per_subsection if per_subsection else 0
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
        if report and (_check_placeholder_markers(report) or "…" in report):
            return [QualityIssue(code="evidence_binding_report_placeholders", message=f"`{report_rel}` contains placeholders; regenerate binder report.")]

    return []


def _check_survey_visuals(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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


def _check_table_schema(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "outline/table_schema.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_table_schema", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_table_schema", message=f"`{out_rel}` is empty.")]
    if _check_placeholder_markers(text) or "…" in text:
        return [QualityIssue(code="table_schema_placeholders", message=f"`{out_rel}` contains placeholders; fill schema with real table definitions.")]
    n = len(re.findall(r"(?m)^##\s+Table\s+[IA]\d+:", text))
    if n < 4:
        return [QualityIssue(code="table_schema_too_few", message=f"`{out_rel}` should define >=4 tables (I* index + A* appendix; found {n}).")]
    return []


def _check_tables_index_md(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "outline/tables_index.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_tables_md", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_tables_md", message=f"`{out_rel}` is empty.")]
    if _check_placeholder_markers(text) or "…" in text or re.search(r"(?m)\.\.\.+", text):
        return [
            QualityIssue(
                code="tables_placeholders",
                message=f"`{out_rel}` contains placeholders/ellipsis (including `...` truncation); fill tables from evidence packs and remove truncation markers.",
            )
        ]
    table_seps = re.findall(r"(?m)^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", text)
    if len(table_seps) < 2:
        return [QualityIssue(code="tables_missing", message=f"`{out_rel}` should contain >=2 Markdown tables (found {len(table_seps)}).")]
    if "[@" not in text:
        return [QualityIssue(code="tables_no_cites", message=f"`{out_rel}` should include citations in table rows (e.g., `[@BibKey]`).")]
    if re.search(r"\[@(?:Key|KEY)\d+", text):
        return [QualityIssue(code="tables_placeholder_cites", message=f"`{out_rel}` contains placeholder cite keys like `[@Key1]`.")]
    return []


def _check_tables_appendix_md(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "outline/tables_appendix.md"
    expected_report = any(p.endswith("TABLES_APPENDIX_REPORT.md") for p in (outputs or []))
    report_rel = next((p for p in outputs if p.endswith("TABLES_APPENDIX_REPORT.md")), "output/TABLES_APPENDIX_REPORT.md")
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_tables_appendix", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_tables_appendix", message=f"`{out_rel}` is empty.")]
    if _check_placeholder_markers(text) or "…" in text or re.search(r"(?m)\.\.\.+", text):
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
    if len(table_seps) < 2:
        return [QualityIssue(code="tables_appendix_missing", message=f"`{out_rel}` should contain >=2 Markdown tables (found {len(table_seps)}).")]
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


def _check_transitions(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "outline/transitions.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_transitions", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_transitions", message=f"`{out_rel}` is empty.")]
    if _check_placeholder_markers(text) or "…" in text:
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
    rep = _check_repeated_template_text(text=text, min_len=60, min_repeats=8)
    if rep:
        example, count = rep
        return [
            QualityIssue(
                code="transitions_repeated_text",
                message=f"`{out_rel}` contains repeated transition boilerplate ({count}×), e.g., `{example}`; rewrite to be more subsection-specific.",
            )
        ]
    return []


def _check_writer_selfloop(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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


def _check_eval_anchor_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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


def _check_sections_manifest_index(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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
                        expected.add(f"sections/{_slug_unit_id(sub_id)}.md")
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

    return issues


def _check_sections_manifest(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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
    global_threshold = _global_citation_min_subsections(workspace)
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
        if _check_placeholder_markers(text) or "…" in text or re.search(r"(?m)\.\.\.+", text):
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
            profile = _pipeline_profile(workspace)
            draft_profile = _draft_profile(workspace)
            if profile == "arxiv-survey":
                # Survey H3s should stay evidence-dense, but local floors must not force
                # citation-padding or template-only breadth paragraphs. Use a lower local
                # floor here and rely on the global citation target later in the pipeline.
                min_cites = 8 if draft_profile == "deep" else 6
                if len(cite_keys) < min_cites:
                    issues.append(
                        QualityIssue(
                            code="sections_h3_sparse_citations",
                            message=f"`{rel}` has <{min_cites} unique citations ({len(cite_keys)}); each H3 should be evidence-first for survey-quality runs.",
                        )
                    )

            if profile == "arxiv-survey":
                if draft_profile == "deep":
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
                limitation_re = r"(?i)\b(?:limitation|limited|provisional|unclear|sensitive|caveat|downside|failure|risk|open\s+question|remains)\b|受限|尚不明确|缺乏|需要核验|局限|失败|风险|待验证"

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

                if draft_profile == "deep":
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

                profile = _pipeline_profile(workspace)
                if profile == "arxiv-survey":
                    sub_specific = {k for k in cite_keys if k in allowed_sub}
                    if len(sub_specific) < 3:
                        issues.append(
                            QualityIssue(
                                code="sections_h3_sparse_subsection_cites",
                                message=(
                                    f"`{rel}` cites too few subsection-specific papers ({len(sub_specific)}). "
                                    "Chapter-scoped reuse is allowed, but each H3 should still ground itself in >=3 papers mapped to that subsection."
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
            if _pipeline_profile(workspace) == "arxiv-survey" and len(cite_keys) < 2:
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

                if _pipeline_profile(workspace) == "arxiv-survey" and (is_intro or is_related):
                    draft_profile = _draft_profile(workspace)
                    front_kind = "introduction" if is_intro else "related_work"
                    default_front = (
                        {"min_cites": 40, "min_paras": 3, "min_chars": 3600}
                        if draft_profile == "deep" and is_intro
                        else {"min_cites": 55, "min_paras": 2, "min_chars": 4200}
                        if draft_profile == "deep"
                        else {"min_cites": 35, "min_paras": 2, "min_chars": 3200}
                        if is_intro
                        else {"min_cites": 50, "min_paras": 1, "min_chars": 3800}
                    )
                    min_cites = _quality_contract_int(
                        workspace,
                        keys=("front_matter_policy", draft_profile, front_kind, "min_cites"),
                        default=default_front["min_cites"],
                    )
                    min_paras = _quality_contract_int(
                        workspace,
                        keys=("front_matter_policy", draft_profile, front_kind, "min_paras"),
                        default=default_front["min_paras"],
                    )
                    min_chars = _quality_contract_int(
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


def _check_section_logic_polisher(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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
    if _check_placeholder_markers(report) or "…" in report:
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


def _check_merge_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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


def _check_audit_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/AUDIT_REPORT.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_audit_report", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_audit_report", message=f"`{out_rel}` is empty.")]
    if "- Status: PASS" not in text:
        return [QualityIssue(code="audit_report_not_pass", message=f"`{out_rel}` does not report PASS; fix issues and rerun auditor.")]
    return []


def _check_draft(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/DRAFT.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_draft", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore")

    issues: list[QualityIssue] = []
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

    profile = _pipeline_profile(workspace)
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
            min_bib = int(_core_size(workspace)) or 150
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
        h3_blocks = _split_h3_blocks(text)
        floor = 0.30 if _draft_profile(workspace) in {"survey", "deep"} else 0.20
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
        draft_profile = _draft_profile(workspace)
        min_h3_cites = _quality_contract_int(
            workspace,
            keys=("subsection_policy", draft_profile, "min_unique_citations"),
            default=14 if draft_profile == "deep" else 12,
        )
        min_h3_chars = _quality_contract_int(
            workspace,
            keys=("subsection_policy", draft_profile, "min_chars"),
            default=6000 if draft_profile == "deep" else 5000,
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
    intro = _extract_section_body(text, heading_re=r"(?im)^##\s+(introduction|引言)\b")
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
    repeated = _check_repeated_template_text(text=text, min_len=48, min_repeats=10)
    if repeated is not None:
        example, count = repeated
        issues.append(
            QualityIssue(
                code="draft_repeated_lines",
                message=f"Draft contains repeated template-like lines ({count}×), e.g., `{example}...`; rewrite to be section-specific.",
            )
        )
    repeated_sent = _check_repeated_sentences(text=text, min_len=90, min_repeats=6)
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


def _check_citation_anchoring(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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


def _check_global_review(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    report_rel = outputs[0] if outputs else "output/GLOBAL_REVIEW.md"
    report_path = workspace / report_rel
    if not report_path.exists():
        return [QualityIssue(code="missing_global_review", message=f"`{report_rel}` does not exist.")]
    text = report_path.read_text(encoding="utf-8", errors="ignore")

    issues: list[QualityIssue] = []
    if _check_placeholder_markers(text):
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
    issues.extend(_check_draft(workspace, ["output/DRAFT.md"]))
    return issues


def _check_protocol(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/PROTOCOL.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_protocol", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore")

    issues: list[QualityIssue] = []
    if _check_placeholder_markers(text):
        issues.append(QualityIssue(code="protocol_placeholders", message="Protocol contains placeholder markers (TODO/TBD/FIXME)."))

    low = text.lower()
    required = [
        ("databases", "数据库"),
        ("inclusion", "纳入"),
        ("exclusion", "排除"),
        ("extraction", "提取"),
        ("time window", "时间窗"),
    ]
    missing = [en for en, zh in required if (en not in low and zh not in text)]
    if missing:
        issues.append(
            QualityIssue(
                code="protocol_missing_sections",
                message=f"Protocol is missing key sections: {', '.join(missing)} (add databases/queries/inclusion-exclusion/time window/extraction fields).",
            )
        )
    return issues


def _check_tutorial_spec(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/TUTORIAL_SPEC.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_tutorial_spec", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore")

    issues: list[QualityIssue] = []
    if _check_placeholder_markers(text):
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


def _check_source_manifest(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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


def _check_source_ingest(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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


def _check_source_tutorial_spec(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/TUTORIAL_SPEC.md"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_source_tutorial_spec", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore")
    if _check_placeholder_markers(text):
        return [QualityIssue(code="source_tutorial_spec_placeholders", message=f"`{out_rel}` contains placeholders.")]
    low = text.lower()
    needed = ["audience", "prerequisites", "learning objectives", "source scope", "running example", "delivery"]
    missing = [item for item in needed if item not in low]
    if missing:
        return [QualityIssue(code="source_tutorial_spec_missing_sections", message=f"`{out_rel}` is missing key sections: {', '.join(missing)}.")]
    return []


def _check_module_source_coverage(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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


def _check_tutorial_context_packs(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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


def _check_tutorial_selfloop_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "output/TUTORIAL_SELFLOOP_TODO.md"
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code="missing_tutorial_selfloop_report", message=f"`{out_rel}` is missing or empty.")]
    text = path.read_text(encoding="utf-8", errors="ignore")
    if _check_placeholder_markers(text) or "…" in text:
        return [QualityIssue(code="tutorial_selfloop_placeholders", message=f"`{out_rel}` contains placeholders/ellipsis.")]
    if "- Status: PASS" not in text:
        return [QualityIssue(code="tutorial_selfloop_not_pass", message=f"`{out_rel}` is not PASS.")]
    return []




def _split_h3_blocks(text: str) -> list[tuple[str, str]]:
    """Split Markdown draft into H3 blocks: [(title, body)]."""

    out: list[tuple[str, str]] = []
    cur_title = ""
    cur_lines: list[str] = []

    def _flush() -> None:
        nonlocal cur_title, cur_lines
        if not cur_title:
            return
        out.append((cur_title, "\n".join(cur_lines).strip()))

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


def _extract_section_body(text: str, *, heading_re: str) -> str | None:
    m = re.search(heading_re, text)
    if not m:
        return None
    start = m.end()
    nxt = re.search(r"(?m)^##\s+", text[start:])
    end = start + nxt.start() if nxt else len(text)
    return text[start:end].strip()


def _check_latex_scaffold(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "latex/main.tex"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_main_tex", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore")
    profile = pipeline_profile(workspace)
    bib_path = workspace / "citations" / "ref.bib"

    issues: list[QualityIssue] = []
    if profile not in {"source-tutorial"} and "\\begin{abstract}" not in text:
        issues.append(QualityIssue(code="latex_missing_abstract", message="LaTeX output has no `\\begin{abstract}` block."))
    if bib_path.exists() and "\\bibliography{../citations/ref}" not in text:
        issues.append(QualityIssue(code="latex_missing_bib", message="LaTeX output does not reference `../citations/ref.bib`."))
    if not bib_path.exists() and profile not in {"source-tutorial"} and "\\bibliography{../citations/ref}" not in text:
        issues.append(QualityIssue(code="latex_missing_bib", message="LaTeX output does not reference `../citations/ref.bib`."))
    # Heuristics: markdown artifacts should not leak into TeX.
    if "[@" in text:
        issues.append(QualityIssue(code="latex_markdown_cites", message="LaTeX still contains markdown cite markers like `[@...]`."))
    if "**" in text:
        issues.append(QualityIssue(code="latex_markdown_bold", message="LaTeX still contains markdown bold markers `**...**`."))
    if "## " in text or "### " in text:
        issues.append(QualityIssue(code="latex_markdown_headings", message="LaTeX still contains markdown headings like `##`/`###`."))
    return issues


def _check_latex_compile_qa(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    pdf_rel = outputs[0] if outputs else "latex/main.pdf"
    report_rel = outputs[1] if len(outputs) > 1 else "output/LATEX_BUILD_REPORT.md"

    pdf_path = workspace / pdf_rel
    report_path = workspace / report_rel
    log_path = workspace / "latex" / "main.log"

    if not pdf_path.exists():
        return [QualityIssue(code="missing_main_pdf", message=f"`{pdf_rel}` does not exist.")]
    if not report_path.exists():
        return [QualityIssue(code="missing_build_report", message=f"`{report_rel}` does not exist.")]

    report_text = report_path.read_text(encoding="utf-8", errors="ignore")
    issues: list[QualityIssue] = []
    profile = pipeline_profile(workspace)

    if "Status: SUCCESS" not in report_text and "- Status: SUCCESS" not in report_text:
        issues.append(
            QualityIssue(
                code="latex_build_not_success",
                message=f"`{report_rel}` does not report SUCCESS; fix LaTeX build errors and re-run compile.",
            )
        )

    # Prefer the final LaTeX log for undefined-citation checks. The build report may
    # include warning counters (e.g., `citation_undefined: N`) which are not proof
    # that the final PDF still contains unresolved cites.
    undefined_text = ""
    if log_path.exists():
        undefined_text = log_path.read_text(encoding="utf-8", errors="ignore")
    else:
        undefined_text = report_text

    if re.search(r"(?im)^Package\s+natbib\s+Warning: Citation.+undefined", undefined_text) or re.search(
        r"(?im)There were undefined citations", undefined_text
    ) or re.search(r"(?im)There were undefined references", undefined_text) or re.search(
        r"(?im)^LaTeX\s+Warning: Reference.+undefined", undefined_text
    ):
        issues.append(
            QualityIssue(
                code="latex_undefined_citations",
                message="LaTeX build reports undefined citations/references; ensure all cited keys exist in `citations/ref.bib` and rerun until warnings disappear.",
            )
        )

    if re.search(r"(?im)^LaTeX Warning: Float too large for page", undefined_text):
        issues.append(
            QualityIssue(
                code="latex_float_too_large",
                message="LaTeX build still has `Float too large for page` warnings; shrink or split oversized tables/figures and recompile.",
            )
        )

    if re.search(r"(?im)^Missing character:", undefined_text):
        issues.append(
            QualityIssue(
                code="latex_missing_character",
                message="LaTeX build still reports missing Unicode glyphs; add an explicit mapping or sanitize the generated TeX before recompiling.",
            )
        )

    sample_text = ""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        pages = int(len(doc))
        sample_pages = min(pages, 4)
        for i in range(sample_pages):
            try:
                sample_text += doc.load_page(i).get_text("text") + "\n"
            except Exception:
                continue
        doc.close()
    except Exception as exc:
        try:
            import subprocess

            pdfinfo = shutil.which("pdfinfo")
            if not pdfinfo:
                raise exc
            proc = subprocess.run([pdfinfo, str(pdf_path)], capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "pdfinfo failed")
            m = re.search(r"(?im)^Pages:\s+(\d+)\b", proc.stdout or "")
            if not m:
                raise RuntimeError("pdfinfo output missing page count")
            pages = int(m.group(1))
        except Exception as inner_exc:
            issues.append(
                QualityIssue(
                    code="pdf_page_count_unavailable",
                    message=f"Could not compute PDF page count for `{pdf_rel}` ({type(inner_exc).__name__}: {inner_exc}).",
                )
            )
            return issues

    min_pages = 4 if profile == "source-tutorial" else 8
    if pages < min_pages:
        issues.append(
            QualityIssue(
                code="pdf_too_short",
                message=f"`{pdf_rel}` is too short ({pages} pages); expand the draft until the compiled PDF has >= {min_pages} pages.",
            )
        )

    if re.search(r"(?i)\b(?:TODO|TBD|FIXME)\b", sample_text) or "(placeholder)" in sample_text.lower() or "<!-- SCAFFOLD" in sample_text:
        issues.append(
            QualityIssue(
                code="pdf_contains_placeholders",
                message="PDF still contains placeholder text (TODO/TBD/FIXME/SCAFFOLD); rewrite the draft and recompile.",
            )
        )

    return issues


def _check_beamer_scaffold(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "latex/slides/main.tex"
    path = workspace / out_rel
    if not path.exists():
        return [QualityIssue(code="missing_beamer_tex", message=f"`{out_rel}` does not exist.")]
    text = path.read_text(encoding="utf-8", errors="ignore")
    issues: list[QualityIssue] = []
    if "\\documentclass" not in text or "beamer" not in text:
        issues.append(QualityIssue(code="beamer_missing_class", message=f"`{out_rel}` is not a Beamer document."))
    if "\\begin{frame}" not in text:
        issues.append(QualityIssue(code="beamer_missing_frames", message=f"`{out_rel}` has no frame structure."))
    if "## " in text or "### " in text:
        issues.append(QualityIssue(code="beamer_markdown_headings", message=f"`{out_rel}` still contains markdown headings."))
    return issues


def _check_beamer_compile_qa(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    pdf_rel = outputs[0] if outputs else "latex/slides/main.pdf"
    report_rel = outputs[1] if len(outputs) > 1 else "output/SLIDES_BUILD_REPORT.md"
    pdf_path = workspace / pdf_rel
    report_path = workspace / report_rel
    if not pdf_path.exists():
        return [QualityIssue(code="missing_beamer_pdf", message=f"`{pdf_rel}` does not exist.")]
    if not report_path.exists():
        return [QualityIssue(code="missing_slides_build_report", message=f"`{report_rel}` does not exist.")]
    text = report_path.read_text(encoding="utf-8", errors="ignore")
    if "- Status: PASS" not in text and "Status: PASS" not in text:
        return [QualityIssue(code="beamer_build_not_pass", message=f"`{report_rel}` is not PASS.")]
    return []

def _check_contract_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = next((p for p in outputs if p.endswith('CONTRACT_REPORT.md')), 'output/CONTRACT_REPORT.md')
    path = workspace / out_rel
    if not path.exists() or path.stat().st_size == 0:
        return [QualityIssue(code='missing_contract_report', message=f'`{out_rel}` is missing or empty.')]

    text = path.read_text(encoding='utf-8', errors='ignore').strip()
    if not text:
        return [QualityIssue(code='empty_contract_report', message=f'`{out_rel}` is empty.')]
    if _check_placeholder_markers(text) or '…' in text:
        return [QualityIssue(code='contract_report_placeholders', message=f'`{out_rel}` contains placeholders/ellipsis; regenerate after fixing missing artifacts.')]

    ok_status = bool(re.search(r'(?im)^-\s*Status:\s*PASS\b', text))
    ok_complete = bool(re.search(r'(?im)^-\s*Pipeline complete \(units\):\s*yes\b', text))
    if ok_status and ok_complete:
        return []

    return [
        QualityIssue(
            code='contract_report_not_pass',
            message=(
                f'`{out_rel}` is not PASS (or pipeline not complete). '
                'Fix missing artifacts / unit statuses and rerun `artifact-contract-auditor`.'
            ),
        )
    ]
