from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--checkpoint", default="C2")
    parser.add_argument("--unit-id", default="")
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
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

    from tooling.checkpoint_brief import write_checkpoint_brief
    from tooling.common import parse_semicolon_list

    write_checkpoint_brief(
        workspace=Path(args.workspace),
        checkpoint=str(args.checkpoint or "C2"),
        inputs=parse_semicolon_list(args.inputs),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
