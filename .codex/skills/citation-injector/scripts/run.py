from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _extract_cites(text: str) -> list[str]:
    keys: list[str] = []
    for m in re.finditer(r"\[@([^\]]+)\]", text or ""):
        inside = (m.group(1) or "").strip()
        for k in re.findall(r"[A-Za-z0-9:_-]+", inside):
            if k and k not in keys:
                keys.append(k)
    return keys


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

    from tooling.common import atomic_write_text, ensure_dir, parse_semicolon_list
    from tooling.quality_gate import QualityIssue, check_unit_outputs, write_quality_report

    workspace = Path(args.workspace).resolve()
    unit_id = str(args.unit_id or "U1045").strip() or "U1045"

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

    draft_rel = next((p for p in outputs if p.endswith("DRAFT.md")), "output/DRAFT.md")
    report_rel = next((p for p in outputs if p.endswith("CITATION_INJECTION_REPORT.md")), "output/CITATION_INJECTION_REPORT.md")

    draft_path = workspace / draft_rel
    report_path = workspace / report_rel
    ensure_dir(report_path.parent)

    budget_rel = next((p for p in inputs if p.endswith("CITATION_BUDGET_REPORT.md")), "output/CITATION_BUDGET_REPORT.md")
    budget_path = workspace / budget_rel

    # LLM-first policy: do NOT inject citations in code.
    # This helper only validates whether the draft meets the budget target and writes a report.

    missing_inputs: list[str] = []
    if not draft_path.exists() or draft_path.stat().st_size <= 0:
        missing_inputs.append(draft_rel)
    if not budget_path.exists() or budget_path.stat().st_size <= 0:
        missing_inputs.append(budget_rel)

    if missing_inputs:
        msg = "Missing inputs: " + ", ".join(missing_inputs)
        write_quality_report(
            workspace=workspace,
            unit_id=unit_id,
            skill="citation-injector",
            issues=[QualityIssue(code="missing_inputs", message=msg)],
        )
        # Also write a report-class file to make the block debuggable without re-running.
        atomic_write_text(
            report_path,
            "\n".join(
                [
                    "# Citation injection report",
                    "",
                    "- Status: FAIL",
                    f"- Reason: {msg}",
                    "",
                    "## Next action",
                    "- Generate the budget report (`citation-diversifier`) and ensure `output/DRAFT.md` exists, then rerun.",
                    "",
                ]
            ).rstrip()
            + "\n",
        )
        return 2

    budget_md = budget_path.read_text(encoding="utf-8", errors="ignore")
    target, gap, suggestions = _parse_budget_report(budget_md)

    draft = draft_path.read_text(encoding="utf-8", errors="ignore")
    unique = len(set(_extract_cites(draft)))

    # If the budget report says gap=0, treat as a no-op PASS.
    # Otherwise, require meeting the global target when a target is present.
    ok = True
    reason = ""
    if gap > 0 and target > 0 and unique < target:
        ok = False
        reason = f"Unique citations are still below target (unique={unique}, target>={target}, gap={gap})."

    status = "PASS" if ok else "FAIL"

    lines: list[str] = [
        "# Citation injection report",
        "",
        f"- Status: {status}",
        f"- Draft: `{draft_rel}`",
        f"- Budget: `{budget_rel}`",
        f"- Unique citations (current): {unique}",
        f"- Global target (from budget): {target}",
        f"- Gap (from budget): {gap}",
        "",
    ]

    if ok:
        lines.extend(
            [
                "## Summary",
                "",
                "- Budget target satisfied (or no injection needed).",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Summary",
                "",
                f"- {reason}",
                "",
                "## How to fix (LLM-first; NO NEW FACTS)",
                "",
                "- Edit `output/DRAFT.md` and inject *in-scope* citations using the patterns in `citation-injector/SKILL.md`.",
                "- Prefer short, axis-anchored exemplars or parenthetical grounding; avoid cite-dump paragraphs.",
                "- Only use keys suggested for each H3 in the budget report.",
                "- Then rerun this unit to recheck the target.",
                "",
            ]
        )

        if suggestions:
            lines.append("## Suggested keys by subsection (from budget)")
            lines.append("")
            # Keep this short: show a few highest-leverage subsections.
            shown = 0
            for sid, keys in list(suggestions.items())[:10]:
                ktxt = ", ".join([f"`{k}`" for k in keys[:8]])
                suffix = "..." if len(keys) > 8 else ""
                lines.append(f"- `{sid}`: {ktxt}{suffix}")
                shown += 1
                if shown >= 10:
                    break
            lines.append("")

    atomic_write_text(report_path, "\n".join(lines).rstrip() + "\n")

    # Reuse the standard quality gate: PASS requires the report to be PASS.
    issues = check_unit_outputs(skill="citation-injector", workspace=workspace, outputs=[report_rel])
    if issues:
        write_quality_report(workspace=workspace, unit_id=unit_id, skill="citation-injector", issues=issues)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
