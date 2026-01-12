from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def _stable_choice(key: str, options: list[str]) -> str:
    if not options:
        return ""
    digest = hashlib.sha1((key or "").encode("utf-8", errors="ignore")).hexdigest()
    idx = int(digest[:8], 16) % len(options)
    return options[idx]


def _load_subsection_briefs(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
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
        if sid:
            out[sid] = rec
    return out


def _iter_outline_boundaries(outline: Any) -> dict[str, list[tuple[str, str]]]:
    """Return adjacency boundaries for transition generation.

    Keys:
      - within_h3: (sub_id -> next_sub_id) pairs within the same H2.
      - h2_openers: (section_title -> first_sub_id) openers per H2.
      - h2_closers: (last_sub_id -> next_section_title) handoffs between H2s.
      - between_h2: (section_title -> next_section_title) pairs.
    """

    out: dict[str, list[tuple[str, str]]] = {"within_h3": [], "h2_openers": [], "h2_closers": [], "between_h2": []}

    if not isinstance(outline, list):
        return out

    sections: list[dict[str, Any]] = []
    for sec in outline:
        if isinstance(sec, dict):
            sections.append(sec)

    for i, sec in enumerate(sections):
        sec_title = str(sec.get("title") or "").strip()
        subs = sec.get("subsections") or []
        sub_ids: list[str] = []
        if isinstance(subs, list):
            for sub in subs:
                if not isinstance(sub, dict):
                    continue
                sid = str(sub.get("id") or "").strip()
                if sid:
                    sub_ids.append(sid)

        if sec_title and sub_ids:
            out["h2_openers"].append((sec_title, sub_ids[0]))

        for a, b in zip(sub_ids, sub_ids[1:]):
            out["within_h3"].append((a, b))

        if i < len(sections) - 1:
            next_title = str(sections[i + 1].get("title") or "").strip()
            if sec_title and next_title:
                out["between_h2"].append((sec_title, next_title))
            if sub_ids and next_title:
                out["h2_closers"].append((sub_ids[-1], next_title))

    return out


def _short_list(items: Any, *, limit: int = 4) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for x in items:
        s = str(x or "").strip()
        if not s:
            continue
        if s not in out:
            out.append(s)
        if len(out) >= int(limit):
            break
    return out


def _h3_transition(*, a_id: str, b_id: str, briefs: dict[str, dict[str, Any]]) -> str:
    a = briefs.get(a_id) or {}
    b = briefs.get(b_id) or {}

    a_title = str(a.get("title") or a_id).strip()
    b_title = str(b.get("title") or b_id).strip()

    b_bridge = ", ".join(_short_list(b.get("bridge_terms"), limit=3))
    b_hook = str(b.get("contrast_hook") or "").strip()

    b_focus = b_bridge or b_hook or "the next comparison handles"

    variants = [
        f"With “{a_title}” establishing the framing, “{b_title}” zooms into {b_focus} so later comparisons stay operational and checkable.",
        f"Building on “{a_title}”, we turn to “{b_title}” and make the next contrast concrete via {b_focus}.",
        f"After “{a_title}”, “{b_title}” shifts from setup to {b_focus}, tightening the link between mechanisms and evaluation.",
        f"To keep the narrative continuous, “{b_title}” follows “{a_title}” by focusing on {b_focus} and what it enables or constrains downstream.",
    ]
    sent = _stable_choice(f"h3:{a_id}->{b_id}", variants)
    return f"- {a_id} → {b_id}: {sent}"


def _h2_opener(*, sec_title: str, first_sub_id: str, briefs: dict[str, dict[str, Any]]) -> str:
    b = briefs.get(first_sub_id) or {}
    b_title = str(b.get("title") or first_sub_id).strip()

    b_bridge = ", ".join(_short_list(b.get("bridge_terms"), limit=3))
    b_hook = str(b.get("contrast_hook") or "").strip()

    b_focus = b_bridge or b_hook or "shared comparison handles"

    variants = [
        f"We open “{sec_title}” with “{b_title}” to set shared terms and the comparison handles ({b_focus}) reused across the section.",
        f"“{sec_title}” starts at “{b_title}”, turning the theme into concrete handles ({b_focus}) that later subsections can vary and test.",
        f"To ground “{sec_title}”, we begin with “{b_title}” and establish {b_focus} as the common lens for the section’s contrasts.",
    ]
    sent = _stable_choice(f"h2open:{sec_title}->{first_sub_id}", variants)
    return f"- {sec_title} → {first_sub_id}: {sent}"


def _h2_handoff(*, last_sub_id: str, next_sec_title: str, briefs: dict[str, dict[str, Any]]) -> str:
    a = briefs.get(last_sub_id) or {}
    a_title = str(a.get("title") or last_sub_id).strip()
    a_bridge = ", ".join(_short_list(a.get("bridge_terms"), limit=3))

    a_focus = a_bridge or "the key axes"

    variants = [
        f"After “{a_title}” closes the local comparison ({a_focus}), we broaden back out and move to “{next_sec_title}” to revisit the theme at the next layer (design → evidence → implications).",
        f"With “{a_title}” establishing the section’s last needed contrast, the narrative hands off to “{next_sec_title}”, which continues the argument by changing the lens while keeping terminology consistent.",
        f"Having finished “{a_title}”, we transition to “{next_sec_title}” to address what the previous section could not: new constraints, new interfaces, or a different evaluation emphasis.",
    ]
    sent = _stable_choice(f"h2handoff:{last_sub_id}->{next_sec_title}", variants)
    return f"- {last_sub_id} → {next_sec_title}: {sent}"


def _h2_to_h2(*, a_title: str, b_title: str) -> str:
    variants = [
        f"Once “{a_title}” has established its core distinctions, “{b_title}” follows to build the next layer of the argument rather than repeating background.",
        f"“{a_title}” provides the prior context; “{b_title}” continues by shifting the emphasis from framing to concrete comparisons.",
        f"The hand-off from “{a_title}” to “{b_title}” is driven by a gap: after describing what matters, the next section clarifies how to compare and validate it.",
    ]
    sent = _stable_choice(f"h2:{a_title}->{b_title}", variants)
    return f"- {a_title} → {b_title}: {sent}"


def _render_transitions(*, outline: Any, briefs: dict[str, dict[str, Any]]) -> str:
    b = _iter_outline_boundaries(outline)
    within = b.get("within_h3") or []
    openers = b.get("h2_openers") or []
    handoffs = b.get("h2_closers") or []
    between = b.get("between_h2") or []

    lines: list[str] = [
        "# Transitions (no new facts; no citations)",
        "",
        "- Guardrail: transitions add no new facts and introduce no new citations.",
        "- Use these as hand-offs: what was established → what remains unclear → why the next unit follows.",
        "",
        "## Section openers (H2 → first H3)",
    ]

    if openers:
        for sec_title, first_sub_id in openers:
            lines.append(_h2_opener(sec_title=sec_title, first_sub_id=first_sub_id, briefs=briefs))
    else:
        lines.append("- (no section openers detected)")

    lines.extend(["", "## Within-section (H3 → next H3)", ""])
    if within:
        for a_id, b_id in within:
            lines.append(_h3_transition(a_id=a_id, b_id=b_id, briefs=briefs))
    else:
        lines.append("- (no within-section pairs detected)")

    lines.extend(["", "## Between sections (last H3 → next H2)", ""])
    if handoffs:
        for last_sub_id, next_sec_title in handoffs:
            lines.append(_h2_handoff(last_sub_id=last_sub_id, next_sec_title=next_sec_title, briefs=briefs))
    else:
        lines.append("- (no section handoffs detected)")

    lines.extend(["", "## Between sections (H2 → next H2)", ""])
    if between:
        for a_title, b_title in between:
            lines.append(_h2_to_h2(a_title=a_title, b_title=b_title))
    else:
        lines.append("- (no H2 adjacency detected)")

    lines.append("")
    return "\n".join(lines)


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

    from tooling.common import atomic_write_text, ensure_dir, load_yaml, parse_semicolon_list
    from tooling.quality_gate import check_unit_outputs, write_quality_report

    workspace = Path(args.workspace).resolve()
    unit_id = str(args.unit_id or "U098").strip() or "U098"

    inputs = parse_semicolon_list(args.inputs) or ["outline/outline.yml", "outline/subsection_briefs.jsonl"]
    outputs = parse_semicolon_list(args.outputs) or ["outline/transitions.md"]

    out_rel = outputs[0] if outputs else "outline/transitions.md"
    out_path = workspace / out_rel
    ensure_dir(out_path.parent)

    freeze_marker = out_path.with_name("transitions.refined.ok")
    if out_path.exists() and out_path.stat().st_size > 0 and freeze_marker.exists():
        return 0

    issues = check_unit_outputs(skill="transition-weaver", workspace=workspace, outputs=[out_rel])
    if not issues:
        return 0

    outline_rel = inputs[0]
    briefs_rel = inputs[1] if len(inputs) >= 2 else "outline/subsection_briefs.jsonl"
    outline = load_yaml(workspace / outline_rel) if (workspace / outline_rel).exists() else []
    briefs = _load_subsection_briefs(workspace / briefs_rel)

    atomic_write_text(out_path, _render_transitions(outline=outline, briefs=briefs))

    issues = check_unit_outputs(skill="transition-weaver", workspace=workspace, outputs=[out_rel])
    if issues:
        write_quality_report(workspace=workspace, unit_id=unit_id, skill="transition-weaver", issues=issues)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
