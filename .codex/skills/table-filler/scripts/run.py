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
    return len(seps) >= 2 and "[@" in text and len(text.strip()) >= 800


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


def _clean_verify_field(v: str) -> str:
    v = re.sub(r"\s+", " ", (v or "").strip())
    v = v.rstrip(" .;:，；。")
    return v


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
        "citations/ref.bib",
    ]
    outputs = parse_semicolon_list(args.outputs) or ["outline/tables.md"]

    out_path = workspace / outputs[0]
    ensure_dir(out_path.parent)

    freeze_marker = out_path.with_name(f"{out_path.name}.refined.ok")
    if out_path.exists() and out_path.stat().st_size > 0:
        if freeze_marker.exists():
            return 0
        _backup_existing(out_path)

    briefs = read_jsonl(workspace / inputs[1]) if (workspace / inputs[1]).exists() else []
    bib_text = (workspace / inputs[3]).read_text(encoding="utf-8", errors="ignore") if (workspace / inputs[3]).exists() else ""
    bib_keys = set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text))

    packs = read_jsonl(workspace / inputs[2]) if (workspace / inputs[2]).exists() else []

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

    sub_ids = sorted(briefs_by.keys(), key=_sid_key)

    lines: list[str] = [
        "# Tables",
        "",
        "All tables are generated evidence-first from subsection briefs + evidence packs.",
        "",
        "## Table 1: Subsection comparison map (axes + representative works)",
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
        lines.append("| (no subsections) | - | - |")

    lines.extend(
        [
            "",
            "## Table 2: Evidence readiness + verification needs",
            "",
            "| Subsection | Evidence levels | Verify fields | Representative works |",
            "|---|---|---|---|",
        ]
    )

    for sid in sub_ids:
        brief = briefs_by.get(sid) or {}
        pack = packs_by.get(sid) or {}
        title = str(brief.get("title") or pack.get("title") or "").strip()

        ev = pack.get("evidence_level_summary") or {}
        if isinstance(ev, dict):
            ev_txt = ", ".join([f"{k}={int(ev.get(k) or 0)}" for k in ["fulltext", "abstract", "title"] if k in ev])
        else:
            ev_txt = ""

        verify = pack.get("verify_fields") or []
        verify_items = [_clean_verify_field(v) for v in verify if _clean_verify_field(v)]

        # Drop generic boilerplate if more specific fields exist.
        generic_prefixes = ("verify fine-grained", "validate with full", "abstract-level evidence")
        specific = [v for v in verify_items if not v.lower().startswith(generic_prefixes)]
        verify_items = specific or verify_items

        cite_keys = [k for k in _collect_pack_citations(pack) if (not bib_keys) or (k in bib_keys)]
        cites = _format_cites(cite_keys[:5])

        lines.append(
            "| "
            + _truncate(f"{sid} {title}", 90).replace("|", " ")
            + " | "
            + (ev_txt or "—")
            + " | "
            + ("<br>".join([_truncate(v, 80) for v in verify_items[:5]]) if verify_items else "—").replace("|", " ")
            + " | "
            + (cites or "—")
            + " |"
        )

    blocking: list[str] = []
    for sid in sub_ids:
        pack = packs_by.get(sid) or {}
        miss = pack.get("blocking_missing") or []
        if isinstance(miss, list) and any(str(x).strip() for x in miss):
            blocking.append(sid)
    if blocking:
        lines.extend(
            [
                "",
                "## Blocking evidence gaps (from evidence packs)",
                "",
                "- The following subsections are marked as `blocking_missing` and should stop drafting until evidence is enriched:",
            ]
        )
        for sid in blocking[:30]:
            lines.append(f"- {sid}")

    atomic_write_text(out_path, "\n".join(lines).rstrip() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
