from __future__ import annotations

import argparse
import csv
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--max-papers", type=int, default=40)
    parser.add_argument("--max-pages", type=int, default=6)
    parser.add_argument("--min-chars", type=int, default=1500)
    parser.add_argument("--sleep", type=float, default=1.0, help="Delay between downloads (seconds)")
    parser.add_argument(
        "--local-pdfs-only",
        action="store_true",
        help="Do not download PDFs; only use cached PDFs under papers/pdfs/ (fulltext mode).",
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

    from tooling.common import ensure_dir, parse_semicolon_list, read_tsv, write_jsonl

    workspace = Path(args.workspace).resolve()
    inputs = parse_semicolon_list(args.inputs) or ["papers/core_set.csv"]
    outputs = parse_semicolon_list(args.outputs) or ["papers/fulltext_index.jsonl"]

    core_path = workspace / inputs[0]
    mapping_path = workspace / "outline" / "mapping.tsv"
    out_path = workspace / outputs[0]

    cfg = _parse_fulltext_config(workspace / "queries.md")
    mode = str(cfg.get("mode") or "abstract").strip().lower()
    if cfg.get("max_papers"):
        args.max_papers = int(cfg["max_papers"])
    if cfg.get("max_pages"):
        args.max_pages = int(cfg["max_pages"])
    if cfg.get("min_chars"):
        args.min_chars = int(cfg["min_chars"])

    core_rows = _load_core_set(core_path)
    if not core_rows:
        raise SystemExit(f"No rows found in {core_path}")

    mapped_ids = set()
    if mapping_path.exists():
        for row in read_tsv(mapping_path):
            pid = str(row.get("paper_id") or "").strip()
            if pid:
                mapped_ids.add(pid)

    # The full-text limit is a download/extraction budget. Abstract mode performs
    # no downloads, so its index must retain one traceability record per core paper.
    max_papers = int(args.max_papers) if mode == "fulltext" else len(core_rows)
    prioritized = _prioritize(core_rows, mapped_ids=mapped_ids, max_papers=max_papers)

    if mode != "fulltext":
        # Evidence mode "abstract": do not download PDFs; just emit an index so downstream
        # steps can proceed with explicit evidence-level tracking.
        index_records: list[dict[str, Any]] = []
        for row in prioritized:
            paper_id = row["paper_id"]
            title = row.get("title") or ""
            pdf_url = _resolve_pdf_url(row)
            pdf_path = workspace / "papers" / "pdfs" / f"{paper_id}.pdf"
            text_path = workspace / "papers" / "fulltext" / f"{paper_id}.txt"
            index_records.append(
                {
                    "paper_id": paper_id,
                    "title": title,
                    "year": row.get("year") or "",
                    "url": row.get("url") or "",
                    "arxiv_id": row.get("arxiv_id") or "",
                    "pdf_url": pdf_url,
                    "pdf_path": str(pdf_path.relative_to(workspace)),
                    "text_path": str(text_path.relative_to(workspace)),
                    "status": f"skip_mode_{mode}",
                    "pages_extracted": 0,
                    "chars_extracted": 0,
                    "error": "",
                }
            )
        write_jsonl(out_path, index_records)
        return 0

    pdf_dir = workspace / "papers" / "pdfs"
    text_dir = workspace / "papers" / "fulltext"
    ensure_dir(pdf_dir)
    ensure_dir(text_dir)
    ensure_dir(out_path.parent)

    index_records: list[dict[str, Any]] = []
    missing_pdfs: list[dict[str, Any]] = []
    for row in prioritized:
        paper_id = row["paper_id"]
        title = row.get("title") or ""
        pdf_url = _resolve_pdf_url(row)
        pdf_path = pdf_dir / f"{paper_id}.pdf"
        text_path = text_dir / f"{paper_id}.txt"

        record: dict[str, Any] = {
            "paper_id": paper_id,
            "title": title,
            "year": row.get("year") or "",
            "url": row.get("url") or "",
            "arxiv_id": row.get("arxiv_id") or "",
            "pdf_url": pdf_url,
            "pdf_path": str(pdf_path.relative_to(workspace)),
            "text_path": str(text_path.relative_to(workspace)),
            "status": "",
            "pages_extracted": 0,
            "chars_extracted": 0,
            "error": "",
        }

        if text_path.exists() and text_path.stat().st_size >= int(args.min_chars):
            record["status"] = "ok_cached"
            record["chars_extracted"] = int(text_path.stat().st_size)
            index_records.append(record)
            continue
        if not pdf_url:
            record["status"] = "skip_no_pdf_url"
            missing_pdfs.append({**record, **{"reason": "no_pdf_url"}})
            index_records.append(record)
            continue

        if bool(args.local_pdfs_only) and not pdf_path.exists():
            record["status"] = "skip_local_pdfs_only"
            record["error"] = "local_pdfs_only: missing cached PDF"
            missing_pdfs.append({**record, **{"reason": "missing_local_pdf"}})
            index_records.append(record)
            continue

        if not pdf_path.exists():
            try:
                _download_pdf(pdf_url, pdf_path)
                time.sleep(max(0.0, float(args.sleep)))
            except Exception as exc:
                record["status"] = "error_download"
                record["error"] = str(exc)
                index_records.append(record)
                continue

        try:
            pages, text = _extract_text(pdf_path, max_pages=int(args.max_pages))
            record["pages_extracted"] = pages
            record["chars_extracted"] = len(text)
            if len(text) < int(args.min_chars):
                record["status"] = "error_too_short"
                record["error"] = f"extracted_text<{int(args.min_chars)} chars"
                index_records.append(record)
                continue
            # Never overwrite if a human already curated the text.
            if not text_path.exists():
                text_path.write_text(text, encoding="utf-8")
            record["status"] = "ok"
            index_records.append(record)
        except Exception as exc:
            record["status"] = "error_extract"
            record["error"] = str(exc)
            index_records.append(record)

    if missing_pdfs:
        _write_missing_pdfs_report(
            workspace,
            missing_pdfs,
            local_pdfs_only=bool(args.local_pdfs_only),
        )
    write_jsonl(out_path, index_records)
    return 0


def _write_missing_pdfs_report(workspace: Path, rows: list[dict[str, Any]], *, local_pdfs_only: bool) -> None:
    from tooling.common import ensure_dir, atomic_write_text

    ensure_dir(workspace / "output")
    ensure_dir(workspace / "papers")

    md_path = workspace / "output" / "MISSING_PDFS.md"
    csv_path = workspace / "papers" / "missing_pdfs.csv"

    # CSV for automation.
    fieldnames = [
        "paper_id",
        "title",
        "year",
        "url",
        "arxiv_id",
        "pdf_url",
        "status",
        "reason",
        "error",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: str(r.get(k) or "") for k in fieldnames})

    # Markdown summary for humans.
    lines: list[str] = [
        "# Missing PDFs report",
        "",
        f"- Mode: `fulltext`",
        f"- local_pdfs_only: `{local_pdfs_only}`",
        f"- Missing count: `{len(rows)}`",
        "",
        "## How to fix",
        "",
        "- Provide PDFs under `papers/pdfs/<paper_id>.pdf`.",
        "- Or populate `pdf_url`/`arxiv_id` in `papers/core_set.csv` and rerun without `--local-pdfs-only`.",
        "",
        "## Items",
        "",
        "| paper_id | title | pdf_url | reason |",
        "|---|---|---|---|",
    ]
    for r in rows[:200]:
        pid = str(r.get("paper_id") or "").strip()
        title = str(r.get("title") or "").strip().replace("|", "\\|")
        pdf_url = str(r.get("pdf_url") or "").strip().replace("|", "\\|")
        reason = str(r.get("reason") or "").strip().replace("|", "\\|")
        lines.append(f"| {pid} | {title} | {pdf_url} | {reason} |")

    if len(rows) > 200:
        lines.append("")
        lines.append(f"(showing first 200 of {len(rows)} items)")

    atomic_write_text(md_path, "\n".join(lines).rstrip() + "\n")


def _load_core_set(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing core set: {path}")
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            paper_id = str(row.get("paper_id") or "").strip()
            title = str(row.get("title") or "").strip()
            if not paper_id or not title:
                continue
            rows.append(
                {
                    "paper_id": paper_id,
                    "title": title,
                    "year": str(row.get("year") or "").strip(),
                    "url": str(row.get("url") or "").strip(),
                    "arxiv_id": str(row.get("arxiv_id") or "").strip(),
                    "pdf_url": str(row.get("pdf_url") or "").strip(),
                }
            )
    return rows


def _prioritize(rows: list[dict[str, str]], *, mapped_ids: set[str], max_papers: int) -> list[dict[str, str]]:
    if max_papers <= 0:
        return []
    mapped: list[dict[str, str]] = []
    rest: list[dict[str, str]] = []
    for row in rows:
        if row["paper_id"] in mapped_ids:
            mapped.append(row)
        else:
            rest.append(row)
    return (mapped + rest)[: min(len(rows), max_papers)]


def _resolve_pdf_url(row: dict[str, str]) -> str:
    pdf_url = str(row.get("pdf_url") or "").strip()
    if pdf_url:
        return pdf_url

    arxiv_id = str(row.get("arxiv_id") or "").strip()
    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    url = str(row.get("url") or "").strip()
    if not url:
        return ""
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([^/?#]+)", url)
    if not m:
        return ""
    arxiv_id = m.group(1).replace(".pdf", "")
    arxiv_id = re.sub(r"v\d+$", "", arxiv_id)
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


def _download_pdf(url: str, path: Path) -> None:
    from tooling.common import ensure_dir

    ensure_dir(path.parent)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "research-units-pipeline-skills/1.0 (+https://github.com/r-j-s/research-units-pipeline-skills)",
            "Accept": "application/pdf",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    if not data or len(data) < 1024:
        raise RuntimeError("download returned empty/too-small payload")
    path.write_bytes(data)


def _extract_text(pdf_path: Path, *, max_pages: int) -> tuple[int, str]:
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    pages = min(len(doc), max(1, int(max_pages)))
    chunks: list[str] = []
    for i in range(pages):
        page = doc.load_page(i)
        chunks.append(page.get_text("text"))
    doc.close()
    text = "\n".join(chunks)
    # Normalize whitespace a bit.
    text = re.sub(r"[ \\t]+", " ", text)
    text = re.sub(r"\\n\\s*\\n\\s*\\n+", "\n\n", text)
    return pages, text.strip() + "\n"


def _parse_fulltext_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    out: dict[str, Any] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line.startswith("- "):
            continue
        if ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        key = key.strip()
        value = value.split("#", 1)[0].strip().strip('"').strip("'").strip()
        if key == "evidence_mode":
            out["mode"] = value.strip().lower()
        if key == "fulltext_max_papers":
            out["max_papers"] = _parse_pos_int(value)
        if key == "fulltext_max_pages":
            out["max_pages"] = _parse_pos_int(value)
        if key == "fulltext_min_chars":
            out["min_chars"] = _parse_pos_int(value)
    return {k: v for k, v in out.items() if v}


def _parse_pos_int(value: str) -> int:
    try:
        n = int(str(value).strip())
    except Exception:
        return 0
    return n if n > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
