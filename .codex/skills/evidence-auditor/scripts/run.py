from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _gap_for_claim(claim: dict[str, str]) -> tuple[str, str, str]:
    text = str(claim.get("claim") or "")
    low = text.lower()
    evidence_present = "The extracted claim has a locatable manuscript source pointer."
    if claim.get("type") == "empirical":
        if "%" in text or any(token in low for token in ("benchmark", "dataset", "accuracy", "success rate", "metric")):
            return (
                evidence_present,
                "The claim still needs an explicit baseline/protocol check before it can support a strong review judgment.",
                "Add a comparison table that states dataset, metric, baseline, and evaluation budget for this claim.",
            )
        return (
            evidence_present,
            "The empirical claim is underspecified: no concrete metric, dataset, or benchmark detail appears in the extracted claim text.",
            "State the task, metric, baseline, and result in the manuscript section tied to this claim.",
        )
    return (
        evidence_present,
        "The conceptual claim needs a clearer boundary and stronger relation to prior work.",
        "Clarify what the claim excludes and tie it to the closest prior work in the related-work section.",
    )


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

    from tooling.common import read_jsonl, write_jsonl
    from tooling.review_artifacts import write_text
    from tooling.review_render import render_gap_report_markdown
    from tooling.review_text import parse_item_blocks

    workspace = Path(args.workspace).resolve()
    claims_path = workspace / "output" / "CLAIMS.md"
    if not claims_path.exists():
        raise SystemExit("evidence-auditor requires `output/CLAIMS.md`.")

    claims_jsonl = workspace / "output" / "CLAIMS.jsonl"
    if claims_jsonl.exists():
        claims = read_jsonl(claims_jsonl)
    else:
        claims = parse_item_blocks(claims_path.read_text(encoding="utf-8", errors="ignore"))
    if not claims:
        raise SystemExit("No claim blocks found in `output/CLAIMS.md`.")

    gaps: list[dict[str, str]] = []
    for idx, claim in enumerate(claims, start=1):
        normalized_claim = {
            "id": str(claim.get("claim_id") or claim.get("id") or ""),
            "claim": str(claim.get("text") or claim.get("claim") or ""),
            "type": str(claim.get("claim_type") or claim.get("type") or ""),
        }
        evidence_present, gap, fix = _gap_for_claim(normalized_claim)
        severity = "major" if "underspecified" in gap.lower() else "minor"
        gaps.append(
            {
                "schema": "review-evidence-gap.v1",
                "gap_id": f"G{idx:02d}",
                "claim_id": normalized_claim["id"],
                "claim": normalized_claim["claim"],
                "evidence_present": evidence_present,
                "gap": gap,
                "minimal_fix": fix,
                "severity": severity,
            }
        )
    write_jsonl(workspace / "output" / "EVIDENCE_AUDIT.jsonl", gaps)
    write_text(workspace / "output" / "MISSING_EVIDENCE.md", render_gap_report_markdown(gaps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
