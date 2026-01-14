from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _read_ids(path: Path) -> list[str]:
    ids: list[str] = []
    if not path.exists():
        raise SystemExit(f"Missing id list: {path}")
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.replace("https://arxiv.org/abs/", "").replace("http://arxiv.org/abs/", "")
        line = line.replace("https://arxiv.org/pdf/", "").replace("http://arxiv.org/pdf/", "")
        line = line.removesuffix(".pdf")
        ids.append(line)
    # de-dupe preserving order
    out: list[str] = []
    seen: set[str] = set()
    for x in ids:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _fetch_arxiv_meta(arxiv_id: str) -> dict[str, Any]:
    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "codex-agent-survey-corpus/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()

    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(data)
    entry = root.find("a:entry", ns)
    if entry is None:
        return {}

    title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip().replace("\n", " ")
    published = (entry.findtext("a:published", default="", namespaces=ns) or "").strip()
    updated = (entry.findtext("a:updated", default="", namespaces=ns) or "").strip()
    abs_url = (entry.findtext("a:id", default="", namespaces=ns) or "").strip()

    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "published": published,
        "updated": updated,
        "abs_url": abs_url,
    }


def _download(url: str, dst: Path, *, overwrite: bool, sleep_s: float) -> None:
    if dst.exists() and not overwrite:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "codex-agent-survey-corpus/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        dst.write_bytes(resp.read())
    if sleep_s:
        time.sleep(max(0.0, float(sleep_s)))


def _extract_text(pdf_path: Path, *, max_pages: int) -> tuple[int, str]:
    import re

    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    pages = min(len(doc), max(1, int(max_pages)))
    chunks: list[str] = []
    for i in range(pages):
        page = doc.load_page(i)
        chunks.append(page.get_text("text"))
    doc.close()
    text = "\n".join(chunks)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return pages, text.strip() + "\n"


def _extract_section_headings(text: str) -> list[str]:
    """Best-effort extraction of top-level section headings from PDF text.

    Heuristics:
    - Keep only numeric top-level headings (1..15).
    - Prefer headings that look like paper sections (avoid tables/lists).
    - Deduplicate by section number.

    This is intentionally approximate; PDF text extraction is noisy.
    """
    import re

    allow_single = {
        "abstract",
        "introduction",
        "background",
        "preliminaries",
        "overview",
        "methodology",
        "methods",
        "taxonomy",
        "evaluation",
        "benchmarks",
        "benchmark",
        "datasets",
        "experiments",
        "results",
        "applications",
        "challenges",
        "discussion",
        "conclusion",
        "references",
        "appendix",
        "planning",
        "memory",
        "techniques",
        "scenarios",
        "safety",
        "security",
    }

    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    candidates: list[tuple[int, str]] = []

    def _maybe_add(num: int, title: str) -> None:
        title = re.sub(r"\s+", " ", (title or "").strip())
        if not title:
            return
        if num < 1 or num > 15:
            return
        if len(title) < 3 or len(title) > 80:
            return
        low = title.lower()
        if low.startswith(("table", "figure", "fig.", "fig ")):
            return
        if title.endswith("-"):
            return
        if len(re.findall(r"\d", title)) > 3:
            return
        if title.count(",") >= 3:
            return
        if "http" in low:
            return

        # Single-token headings are common, but avoid false positives like country names.
        words = [w for w in re.split(r"\s+", title) if w]
        if len(words) == 1:
            w = words[0]
            if not w.isalpha():
                return
            if w.lower() not in allow_single:
                return

        candidates.append((num, title))

    i = 0
    while i < len(lines):
        ln = lines[i]

        # Pattern: "1" then "Introduction" on the next line.
        if re.fullmatch(r"\d{1,2}", ln) and i + 1 < len(lines):
            nxt = lines[i + 1]
            if re.fullmatch(r"[A-Z][A-Za-z0-9 \-,:/()]{2,80}", nxt):
                _maybe_add(int(ln), nxt)
                i += 2
                continue

        m = re.match(r"^(\d{1,2})\s+([A-Z][A-Za-z0-9 \-,:/()]{2,80})$", ln)
        if m:
            _maybe_add(int(m.group(1)), m.group(2))

        i += 1

    # Deduplicate by number (keep first occurrence).
    by_num: dict[int, str] = {}
    for num, title in candidates:
        by_num.setdefault(num, title)

    return [f"{n} {by_num[n]}" for n in sorted(by_num)]




def _build_style_report(records: list[dict[str, object]], *, workspace: Path, out_dir: Path) -> str:
    import statistics

    rows = []
    counts = []

    for rec in records:
        arxiv_id = str(rec.get("arxiv_id") or "").strip()
        status = str(rec.get("status") or "").strip()
        pages = int(rec.get("pages_extracted") or 0)
        text_path = workspace / str(rec.get("text_path") or "")

        headings: list[str] = []
        if status == "ok" and text_path.exists() and text_path.stat().st_size > 0:
            headings = _extract_section_headings(text_path.read_text(encoding="utf-8", errors="ignore"))

        counts.append(len(headings))
        sample = "; ".join(headings[:8])
        if len(headings) > 8:
            sample += " …"

        rows.append((arxiv_id, pages, len(headings), sample))

    ok = sum(1 for r in records if str(r.get("status") or "").strip() == "ok")
    total = len(records)

    lines = [
        "# Agent survey style report (auto)",
        "",
        f"- Papers: {total} (ok={ok}, error={total - ok})",
        "",
    ]

    if counts:
        lines.append("## Detected top-level section counts")
        lines.append("")
        lines.append(f"- min/median/max: {min(counts)}/{statistics.median(counts)}/{max(counts)}")
        lines.append("")

    lines.extend([
        "## Per-paper detected headings (best-effort)",
        "",
        "| arXiv | pages | #sections | headings (first 8) |",
        "|---|---:|---:|---|",
    ])

    for arxiv_id, pages, nsec, sample in rows:
        lines.append(f"| {arxiv_id} | {pages} | {nsec} | {sample} |")

    lines.append("")
    lines.append("## How to use (for pipeline tuning)")
    lines.append("")
    lines.append("- Target paper-like structure: ~6–8 top-level sections with fewer, thicker subsections.")
    lines.append("- Front matter (Intro/Related Work) typically has higher citation density than a single H3 subsection.")
    lines.append("- Use this report to sanity-check whether your generated outline and section sizing resembles real surveys.")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()

    ids_rel = "ref/agent-surveys/arxiv_ids.txt"
    if str(args.inputs).strip():
        # first token wins (semicolon-separated)
        ids_rel = str(args.inputs).split(";", 1)[0].strip() or ids_rel

    ids_path = workspace / ids_rel
    arxiv_ids = _read_ids(ids_path)
    if not arxiv_ids:
        raise SystemExit(f"No arXiv ids found in {ids_path}")

    out_dir = workspace / "ref" / "agent-surveys"
    pdf_dir = out_dir / "pdfs"
    text_dir = out_dir / "text"
    index_path = out_dir / "index.jsonl"

    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []

    for arxiv_id in arxiv_ids:
        rec: dict[str, Any] = {
            "arxiv_id": arxiv_id,
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            "pdf_path": str((pdf_dir / f"{arxiv_id}.pdf").relative_to(workspace)),
            "text_path": str((text_dir / f"{arxiv_id}.txt").relative_to(workspace)),
            "max_pages": int(args.max_pages),
            "status": "",
            "error": "",
            "pages_extracted": 0,
        }

        try:
            rec.update(_fetch_arxiv_meta(arxiv_id))
        except Exception as exc:
            # Metadata is best-effort.
            rec["meta_error"] = f"{type(exc).__name__}: {exc}"

        pdf_path = workspace / rec["pdf_path"]
        text_path = workspace / rec["text_path"]

        try:
            _download(rec["pdf_url"], pdf_path, overwrite=bool(args.overwrite), sleep_s=float(args.sleep))
            pages, text = _extract_text(pdf_path, max_pages=int(args.max_pages))
            rec["pages_extracted"] = int(pages)
            if bool(args.overwrite) or not text_path.exists():
                text_path.write_text(text, encoding="utf-8")
            rec["status"] = "ok"
        except Exception as exc:
            rec["status"] = "error"
            rec["error"] = f"{type(exc).__name__}: {exc}"

        records.append(rec)

    index_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {index_path.relative_to(workspace)}")

    try:
        report = _build_style_report(records, workspace=workspace, out_dir=out_dir)
        report_path = out_dir / "STYLE_REPORT.md"
        report_path.write_text(report, encoding="utf-8")
        print(f"Wrote {report_path.relative_to(workspace)}")
    except Exception as exc:
        print(f"Style report skipped: {type(exc).__name__}: {exc}", file=sys.stderr)

    # Non-zero keeps this as a manual helper (not pipeline).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
