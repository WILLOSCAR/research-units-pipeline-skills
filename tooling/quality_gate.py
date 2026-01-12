from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class QualityIssue:
    code: str
    message: str


def _pipeline_profile(workspace: Path) -> str:
    lock_path = workspace / "PIPELINE.lock.md"
    if not lock_path.exists():
        return "default"
    try:
        for raw in lock_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("pipeline:"):
                continue
            pipeline = line.split(":", 1)[1].strip().lower()
            if "arxiv-survey" in pipeline:
                return "arxiv-survey"
            return "default"
    except Exception:
        return "default"


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
        return _check_tables_md(workspace, outputs)
    if skill == "subsection-briefs":
        return _check_subsection_briefs(workspace, outputs)
    if skill == "evidence-binder":
        return _check_evidence_bindings(workspace, outputs)
    if skill == "evidence-draft":
        return _check_evidence_drafts(workspace, outputs)
    if skill == "survey-visuals":
        return _check_survey_visuals(workspace, outputs)
    if skill == "transition-weaver":
        return _check_transitions(workspace, outputs)
    if skill == "subsection-writer":
        return _check_sections_manifest(workspace, outputs)
    if skill == "section-merger":
        return _check_merge_report(workspace, outputs)
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
    if skill == "protocol-writer":
        return _check_protocol(workspace, outputs)
    if skill == "tutorial-spec":
        return _check_tutorial_spec(workspace, outputs)
    return []


def _check_pdf_text_extractor(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    out_rel = outputs[0] if outputs else "papers/fulltext_index.jsonl"
    path = workspace / out_rel
    records = read_jsonl(path) if path.exists() else []
    if not records:
        return [QualityIssue(code="empty_fulltext_index", message=f"`{out_rel}` is missing or empty.")]

    mode = "abstract"
    queries_path = workspace / "queries.md"
    if queries_path.exists():
        for raw in queries_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("- evidence_mode:"):
                continue
            value = line.split(":", 1)[1].split("#", 1)[0].strip().strip('"').strip("'").strip().lower()
            if value:
                mode = value
            break
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
    lines: list[str] = [
        "# Quality gate report",
        "",
        f"- Timestamp: `{now}`",
        f"- Unit: `{unit_id}`",
        f"- Skill: `{skill}`",
        "",
        "## Issues",
        "",
    ]
    for issue in issues:
        lines.append(f"- `{issue.code}`: {issue.message}")
    lines.append("")
    lines.append("## Next action")
    lines.append("")
    for ln in _next_action_lines(skill=skill, unit_id=unit_id):
        lines.append(ln)
    lines.append("")

    atomic_write_text(report_path, "\n".join(lines).rstrip() + "\n")
    return report_path


def _next_action_lines(*, skill: str, unit_id: str) -> list[str]:
    skill_md = f".codex/skills/{skill}/SKILL.md"
    common = [
        "- Treat the current outputs as a starting point (often a scaffold).",
        f"- Follow `{skill_md}` to refine the required artifacts until the issues above no longer apply.",
        f"- Then mark `{unit_id}` as `DONE` in `UNITS.csv` (or run `python scripts/pipeline.py mark --workspace <ws> --unit-id {unit_id} --status DONE --note \"LLM refined\"`).",
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
            "- Fill `outline/tables.md` with ≥2 real Markdown tables (method + evaluation/benchmarks) and include citations in rows.",
            "- Fill `outline/timeline.md` with ≥8 milestone bullets (year + cited works).",
            "- Fill `outline/figures.md` with ≥2 figure specs (purpose, elements, supporting citations).",
        ],
        "subsection-writer": [
            "- Write per-unit prose files under `sections/` (small, verifiable units):",
            "  - `sections/abstract.md` (`## Abstract`), `sections/open_problems.md`, `sections/conclusion.md`.",
            "  - `sections/S<section_id>.md` for H2 sections without H3 (body only).",
            "  - `sections/S<sub_id>.md` for each H3 (body only; no headings).",
            "- Each H3 file should have >=3 unique citations and avoid ellipsis/TODO/template boilerplate.",
            "- Keep H3 citations subsection-scoped: cite only keys mapped in `outline/evidence_bindings.jsonl` for that H3 (or fix mapping/bindings).",
        ],
        "section-merger": [
            "- Ensure all required `sections/*.md` exist (see `output/MERGE_REPORT.md` for missing paths), then rerun merge.",
            "- After merge, polish/review the combined `output/DRAFT.md` (then run `pipeline-auditor` before LaTeX).",
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
        min_raw = 200
        if total < min_raw:
            issues.append(
                QualityIssue(
                    code="raw_too_small",
                    message=f"`{out_rel}` has {total} records; target >= {min_raw} for survey-quality runs (add more imports / enable online + snowball).",
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
        evidence_mode = "abstract"
        queries_path = workspace / "queries.md"
        if queries_path.exists():
            for raw in queries_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line.startswith("- evidence_mode:"):
                    continue
                value = line.split(":", 1)[1].split("#", 1)[0].strip().strip('"').strip("'").strip().lower()
                if value:
                    evidence_mode = value
                break
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
        min_core = 150
        if len(rows) < min_core:
            issues.append(
                QualityIssue(
                    code="core_set_too_small",
                    message=f"`{core_rel}` has {len(rows)} rows; target >= {min_core} for survey-quality coverage (increase candidate pool and `core_size`).",
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
        if len([r for r in dedup if isinstance(r, dict)]) < 200:
            issues.append(
                QualityIssue(
                    code="dedup_pool_too_small",
                    message=f"`{dedup_rel}` has too few deduplicated records for a survey run; expand retrieval/snowballing first.",
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
        min_bib = 150
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
    from tooling.common import load_yaml

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

        # Paper-like constraint: avoid fragmenting the survey into too many tiny H3s.
        if subs_total > 12:
            return [
                QualityIssue(
                    code="outline_too_many_subsections",
                    message=(
                        f"Outline has too many subsections for survey-quality writing ({subs_total}). "
                        "Prefer <=12 H3 subsections (fewer, thicker sections). Merge/simplify the taxonomy/outline so each H3 can sustain deeper evidence-first prose."
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

        per_subsection = 3
        ok = sum(1 for _, c in counts.items() if c >= per_subsection)
        total = max(1, len(counts))
        if ok / total < 0.8:
            issues.append(
                QualityIssue(
                    code="mapping_low_coverage",
                    message=f"Only {ok}/{len(counts)} subsections have >= {per_subsection} mapped papers; mapping should cover most subsections before evidence/drafting.",
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
    min_plan_len = 6 if profile == "arxiv-survey" else 2

    required_top = {"sub_id", "title", "section_id", "section_title", "scope_rule", "rq", "axes", "clusters", "paragraph_plan", "evidence_level_summary"}
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
            if str(item.get("intent") or "").strip():
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
    return issues


def _check_coverage_report(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import read_jsonl

    report_rel = outputs[0] if outputs else "outline/coverage_report.md"
    state_rel = outputs[1] if len(outputs) >= 2 else "outline/outline_state.jsonl"

    report_path = workspace / report_rel
    state_path = workspace / state_rel

    if not report_path.exists():
        return [QualityIssue(code="missing_coverage_report", message=f"`{report_rel}` does not exist.")]
    report = report_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not report:
        return [QualityIssue(code="empty_coverage_report", message=f"`{report_rel}` is empty.")]
    if _check_placeholder_markers(report) or "…" in report:
        return [QualityIssue(code="coverage_report_placeholders", message=f"`{report_rel}` contains placeholders; regenerate planner report.")]
    if "| Subsection |" not in report:
        return [QualityIssue(code="coverage_report_missing_table", message=f"`{report_rel}` is missing the per-subsection table.")]

    if not state_path.exists():
        return [QualityIssue(code="missing_outline_state", message=f"`{state_rel}` does not exist.")]
    recs = read_jsonl(state_path)
    recs = [r for r in recs if isinstance(r, dict)]
    if not recs:
        return [QualityIssue(code="empty_outline_state", message=f"`{state_rel}` has no JSON records.")]
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
    bad = 0
    missing_bib = 0
    blocking_missing = 0
    weak_comparisons = 0
    missing_snippets = 0
    bad_snippet_prov = 0

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
        if not isinstance(snippets, list) or len([s for s in snippets if isinstance(s, dict) and str(s.get("text") or "").strip()]) < 1:
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
        if not isinstance(comps, list) or len([c for c in comps if isinstance(c, dict)]) < 3:
            weak_comparisons += 1
            continue

        required_blocks = ["definitions_setup", "claim_candidates", "concrete_comparisons", "evaluation_protocol", "failures_limitations"]
        for name in required_blocks:
            block = pack.get(name)
            if not isinstance(block, list) or not block:
                bad += 1
                break
        else:
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
                message=f"{missing_snippets} evidence pack(s) have no usable `evidence_snippets`; add abstracts/fulltext or enrich paper notes before writing.",
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
                message=f"{weak_comparisons} evidence pack(s) have <3 concrete comparisons; expand comparisons per subsection before writing.",
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

    bad = 0
    missing_bank = 0
    for sid, rec in by_sub.items():
        title = str(rec.get("title") or "").strip()
        eids = rec.get("evidence_ids") or []
        if not title or not isinstance(eids, list) or len([e for e in eids if str(e).strip()]) < 6:
            bad += 1
            continue
        if bank_ids and any(str(e).strip() and str(e).strip() not in bank_ids for e in eids):
            missing_bank += 1

    if bad:
        return [QualityIssue(code="evidence_bindings_incomplete", message=f"`{out_rel}` has {bad} record(s) missing title or with too few evidence_ids (<6).")]
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
        tables_rel = outputs[0] if outputs else "outline/tables.md"
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
    n = len(re.findall(r"(?m)^##\s+Table\s+\d+:", text))
    if n < 2:
        return [QualityIssue(code="table_schema_too_few", message=f"`{out_rel}` should define >=2 tables (found {n}).")]
    return []


def _check_tables_md(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    out_rel = outputs[0] if outputs else "outline/tables.md"
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
    if len(bullets) < 8:
        return [
            QualityIssue(
                code="transitions_too_short",
                message=f"`{out_rel}` looks too short (bullets={len(bullets)}); generate more subsection transitions.",
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
    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            sec_id = str(sec.get("id") or "").strip()
            sec_title = str(sec.get("title") or "").strip()
            subs = sec.get("subsections") or []
            if subs and isinstance(subs, list):
                for sub in subs:
                    if not isinstance(sub, dict):
                        continue
                    sub_id = str(sub.get("id") or "").strip()
                    sub_title = str(sub.get("title") or "").strip()
                    if sub_id and sub_title:
                        expected_units.append({"kind": "h3", "id": sub_id, "title": sub_title, "section_title": sec_title})
            else:
                if sec_id and sec_title:
                    expected_units.append({"kind": "h2", "id": sec_id, "title": sec_title, "section_title": sec_title})

    # Required global sections (kept outside outline for consistency).
    required_globals = [
        ("abstract", "Abstract", base_dir / "abstract.md"),
        ("open_problems", "Open Problems", base_dir / "open_problems.md"),
        ("conclusion", "Conclusion", base_dir / "conclusion.md"),
    ]
    optional_globals = [
        ("evidence_note", "Evidence note", base_dir / "evidence_note.md"),
    ]

    expected_files: list[tuple[str, str, str]] = []
    for gid, title, rel in required_globals:
        expected_files.append(("global", gid, rel.as_posix()))
    for gid, title, rel in optional_globals:
        expected_files.append(("global_optional", gid, rel.as_posix()))
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

    def _extract_keys(text: str) -> set[str]:
        keys: set[str] = set()
        for m in re.finditer(r"\[@([^\]]+)\]", text):
            inside = (m.group(1) or "").strip()
            for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
                if k:
                    keys.add(k)
        return keys

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
        if re.search(r"(?i)\babstracts are treated as verification targets\b", text) or re.search(r"(?i)\bthe main axes we track are\b", text):
            issues.append(
                QualityIssue(
                    code="sections_contains_pipeline_voice",
                    message=f"`{rel}` contains pipeline-style boilerplate; rewrite to be subsection-specific and avoid repeated template sentences.",
                )
            )
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
            if profile == "arxiv-survey" and len(cite_keys) < 3:
                issues.append(
                    QualityIssue(
                        code="sections_h3_sparse_citations",
                        message=f"`{rel}` has <3 unique citations ({len(cite_keys)}); each H3 should be evidence-first (>=3) for survey-quality runs.",
                    )
                )

            if profile == "arxiv-survey":
                paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
                if len(paragraphs) < 6:
                    issues.append(
                        QualityIssue(
                            code="sections_h3_too_few_paragraphs",
                            message=f"`{rel}` has too few paragraphs ({len(paragraphs)}); for survey-quality runs aim for 6–10 paragraphs per H3 (thesis → contrasts → eval anchor → synthesis → limitations), not a short stub.",
                        )
                    )

                content = re.sub(r"\[@[^\]]+\]", "", text)
                content = re.sub(r"\s+", " ", content).strip()
                if len(content) < 4000:
                    issues.append(
                        QualityIssue(
                            code="sections_h3_too_short",
                            message=(
                                f"`{rel}` looks too short ({len(content)} chars after removing citations). "
                                "For survey-quality runs, expand with concrete comparisons + evaluation details + synthesis + limitations from the evidence pack."
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
                contrast_re = r"(?i)\b(?:whereas|however|in\s+contrast|by\s+contrast|versus|vs\.)\b|相比|不同于|相较|对比|反之"
                eval_re = r"(?i)\b(?:benchmark|dataset|datasets|metric|metrics|evaluation|eval\.|protocol|human|ablation)\b|评测|基准|数据集|指标|协议|人工|实验"
                limitation_re = r"(?i)\b(?:limitation|limited|unclear|sensitive|caveat|downside|failure|risk|open\s+question|remains)\b|受限|尚不明确|缺乏|需要核验|局限|失败|风险|待验证"

                if not re.search(contrast_re, text):
                    issues.append(
                        QualityIssue(
                            code="sections_h3_missing_contrast",
                            message=f"`{rel}` lacks explicit contrast phrasing (e.g., whereas/in contrast/相比/不同于); survey paragraphs should compare routes, not only summarize.",
                        )
                    )
                if not re.search(eval_re, text):
                    issues.append(
                        QualityIssue(
                            code="sections_h3_missing_eval_anchor",
                            message=f"`{rel}` lacks an evaluation anchor (benchmark/dataset/metric/protocol/评测); add at least one concrete evaluation reference even at abstract level.",
                        )
                    )
                if not re.search(limitation_re, text):
                    issues.append(
                        QualityIssue(
                            code="sections_h3_missing_limitation",
                            message=f"`{rel}` lacks a limitation/provisional sentence (limited/unclear/受限/待验证); include at least one explicit caveat to avoid overclaiming.",
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
                allowed = mapped_by_sub.get(uid) or set()
                outside = sorted([k for k in cite_keys if k not in allowed])
                if outside:
                    sample = ", ".join(outside[:8])
                    suffix = "..." if len(outside) > 8 else ""
                    issues.append(
                        QualityIssue(
                            code="sections_cites_outside_mapping",
                            message=f"`{rel}` cites keys not mapped to subsection {uid} (e.g., {sample}{suffix}); keep citations subsection-scoped (or fix mapping/bindings).",
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
            if uid == "open_problems" and not re.search(r"(?im)^##\s+(open problems|future directions|future work|开放问题|未来方向|未来工作)\b", text):
                issues.append(
                    QualityIssue(
                        code="sections_open_problems_missing_heading",
                        message=f"`{rel}` should include an `## Open Problems & Future Directions` heading (or equivalent).",
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
            # H2 body files: encourage at least one citation.
            if kind == "h2" and "[@" not in text:
                issues.append(
                    QualityIssue(
                        code="sections_h2_no_citations",
                        message=f"`{rel}` contains no citations; H2 sections should be grounded with citations (or keep claims purely structural).",
                    )
                )

    return issues


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
                    "Move evidence caveats into a single, short 'Evidence note' (once), and keep subsections focused on concrete comparisons."
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
            min_bib = 150
            if len(bib_keys) < min_bib:
                issues.append(
                    QualityIssue(
                        code="draft_bib_too_small",
                        message=f"`citations/ref.bib` has {len(bib_keys)} entries; target >= {min_bib} for survey-quality coverage.",
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
        no_cite = 0
        too_short = 0
        low_cite_density = 0
        for block in subsection_blocks:
            lines = [ln for ln in block.splitlines() if ln.strip()]
            # Robustness: do not use line-count as a proxy for section length.
            # Many writers use 1 line per paragraph, which makes "short section" detection brittle.
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            body = re.sub(r"\[@[^\]]+\]", "", body)
            if len(body) < 4000:
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
                if len(cite_keys) < 3:
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
                    message="Many subsections are very short (<~4000 chars sans citations); expand with concrete comparisons, evaluation anchors, synthesis paragraphs, and limitations from evidence packs/paper notes.",
                )
            )
        if profile == "arxiv-survey" and low_cite_density / total >= 0.2:
            issues.append(
                QualityIssue(
                    code="draft_sparse_subsection_citations",
                    message=f"Many subsections have <3 unique citations ({low_cite_density}/{len(subsection_blocks)}); increase section-level evidence binding and cite density.",
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
    if not re.search(r"(?im)^##\s+(open problems|future directions|future work|开放问题|未来方向|未来工作)\b", text) and not re.search(
        r"(?im)^##\s+(discussion|discussion and future work|discussion & future work|讨论|讨论与未来工作)\b", text
    ):
        issues.append(
            QualityIssue(
                code="draft_missing_open_problems",
                message="Draft is missing an `Open Problems & Future Directions` or `Discussion/Future Work` section.",
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
                    message="Introduction looks too short (<~180 words); expand motivation, scope, contributions, and positioning vs. prior surveys.",
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

    issues: list[QualityIssue] = []
    if "\\begin{abstract}" not in text:
        issues.append(QualityIssue(code="latex_missing_abstract", message="LaTeX output has no `\\begin{abstract}` block."))
    if "\\bibliography{../citations/ref}" not in text:
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

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        pages = int(len(doc))
        sample_pages = min(pages, 4)
        sample_text = ""
        for i in range(sample_pages):
            try:
                sample_text += doc.load_page(i).get_text("text") + "\n"
            except Exception:
                continue
        doc.close()
    except Exception as exc:
        issues.append(
            QualityIssue(
                code="pdf_page_count_unavailable",
                message=f"Could not compute PDF page count for `{pdf_rel}` ({type(exc).__name__}: {exc}).",
            )
        )
        return issues

    if pages < 8:
        issues.append(
            QualityIssue(
                code="pdf_too_short",
                message=f"`{pdf_rel}` is too short ({pages} pages); expand the draft until the compiled PDF has >= 8 pages.",
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
