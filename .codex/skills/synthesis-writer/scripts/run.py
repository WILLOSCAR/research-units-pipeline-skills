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

    from tooling.review_artifacts import read_csv_rows, write_text
    from tooling.review_render import render_evidence_synthesis_markdown

    workspace = Path(args.workspace).resolve()
    table_path = workspace / "papers" / "extraction_table.csv"
    rows = read_csv_rows(table_path)
    if not rows:
        raise SystemExit("synthesis-writer requires `papers/extraction_table.csv`.")

    write_text(workspace / "output" / "SYNTHESIS.md", render_evidence_synthesis_markdown(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
