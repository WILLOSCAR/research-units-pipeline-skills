from __future__ import annotations

import argparse
import hashlib
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
    outputs = parse_semicolon_list(args.outputs) or ["papers/paper_notes.jsonl", "papers/evidence_bank.jsonl"]

    core_path = workspace / inputs[0]
    fulltext_index_path = workspace / "papers" / "fulltext_index.jsonl"
    mapping_path = workspace / "outline" / "mapping.tsv"
    dedup_path = workspace / "papers" / "papers_dedup.jsonl"
    out_path = workspace / outputs[0]
    bank_path = workspace / (outputs[1] if len(outputs) >= 2 else "papers/evidence_bank.jsonl")

    core_rows = _load_core_set(core_path)
    if not core_rows:
        raise SystemExit(f"No rows found in {core_path}")

    metadata = read_jsonl(dedup_path) if dedup_path.exists() else []
    fulltext_by_id = _load_fulltext_index(fulltext_index_path, workspace=workspace)
    mapping_info = _load_mapping(mapping_path) if mapping_path.exists() else {}

    priority_set = _select_priority_papers(core_rows, mapping_info=mapping_info)
    core_by_id = {r["paper_id"]: r for r in core_rows}

    existing_notes_by_id: dict[str, dict[str, Any]] = {}
    if out_path.exists():
        for rec in read_jsonl(out_path):
            if not isinstance(rec, dict):
                continue
            pid = str(rec.get("paper_id") or "").strip()
            if pid:
                existing_notes_by_id[pid] = rec

    used_bibkeys: set[str] = set()
    for pid, rec in existing_notes_by_id.items():
        row = core_by_id.get(pid)
        if not row:
            continue
        if not _note_matches_row(rec, row):
            continue
        bibkey = str(rec.get("bibkey") or "").strip()
        if bibkey:
            used_bibkeys.add(bibkey)

    notes: list[dict[str, Any]] = []
    for row in core_rows:
        paper_id = row["paper_id"]
        existing = existing_notes_by_id.get(paper_id)
        if existing and _note_matches_row(existing, row):
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
            key_results = _infer_key_results(abstract=abstract, max_items=2)
            limitations = _infer_limitations(evidence_level=evidence_level, mapped_sections=mapped_sections, abstract=abstract)
        else:
            summary_bullets = _abstract_to_bullets(abstract)
            # Keep normal-priority notes lightweight, but still extract method/results so the evidence bank is usable.
            method = _infer_method(title=row["title"], abstract=abstract, bullets=summary_bullets)
            key_results = _infer_key_results(abstract=abstract, max_items=2)
            limitations = _infer_limitations(evidence_level=evidence_level, mapped_sections=mapped_sections, abstract=abstract)

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

    # Evidence bank: addressable evidence items for binder/writer/auditor.
    bank_freeze = bank_path.with_name("evidence_bank.refined.ok")
    if not (bank_path.exists() and bank_path.stat().st_size > 0 and bank_freeze.exists()):
        if bank_path.exists() and bank_path.stat().st_size > 0:
            _backup_existing(bank_path)
        bank_items = _build_evidence_bank(notes)
        write_jsonl(bank_path, bank_items)

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



def _note_matches_row(note: dict[str, Any], row: dict[str, str]) -> bool:
    """Return True iff an existing note still corresponds to the core-set row for this paper_id.

    This prevents catastrophic drift when `papers/core_set.csv` is regenerated and paper_ids are reassigned.
    """

    from tooling.common import normalize_title_for_dedupe

    note_title = normalize_title_for_dedupe(str(note.get("title") or "").strip())
    row_title = normalize_title_for_dedupe(str(row.get("title") or "").strip())
    if not note_title or not row_title or note_title != row_title:
        return False

    n_year = str(note.get("year") or "").strip()
    r_year = str(row.get("year") or "").strip()
    if n_year and r_year and n_year != r_year:
        return False

    return True


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

    bullets = _abstract_to_bullets(abstract, max_items=5)
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


def _infer_key_results(*, abstract: str, max_items: int = 1) -> list[str]:
    abstract = (abstract or "").strip()

    try:
        max_n = int(max_items)
    except Exception:
        max_n = 1
    max_n = max(1, min(3, max_n))

    if not abstract:
        return [
            "Key quantitative results are not fully stated in available metadata; verify benchmarks/metrics in the full text before citing numbers."
        ]

    sents = _split_sentences(abstract)
    scored: list[tuple[float, int, str]] = []

    for idx, s in enumerate(sents):
        s = re.sub(r"\s+", " ", (s or "").strip())
        if len(s) < 16:
            continue
        low = s.lower()
        if low.startswith("project site") or "code:" in low:
            continue

        score = 0.0
        if re.search(r"\b\d+(?:\.\d+)?%?\b", s):
            score += 3.0
        if re.search(
            r"(?i)\b(benchmark|benchmarks|dataset|datasets|metric|metrics|evaluation|human|accuracy|success(?: rate)?|f1|bleu|rouge|mmlu|gsm8k|hotpotqa|fever|alfworld|webshop)\b",
            s,
        ):
            score += 2.0
        if re.search(r"(?i)\b(outperform|improv|achiev|state[- ]of[- ]the[- ]art|sota|gain|increase|decrease)\b", s):
            score += 1.0

        if score > 0:
            scored.append((score, idx, s))

    if scored:
        scored.sort(key=lambda t: (-t[0], t[1]))
        out: list[str] = []
        seen: set[str] = set()
        for _, _, s in scored:
            if s in seen:
                continue
            seen.add(s)
            out.append(s)
            if len(out) >= max_n:
                break
        if out:
            return out

    # Fall back to the last sentence as a coarse "result" proxy.
    last = _last_sentence(abstract)
    if last:
        return [re.sub(r"\s+", " ", last).strip()]

    return [abstract[:240].strip()]


def _infer_limitations(*, evidence_level: str, mapped_sections: list[str], abstract: str) -> list[str]:
    evidence_level = (evidence_level or "").strip().lower() or "abstract"
    abstract = (abstract or "").strip()

    lims: list[str] = []
    if evidence_level == "fulltext":
        lims.append(
            "Even with extracted text, evaluation details may be incomplete; verify the official PDF for exact settings and ablations."
        )
    elif evidence_level == "abstract":
        lims.append(
            "Abstract-level evidence only: validate assumptions, evaluation protocol, and failure cases in the full paper before relying on this as key evidence."
        )
    else:
        lims.append(
            "Title-only evidence: do not infer methods/results beyond what the title states; fetch abstract/full text before using this as key evidence."
        )

    # Try to capture an explicit limitation cue from the abstract (best-effort, still conservative).
    if abstract:
        sent = _pick_sentence(
            abstract,
            patterns=[
                r"(?i)\b(limitations?|future work|open problems?|remains (?:an )?open|we (?:leave|defer)|we do not|does not)\b",
            ],
        )
        if sent:
            sent = re.sub(r"\s+", " ", sent).strip()
            low = sent.lower()
            if sent and not low.startswith("project site") and sent not in lims:
                lims.append(sent)

    if not abstract:
        lims.append("Abstract missing in metadata; treat all details as provisional until verified.")

    return lims[:3]
_ABBREV_RX = re.compile(
    r"\b(?:e\.g\.|i\.e\.|etc\.|cf\.|vs\.|et al\.|fig\.|figs\.|eq\.|eqs\.|sec\.|secs\.|no\.|dr\.|mr\.|ms\.|prof\.)",
    flags=re.IGNORECASE,
)


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []

    def protect(m: re.Match[str]) -> str:
        return (m.group(0) or "").replace(".", "__DOT__")

    protected = _ABBREV_RX.sub(protect, text)
    parts = re.split(r"(?<=[.!?])\s+", protected)
    out: list[str] = []
    for p in parts:
        p = (p or "").replace("__DOT__", ".").strip()
        if p:
            out.append(p)
    return out


def _pick_sentence(text: str, *, patterns: list[str]) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return ""
    sents = _split_sentences(text)
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
    sents = _split_sentences(text)
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


def _abstract_to_bullets(abstract: str, *, max_items: int = 3) -> list[str]:
    abstract = (abstract or "").strip()
    if not abstract:
        return []

    try:
        max_n = int(max_items)
    except Exception:
        max_n = 3
    max_n = max(1, min(8, max_n))

    # Deterministic scaffold: use first few sentences as bullets (LLM should refine for priority papers).
    parts = _split_sentences(abstract)
    bullets: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        bullets.append(p)
        if len(bullets) >= max_n:
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
    note["title"] = row.get("title") or str(note.get("title") or "").strip()
    note["year"] = int(row["year"]) if str(row.get("year") or "").isdigit() else str(row.get("year") or "")
    note["url"] = row.get("url") or str(note.get("url") or "").strip()

    arxiv_id = str(note.get("arxiv_id") or "").strip() or str(row.get("arxiv_id") or "").strip() or str(meta.get("arxiv_id") or "").strip()
    note["arxiv_id"] = arxiv_id
    note.setdefault("primary_category", str(meta.get("primary_category") or "").strip())
    note.setdefault("categories", meta.get("categories") or [])

    pdf_url = str(note.get("pdf_url") or "").strip() or str(row.get("pdf_url") or "").strip() or str(meta.get("pdf_url") or "").strip()
    note["pdf_url"] = pdf_url

    mapped_sections = sorted(mapping_info.get(pid, {}).get("sections", set()))
    note["mapped_sections"] = mapped_sections
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
    abstract = str(note.get("abstract") or abstract or "").strip()

    # If a paper becomes high-priority after mapping updates, upgrade the note in-place
    # (method/key results/limitations) instead of keeping a normal-priority stub.
    if str(note.get("priority") or "").strip().lower() == "high":
        bullets = note.get("summary_bullets")
        if not isinstance(bullets, list) or len([b for b in bullets if str(b).strip()]) < 3:
            bullets = _high_priority_bullets(title=str(note.get("title") or ""), abstract=abstract, mapped_sections=mapped_sections)
            note["summary_bullets"] = bullets

        method = str(note.get("method") or "").strip()
        if not method:
            note["method"] = _infer_method(title=str(note.get("title") or ""), abstract=abstract, bullets=bullets or [])

        key_results = note.get("key_results")
        if not isinstance(key_results, list) or not key_results:
            note["key_results"] = _infer_key_results(abstract=abstract, max_items=2)

        lims = note.get("limitations")
        if (not isinstance(lims, list)) or (not lims) or (len(lims) == 1 and str(lims[0]).lower().startswith("evidence level:")):
            note["limitations"] = _infer_limitations(evidence_level=str(note.get("evidence_level") or ""), mapped_sections=mapped_sections, abstract=abstract)



    # For normal-priority notes, still ensure method/results exist so downstream evidence binding is usable.
    bullets = note.get("summary_bullets")
    if not isinstance(bullets, list) or len([b for b in bullets if str(b).strip()]) < 1:
        bullets = _abstract_to_bullets(abstract, max_items=5)
        note["summary_bullets"] = bullets

    method = str(note.get("method") or "").strip()
    if not method:
        note["method"] = _infer_method(title=str(note.get("title") or ""), abstract=abstract, bullets=bullets or [])

    key_results = note.get("key_results")
    if not isinstance(key_results, list) or not [k for k in key_results if str(k).strip()]:
        note["key_results"] = _infer_key_results(abstract=abstract)

    lims = note.get("limitations")
    if not isinstance(lims, list) or not [x for x in lims if str(x).strip()]:
        note["limitations"] = _infer_limitations(evidence_level=str(note.get("evidence_level") or ""), mapped_sections=mapped_sections, abstract=abstract)

    # Ensure bibkey exists (never overwrite).
    used: set[str] = set()
    bibkey = str(note.get("bibkey") or "").strip()
    if bibkey:
        used.add(bibkey)
    note.setdefault("bibkey", _make_bibkey(authors=note.get("authors") or [], year=str(row.get("year") or ""), title=row.get("title") or "", used=used))
    return note





def _backup_existing(path: Path) -> None:
    from tooling.common import backup_existing

    backup_existing(path)

def _build_evidence_bank(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract addressable evidence items from paper notes.

    This is best-effort and stays conservative: it only turns existing note fields
    into short, citeable snippets with stable IDs and provenance pointers.
    """

    def norm(s: str) -> str:
        s = re.sub(r"\s+", " ", (s or '').strip())
        return s

    def bad_lim(s: str) -> bool:
        low = (s or '').strip().lower()
        return (
            low.startswith('evidence level:')
            or low.startswith('abstract-level evidence only')
            or low.startswith('title-only evidence')
            or low.startswith('even with extracted text')
            or low.startswith('this work is mapped to:')
            or low.startswith('mapped to outline subsections:')
        )

    def evidence_id(pid: str, kind: str, snippet: str) -> str:
        h = hashlib.sha1(f"{kind}|{snippet}".encode('utf-8', errors='ignore')).hexdigest()[:10]
        return f"E-{pid}-{h}"

    def confidence(level: str) -> str:
        level = (level or '').strip().lower()
        if level == 'fulltext':
            return 'high'
        if level == 'abstract':
            return 'medium'
        return 'low'

    def tags_for(snippet: str) -> list[str]:
        low = (snippet or '').lower()
        tags: set[str] = set()
        if any(w in low for w in ['benchmark', 'benchmarks', 'dataset', 'datasets', 'metric', 'metrics', 'eval', 'evaluation']):
            tags.add('evaluation')
        if any(w in low for w in ['tool', 'tools', 'api', 'function call', 'function-calling', 'mcp', 'schema']):
            tags.add('tooling')
        if any(w in low for w in ['memory', 'retrieval', 'rag', 'cache']):
            tags.add('memory')
        if any(w in low for w in ['attack', 'vulnerab', 'prompt injection', 'exfiltration', 'jailbreak', 'guardrail', 'sandbox']):
            tags.add('security')
        if re.search(r"\b\d+(?:\.\d+)?%?\b", low):
            tags.add('numbers')
        return sorted(tags)

    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for note in [n for n in notes if isinstance(n, dict)]:
        pid = str(note.get('paper_id') or '').strip()
        if not pid:
            continue
        bibkey = str(note.get('bibkey') or '').strip()
        level = str(note.get('evidence_level') or '').strip().lower()
        title = str(note.get('title') or '').strip()
        year = note.get('year')

        def add(kind: str, snippet: str, pointer: str) -> None:
            snippet = norm(snippet)
            if not snippet or len(snippet) < 24:
                return
            if kind == 'limitation' and bad_lim(snippet):
                return
            eid = evidence_id(pid, kind, snippet)
            if eid in seen:
                return
            seen.add(eid)
            items.append(
                {
                    'evidence_id': eid,
                    'paper_id': pid,
                    'bibkey': bibkey,
                    'title': title,
                    'year': year,
                    'evidence_level': level or 'unknown',
                    'claim_type': kind,
                    'snippet': snippet,
                    'locator': {'source': 'paper_notes', 'pointer': pointer},
                    'confidence': confidence(level),
                    'tags': tags_for(snippet),
                }
            )

        # Method / results / summary bullets are the best structured sources.
        method = note.get('method')
        if isinstance(method, str) and method.strip():
            add('method', method, f"papers/paper_notes.jsonl:paper_id={pid}#method")

        for idx, kr in enumerate(note.get('key_results') or []):
            if isinstance(kr, str) and kr.strip():
                add('result', kr, f"papers/paper_notes.jsonl:paper_id={pid}#key_results[{idx}]")

        for idx, b in enumerate(note.get('summary_bullets') or []):
            if isinstance(b, str) and b.strip():
                add('summary', b, f"papers/paper_notes.jsonl:paper_id={pid}#summary_bullets[{idx}]")

        for idx, lim in enumerate(note.get('limitations') or []):
            if isinstance(lim, str) and lim.strip():
                add('limitation', lim, f"papers/paper_notes.jsonl:paper_id={pid}#limitations[{idx}]")

        # Ensure at least one addressable snippet per paper (fallback to title).
        if not any(it.get('paper_id') == pid for it in items):
            add('title', title or f"Paper {pid}", f"papers/paper_notes.jsonl:paper_id={pid}#title")

    return items


if __name__ == "__main__":
    raise SystemExit(main())
