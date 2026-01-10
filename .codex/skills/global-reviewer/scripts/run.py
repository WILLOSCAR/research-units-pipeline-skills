from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _scaffold() -> str:
    return "\n".join(
        [
            "# Global review (placeholder)",
            "",
            "- Status: (placeholder)",
            "- Scope decision: (placeholder; confirm in-scope/out-of-scope)",
            "",
            "## A. Input integrity / placeholder leakage",
            "- Did the outline contain prompt-like bullets (or missing RQ/evidence needs)?",
            "- Did the claim-evidence matrix contain ellipsis, scaffold phrases, or generic claims?",
            "- Do paper notes include concrete evidence fields (metrics/datasets/compute/failure modes), or only title-level metadata?",
            "- If evidence is abstract-only, does the draft avoid strong/definitive conclusions (use provisional language or block)?",
            "",
            "## B. Narrative and argument chain",
            "- For each subsection: one unique thesis (would be false in other sections) + two contrast sentences (A vs B) backed by citations.",
            "- For each subsection: at least one paragraph with >=2 citations (cross-paper synthesis), not per-paper lists.",
            "- Identify repeated templates / duplicated paragraphs and specify exact rewrites.",
            "",
            "## C. Scope and taxonomy consistency",
            "- Does the draft match the goal scope? If goal is T2I but many mapped works are T2V/T2AV, either justify or tighten retrieval filters.",
            "- Are taxonomy node boundaries consistent (include/exclude rules)?",
            "- Are section titles and mapped paper sets coherent (no section islands)?",
            "",
            "## D. Citations and verifiability (claim -> evidence)",
            "- Provide a small claim-evidence table (5-10 rows): claim | section | papers | evidence_field | evidence_level.",
            "- Flag any paragraph-length claims with weak/irrelevant citations.",
            "- Flag any cited keys missing from ref.bib (undefined cites).",
            "",
            "## E. Tables and structural outputs",
            "- Are tables answering a real comparison question (schema), or copying outline placeholders?",
            "- Do tables contain citations in rows? Are cells readable in LaTeX (line breaks, column widths, booktabs)?",
            "- If tables are ugly: classify root cause (content schema vs LaTeX template) and propose the exact fix.",
            "",
            "## Terminology glossary",
            "- Term: canonical name; synonyms; where defined (section)",
            "",
            "## Ready-for-LaTeX checklist",
            "- Undefined citations: 0",
            "- No placeholders / ellipsis / scaffold phrases",
            "- Each subsection has >=3 citations and at least one multi-citation paragraph",
            "- Tables >=2 and readable; timeline has >=8 cited milestones",
            "- Conclusion answers the main RQs and matches scope",
            "",
        ]
    )


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
    from tooling.quality_gate import check_unit_outputs, write_quality_report

    workspace = Path(args.workspace).resolve()
    unit_id = str(args.unit_id or "U120").strip() or "U120"

    outputs = parse_semicolon_list(args.outputs) or ["output/GLOBAL_REVIEW.md"]
    report_rel = outputs[0] if outputs else "output/GLOBAL_REVIEW.md"

    report_path = workspace / report_rel
    if not report_path.exists() or report_path.stat().st_size == 0:
        ensure_dir(report_path.parent)
        atomic_write_text(report_path, _scaffold())

    issues = check_unit_outputs(skill="global-reviewer", workspace=workspace, outputs=[report_rel])
    if issues:
        write_quality_report(workspace=workspace, unit_id=unit_id, skill="global-reviewer", issues=issues)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
