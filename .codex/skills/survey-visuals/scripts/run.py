from __future__ import annotations

import argparse
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

    from tooling.common import ensure_dir, load_yaml, parse_semicolon_list, read_jsonl, read_tsv

    workspace = Path(args.workspace).resolve()
    inputs = parse_semicolon_list(args.inputs) or [
        "outline/outline.yml",
        "outline/claim_evidence_matrix.md",
        "papers/paper_notes.jsonl",
        "citations/ref.bib",
    ]
    outputs = parse_semicolon_list(args.outputs) or ["outline/timeline.md", "outline/figures.md"]

    # Backward compatible:
    # - 3 outputs: tables_index + timeline + figures (legacy)
    # - 2 outputs: timeline + figures (tables are produced by `table-filler` + `appendix-table-writer`)
    out_tables: Path | None = None
    out_timeline: Path
    out_figures: Path
    if len(outputs) >= 3:
        out_tables = workspace / outputs[0]
        out_timeline = workspace / outputs[1]
        out_figures = workspace / outputs[2]
    elif len(outputs) == 2:
        out_timeline = workspace / outputs[0]
        out_figures = workspace / outputs[1]
    else:
        # Legacy fallback (kept for older call sites): write an internal index table, not a paper table.
        out_tables = workspace / "outline" / "tables_index.md"
        out_timeline = workspace / "outline" / "timeline.md"
        out_figures = workspace / "outline" / "figures.md"

    if out_tables is not None:
        ensure_dir(out_tables.parent)
    ensure_dir(out_timeline.parent)
    ensure_dir(out_figures.parent)

    outline_path = workspace / inputs[0]
    outline = load_yaml(outline_path) if outline_path.exists() else []

    notes_path = workspace / "papers" / "paper_notes.jsonl"
    notes = read_jsonl(notes_path) if notes_path.exists() else []

    mapping_path = workspace / "outline" / "mapping.tsv"
    mappings = read_tsv(mapping_path) if mapping_path.exists() else []

    notes_by_id = {str(n.get("paper_id") or "").strip(): n for n in notes if isinstance(n, dict)}
    bibkey_by_pid = {
        pid: str(n.get("bibkey") or "").strip()
        for pid, n in notes_by_id.items()
        if pid and str(n.get("bibkey") or "").strip()
    }

    mapped_by_section: dict[str, list[str]] = {}
    for row in mappings:
        sid = str(row.get("section_id") or "").strip()
        pid = str(row.get("paper_id") or "").strip()
        if sid and pid:
            mapped_by_section.setdefault(sid, []).append(pid)

    # Write artifacts (regenerate by default; skip only if explicit `*.refined.ok` marker exists).
    if out_tables is not None:
        _maybe_write(
            out_tables,
            _render_tables(outline=outline, mapped_by_section=mapped_by_section, notes_by_id=notes_by_id, bibkey_by_pid=bibkey_by_pid),
        )
    _maybe_write(out_timeline, _render_timeline(notes_by_id=notes_by_id, bibkey_by_pid=bibkey_by_pid))
    _maybe_write(out_figures, _render_figures(outline=outline, notes_by_id=notes_by_id, bibkey_by_pid=bibkey_by_pid))
    return 0


def _maybe_write(path: Path, content: str) -> None:
    freeze_marker = path.with_name(f"{path.name}.refined.ok")
    if path.exists() and path.stat().st_size > 0:
        if freeze_marker.exists():
            return
        _backup_existing(path)

    from tooling.common import atomic_write_text

    atomic_write_text(path, content)



def _backup_existing(path: Path) -> None:
    from tooling.common import backup_existing

    backup_existing(path)

def _is_placeholder(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return True
    if "<!-- SCAFFOLD" in text:
        return True
    if re.search(r"(?i)\b(?:TODO|TBD|FIXME)\b", text):
        return True
    if re.search(r"\[@(?:Key|KEY)\d+", text):
        return True
    return False


def _iter_subsections(outline: list) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for section in outline if isinstance(outline, list) else []:
        if not isinstance(section, dict):
            continue
        for sub in section.get("subsections") or []:
            if not isinstance(sub, dict):
                continue
            sid = str(sub.get("id") or "").strip()
            title = str(sub.get("title") or "").strip()
            bullets = sub.get("bullets") or []
            if sid and title:
                items.append({"id": sid, "title": title, "bullets": bullets})
    return items


def _extract_prefixed(bullets: list[str], *, prefix: str) -> str:
    prefix = (prefix or "").strip().lower()
    for b in bullets:
        b = str(b).strip()
        if not b:
            continue
        m = re.match(r"^([A-Za-z ]+)\s*[:：]\s*(.+)$", b)
        if not m:
            continue
        head = (m.group(1) or "").strip().lower()
        if head == prefix:
            return (m.group(2) or "").strip()
    return ""


def _extract_list_prefixed(bullets: list[str], *, prefix: str) -> list[str]:
    raw = _extract_prefixed(bullets, prefix=prefix)
    if not raw:
        return []
    return [p.strip() for p in re.split(r"[,;；]", raw) if p.strip()]


def _render_tables(*, outline: list, mapped_by_section: dict[str, list[str]], notes_by_id: dict[str, dict[str, Any]], bibkey_by_pid: dict[str, str]) -> str:
    subs = _iter_subsections(outline)

    lines: list[str] = [
        "# Tables",
        "",
        "## Table 1: Subsection evidence plan (RQ -> evidence needs -> mapped works)",
        "",
        "| Subsection | RQ | Evidence needs | Representative works |",
        "|---|---|---|---|",
    ]

    rows_written = 0
    for sub in subs:
        sid = sub["id"]
        title = sub["title"]
        bullets = [str(b).strip() for b in (sub.get("bullets") or []) if str(b).strip()]
        rq = _extract_prefixed(bullets, prefix="rq")
        evidence_needs = _extract_list_prefixed(bullets, prefix="evidence needs")
        axes = "; ".join(evidence_needs[:6])

        pids = mapped_by_section.get(sid, [])
        uniq: list[str] = []
        for pid in pids:
            if pid in notes_by_id and pid not in uniq:
                uniq.append(pid)
            if len(uniq) >= 3:
                break
        rep_cells: list[str] = []
        for pid in uniq:
            note = notes_by_id.get(pid, {})
            bibkey = bibkey_by_pid.get(pid, "")
            cite = f" [@{bibkey}]" if bibkey else ""
            rep_cells.append(f"`{pid}` {str(note.get('title') or '').strip()}{cite}".strip())
        rep = "<br>".join(rep_cells) if rep_cells else ""

        lines.append(
            "| "
            + " ".join([sid, title]).replace("|", " ")
            + " | "
            + rq.replace("|", " ")
            + " | "
            + axes.replace("|", " ")
            + " | "
            + rep.replace("|", " ")
            + " |"
        )
        rows_written += 1
        if rows_written >= 12:
            break

    if rows_written == 0:
        lines.append("| (no outline subsections found) | - | - | - |")

    lines.extend(
        [
            "",
            "## Table 2: High-priority papers (quick view)",
            "",
            "| Work | Contribution (from notes) | Evidence | Notable limitation |",
            "|---|---|---|---|",
        ]
    )

    high = [n for n in notes_by_id.values() if str(n.get("priority") or "").strip().lower() == "high"]
    pool = high if high else list(notes_by_id.values())
    pool.sort(key=lambda n: (-_year_int(n.get("year")), str(n.get("paper_id") or "")))

    wrote = 0
    for note in pool[:14]:
        pid = str(note.get("paper_id") or "").strip()
        if not pid:
            continue
        bibkey = bibkey_by_pid.get(pid, "")
        if not bibkey:
            continue
        title = str(note.get("title") or "").strip()
        contrib = _first_bullet(note)
        evidence = str(note.get("evidence_level") or "").strip() or "abstract"
        lim = _first_limitation(note)
        lines.append(f"| `{pid}` {title} [@{bibkey}] | {contrib} | {evidence} | {lim} |")
        wrote += 1
        if wrote >= 10:
            break

    if wrote < 2:
        lines.append("| (insufficient notes) | Provide richer paper notes to populate this table. | - | - |")

    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_timeline(*, notes_by_id: dict[str, dict[str, Any]], bibkey_by_pid: dict[str, str]) -> str:
    notes = list(notes_by_id.values())
    notes = [n for n in notes if _year_int(n.get("year")) >= 2000 and str(n.get("paper_id") or "").strip()]
    notes.sort(key=lambda n: (_year_int(n.get("year")), str(n.get("paper_id") or "")))

    lines: list[str] = [
        "# Timeline / Evolution",
        "",
        "This timeline is a lightweight, citation-backed set of milestones extracted from the core set.",
        "",
    ]

    bullets: list[str] = []
    for note in notes:
        y = _year_int(note.get("year"))
        pid = str(note.get("paper_id") or "").strip()
        bibkey = bibkey_by_pid.get(pid, "")
        if not bibkey:
            continue
        title = str(note.get("title") or "").strip()
        bullets.append(f"- {y}: {title} (`{pid}`) [@{bibkey}]")
        if len(bullets) >= 10:
            break

    if len(bullets) < 8:
        for note in reversed(notes):
            if len(bullets) >= 8:
                break
            y = _year_int(note.get("year"))
            pid = str(note.get("paper_id") or "").strip()
            bibkey = bibkey_by_pid.get(pid, "")
            if not bibkey:
                continue
            title = str(note.get("title") or "").strip()
            line = f"- {y}: {title} (`{pid}`) [@{bibkey}]"
            if line not in bullets:
                bullets.append(line)

    lines.extend(bullets[: max(8, len(bullets))])
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_figures(*, outline: list, notes_by_id: dict[str, dict[str, Any]], bibkey_by_pid: dict[str, str]) -> str:
    cite_keys: list[str] = []
    notes = list(notes_by_id.values())
    notes.sort(
        key=lambda n: (
            0 if str(n.get("priority") or "").strip().lower() == "high" else 1,
            -_year_int(n.get("year")),
        )
    )
    for note in notes:
        pid = str(note.get("paper_id") or "").strip()
        key = bibkey_by_pid.get(pid, "")
        if key and key not in cite_keys:
            cite_keys.append(key)
        if len(cite_keys) >= 6:
            break

    cite = f"[@{'; @'.join(cite_keys[:4])}]" if cite_keys else ""

    n_sub = len(_iter_subsections(outline))
    outline_hint = f"{n_sub} subsections" if n_sub else "the approved outline"

    lines: list[str] = [
        "# Figure specs (no prose)",
        "",
        "- Figure 1 (pipeline + dataflow): A diagram from retrieval -> curation -> taxonomy -> mapping -> evidence -> synthesis -> PDF.",
        "  - Purpose: help readers understand where evidence comes from and how sections are grounded.",
        "  - Elements: queries; raw set; dedupe/rank; taxonomy; outline; mapping; notes; claim-evidence matrix; draft; LaTeX/PDF.",
        f"  - Supported by: {cite}".rstrip(),
        "",
        f"- Figure 2 (taxonomy view): A two-level tree summarizing {outline_hint} with representative works per leaf.",
        "  - Purpose: provide a navigable mental model of the design space before details.",
        "  - Elements: top-level chapters; leaf subtopics; 2-3 cited exemplars per leaf; arrows for common trade-offs.",
        f"  - Supported by: {cite}".rstrip(),
        "",
    ]
    return "\n".join([ln for ln in lines if ln.strip()]).rstrip() + "\n"


def _first_bullet(note: dict[str, Any]) -> str:
    bullets = note.get("summary_bullets") or []
    if isinstance(bullets, list):
        for b in bullets:
            b = str(b).strip()
            if b:
                return b.replace("|", " ")
    method = str(note.get("method") or "").strip()
    if method:
        return method.replace("|", " ")
    return "Metadata-only; see paper notes for details.".replace("|", " ")


def _first_limitation(note: dict[str, Any]) -> str:
    lims = note.get("limitations") or []
    if isinstance(lims, list):
        for l in lims:
            l = str(l).strip()
            if l:
                return l.replace("|", " ")
    return "Limitations not captured in metadata; verify from full text.".replace("|", " ")


def _milestone_phrase(title: str) -> str:
    terms = _salient_terms(title)
    if not terms:
        return "a representative work in the core set"
    if len(terms) == 1:
        return f"highlights a key line of work around {terms[0]}"
    return f"highlights a line of work connecting {terms[0]} and {terms[1]}"


def _salient_terms(text: str) -> list[str]:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    toks = [t for t in text.split() if t]
    stop = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
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
        "toward",
        "towards",
        "model",
        "models",
        "method",
        "methods",
        "system",
        "systems",
        "approach",
        "approaches",
        "survey",
        "review",
    }
    out: list[str] = []
    for t in toks:
        if len(t) < 4:
            continue
        if t in stop:
            continue
        if t not in out:
            out.append(t)
    return out[:6]


def _year_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
