from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


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


def _sub_sort_key(sub_id: str) -> tuple:
    parts = []
    for p in str(sub_id or "").split("."):
        p = p.strip()
        if p.isdigit():
            parts.append(int(p))
        else:
            # Keep deterministic ordering for odd ids.
            m = re.findall(r"\d+|\D+", p)
            for tok in m:
                if tok.isdigit():
                    parts.append(int(tok))
                else:
                    parts.append(tok)
    return tuple(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--checkpoint", default="")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve()
    for _ in range(10):
        if (repo_root / "AGENTS.md").exists():
            break
        parent = repo_root.parent
        if parent == repo_root:
            break
        repo_root = parent
    sys.path.insert(0, str(repo_root))

    from tooling.common import atomic_write_text, ensure_dir, now_iso_seconds, parse_semicolon_list

    workspace = Path(args.workspace).resolve()

    inputs = parse_semicolon_list(args.inputs) or [
        "outline/subsection_briefs.jsonl",
        "outline/evidence_bindings.jsonl",
        "outline/evidence_drafts.jsonl",
        "outline/anchor_sheet.jsonl",
    ]
    outputs = parse_semicolon_list(args.outputs) or ["output/EVIDENCE_SELFLOOP_TODO.md"]

    briefs_path = workspace / inputs[0]
    bindings_path = workspace / inputs[1]
    drafts_path = workspace / inputs[2]
    anchors_path = workspace / inputs[3]

    out_path = workspace / (outputs[0] if outputs else "output/EVIDENCE_SELFLOOP_TODO.md")
    ensure_dir(out_path.parent)

    missing_inputs: list[str] = []
    for p in [briefs_path, bindings_path, drafts_path]:
        if not p.exists() or p.stat().st_size <= 0:
            missing_inputs.append(str(p.relative_to(workspace)))

    briefs = _load_jsonl(briefs_path)
    briefs_by_sub: dict[str, dict[str, Any]] = {}
    for rec in briefs:
        sid = str(rec.get("sub_id") or "").strip()
        if sid:
            briefs_by_sub[sid] = rec

    bindings = _load_jsonl(bindings_path)
    binds_by_sub: dict[str, dict[str, Any]] = {}
    for rec in bindings:
        sid = str(rec.get("sub_id") or "").strip()
        if sid:
            binds_by_sub[sid] = rec

    drafts = _load_jsonl(drafts_path)
    drafts_by_sub: dict[str, dict[str, Any]] = {}
    for rec in drafts:
        sid = str(rec.get("sub_id") or "").strip()
        if sid:
            drafts_by_sub[sid] = rec

    anchors_by_sub: dict[str, list[dict[str, Any]]] = {}
    for rec in _load_jsonl(anchors_path):
        sid = str(rec.get("sub_id") or "").strip()
        anchors = rec.get("anchors") or []
        if sid and isinstance(anchors, list):
            anchors_by_sub[sid] = [a for a in anchors if isinstance(a, dict)]

    # Aggregate per-subsection issues.
    items: list[dict[str, Any]] = []

    blocking_subs: list[str] = []
    gap_subs: list[str] = []

    common_blocking: dict[str, int] = {}
    common_gaps: dict[str, int] = {}

    smell_subs: list[str] = []
    common_smells: dict[str, int] = {}

    all_subs = sorted(set(briefs_by_sub) | set(binds_by_sub) | set(drafts_by_sub), key=_sub_sort_key)

    for sid in all_subs:
        brief = briefs_by_sub.get(sid) or {}
        bind = binds_by_sub.get(sid) or {}
        pack = drafts_by_sub.get(sid) or {}

        title = str(brief.get("title") or bind.get("title") or pack.get("title") or "").strip()

        binding_gaps = bind.get("binding_gaps") or []
        if not isinstance(binding_gaps, list):
            binding_gaps = []
        binding_gaps = [str(x).strip() for x in binding_gaps if str(x).strip()]

        blocking_missing = pack.get("blocking_missing") or []
        if not isinstance(blocking_missing, list):
            blocking_missing = []
        blocking_missing = [str(x).strip() for x in blocking_missing if str(x).strip()]

        # Lightweight richness signals (non-blocking, but useful to route work).
        comparisons = pack.get("concrete_comparisons") or []
        comp_n = len([c for c in comparisons if isinstance(c, dict)]) if isinstance(comparisons, list) else 0

        eval_proto = pack.get("evaluation_protocol") or []
        eval_n = len([e for e in eval_proto if str(e).strip() or isinstance(e, dict)]) if isinstance(eval_proto, list) else 0

        lims = pack.get("failures_limitations") or []
        lim_n = len([l for l in lims if (isinstance(l, dict) and str(l.get("bullet") or "").strip()) or (isinstance(l, str) and l.strip())]) if isinstance(lims, list) else 0

        snippets = pack.get("evidence_snippets") or []
        snip_n = len([s for s in snippets if isinstance(s, dict) and str(s.get("text") or "").strip()]) if isinstance(snippets, list) else 0

        anchor_n = len([a for a in (anchors_by_sub.get(sid) or []) if str(a.get("text") or "").strip()])

        smells: list[str] = []
        if comp_n < 3:
            smells.append(f"comparisons_low({comp_n})")
        if eval_n == 0:
            smells.append("missing_eval_protocol")
        if lim_n == 0:
            smells.append("missing_limitations")
        if anchor_n == 0:
            smells.append("missing_anchors")
        if snip_n == 0:
            smells.append("missing_snippets")
        if smells:
            smell_subs.append(sid)
            for s in smells:
                common_smells[s] = common_smells.get(s, 0) + 1

        if blocking_missing:
            blocking_subs.append(sid)
            for m in blocking_missing:
                common_blocking[m] = common_blocking.get(m, 0) + 1

        if binding_gaps:
            gap_subs.append(sid)
            for g in binding_gaps:
                common_gaps[g] = common_gaps.get(g, 0) + 1

        items.append(
            {
                "sub_id": sid,
                "title": title,
                "binding_gaps": binding_gaps,
                "blocking_missing": blocking_missing,
                "writability_smells": smells,
                "signals": {
                    "snippets": snip_n,
                    "comparisons": comp_n,
                    "eval_protocol": eval_n,
                    "limitations": lim_n,
                    "anchors": anchor_n,
                },
            }
        )

    status = "PASS"
    if missing_inputs:
        status = "FAIL"
    elif blocking_subs:
        status = "FAIL"
    elif gap_subs:
        status = "OK"

    now = now_iso_seconds()

    def _top_counts(d: dict[str, int], *, limit: int = 8) -> list[tuple[str, int]]:
        return sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[: int(limit)]

    lines: list[str] = []
    lines.append("# Evidence self-loop TODO")
    lines.append("")
    lines.append(f"- Generated at: `{now}`")
    lines.append(f"- Status: {status}")
    lines.append("")

    if missing_inputs:
        lines.append("## A. Missing inputs (hard block)")
        lines.append("")
        for rel in missing_inputs:
            lines.append(f"- `{rel}`")
        lines.append("")
        lines.append("Fix: run the upstream C3/C4 units to generate these artifacts before attempting evidence self-loop routing.")
        lines.append("")

    lines.append("## B. Summary")
    lines.append("")
    lines.append(f"- Subsections seen: {len(items)}")
    lines.append(f"- Packs with `blocking_missing`: {len(blocking_subs)}")
    lines.append(f"- Subsections with `binding_gaps`: {len(gap_subs)}")
    lines.append(f"- Subsections with writability smells (non-blocking): {len(smell_subs)}")

    if common_blocking:
        lines.append("")
        lines.append("Top `blocking_missing` reasons:")
        for reason, n in _top_counts(common_blocking):
            lines.append(f"- {n}× {reason}")

    if common_gaps:
        lines.append("")
        lines.append("Top `binding_gaps` fields:")
        for g, n in _top_counts(common_gaps):
            lines.append(f"- {n}× {g}")

    if common_smells:
        lines.append("")
        lines.append("Top writability smells (non-blocking):")
        for s, n in _top_counts(common_smells):
            lines.append(f"- {n}× {s}")

    lines.append("")

    lines.append("## C. Per-subsection TODO (smallest upstream fix path)")
    lines.append("")

    if not items:
        lines.append("- (no subsections found; check that briefs/bindings/packs were generated)")
    else:
        for it in items:
            sid = it["sub_id"]
            title = it.get("title") or ""
            gaps = it.get("binding_gaps") or []
            block = it.get("blocking_missing") or []
            smells = it.get("writability_smells") or []
            sig = it.get("signals") or {}

            if status == "PASS":
                # On PASS, still surface non-blocking smells that predict hollow prose.
                if not smells:
                    continue
            else:
                # On FAIL/OK, focus the loop on explicit gaps/blocks.
                if not (gaps or block):
                    continue

            lines.append(f"### {sid} {title}".rstrip())
            lines.append("")
            lines.append(
                "- Signals: "
                f"snippets={sig.get('snippets')} "
                f"comparisons={sig.get('comparisons')} "
                f"eval={sig.get('eval_protocol')} "
                f"limitations={sig.get('limitations')} "
                f"anchors={sig.get('anchors')}"
            )

            if block:
                lines.append("- blocking_missing:")
                for m in block[:8]:
                    lines.append(f"  - {m}")

            if gaps:
                lines.append("- binding_gaps:")
                for g in gaps:
                    lines.append(f"  - {g}")

            if smells:
                lines.append("- writability_smells (non-blocking):")
                for s in smells[:8]:
                    lines.append(f"  - {s}")

            # Minimal fix routing (skill-level, not code-level).
            fix_steps: list[str] = []

            joined = " ".join(block).lower()
            if "no usable citation" in joined or "bibkey" in joined:
                fix_steps.append("C4: fix `papers/paper_notes.jsonl` bibkeys → rerun `citation-verifier` (then regenerate binder/packs)")
            if "title-only" in joined or "no evidence snippets" in joined:
                fix_steps.append("C3: enrich evidence: `pdf-text-extractor` (fulltext where possible) → rerun `paper-notes` (then regenerate binder/packs)")
            if "evaluation tokens" in joined or "benchmark" in joined or "metrics" in joined:
                fix_steps.append("C3: extract evaluation anchors into notes/bank (benchmarks/metrics/budgets) → rerun `paper-notes`/`evidence_bank` then `evidence-draft`")
            if "too few concrete comparisons" in joined:
                fix_steps.append("C3: strengthen `outline/subsection_briefs.jsonl` clusters (ensure 2–3 distinct clusters with enough papers) → rerun `evidence-draft`")

            if gaps:
                fix_steps.append("C4: address `binding_gaps`: enrich evidence bank tags for mapped papers OR expand `outline/mapping.tsv` coverage OR relax `required_evidence_fields` if unrealistic")

            if smells:
                if any("missing_eval_protocol" == s for s in smells):
                    fix_steps.append("C3: extract evaluation anchors (task/metric/constraint) into notes/bank → rerun `paper-notes` then regenerate packs")
                if any("missing_anchors" == s for s in smells):
                    fix_steps.append("C4: improve anchor density: rerun `anchor-sheet` after strengthening packs (anchors should cite specific evidence)")
                if any(s.startswith("comparisons_low") for s in smells):
                    fix_steps.append("C3: increase contrastability: refine clusters/axes in `subsection-briefs` → rerun `evidence-draft`")
                if any("missing_limitations" == s for s in smells):
                    fix_steps.append("C3: extract limitations/failure modes into notes/packs → rerun `paper-notes` / `evidence-draft`")
                if any("missing_snippets" == s for s in smells):
                    fix_steps.append("C3: enrich evidence snippets: prefer fulltext (`pdf-text-extractor`) and rerun `paper-notes` / `evidence-draft`")

            if not fix_steps:
                if block:
                    fix_steps.append("C3/C4: treat `blocking_missing` as STOP; enrich notes/evidence bank or adjust scope, then regenerate `evidence-binder` → `evidence-draft`")
                else:
                    fix_steps.append("C4: review `binding_gaps` and decide: enrich notes/bank, expand mapping, or adjust required fields")

            lines.append("- Suggested fix path:")
            for s in fix_steps:
                lines.append(f"  - {s}")

            lines.append("")

    if status == "PASS":
        lines.append("## D. Next action")
        lines.append("")
        lines.append("- Evidence looks writeable. Proceed to C5 writing (and keep the evidence policy disclaimer once in front matter).")
        lines.append("- If section C lists writability smells, consider fixing them now; they often predict hollow prose even when packs are schema-valid.")
    elif status == "OK":
        lines.append("## D. Next action")
        lines.append("")
        lines.append("- You can draft, but expect weaker specificity where `binding_gaps` appears.")
        lines.append("- Prefer fixing the listed gaps before spending time polishing prose.")
    else:
        lines.append("## D. Next action")
        lines.append("")
        lines.append("- Evidence is not yet writeable (FAIL). Fix upstream first; do not write filler prose.")

    atomic_write_text(out_path, "\n".join(lines).rstrip() + "\n")
    return 0 if status in {"PASS", "OK"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
