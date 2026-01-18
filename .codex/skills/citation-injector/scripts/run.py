from __future__ import annotations

import argparse
import hashlib
import json
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


def _stable_choice(key: str, options: list[str]) -> str:
    if not options:
        return ""
    digest = hashlib.sha1((key or "").encode("utf-8", errors="ignore")).hexdigest()
    return options[int(digest[:8], 16) % len(options)]


def _parse_budget_report(md: str) -> tuple[int, int, dict[str, list[str]]]:
    """Return (target, gap, suggestions[sub_id] -> keys)."""

    target = 0
    gap = 0
    suggestions: dict[str, list[str]] = {}

    m = re.search(r"(?im)^\s*-\s*Global target.*>=\s*(\d+)\s*$", md or "")
    if m:
        target = int(m.group(1))
    m = re.search(r"(?im)^\s*-\s*Gap:\s*(\d+)\s*$", md or "")
    if m:
        gap = int(m.group(1))

    for raw in (md or "").splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        if line.startswith("|---"):
            continue
        if "| suggested keys" in line.lower():
            continue
        # | 4.1 | Title | ... | `K1`, `K2` |
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 6:
            continue
        sub_id = cols[0].strip()
        sug = cols[5].strip()
        if not sub_id or not sug or sug == "(none)":
            continue
        keys = [k.strip() for k in re.findall(r"`([^`]+)`", sug) if k.strip()]
        if keys:
            suggestions[sub_id] = keys

    return target, gap, suggestions


def _parse_outline(outline: Any) -> tuple[list[str], dict[str, str]]:
    """Return (sub_ids_in_order, title_norm->sub_id)."""

    order: list[str] = []
    title_to_sid: dict[str, str] = {}
    if not isinstance(outline, list):
        return order, title_to_sid
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
            order.append(sid)
            title_to_sid[_norm_title(title)] = sid
    return order, title_to_sid


def _bib_first_author_last(bib_text: str) -> dict[str, str]:
    """Best-effort bib parser for 'FirstAuthor et al.' handles."""

    authors: dict[str, str] = {}

    cur_key = ""
    cur_lines: list[str] = []

    def flush() -> None:
        nonlocal cur_key, cur_lines
        if not cur_key:
            cur_lines = []
            return
        blob = "\n".join(cur_lines)
        m = re.search(r"(?is)\bauthor\s*=\s*[{\"]([^}\"]+)[}\"]", blob)
        if m:
            raw = re.sub(r"\s+", " ", (m.group(1) or "").strip())
            first = raw.split(" and ", 1)[0].strip()
            if "," in first:
                last = first.split(",", 1)[0].strip()
            else:
                parts = [p for p in first.split(" ") if p]
                last = parts[-1] if parts else ""
            last = re.sub(r"[^A-Za-z\\-]", "", last)
            if last:
                authors[cur_key] = last
        cur_key = ""
        cur_lines = []

    for raw in (bib_text or "").splitlines():
        line = raw.rstrip("\n")
        if line.lstrip().startswith("@"):
            flush()
            m = re.search(r"@\w+\s*\{\s*([^,\s]+)\s*,", line)
            cur_key = (m.group(1) if m else "").strip()
            cur_lines = [line]
            continue
        if cur_key:
            cur_lines.append(line)
    flush()
    return authors


def _format_injection_para(*, sub_id: str, context: str, keys: list[str], authors: dict[str, str]) -> str:
    # Keep this evidence-neutral (NO NEW FACTS) while avoiding repeated 'representative works include' stems.
    ctx = re.sub(r"\s+", " ", (context or "").strip())

    if ctx:
        variants = [
            f"Concrete examples in {ctx} include",
            f"Work on {ctx} includes",
            f"Recent systems for {ctx} include",
            f"Examples that illustrate {ctx} include",
            f"Representative systems for {ctx} include",
        ]
    else:
        variants = [
            "Concrete systems include",
            "Work in this area includes",
            "Recent systems include",
            "Examples include",
            "Representative systems include",
        ]

    prefix = _stable_choice(f"inject:{sub_id}:{ctx}", variants) or (variants[0] if variants else "Examples include")

    mentions: list[str] = []
    for k in keys:
        last = authors.get(k, "").strip()
        if last:
            mentions.append(f"{last} et al. [@{k}]")
        else:
            mentions.append(f"the cited work [@{k}]")

    if not mentions:
        return ""
    if len(mentions) == 1:
        return f"{prefix} {mentions[0]}."
    if len(mentions) == 2:
        return f"{prefix} {mentions[0]} and {mentions[1]}."
    return f"{prefix} {', '.join(mentions[:-1])}, and {mentions[-1]}."


def _inject(
    draft: str, *, title_to_sid: dict[str, str], plan: dict[str, list[str]], authors: dict[str, str], context_by_sid: dict[str, str]
) -> tuple[str, dict[str, list[str]]]:
    used_global = set(_extract_cites(draft))
    injected: dict[str, list[str]] = {}

    lines = (draft or "").splitlines()
    out: list[str] = []

    cur_sid = ""
    cur_context = ""
    cur_keys: list[str] = []
    inserted = False
    in_para = False
    para_count = 0

    def pick_keys(sid: str) -> list[str]:
        want = plan.get(sid) or []
        chosen: list[str] = []
        for k in want:
            if k in used_global:
                continue
            if k in chosen:
                continue
            chosen.append(k)
            if len(chosen) >= 6:
                break
        return chosen

    def maybe_insert_end() -> None:
        nonlocal inserted
        if not cur_sid or inserted or not cur_keys:
            return
        para = _format_injection_para(sub_id=cur_sid, context=cur_context, keys=cur_keys, authors=authors)
        if not para:
            return
        if out and out[-1].strip():
            out.append("")
        out.append(para)
        out.append("")
        injected[cur_sid] = list(cur_keys)
        for k in cur_keys:
            used_global.add(k)
        inserted = True

    for raw in lines:
        if raw.startswith("### ") or raw.startswith("## "):
            # Leaving an H3 block: if we never hit a paragraph boundary, inject at end.
            maybe_insert_end()
            # Reset state on any heading.
            cur_sid = ""
            cur_context = ""
            cur_keys = []
            inserted = False
            in_para = False
            para_count = 0

        if raw.startswith("### "):
            title = raw[4:].strip()
            sid = title_to_sid.get(_norm_title(title), "")
            cur_sid = sid
            cur_context = (context_by_sid.get(sid) or title).strip()
            cur_keys = pick_keys(sid) if sid else []
            inserted = False
            in_para = False
            para_count = 0
            out.append(raw)
            continue

        if cur_sid and cur_keys and not inserted:
            if raw.strip():
                if not in_para:
                    para_count += 1
                    in_para = True
            else:
                # Blank line ends a paragraph.
                if in_para:
                    in_para = False
                    if para_count == 1:
                        # Insert right after paragraph 1.
                        out.append("")
                        para = _format_injection_para(sub_id=cur_sid, context=cur_context, keys=cur_keys, authors=authors)
                        if para:
                            out.append(para)
                            out.append("")
                            injected[cur_sid] = list(cur_keys)
                            for k in cur_keys:
                                used_global.add(k)
                        inserted = True
                        continue

        out.append(raw)

    maybe_insert_end()
    return "\n".join(out).rstrip() + "\n", injected


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

    from tooling.common import atomic_write_text, load_yaml, now_iso_seconds, parse_semicolon_list
    from tooling.quality_gate import _draft_profile, _pipeline_profile

    workspace = Path(args.workspace).resolve()

    inputs = parse_semicolon_list(args.inputs) or [
        "output/DRAFT.md",
        "output/CITATION_BUDGET_REPORT.md",
        "outline/outline.yml",
        "citations/ref.bib",
    ]
    outputs = parse_semicolon_list(args.outputs) or [
        "output/DRAFT.md",
        "output/CITATION_INJECTION_REPORT.md",
    ]

    draft_rel = next((p for p in inputs if p.endswith("DRAFT.md")), "output/DRAFT.md")
    budget_rel = next((p for p in inputs if p.endswith("CITATION_BUDGET_REPORT.md")), "output/CITATION_BUDGET_REPORT.md")
    outline_rel = next((p for p in inputs if p.endswith("outline.yml")), "outline/outline.yml")
    bib_rel = next((p for p in inputs if p.endswith("ref.bib")), "citations/ref.bib")

    out_draft_rel = next((p for p in outputs if p.endswith("DRAFT.md")), "output/DRAFT.md")
    out_report_rel = next((p for p in outputs if p.endswith("CITATION_INJECTION_REPORT.md")), "output/CITATION_INJECTION_REPORT.md")

    draft_path = workspace / draft_rel
    budget_path = workspace / budget_rel
    outline_path = workspace / outline_rel
    bib_path = workspace / bib_rel

    problems: list[str] = []
    if not draft_path.exists() or draft_path.stat().st_size == 0:
        problems.append(f"missing `{draft_rel}`")
    if not budget_path.exists() or budget_path.stat().st_size == 0:
        problems.append(f"missing `{budget_rel}`")
    if not outline_path.exists() or outline_path.stat().st_size == 0:
        problems.append(f"missing `{outline_rel}`")
    if not bib_path.exists() or bib_path.stat().st_size == 0:
        problems.append(f"missing `{bib_rel}`")

    if problems:
        report = "\n".join(
            [
                "# Citation injection report",
                "",
                f"- Generated at: {now_iso_seconds()}",
                "- Status: FAIL",
                "- Reason:",
                *[f"  - {p}" for p in problems],
                "",
            ]
        )
        atomic_write_text(workspace / out_report_rel, report)
        return 0

    draft = draft_path.read_text(encoding="utf-8", errors="ignore")
    budget = budget_path.read_text(encoding="utf-8", errors="ignore")
    target, gap, plan = _parse_budget_report(budget)

    outline = load_yaml(outline_path) if outline_path.exists() else []
    _, title_to_sid = _parse_outline(outline)

    bib_text = bib_path.read_text(encoding="utf-8", errors="ignore")
    authors = _bib_first_author_last(bib_text)

    # Best-effort subsection context handles (keeps injected sentences more specific and less repetitive).
    context_by_sid: dict[str, str] = {}
    wcp_path = workspace / "outline" / "writer_context_packs.jsonl"
    if wcp_path.exists() and wcp_path.stat().st_size > 0:
        for raw in wcp_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if not isinstance(rec, dict):
                continue
            sid = str(rec.get("sub_id") or "").strip()
            if not sid:
                continue
            hook = str(rec.get("contrast_hook") or "").strip()
            title = str(rec.get("title") or "").strip()
            if hook:
                context_by_sid[sid] = hook
            elif title:
                context_by_sid[sid] = title

    before = len(set(_extract_cites(draft)))

    # Decide whether injection is needed using the same target logic as the budget report.
    profile = _pipeline_profile(workspace)
    draft_profile = _draft_profile(workspace)

    status = "PASS"
    injected: dict[str, list[str]] = {}
    after = before

    if profile == "arxiv-survey" and int(target) > 0 and int(gap) > 0:
        new_draft, injected = _inject(draft, title_to_sid=title_to_sid, plan=plan, authors=authors, context_by_sid=context_by_sid)
        atomic_write_text(workspace / out_draft_rel, new_draft)
        after = len(set(_extract_cites(new_draft)))
        if after < int(target):
            status = "FAIL"
    else:
        # No-op when there is no gap (or no target).
        atomic_write_text(workspace / out_draft_rel, draft.rstrip() + "\n")

    lines: list[str] = [
        "# Citation injection report",
        "",
        f"- Generated at: {now_iso_seconds()}",
        f"- Status: {status}",
        f"- Draft: `{draft_rel}`",
        f"- Draft profile: `{draft_profile}`",
        f"- Unique citations before: {before}",
        f"- Unique citations after: {after}",
    ]
    if target:
        lines.append(f"- Target (pipeline-auditor): >= {target}")
        lines.append(f"- Gap (from budget report): {gap}")
    lines.append("")

    if injected:
        lines.extend(
            [
                "## Per-H3 injections",
                "",
                "| H3 | added | keys |",
                "|---|---:|---|",
            ]
        )
        for sid in sorted(injected.keys()):
            keys = injected.get(sid) or []
            keys_s = ", ".join([f"`{k}`" for k in keys]) if keys else "(none)"
            lines.append(f"| {sid} | {len(keys)} | {keys_s} |")
        lines.append("")
    else:
        lines.append("- No injections applied (no gap, or no in-scope unused keys).")
        lines.append("")

    if status != "PASS":
        lines.extend(
            [
                "## Next actions (skills-first)",
                "",
                "- If the draft still fails the unique-citation target, go upstream:",
                "  - C1: increase candidate pool/core set (`literature-engineer` / `dedupe-rank`)",
                "  - C2: improve mapping coverage (`section-mapper`) so each H3 has a larger in-scope citation pool",
                "  - C4: regenerate packs (`writer-context-pack`) so the budget report has more usable keys per H3",
                "",
            ]
        )

    atomic_write_text(workspace / out_report_rel, "\n".join(lines).rstrip() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
