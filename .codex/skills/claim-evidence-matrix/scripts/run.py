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

    from tooling.common import atomic_write_text, load_yaml, parse_semicolon_list, read_jsonl, read_tsv, tokenize

    workspace = Path(args.workspace).resolve()
    inputs = parse_semicolon_list(args.inputs) or ["outline/outline.yml", "papers/paper_notes.jsonl"]
    outputs = parse_semicolon_list(args.outputs) or ["outline/claim_evidence_matrix.md"]

    outline_path = workspace / inputs[0]
    notes_path = workspace / inputs[1]
    mapping_path = workspace / "outline" / "mapping.tsv"
    out_path = workspace / outputs[0]

    # Bootstrap-only behavior: if a human/LLM already refined the matrix, do not overwrite.
    if _looks_refined_matrix(out_path):
        return 0

    outline = load_yaml(outline_path) or []
    notes = read_jsonl(notes_path)
    mappings = read_tsv(mapping_path) if mapping_path.exists() else []

    papers_by_id: dict[str, dict[str, Any]] = {}
    for n in notes:
        if not isinstance(n, dict):
            continue
        pid = str(n.get("paper_id") or "").strip()
        if pid:
            papers_by_id[pid] = n

    paper_ids_fallback = [pid for pid in papers_by_id.keys() if pid]

    mapped_by_section: dict[str, list[str]] = {}
    for row in mappings:
        sid = str(row.get("section_id") or "").strip()
        pid = str(row.get("paper_id") or "").strip()
        if not sid or not pid:
            continue
        mapped_by_section.setdefault(sid, []).append(pid)

    parts: list[str] = [
        "# Claim–Evidence matrix",
        "",
        "This artifact is bullets-only and is meant to make evidence explicit before writing.",
        "",
    ]

    for subsection in _iter_subsections(outline):
        sid = subsection["id"]
        title = subsection["title"]
        bullets = [str(b).strip() for b in (subsection.get("bullets") or []) if str(b).strip()]

        rq = _extract_prefixed(bullets, prefix="rq")
        evidence_needs = _extract_list_prefixed(bullets, prefix="evidence needs")
        outline_axes = _extract_list_prefixed(bullets, prefix="comparison axes")

        pids = mapped_by_section.get(sid, [])
        uniq: list[str] = []
        for pid in pids:
            if pid in papers_by_id and pid not in uniq:
                uniq.append(pid)
        if not uniq:
            uniq = paper_ids_fallback[:6]
        uniq = uniq[:12]

        themes = _top_terms(
            [
                str(papers_by_id.get(pid, {}).get("title") or "") + " " + str(papers_by_id.get(pid, {}).get("abstract") or "")
                for pid in uniq
            ],
            tokenize=tokenize,
        )

        evidence_levels = _evidence_levels(pids=uniq, papers_by_id=papers_by_id)
        axes = _merge_axes(evidence_needs=evidence_needs, outline_axes=outline_axes, themes=themes)

        claim = _make_claim(title=title, rq=rq, axes=axes, themes=themes, evidence_levels=evidence_levels)

        parts.append(f"## {sid} {title}")
        parts.append("")

        if rq:
            parts.append(f"- RQ: {rq}")

        parts.append(f"- Claim: {claim}")

        if axes:
            parts.append(f"  - Axes: {'; '.join(axes[:8])}")
        if themes:
            parts.append(f"  - Themes: {', '.join(themes[:8])}")
        if evidence_levels:
            parts.append(f"  - Evidence levels: {', '.join([f'{k}={v}' for k, v in sorted(evidence_levels.items())])}.")

        for pid in uniq[:6]:
            note = papers_by_id.get(pid, {})
            bibkey = str(note.get("bibkey") or "").strip()
            cite = f" [@{bibkey}]" if bibkey else ""
            tagline = _tagline(note)
            if tagline:
                parts.append(f"  - Evidence: `{pid}`{cite} — {tagline}")
            else:
                parts.append(f"  - Evidence: `{pid}`{cite}")

        if evidence_levels.get("title", 0) >= 2 or evidence_levels.get("fulltext", 0) == 0:
            parts.append(
                "  - Caveat: Evidence is not full-text grounded for this subsection; treat the claim as provisional and prioritize abstract/fulltext enrichment before making strong generalizations."
            )

        parts.append("")

    atomic_write_text(out_path, "\n".join(parts).rstrip() + "\n")
    return 0


def _looks_refined_matrix(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    if "<!-- SCAFFOLD" in text:
        return False
    if re.search(r"(?i)\b(?:TODO|TBD|FIXME)\b", text):
        return False
    if "- Claim:" in text and len(text.strip()) > 600:
        return True
    return False


def _iter_subsections(outline: list) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for section in outline:
        if not isinstance(section, dict):
            continue
        for subsection in section.get("subsections") or []:
            if not isinstance(subsection, dict):
                continue
            sid = str(subsection.get("id") or "").strip()
            title = str(subsection.get("title") or "").strip()
            if sid and title:
                items.append({"id": sid, "title": title, "bullets": subsection.get("bullets") or []})
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
    parts = [p.strip() for p in re.split(r"[,;；]", raw) if p.strip()]
    return parts


def _merge_axes(*, evidence_needs: list[str], outline_axes: list[str], themes: list[str]) -> list[str]:
    axes: list[str] = []

    def _add(x: str) -> None:
        x = re.sub(r"\s+", " ", (x or "").strip())
        if not x:
            return
        if x.lower().startswith(("refine with evidence", "refine")):
            return
        if x not in axes:
            axes.append(x)

    for a in evidence_needs:
        _add(a)
    for a in outline_axes:
        _add(a)

    if not axes:
        for t in themes[:4]:
            _add(f"theme={t}")

    if not axes:
        axes = ["mechanism", "data", "evaluation", "limitations"]

    return axes[:8]


def _evidence_levels(*, pids: list[str], papers_by_id: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for pid in pids:
        lvl = str((papers_by_id.get(pid) or {}).get("evidence_level") or "").strip().lower() or "unknown"
        counts[lvl] = counts.get(lvl, 0) + 1
    return counts


def _make_claim(*, title: str, rq: str, axes: list[str], themes: list[str], evidence_levels: dict[str, int]) -> str:
    title = (title or "this subsection").strip()
    rq = (rq or "").strip()

    # Evidence-aware wording: avoid strong conclusions when evidence is not full-text grounded.
    provisional = evidence_levels.get("fulltext", 0) == 0

    axis_hint = ", ".join([a for a in axes[:3] if a])
    theme_hint = ", ".join([t for t in themes[:3] if t])

    lead = "Provisional claim" if provisional else "Claim"

    if rq and axis_hint:
        return f"{lead}: For {title}, answering the RQ requires comparing approaches along {axis_hint} and validating conclusions against the cited evidence."
    if axis_hint and theme_hint:
        return f"{lead}: In {title}, mapped works differ along {axis_hint}, with recurring emphases on {theme_hint}; comparisons should cite evaluation context explicitly."
    if axis_hint:
        return f"{lead}: In {title}, mapped works can be compared along {axis_hint}; the evidence should be used to clarify when each choice is preferred."
    if rq:
        return f"{lead}: {rq} (use mapped papers to support a concrete, subsection-specific answer)."
    return f"{lead}: Organize {title} into a small set of evidence-backed comparisons grounded in the mapped papers."


def _tagline(note: dict[str, Any]) -> str:
    method = str(note.get("method") or "").strip()
    if method and not method.lower().startswith("main idea (from title):"):
        return method

    bullets = note.get("summary_bullets") or []
    if isinstance(bullets, list):
        for b in bullets:
            b = str(b).strip()
            if b and len(b) >= 16:
                return b

    abstract = str(note.get("abstract") or "").strip()
    if abstract:
        return abstract.splitlines()[0].strip()

    return ""


def _top_terms(texts: list[str], *, tokenize) -> list[str]:
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
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "with",
        "via",
        "using",
        "use",
        "based",
        "new",
        "toward",
        "towards",
    }
    generic = {
        "survey",
        "review",
        "framework",
        "frameworks",
        "system",
        "systems",
        "model",
        "models",
        "approach",
        "approaches",
        "method",
        "methods",
    }
    counts: dict[str, int] = {}
    for text in texts:
        for t in tokenize(text or ""):
            if len(t) < 4:
                continue
            if t in stop or t in generic:
                continue
            counts[t] = counts.get(t, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [t for t, _ in ranked[:10]]


if __name__ == "__main__":
    raise SystemExit(main())
