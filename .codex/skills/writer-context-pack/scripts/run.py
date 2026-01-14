from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def _backup_existing(path: Path) -> None:
    from tooling.common import backup_existing

    backup_existing(path)


def _trim(text: str, *, max_len: int = 260) -> str:
    text = re.sub(r"\s+", " ", str(text or "").strip())
    if len(text) > int(max_len):
        text = text[: int(max_len)].rstrip() + "…"
    return text


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size <= 0:
        return []
    out: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _bib_keys(bib_path: Path) -> set[str]:
    text = bib_path.read_text(encoding="utf-8", errors="ignore") if bib_path.exists() else ""
    return set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", text))


def _iter_outline_subsections(outline: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(outline, list):
        return out
    for sec in outline:
        if not isinstance(sec, dict):
            continue
        sec_id = str(sec.get("id") or "").strip()
        sec_title = str(sec.get("title") or "").strip()
        for sub in sec.get("subsections") or []:
            if not isinstance(sub, dict):
                continue
            sub_id = str(sub.get("id") or "").strip()
            title = str(sub.get("title") or "").strip()
            if sec_id and sec_title and sub_id and title:
                out.append({"sub_id": sub_id, "title": title, "section_id": sec_id, "section_title": sec_title})
    return out


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

    from tooling.common import ensure_dir, load_yaml, now_iso_seconds, parse_semicolon_list, write_jsonl

    workspace = Path(args.workspace).resolve()

    inputs = parse_semicolon_list(args.inputs) or [
        "outline/outline.yml",
        "outline/subsection_briefs.jsonl",
        "outline/chapter_briefs.jsonl",
        "outline/evidence_drafts.jsonl",
        "outline/anchor_sheet.jsonl",
        "outline/evidence_bindings.jsonl",
        "citations/ref.bib",
    ]
    outputs = parse_semicolon_list(args.outputs) or ["outline/writer_context_packs.jsonl"]

    outline_path = workspace / inputs[0]
    briefs_path = workspace / inputs[1]
    chapter_path = workspace / inputs[2]
    packs_path = workspace / inputs[3]
    anchors_path = workspace / inputs[4]
    bindings_path = workspace / inputs[5]
    bib_path = workspace / inputs[6]

    out_path = workspace / (outputs[0] if outputs else "outline/writer_context_packs.jsonl")
    ensure_dir(out_path.parent)

    freeze_marker = out_path.parent / "writer_context_packs.refined.ok"
    if out_path.exists() and out_path.stat().st_size > 0 and freeze_marker.exists():
        return 0
    if out_path.exists() and out_path.stat().st_size > 0:
        _backup_existing(out_path)

    outline = load_yaml(outline_path) if outline_path.exists() else []
    subsections = _iter_outline_subsections(outline)
    if not subsections:
        raise SystemExit(f"No H3 subsections found in {outline_path}")

    bibkeys = _bib_keys(bib_path)

    briefs_by_sub: dict[str, dict[str, Any]] = {}
    for rec in _load_jsonl(briefs_path):
        sid = str(rec.get("sub_id") or "").strip()
        if sid:
            briefs_by_sub[sid] = rec

    chapters_by_sec: dict[str, dict[str, Any]] = {}
    for rec in _load_jsonl(chapter_path):
        sec_id = str(rec.get("section_id") or "").strip()
        if sec_id:
            chapters_by_sec[sec_id] = rec

    packs_by_sub: dict[str, dict[str, Any]] = {}
    for rec in _load_jsonl(packs_path):
        sid = str(rec.get("sub_id") or "").strip()
        if sid:
            packs_by_sub[sid] = rec

    anchors_by_sub: dict[str, list[dict[str, Any]]] = {}
    for rec in _load_jsonl(anchors_path):
        sid = str(rec.get("sub_id") or "").strip()
        anchors = rec.get("anchors") or []
        if sid and isinstance(anchors, list):
            anchors_by_sub[sid] = [a for a in anchors if isinstance(a, dict)]

    bindings_by_sub: dict[str, dict[str, Any]] = {}
    for rec in _load_jsonl(bindings_path):
        sid = str(rec.get("sub_id") or "").strip()
        if sid:
            bindings_by_sub[sid] = rec

    # Chapter-scoped union of mapped bibkeys.
    chapter_union: dict[str, set[str]] = {}
    for sub in subsections:
        sid = sub["sub_id"]
        sec_id = sub["section_id"]
        mapped = (bindings_by_sub.get(sid) or {}).get("mapped_bibkeys") or []
        if not isinstance(mapped, list):
            continue
        bucket = chapter_union.setdefault(sec_id, set())
        for bk in mapped:
            bk = str(bk).strip()
            if bk and (not bibkeys or bk in bibkeys):
                bucket.add(bk)

    records: list[dict[str, Any]] = []
    now = now_iso_seconds()

    for sub in subsections:
        sid = sub["sub_id"]
        title = sub["title"]
        sec_id = sub["section_id"]
        sec_title = sub["section_title"]

        brief = briefs_by_sub.get(sid) or {}
        pack = packs_by_sub.get(sid) or {}
        binding = bindings_by_sub.get(sid) or {}
        chapter = chapters_by_sec.get(sec_id) or {}

        rq = str(brief.get("rq") or "").strip()
        axes = [str(a).strip() for a in (brief.get("axes") or []) if str(a).strip()]
        paragraph_plan = brief.get("paragraph_plan") or []

        mapped = [str(x).strip() for x in (binding.get("mapped_bibkeys") or []) if str(x).strip()]
        selected = [str(x).strip() for x in (binding.get("bibkeys") or []) if str(x).strip()]
        mapped = [k for k in mapped if (not bibkeys or k in bibkeys)]
        selected = [k for k in selected if (not bibkeys or k in bibkeys)]

        anchors_raw = anchors_by_sub.get(sid) or []
        anchor_facts: list[dict[str, Any]] = []
        for a in anchors_raw[:12]:
            cites = [str(c).strip() for c in (a.get("citations") or []) if str(c).strip()]
            cites = [c for c in cites if c.startswith("@") and (not bibkeys or c[1:] in bibkeys)]
            if not cites:
                continue
            anchor_facts.append(
                {
                    "hook_type": str(a.get("hook_type") or "").strip(),
                    "text": _trim(a.get("text") or ""),
                    "citations": cites,
                    "paper_id": str(a.get("paper_id") or "").strip(),
                    "evidence_id": str(a.get("evidence_id") or "").strip(),
                    "pointer": str(a.get("pointer") or "").strip(),
                }
            )
            if len(anchor_facts) >= 8:
                break

        comparison_cards: list[dict[str, Any]] = []
        for comp in (pack.get("concrete_comparisons") or [])[:6]:
            if not isinstance(comp, dict):
                continue
            cites = [str(c).strip() for c in (comp.get("citations") or []) if str(c).strip()]
            cites = [c for c in cites if c.startswith("@") and (not bibkeys or c[1:] in bibkeys)]

            def _hl(side: str) -> list[dict[str, Any]]:
                out: list[dict[str, Any]] = []
                for hl in (comp.get(side) or [])[:2]:
                    if not isinstance(hl, dict):
                        continue
                    hcites = [str(c).strip() for c in (hl.get("citations") or []) if str(c).strip()]
                    hcites = [c for c in hcites if c.startswith("@") and (not bibkeys or c[1:] in bibkeys)]
                    if not hcites:
                        continue
                    out.append(
                        {
                            "paper_id": str(hl.get("paper_id") or "").strip(),
                            "evidence_id": str(hl.get("evidence_id") or "").strip(),
                            "excerpt": _trim(hl.get("excerpt") or "", max_len=220),
                            "citations": hcites,
                            "pointer": str(hl.get("pointer") or "").strip(),
                        }
                    )
                return out

            card = {
                "axis": str(comp.get("axis") or "").strip(),
                "A_label": str(comp.get("A_label") or "").strip(),
                "B_label": str(comp.get("B_label") or "").strip(),
                "citations": cites,
                "A_highlights": _hl("A_highlights"),
                "B_highlights": _hl("B_highlights"),
                "write_prompt": _trim(comp.get("write_prompt") or "", max_len=320),
            }
            if card["axis"] and (card["A_highlights"] or card["B_highlights"]):
                comparison_cards.append(card)
            if len(comparison_cards) >= 4:
                break

        eval_proto = []
        for it in (pack.get("evaluation_protocol") or [])[:6]:
            if not isinstance(it, dict):
                continue
            cites = [str(c).strip() for c in (it.get("citations") or []) if str(c).strip()]
            cites = [c for c in cites if c.startswith("@") and (not bibkeys or c[1:] in bibkeys)]
            if not cites:
                continue
            eval_proto.append({"bullet": _trim(it.get("bullet") or "", max_len=260), "citations": cites})

        lim_hooks = []
        for it in (pack.get("failures_limitations") or [])[:8]:
            if not isinstance(it, dict):
                continue
            cites = [str(c).strip() for c in (it.get("citations") or []) if str(c).strip()]
            cites = [c for c in cites if c.startswith("@") and (not bibkeys or c[1:] in bibkeys)]
            if not cites:
                continue
            # `evidence-draft` uses `bullet` (not `excerpt`) for failures/limitations.
            text = it.get("excerpt") or it.get("bullet") or it.get("text") or ""
            lim_hooks.append(
                {
                    "excerpt": _trim(text, max_len=260),
                    "citations": cites,
                    "pointer": str(it.get("pointer") or "").strip(),
                }
            )

        record = {
            "sub_id": sid,
            "title": title,
            "section_id": sec_id,
            "section_title": sec_title,
            "rq": rq,
            "axes": axes,
            "paragraph_plan": paragraph_plan,
            "chapter_throughline": chapter.get("throughline") or [],
            "chapter_key_contrasts": chapter.get("key_contrasts") or [],
            "allowed_bibkeys_selected": selected,
            "allowed_bibkeys_mapped": mapped,
            "allowed_bibkeys_chapter": sorted(chapter_union.get(sec_id, set())),
            "evidence_ids": [str(e).strip() for e in (binding.get("evidence_ids") or []) if str(e).strip()],
            "anchor_facts": anchor_facts,
            "comparison_cards": comparison_cards,
            "evaluation_protocol": eval_proto,
            "limitation_hooks": lim_hooks,
            "generated_at": now,
        }

        records.append(record)

    write_jsonl(out_path, records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
