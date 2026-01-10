from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(repo_root))

    from tooling.common import parse_semicolon_list, read_jsonl, read_tsv, write_jsonl

    workspace = Path(args.workspace).resolve()
    inputs = parse_semicolon_list(args.inputs) or ["papers/core_set.csv"]
    outputs = parse_semicolon_list(args.outputs) or ["papers/paper_notes.jsonl"]

    core_path = workspace / inputs[0]
    fulltext_index_path = workspace / "papers" / "fulltext_index.jsonl"
    mapping_path = workspace / "outline" / "mapping.tsv"
    dedup_path = workspace / "papers" / "papers_dedup.jsonl"
    out_path = workspace / outputs[0]

    core_rows = _load_core_set(core_path)
    if not core_rows:
        raise SystemExit(f"No rows found in {core_path}")

    metadata = read_jsonl(dedup_path) if dedup_path.exists() else []
    fulltext_by_id = _load_fulltext_index(fulltext_index_path, workspace=workspace)
    mapping_info = _load_mapping(mapping_path) if mapping_path.exists() else {}

    priority_set = _select_priority_papers(core_rows, mapping_info=mapping_info)

    existing_notes_by_id: dict[str, dict[str, Any]] = {}
    if out_path.exists():
        for rec in read_jsonl(out_path):
            if not isinstance(rec, dict):
                continue
            pid = str(rec.get("paper_id") or "").strip()
            if pid:
                existing_notes_by_id[pid] = rec

    used_bibkeys: set[str] = set()
    for rec in existing_notes_by_id.values():
        bibkey = str(rec.get("bibkey") or "").strip()
        if bibkey:
            used_bibkeys.add(bibkey)

    notes: list[dict[str, Any]] = []
    for row in core_rows:
        paper_id = row["paper_id"]
        existing = existing_notes_by_id.get(paper_id)
        if existing:
            notes.append(
                _backfill_note(
                    existing,
                    row=row,
                    meta=_match_metadata(metadata, title=row["title"], year=row.get("year") or "", url=row.get("url") or ""),
                    fulltext_by_id=fulltext_by_id,
                    mapping_info=mapping_info,
                    priority_set=priority_set,
                    workspace=workspace,
                )
            )
            continue

        meta = _match_metadata(metadata, title=row["title"], year=row.get("year") or "", url=row.get("url") or "")
        authors = meta.get("authors") or []
        abstract = str(meta.get("abstract") or "").strip()
        categories = meta.get("categories") or []
        primary_category = str(meta.get("primary_category") or "").strip()

        arxiv_id = str(row.get("arxiv_id") or "").strip() or str(meta.get("arxiv_id") or "").strip()
        pdf_url = str(row.get("pdf_url") or "").strip() or str(meta.get("pdf_url") or "").strip()

        fulltext_path = fulltext_by_id.get(paper_id)
        fulltext_ok = bool(fulltext_path and fulltext_path.exists() and fulltext_path.stat().st_size > 0)
        has_abstract = bool(abstract)
        evidence_level = "fulltext" if fulltext_ok else ("abstract" if has_abstract else "title")

        priority = "high" if paper_id in priority_set else "normal"
        mapped_sections = sorted(mapping_info.get(paper_id, {}).get("sections", set()))

        bibkey = _make_bibkey(authors=authors, year=str(row.get("year") or ""), title=row["title"], used=used_bibkeys)
        if priority == "high":
            summary_bullets = _high_priority_bullets(title=row["title"], abstract=abstract, mapped_sections=mapped_sections)
            method = _infer_method(title=row["title"], abstract=abstract, bullets=summary_bullets)
            key_results = _infer_key_results(abstract=abstract)
            limitations = _infer_limitations(evidence_level=evidence_level, mapped_sections=mapped_sections, abstract=abstract)
        else:
            summary_bullets = _abstract_to_bullets(abstract)
            method = ""
            key_results = []
            if evidence_level == "abstract":
                limitations = [f"Evidence level: abstract ({len(abstract)} chars). Validate with full text if used as key evidence."]
            else:
                limitations = ["Evidence level: title only (no abstract/full text). Do not infer technical details; verify the source before using as evidence."]

        notes.append(
            {
                "paper_id": paper_id,
                "title": row["title"],
                "year": int(row["year"]) if str(row.get("year") or "").isdigit() else str(row.get("year") or ""),
                "url": row.get("url") or "",
                "arxiv_id": arxiv_id,
                "primary_category": primary_category,
                "categories": categories,
                "pdf_url": pdf_url,
                "priority": priority,
                "mapped_sections": mapped_sections,
                "evidence_level": evidence_level,
                "fulltext_path": str(fulltext_path.relative_to(workspace)) if fulltext_ok and fulltext_path else "",
                "authors": authors,
                "abstract": abstract,
                "summary_bullets": summary_bullets,
                "method": method,
                "key_results": key_results,
                "limitations": limitations,
                "bibkey": bibkey,
            }
        )

    write_jsonl(out_path, notes)
    return 0


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
                    "reason": str(row.get("reason") or "").strip(),
                }
            )
    return rows


def _load_fulltext_index(path: Path, *, workspace: Path) -> dict[str, Path]:
    from tooling.common import read_jsonl

    out: dict[str, Path] = {}
    if not path.exists():
        return out
    for rec in read_jsonl(path):
        if not isinstance(rec, dict):
            continue
        pid = str(rec.get("paper_id") or "").strip()
        rel = str(rec.get("text_path") or "").strip()
        status = str(rec.get("status") or "").strip()
        if not pid or not rel:
            continue
        if not status.startswith("ok"):
            continue
        p = workspace / rel
        out[pid] = p
    return out


def _load_mapping(path: Path) -> dict[str, dict[str, Any]]:
    by_pid: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return by_pid
    from tooling.common import read_tsv

    for row in read_tsv(path):
        pid = str(row.get("paper_id") or "").strip()
        sid = str(row.get("section_id") or "").strip()
        if not pid or not sid:
            continue
        rec = by_pid.setdefault(pid, {"sections": set(), "count": 0})
        rec["sections"].add(sid)
        rec["count"] += 1
    return by_pid


def _select_priority_papers(core_rows: list[dict[str, str]], *, mapping_info: dict[str, dict[str, Any]]) -> set[str]:
    pinned = {r["paper_id"] for r in core_rows if "pinned_classic" in (r.get("reason") or "")}
    scored: list[tuple[int, str]] = []
    for row in core_rows:
        pid = row["paper_id"]
        count = int(mapping_info.get(pid, {}).get("count") or 0)
        scored.append((count, pid))
    scored.sort(key=lambda t: (-t[0], t[1]))

    core_n = len(core_rows)
    target_n = min(15, max(10, core_n // 4))  # 50 -> 12
    top = {pid for _, pid in scored[:target_n]}
    return set(pinned) | set(top)


def _match_metadata(records: list[dict[str, Any]], *, title: str, year: str, url: str) -> dict[str, Any]:
    from tooling.common import normalize_title_for_dedupe

    if not records:
        return {}
    if url:
        for rec in records:
            if str(rec.get("url") or rec.get("id") or "").strip() == url:
                return rec
    key = f"{normalize_title_for_dedupe(title)}::{year}"
    for rec in records:
        rtitle = str(rec.get("title") or "").strip()
        ryear = str(rec.get("year") or "").strip()
        if f"{normalize_title_for_dedupe(rtitle)}::{ryear}" == key:
            return rec
    return {}


def _make_bibkey(*, authors: list[Any], year: str, title: str, used: set[str]) -> str:
    from tooling.common import tokenize

    last = "Anon"
    if authors and isinstance(authors, list):
        first = str(authors[0]).strip()
        if first:
            last = first.split()[-1]
    keyword = "Work"
    for token in tokenize(title):
        if len(token) >= 4:
            keyword = token
            break
    base = f"{_slug(last)}{year}{_slug(keyword).title()}"
    bibkey = base
    suffix = ord("a")
    while bibkey in used:
        bibkey = f"{base}{chr(suffix)}"
        suffix += 1
    used.add(bibkey)
    return bibkey


def _slug(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "", text)
    return text or "X"


def _high_priority_bullets(*, title: str, abstract: str, mapped_sections: list[str]) -> list[str]:
    title = (title or "").strip()
    abstract = (abstract or "").strip()

    bullets = _abstract_to_bullets(abstract)
    if len([b for b in bullets if str(b).strip()]) >= 3:
        return bullets

    # Fall back to title-driven bullets when abstract is missing.
    tokens = _salient_terms(title)
    token_str = ", ".join(tokens[:6])
    sec_str = ", ".join(mapped_sections[:5])

    out: list[str] = []
    if title:
        out.append(f"Main idea (from title): {title}.")
    if token_str:
        out.append(f"Key terms hinted by title: {token_str}.")
    if sec_str:
        out.append(f"Mapped to outline subsections: {sec_str}.")

    # Ensure at least 3 bullets.
    while len(out) < 3:
        out.append("Abstract not available in metadata; verify details in the full paper before using as key evidence.")
    return out[:3]


def _infer_method(*, title: str, abstract: str, bullets: list[str]) -> str:
    abstract = (abstract or "").strip()
    if abstract:
        sent = _pick_sentence(
            abstract,
            patterns=[r"\bwe\s+(propose|present|introduce|develop|study|analyze)\b", r"\bour\s+(method|approach|framework|model)\b"],
        )
        if sent:
            return sent

    for b in bullets or []:
        b = str(b).strip()
        if b:
            return b

    title = (title or "").strip()
    if title:
        return f"The work targets the problem implied by the title and proposes a technique relevant to that setting: {title}."
    return "Method summary unavailable from metadata; verify the full paper for implementation details."


def _infer_key_results(*, abstract: str) -> list[str]:
    abstract = (abstract or "").strip()
    if abstract:
        sent = _pick_sentence(
            abstract,
            patterns=[r"\b(achieve|outperform|state[- ]of[- ]the[- ]art|sota|improv|results?)\b", r"\b\d+(?:\.\d+)?\b"],
        )
        if sent:
            return [sent]
        # Fall back to the last sentence as a coarse "result" proxy.
        last = _last_sentence(abstract)
        if last:
            return [last]
    return ["Key quantitative results are not fully stated in available metadata; verify benchmarks/metrics in the full text before citing numbers."]


def _infer_limitations(*, evidence_level: str, mapped_sections: list[str], abstract: str) -> list[str]:
    evidence_level = (evidence_level or "").strip().lower() or "abstract"
    sec_str = ", ".join(mapped_sections[:4])

    lims: list[str] = []
    if evidence_level == "fulltext":
        lims.append("Even with extracted text, evaluation details may be incomplete; verify the official PDF for exact settings and ablations.")
    elif evidence_level == "abstract":
        lims.append("Abstract-level evidence only: validate assumptions, evaluation protocol, and failure cases in the full paper before relying on this as key evidence.")
    else:
        lims.append("Title-only evidence: do not infer methods/results beyond what the title states; fetch abstract/full text before using this as key evidence.")

    if sec_str:
        lims.append(f"This work is mapped to: {sec_str}; confirm it is not over-used across unrelated subsections.")

    # Add a light, non-repeated caveat if abstract is missing.
    if not (abstract or "").strip():
        lims.append("Abstract missing in metadata; treat all details as provisional until verified.")

    return lims[:3]


def _pick_sentence(text: str, *, patterns: list[str]) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return ""
    sents = re.split(r"(?<=[.!?])\s+", text)
    for pat in patterns:
        rx = re.compile(pat, flags=re.IGNORECASE)
        for s in sents:
            s = s.strip()
            if len(s) < 12:
                continue
            if rx.search(s):
                return s
    return ""


def _last_sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return ""
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sents:
        return ""
    return sents[-1]


def _salient_terms(title: str) -> list[str]:
    # Cheap, deterministic tokenization; keep longer tokens and drop common filler words.
    title = (title or "").lower()
    title = re.sub(r"[^a-z0-9]+", " ", title)
    toks = [t for t in title.split() if t]
    stop = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "is",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
        "via",
        "using",
        "towards",
        "toward",
        "model",
        "models",
        "method",
        "methods",
        "system",
        "systems",
        "approach",
        "approaches",
        "analysis",
    }
    out: list[str] = []
    for t in toks:
        if len(t) < 4:
            continue
        if t in stop:
            continue
        if t not in out:
            out.append(t)
    return out


def _abstract_to_bullets(abstract: str) -> list[str]:
    abstract = (abstract or "").strip()
    if not abstract:
        return []
    # Deterministic scaffold: use first few sentences as bullets (LLM should refine for priority papers).
    parts = re.split(r"(?<=[.!?])\\s+", re.sub(r"\\s+", " ", abstract))
    bullets: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        bullets.append(p)
        if len(bullets) >= 3:
            break
    if not bullets:
        bullets = [abstract[:240].strip()]
    return bullets


def _backfill_note(
    existing: dict[str, Any],
    *,
    row: dict[str, str],
    meta: dict[str, Any],
    fulltext_by_id: dict[str, Path],
    mapping_info: dict[str, dict[str, Any]],
    priority_set: set[str],
    workspace: Path,
) -> dict[str, Any]:
    note = dict(existing)
    pid = str(note.get("paper_id") or row.get("paper_id") or "").strip()
    if not pid:
        return note

    note.setdefault("paper_id", pid)
    note.setdefault("title", row.get("title") or "")
    note.setdefault("year", int(row["year"]) if str(row.get("year") or "").isdigit() else str(row.get("year") or ""))
    note.setdefault("url", row.get("url") or "")

    arxiv_id = str(note.get("arxiv_id") or "").strip() or str(row.get("arxiv_id") or "").strip() or str(meta.get("arxiv_id") or "").strip()
    note["arxiv_id"] = arxiv_id
    note.setdefault("primary_category", str(meta.get("primary_category") or "").strip())
    note.setdefault("categories", meta.get("categories") or [])

    pdf_url = str(note.get("pdf_url") or "").strip() or str(row.get("pdf_url") or "").strip() or str(meta.get("pdf_url") or "").strip()
    note["pdf_url"] = pdf_url

    mapped_sections = sorted(mapping_info.get(pid, {}).get("sections", set()))
    note.setdefault("mapped_sections", mapped_sections)
    note["priority"] = "high" if pid in priority_set else str(note.get("priority") or "normal")

    fulltext_path = fulltext_by_id.get(pid)
    fulltext_ok = bool(fulltext_path and fulltext_path.exists() and fulltext_path.stat().st_size > 0)
    abstract = str(meta.get("abstract") or "").strip()
    has_abstract = bool(abstract)
    note["evidence_level"] = "fulltext" if fulltext_ok else ("abstract" if has_abstract else "title")
    if fulltext_ok and fulltext_path:
        note.setdefault("fulltext_path", str(fulltext_path.relative_to(workspace)))
    else:
        note.setdefault("fulltext_path", "")

    note.setdefault("authors", meta.get("authors") or [])
    note.setdefault("abstract", abstract)

    # Ensure bibkey exists (never overwrite).
    used: set[str] = set()
    bibkey = str(note.get("bibkey") or "").strip()
    if bibkey:
        used.add(bibkey)
    note.setdefault("bibkey", _make_bibkey(authors=note.get("authors") or [], year=str(row.get("year") or ""), title=row.get("title") or "", used=used))
    return note


if __name__ == "__main__":
    raise SystemExit(main())

