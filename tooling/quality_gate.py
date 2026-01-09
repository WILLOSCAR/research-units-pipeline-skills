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
    if skill == "survey-visuals":
        return _check_survey_visuals(workspace, outputs)
    if skill == "prose-writer":
        return _check_draft(workspace, outputs)
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
        "prose-writer": [
            "- Edit `output/DRAFT.md`: add real cross-paper synthesis (comparisons and trade-offs), not per-paper lists.",
            "- Ensure required paper-like sections exist: Introduction, Timeline/Evolution, Open Problems & Future Directions, Conclusion.",
            "- Add ≥2 comparison tables and remove repeated boilerplate (identical open-problems/takeaways across sections).",
            "- Use only citation keys present in `citations/ref.bib`.",
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
    for rec in records:
        title = str(rec.get("title") or "").strip()
        url = str(rec.get("url") or rec.get("id") or "").strip()
        if title.lower().startswith("(placeholder)") or "0000.00000" in url:
            placeholders += 1
        if str(rec.get("source") or "").strip().lower() == "arxiv":
            arxiv_sources += 1
    if placeholders:
        return [
            QualityIssue(
                code="placeholder_records",
                message=f"`{out_rel}` contains placeholder/demo records ({placeholders}); workspace template should start empty.",
            )
        ]
    # Only enforce keyword hygiene when this looks like an online arXiv retrieval.
    if arxiv_sources:
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

    total = len([n for n in notes if isinstance(n, dict)])
    high = [n for n in notes if isinstance(n, dict) and str(n.get("priority") or "").strip().lower() == "high"]
    high_total = len(high)

    # If priority isn't present (older workspaces), fall back to the old heuristics.
    if total and high_total == 0:
        method_empty = 0
        results_empty = 0
        bullets_short = 0
        lim_first_counts: dict[str, int] = {}
        fulltext = 0
        for n in notes:
            if not isinstance(n, dict):
                continue
            method = str(n.get("method") or "").strip()
            if not method:
                method_empty += 1
            key_results = n.get("key_results") or []
            if not isinstance(key_results, list) or len(key_results) == 0:
                results_empty += 1
            bullets = n.get("summary_bullets") or []
            if not isinstance(bullets, list) or len([b for b in bullets if str(b).strip()]) < 3:
                bullets_short += 1
            lims = n.get("limitations") or []
            if isinstance(lims, list) and lims:
                first = str(lims[0]).strip()
                first = re.sub(r"^\[[A-Za-z]+\]\s*", "", first)
                if first:
                    lim_first_counts[first] = lim_first_counts.get(first, 0) + 1
            if str(n.get("evidence_level") or "").strip().lower() == "fulltext":
                fulltext += 1

        issues: list[QualityIssue] = []
        if total and method_empty / total >= 0.7 and results_empty / total >= 0.7:
            issues.append(
                QualityIssue(
                    code="paper_notes_missing_method_results",
                    message="Most paper notes have empty `method` and `key_results`; enrich notes beyond title/abstract-only scaffolding.",
                )
            )
        if total and bullets_short / total >= 0.7:
            issues.append(
                QualityIssue(
                    code="paper_notes_short_summaries",
                    message="Most paper notes have <3 summary bullets; add concrete contributions, setup, and findings.",
                )
            )
        if total >= 10 and lim_first_counts:
            top_lim, top_count = sorted(lim_first_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            if top_count / total >= 0.4 and top_count >= 8:
                issues.append(
                    QualityIssue(
                        code="paper_notes_repeated_limitations",
                        message=f"Many papers share the same limitation text (e.g., `{top_lim}`); diversify with paper-specific assumptions/failures.",
                    )
                )
        if total >= 20 and fulltext / total < 0.1:
            issues.append(
                QualityIssue(
                    code="paper_notes_too_abstract",
                    message="Most notes are abstract-level; run `pdf-text-extractor` and enrich key papers with full-text evidence before synthesis.",
                )
            )
        return issues

    # New heuristic: require *high-priority* papers to be enriched (LLM-first), allow long-tail to stay abstract-level.
    min_high = 8 if total >= 30 else (5 if total >= 15 else 2)
    issues: list[QualityIssue] = []
    if total and high_total < min_high:
        issues.append(
            QualityIssue(
                code="paper_notes_missing_priority",
                message=f"Expected at least {min_high} high-priority notes (found {high_total}); ensure `priority=high` exists for key papers.",
            )
        )
        return issues

    def _has_todo(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return "TODO" in value
        if isinstance(value, list):
            return any(isinstance(x, str) and "TODO" in x for x in value)
        return False

    complete = 0
    todo_hits = 0
    for n in high:
        method = str(n.get("method") or "").strip()
        key_results = n.get("key_results") or []
        bullets = n.get("summary_bullets") or []
        lims = n.get("limitations") or []

        if _has_todo(method) or _has_todo(key_results) or _has_todo(bullets) or _has_todo(lims):
            todo_hits += 1
            continue
        if not method:
            continue
        if not isinstance(key_results, list) or len([x for x in key_results if str(x).strip()]) < 1:
            continue
        if not isinstance(bullets, list) or len([b for b in bullets if str(b).strip()]) < 3:
            continue
        if not isinstance(lims, list) or len([x for x in lims if str(x).strip()]) < 1:
            continue
        first_lim = str(lims[0]).strip().lower()
        if first_lim.startswith("evidence level:"):
            continue
        complete += 1

    if todo_hits:
        issues.append(
            QualityIssue(
                code="paper_notes_contains_todo",
                message="High-priority paper notes still contain `TODO` placeholders; enrich them (method/results/limitations) before synthesis.",
            )
        )
    target_complete = max(5, int(high_total * 0.8))
    if complete < target_complete:
        issues.append(
            QualityIssue(
                code="paper_notes_priority_incomplete",
                message=f"Only {complete}/{high_total} high-priority notes look complete; target >= {target_complete}.",
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
    return []


def _check_survey_visuals(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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
        if re.search(r"\[@(?:Key|KEY)\d+", text):
            issues.append(QualityIssue(code="visuals_placeholder_cites", message=f"`{rel}` contains placeholder cite keys like `[@Key1]`."))
        return text

    tables = _read(tables_rel)
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
    if text.count("…") >= 20:
        issues.append(
            QualityIssue(
                code="draft_contains_ellipsis_placeholders",
                message="Draft contains many ellipsis placeholders (`…`), suggesting truncated scaffold text; regenerate after fixing outline/mapping/evidence artifacts.",
            )
        )
    if re.search(r"(?i)enumerate\\s+2-4\\s+recurring", text):
        issues.append(
            QualityIssue(
                code="draft_scaffold_instructions",
                message="Draft still contains scaffold instructions like 'enumerate 2-4 recurring ...'; rewrite outline/claims into concrete content before drafting.",
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
            if len(lines) < 8:
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
                    message="Many subsections are very short; expand with method/results/limitations comparisons from paper notes.",
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

    # Require at least 2 Markdown tables (for comparisons + benchmarks).
    table_seps = re.findall(r"(?m)^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", text)
    if len(table_seps) < 2:
        issues.append(
            QualityIssue(
                code="draft_missing_tables",
                message=f"Draft should include >=2 Markdown tables (found {len(table_seps)}); add comparison + benchmarks tables.",
            )
        )

    # Require Introduction + Conclusion headings.
    if not re.search(r"(?im)^##\s+(introduction|引言)\b", text):
        issues.append(QualityIssue(code="draft_missing_introduction", message="Draft is missing an `Introduction/引言` section."))
    if not re.search(r"(?im)^##\s+(conclusion|结论)\b", text):
        issues.append(QualityIssue(code="draft_missing_conclusion", message="Draft is missing a `Conclusion/结论` section."))
    if not re.search(r"(?im)^##\s+(timeline|evolution|chronology|时间线|演化|发展)\b", text):
        issues.append(
            QualityIssue(code="draft_missing_timeline", message="Draft is missing a `Timeline/Evolution/时间线` section.")
        )
    if not re.search(r"(?im)^##\s+(open problems|future directions|future work|开放问题|未来方向|未来工作)\b", text):
        issues.append(
            QualityIssue(
                code="draft_missing_open_problems",
                message="Draft is missing an `Open Problems & Future Directions/开放问题` section.",
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

    timeline = _extract_section_body(text, heading_re=r"(?im)^##\s+(timeline|evolution|chronology|时间线|演化|发展)\b")
    if timeline is not None:
        year_lines = [ln.strip() for ln in timeline.splitlines() if re.search(r"\b20\d{2}\b", ln)]
        cited = [ln for ln in year_lines if "[@" in ln]
        if len(year_lines) < 6:
            issues.append(
                QualityIssue(
                    code="draft_timeline_too_short",
                    message=f"Timeline section seems too short (found {len(year_lines)} year lines); add more milestones with citations.",
                )
            )
        if year_lines and len(cited) / len(year_lines) < 0.6:
            issues.append(
                QualityIssue(
                    code="draft_timeline_sparse_cites",
                    message="Timeline should cite key works for most milestones (>=60%).",
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

    if re.search(r"(?im)^Package\\s+natbib\\s+Warning: Citation.+undefined", undefined_text) or re.search(
        r"(?im)There were undefined citations", undefined_text
    ) or re.search(r"(?im)There were undefined references", undefined_text) or re.search(
        r"(?im)^LaTeX\\s+Warning: Reference.+undefined", undefined_text
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
