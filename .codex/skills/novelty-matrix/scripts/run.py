from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _extract_related_works(paper_text: str) -> list[str]:
    lines = (paper_text or "").splitlines()
    in_refs = False
    works: list[str] = []
    for raw in lines:
        line = raw.strip()
        if line.lower().startswith("## references") or line.lower().startswith("# references"):
            in_refs = True
            continue
        if in_refs and line.startswith("## "):
            break
        if in_refs and line.startswith("- "):
            works.append(line[2:].strip())
    return works


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

    from tooling.common import read_jsonl, write_tsv
    from tooling.review_artifacts import write_text
    from tooling.review_render import render_novelty_matrix_markdown
    from tooling.review_text import extract_related_works, parse_item_blocks, related_work_delta

    workspace = Path(args.workspace).resolve()
    claims_path = workspace / "output" / "CLAIMS.md"
    paper_path = workspace / "output" / "PAPER.md"
    if not claims_path.exists():
        raise SystemExit("novelty-matrix requires `output/CLAIMS.md`.")

    claims_jsonl = workspace / "output" / "CLAIMS.jsonl"
    if claims_jsonl.exists():
        claims = read_jsonl(claims_jsonl)
    else:
        claims = parse_item_blocks(claims_path.read_text(encoding="utf-8", errors="ignore"))
    paper_text = paper_path.read_text(encoding="utf-8", errors="ignore") if paper_path.exists() else ""
    works = extract_related_works(paper_text)
    rows: list[dict[str, str]] = []
    if not works:
        for claim in claims:
            rows.append(
                {
                    "schema": "review-novelty-row.v1",
                    "claim_id": claim.get("claim_id", claim.get("id", "")),
                    "claim": claim.get("text", claim.get("claim", "")),
                    "related_work": "related works unavailable",
                    "overlap": "unavailable",
                    "delta": "unavailable",
                    "evidence": "no reference list found in `output/PAPER.md`",
                }
            )
    else:
        for claim in claims:
            for work in works[:5]:
                # Prefer the manuscript's OWN stated overlap/delta for this work
                # (the Related Work prose often says "the delta over X is Y")
                # rather than identical boilerplate on every row.
                stated_overlap, stated_delta = related_work_delta(paper_text, work)
                rows.append(
                    {
                        "schema": "review-novelty-row.v1",
                        "claim_id": claim.get("claim_id", claim.get("id", "")),
                        "claim": claim.get("text", claim.get("claim", "")),
                        "related_work": work,
                        "overlap": stated_overlap or "adjacent problem setting",
                        "delta": stated_delta or "no explicit delta stated in the manuscript; verify against this work",
                        "evidence": (
                            "manuscript related-work section"
                            if (stated_overlap or stated_delta)
                            else "manuscript claim + cited related work"
                        ),
                    }
                )
    write_tsv(
        workspace / "output" / "NOVELTY_MATRIX.tsv",
        rows,
        fieldnames=["schema", "claim_id", "claim", "related_work", "overlap", "delta", "evidence"],
    )
    write_text(workspace / "output" / "NOVELTY_MATRIX.md", render_novelty_matrix_markdown(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
