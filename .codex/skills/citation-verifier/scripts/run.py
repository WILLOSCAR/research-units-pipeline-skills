from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")

    parser.add_argument(
        "--offline",
        action="store_true",
        help="Generate verification records without network verification (verification_status=offline_generated).",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing citations/verified.jsonl records (does not rewrite citations/ref.bib).",
    )
    parser.add_argument("--timeout", type=int, default=15, help="Network timeout (seconds) for verify-only.")
    parser.add_argument("--max-bytes", type=int, default=2_000_000, help="Max bytes to read per URL for verify-only.")
    parser.add_argument("--verification-note", default="auto-generated; verify manually if needed")

    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(repo_root))

    from tooling.common import atomic_write_text, ensure_dir, parse_semicolon_list, read_jsonl, today_iso, write_jsonl

    workspace = Path(args.workspace).resolve()
    inputs = parse_semicolon_list(args.inputs) or ["papers/paper_notes.jsonl"]
    outputs = parse_semicolon_list(args.outputs) or ["citations/ref.bib", "citations/verified.jsonl"]

    notes_path = workspace / inputs[0]
    bib_path = workspace / outputs[0]
    verified_path = workspace / outputs[1] if len(outputs) > 1 else workspace / "citations/verified.jsonl"

    ensure_dir(verified_path.parent)

    today = today_iso()

    if args.verify_only:
        records = read_jsonl(verified_path)
        recs = [r for r in records if isinstance(r, dict)]
        if not recs:
            raise SystemExit(f"No verification records found: {verified_path}")

        updated: list[dict[str, Any]] = []
        for rec in recs:
            status = str(rec.get("verification_status") or "").strip()
            if status == "verified_online":
                updated.append(rec)
                continue

            title = str(rec.get("title") or "").strip()
            url = str(rec.get("url") or "").strip()
            rec["date"] = today

            if not title or not url:
                rec["verification_status"] = "needs_manual_verification"
                rec.setdefault("notes", args.verification_note)
                updated.append(rec)
                continue

            ok, info = _verify_url_title(
                url,
                expected_title=title,
                timeout=int(args.timeout),
                max_bytes=int(args.max_bytes),
            )

            rec["verified_title"] = info.get("page_title") or ""
            rec["verified_url"] = info.get("final_url") or url

            if ok:
                rec["verification_status"] = "verified_online"
            else:
                rec["verification_status"] = "verify_failed"
                rec["error"] = info.get("error") or ""
                rec.setdefault("notes", args.verification_note)

            updated.append(rec)

        write_jsonl(verified_path, updated)
        return 0

    notes = read_jsonl(notes_path)
    if not notes:
        raise SystemExit(f"No paper notes found: {notes_path}")

    ensure_dir(bib_path.parent)

    bib_entries: list[str] = []
    verified: list[dict[str, Any]] = []
    for note in notes:
        if not isinstance(note, dict):
            continue

        bibkey = str(note.get("bibkey") or "").strip()
        title = str(note.get("title") or "").strip()
        url = str(note.get("url") or "").strip()
        year = note.get("year")
        authors = note.get("authors") or []
        author_field = _bibtex_author(authors)
        year_field = str(year) if year is not None else ""
        arxiv_id = _arxiv_id_from_note(note)
        primary_class = str(note.get("primary_category") or "").strip()

        if not bibkey:
            continue

        bib_entries.append(
            _bibtex_entry(
                bibkey=bibkey,
                title=title,
                author=author_field,
                year=year_field,
                url=url,
                arxiv_id=arxiv_id,
                primary_class=primary_class,
            )
        )

        verification_status = "offline_generated"  # record now, verify later
        if not title or not url:
            verification_status = "needs_manual_verification"

        verified.append(
            {
                "bibkey": bibkey,
                "title": title,
                "url": url,
                "date": today,
                "verification_status": verification_status,
                "notes": args.verification_note,
            }
        )

    atomic_write_text(bib_path, "% Auto-generated BibTeX (verify as needed)\n\n" + "".join(bib_entries))
    write_jsonl(verified_path, verified)
    return 0


def _bibtex_author(authors: Any) -> str:
    if isinstance(authors, list) and authors:
        return " and ".join([str(a).strip() for a in authors if str(a).strip()])
    if isinstance(authors, str) and authors.strip():
        return authors.strip()
    return ""


def _escape_tex(text: str) -> str:
    text = (text or "")
    # BibTeX parses braces structurally (even when TeX-escaped).
    # Upstream titles sometimes contain unbalanced braces (e.g., "4{K}" or stray leading "{")
    # which can break `bibtex`, so we strip braces here.
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text).strip()

    # Make common superscript patterns LaTeX-safe in text mode (avoids raw `^` errors).
    # Example: `MemR$^3$` -> `MemR\textsuperscript{3}`
    text = re.sub(r"(?<!\\)([A-Za-z])\s*\$\s*\^(\d+)\s*\$", r"\1\\textsuperscript{\2}", text)
    # Example: `M^3-Bench` -> `M\textsuperscript{3}-Bench`
    text = re.sub(r"(?<!\\)([A-Za-z])\^(\d+)", r"\1\\textsuperscript{\2}", text)

    # Escape LaTeX special characters (avoid double-escaping already-escaped sequences).
    specials = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_"}
    out: list[str] = []
    for i, ch in enumerate(text):
        if ch in specials and not (i > 0 and text[i - 1] == "\\"):
            out.append(specials[ch])
        else:
            out.append(ch)
    return "".join(out)


def _escape_url(url: str) -> str:
    url = (url or "").strip()
    # Keep URLs raw for LaTeX/url.sty; do not TeX-escape characters here.
    url = url.replace("{", "").replace("}", "")
    url = re.sub(r"\s+", "", url)
    return url

def _arxiv_id_from_note(note: dict[str, Any]) -> str:
    arxiv_id = str(note.get("arxiv_id") or "").strip()
    if arxiv_id:
        return _strip_arxiv_version(arxiv_id)
    url = str(note.get("url") or "").strip()
    m = re.search(r"arxiv\\.org/(?:abs|pdf)/([^/?#]+)", url)
    if not m:
        return ""
    return _strip_arxiv_version(m.group(1))


def _strip_arxiv_version(arxiv_id: str) -> str:
    # 2509.03990v2 -> 2509.03990
    arxiv_id = (arxiv_id or "").strip()
    return re.sub(r"v\\d+$", "", arxiv_id)


def _bibtex_entry(*, bibkey: str, title: str, author: str, year: str, url: str, arxiv_id: str, primary_class: str) -> str:
    fields: list[str] = []
    if arxiv_id:
        fields.append(f"@article{{{bibkey},")
        fields.append(f"  title        = {{{_escape_tex(title)}}},")
        fields.append(f"  author       = {{{_escape_tex(author)}}},")
        fields.append(f"  year         = {{{_escape_tex(year)}}},")
        fields.append(f"  journal      = {{arXiv preprint arXiv:{_escape_tex(arxiv_id)}}},")
        fields.append(f"  eprint       = {{{_escape_tex(arxiv_id)}}},")
        fields.append("  archivePrefix= {arXiv},")
        if primary_class:
            fields.append(f"  primaryClass = {{{_escape_tex(primary_class)}}},")
        if url:
            fields.append(f"  url          = {{{_escape_url(url)}}},")
        fields.append("}")
        fields.append("")
        return "\n".join(fields)

    # Fallback: minimal @misc.
    fields.append(f"@misc{{{bibkey},")
    fields.append(f"  title        = {{{_escape_tex(title)}}},")
    fields.append(f"  author       = {{{_escape_tex(author)}}},")
    fields.append(f"  year         = {{{_escape_tex(year)}}},")
    if url:
        fields.append(f"  howpublished = {{\\url{{{_escape_url(url)}}}}},")
    fields.append("}")
    fields.append("")
    return "\n".join(fields)


def _normalize_title(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _verify_url_title(url: str, *, expected_title: str, timeout: int, max_bytes: int) -> tuple[bool, dict[str, str]]:
    expected = _normalize_title(expected_title)
    if not url or not expected:
        return False, {"final_url": url, "page_title": "", "error": "missing url/title"}

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "research-units-pipeline/1.0 (citation-verifier)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=max(1, int(timeout))) as resp:
            final_url = str(resp.geturl() or url)
            raw = resp.read(max(1024, int(max_bytes)))
    except Exception as exc:
        return False, {"final_url": url, "page_title": "", "error": f"request failed: {type(exc).__name__}: {exc}"}

    text = raw.decode("utf-8", errors="ignore")
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", text)
    page_title = re.sub(r"\s+", " ", (m.group(1) if m else "").strip())

    got = _normalize_title(page_title)
    info = {"final_url": final_url, "page_title": page_title}

    if not got:
        return False, {**info, "error": "no <title> found"}

    if expected in got or got in expected:
        return True, info

    etoks = set(expected.split())
    gtoks = set(got.split())
    overlap = len(etoks & gtoks) / max(1, len(etoks))
    if overlap >= 0.6:
        return True, info

    return False, {**info, "error": f"title mismatch (token_overlap={overlap:.2f})"}


if __name__ == "__main__":
    raise SystemExit(main())
