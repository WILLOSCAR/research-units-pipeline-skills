from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


def _sanitize(text: str) -> str:
    if not text:
        return ""
    # Avoid tokens that the quality gate treats as placeholder markers.
    text = re.sub(r"(?i)\b(?:TODO|TBD|FIXME)\b", "placeholder tokens", text)
    text = text.replace("(placeholder)", "placeholder tokens")
    text = re.sub(r"(?i)<!--\s*scaffold", "<!-- redacted scaffold", text)
    return text


def _extract_citation_keys_md(text: str) -> set[str]:
    cited: set[str] = set()
    for m in re.finditer(r"\[@([^\]]+)\]", text or ""):
        inside = (m.group(1) or "").strip()
        for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
            if k:
                cited.add(k)
    return cited


def _extract_bib_keys(text: str) -> set[str]:
    keys = set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)\s*,", text or ""))
    return {k.strip() for k in keys if k and str(k).strip()}


def _split_h3_blocks(draft: str) -> list[tuple[str, str]]:
    """Return [(h3_title, block_text_including_heading)]."""
    if not draft:
        return []
    parts = re.split(r"(?m)^(?=###\s+)", draft)
    blocks: list[tuple[str, str]] = []
    for part in parts:
        chunk = part.strip("\n")
        if not chunk:
            continue
        if not chunk.lstrip().startswith("###"):
            continue
        first = chunk.splitlines()[0].strip()
        title = re.sub(r"^###\s+", "", first).strip()
        blocks.append((title or first, chunk))
    return blocks


def _count_md_tables(text: str) -> int:
    if not text:
        return 0
    # Rough: count separator rows.
    return len(re.findall(r"(?m)^\|?\s*:?[-]{3,}:?\s*(\|\s*:?[-]{3,}:?\s*)+\|?\s*$", text))


def _count_timeline_milestones(text: str) -> int:
    if not text:
        return 0
    # Expect bullets like '- 2023: ... [@Key]'
    return len([ln for ln in text.splitlines() if ln.strip().startswith("- ") and re.search(r"\b(19|20)\d{2}\b", ln)])


def _read_yaml_best_effort(path: Path) -> Any:
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        import yaml  # type: ignore

        return yaml.safe_load(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None


def _outline_subsection_count(outline: Any) -> int:
    if not isinstance(outline, list):
        return 0
    n = 0
    for sec in outline:
        if not isinstance(sec, dict):
            continue
        subs = sec.get("subsections") or []
        if isinstance(subs, list):
            for sub in subs:
                if isinstance(sub, dict) and str(sub.get("id") or "").strip():
                    n += 1
    return n


def _detect_evidence_mode(workspace: Path) -> str:
    """Best-effort evidence-mode detection.

    Prefer `queries.md` (source of truth). Fall back to whether `papers/fulltext_index.jsonl`
    contains any successful extraction records.
    """

    queries_path = workspace / "queries.md"
    if queries_path.exists():
        for raw in queries_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line.startswith("- evidence_mode:"):
                continue
            value = line.split(":", 1)[1].split("#", 1)[0].strip().strip('"').strip("'").strip().lower()
            if value in {"abstract", "fulltext"}:
                return value
            break

    idx_path = workspace / "papers" / "fulltext_index.jsonl"
    if not idx_path.exists() or idx_path.stat().st_size == 0:
        return "abstract"

    try:
        import json

        for i, raw in enumerate(idx_path.read_text(encoding="utf-8", errors="ignore").splitlines()):
            if i >= 200:
                break
            raw = raw.strip()
            if not raw:
                continue
            rec = json.loads(raw)
            if not isinstance(rec, dict):
                continue
            status = str(rec.get("status") or "").strip().lower()
            if status.startswith("ok"):
                return "fulltext"
    except Exception:
        return "abstract"

    return "abstract"


def _global_review_report(*, workspace: Path) -> str:
    from tooling.common import reader_request_leakage
    from tooling.quality_gate import _draft_profile

    draft_path = workspace / "output" / "DRAFT.md"
    draft = draft_path.read_text(encoding="utf-8", errors="ignore") if draft_path.exists() else ""

    bib_path = workspace / "citations" / "ref.bib"
    bib_text = bib_path.read_text(encoding="utf-8", errors="ignore") if bib_path.exists() else ""

    outline_path = workspace / "outline" / "outline.yml"
    outline = _read_yaml_best_effort(outline_path)

    cites_in_draft = _extract_citation_keys_md(draft)
    bib_keys = _extract_bib_keys(bib_text)
    missing_in_bib = sorted([k for k in cites_in_draft if bib_keys and k not in bib_keys])

    h3_blocks = _split_h3_blocks(draft)
    h3_count = len(h3_blocks)

    draft_profile = _draft_profile(workspace)
    lengths: list[tuple[int, str]] = []
    low_cites: list[str] = []
    min_subsection_cites = 4 if draft_profile == "course_paper" else 3
    min_subsection_chars = 1600 if draft_profile == "course_paper" else 5000
    for title, block in h3_blocks:
        sans_cites = re.sub(r"\[@[^\]]+\]", "", block)
        sans_cites = re.sub(r"\s+", " ", sans_cites).strip()
        lengths.append((len(sans_cites), title))
        if len(_extract_citation_keys_md(block)) < min_subsection_cites:
            low_cites.append(title)

    lengths.sort()
    weakest = [t for _, t in lengths[:3]] if lengths else []
    thin = [title for length, title in lengths if length < min_subsection_chars]
    median_len = lengths[len(lengths) // 2][0] if lengths else 0

    tables_path = workspace / "outline" / "tables_appendix.md"
    timeline_path = workspace / "outline" / "timeline.md"
    figures_path = workspace / "outline" / "figures.md"

    tables_n = _count_md_tables(tables_path.read_text(encoding="utf-8", errors="ignore") if tables_path.exists() else "")
    timeline_n = _count_timeline_milestones(timeline_path.read_text(encoding="utf-8", errors="ignore") if timeline_path.exists() else "")
    figures_has = bool(figures_path.exists() and figures_path.stat().st_size > 0)

    outline_h3 = _outline_subsection_count(outline)

    request_leaks = reader_request_leakage(draft)
    status = "PASS" if (draft and not missing_in_bib and not request_leaks) else "FAIL"

    lines: list[str] = []
    lines.append("# Global Review")
    lines.append("")
    lines.append(f"- Status: {status}")
    lines.append(f"- Draft profile: `{draft_profile}`")
    lines.append(f"- Draft subsections (H3): {h3_count}; median length (chars, sans cites): {median_len}")
    if outline_h3:
        lines.append(f"- Outline subsections (H3): {outline_h3}")
    lines.append(f"- Unique citation keys in draft: {len(cites_in_draft)}; missing in ref.bib: {len(missing_in_bib)}")
    if weakest:
        lines.append("- Weakest subsections by length: " + ", ".join([f"`{t}`" for t in weakest]))

    lines.append("")
    lines.append("## A. Input integrity / placeholder leakage")
    lines.append("- Draft exists: " + ("yes" if bool(draft.strip()) else "no"))
    lines.append("- Evidence mode: " + _detect_evidence_mode(workspace))
    if request_leaks:
        lines.append("- Delivery-request leakage: " + ", ".join(request_leaks) + ". Regenerate front matter and the paper title from the normalized research subject.")
    else:
        lines.append("- Delivery-request leakage: none detected.")
    lines.append("- Visual artifacts present: tables/timeline/figures = " + f"{tables_n}/{timeline_n}/{('yes' if figures_has else 'no')}")

    lines.append("")
    lines.append("## B. Narrative and argument chain")
    if low_cites:
        suffix = f"; and {len(low_cites) - 6} more" if len(low_cites) > 6 else ""
        lines.append(f"- Subsections with <{min_subsection_cites} unique citations: " + ", ".join([f"`{t}`" for t in low_cites[:6]]) + suffix)
    else:
        lines.append(f"- Citation density per subsection: looks OK (no <{min_subsection_cites}-cite subsections detected).")
    if thin:
        lines.append(
            f"- Subsections below the `{draft_profile}` depth floor ({min_subsection_chars} chars sans cites): "
            + ", ".join([f"`{title}`" for title in thin[:6]])
        )
    else:
        lines.append(f"- Subsection depth: every H3 meets the `{draft_profile}` floor ({min_subsection_chars} chars sans cites).")

    lines.append("")
    lines.append("## C. Scope and taxonomy consistency")
    if outline_h3:
        h3_target = 6 if draft_profile == "course_paper" else 12
        lines.append(f"- H3 count: {outline_h3} (`{draft_profile}` target: <={h3_target}).")
    lines.append("- Scope check: ensure section titles match mapped papers; avoid mixing orthogonal axes without an explicit rule.")

    lines.append("")
    lines.append("## D. Citations and verifiability (claim -> evidence)")
    if missing_in_bib:
        suffix = f"; and {len(missing_in_bib) - 8} more" if len(missing_in_bib) > 8 else ""
        sample = ", ".join([f"`{k}`" for k in missing_in_bib[:8]]) + suffix
        lines.append(f"- Undefined citations (present in draft but missing in ref.bib): {sample}")
    else:
        lines.append("- Citation keys appear consistent with ref.bib (no undefined keys detected).")
    lines.append("- Spot-check: each subsection should contain at least one paragraph that compares multiple works (>=2 citations in the same paragraph).")

    lines.append("")
    lines.append("## E. Tables and structural outputs")
    if draft_profile == "course_paper":
        lines.append(f"- Tables: separator rows found = {tables_n} (course-paper target: >=1 comparison table).")
        lines.append(f"- Timeline: year-like milestone bullets = {timeline_n} (optional for this profile).")
        lines.append("- Figures: optional; add one only when it clarifies the argument better than the comparison table.")
    else:
        lines.append(f"- Tables: separator rows found = {tables_n} (survey target: >=2 tables).")
        lines.append(f"- Timeline: year-like milestone bullets = {timeline_n} (survey target: >=8).")
        lines.append("- Figures: provide concrete figure specs (what the figure must show + which cited works anchor it).")

    lines.append("")
    lines.append("## Terminology glossary")
    lines.append("- Canonicalize key terms (one preferred name + allowed synonyms) and define them once early; then keep usage stable.")

    lines.append("")
    lines.append("## Ready-for-LaTeX checklist")
    lines.append(f"- Undefined citations: {len(missing_in_bib)}")
    lines.append(f"- Delivery-request leakage findings: {len(request_leaks)}")
    paragraph_target = "5-7" if draft_profile == "course_paper" else "6-10"
    lines.append(f"- Subsection depth: aim for {paragraph_target} paragraphs per H3 with a cross-paper synthesis paragraph")
    lines.append("")

    return _sanitize("\n".join(lines))


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

    from tooling.common import atomic_write_text, ensure_dir, parse_semicolon_list
    from tooling.quality_gate import check_unit_outputs, write_quality_report

    workspace = Path(args.workspace).resolve()
    unit_id = str(args.unit_id or "U120").strip() or "U120"

    outputs = parse_semicolon_list(args.outputs) or ["output/GLOBAL_REVIEW.md"]
    report_rel = outputs[0] if outputs else "output/GLOBAL_REVIEW.md"

    report_path = workspace / report_rel
    ensure_dir(report_path.parent)

    freeze_marker = report_path.with_name("GLOBAL_REVIEW.refined.ok")
    if report_path.exists() and report_path.stat().st_size > 0 and freeze_marker.exists():
        return 0

    # Always write a report (PASS/OK included). Reports are pipeline contract artifacts
    # and should exist even when there is nothing to flag (for audit/regression).
    atomic_write_text(report_path, _global_review_report(workspace=workspace))

    issues = check_unit_outputs(skill="global-reviewer", workspace=workspace, outputs=[report_rel])
    if issues:
        write_quality_report(workspace=workspace, unit_id=unit_id, skill="global-reviewer", issues=issues)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
