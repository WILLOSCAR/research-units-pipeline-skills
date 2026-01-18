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


def _trim(text: str, *, max_len: int = 400) -> str:
    """Normalize whitespace and trim without adding ellipsis (avoid leakage into prose)."""

    text = re.sub(r"\s+", " ", str(text or "").strip())
    max_len = int(max_len)
    if len(text) <= max_len:
        return text

    cut = text[:max_len].rstrip()
    # Avoid cutting a token in half.
    tail = cut[-60:]
    if " " in tail:
        cut = cut.rsplit(" ", 1)[0].rstrip()
    return cut


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


def _draft_profile(workspace: Path) -> str:
    """Best-effort parse from `queries.md` (lite|survey|deep)."""

    path = workspace / "queries.md"
    if not path.exists():
        return "survey"
    keys = {"draft_profile", "writing_profile", "quality_profile"}
    try:
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("- ") or ":" not in line:
                continue
            key, value = line[2:].split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            if key not in keys:
                continue
            value = value.split("#", 1)[0].strip().strip('"').strip("'").strip().lower()
            if value in {"lite", "survey", "deep"}:
                return value
            return "survey"
    except Exception:
        return "survey"
    return "survey"


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
    from tooling.quality_gate import _global_citation_min_subsections

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

    # Global bibkeys: mapped across multiple subsections (cross-cutting foundations/benchmarks/surveys).
    mapped_counts: dict[str, int] = {}
    for rec in bindings_by_sub.values():
        mapped = rec.get("mapped_bibkeys") or []
        if not isinstance(mapped, list):
            continue
        for bk in mapped:
            bk = str(bk).strip()
            if not bk:
                continue
            if bibkeys and bk not in bibkeys:
                continue
            mapped_counts[bk] = mapped_counts.get(bk, 0) + 1
    global_threshold = _global_citation_min_subsections(workspace)
    mapped_global = sorted([k for k, n in mapped_counts.items() if n >= int(global_threshold)])

    # Trim policy (avoid silent truncation; keep long enough to preserve concrete detail).
    TRIM = {
        "default": 400,
        "anchor_fact": 420,
        "highlight_excerpt": 280,
        "comparison_write_prompt": 420,
        "eval_bullet": 320,
        "limitation_excerpt": 320,
    }

    # Anti-template hints for C5 writers (keep paper prose; avoid “outline narration”).
    DO_NOT_REPEAT = [
        "This subsection surveys",
        "This subsection argues",
        "In this subsection",
        "Next, we move from",
        "We now turn to",
        "this run",
        "this run is",
        "claims remain provisional under abstract-only evidence",
        "abstract-only evidence",
        "Key takeaway:",
        "Main takeaway:",
    ]

    records: list[dict[str, Any]] = []
    now = now_iso_seconds()
    draft_profile = _draft_profile(workspace)

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
        thesis = str(brief.get("thesis") or "").strip()
        axes = [str(a).strip() for a in (brief.get("axes") or []) if str(a).strip()]
        paragraph_plan = brief.get("paragraph_plan") or []

        mapped = [str(x).strip() for x in (binding.get("mapped_bibkeys") or []) if str(x).strip()]
        selected = [str(x).strip() for x in (binding.get("bibkeys") or []) if str(x).strip()]
        mapped = [k for k in mapped if (not bibkeys or k in bibkeys)]
        selected = [k for k in selected if (not bibkeys or k in bibkeys)]

        # Anchor facts (evidence hooks).
        anchors_raw = anchors_by_sub.get(sid) or []
        anchor_facts: list[dict[str, Any]] = []
        anchors_considered = 0
        anchors_dropped_no_cites = 0

        raw_limit = 16
        keep_limit = 12 if draft_profile == "deep" else 8

        for a in anchors_raw[:raw_limit]:
            anchors_considered += 1
            cites = [str(c).strip() for c in (a.get("citations") or []) if str(c).strip()]
            cites = [c for c in cites if c.startswith("@") and (not bibkeys or c[1:] in bibkeys)]
            if not cites:
                anchors_dropped_no_cites += 1
                continue

            anchor_facts.append(
                {
                    "hook_type": str(a.get("hook_type") or "").strip(),
                    "text": _trim(a.get("text") or "", max_len=TRIM["anchor_fact"]),
                    "citations": cites,
                    "paper_id": str(a.get("paper_id") or "").strip(),
                    "evidence_id": str(a.get("evidence_id") or "").strip(),
                    "pointer": str(a.get("pointer") or "").strip(),
                }
            )

            if len(anchor_facts) >= keep_limit:
                break

        # Comparison cards (A-vs-B contrasts).
        raw_comparisons = pack.get("concrete_comparisons") or []
        comparisons_considered = 0
        comparisons_dropped_no_highlights = 0
        hl_dropped_no_cites = 0

        comparison_cards: list[dict[str, Any]] = []
        comp_raw_limit = 10
        comp_keep_limit = 6 if draft_profile == "deep" else 4

        for comp in (raw_comparisons or [])[:comp_raw_limit]:
            if not isinstance(comp, dict):
                continue
            comparisons_considered += 1

            cites = [str(c).strip() for c in (comp.get("citations") or []) if str(c).strip()]
            cites = [c for c in cites if c.startswith("@") and (not bibkeys or c[1:] in bibkeys)]

            def _hl(side: str) -> list[dict[str, Any]]:
                nonlocal hl_dropped_no_cites
                out: list[dict[str, Any]] = []
                for hl in (comp.get(side) or [])[:3]:
                    if not isinstance(hl, dict):
                        continue
                    hcites = [str(c).strip() for c in (hl.get("citations") or []) if str(c).strip()]
                    hcites = [c for c in hcites if c.startswith("@") and (not bibkeys or c[1:] in bibkeys)]
                    if not hcites:
                        hl_dropped_no_cites += 1
                        continue
                    out.append(
                        {
                            "paper_id": str(hl.get("paper_id") or "").strip(),
                            "evidence_id": str(hl.get("evidence_id") or "").strip(),
                            "excerpt": _trim(hl.get("excerpt") or "", max_len=TRIM["highlight_excerpt"]),
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
                "write_prompt": _trim(comp.get("write_prompt") or "", max_len=TRIM["comparison_write_prompt"]),
            }
            if card["axis"] and (card["A_highlights"] or card["B_highlights"]):
                comparison_cards.append(card)
            else:
                comparisons_dropped_no_highlights += 1

            if len(comparison_cards) >= comp_keep_limit:
                break

        # Evaluation protocol bullets.
        raw_eval = pack.get("evaluation_protocol") or []
        eval_considered = 0
        eval_dropped_no_cites = 0

        eval_proto: list[dict[str, Any]] = []
        for it in (raw_eval or [])[:10]:
            if not isinstance(it, dict):
                continue
            eval_considered += 1
            cites = [str(c).strip() for c in (it.get("citations") or []) if str(c).strip()]
            cites = [c for c in cites if c.startswith("@") and (not bibkeys or c[1:] in bibkeys)]
            if not cites:
                eval_dropped_no_cites += 1
                continue
            eval_proto.append({"bullet": _trim(it.get("bullet") or "", max_len=TRIM["eval_bullet"]), "citations": cites})
            if len(eval_proto) >= 8:
                break

        # Failure/limitation hooks.
        raw_lim = pack.get("failures_limitations") or []
        lim_considered = 0
        lim_dropped_no_cites = 0

        lim_hooks: list[dict[str, Any]] = []
        for it in (raw_lim or [])[:14]:
            if not isinstance(it, dict):
                continue
            lim_considered += 1
            cites = [str(c).strip() for c in (it.get("citations") or []) if str(c).strip()]
            cites = [c for c in cites if c.startswith("@") and (not bibkeys or c[1:] in bibkeys)]
            if not cites:
                lim_dropped_no_cites += 1
                continue
            # `evidence-draft` uses `bullet` (not `excerpt`) for failures/limitations.
            text = it.get("excerpt") or it.get("bullet") or it.get("text") or ""
            lim_hooks.append(
                {
                    "excerpt": _trim(text, max_len=TRIM["limitation_excerpt"]),
                    "citations": cites,
                    "pointer": str(it.get("pointer") or "").strip(),
                }
            )
            if len(lim_hooks) >= (10 if draft_profile == "deep" else 8):
                break

        # Explicit must-use minima: make the writer contract executable (and debuggable).
        if draft_profile == "deep":
            min_anchor = 3
            min_comp = 3
            min_lim = 2
        elif draft_profile == "lite":
            min_anchor = 1
            min_comp = 1
            min_lim = 1
        else:
            min_anchor = 2
            min_comp = 2
            min_lim = 1

        must_use = {
            "min_anchor_facts": min_anchor,
            "min_comparison_cards": min_comp,
            "min_limitation_hooks": min_lim,
            "require_cited_numeric_if_available": True,
            "require_multi_cite_synthesis_paragraph": True,
            "thesis_required": True,
        }

        pack_warnings: list[str] = []
        if not thesis:
            pack_warnings.append(
                "Missing `thesis` in subsection briefs; fix `subsection-briefs` so the writer has a central claim to execute."
            )
        if len(anchor_facts) < min_anchor:
            pack_warnings.append(
                "Too few anchor facts after trimming; strengthen `anchor-sheet` or upstream evidence packs to avoid generic prose."
            )
        if len(comparison_cards) < min_comp:
            pack_warnings.append(
                "Too few comparison cards after trimming; strengthen `evidence-draft` (excerpt-level A-vs-B contrasts) to avoid per-paper summaries."
            )
        if len(eval_proto) < 1:
            pack_warnings.append(
                "Missing evaluation protocol bullets; strengthen `evidence-draft` so the writer can anchor comparisons to benchmarks/metrics."
            )
        if len(lim_hooks) < min_lim:
            pack_warnings.append(
                "Too few limitation hooks; strengthen `evidence-draft` so limitations are concrete (not generic future work)."
            )

        if anchors_considered and anchors_dropped_no_cites / max(1, anchors_considered) >= 0.5:
            pack_warnings.append(
                "Many anchor facts were dropped due to missing citations; ensure `anchor-sheet` records citations for each anchor."
            )

        pack_stats = {
            "anchors": {
                "raw": len(anchors_raw),
                "considered": anchors_considered,
                "kept": len(anchor_facts),
                "dropped_no_cites": anchors_dropped_no_cites,
            },
            "comparisons": {
                "raw": len([c for c in (raw_comparisons or []) if isinstance(c, dict)]),
                "considered": comparisons_considered,
                "kept": len(comparison_cards),
                "dropped_no_highlights": comparisons_dropped_no_highlights,
                "highlights_dropped_no_cites": hl_dropped_no_cites,
            },
            "evaluation_protocol": {
                "raw": len([e for e in (raw_eval or []) if isinstance(e, dict)]),
                "considered": eval_considered,
                "kept": len(eval_proto),
                "dropped_no_cites": eval_dropped_no_cites,
            },
            "limitation_hooks": {
                "raw": len([l for l in (raw_lim or []) if isinstance(l, dict)]),
                "considered": lim_considered,
                "kept": len(lim_hooks),
                "dropped_no_cites": lim_dropped_no_cites,
            },
            "trim_policy": TRIM,
        }

        record = {
            "sub_id": sid,
            "title": title,
            "section_id": sec_id,
            "section_title": sec_title,
            "rq": rq,
            "thesis": thesis,
            "axes": axes,
            # Transition handles (NO NEW FACTS): carried from subsection briefs so writers
            # can keep connectors specific without leaking outline meta into the final draft.
            "bridge_terms": [str(x).strip() for x in (brief.get("bridge_terms") or []) if str(x).strip()],
            "contrast_hook": str(brief.get("contrast_hook") or "").strip(),
            "required_evidence_fields": [str(x).strip() for x in (brief.get("required_evidence_fields") or []) if str(x).strip()],
            "paragraph_plan": paragraph_plan,
            "chapter_throughline": chapter.get("throughline") or [],
            "chapter_key_contrasts": chapter.get("key_contrasts") or [],
            "chapter_synthesis_mode": str(chapter.get("synthesis_mode") or "").strip(),
            "allowed_bibkeys_selected": selected,
            "allowed_bibkeys_mapped": mapped,
            "allowed_bibkeys_chapter": sorted(chapter_union.get(sec_id, set())),
            "allowed_bibkeys_global": mapped_global,
            "evidence_ids": [str(e).strip() for e in (binding.get("evidence_ids") or []) if str(e).strip()],
            "anchor_facts": anchor_facts,
            "comparison_cards": comparison_cards,
            "evaluation_protocol": eval_proto,
            "limitation_hooks": lim_hooks,
            "must_use": must_use,
            "do_not_repeat_phrases": DO_NOT_REPEAT,
            "pack_warnings": pack_warnings,
            "pack_stats": pack_stats,
            "generated_at": now,
        }

        records.append(record)

    write_jsonl(out_path, records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
