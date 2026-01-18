from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


def _sha1_text(text: str) -> str:
    return hashlib.sha1((text or "").encode("utf-8", errors="ignore")).hexdigest()


def _slug_unit_id(unit_id: str) -> str:
    raw = str(unit_id or "").strip()
    out: list[str] = []
    for ch in raw:
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    safe = "".join(out).strip("_")
    return f"S{safe}" if safe else "S"


def _extract_citation_keys(text: str) -> list[str]:
    cited: set[str] = set()
    for m in re.finditer(r"\[@([^\]]+)\]", text or ""):
        inside = (m.group(1) or "").strip()
        for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
            if k:
                cited.add(k)
    return sorted(cited)


def _iter_outline_units(outline: Any) -> list[dict[str, str]]:
    units: list[dict[str, str]] = []
    if not isinstance(outline, list):
        return units

    for sec in outline:
        if not isinstance(sec, dict):
            continue
        sec_id = str(sec.get("id") or "").strip()
        sec_title = str(sec.get("title") or "").strip()
        subs = sec.get("subsections") or []
        if subs and isinstance(subs, list):
            for sub in subs:
                if not isinstance(sub, dict):
                    continue
                sub_id = str(sub.get("id") or "").strip()
                sub_title = str(sub.get("title") or "").strip()
                if sub_id and sub_title:
                    units.append(
                        {
                            "kind": "h3",
                            "id": sub_id,
                            "title": sub_title,
                            "section_id": sec_id,
                            "section_title": sec_title,
                        }
                    )
        else:
            if sec_id and sec_title:
                units.append(
                    {
                        "kind": "h2",
                        "id": sec_id,
                        "title": sec_title,
                        "section_id": sec_id,
                        "section_title": sec_title,
                    }
                )
    return units


def _iter_h2_leads(outline: Any) -> list[dict[str, str]]:
    leads: list[dict[str, str]] = []
    if not isinstance(outline, list):
        return leads
    for sec in outline:
        if not isinstance(sec, dict):
            continue
        sec_id = str(sec.get("id") or "").strip()
        sec_title = str(sec.get("title") or "").strip()
        subs = sec.get("subsections") or []
        if sec_id and sec_title and subs and isinstance(subs, list):
            leads.append({"kind": "h2_lead", "id": sec_id, "title": sec_title})
    return leads


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

    from tooling.common import (
        atomic_write_text,
        decisions_has_approval,
        ensure_dir,
        load_yaml,
        now_iso_seconds,
        parse_semicolon_list,
        upsert_checkpoint_block,
    )
    from tooling.quality_gate import check_unit_outputs, write_quality_report, _global_citation_min_subsections

    workspace = Path(args.workspace).resolve()
    unit_id = str(args.unit_id or "U100").strip() or "U100"

    inputs = parse_semicolon_list(args.inputs)
    outputs = parse_semicolon_list(args.outputs) or ["sections/sections_manifest.jsonl"]

    out_rel = outputs[0] if outputs else "sections/sections_manifest.jsonl"
    out_path = workspace / out_rel
    ensure_dir(out_path.parent)

    # Approval gate (survey policy): prose after C2.
    decisions_rel = "DECISIONS.md"
    for rel in inputs:
        if str(rel or "").strip().endswith("DECISIONS.md"):
            decisions_rel = str(rel).strip()
            break
    decisions_path = workspace / decisions_rel
    if not decisions_has_approval(decisions_path, "C2"):
        block = "\n".join(
            [
                "## C5 section writing request",
                "",
                "- This unit writes prose into per-section files under `sections/`.",
                "- Please tick `Approve C2` (scope + outline) in the approvals checklist above.",
                "- Then rerun this unit.",
                "",
            ]
        )
        upsert_checkpoint_block(decisions_path, "C5", block)
        return 2

    outline_rel = "outline/outline.yml"
    for rel in inputs:
        rel = str(rel or "").strip()
        if rel.endswith("outline/outline.yml") or rel.endswith("outline.yml"):
            outline_rel = rel
            break

    outline = load_yaml(workspace / outline_rel) if (workspace / outline_rel).exists() else []
    units = _iter_outline_units(outline)
    leads = _iter_h2_leads(outline)

    sections_dir = out_path.parent

    # Helpful writer context (deterministic): per-H3 allowed citations + anchor facts.
    bindings_by_sub: dict[str, dict[str, Any]] = {}
    bindings_path = workspace / "outline" / "evidence_bindings.jsonl"
    if bindings_path.exists() and bindings_path.stat().st_size > 0:
        for raw in bindings_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except Exception:
                continue
            if not isinstance(rec, dict):
                continue
            sid = str(rec.get("sub_id") or "").strip()
            if sid:
                bindings_by_sub[sid] = rec

    anchors_by_sub: dict[str, list[dict[str, Any]]] = {}
    anchors_path = workspace / "outline" / "anchor_sheet.jsonl"
    if anchors_path.exists() and anchors_path.stat().st_size > 0:
        for raw in anchors_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except Exception:
                continue
            if not isinstance(rec, dict):
                continue
            sid = str(rec.get("sub_id") or "").strip()
            anchors = rec.get("anchors") or []
            if not sid or not isinstance(anchors, list):
                continue
            out: list[dict[str, Any]] = []
            for a in anchors:
                if not isinstance(a, dict):
                    continue
                out.append(
                    {
                        "hook_type": str(a.get("hook_type") or "").strip(),
                        "text": str(a.get("text") or "").strip(),
                        "citations": [str(x).strip() for x in (a.get("citations") or []) if str(x).strip()],
                        "paper_id": str(a.get("paper_id") or "").strip(),
                        "evidence_id": str(a.get("evidence_id") or "").strip(),
                        "pointer": str(a.get("pointer") or "").strip(),
                    }
                )
            anchors_by_sub[sid] = out


    # Globally allowed citations (cross-cutting): mapped across multiple subsections.
    mapped_counts: dict[str, int] = {}
    for rec in bindings_by_sub.values():
        mapped = rec.get("mapped_bibkeys") or []
        if not isinstance(mapped, list):
            continue
        for bk in mapped:
            bk = str(bk).strip()
            if bk:
                mapped_counts[bk] = mapped_counts.get(bk, 0) + 1
    global_threshold = _global_citation_min_subsections(workspace)
    allowed_global = sorted([k for k, n in mapped_counts.items() if n >= int(global_threshold)])


    # Chapter-scoped allowed citations: union of mapped bibkeys across sibling H3s in the same H2 section.
    # This provides flexibility while still keeping citations chapter-bounded.
    allowed_by_section: dict[str, set[str]] = {}
    for u in units:
        if str(u.get("kind") or "").strip() != "h3":
            continue
        sub_id = str(u.get("id") or "").strip()
        sec_id = str(u.get("section_id") or "").strip()
        if not sub_id or not sec_id:
            continue
        binding = bindings_by_sub.get(sub_id) or {}
        mapped = binding.get("mapped_bibkeys") or []
        if not isinstance(mapped, list):
            continue
        bucket = allowed_by_section.setdefault(sec_id, set())
        for bk in mapped:
            bk = str(bk).strip()
            if bk:
                bucket.add(bk)


    global_files = [
        {
            "kind": "global",
            "id": "abstract",
            "title": "Abstract",
            "path": str((sections_dir / "abstract.md").relative_to(workspace)),
        },
        {
            "kind": "global",
            "id": "discussion",
            "title": "Discussion",
            "path": str((sections_dir / "discussion.md").relative_to(workspace)),
        },
        {
            "kind": "global",
            "id": "conclusion",
            "title": "Conclusion",
            "path": str((sections_dir / "conclusion.md").relative_to(workspace)),
        },
    ]

    records: list[dict[str, Any]] = []
    generated_at = now_iso_seconds()

    def _add_record(rec: dict[str, Any]) -> None:
        p = workspace / str(rec.get("path") or "")
        exists = p.exists() and p.is_file() and p.stat().st_size > 0
        rec["exists"] = bool(exists)
        if exists:
            text = p.read_text(encoding="utf-8", errors="ignore")
            rec["sha1"] = _sha1_text(text)
            rec["bytes"] = int(p.stat().st_size)
            rec["citations"] = _extract_citation_keys(text)
        records.append(rec)

    for gf in global_files:
        _add_record({**gf, "generated_at": generated_at})

    for lead in leads:
        sid = str(lead.get("id") or "").strip()
        if not sid:
            continue
        rel = (sections_dir / f"{_slug_unit_id(sid)}_lead.md").relative_to(workspace)
        _add_record(
            {
                "kind": "h2_lead",
                "id": sid,
                "title": lead.get("title"),
                "section_id": sid,
                "section_title": lead.get("title"),
                "path": str(rel),
                "generated_at": generated_at,
            }
        )

    for u in units:
        uid = str(u.get("id") or "").strip()
        rel = (sections_dir / f"{_slug_unit_id(uid)}.md").relative_to(workspace)

        rec: dict[str, Any] = {
            "kind": u.get("kind"),
            "id": uid,
            "title": u.get("title"),
            "section_id": u.get("section_id"),
            "section_title": u.get("section_title"),
            "path": str(rel),
        }

        if rec.get("kind") == "h3":
            binding = bindings_by_sub.get(uid) or {}
            if isinstance(binding, dict) and binding:
                mapped = binding.get("mapped_bibkeys") or []
                selected = binding.get("bibkeys") or []
                evidence_ids = binding.get("evidence_ids") or []
                if isinstance(mapped, list):
                    rec["allowed_bibkeys_mapped"] = sorted({str(x).strip() for x in mapped if str(x).strip()})
                if isinstance(selected, list):
                    rec["allowed_bibkeys_selected"] = sorted({str(x).strip() for x in selected if str(x).strip()})
                if isinstance(evidence_ids, list):
                    rec["evidence_ids"] = [str(x).strip() for x in evidence_ids if str(x).strip()]

            anchors = anchors_by_sub.get(uid) or []
            if isinstance(anchors, list) and anchors:
                rec["anchor_facts"] = anchors

            sec_id = str(rec.get("section_id") or "").strip()
            if sec_id and allowed_by_section.get(sec_id):
                rec["allowed_bibkeys_chapter"] = sorted(allowed_by_section.get(sec_id) or set())

            if allowed_global:
                rec["allowed_bibkeys_global"] = allowed_global

        _add_record({**rec, "generated_at": generated_at})

    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    atomic_write_text(out_path, "\n".join(lines).rstrip() + "\n")

    issues: list[Any] = []

    for prereq_skill, prereq_outs in [
        ("outline-builder", [outline_rel]),
        ("subsection-briefs", ["outline/subsection_briefs.jsonl"]),
        ("chapter-briefs", ["outline/chapter_briefs.jsonl"]),
        ("evidence-draft", ["outline/evidence_drafts.jsonl"]),
        ("anchor-sheet", ["outline/anchor_sheet.jsonl"]),
        ("writer-context-pack", ["outline/writer_context_packs.jsonl"]),
        ("citation-verifier", ["citations/ref.bib"]),
        ("evidence-binder", ["outline/evidence_bindings.jsonl"]),
    ]:
        issues.extend(check_unit_outputs(skill=prereq_skill, workspace=workspace, outputs=prereq_outs))

    issues.extend(check_unit_outputs(skill="subsection-writer", workspace=workspace, outputs=[out_rel]))

    if issues:
        write_quality_report(workspace=workspace, unit_id=unit_id, skill="subsection-writer", issues=issues)
        return 2

    # Avoid confusing stale QUALITY_GATE.md after a successful run.
    report_path = workspace / "output" / "QUALITY_GATE.md"
    if report_path.exists():
        write_quality_report(workspace=workspace, unit_id=unit_id, skill="subsection-writer", issues=[])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
