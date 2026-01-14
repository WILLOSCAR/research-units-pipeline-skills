from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class RouteProvenance:
    route: str
    source: str
    source_path: str
    imported_at: str
    note: str = ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--online", action="store_true", help="Force online arXiv API retrieval (needs network).")
    parser.add_argument("--snowball", action="store_true", help="Merge snowball exports (offline) and/or fetch via APIs (needs network).")
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="Optional offline export(s) to import; repeatable; supports csv/json/jsonl/bib.",
    )
    parser.add_argument("--max-results", type=int, default=0, help="Cap total records (0 = use queries.md / no cap).")
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(repo_root))

    from tooling.common import atomic_write_text, ensure_dir, now_iso_seconds, parse_semicolon_list, read_jsonl, write_jsonl

    workspace = Path(args.workspace).resolve()

    inputs = parse_semicolon_list(args.inputs) or ["queries.md"]
    outputs = parse_semicolon_list(args.outputs) or ["papers/papers_raw.jsonl", "papers/retrieval_report.md"]

    out_jsonl = workspace / outputs[0]
    out_report = workspace / (outputs[1] if len(outputs) > 1 else "papers/retrieval_report.md")

    queries_path = workspace / inputs[0]
    keywords, excludes, max_results_md, year_from, year_to = _parse_queries_md(queries_path)

    max_results = int(args.max_results) if int(args.max_results) > 0 else (max_results_md or 0)

    imported_at = now_iso_seconds()

    records: list[dict[str, Any]] = []
    route_to_source_paths: dict[str, set[str]] = {}
    online_status: str = "SKIPPED"
    online_errors: list[str] = []

    offline_inputs = [str(Path(p).resolve()) for p in (args.input or []) if str(p).strip()]
    if not offline_inputs and not args.online:
        offline_inputs = _detect_offline_exports(workspace)

    if offline_inputs and not args.online:
        for src_path in offline_inputs:
            p = Path(src_path)
            route = f"import:{p.name}"
            route_to_source_paths.setdefault(route, set()).add(str(p))
            try:
                recs = _convert_export(p)
            except Exception as exc:
                raise SystemExit(f"Failed to import {p}: {type(exc).__name__}: {exc}")
            for idx, rec in enumerate(recs, start=1):
                norm = _normalize_record(rec)
                _attach_provenance(
                    norm,
                    prov=RouteProvenance(
                        route=route,
                        source=str(norm.get("source") or "export"),
                        source_path=str(p),
                        imported_at=imported_at,
                        note=f"row={idx}",
                    ),
                )
                records.append(norm)

    if args.snowball and not args.online:
        snowball_inputs = _detect_snowball_exports(workspace)
        for src_path in snowball_inputs:
            p = Path(src_path)
            route = f"snowball:{p.name}"
            route_to_source_paths.setdefault(route, set()).add(str(p))
            try:
                recs = _convert_export(p)
            except Exception as exc:
                raise SystemExit(f"Failed to import snowball export {p}: {type(exc).__name__}: {exc}")
            for idx, rec in enumerate(recs, start=1):
                norm = _normalize_record(rec)
                _attach_provenance(
                    norm,
                    prov=RouteProvenance(
                        route=route,
                        source=str(norm.get("source") or "export"),
                        source_path=str(p),
                        imported_at=imported_at,
                        note=f"row={idx}",
                    ),
                )
                records.append(norm)


    # Pinned classics/surveys (agent topics): ensure key anchor works are present even if keyword
    # search/ranking misses them. Best-effort (non-fatal on network errors).
    pinned_ids = _pinned_arxiv_ids(workspace=workspace, keywords=keywords)
    if pinned_ids:
        try:
            pinned = _fetch_arxiv_id_list(ids=pinned_ids, excludes=excludes, year_from=year_from, year_to=year_to)
        except KeyboardInterrupt:
            raise
        except BaseException as exc:
            online_errors.append(f"Pinned arXiv ids: {type(exc).__name__}: {exc}")
        else:
            for rec in pinned:
                norm = _normalize_record(rec)
                aid = str(norm.get('arxiv_id') or '').strip()
                route = f"pinned_arxiv_id:{aid}" if aid else "pinned_arxiv_id"
                _attach_provenance(
                    norm,
                    prov=RouteProvenance(
                        route=route,
                        source="arxiv",
                        source_path="https://export.arxiv.org/api/query?id_list=...",
                        imported_at=imported_at,
                    ),
                )
                records.append(norm)

    # Online retrieval policy:
    # - If explicitly requested via --online: always try.
    # - Otherwise, when the current pool is smaller than a reasonable minimum,
    #   try online retrieval as a best-effort expansion step (so a single seed
    #   import doesn't trap the pipeline in offline-only mode).
    desired_min = 200
    if max_results and max_results < desired_min:
        desired_min = max_results

    def _estimate_unique_count(rs: list[dict[str, Any]]) -> int:
        from tooling.common import normalize_title_for_dedupe

        keys: set[str] = set()
        for r in rs:
            if not isinstance(r, dict):
                continue
            title = str(r.get("title") or "").strip()
            if not title:
                continue
            keys.add(_dedupe_key(r, normalize_title_for_dedupe=normalize_title_for_dedupe))
        return len(keys)

    should_try_online = bool(args.online) or (_estimate_unique_count(records) < desired_min)

    if should_try_online:
        online_status = "FAILED"
        if not keywords:
            online_errors.append(
                "No keywords found in queries.md. "
                "Add keywords (recommended) or provide larger offline exports under papers/imports/."
            )
        else:
            arxiv_error = ""
            try:
                online = _search_arxiv_paged(
                    queries=_pick_online_queries(keywords, cap=4),
                    excludes=excludes,
                    max_results=max_results or 200,
                    year_from=year_from,
                    year_to=year_to,
                )
            except KeyboardInterrupt:
                raise
            except BaseException as exc:
                online = []
                arxiv_error = f"{type(exc).__name__}: {exc}"
            for rec in online:
                norm = _normalize_record(rec)
                query = str(rec.get("_query") or "").strip()
                route = f"arxiv_query:{query}" if query else "arxiv_query"
                _attach_provenance(
                    norm,
                    prov=RouteProvenance(
                        route=route,
                        source="arxiv",
                        source_path="https://export.arxiv.org/api/query",
                        imported_at=imported_at,
                    ),
                )
                records.append(norm)

            s2_error = ""
            # If arXiv fails (common in restricted environments) or yields too little, fallback to Semantic Scholar.
            if arxiv_error or _estimate_unique_count(records) < desired_min:
                try:
                    s2_online = _search_semantic_scholar_paged(
                        queries=_pick_online_queries(keywords, cap=4),
                        excludes=excludes,
                        max_results=max_results or 200,
                        year_from=year_from,
                        year_to=year_to,
                    )
                except KeyboardInterrupt:
                    raise
                except BaseException as exc:
                    s2_online = []
                    s2_error = f"{type(exc).__name__}: {exc}"
                for rec in s2_online:
                    norm = _normalize_record(rec)
                    query = str(rec.get("_query") or "").strip()
                    route = f"s2_query:{query}" if query else "s2_query"
                    _attach_provenance(
                        norm,
                        prov=RouteProvenance(
                            route=route,
                            source="semantic_scholar",
                            source_path="https://api.semanticscholar.org/graph/v1/paper/search",
                            imported_at=imported_at,
                        ),
                    )
                    records.append(norm)

            if arxiv_error:
                online_errors.append(f"arXiv: {arxiv_error}")
            if s2_error:
                online_errors.append(f"Semantic Scholar: {s2_error}")

            if _estimate_unique_count(records) > 0:
                online_status = "OK"

    # Basic filters.
    if year_from or year_to:
        records = [r for r in records if _within_year_window(r.get("year"), year_from=year_from, year_to=year_to)]

    deduped = _dedupe_merge(records)

    if max_results and len(deduped) > max_results:
        pinned_for_cap = _pinned_arxiv_ids(workspace=workspace, keywords=keywords)
        if pinned_for_cap:
            deduped = _cap_keep_pinned_arxiv(deduped, max_results=max_results, pinned_arxiv_ids=pinned_for_cap)
        else:
            deduped = deduped[:max_results]

    # Write outputs.
    write_jsonl(out_jsonl, deduped)
    _write_csv_index(out_jsonl.with_suffix(".csv"), deduped)

    ensure_dir(out_report.parent)
    atomic_write_text(
        out_report,
        _render_report(
            workspace=workspace,
            queries_path=queries_path,
            keywords=keywords,
            excludes=excludes,
            year_from=year_from,
            year_to=year_to,
            offline_inputs=offline_inputs,
            snowball_inputs=_detect_snowball_exports(workspace) if args.snowball else [],
            online_status=online_status,
            online_error="; ".join([e for e in online_errors if str(e).strip()]),
            total_in=len(records),
            total_out=len(deduped),
            records=deduped,
        ),
    )
    return 0


def _detect_offline_exports(workspace: Path) -> list[str]:
    candidates: list[Path] = []

    def _add(p: Path) -> None:
        if p.exists() and p.is_file():
            candidates.append(p)

    base = workspace / "papers"
    for stem in ("import", "arxiv_export"):
        for ext in ("csv", "json", "jsonl", "bib"):
            _add(base / f"{stem}.{ext}")

    imports_dir = base / "imports"
    if imports_dir.exists() and imports_dir.is_dir():
        for p in sorted(imports_dir.glob("*")):
            if p.suffix.lower() in {".csv", ".json", ".jsonl", ".bib"}:
                candidates.append(p)

    # Deduplicate while preserving order.
    out: list[str] = []
    seen: set[str] = set()
    for p in candidates:
        sp = str(p)
        if sp in seen:
            continue
        seen.add(sp)
        out.append(sp)
    return out


def _detect_snowball_exports(workspace: Path) -> list[str]:
    base = workspace / "papers" / "snowball"
    if not base.exists() or not base.is_dir():
        return []
    out: list[str] = []
    for p in sorted(base.glob("*")):
        if p.is_file() and p.suffix.lower() in {".csv", ".json", ".jsonl", ".bib"}:
            out.append(str(p))
    return out


def _convert_export(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return _load_jsonl(path)
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        if isinstance(data, list):
            return [dict(x) for x in data if isinstance(x, dict)]
        if isinstance(data, dict) and isinstance(data.get("papers"), list):
            return [dict(x) for x in data["papers"] if isinstance(x, dict)]
        raise ValueError("JSON export must be a list of records or a dict with key 'papers'")
    if suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return [dict(row) for row in reader]
    if suffix == ".bib":
        return _load_bib(path)
    raise ValueError(f"Unsupported export format: {path}")


def _load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                records.append(obj)
    return records


def _load_bib(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    entries = _split_bib_entries(text)
    out: list[dict] = []
    for entry in entries:
        parsed = _parse_bib_entry(entry)
        if not parsed:
            continue
        out.append(parsed)
    return out


def _split_bib_entries(text: str) -> list[str]:
    entries: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        at = text.find("@", i)
        if at < 0:
            break
        brace = text.find("{", at)
        if brace < 0:
            break
        depth = 0
        end = -1
        for j in range(brace, n):
            ch = text[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end < 0:
            break
        entries.append(text[at : end + 1].strip())
        i = end + 1
    return entries


def _parse_bib_entry(entry: str) -> dict[str, Any] | None:
    m = re.match(r"(?is)^@(?P<typ>\w+)\s*\{\s*(?P<key>[^,\s]+)\s*,", entry)
    if not m:
        return None

    body_start = m.end()
    body = entry[body_start : entry.rfind("}")].strip()
    fields = _parse_bib_fields(body)

    title = _clean_bib_value(str(fields.get("title") or "")).strip()
    year = _clean_bib_value(str(fields.get("year") or "")).strip()
    url = _clean_bib_value(str(fields.get("url") or "")).strip()
    doi = _normalize_doi(_clean_bib_value(str(fields.get("doi") or "")).strip())
    abstract = _clean_bib_value(str(fields.get("abstract") or "")).strip()
    if not url and doi:
        url = _doi_url(doi)

    author_raw = _clean_bib_value(str(fields.get("author") or "")).strip()
    authors = _split_bib_authors(author_raw)

    eprint = _clean_bib_value(str(fields.get("eprint") or "")).strip()
    archive_prefix = _clean_bib_value(str(fields.get("archiveprefix") or fields.get("archivePrefix") or "")).strip()

    arxiv_id = ""
    if eprint and archive_prefix.lower() == "arxiv":
        arxiv_id = eprint
    if not arxiv_id and url and "arxiv.org" in url:
        arxiv_id = _extract_arxiv_id(url)

    pdf_url = _clean_bib_value(str(fields.get("pdf") or fields.get("pdf_url") or "")).strip()
    if not pdf_url and arxiv_id:
        pdf_url = _default_pdf_url(arxiv_id)

    venue = _clean_bib_value(str(fields.get("booktitle") or fields.get("journal") or "")).strip()

    # Best-effort parse year.
    year_int: int | str = ""
    try:
        if year:
            year_int = int(re.findall(r"\d{4}", year)[0])
    except Exception:
        year_int = ""

    if not title:
        return None

    return {
        "title": title,
        "authors": authors,
        "year": year_int,
        "url": url or (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""),
        "abstract": abstract,
        "source": "bib",
        "arxiv_id": arxiv_id,
        "pdf_url": pdf_url,
        "doi": doi,
        "venue": venue,
        "bibkey": str(m.group("key") or "").strip(),
    }


def _parse_bib_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    i = 0
    n = len(body)
    while i < n:
        # Skip whitespace and trailing commas.
        while i < n and body[i] in "\r\n\t ,":
            i += 1
        if i >= n:
            break

        # Field name.
        name_start = i
        while i < n and re.match(r"[A-Za-z0-9_\-]", body[i]):
            i += 1
        name = body[name_start:i].strip().lower()
        if not name:
            break

        while i < n and body[i].isspace():
            i += 1
        if i >= n or body[i] != "=":
            # Malformed; skip to next comma.
            nxt = body.find(",", i)
            if nxt < 0:
                break
            i = nxt + 1
            continue
        i += 1
        while i < n and body[i].isspace():
            i += 1

        # Field value.
        if i < n and body[i] == "{":
            depth = 0
            start = i
            while i < n:
                ch = body[i]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
            value = body[start:i].strip()
        elif i < n and body[i] == '"':
            i += 1
            start = i
            while i < n:
                if body[i] == '"' and body[i - 1] != "\\":
                    break
                i += 1
            value = body[start:i].strip()
            if i < n and body[i] == '"':
                i += 1
        else:
            start = i
            while i < n and body[i] not in ",\r\n":
                i += 1
            value = body[start:i].strip()

        fields[name] = value
        # Move to next comma.
        nxt = body.find(",", i)
        i = (nxt + 1) if nxt >= 0 else n
    return fields


def _clean_bib_value(value: str) -> str:
    v = (value or "").strip()
    if v.startswith("{") and v.endswith("}"):
        v = v[1:-1].strip()
    return v


def _split_bib_authors(author: str) -> list[str]:
    author = (author or "").strip()
    if not author:
        return []
    parts = [p.strip() for p in author.replace("\n", " ").split(" and ") if p.strip()]
    out: list[str] = []
    for p in parts:
        p = re.sub(r"\s+", " ", p).strip()
        if p:
            out.append(p)
    return out


def _normalize_record(rec: dict) -> dict[str, Any]:
    title = str(rec.get("title") or "").strip()
    url = str(rec.get("url") or rec.get("id") or "").strip()

    authors = rec.get("authors") or rec.get("author") or []
    if isinstance(authors, str):
        # tolerate CSV exports "a;b" or bib-like "a and b".
        if " and " in authors:
            authors = _split_bib_authors(authors)
        else:
            authors = [a.strip() for a in authors.split(";") if a.strip()]
    if not isinstance(authors, list):
        authors = []

    year = rec.get("year")
    try:
        year = int(year) if year is not None and str(year).strip() else ""
    except ValueError:
        year = ""

    abstract = str(rec.get("abstract") or rec.get("summary") or "").strip()

    arxiv_id = str(rec.get("arxiv_id") or rec.get("arxiv") or "").strip()
    if not arxiv_id:
        arxiv_id = str(rec.get("eprint") or "").strip()
    if not arxiv_id and url and "arxiv.org/" in url:
        arxiv_id = _extract_arxiv_id(url)

    doi = _normalize_doi(str(rec.get("doi") or ""))
    if not url and doi:
        url = _doi_url(doi)

    pdf_url = str(rec.get("pdf_url") or rec.get("pdf") or "").strip()
    if not pdf_url and arxiv_id:
        pdf_url = _default_pdf_url(arxiv_id)

    categories = rec.get("categories") or []
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.split(",") if c.strip()]
    if not isinstance(categories, list):
        categories = []

    primary_category = str(rec.get("primary_category") or "").strip()

    source = str(rec.get("source") or "").strip() or "export"

    return {
        **{k: v for k, v in rec.items() if k in {"bibkey"} and v},
        "title": title,
        "authors": authors,
        "year": year,
        "url": url,
        "abstract": abstract,
        "source": source,
        "arxiv_id": arxiv_id,
        "pdf_url": pdf_url,
        "categories": categories,
        "primary_category": primary_category,
        "doi": doi,
        "venue": str(rec.get("venue") or rec.get("journal_ref") or rec.get("journal") or rec.get("booktitle") or "").strip(),
        "published": str(rec.get("published") or "").strip(),
        "updated": str(rec.get("updated") or "").strip(),
        "provenance": rec.get("provenance") if isinstance(rec.get("provenance"), list) else [],
    }


def _attach_provenance(record: dict[str, Any], *, prov: RouteProvenance) -> None:
    prov_list = record.get("provenance")
    if not isinstance(prov_list, list):
        prov_list = []
    prov_list.append(
        {
            "route": prov.route,
            "source": prov.source,
            "source_path": prov.source_path,
            "imported_at": prov.imported_at,
            "note": prov.note,
        }
    )
    record["provenance"] = prov_list


def _dedupe_merge(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from tooling.common import normalize_title_for_dedupe

    best: dict[str, dict[str, Any]] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        title = str(rec.get("title") or "").strip()
        if not title:
            continue
        key = _dedupe_key(rec, normalize_title_for_dedupe=normalize_title_for_dedupe)
        prev = best.get(key)
        if not prev:
            best[key] = rec
            continue
        best[key] = _merge_records(prev, rec)

    out = list(best.values())
    out.sort(key=lambda r: (-(int(r.get("year") or 0)), str(r.get("title") or "")))
    return out


def _dedupe_key(rec: dict[str, Any], *, normalize_title_for_dedupe) -> str:
    arxiv_id = _strip_arxiv_version(str(rec.get("arxiv_id") or "").strip())
    if arxiv_id:
        return f"arxiv:{arxiv_id}"
    doi = str(rec.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    url = str(rec.get("url") or "").strip()
    if url:
        return f"url:{_canonical_url(url)}"
    year = rec.get("year")
    try:
        year_int = int(year) if year is not None and str(year).strip() else ""
    except Exception:
        year_int = ""
    return f"title:{normalize_title_for_dedupe(str(rec.get('title') or ''))}::{year_int}"


def _merge_records(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    def _pick_str(x: Any, y: Any) -> str:
        xs = str(x or "").strip()
        ys = str(y or "").strip()
        return ys if len(ys) > len(xs) else xs

    def _pick_year(x: Any, y: Any) -> int | str:
        for v in (x, y):
            try:
                if v is None:
                    continue
                s = str(v).strip()
                if not s:
                    continue
                return int(s)
            except Exception:
                continue
        return ""

    def _pick_list(x: Any, y: Any) -> list:
        xl = x if isinstance(x, list) else []
        yl = y if isinstance(y, list) else []
        return yl if len(yl) > len(xl) else xl

    merged = dict(a)
    merged["title"] = _pick_str(a.get("title"), b.get("title"))
    merged["abstract"] = _pick_str(a.get("abstract"), b.get("abstract"))
    merged["url"] = _pick_str(a.get("url"), b.get("url"))
    merged["pdf_url"] = _pick_str(a.get("pdf_url"), b.get("pdf_url"))
    merged["arxiv_id"] = _pick_str(a.get("arxiv_id"), b.get("arxiv_id"))
    merged["doi"] = _pick_str(a.get("doi"), b.get("doi"))
    merged["venue"] = _pick_str(a.get("venue"), b.get("venue"))
    merged["year"] = _pick_year(a.get("year"), b.get("year"))
    merged["authors"] = _pick_list(a.get("authors"), b.get("authors"))
    merged["categories"] = _pick_list(a.get("categories"), b.get("categories"))
    merged["primary_category"] = _pick_str(a.get("primary_category"), b.get("primary_category"))

    prov_a = a.get("provenance") if isinstance(a.get("provenance"), list) else []
    prov_b = b.get("provenance") if isinstance(b.get("provenance"), list) else []
    prov_all = []
    seen: set[tuple[str, str, str]] = set()
    for p in list(prov_a) + list(prov_b):
        if not isinstance(p, dict):
            continue
        route = str(p.get("route") or "").strip()
        source_path = str(p.get("source_path") or "").strip()
        imported_at = str(p.get("imported_at") or "").strip()
        key = (route, source_path, imported_at)
        if key in seen:
            continue
        seen.add(key)
        prov_all.append(p)
    merged["provenance"] = prov_all

    merged["source"] = _pick_str(a.get("source"), b.get("source"))
    return merged


def _write_csv_index(path: Path, records: list[dict[str, Any]]) -> None:
    from tooling.common import ensure_dir

    ensure_dir(path.parent)
    fieldnames = [
        "title",
        "year",
        "url",
        "arxiv_id",
        "doi",
        "venue",
        "primary_category",
        "categories",
        "pdf_url",
        "source",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            cats = rec.get("categories") or []
            if isinstance(cats, list):
                cats = ",".join([str(c).strip() for c in cats if str(c).strip()])
            writer.writerow(
                {
                    "title": str(rec.get("title") or "").strip(),
                    "year": str(rec.get("year") or "").strip(),
                    "url": str(rec.get("url") or "").strip(),
                    "arxiv_id": str(rec.get("arxiv_id") or "").strip(),
                    "doi": str(rec.get("doi") or "").strip(),
                    "venue": str(rec.get("venue") or "").strip(),
                    "primary_category": str(rec.get("primary_category") or "").strip(),
                    "categories": str(cats or "").strip(),
                    "pdf_url": str(rec.get("pdf_url") or "").strip(),
                    "source": str(rec.get("source") or "").strip(),
                }
            )


def _render_report(
    *,
    workspace: Path,
    queries_path: Path,
    keywords: list[str],
    excludes: list[str],
    year_from: int | None,
    year_to: int | None,
    offline_inputs: list[str],
    snowball_inputs: list[str],
    online_status: str,
    online_error: str = "",
    total_in: int,
    total_out: int,
    records: list[dict[str, Any]],
) -> str:
    # Route coverage.
    route_to_keys: dict[str, set[str]] = {}

    def _rec_key(rec: dict[str, Any]) -> str:
        aid = _strip_arxiv_version(str(rec.get("arxiv_id") or "").strip())
        if aid:
            return f"arxiv:{aid}"
        doi = str(rec.get("doi") or "").strip().lower()
        if doi:
            return f"doi:{doi}"
        url = str(rec.get("url") or "").strip()
        if url:
            return f"url:{_canonical_url(url)}"
        return f"title:{str(rec.get('title') or '').strip()}::{str(rec.get('year') or '').strip()}"

    missing_id = 0
    missing_abstract = 0
    missing_authors = 0

    for rec in records:
        if not isinstance(rec, dict):
            continue
        rid = _rec_key(rec)
        if not str(rec.get("arxiv_id") or "").strip() and not str(rec.get("doi") or "").strip() and not str(rec.get("url") or "").strip():
            missing_id += 1
        if not str(rec.get("abstract") or "").strip():
            missing_abstract += 1
        auth = rec.get("authors")
        if not isinstance(auth, list) or not [a for a in auth if str(a).strip()]:
            missing_authors += 1

        prov = rec.get("provenance") or []
        if not isinstance(prov, list):
            continue
        for p in prov:
            if not isinstance(p, dict):
                continue
            route = str(p.get("route") or "").strip() or "(unknown)"
            route_to_keys.setdefault(route, set()).add(rid)

    lines: list[str] = [
        "# Retrieval report",
        "",
        f"- Workspace: `{workspace}`",
        f"- queries.md: `{queries_path}`",
        f"- Keywords: `{len(keywords)}`",
        f"- Excludes: `{len(excludes)}`",
        f"- Time window: `{year_from or ''}`..`{year_to or ''}`",
        f"- Online retrieval (best-effort): `{online_status}`",
        "",
        f"## Summary",
        "",
        f"- Imported/collected records (pre-dedupe): `{total_in}`",
        f"- Deduped records (output): `{total_out}`",
        f"- Online error: `{online_error}`" if online_error else "- Online error: (none)",
        f"- Missing stable ID (arxiv_id/doi/url all empty): `{missing_id}`",
        f"- Missing abstract: `{missing_abstract}`",
        f"- Missing authors: `{missing_authors}`",
        "",
        "## Sources",
        "",
        f"- Offline inputs: `{len(offline_inputs)}`",
    ]
    for p in offline_inputs[:20]:
        lines.append(f"  - `{p}`")
    if len(offline_inputs) > 20:
        lines.append("  - ...")

    lines.append(f"- Snowball inputs: `{len(snowball_inputs)}`")
    for p in snowball_inputs[:20]:
        lines.append(f"  - `{p}`")
    if len(snowball_inputs) > 20:
        lines.append("  - ...")

    lines.extend(["", "## Coverage buckets (by route)", "", "| route | unique_papers |", "|---|---:|"])
    for route, keys in sorted(route_to_keys.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        lines.append(f"| {route} | {len(keys)} |")

    lines.extend(
        [
            "",
            "## Next actions",
            "",
            "- If the pool is too small: add more exports under `papers/imports/` (multi-route) or enable network and rerun with `--online`.",
            "- If cite coverage is poor later: increase candidate pool size and run snowballing (provide exports under `papers/snowball/`).",
            "- If many abstracts are missing: provide richer exports or rerun online enrichment.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"



def _pick_online_queries(keywords: list[str], *, cap: int = 4) -> list[str]:
    uniq: list[str] = []
    seen: set[str] = set()
    for q in keywords or []:
        q = str(q or "").strip()
        if not q:
            continue
        ql = q.lower()
        if ql in seen:
            continue
        seen.add(ql)
        uniq.append(q)

    def _score(q: str) -> float:
        ql = q.lower()
        score = 0.0
        if any(tok in ql for tok in ("survey", "review", "综述", "调研")):
            score += 5.0
        if "agent" in ql:
            score += 3.0
        if "llm" in ql or "language model" in ql:
            score += 2.0
        if any(tok in ql for tok in ("tool", "function calling", "tool-use", "tool use")):
            score += 1.0
        # Prefer shorter, reusable queries.
        score -= min(2.0, len(q) / 200.0)
        return score

    uniq.sort(key=_score, reverse=True)
    return uniq[: max(1, int(cap))]


def _is_excluded_text(text: str, excludes: list[str]) -> bool:
    if not excludes:
        return False
    blob = (text or "").lower()
    for ex in excludes:
        ex = str(ex or "").strip().lower()
        if not ex:
            continue
        if ex in blob:
            return True
    return False


def _semantic_scholar_request_json(url: str, *, timeout: int = 30, max_retries: int = 5) -> dict[str, Any]:
    """Fetch Semantic Scholar JSON via the r.jina.ai proxy.

    Rationale: some environments intermittently fail TLS handshakes to external domains;
    r.jina.ai provides a stable, cache-friendly fetch path.

    Note: r.jina.ai has changed formats over time:
    - Legacy: plain text wrapper with `Markdown Content:` then raw JSON.
    - Current: JSON envelope with `data.content` containing the upstream body as a string.
    This helper supports both to keep retrieval robust.
    """
    headers = {
        "User-Agent": "research-units-pipeline-skills/1.0 (+https://github.com/anthropics/skills)",
        "Accept": "application/json",
    }
    proxy_url = "https://r.jina.ai/" + url
    req = urllib.request.Request(proxy_url, headers=headers, method="GET")
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            text = raw.decode("utf-8", errors="ignore")

            payload = text

            # r.jina.ai wraps the upstream response body; extract it.
            marker = "Markdown Content:"
            if marker in text:
                payload = text.split(marker, 1)[1].lstrip()
            else:
                # New: JSON envelope with `data.content` as a string.
                try:
                    outer = json.loads(text)
                except Exception:
                    outer = None
                if isinstance(outer, dict):
                    try:
                        code = int(outer.get("code") or 0)
                    except Exception:
                        code = 0
                    if code in {429, 500, 502, 503, 504}:
                        time.sleep(min(20.0, 1.5 * (2**attempt)))
                        continue
                    data = outer.get("data")
                    if isinstance(data, dict):
                        content = data.get("content")
                        if isinstance(content, str) and content.strip():
                            payload = content.strip()

            try:
                obj = json.loads(payload or "{}")
            except Exception as exc:
                # Common rate limit / upstream errors are rendered as plain text.
                pl = (payload or "").lstrip()
                if (not pl) or pl.startswith("<") or "returned error 429" in text or "Too Many Requests" in text or "HTTP Error 429" in text:
                    time.sleep(min(20.0, 1.5 * (2**attempt)))
                    continue
                last_exc = exc
                time.sleep(min(10.0, 1.25 * (2**attempt)))
                continue

            if not isinstance(obj, dict):
                return {}

            # Semantic Scholar may return structured error JSON (no `data`).
            if obj.get("error") or obj.get("message"):
                msg = str(obj.get("error") or obj.get("message") or "").lower()
                if "too many requests" in msg or "rate limit" in msg or "429" in msg:
                    time.sleep(min(20.0, 1.5 * (2**attempt)))
                    continue
                raise SystemExit(f"Semantic Scholar error: {obj.get('error') or obj.get('message')}")

            return obj
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if int(getattr(exc, "code", 0)) in {429, 500, 502, 503, 504}:
                time.sleep(min(20.0, 1.5 * (2**attempt)))
                continue
            raise
        except Exception as exc:
            last_exc = exc
            time.sleep(min(10.0, 1.25 * (2**attempt)))
            continue
    raise SystemExit(f"Semantic Scholar request failed after {max_retries} retries: {last_exc}")


def _search_semantic_scholar_paged(
    *,
    queries: list[str],
    excludes: list[str],
    max_results: int,
    year_from: int | None,
    year_to: int | None,
) -> list[dict[str, Any]]:
    picked = _pick_online_queries(queries, cap=4)
    if not picked:
        return []

    target = max(1, int(max_results))
    page_size = min(100, target)
    out: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    fields = ",".join(["title", "authors", "year", "abstract", "url", "externalIds", "venue"])

    for q in picked:
        offset = 0
        # Per-query cap: avoid spending the entire budget on one weak query.
        per_query_cap = max(50, target // max(1, len(picked)))
        while len(out) < target and offset < 5000 and offset < per_query_cap:
            url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(
                {
                    "query": q,
                    "limit": page_size,
                    "offset": offset,
                    "fields": fields,
                }
            )
            payload = _semantic_scholar_request_json(url)
            data = payload.get("data") or []
            if not isinstance(data, list) or not data:
                break

            for paper in data:
                if not isinstance(paper, dict):
                    continue
                rec = _semantic_scholar_to_record(paper, query=q)
                if not rec:
                    continue

                # Stable-id only: downstream gates assume arxiv_id/doi coverage.
                aid = _strip_arxiv_version(str(rec.get("arxiv_id") or "").strip())
                doi = str(rec.get("doi") or "").strip().lower()
                if not aid and not doi:
                    continue

                blob = f"{rec.get('title','')}\n{rec.get('abstract','')}"
                if _is_excluded_text(blob, excludes):
                    continue
                if year_from or year_to:
                    if not _within_year_window(rec.get("year"), year_from=year_from, year_to=year_to):
                        continue

                key = f"arxiv:{aid}" if aid else f"doi:{doi}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                out.append(rec)

                if len(out) >= target:
                    break

            offset += len(data)
            if len(data) < page_size:
                break
            time.sleep(1.0)
        time.sleep(0.5)
        if len(out) >= target:
            break

    return out[:target]


def _semantic_scholar_to_record(paper: dict[str, Any], *, query: str) -> dict[str, Any] | None:
    title = str(paper.get("title") or "").strip()
    if not title:
        return None

    ext = paper.get("externalIds") or {}
    if not isinstance(ext, dict):
        ext = {}

    arxiv_id = str(ext.get("ArXiv") or ext.get("arxiv") or ext.get("arxivId") or "").strip()
    doi = _normalize_doi(str(ext.get("DOI") or ext.get("doi") or "").strip())

    url = str(paper.get("url") or "").strip()
    if arxiv_id:
        url = f"https://arxiv.org/abs/{arxiv_id}"
    elif doi:
        url = _doi_url(doi)

    authors = paper.get("authors") or []
    author_names: list[str] = []
    if isinstance(authors, list):
        for a in authors:
            if isinstance(a, dict):
                name = str(a.get("name") or "").strip()
                if name:
                    author_names.append(name)

    year = paper.get("year")
    try:
        year = int(year) if year is not None and str(year).strip() else ""
    except ValueError:
        year = ""

    abstract = str(paper.get("abstract") or "").strip()
    venue = str(paper.get("venue") or "").strip()

    pdf_url = _default_pdf_url(arxiv_id) if arxiv_id else ""

    return {
        "title": title,
        "authors": author_names,
        "year": year,
        "url": url,
        "abstract": abstract,
        "source": "semantic_scholar",
        "arxiv_id": arxiv_id,
        "pdf_url": pdf_url,
        "doi": doi,
        "venue": venue,
        "_query": query,
    }


def _parse_queries_md(path: Path) -> tuple[list[str], list[str], int | None, int | None, int | None]:
    if not path.exists():
        return ([], [], None, None, None)
    keywords: list[str] = []
    excludes: list[str] = []
    mode: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    max_results: int | None = None

    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if line.startswith("- keywords:"):
            mode = "keywords"
            continue
        if line.startswith("- exclude:"):
            mode = "exclude"
            continue
        if line.startswith("- time window:"):
            mode = "time"
            continue
        if line.startswith("- max_results:"):
            value = line.split(":", 1)[1].strip().strip('"').strip("'")
            try:
                max_results = int(value)
            except Exception:
                max_results = None
            mode = None
            continue
        if line.startswith("- ") and mode in {"keywords", "exclude"}:
            value = line[2:].strip().strip('"').strip("'")
            if not value:
                continue
            if mode == "keywords":
                keywords.append(value)
            else:
                excludes.append(value)
            continue
        if mode == "time" and line.startswith("- from:"):
            year_from = _parse_year(line.split(":", 1)[1].strip().strip('"').strip("'"))
            continue
        if mode == "time" and line.startswith("- to:"):
            year_to = _parse_year(line.split(":", 1)[1].strip().strip('"').strip("'"))
            continue

    return (keywords, excludes, max_results, year_from, year_to)



def _pinned_arxiv_ids(*, workspace: Path, keywords: list[str]) -> list[str]:
    """Return a stable arXiv-id pin list for topics that need canonical anchors.

    Rationale: keyword retrieval can miss “must-cite” classics; downstream writing then becomes
    either generic or forced to delete those anchors due to missing BibTeX keys.
    """

    text = "\n".join([str(k or "") for k in (keywords or [])])
    goal_path = workspace / "GOAL.md"
    if goal_path.exists():
        text += "\n" + goal_path.read_text(encoding="utf-8", errors="ignore")

    low = text.lower()
    llm_agent = ("agent" in low or "agents" in low) and ("llm" in low or "language model" in low or "gpt" in low)
    has_triggers = any(t in low for t in ["react", "toolformer", "reflexion", "voyager", "tree of thoughts"])
    if not (llm_agent or has_triggers):
        return []

    # Canonical LLM-agent classics (also referenced by `dedupe-rank` pinning).
    classics = [
        "2210.03629",  # ReAct
        "2302.04761",  # Toolformer
        "2303.11366",  # Reflexion
        "2305.10601",  # Tree of Thoughts
        "2305.16291",  # Voyager
    ]

    # A small survey/review seed set for Related Work positioning.
    surveys = [
        "2308.11432",  # A Survey on Large Language Model based Autonomous Agents
        "2503.21460",  # Large Language Model Agent: A Survey on Methodology, Applications and Challenges
        "2503.23037",  # Agentic Large Language Models, a survey
        "2411.18279",  # Large Language Model-Brained GUI Agents: A Survey
    ]

    # Preserve order and de-dupe.
    out: list[str] = []
    for aid in classics + surveys:
        if aid not in out:
            out.append(aid)
    return out



def _parse_year(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        year = int(value)
    except Exception:
        return None
    return year if 1900 <= year <= 2100 else None


def _within_year_window(year: Any, *, year_from: int | None, year_to: int | None) -> bool:
    if not year_from and not year_to:
        return True
    try:
        y = int(year)
    except Exception:
        return False
    if year_from and y < year_from:
        return False
    if year_to and y > year_to:
        return False
    return True


def _strip_arxiv_version(arxiv_id: str) -> str:
    arxiv_id = (arxiv_id or "").strip()
    return re.sub(r"v\d+$", "", arxiv_id)




def _cap_keep_pinned_arxiv(records: list[dict[str, Any]], *, max_results: int, pinned_arxiv_ids: list[str]) -> list[dict[str, Any]]:
    """Cap a sorted record list while keeping pinned arXiv IDs.

    Rationale: we often cap `papers_raw` (e.g., max_results=800) but the pool is sorted by recency;
    without this, must-cite classics (older) can be truncated out before `dedupe-rank` pinning runs.
    """

    cap = max(1, int(max_results))
    pins = [_strip_arxiv_version(str(a).strip()) for a in (pinned_arxiv_ids or []) if str(a).strip()]
    pin_set = set([p for p in pins if p])
    if not pin_set:
        return records[:cap]

    pinned_map: dict[str, dict[str, Any]] = {}
    rest: list[dict[str, Any]] = []
    for rec in records:
        aid = _strip_arxiv_version(str(rec.get("arxiv_id") or "").strip())
        if aid and aid in pin_set and aid not in pinned_map:
            pinned_map[aid] = rec
            continue
        rest.append(rec)

    pinned_list = [pinned_map[aid] for aid in pins if aid in pinned_map]
    out = pinned_list + rest
    return out[:cap]

def _extract_arxiv_id(url_abs: str) -> str:
    url_abs = (url_abs or "").strip()
    if not url_abs:
        return ""
    parsed = urllib.parse.urlparse(url_abs)
    parts = [p for p in (parsed.path or "").split("/") if p]
    if not parts:
        return ""
    if parts[0] in {"abs", "pdf"} and len(parts) >= 2:
        return parts[1].replace(".pdf", "")
    return parts[-1].replace(".pdf", "")


def _default_pdf_url(arxiv_id: str) -> str:
    arxiv_id = (arxiv_id or "").strip()
    if not arxiv_id:
        return ""
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


def _normalize_doi(doi: str) -> str:
    doi = (doi or "").strip()
    if not doi:
        return ""
    doi = re.sub(r"(?i)^https?://doi\.org/", "", doi).strip()
    doi = re.sub(r"(?i)^doi\s*:\s*", "", doi).strip()
    return doi


def _doi_url(doi: str) -> str:
    doi = _normalize_doi(doi)
    if not doi:
        return ""
    return f"https://doi.org/{doi}"


def _canonical_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path
    # Prefer abs over pdf.
    if "arxiv.org" in netloc and path.startswith("/pdf/"):
        path = "/abs/" + path.split("/pdf/", 1)[1].replace(".pdf", "")
    return urllib.parse.urlunparse((scheme, netloc, path, "", "", ""))


# --- Online arXiv API retrieval (best-effort) ---



def _fetch_arxiv_id_list(
    *,
    ids: list[str],
    excludes: list[str],
    year_from: int | None,
    year_to: int | None,
) -> list[dict[str, Any]]:
    ids = [str(i).strip() for i in (ids or []) if str(i).strip()]
    if not ids:
        return []

    def chunked(xs: list[str], n: int) -> list[list[str]]:
        out: list[list[str]] = []
        for i in range(0, len(xs), n):
            out.append(xs[i : i + n])
        return out

    all_records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for chunk in chunked(ids, 24):
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"id_list": ",".join(chunk)})
        batch, raw_count = _search_arxiv_once(url=url, query=f"id_list:{','.join(chunk)}", excludes=excludes, year_from=year_from, year_to=year_to)
        if raw_count <= 0:
            continue
        for rec in batch:
            rec_url = str(rec.get("url") or "").strip()
            if rec_url and rec_url in seen_urls:
                continue
            if rec_url:
                seen_urls.add(rec_url)
            all_records.append(rec)
        time.sleep(3.0)

    return all_records

def _search_arxiv_paged(
    *,
    queries: list[str],
    excludes: list[str],
    max_results: int,
    year_from: int | None,
    year_to: int | None,
) -> list[dict[str, Any]]:
    q = _build_arxiv_query(queries)
    if not q:
        return []
    target = max(1, int(max_results))

    page_size = min(200, target)
    all_records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    start = 0
    while len(all_records) < target:
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
            {"search_query": q, "start": start, "max_results": page_size}
        )
        batch, raw_count = _search_arxiv_once(url=url, query=q, excludes=excludes, year_from=year_from, year_to=year_to)
        if raw_count == 0:
            break
        for rec in batch:
            rec_url = str(rec.get("url") or "").strip()
            if rec_url and rec_url in seen_urls:
                continue
            if rec_url:
                seen_urls.add(rec_url)
            all_records.append(rec)
        start += raw_count
        if raw_count < page_size:
            break
        time.sleep(3.0)
    return all_records[:target]


def _search_arxiv_once(
    *,
    url: str,
    query: str,
    excludes: list[str],
    year_from: int | None,
    year_to: int | None,
) -> tuple[list[dict[str, Any]], int]:
    headers = {"User-Agent": "research-units-pipeline-skills/1.0 (+https://github.com/anthropics/skills)"}
    req = urllib.request.Request(url, headers=headers, method="GET")

    content = b""
    last_exc: Exception | None = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
            last_exc = None
            break
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            last_exc = exc
            time.sleep(min(10.0, 1.25 * (2**attempt)))
            continue

    if last_exc is not None or not content:
        raise SystemExit(f"arXiv request failed (network?): {last_exc}")

    root = ET.fromstring(content)
    ns = {
        "a": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    entries = root.findall("a:entry", ns)
    raw_count = len(entries)

    records: list[dict[str, Any]] = []
    for entry in entries:
        title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
        summary = (entry.findtext("a:summary", default="", namespaces=ns) or "").strip()
        published = (entry.findtext("a:published", default="", namespaces=ns) or "").strip()
        updated = (entry.findtext("a:updated", default="", namespaces=ns) or "").strip()

        year: int | str = ""
        if len(published) >= 4 and published[:4].isdigit():
            year = int(published[:4])
        if year_from or year_to:
            if not _within_year_window(year, year_from=year_from, year_to=year_to):
                continue

        url_abs = (entry.findtext("a:id", default="", namespaces=ns) or "").strip()
        arxiv_id = _extract_arxiv_id(url_abs)
        pdf_url = _extract_pdf_url(entry, ns=ns) or (_default_pdf_url(arxiv_id) if arxiv_id else "")

        authors = [(a.findtext("a:name", default="", namespaces=ns) or "").strip() for a in entry.findall("a:author", ns)]
        authors = [a for a in authors if a]

        categories = _extract_categories(entry, ns=ns)
        primary_category = _extract_primary_category(entry, ns=ns)

        doi = (entry.findtext("arxiv:doi", default="", namespaces=ns) or "").strip()
        journal_ref = (entry.findtext("arxiv:journal_ref", default="", namespaces=ns) or "").strip()
        comment = (entry.findtext("arxiv:comment", default="", namespaces=ns) or "").strip()

        record = {
            "title": title,
            "authors": authors,
            "year": year,
            "url": url_abs,
            "abstract": summary,
            "source": "arxiv",
            "arxiv_id": arxiv_id,
            "pdf_url": pdf_url,
            "categories": categories,
            "primary_category": primary_category,
            "published": published,
            "updated": updated,
            "doi": doi,
            "journal_ref": journal_ref,
            "comment": comment,
            "_query": query,
        }
        if excludes and _is_excluded(record, excludes):
            continue
        records.append(record)
    return (records, raw_count)


def _build_arxiv_query(queries: list[str]) -> str:
    queries = [q.strip() for q in (queries or []) if q and q.strip()]
    if not queries:
        return ""

    parts: list[str] = []
    for q in queries:
        if (
            (" AND " in q)
            or (" OR " in q)
            or ("NOT " in q)
            or re.search(r"\b(?:all|ti|abs|au|cat|co|jr|rn):", q)
        ):
            parts.append(q)
            continue
        if " " in q:
            parts.append(f'all:"{q}"')
        else:
            parts.append(f"all:{q}")
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return "(" + " OR ".join(parts) + ")"


def _extract_pdf_url(entry: ET.Element, *, ns: dict[str, str]) -> str:
    for link in entry.findall("a:link", ns):
        href = (link.attrib.get("href") or "").strip()
        ltype = (link.attrib.get("type") or "").strip()
        title = (link.attrib.get("title") or "").strip().lower()
        rel = (link.attrib.get("rel") or "").strip().lower()
        if not href:
            continue
        if ltype == "application/pdf" or title == "pdf":
            return href
        if rel == "related" and href.endswith(".pdf"):
            return href
    return ""


def _extract_categories(entry: ET.Element, *, ns: dict[str, str]) -> list[str]:
    out: list[str] = []
    for cat in entry.findall("a:category", ns):
        term = (cat.attrib.get("term") or "").strip()
        if term and term not in out:
            out.append(term)
    return out


def _extract_primary_category(entry: ET.Element, *, ns: dict[str, str]) -> str:
    node = entry.find("arxiv:primary_category", ns)
    if node is None:
        return ""
    return (node.attrib.get("term") or "").strip()


def _is_excluded(record: dict, excludes: list[str]) -> bool:
    hay = f"{record.get('title','')} {record.get('abstract','')}".lower()
    for term in excludes:
        term = term.strip().lower()
        if term and term in hay:
            return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
