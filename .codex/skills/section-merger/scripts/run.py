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
        # H3: - 2.1 -> 2.2: ... (accepts unicode arrow too)
        m = re.match(r"^\-\s+([0-9]+\.[0-9]+)\s*(?:→|->)\s*([0-9]+\.[0-9]+):\s+(.*)$", line)
        if m:
            a, b, body = m.group(1), m.group(2), m.group(3)
            h3_map[(a, b)] = body.strip()
            continue
        # H2: - Title A -> Title B: ... (accepts unicode arrow too)
        m2 = re.match(r"^\-\s+(.+?)\s*(?:→|->)\s*(.+?):\s+(.*)$", line)
        if m2:
            a, b, body = m2.group(1).strip(), m2.group(2).strip(), m2.group(3).strip()
            if a and b and body:
                h2_map[(a, b)] = body
    return h3_map, h2_map


_TABLE_SEP = re.compile(r"(?m)^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")


def _count_md_tables(text: str) -> int:
    # Count table separator lines (one per Markdown table).
    return len(re.findall(_TABLE_SEP, text or ""))


def _clean_tables_for_insertion(text: str) -> str:
    # `outline/tables_appendix.md` is inserted without headings to avoid ToC bloat.
    out: list[str] = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s:
            out.append("")
            continue
        if s.startswith("#"):
            continue
        out.append(raw.rstrip())
    return "\n".join(out).strip()


def _is_related_work(title: str) -> bool:
    t = re.sub(r"\s+", " ", (title or "").strip().lower())
    return "related work" in t


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
    from tooling.quality_gate import _pipeline_profile

    workspace = Path(args.workspace).resolve()
    profile = _pipeline_profile(workspace)

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
        "sections/discussion.md",
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
            # H2 lead paragraph block (no headings) for chapter coherence.
            sec_id = str(sec.get("id") or "").strip()
            if sec_id:
                unit_files.append(f"sections/{_slug_unit_id(sec_id)}_lead.md")

            for sub in subs:
                sid = str(sub.get("id") or "").strip()
                if sid:
                    unit_files.append(f"sections/{_slug_unit_id(sid)}.md")
        else:
            sid = str(sec.get("id") or "").strip()
            if sid:
                unit_files.append(f"sections/{_slug_unit_id(sid)}.md")

    # Tables are part of the default deliverable for arxiv-survey pipelines.
    tables_rel = "outline/tables_appendix.md"
    tables_off = (workspace / "outline" / "tables.insert.off").exists()
    require_tables = profile == "arxiv-survey" and not tables_off

    tables_text = ""
    tables_n = 0

    # Probe all required inputs. We do NOT write a partial draft with TODO markers.
    for rel in required_global + unit_files + required_transitions:
        _require(rel)

    if require_tables:
        p = workspace / tables_rel
        if not p.exists() or p.stat().st_size <= 0:
            missing.append(tables_rel)
        else:
            tables_text = _clean_tables_for_insertion(_read_text(p))
            tables_n = _count_md_tables(tables_text)
            if tables_n < 2:
                missing.append(f"{tables_rel} (expected >=2 Markdown tables)")

    status = "PASS" if not missing else "FAIL"

    if missing:
        rep_lines = [
            "# Merge report",
            "",
            f"- Status: {status}",
            f"- Draft: `{draft_rel}`",
            f"- Missing inputs: {len(missing)}",
        ]
        if profile == "arxiv-survey":
            rep_lines.append(f"- Tables required: {'yes' if require_tables else 'no'}")
            if require_tables:
                rep_lines.append(f"- Tables detected (outline): {tables_n}")
        rep_lines.extend(["", "## Missing files"])
        for rel in sorted(set(missing)):
            rep_lines.append(f"- `{rel}`")
        rep_lines.append("")
        atomic_write_text(report_path, "\n".join(rep_lines).rstrip() + "\n")
        return 2

    # Title from GOAL.md (first non-heading line).
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

    # By default, do not inject between-H2 narrator transitions into the paper body.
    # If you really want H2->H2 transitions inserted, create: outline/transitions.insert_h2.ok
    insert_h2_transitions = (workspace / "outline" / "transitions.insert_h2.ok").exists()

    out_lines: list[str] = [f"# {title}", ""]

    out_lines.append(_require("sections/abstract.md").strip())
    out_lines.append("")

    tables_inserted = False
    tables_insert_note = ""

    for idx, sec in enumerate(outline_sections):
        sec_title = sec["title"]
        out_lines.append(f"## {sec_title}")
        out_lines.append("")

        subs = sec.get("subsections") or []
        if subs:
            lead_rel = f"sections/{_slug_unit_id(sec['id'])}_lead.md"
            out_lines.append(_read_text(workspace / lead_rel).strip())
            out_lines.append("")

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


        if insert_h2_transitions and idx + 1 < len(outline_sections):
            nxt_title = outline_sections[idx + 1]["title"]
            t = h2_trans.get((sec_title, nxt_title), "").strip()
            if t:
                out_lines.append(t)
                out_lines.append("")

    out_lines.append(_require("sections/discussion.md").strip())
    out_lines.append("")
    out_lines.append(_require("sections/conclusion.md").strip())
    out_lines.append("")

    if require_tables:
        out_lines.append("## Appendix: Tables")
        out_lines.append("")
        out_lines.append(tables_text)
        out_lines.append("")
        tables_inserted = True
        tables_insert_note = "appendix"

    ensure_dir(draft_path.parent)
    atomic_write_text(draft_path, "\n".join([ln for ln in out_lines if ln is not None]).rstrip() + "\n")

    rep_lines = [
        "# Merge report",
        "",
        "- Status: PASS",
        f"- Draft: `{draft_rel}`",
        "- Missing inputs: 0",
    ]
    if profile == "arxiv-survey":
        rep_lines.append(f"- Tables required: {'yes' if require_tables else 'no'}")
        if require_tables:
            rep_lines.append(f"- Tables detected (outline): {tables_n}")
            rep_lines.append(f"- Tables inserted: {'yes' if tables_inserted else 'no'}")
            if tables_inserted:
                rep_lines.append(f"- Tables insertion: {tables_insert_note}")
                rep_lines.append(f"- Tables source: `{tables_rel}`")
    rep_lines.append("")
    atomic_write_text(report_path, "\n".join(rep_lines).rstrip() + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
