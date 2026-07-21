from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--max-results", type=int, default=100)
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--input", default="", help="Optional CSV/JSON/JSONL export to convert (offline mode)")
    parser.add_argument(
        "--enrich-metadata",
        action="store_true",
        help="Best-effort: for records with `arxiv_id` but missing fields (abstract/authors/categories), fetch metadata via arXiv API id_list.",
    )
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve()
    for _ in range(10):
        if (repo_root / "AGENTS.md").exists():
            break
        parent = repo_root.parent
        if parent == repo_root:
            break
        repo_root = parent
    sys.path.insert(0, str(repo_root))

    from tooling.common import parse_semicolon_list, read_jsonl, write_jsonl

    workspace = Path(args.workspace).resolve()
    outputs = parse_semicolon_list(args.outputs) or ["papers/papers_raw.jsonl"]
    out_path = workspace / outputs[0]

    offline_input = args.input or _detect_offline_export(workspace)
    if offline_input:
        records = _convert_export(Path(offline_input).resolve())
        _, _, max_results, year_from, year_to, enrich_md = _parse_queries_md(workspace / "queries.md")
        if year_from or year_to:
            records = [r for r in records if _within_year_window(r.get("year"), year_from=year_from, year_to=year_to)]
        if max_results:
            records = records[: int(max_results)]
        if bool(args.enrich_metadata) or bool(enrich_md):
            _best_effort_enrich(records)
        write_jsonl(out_path, records)
        _write_csv_index(out_path.with_suffix(".csv"), records)
        return 0

    queries = list(args.query)
    excludes = list(args.exclude)
    if not queries:
        queries, excludes, max_results, year_from, year_to, _enrich_md = _parse_queries_md(workspace / "queries.md")
        if max_results:
            args.max_results = max_results
    else:
        year_from = None
        year_to = None

    if not queries:
        raise SystemExit("No query provided (use --query, fill queries.md, or place an offline export under papers/import.(csv|json|jsonl))")

    # Convenience: if the user passes a raw arXiv identifier, fetch it directly via `id_list`.
    if len(queries) == 1:
        arxiv_id = _normalize_arxiv_id_query(queries[0])
        if arxiv_id:
            url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"id_list": arxiv_id})
            records, _raw_count = _search_arxiv_once(url=url, queries=[arxiv_id], excludes=[], year_from=None, year_to=None)
            if not records:
                raise SystemExit(f"No results returned for arXiv id_list={arxiv_id} (network blocked or id not found)")
            existing = read_jsonl(out_path)
            combined = existing + records
            write_jsonl(out_path, combined)
            _write_csv_index(out_path.with_suffix(".csv"), combined)
            return 0

    records = _search_arxiv_paged(
        queries=queries,
        excludes=excludes,
        max_results=int(args.max_results),
        year_from=year_from,
        year_to=year_to,
        workspace=workspace,
    )
    if not records:
        raise SystemExit("No results returned (network blocked or query too narrow)")

    existing = read_jsonl(out_path)
    combined = existing + records
    write_jsonl(out_path, combined)
    _write_csv_index(out_path.with_suffix(".csv"), combined)
    return 0


def _convert_export(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Input not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return _load_jsonl(path)
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise SystemExit("JSON export must be a list of records")
        return [_normalize_record(rec) for rec in data]
    if suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return [_normalize_record(row) for row in reader]
    raise SystemExit(f"Unsupported export format: {path}")




def _normalize_arxiv_id_query(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    low = raw.lower()
    for prefix in ("arxiv:", "arxiv_id:", "arxiv-id:", "id:"):
        if low.startswith(prefix):
            raw = raw[len(prefix) :].strip()
            break
    raw = _strip_arxiv_version(raw)
    if re.fullmatch(r"\d{4}\.\d{4,5}", raw):
        return raw
    if re.fullmatch(r"[a-z-]+(?:\.[a-z-]+)?/\d{7}", raw):
        return raw
    return ""

def _detect_offline_export(workspace: Path) -> str:
    candidates = [
        workspace / "papers" / "import.csv",
        workspace / "papers" / "import.json",
        workspace / "papers" / "import.jsonl",
        workspace / "papers" / "arxiv_export.csv",
        workspace / "papers" / "arxiv_export.json",
        workspace / "papers" / "arxiv_export.jsonl",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return ""


def _load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(_normalize_record(json.loads(line)))
    return records


def _write_csv_index(path: Path, records: list[dict[str, Any]]) -> None:
    # Convenience artifact for humans to scan/filter.
    from tooling.common import ensure_dir

    ensure_dir(path.parent)
    fieldnames = [
        "title",
        "year",
        "url",
        "arxiv_id",
        "primary_category",
        "categories",
        "pdf_url",
        "published",
        "updated",
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
                    "primary_category": str(rec.get("primary_category") or "").strip(),
                    "categories": str(cats or "").strip(),
                    "pdf_url": str(rec.get("pdf_url") or "").strip(),
                    "published": str(rec.get("published") or "").strip(),
                    "updated": str(rec.get("updated") or "").strip(),
                }
            )


def _normalize_record(rec: dict) -> dict:
    title = str(rec.get("title") or "").strip()
    url = str(rec.get("url") or rec.get("id") or "").strip()
    authors = rec.get("authors") or rec.get("author") or []
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(";") if a.strip()]
    if not isinstance(authors, list):
        authors = []
    year = rec.get("year")
    try:
        year = int(year) if year is not None and str(year).strip() else ""
    except ValueError:
        year = ""
    abstract = str(rec.get("abstract") or rec.get("summary") or "").strip()
    arxiv_id = str(rec.get("arxiv_id") or "").strip()
    if not arxiv_id and url and "arxiv.org/" in url:
        arxiv_id = _extract_arxiv_id(url)
    pdf_url = str(rec.get("pdf_url") or "").strip()
    if not pdf_url and arxiv_id:
        pdf_url = _default_pdf_url(arxiv_id)
    return {
        "title": title,
        "authors": authors,
        "year": year,
        "url": url,
        "abstract": abstract,
        "source": rec.get("source") or "export",
        "arxiv_id": arxiv_id,
        "pdf_url": pdf_url,
        "categories": rec.get("categories") or [],
        "primary_category": str(rec.get("primary_category") or "").strip(),
        "published": str(rec.get("published") or "").strip(),
        "updated": str(rec.get("updated") or "").strip(),
        "doi": str(rec.get("doi") or "").strip(),
        "journal_ref": str(rec.get("journal_ref") or "").strip(),
        "comment": str(rec.get("comment") or "").strip(),
    }


def _parse_queries_md(path: Path) -> tuple[list[str], list[str], int | None, int | None, int | None, bool]:
    if not path.exists():
        return ([], [], None, None, None, False)
    keywords: list[str] = []
    excludes: list[str] = []
    mode: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    max_results: int | None = None
    enrich_metadata: bool = False
    for raw in path.read_text(encoding="utf-8").splitlines():
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
        if line.startswith("- enrich_metadata:"):
            value = line.split(":", 1)[1].strip().strip('"').strip("'").lower()
            if value in {"1", "true", "yes", "y"}:
                enrich_metadata = True
            elif value in {"0", "false", "no", "n", ""}:
                enrich_metadata = False
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
    return (keywords, excludes, max_results, year_from, year_to, enrich_metadata)


def _best_effort_enrich(records: list[dict[str, Any]]) -> None:
    # Enrich missing metadata via id_list. This is best-effort and should not
    # fail the whole unit if the network is unavailable.
    ids: list[str] = []
    seen: set[str] = set()

    def _needs(rec: dict[str, Any]) -> bool:
        if not str(rec.get("arxiv_id") or "").strip():
            return False
        if str(rec.get("abstract") or "").strip() and (rec.get("authors") or rec.get("categories")):
            return False
        return True

    for rec in records:
        if not isinstance(rec, dict):
            continue
        if not _needs(rec):
            continue
        arxiv_id = _strip_arxiv_version(str(rec.get("arxiv_id") or "").strip())
        if not arxiv_id or arxiv_id in seen:
            continue
        seen.add(arxiv_id)
        ids.append(arxiv_id)

    if not ids:
        return

    by_id: dict[str, dict[str, Any]] = {}
    batch_size = 50
    for start in range(0, len(ids), batch_size):
        chunk = ids[start : start + batch_size]
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"id_list": ",".join(chunk)})
        try:
            fetched, _raw_count = _search_arxiv_once(url=url, queries=[], excludes=[], year_from=None, year_to=None)
        except Exception as exc:
            print(f"[arxiv-search] WARN: metadata enrichment skipped (network?): {exc}", file=sys.stderr)
            return
        for rec in fetched:
            aid = _strip_arxiv_version(str(rec.get("arxiv_id") or "").strip())
            if aid:
                by_id[aid] = rec
        time.sleep(3.0)

    if not by_id:
        return

    # Fill only missing fields.
    fill_fields = {
        "title",
        "authors",
        "year",
        "url",
        "abstract",
        "arxiv_id",
        "pdf_url",
        "categories",
        "primary_category",
        "published",
        "updated",
        "doi",
        "journal_ref",
        "comment",
    }
    for rec in records:
        if not isinstance(rec, dict):
            continue
        arxiv_id = _strip_arxiv_version(str(rec.get("arxiv_id") or "").strip())
        if not arxiv_id:
            continue
        src = by_id.get(arxiv_id)
        if not src:
            continue
        for k in fill_fields:
            if rec.get(k):
                continue
            if src.get(k):
                rec[k] = src.get(k)
        if rec.get("source") == "export":
            rec["source"] = "export+arxiv"


def _strip_arxiv_version(arxiv_id: str) -> str:
    # 2509.03990v2 -> 2509.03990
    arxiv_id = (arxiv_id or "").strip()
    return re.sub(r"v\\d+$", "", arxiv_id)


def _search_arxiv_paged(
    *,
    queries: list[str],
    excludes: list[str],
    max_results: int,
    year_from: int | None,
    year_to: int | None,
    workspace: Path | None = None,
) -> list[dict[str, Any]]:
    q = _build_arxiv_query(queries, workspace=workspace)
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
        batch, raw_count = _search_arxiv_once(url=url, queries=queries, excludes=excludes, year_from=year_from, year_to=year_to)
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
        # Be polite to the public API.
        time.sleep(3.0)
    return all_records[:target]


def _search_arxiv_once(
    *,
    url: str,
    queries: list[str],
    excludes: list[str],
    year_from: int | None,
    year_to: int | None,
) -> tuple[list[dict[str, Any]], int]:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            content = resp.read()
    except Exception as exc:
        raise SystemExit(f"arXiv request failed (network?): {exc}")

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
        if not _within_year_window(year, year_from=year_from, year_to=year_to):
            continue

        authors = [a.findtext("a:name", default="", namespaces=ns).strip() for a in entry.findall("a:author", ns)]
        authors = [a for a in authors if a]
        url_abs = (entry.findtext("a:id", default="", namespaces=ns) or "").strip()

        arxiv_id = _extract_arxiv_id(url_abs)
        pdf_url = _extract_pdf_url(entry, ns=ns) or (_default_pdf_url(arxiv_id) if arxiv_id else "")
        categories = _extract_categories(entry, ns=ns)
        primary_category = _extract_primary_category(entry, ns=ns) or (categories[0] if categories else "")
        comment = (entry.findtext("arxiv:comment", default="", namespaces=ns) or "").strip()
        doi = (entry.findtext("arxiv:doi", default="", namespaces=ns) or "").strip()
        journal_ref = (entry.findtext("arxiv:journal_ref", default="", namespaces=ns) or "").strip()

        record = {
            "title": title,
            "authors": authors,
            "year": year,
            "url": url_abs,
            "abstract": summary,
            "source": "arxiv",
            "query": queries,
            "arxiv_id": arxiv_id,
            "pdf_url": pdf_url,
            "categories": categories,
            "primary_category": primary_category,
            "published": published,
            "updated": updated,
            "doi": doi,
            "journal_ref": journal_ref,
            "comment": comment,
        }
        if excludes and _is_excluded(record, excludes):
            continue
        records.append(record)
    return (records, raw_count)


def _build_arxiv_query(queries: list[str], workspace: Path | None = None) -> str:
    queries = [q.strip() for q in (queries or []) if q and q.strip()]
    if not queries:
        return ""

    # Domain-pack rewrites remain the default for broad discovery workflows.
    # Focused workflows can make their explicit query list authoritative.
    if workspace is not None:
        from tooling.common import pipeline_quality_contract_value

        query_mode = str(
            pipeline_quality_contract_value(
                workspace,
                "retrieval_policy",
                "domain_pack_query_mode",
                default="rewrite",
            )
            or "rewrite"
        ).strip().lower()
        if query_mode != "explicit":
            pack = _load_domain_pack(workspace)
            if _domain_pack_matches(queries, pack):
                rewritten = _domain_pack_query(queries, pack)  # type: ignore[arg-type]
                if rewritten:
                    return rewritten

    parts: list[str] = []
    for q in queries:
        # Allow advanced arXiv query strings (fielded / boolean) to pass through.
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


def _load_domain_pack(workspace: Path) -> dict | None:
    """Load the first matching domain pack for this workspace.

    Globs ``assets/domain_packs/*.json`` from the skill package root.  For
    each pack, checks ``topic_triggers.trigger_group_a`` **and**
    ``trigger_group_b`` against the combined text of the workspace's
    ``GOAL.md`` and ``queries.md``.  A pack matches when **at least one**
    trigger from group_a **and** at least one from group_b appear in the
    text.  Returns the first matching pack dict, or ``None``.
    """
    skill_root = Path(__file__).resolve().parents[1]  # .../arxiv-search/
    pack_dir = skill_root / "assets" / "domain_packs"
    if not pack_dir.is_dir():
        return None

    # Build the haystack from workspace context files.
    haystack_parts: list[str] = []
    for name in ("GOAL.md", "queries.md"):
        ctx = workspace / name
        if ctx.exists():
            haystack_parts.append(ctx.read_text(encoding="utf-8"))
    haystack = " ".join(haystack_parts).lower()
    if not haystack.strip():
        return None

    for pack_path in sorted(pack_dir.glob("*.json")):
        try:
            pack = json.loads(pack_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        triggers = pack.get("topic_triggers") or {}
        group_a = [t.lower() for t in (triggers.get("trigger_group_a") or [])]
        group_b = [t.lower() for t in (triggers.get("trigger_group_b") or [])]
        if not group_a or not group_b:
            continue
        if any(t in haystack for t in group_a) and any(t in haystack for t in group_b):
            return pack
    return None


def _domain_pack_matches(queries: list[str], pack: dict | None) -> bool:
    """Return True when *pack* is non-None (i.e. a domain pack matched)."""
    return pack is not None


def _domain_pack_query(queries: list[str], pack: dict) -> str:
    """Build an AND-constrained arXiv query from a matched domain pack."""
    qr = pack.get("query_rewrite") or {}
    core = qr.get("core_clause", "")
    signals = qr.get("signal_clause", "")

    triggers = pack.get("topic_triggers") or {}
    name_triggers = [n.lower() for n in (triggers.get("name_triggers") or [])]

    names: list[str] = []
    for q in queries:
        qlow = q.lower()
        if any(n in qlow for n in name_triggers):
            names.append(q.strip())
    names_clause = ""
    if names:
        parts: list[str] = []
        for n in names[:12]:
            if " " in n:
                parts.append(f'all:"{n}"')
            else:
                parts.append(f"all:{n}")
        names_clause = "(" + " OR ".join(parts) + ")"

    if not core:
        # Degenerate pack without query_rewrite — fall through to default.
        return ""
    if names_clause:
        # Important: allow named classics through even if they don't match the core clause.
        return f"(({core} AND {signals}) OR {names_clause})" if signals else f"({core} OR {names_clause})"
    return f"({core} AND {signals})" if signals else core


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
