from __future__ import annotations

import argparse
import sys
from pathlib import Path


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

    from tooling.common import read_jsonl
    from tooling.review_artifacts import write_text
    from tooling.review_render import render_rubric_review_markdown
    from tooling.review_text import parse_item_blocks

    workspace = Path(args.workspace).resolve()
    claims_path = workspace / "output" / "CLAIMS.md"
    gaps_path = workspace / "output" / "MISSING_EVIDENCE.md"
    matrix_path = workspace / "output" / "NOVELTY_MATRIX.md"
    if not claims_path.exists() or not gaps_path.exists():
        raise SystemExit("rubric-writer requires `output/CLAIMS.md` and `output/MISSING_EVIDENCE.md`.")

    claims_jsonl = workspace / "output" / "CLAIMS.jsonl"
    gaps_jsonl = workspace / "output" / "EVIDENCE_AUDIT.jsonl"
    claims = read_jsonl(claims_jsonl) if claims_jsonl.exists() else parse_item_blocks(claims_path.read_text(encoding="utf-8", errors="ignore"))
    gaps = read_jsonl(gaps_jsonl) if gaps_jsonl.exists() else parse_item_blocks(gaps_path.read_text(encoding="utf-8", errors="ignore"))
    major = []
    for gap in gaps:
        severity = str(gap.get("severity") or "").strip().lower()
        if severity == "major":
            major.append(
                {
                    "gap_id": gap.get("gap_id", gap.get("id", "")),
                    "claim_id": gap.get("claim_id", ""),
                    "gap": gap.get("gap___concern", gap.get("gap_concern", gap.get("gap", ""))),
                    "minimal_fix": gap.get("minimal_fix", ""),
                }
            )
    text = render_rubric_review_markdown(
        claim_count=len(claims),
        gap_count=len(gaps),
        major_gaps=major,
        novelty_available=matrix_path.exists(),
    )
    write_text(workspace / "output" / "REVIEW.md", text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
