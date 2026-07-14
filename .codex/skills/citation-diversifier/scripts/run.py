from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path
from typing import Any


def _norm_title(x: str) -> str:
    x = re.sub(r"\s+", " ", (x or "").strip()).lower()
    x = re.sub(r"[^a-z0-9]+", " ", x).strip()
    return x


def _extract_cites(text: str) -> list[str]:
    keys: list[str] = []
    for m in re.finditer(r"\[@([^\]]+)\]", text or ""):
        inside = (m.group(1) or "").strip()
        for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
            if k and k not in keys:
                keys.append(k)
    return keys


def _split_h3_chunks(md: str) -> list[tuple[str, str]]:
    """Parse H3 chunks from a merged draft.

    Treat new H2 headings as boundaries so later global sections/tables don't get
    attributed to the previous H3.
    """

    chunks: list[tuple[str, str]] = []
    cur_title = ""
    cur_lines: list[str] = []
    for raw in (md or "").splitlines():
        if raw.startswith("### "):
            if cur_title:
                chunks.append((cur_title, "\n".join(cur_lines).strip()))
            cur_title = raw[4:].strip()
            cur_lines = []
            continue
        if raw.startswith("## "):
            if cur_title:
                chunks.append((cur_title, "\n".join(cur_lines).strip()))
            cur_title = ""
            cur_lines = []
            continue
        if cur_title:
            cur_lines.append(raw)
    if cur_title:
        chunks.append((cur_title, "\n".join(cur_lines).strip()))
    return chunks


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

    from tooling.common import atomic_write_text, load_yaml, parse_semicolon_list, read_jsonl
    from tooling.quality_gate import _citation_target, _draft_profile, _pipeline_profile, survey_citation_policy

    workspace = Path(args.workspace).resolve()

    inputs = parse_semicolon_list(args.inputs) or [
        "output/DRAFT.md",
        "outline/outline.yml",
        "outline/writer_context_packs.jsonl",
        "citations/ref.bib",
    ]
    outputs = parse_semicolon_list(args.outputs) or ["output/CITATION_BUDGET_REPORT.md"]

    draft_rel = next((p for p in inputs if p.endswith("DRAFT.md")), "output/DRAFT.md")
    outline_rel = next((p for p in inputs if p.endswith("outline.yml")), "outline/outline.yml")
    packs_rel = next((p for p in inputs if p.endswith("writer_context_packs.jsonl")), "outline/writer_context_packs.jsonl")
    bib_rel = next((p for p in inputs if p.endswith("ref.bib")), "citations/ref.bib")

    out_rel = outputs[0] if outputs else "output/CITATION_BUDGET_REPORT.md"
    out_path = workspace / out_rel

    draft_path = workspace / draft_rel
    outline_path = workspace / outline_rel
    packs_path = workspace / packs_rel
    bib_path = workspace / bib_rel

    problems: list[str] = []
    if not draft_path.exists() or draft_path.stat().st_size == 0:
        problems.append(f"missing `{draft_rel}`")
    if not outline_path.exists() or outline_path.stat().st_size == 0:
        problems.append(f"missing `{outline_rel}`")
    if not packs_path.exists() or packs_path.stat().st_size == 0:
        problems.append(f"missing `{packs_rel}`")
    if not bib_path.exists() or bib_path.stat().st_size == 0:
        problems.append(f"missing `{bib_rel}`")

    if problems:
        report = "\n".join(
            [
                "# Citation budget report",
                "",
                "- Status: FAIL",
                "- Reason:",
                *[f"  - {p}" for p in problems],
                "",
            ]
        )
        atomic_write_text(out_path, report)
        return 2

    draft = draft_path.read_text(encoding="utf-8", errors="ignore")
    outline = load_yaml(outline_path) if outline_path.exists() else []
    packs = [r for r in read_jsonl(packs_path) if isinstance(r, dict)]

    bib_text = bib_path.read_text(encoding="utf-8", errors="ignore")
    bib_keys = set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", bib_text))

    packs_by_sub: dict[str, dict[str, Any]] = {}
    for rec in packs:
        sid = str(rec.get("sub_id") or "").strip()
        if sid:
            packs_by_sub[sid] = rec

    # Outline order + title mapping.
    outline_order: list[str] = []
    title_to_sid: dict[str, str] = {}
    sid_to_title: dict[str, str] = {}
    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            for sub in sec.get("subsections") or []:
                if not isinstance(sub, dict):
                    continue
                sid = str(sub.get("id") or "").strip()
                title = str(sub.get("title") or "").strip()
                if not sid or not title:
                    continue
                outline_order.append(sid)
                title_to_sid[_norm_title(title)] = sid
                sid_to_title[sid] = title

    # Citations used in draft by H3.
    found: dict[str, set[str]] = {}
    unknown_h3: list[str] = []
    for h3_title, body in _split_h3_chunks(draft):
        sid = title_to_sid.get(_norm_title(h3_title))
        if not sid:
            unknown_h3.append(h3_title)
            continue
        found[sid] = set(_extract_cites(body))

    used_global = set(_extract_cites(draft))

    profile = _pipeline_profile(workspace)
    draft_profile = _draft_profile(workspace)
    citation_target = _citation_target(workspace)

    # Resolve one profile-aware budget shared with the final pipeline audit.
    min_unique_hard = 0
    min_unique_rec = 0
    min_unique_struct = 0
    min_unique_frac = 0
    recommended_fraction = 0.0
    if profile == "arxiv-survey" and outline_order and bib_keys:
        h3_n = len(set(outline_order))
        policy = survey_citation_policy(workspace, bibliography_size=len(bib_keys), h3_count=h3_n)
        min_unique_hard = int(policy["hard"])
        min_unique_rec = int(policy["recommended"])
        min_unique_struct = int(policy["structural"])
        min_unique_frac = int(policy["bibliography_target"])
        recommended_fraction = float(policy["recommended_fraction"])

    gap_hard = max(0, int(min_unique_hard) - len(used_global)) if min_unique_hard else 0
    gap_rec = max(0, int(min_unique_rec) - len(used_global)) if min_unique_rec else 0

    target_policy = min_unique_hard
    gap_policy = gap_hard
    if citation_target == "recommended" and min_unique_rec:
        target_policy = min_unique_rec
        gap_policy = gap_rec

    # Size the per-H3 budget against the *policy target* so the report can be used
    # as an execution contract (not just a diagnostic).
    desired_gap = gap_policy

    # Dynamic per-H3 suggestion size so the budget can actually close the gap.
    h3_n = max(1, len(set(outline_order))) if outline_order else 1
    budget_per_h3 = 0
    if desired_gap > 0:
        budget_per_h3 = int(math.ceil(desired_gap / h3_n))
        if draft_profile == "course_paper":
            budget_per_h3 = max(3, min(6, budget_per_h3))
        else:
            budget_per_h3 = max(6, min(12, budget_per_h3))

    # Suggest per-H3 unused keys (prefer selected -> mapped -> chapter).
    rows: list[dict[str, Any]] = []
    suggested_anywhere: set[str] = set()
    for sid in outline_order:
        pack = packs_by_sub.get(sid) or {}
        title = str(pack.get("title") or sid_to_title.get(sid) or sid).strip()
        used_h3 = found.get(sid, set())

        sel = [str(k).strip() for k in (pack.get("allowed_bibkeys_selected") or []) if str(k).strip()]
        mapped = [str(k).strip() for k in (pack.get("allowed_bibkeys_mapped") or []) if str(k).strip()]
        chapter = [str(k).strip() for k in (pack.get("allowed_bibkeys_chapter") or []) if str(k).strip()]

        glob = [str(k).strip() for k in (pack.get("allowed_bibkeys_global") or []) if str(k).strip()]


        def _cands(keys: list[str]) -> list[str]:
            out: list[str] = []
            for k in keys:
                if bib_keys and k not in bib_keys:
                    continue
                if k in used_global:
                    continue
                if k in out:
                    continue
                out.append(k)
            return out

        cand_sel = _cands(sel)
        cand_map = _cands([k for k in mapped if k not in cand_sel])
        cand_ch = _cands([k for k in chapter if k not in cand_sel and k not in cand_map])
        cand_glob = _cands([k for k in glob if k not in cand_sel and k not in cand_map and k not in cand_ch])

        suggest: list[str] = []
        want = budget_per_h3 or 6

        # Prefer globally-unused AND budget-unique keys first (maximize global unique lift).
        for pool in (cand_sel, cand_map, cand_ch, cand_glob):
            for k in pool:
                if k in suggested_anywhere:
                    continue
                suggest.append(k)
                suggested_anywhere.add(k)
                if len(suggest) >= want:
                    break
            if len(suggest) >= want:
                break

        # If the local pool is too small, allow repeats across subsections as a last resort
        # (still globally-unused in the draft).
        if len(suggest) < want:
            for pool in (cand_sel, cand_map, cand_ch, cand_glob):
                for k in pool:
                    if k in suggest:
                        continue
                    suggest.append(k)
                    if len(suggest) >= want:
                        break
                if len(suggest) >= want:
                    break

        rows.append(
            {
                "sub_id": sid,
                "title": title,
                "unique_cites_in_h3": len(used_h3),
                "unused_global_in_selected": len(cand_sel),
                "unused_global_in_mapped": len(cand_map),
                "suggest_keys": suggest,
            }
        )

    status = "PASS" if gap_policy <= 0 else "FAIL"

    lines: list[str] = [
        "# Citation budget report",
        "",
        f"- Status: {status}",
        f"- Draft: `{draft_rel}`",
        f"- Bib entries: {len(bib_keys)}",
        f"- Draft unique citations: {len(used_global)}",
        f"- Draft profile: `{draft_profile}`",
        f"- Citation target policy: `{citation_target}`",
        "",
    ]

    # Canonical, parseable lines for downstream validators (citation-injector):
    # - `Global target ... >= N` (policy target; blocking)
    # - `Gap: X` (gap-to-target; blocking)
    if min_unique_hard or min_unique_rec:
        hard_details = f"(struct={min_unique_struct}, hard_frac={min_unique_frac}, bib={len(bib_keys)})"
        lines.append(f"- Global target (policy; blocking): >= {target_policy} {hard_details}")
        lines.append(f"- Gap: {gap_policy}")

        # Preserve both numbers for transparency/debugging.
        lines.append(f"- Global hard minimum: >= {min_unique_hard} {hard_details}")
        if min_unique_rec and min_unique_rec >= min_unique_hard:
            rec_frac = int(len(bib_keys) * recommended_fraction)
            lines.append(f"- Global recommended target: >= {min_unique_rec} (rec_frac={rec_frac}, bib={len(bib_keys)})")
            lines.append(f"- Gap to recommended: {gap_rec}")
        if budget_per_h3:
            lines.append(f"- Suggested keys per H3 (sizing): {budget_per_h3}")
        lines.append("")

    if unknown_h3:
        lines.append("## Unmatched H3 headings")
        lines.extend([f"- {t}" for t in unknown_h3[:12]])
        lines.append("")

    lines.append("## Per-H3 suggestions (unused global keys, in-scope)")
    lines.append("")
    add_hint = "add 3-6" if not budget_per_h3 else f"add {max(3, min(6, budget_per_h3))}-{budget_per_h3}"
    lines.append(f"| H3 | title | unique cites | unused in selected | unused in mapped | suggested keys ({add_hint}) |")
    lines.append("|---|---|---:|---:|---:|---|")

    for r in rows:
        sug = ", ".join([f"`{k}`" for k in (r["suggest_keys"] or [])]) or "(none)"
        lines.append(
            f"| {r['sub_id']} | {r['title']} | {r['unique_cites_in_h3']} | {r['unused_global_in_selected']} | {r['unused_global_in_mapped']} | {sug} |"
        )

    lines.extend(
        [
            "",
            "## How to apply (NO NEW FACTS)",
            "",
            "- Prefer cite-embedding edits that do not change claims (paraphrase; avoid repeated stems):",
            "  - Axis-anchored exemplars: `... as seen in X [@a] and Y [@b] ...; Z [@c] illustrates a contrasting design point.`",
            "  - Parenthetical grounding (low risk): `... (e.g., X [@a], Y [@b], Z [@c]).`",
            "  - Contrast pointer: `While some systems emphasize <A> (X [@a]; Y [@b]), others emphasize <B> (Z [@c]).`",
            "- Avoid budget-dump voice (high-signal automation tells): `Representative systems include ...`, `Notable lines of work include ...`.",
            "- Keep additions inside the same H3 (no cross-subsection citation drift).",
            "- Apply via `citation-injector` (LLM-first) and then rerun: `draft-polisher` → `global-reviewer` → `pipeline-auditor`.",
        ]
    )

    atomic_write_text(out_path, "\n".join(lines).rstrip() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
