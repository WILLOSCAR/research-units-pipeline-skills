from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def _stable_choice(key: str, options: list[str]) -> str:
    """Deterministic choice (stable across runs) while allowing rich template variety."""

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


def _focus_terms(rec: dict[str, Any]) -> str:
    """Pick subsection-specific, no-facts "handles" to mention in transitions."""

    parts: list[str] = []
    bridge = ", ".join(_short_list(rec.get("bridge_terms"), limit=3))
    axes = ", ".join(_short_list(rec.get("axes"), limit=2))
    hook = str(rec.get("contrast_hook") or "").strip()

    if bridge:
        parts.append(bridge)
    if axes:
        parts.append(axes)
    if hook:
        parts.append(hook)

    out: list[str] = []
    for p in parts:
        p = str(p or "").strip()
        if p and p not in out:
            out.append(p)
    return "; ".join(out[:2]).strip()


def _h3_transition(*, a_id: str, b_id: str, briefs: dict[str, dict[str, Any]]) -> str:
    a = briefs.get(a_id) or {}
    b = briefs.get(b_id) or {}

    a_title = str(a.get("title") or a_id).strip()
    b_title = str(b.get("title") or b_id).strip()

    b_focus = _focus_terms(b) or "a concrete comparison handle"

    # Avoid "From X to Y ..." title narration; keep the bridge as an argument move.
    variants = [
        f"With {a_title} in place, {b_title} narrows the focus to {b_focus}, which becomes the handle for the next comparisons.",
        f"Building on {a_title}, {b_title} foregrounds {b_focus} to make the contrast operational rather than purely thematic.",
        f"What {a_title} leaves underspecified is {b_focus}; {b_title} uses it to sharpen how we compare the next set of approaches.",
        f"Rather than restarting, {b_title} carries forward the thread from {a_title} and stresses it through {b_focus}.",
        f"After {a_title}, {b_title} makes the bridge explicit via {b_focus}, setting up a cleaner A-vs-B comparison.",
        f"{b_title} follows naturally by turning {a_title}'s framing into {b_focus}-anchored evaluation questions.",
    ]

    # Include titles/focus in the seed so different surveys with the same numeric IDs
    # don't always pick the same template variant.
    sent = _stable_choice(f"h3:{a_id}:{a_title}->{b_id}:{b_title}:{b_focus}", variants)
    return f"- {a_id} → {b_id}: {sent}"


def _h2_opener(*, sec_title: str, first_sub_id: str, briefs: dict[str, dict[str, Any]]) -> str:
    b = briefs.get(first_sub_id) or {}
    b_title = str(b.get("title") or first_sub_id).strip()
    b_focus = _focus_terms(b) or "shared comparison handles"

    variants = [
        f"{sec_title} opens with {b_title} to establish {b_focus} as the common lens reused across the chapter.",
        f"{sec_title} begins with {b_title}, translating the theme into {b_focus} that later subsections can vary and stress-test.",
        f"To ground {sec_title}, {b_title} pins down {b_focus} before the chapter layers on additional constraints.",
        f"{b_title} is the first step in {sec_title}: it fixes {b_focus} so subsequent comparisons do not drift.",
        f"{sec_title} begins at {b_title}, where {b_focus} turns a broad topic into concrete evaluation-ready handles.",
    ]

    sent = _stable_choice(f"h2open:{sec_title}->{first_sub_id}:{b_title}:{b_focus}", variants)
    return f"- {sec_title} → {first_sub_id}: {sent}"


def _h2_handoff(*, last_sub_id: str, next_sec_title: str, briefs: dict[str, dict[str, Any]]) -> str:
    a = briefs.get(last_sub_id) or {}
    a_title = str(a.get("title") or last_sub_id).strip()
    a_focus = _focus_terms(a) or "the key axes"

    variants = [
        f"After {a_title} closes the local comparison ({a_focus}), {next_sec_title} revisits the theme at the next layer of abstraction.",
        f"With {a_title} completing this chapter’s last needed contrast, {next_sec_title} changes the lens while keeping core terms stable.",
        f"Having finished {a_title}, {next_sec_title} addresses what the previous section leaves open: new interfaces, new constraints, or a different evaluation emphasis.",
        f"{a_title} leaves us with {a_focus}; {next_sec_title} follows by reframing those handles into a new set of comparisons.",
        f"{next_sec_title} carries forward {a_focus} from {a_title} but applies it to a different part of the overall argument.",
    ]

    sent = _stable_choice(f"h2handoff:{last_sub_id}:{a_title}:{a_focus}->{next_sec_title}", variants)
    return f"- {last_sub_id} → {next_sec_title}: {sent}"


def _h2_to_h2(*, a_title: str, b_title: str) -> str:
    # Paper-like handoff: keep it as an argument bridge, not title narration.
    variants = [
        f"{b_title} builds on {a_title} by turning the framing into checkable contrasts and evaluation anchors.",
        f"{b_title} continues by tightening the unit of analysis from motivation to decisions, protocols, and failure modes.",
        f"{b_title} makes the next layer of the argument concrete, emphasizing comparison handles the later subsections reuse.",
        f"{b_title} follows by narrowing to the evidence: what is measured, under what constraints, and what remains ambiguous.",
        f"{b_title} picks up the thread by reframing {a_title} into operational questions the later subsections can stress-test.",
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
