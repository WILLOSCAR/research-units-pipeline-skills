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
    if "(placeholder)" in low:
        return True
    if "<!-- scaffold" in low:
        return True
    if "…" in text:
        return True
    if re.search(r"(?i)\b(?:todo|tbd|fixme)\b", low):
        return True
    return False


def _looks_refined(text: str) -> bool:
    if _is_placeholder(text):
        return False
    bullets = [ln for ln in text.splitlines() if ln.strip().startswith("- ")]
    return len(bullets) >= 12


def _pick_axis(axes: Any) -> str:
    if not isinstance(axes, list):
        return ""
    for a in axes:
        a = re.sub(r"\s+", " ", str(a or "").strip())
        if a and len(a) <= 56:
            return a
    return ""


def _transition_sentence(*, a_title: str, a_axis: str, b_title: str, b_axis: str) -> str:
    a_title = (a_title or "").strip()
    b_title = (b_title or "").strip()
    a_axis = (a_axis or "").strip()
    b_axis = (b_axis or "").strip()

    if a_axis and b_axis and a_axis != b_axis:
        return (
            f"After grounding the discussion in **{a_title}** (especially along *{a_axis}*), "
            f"we next turn to **{b_title}**, shifting emphasis toward *{b_axis}*."
        )
    if a_axis:
        return f"Building on **{a_title}** (key axis: *{a_axis}*), we now move to **{b_title}** to extend the comparison."
    return f"With **{a_title}** in place, we now move to **{b_title}** to continue the survey’s argument chain."


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

    from tooling.common import atomic_write_text, ensure_dir, load_yaml, parse_semicolon_list, read_jsonl

    workspace = Path(args.workspace).resolve()
    inputs = parse_semicolon_list(args.inputs) or ["outline/outline.yml", "outline/subsection_briefs.jsonl"]
    outputs = parse_semicolon_list(args.outputs) or ["outline/transitions.md"]

    out_path = workspace / outputs[0]
    ensure_dir(out_path.parent)

    if out_path.exists() and out_path.stat().st_size > 0:
        existing = out_path.read_text(encoding="utf-8", errors="ignore")
        if _looks_refined(existing):
            return 0

    outline = load_yaml(workspace / inputs[0]) if (workspace / inputs[0]).exists() else []
    briefs = read_jsonl(workspace / inputs[1]) if (workspace / inputs[1]).exists() else []
    briefs_by = {
        str(b.get("sub_id") or "").strip(): b
        for b in briefs
        if isinstance(b, dict) and str(b.get("sub_id") or "").strip()
    }

    sections: list[dict[str, Any]] = []
    if isinstance(outline, list):
        for section in outline:
            if not isinstance(section, dict):
                continue
            stitle = str(section.get("title") or "").strip()
            subs: list[dict[str, str]] = []
            for sub in section.get("subsections") or []:
                if not isinstance(sub, dict):
                    continue
                sid = str(sub.get("id") or "").strip()
                title = str(sub.get("title") or "").strip()
                if sid and title:
                    subs.append({"id": sid, "title": title})
            if stitle and subs:
                sections.append({"title": stitle, "subsections": subs})

    lines: list[str] = [
        "# Transitions (to weave into the draft)",
        "",
        "- Guardrail: transitions add no new facts and introduce no new citations.",
        "",
        "## Within-section (H3 → next H3)",
    ]

    wrote = 0
    for sec in sections:
        subs = sec.get("subsections") or []
        if not isinstance(subs, list) or len(subs) < 2:
            continue
        for i in range(len(subs) - 1):
            a = subs[i]
            b = subs[i + 1]
            a_id = str(a.get("id") or "").strip()
            b_id = str(b.get("id") or "").strip()
            a_title = str(a.get("title") or "").strip()
            b_title = str(b.get("title") or "").strip()
            a_axis = _pick_axis((briefs_by.get(a_id) or {}).get("axes"))
            b_axis = _pick_axis((briefs_by.get(b_id) or {}).get("axes"))
            sent = _transition_sentence(a_title=a_title, a_axis=a_axis, b_title=b_title, b_axis=b_axis)
            lines.append(f"- {a_id} → {b_id}: {sent}")
            wrote += 1

    if wrote == 0:
        lines.append("- (none generated; outline missing or has single-subsection sections)")

    lines.extend(["", "## Between sections (H2 → next H2)", ""])

    for i in range(len(sections) - 1):
        a = sections[i]
        b = sections[i + 1]
        a_title = str(a.get("title") or "").strip()
        b_title = str(b.get("title") or "").strip()
        if not a_title or not b_title:
            continue
        sent = f"Having covered **{a_title}**, we now broaden to **{b_title}** to connect the taxonomy end-to-end."
        lines.append(f"- {a_title} → {b_title}: {sent}")

    atomic_write_text(out_path, "\n".join(lines).rstrip() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
