from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _goal_text(path: Path) -> str:
    if not path.exists():
        return ""
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
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

    repo_root = Path(__file__).resolve()
    for _ in range(10):
        if (repo_root / "AGENTS.md").exists():
            break
        parent = repo_root.parent
        if parent == repo_root:
            break
        repo_root = parent
    sys.path.insert(0, str(repo_root))

    from tooling.review_artifacts import write_text
    from tooling.review_protocol import maybe_parse_queries_md, protocol_markdown

    workspace = Path(args.workspace).resolve()
    goal = _goal_text(workspace / "GOAL.md")
    keywords, exclude, time_from, time_to = maybe_parse_queries_md(workspace / "queries.md")
    review_questions = [
        goal or "What does the available evidence support in the target topic?",
        "What evidence remains after screening and extraction?",
        "What bias and heterogeneity limits the conclusions?",
    ]
    extraction_fields = [
        {"field": "population_or_setting", "definition": "population, dataset, environment, or evaluation setting", "allowed_values": "free text or not reported", "notes": "name the observed setting without inference"},
        {"field": "task", "definition": "primary task or study focus", "allowed_values": "free text", "notes": "use short stable labels"},
        {"field": "metric", "definition": "main reported metric or endpoint", "allowed_values": "free text", "notes": "keep the reported wording"},
        {"field": "study_type", "definition": "study design or evaluation type", "allowed_values": "free text", "notes": "empirical, benchmark, user study, etc."},
        {"field": "result_summary", "definition": "bounded result supported by the available record", "allowed_values": "free text or not reported", "notes": "do not infer beyond abstract/full text"},
        {"field": "evidence_pointer", "definition": "URL or local source pointer for the extracted row", "allowed_values": "URL or workspace path", "notes": "must resolve to the screened record"},
    ]
    text = protocol_markdown(
        goal=goal,
        review_questions=review_questions,
        include_keywords=keywords,
        exclude_keywords=exclude,
        time_window_from=time_from,
        time_window_to=time_to,
        sources=["arXiv", "manual snowballing"],
        extraction_fields=extraction_fields,
    )
    write_text(workspace / "output" / "PROTOCOL.md", text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
