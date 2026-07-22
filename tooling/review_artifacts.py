from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from tooling.common import atomic_write_text, load_yaml, read_jsonl


def load_candidate_records(workspace: Path) -> list[dict[str, Any]]:
    papers_dir = workspace / "papers"
    for path in (papers_dir / "papers_dedup.jsonl", papers_dir / "papers_raw.jsonl", papers_dir / "core_set.csv"):
        if not path.exists():
            continue
        if path.suffix == ".jsonl":
            return [dict(rec) for rec in read_jsonl(path) if isinstance(rec, dict)]
        if path.suffix == ".csv":
            with path.open("r", encoding="utf-8", newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
    return []


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv_rows(path: Path, rows: list[dict[str, Any]], *, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def find_workspace_text_source(workspace: Path, *, stems: tuple[str, ...]) -> Path | None:
    candidates: list[Path] = []
    for base in (workspace / "inputs", workspace / "input", workspace):
        for stem in stems:
            for suffix in (".md", ".txt", ".pdf"):
                candidate = base / f"{stem}{suffix}"
                if candidate.exists():
                    candidates.append(candidate)
    return candidates[0] if candidates else None


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"PDF extraction requires pypdf: {exc}") from exc

    try:
        reader = PdfReader(str(path))
        parts: list[str] = []
        for idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                parts.append(f"[page {idx}]\n{text.strip()}")
    except Exception as exc:
        raise RuntimeError(
            f"Could not extract manuscript PDF `{path}` ({type(exc).__name__}: {exc})."
        ) from exc
    return "\n\n".join(parts).strip()


def choose_candidate_pool_path(workspace: Path) -> Path | None:
    for path in (workspace / "papers" / "papers_dedup.jsonl", workspace / "papers" / "papers_raw.jsonl", workspace / "papers" / "core_set.csv"):
        if path.exists():
            return path
    return None


def stable_paper_id(record: dict[str, Any], *, index: int) -> str:
    value = str(record.get("paper_id") or "").strip()
    return value if value else f"P{index:04d}"


def write_text(path: Path, text: str) -> None:
    atomic_write_text(path, text.rstrip() + "\n")


def summarize_outline(path: Path) -> tuple[list[str], list[str]]:
    if not path.exists():
        return [], []
    outline = load_yaml(path)
    sections: list[str] = []
    bullets: list[str] = []
    if not isinstance(outline, list):
        return sections, bullets
    for sec in outline:
        if not isinstance(sec, dict):
            continue
        title = str(sec.get("title") or "").strip()
        if title:
            sections.append(title)
        for bullet in sec.get("bullets") or []:
            if isinstance(bullet, str) and bullet.strip():
                bullets.append(bullet.strip())
        for sub in sec.get("subsections") or []:
            if not isinstance(sub, dict):
                continue
            for bullet in sub.get("bullets") or []:
                if isinstance(bullet, str) and bullet.strip():
                    bullets.append(bullet.strip())
    return sections, bullets
