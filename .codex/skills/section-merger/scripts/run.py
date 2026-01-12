from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


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


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _iter_outline(outline: Any) -> list[dict[str, Any]]:
    if not isinstance(outline, list):
        return []
    out: list[dict[str, Any]] = []
    for sec in outline:
        if not isinstance(sec, dict):
            continue
        sec_id = str(sec.get("id") or "").strip()
        sec_title = str(sec.get("title") or "").strip()
        subs = []
        for sub in sec.get("subsections") or []:
            if not isinstance(sub, dict):
                continue
            sub_id = str(sub.get("id") or "").strip()
            sub_title = str(sub.get("title") or "").strip()
            if sub_id and sub_title:
                subs.append({"id": sub_id, "title": sub_title})
        if sec_id and sec_title:
            out.append({"id": sec_id, "title": sec_title, "subsections": subs})
    return out


def _parse_transitions(text: str) -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], str]]:
    h3_map: dict[tuple[str, str], str] = {}
    h2_map: dict[tuple[str, str], str] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line.startswith("-"):
            continue
        # H3: - 2.1 → 2.2: ...
        m = re.match(r"^\-\s+([0-9]+\.[0-9]+)\s+→\s+([0-9]+\.[0-9]+):\s+(.*)$", line)
        if m:
            a, b, body = m.group(1), m.group(2), m.group(3)
            h3_map[(a, b)] = body.strip()
            continue
        # H2: - Title A → Title B: ...
        m2 = re.match(r"^\-\s+(.+?)\s+→\s+(.+?):\s+(.*)$", line)
        if m2:
            a, b, body = m2.group(1).strip(), m2.group(2).strip(), m2.group(3).strip()
            if a and b and body:
                h2_map[(a, b)] = body
    return h3_map, h2_map


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

    workspace = Path(args.workspace).resolve()

    inputs = parse_semicolon_list(args.inputs)
    outputs = parse_semicolon_list(args.outputs) or ["output/DRAFT.md", "output/MERGE_REPORT.md"]

    draft_rel = outputs[0] if outputs else "output/DRAFT.md"
    report_rel = outputs[1] if len(outputs) > 1 else "output/MERGE_REPORT.md"

    draft_path = workspace / draft_rel
    report_path = workspace / report_rel
    ensure_dir(report_path.parent)

    outline_rel = "outline/outline.yml"
    for rel in inputs:
        rel = str(rel or "").strip()
        if rel.endswith("outline/outline.yml") or rel.endswith("outline.yml"):
            outline_rel = rel
            break

    outline = load_yaml(workspace / outline_rel) if (workspace / outline_rel).exists() else []
    outline_sections = _iter_outline(outline)

    missing: list[str] = []

    def _require(relpath: str) -> str:
        p = workspace / relpath
        if not p.exists() or p.stat().st_size <= 0:
            missing.append(relpath)
            return ""
        return _read_text(p).strip() + "\n"

    # Required global sections.
    required_global = [
        "sections/abstract.md",
        "sections/open_problems.md",
        "sections/conclusion.md",
    ]

    # Required transitions map.
    required_transitions = [
        "outline/transitions.md",
    ]

    # Required per-outline unit files.
    unit_files: list[str] = []
    for sec in outline_sections:
        subs = sec.get("subsections") or []
        if subs:
            for sub in subs:
                sid = str(sub.get("id") or "").strip()
                if sid:
                    unit_files.append(f"sections/{_slug_unit_id(sid)}.md")
        else:
            sid = str(sec.get("id") or "").strip()
            if sid:
                unit_files.append(f"sections/{_slug_unit_id(sid)}.md")

    # Probe all required inputs. We do NOT write a partial draft with TODO markers.
    for rel in required_global + unit_files + required_transitions:
        _require(rel)

    status = "PASS" if not missing else "FAIL"

    rep_lines = [
        "# Merge report",
        "",
        f"- Status: {status}",
        f"- Draft: `{draft_rel}`",
        f"- Missing inputs: {len(missing)}",
        "",
    ]
    if missing:
        rep_lines.append("## Missing files")
        for rel in sorted(set(missing)):
            rep_lines.append(f"- `{rel}`")
        rep_lines.append("")

    atomic_write_text(report_path, "\n".join(rep_lines).rstrip() + "\n")

    if missing:
        # Block: do not generate a partial draft.
        return 2

    ensure_dir(draft_path.parent)

    goal = _read_text(workspace / "GOAL.md").strip().splitlines()
    title = "Survey"
    for ln in goal:
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        title = ln
        break

    transitions_text = _read_text(workspace / "outline" / "transitions.md")
    h3_trans, h2_trans = _parse_transitions(transitions_text)

    out_lines: list[str] = [f"# {title}", ""]

    out_lines.append(_require("sections/abstract.md").strip())
    out_lines.append("")

    for idx, sec in enumerate(outline_sections):
        sec_title = sec["title"]
        out_lines.append(f"## {sec_title}")
        out_lines.append("")

        subs = sec.get("subsections") or []
        if subs:
            for j, sub in enumerate(subs):
                sid = sub["id"]
                stitle = sub["title"]
                out_lines.append(f"### {stitle}")
                out_lines.append("")
                body_rel = f"sections/{_slug_unit_id(sid)}.md"
                out_lines.append(_read_text(workspace / body_rel).strip())
                out_lines.append("")

                if j + 1 < len(subs):
                    nxt = subs[j + 1]["id"]
                    t = h3_trans.get((sid, nxt), "").strip()
                    if t:
                        out_lines.append(t)
                        out_lines.append("")
        else:
            body_rel = f"sections/{_slug_unit_id(sec['id'])}.md"
            out_lines.append(_read_text(workspace / body_rel).strip())
            out_lines.append("")

        if idx + 1 < len(outline_sections):
            nxt_title = outline_sections[idx + 1]["title"]
            t = h2_trans.get((sec_title, nxt_title), "").strip()
            if t:
                out_lines.append(t)
                out_lines.append("")

    out_lines.append(_require("sections/open_problems.md").strip())
    out_lines.append("")
    out_lines.append(_require("sections/conclusion.md").strip())
    out_lines.append("")

    atomic_write_text(draft_path, "\n".join([ln for ln in out_lines if ln is not None]).rstrip() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
