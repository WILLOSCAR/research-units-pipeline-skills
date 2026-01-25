from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


def _is_placeholder(text: str) -> bool:
    low = (text or "").strip().lower()
    if not low:
        return True
    if "<!-- scaffold" in low:
        return True
    if "(placeholder)" in low:
        return True
    # Treat unicode ellipsis as placeholder leakage.
    if "…" in (text or ""):
        return True
    if re.search(r"(?i)\b(?:todo|tbd|fixme)\b", low):
        return True
    # Treat three-or-more dots as truncation / scaffold leakage in tables.
    if re.search(r"(?m)\.\.+", text or ""):
        return True
    return False


def _looks_refined(text: str) -> bool:
    if _is_placeholder(text):
        return False
    # Require at least 2 Markdown tables.
    seps = re.findall(r"(?m)^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", text)
    return len(seps) >= 2 and "[@" in text and len(text.strip()) >= 600


def _sid_key(s: str) -> tuple[int, ...]:
    out: list[int] = []
    for chunk in str(s).split("."):
        try:
            out.append(int(chunk))
        except Exception:
            out.append(9999)
    return tuple(out)


def _format_cites(keys: list[str]) -> str:
    cleaned: list[str] = []
    for k in keys:
        k = str(k or "").strip()
        if not k:
            continue
        if k.startswith("[@") and k.endswith("]"):
            k = k[2:-1]
        if k.startswith("@"):  # tolerate @Key
            k = k[1:]
        for token in re.findall(r"[A-Za-z0-9:_-]+", k):
            if token and token not in cleaned:
                cleaned.append(token)
    if not cleaned:
        return ""
    return "[@" + "; @".join(cleaned) + "]"


def _truncate(text: str, n: int) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= n:
        return text
    # Do not emit `...` markers; prefer shorter schemas/cells.
    return text[:n].rstrip()


def _collect_pack_citations(pack: dict[str, Any]) -> list[str]:
    keys: list[str] = []

    def add_many(citations: Any) -> None:
        if not isinstance(citations, list):
            return
        for c in citations:
            c = str(c or "").strip()
            if not c:
                continue
            if c.startswith("[@") and c.endswith("]"):
                c = c[2:-1]
            if c.startswith("@"):  # tolerate @Key
                c = c[1:]
            for k in re.findall(r"[A-Za-z0-9:_-]+", c):
                if k and k not in keys:
                    keys.append(k)

    for snip in pack.get("evidence_snippets") or []:
        if isinstance(snip, dict):
            add_many(snip.get("citations"))

    for block_name in [
        "definitions_setup",
        "claim_candidates",
        "concrete_comparisons",
        "evaluation_protocol",
        "failures_limitations",
    ]:
        for item in pack.get(block_name) or []:
            if isinstance(item, dict):
                add_many(item.get("citations"))

    return keys


def _backup_existing(path: Path) -> None:
    from tooling.common import backup_existing

    backup_existing(path)


def _clean_axis(axis: str) -> str:
    axis = re.sub(r"\s+", " ", (axis or "").strip())
    axis = axis.rstrip(" .;:，；。")
    # Make slashes breakable in LaTeX tables by surrounding with spaces.
    axis = re.sub(r"\s*/\s*", " / ", axis)
    return axis


def _clean_anchor_text(text: str) -> str:
    text = re.sub(r"\[@[^\]]+\]", "", str(text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text.rstrip(" .;:，；。")


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

    from tooling.common import atomic_write_text, ensure_dir, parse_semicolon_list, read_jsonl

    workspace = Path(args.workspace).resolve()

    inputs = parse_semicolon_list(args.inputs) or [
        "outline/table_schema.md",
        "outline/subsection_briefs.jsonl",
        "outline/evidence_drafts.jsonl",
        "outline/anchor_sheet.jsonl",
        "citations/ref.bib",
    ]
    outputs = parse_semicolon_list(args.outputs) or ["outline/tables_index.md"]

    schema_rel = next((p for p in inputs if str(p).endswith("outline/table_schema.md") or str(p).endswith("table_schema.md")), "outline/table_schema.md")
    briefs_rel = next((p for p in inputs if str(p).endswith("outline/subsection_briefs.jsonl") or str(p).endswith("subsection_briefs.jsonl")), "outline/subsection_briefs.jsonl")
    packs_rel = next((p for p in inputs if str(p).endswith("outline/evidence_drafts.jsonl") or str(p).endswith("evidence_drafts.jsonl")), "outline/evidence_drafts.jsonl")
    anchors_rel = next((p for p in inputs if str(p).endswith("outline/anchor_sheet.jsonl") or str(p).endswith("anchor_sheet.jsonl")), "outline/anchor_sheet.jsonl")
    bib_rel = next((p for p in inputs if str(p).endswith("citations/ref.bib") or str(p).endswith("ref.bib")), "citations/ref.bib")

    out_path = workspace / outputs[0]
    ensure_dir(out_path.parent)

    freeze_marker = out_path.with_name(f"{out_path.name}.refined.ok")
    if out_path.exists() and out_path.stat().st_size > 0:
        if freeze_marker.exists():
            return 0
        _backup_existing(out_path)

    # Read inputs (schema is a contract artifact; filler is driven by briefs + packs + anchors).
    briefs = read_jsonl(workspace / briefs_rel) if (workspace / briefs_rel).exists() else []
    packs = read_jsonl(workspace / packs_rel) if (workspace / packs_rel).exists() else []
    anchors = read_jsonl(workspace / anchors_rel) if (workspace / anchors_rel).exists() else []

    bib_text = (workspace / bib_rel).read_text(encoding="utf-8", errors="ignore") if (workspace / bib_rel).exists() else ""
    bib_keys = set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text))

    briefs_by = {
        str(b.get("sub_id") or "").strip(): b
        for b in briefs
        if isinstance(b, dict) and str(b.get("sub_id") or "").strip()
    }
    packs_by = {
        str(p.get("sub_id") or "").strip(): p
        for p in packs
        if isinstance(p, dict) and str(p.get("sub_id") or "").strip()
    }

    anchors_by: dict[str, list[dict[str, Any]]] = {}
    for rec in anchors:
        if not isinstance(rec, dict):
            continue
        sid = str(rec.get("sub_id") or "").strip()
        if not sid:
            continue
        items = rec.get("anchors") or []
        if isinstance(items, list):
            anchors_by[sid] = [a for a in items if isinstance(a, dict)]

    sub_ids = sorted(briefs_by.keys(), key=_sid_key)

    lines: list[str] = [
        "**Index Table 1. Subsection map (axes + representative works).**",
        "",
        "| Subsection | Axes | Representative works |",
        "|---|---|---|",
    ]

    wrote = 0
    for sid in sub_ids:
        brief = briefs_by.get(sid) or {}
        pack = packs_by.get(sid) or {}
        title = str(brief.get("title") or pack.get("title") or "").strip()

        axes_raw = [str(a).strip() for a in (brief.get("axes") or []) if str(a).strip()]
        axes = [_clean_axis(a) for a in axes_raw if _clean_axis(a)]

        cite_keys = [k for k in _collect_pack_citations(pack) if (not bib_keys) or (k in bib_keys)]
        cites = _format_cites(cite_keys[:5])

        lines.append(
            "| "
            + _truncate(f"{sid} {title}", 90).replace("|", " ")
            + " | "
            + ("<br>".join([_truncate(a, 72) for a in axes[:5]]) if axes else "—").replace("|", " ")
            + " | "
            + (cites or "—")
            + " |"
        )
        wrote += 1

    if wrote == 0:
        lines.append("| (no subsections) | — | — |")

    lines.extend(
        [
            "",
            "**Index Table 2. Concrete anchors (benchmarks / numbers / caveats).**",
            "",
            "| Subsection | Anchor facts | Representative works |",
            "|---|---|---|",
        ]
    )

    for sid in sub_ids:
        brief = briefs_by.get(sid) or {}
        pack = packs_by.get(sid) or {}
        title = str(brief.get("title") or pack.get("title") or "").strip()

        aitems = anchors_by.get(sid) or []
        prefer = [a for a in aitems if str(a.get("hook_type") or "").strip().lower() in {"quant", "eval"}]
        picked = prefer or aitems

        facts: list[str] = []
        cite_keys: list[str] = []
        for a in picked:
            txt = _clean_anchor_text(a.get("text") or "")
            if txt and txt not in facts:
                facts.append(txt)
            for k in a.get("citations") or []:
                k = str(k or "").strip()
                if not k:
                    continue
                if bib_keys and k not in bib_keys:
                    continue
                if k not in cite_keys:
                    cite_keys.append(k)
            if len(facts) >= 3:
                break

        facts_cell = "<br>".join([_truncate(t, 130) for t in facts[:3]]) if facts else "—"

        # If anchor sheet is empty for a subsection, fall back to pack citations so the row is still cite-backed.
        if not cite_keys:
            cite_keys = [k for k in _collect_pack_citations(pack) if (not bib_keys) or (k in bib_keys)]

        cites = _format_cites(cite_keys[:5])

        lines.append(
            "| "
            + _truncate(f"{sid} {title}", 90).replace("|", " ")
            + " | "
            + facts_cell.replace("|", " ")
            + " | "
            + (cites or "—")
            + " |"
        )

    out_text = "\n".join(lines).rstrip() + "\n"
    if _is_placeholder(out_text) or not _looks_refined(out_text):
        raise SystemExit("Generated tables look unrefined or contain placeholders")

    atomic_write_text(out_path, out_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
