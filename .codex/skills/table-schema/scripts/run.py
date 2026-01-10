from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _is_placeholder(text: str) -> bool:
    low = (text or "").strip().lower()
    if not low:
        return True
    if "(placeholder)" in low:
        return True
    if "<!-- scaffold" in low:
        return True
    if re.search(r"(?i)\b(?:todo|tbd|fixme)\b", low):
        return True
    if "…" in text:
        return True
    return False


def _looks_refined(text: str) -> bool:
    if _is_placeholder(text):
        return False
    # Require at least two table definitions.
    return len(re.findall(r"(?m)^##\s+Table\s+\d+:", text)) >= 2 and len(text.strip()) >= 600


def _read_goal(workspace: Path) -> str:
    goal_path = workspace / "GOAL.md"
    if not goal_path.exists():
        return ""
    for raw in goal_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(("-", ">", "<!--")):
            continue
        low = line.lower()
        if "写一句话" in line or "fill" in low:
            continue
        return line
    return ""


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

    inputs = parse_semicolon_list(args.inputs) or [
        "outline/outline.yml",
        "outline/subsection_briefs.jsonl",
        "outline/evidence_drafts.jsonl",
        "GOAL.md",
    ]
    outputs = parse_semicolon_list(args.outputs) or ["outline/table_schema.md"]

    out_path = workspace / outputs[0]
    ensure_dir(out_path.parent)

    if out_path.exists() and out_path.stat().st_size > 0:
        existing = out_path.read_text(encoding="utf-8", errors="ignore")
        if _looks_refined(existing):
            return 0

    outline = load_yaml(workspace / inputs[0]) if (workspace / inputs[0]).exists() else []
    briefs = read_jsonl(workspace / inputs[1]) if (workspace / inputs[1]).exists() else []
    packs = read_jsonl(workspace / inputs[2]) if (workspace / inputs[2]).exists() else []

    sub_count = 0
    if isinstance(outline, list):
        for section in outline:
            if not isinstance(section, dict):
                continue
            for sub in section.get("subsections") or []:
                if isinstance(sub, dict) and str(sub.get("id") or "").strip():
                    sub_count += 1

    goal = _read_goal(workspace)

    lines: list[str] = [
        "# Table schema (evidence-first)",
        "",
        "- Policy: schema-first; tables are verifiable artifacts (not prose).",
        "- Cell style: short phrases; avoid paragraph cells; prefer 1–2 clauses per cell.",
        "- Citation rule: every row must include at least one citation marker `[@BibKey]` in a dedicated column.",
        "",
        f"- Goal (from `GOAL.md`): {goal or '(missing)'}",
        f"- Subsections (H3) detected: {sub_count}",
        f"- Evidence packs: {len([p for p in packs if isinstance(p, dict)])}",
        f"- Briefs: {len([b for b in briefs if isinstance(b, dict)])}",
        "",
        "## Table 1: Subsection comparison map (axes + representative works)",
        "- Question: For each H3, what are the concrete comparison axes and which representative works ground them?",
        "- Row unit: H3 subsection (`sub_id`).",
        "- Columns:",
        "  - Subsection (id + title)",
        "  - Axes (3–5 short phrases)",
        "  - Clusters (2–3 labels; optional)",
        "  - Evidence snippet (1 short factual snippet)",
        "  - Representative works (3–5 cite keys)",
        "- Evidence mapping:",
        "  - Axes: `outline/subsection_briefs.jsonl:axes`",
        "  - Clusters: `outline/subsection_briefs.jsonl:clusters`",
        "  - Evidence snippet: `outline/evidence_drafts.jsonl:evidence_snippets[0]`",
        "  - Representative works: cite keys from evidence pack blocks (snippets/claims/comparisons/limitations)",
        "",
        "## Table 2: Evaluation practice + verification needs",
        "- Question: What evaluation protocol elements are mentioned, and what fields must be verified before strong conclusions?",
        "- Row unit: H3 subsection (`sub_id`).",
        "- Columns:",
        "  - Subsection (id + title)",
        "  - Evaluation protocol highlights (benchmarks/datasets/metrics if present)",
        "  - Verify fields (short checklist; non-blocking)",
        "  - Evidence levels (fulltext/abstract/title counts)",
        "  - Representative works (3–5 cite keys)",
        "- Evidence mapping:",
        "  - Evaluation: `outline/evidence_drafts.jsonl:evaluation_protocol` (fallback: `verify_fields`)",
        "  - Verify fields: `outline/evidence_drafts.jsonl:verify_fields`",
        "  - Evidence levels: `outline/evidence_drafts.jsonl:evidence_level_summary`",
        "",
        "## Constraints (for table-filler)",
        "- Minimum tables: >=2.",
        "- No placeholders: no `TODO`, `…`, or instruction text (e.g., 'enumerate 2-4 ...').",
        "- No long prose cells: keep each cell <= ~160 characters when possible.",
        "",
    ]

    atomic_write_text(out_path, "\n".join(lines).rstrip() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
