from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def _top_novelty_row(workspace: Path, claims: list) -> dict | None:
    """Novelty-matrix row for the headline claim (else the first row).

    Reads output/NOVELTY_MATRIX.tsv (schema review-novelty-row.v1: claim_id,
    claim, related_work, overlap, delta) so the review's Novelty note can cite
    the closest related work + delta for the paper's leading claim, instead of
    only asserting that a matrix exists. Returns None when the TSV is absent or
    unparseable (renderer falls back to the generic note).
    """
    tsv = workspace / "output" / "NOVELTY_MATRIX.tsv"
    if not tsv.is_file():
        return None
    try:
        rows = list(csv.DictReader(tsv.read_text(encoding="utf-8", errors="ignore").splitlines(), delimiter="\t"))
    except Exception:
        return None
    if not rows:
        return None
    # Prefer the row for the first claim's id (the headline claim), else row 0.
    head_id = ""
    for c in claims or []:
        if isinstance(c, dict):
            head_id = str(c.get("claim_id") or c.get("id") or "").strip()
            if head_id:
                break
    if head_id:
        for row in rows:
            if str(row.get("claim_id") or "").strip() == head_id:
                return row
    return rows[0]


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
    minor = []
    for gap in gaps:
        severity = str(gap.get("severity") or "").strip().lower()
        record = {
            "gap_id": gap.get("gap_id", gap.get("id", "")),
            "claim_id": gap.get("claim_id", ""),
            "gap": gap.get("gap___concern", gap.get("gap_concern", gap.get("gap", ""))),
            "minimal_fix": gap.get("minimal_fix", ""),
        }
        if severity == "major":
            major.append(record)
        else:
            minor.append(record)
    text = render_rubric_review_markdown(
        claim_count=len(claims),
        gap_count=len(gaps),
        major_gaps=major,
        novelty_available=matrix_path.exists(),
        claims=claims,
        novelty_row=_top_novelty_row(workspace, claims),
        minor_gaps=minor,
    )
    write_text(workspace / "output" / "REVIEW.md", text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
