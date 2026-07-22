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

    from tooling.review_artifacts import extract_pdf_text, find_workspace_text_source, write_text

    workspace = Path(args.workspace).resolve()
    out_path = workspace / "output" / "PAPER.md"
    if out_path.exists() and out_path.read_text(encoding="utf-8", errors="ignore").strip():
        return 0

    source = find_workspace_text_source(workspace, stems=("manuscript", "paper"))
    if source is None:
        raise SystemExit("No manuscript source found. Add `inputs/manuscript.md|txt|pdf` or `inputs/paper.*`.")

    if source.suffix.lower() == ".pdf":
        try:
            text = extract_pdf_text(source)
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from None
    else:
        text = source.read_text(encoding="utf-8", errors="ignore")
    if not text.strip():
        raise SystemExit(f"Manuscript source is empty: {source}")

    write_text(out_path, text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
