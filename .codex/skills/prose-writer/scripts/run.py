from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable


def _first_match(values: Iterable[str], suffixes: tuple[str, ...]) -> str | None:
    for raw in values:
        rel = str(raw or "").strip()
        if not rel:
            continue
        for suf in suffixes:
            if rel.endswith(suf):
                return rel
    return None


def _newer_than(reference: Path, paths: list[Path]) -> list[Path]:
    if not reference.exists():
        return []
    ref_ts = reference.stat().st_mtime
    newer: list[Path] = []
    for p in paths:
        try:
            if p.exists() and p.stat().st_mtime > ref_ts:
                newer.append(p)
        except OSError:
            continue
    return newer


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

    from tooling.common import decisions_has_approval, parse_semicolon_list, upsert_checkpoint_block
    from tooling.quality_gate import QualityIssue, check_unit_outputs, write_quality_report

    workspace = Path(args.workspace).resolve()
    unit_id = str(args.unit_id or "U100").strip() or "U100"

    inputs = parse_semicolon_list(args.inputs)
    outputs = parse_semicolon_list(args.outputs) or ["output/DRAFT.md"]

    out_rel = outputs[0] if outputs else "output/DRAFT.md"

    decisions_rel = _first_match(inputs, ("DECISIONS.md",)) or "DECISIONS.md"
    decisions_path = workspace / decisions_rel

    outline_rel = _first_match(inputs, ("outline/outline.yml", "outline.yml")) or "outline/outline.yml"
    briefs_rel = _first_match(inputs, ("outline/subsection_briefs.jsonl", "subsection_briefs.jsonl")) or "outline/subsection_briefs.jsonl"
    evidence_rel = _first_match(inputs, ("outline/evidence_drafts.jsonl", "evidence_drafts.jsonl")) or "outline/evidence_drafts.jsonl"
    transitions_rel = _first_match(inputs, ("outline/transitions.md", "transitions.md")) or "outline/transitions.md"
    tables_rel = _first_match(inputs, ("outline/tables_appendix.md", "tables_appendix.md")) or "outline/tables_appendix.md"
    timeline_rel = _first_match(inputs, ("outline/timeline.md", "timeline.md")) or "outline/timeline.md"
    figures_rel = _first_match(inputs, ("outline/figures.md", "figures.md")) or "outline/figures.md"
    bib_rel = _first_match(inputs, ("citations/ref.bib", "ref.bib")) or "citations/ref.bib"

    # Survey policy: prose is allowed after HUMAN approves C2.
    if not decisions_has_approval(decisions_path, "C2"):
        block = "\n".join(
            [
                "## C5 writing request",
                "",
                "- This unit writes prose. Please tick `Approve C2` (scope + outline) in the approvals checklist above.",
                "- Then rerun the writing unit.",
                "",
            ]
        )
        upsert_checkpoint_block(decisions_path, "C5", block)
        return 2

    draft_path = workspace / out_rel

    # If a refined draft already exists, accept it only if it is still up-to-date
    # w.r.t. the evidence-first inputs (otherwise it becomes a stale artifact that
    # silently ignores improved briefs/evidence packs).
    if draft_path.exists() and draft_path.stat().st_size > 0:
        issues = check_unit_outputs(skill="prose-writer", workspace=workspace, outputs=[out_rel])
        if issues:
            write_quality_report(workspace=workspace, unit_id=unit_id, skill="prose-writer", issues=issues)
            return 2

        deps = [
            workspace / outline_rel,
            workspace / briefs_rel,
            workspace / evidence_rel,
            workspace / transitions_rel,
            workspace / tables_rel,
            workspace / timeline_rel,
            workspace / figures_rel,
            workspace / bib_rel,
        ]
        newer = _newer_than(draft_path, deps)
        if newer:
            sample = ", ".join([p.relative_to(workspace).as_posix() for p in newer[:6]])
            suffix = "..." if len(newer) > 6 else ""
            write_quality_report(
                workspace=workspace,
                unit_id=unit_id,
                skill="prose-writer",
                issues=[
                    QualityIssue(
                        code="draft_stale",
                        message=(
                            f"`{out_rel}` exists but is older than updated inputs ({sample}{suffix}); "
                            "regenerate the draft so it reflects the latest briefs/evidence packs/visuals."
                        ),
                    )
                ],
            )
            return 2

        return 0

    prereq: list = []

    def require(skill: str, outs: list[str]) -> None:
        prereq.extend(check_unit_outputs(skill=skill, workspace=workspace, outputs=outs))

    # Evidence-first prerequisites: writing depends on refined structure + evidence packs + citations/visuals.
    require("outline-builder", [outline_rel])
    require("section-mapper", ["outline/mapping.tsv"])
    require("subsection-briefs", [briefs_rel])
    require("evidence-draft", [evidence_rel])
    require("citation-verifier", [bib_rel])
    require("claim-matrix-rewriter", ["outline/claim_evidence_matrix.md"])
    require("table-schema", ["outline/table_schema.md"])
    require("appendix-table-writer", [tables_rel])
    require("survey-visuals", [timeline_rel, figures_rel])
    require("transition-weaver", [transitions_rel])

    if prereq:
        write_quality_report(workspace=workspace, unit_id=unit_id, skill="prose-writer", issues=prereq)
        return 2

    # Prereqs are satisfied, but the draft does not exist yet: block and let the LLM write the prose.
    issues = check_unit_outputs(skill="prose-writer", workspace=workspace, outputs=[out_rel])
    write_quality_report(workspace=workspace, unit_id=unit_id, skill="prose-writer", issues=issues)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
