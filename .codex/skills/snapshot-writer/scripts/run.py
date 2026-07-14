from __future__ import annotations

import argparse
import csv
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
    from tooling.review_artifacts import summarize_outline, write_text
    from tooling.review_render import render_research_brief_markdown

    workspace = Path(args.workspace).resolve()
    outline_path = workspace / "outline" / "outline.yml"
    core_path = workspace / "papers" / "core_set.csv"
    if not outline_path.exists() or not core_path.exists():
        raise SystemExit("snapshot-writer requires `outline/outline.yml` and `papers/core_set.csv`.")

    sections, _ = summarize_outline(outline_path)
    with core_path.open("r", encoding="utf-8", newline="") as handle:
        papers = [dict(row) for row in csv.DictReader(handle)]
    if not papers:
        raise SystemExit("`papers/core_set.csv` is empty.")

    deduped = read_jsonl(workspace / "papers" / "papers_dedup.jsonl")
    by_title = {str(item.get("title") or "").strip().lower(): item for item in deduped}
    by_url = {str(item.get("url") or "").strip(): item for item in deduped if str(item.get("url") or "").strip()}
    enriched: list[dict[str, str]] = []
    for idx, paper in enumerate(papers, start=1):
        title = str(paper.get("title") or f"Paper {idx}").strip()
        source = by_url.get(str(paper.get("url") or "").strip()) or by_title.get(title.lower()) or {}
        enriched.append(
            {
                **paper,
                "paper_id": str(paper.get("paper_id") or f"P{idx:04d}").strip(),
                "title": title,
                "abstract": str(source.get("abstract") or paper.get("abstract") or "").strip(),
            }
        )

    goal_path = workspace / "GOAL.md"
    goal = goal_path.read_text(encoding="utf-8", errors="ignore") if goal_path.exists() else ""
    text = render_research_brief_markdown(goal=goal, papers=enriched, sections=sections)
    write_text(workspace / "output" / "SNAPSHOT.md", text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
