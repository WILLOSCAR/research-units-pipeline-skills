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

    from tooling.common import write_jsonl
    from tooling.review_artifacts import write_text
    from tooling.review_render import render_claims_markdown
    from tooling.review_text import classify_claim, pick_claim_candidates

    workspace = Path(args.workspace).resolve()
    paper_path = workspace / "output" / "PAPER.md"
    if not paper_path.exists():
        raise SystemExit("claims-extractor requires `output/PAPER.md`.")

    text = paper_path.read_text(encoding="utf-8", errors="ignore")
    candidates = pick_claim_candidates(text)
    claims = []
    for idx, item in enumerate(candidates, start=1):
        claim_type = classify_claim(item["sentence"])
        quote = item["sentence"].strip().strip('"')
        source = item["section"]
        if item["page"]:
            source += f" [page {item['page']}]"
        source += f' | "{quote}"'
        claims.append(
            {
                "schema": "review-claim.v1",
                "claim_id": f"C{idx:02d}",
                "text": quote,
                "claim_type": claim_type,
                "scope": f"{item['section']} scope",
                "source_pointer": source,
            }
        )

    if not claims:
        raise SystemExit("No claim candidates found in `output/PAPER.md`.")

    write_jsonl(workspace / "output" / "CLAIMS.jsonl", claims)
    write_text(workspace / "output" / "CLAIMS.md", render_claims_markdown(claims))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
