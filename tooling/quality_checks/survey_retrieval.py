from __future__ import annotations

import re
from pathlib import Path

from tooling.quality_checks.common import QualityIssue, has_placeholder_markers
from tooling.quality_checks.survey_policy import core_size, evidence_mode, pipeline_profile_name


def check_keyword_expansion(workspace: Path) -> list[QualityIssue]:
    queries_path = workspace / "queries.md"
    if not queries_path.exists():
        return [QualityIssue(code="missing_queries", message="Missing `queries.md`; expected keyword list for retrieval.")]

    text = queries_path.read_text(encoding="utf-8", errors="ignore")
    if has_placeholder_markers(text):
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


def check_citation_injection(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    report_rel = next((p for p in outputs if p.endswith("CITATION_INJECTION_REPORT.md")), "output/CITATION_INJECTION_REPORT.md")
    report_path = workspace / report_rel
    if not report_path.exists() or report_path.stat().st_size == 0:
        return [QualityIssue(code="missing_citation_injection_report", message=f"`{report_rel}` is missing or empty.")]

    text = report_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return [QualityIssue(code="empty_citation_injection_report", message=f"`{report_rel}` is empty.")]
    if has_placeholder_markers(text) or "…" in text:
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


def check_pdf_text_extractor(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    import csv

    from tooling.common import read_jsonl

    out_rel = outputs[0] if outputs else "papers/fulltext_index.jsonl"
    path = workspace / out_rel
    records = read_jsonl(path) if path.exists() else []
    if not records:
        return [QualityIssue(code="empty_fulltext_index", message=f"`{out_rel}` is missing or empty.")]

    mode = evidence_mode(workspace)
    if mode != "fulltext":
        core_path = workspace / "papers" / "core_set.csv"
        core_ids: set[str] = set()
        if core_path.exists():
            with core_path.open(encoding="utf-8", newline="") as handle:
                core_ids = {
                    str(row.get("paper_id") or "").strip()
                    for row in csv.DictReader(handle)
                    if str(row.get("paper_id") or "").strip()
                }
        indexed_ids = {
            str(record.get("paper_id") or "").strip()
            for record in records
            if isinstance(record, dict) and str(record.get("paper_id") or "").strip()
        }
        missing_ids = sorted(core_ids - indexed_ids)
        if missing_ids:
            preview = ", ".join(missing_ids[:8])
            suffix = " ..." if len(missing_ids) > 8 else ""
            return [
                QualityIssue(
                    code="abstract_index_incomplete",
                    message=(
                        f"`{out_rel}` is missing {len(missing_ids)}/{len(core_ids)} core paper(s): "
                        f"{preview}{suffix}. Abstract mode must index the complete core set."
                    ),
                )
            ]
        unexpected_statuses = sorted(
            {
                str(record.get("status") or "").strip()
                for record in records
                if isinstance(record, dict)
                and str(record.get("paper_id") or "").strip() in core_ids
                and str(record.get("status") or "").strip() != "skip_mode_abstract"
            }
        )
        if unexpected_statuses:
            return [
                QualityIssue(
                    code="abstract_index_status_invalid",
                    message=(
                        f"`{out_rel}` contains non-abstract skip statuses: "
                        + ", ".join(unexpected_statuses)
                        + "."
                    ),
                )
            ]
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


def check_arxiv_search(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import pipeline_quality_contract_value, read_jsonl

    out_rel = outputs[0] if outputs else "papers/papers_raw.jsonl"
    path = workspace / out_rel
    records = read_jsonl(path)
    if not records:
        return [QualityIssue(code="empty_raw", message=f"No records found in `{out_rel}`.")]

    minimum_records = int(
        pipeline_quality_contract_value(
            workspace,
            "retrieval_policy",
            "minimum_records",
            default=1,
        )
        or 1
    )
    if len(records) < minimum_records:
        return [
            QualityIssue(
                code="raw_pool_too_small",
                message=(
                    f"`{out_rel}` contains {len(records)} records; the Workflow contract "
                    f"requires at least {minimum_records}. Broaden or repair the query before ranking."
                ),
            )
        ]

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
        return check_keyword_expansion(workspace)
    return []


def check_literature_engineer(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import pipeline_quality_contract_value, read_jsonl

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
    minimum_records = int(
        pipeline_quality_contract_value(
            workspace,
            "retrieval_policy",
            "minimum_records",
            default=1,
        )
        or 1
    )
    if total < minimum_records:
        issues.append(
            QualityIssue(
                code="raw_pool_too_small",
                message=(
                    f"`{out_rel}` contains {total} records; the Workflow contract "
                    f"requires at least {minimum_records}. Expand the approved retrieval plan before screening."
                ),
            )
        )
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

    profile = pipeline_profile_name(workspace)
    if profile == "arxiv-survey":
        min_raw = max(200, int(core_size(workspace)) * 4)
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
        mode = evidence_mode(workspace)
        if mode != "fulltext" and missing_abstract / max(1, total) >= 0.7:
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


def check_dedupe_rank(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
    from tooling.common import pipeline_quality_contract_value, read_jsonl

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

    core_size_min = int(
        pipeline_quality_contract_value(
            workspace,
            "candidate_pool_policy",
            "core_size_min",
            default=0,
        )
        or 0
    )
    core_size_max = int(
        pipeline_quality_contract_value(
            workspace,
            "candidate_pool_policy",
            "core_size_max",
            default=0,
        )
        or 0
    )
    if core_size_min and len(rows) < core_size_min:
        issues.append(
            QualityIssue(
                code="core_set_too_small",
                message=f"`{core_rel}` has {len(rows)} rows; the Workflow contract requires at least {core_size_min}.",
            )
        )
    if core_size_max and len(rows) > core_size_max:
        issues.append(
            QualityIssue(
                code="core_set_too_large",
                message=f"`{core_rel}` has {len(rows)} rows; the Workflow contract allows at most {core_size_max}.",
            )
        )

    profile = pipeline_profile_name(workspace)
    if profile == "arxiv-survey":
        min_core = int(core_size(workspace))
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


def check_citations(workspace: Path, outputs: list[str]) -> list[QualityIssue]:
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

    profile = pipeline_profile_name(workspace)
    if profile == "arxiv-survey":
        min_bib = int(core_size(workspace)) or 150
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
