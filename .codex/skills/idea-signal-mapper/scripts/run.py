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

    from tooling.common import parse_semicolon_list
    from tooling.ideation import build_signal_rows, map_notes_to_clusters, signal_table_markdown, write_jsonl, write_markdown

    workspace = Path(args.workspace).resolve()
    outputs = parse_semicolon_list(args.outputs) or ["output/trace/IDEA_SIGNAL_TABLE.md"]
    out_rel = outputs[0] if outputs else "output/trace/IDEA_SIGNAL_TABLE.md"
    out_path = workspace / out_rel
    jsonl_path = out_path.with_suffix('.jsonl')

    clustered = map_notes_to_clusters(workspace / 'outline' / 'taxonomy.yml', workspace / 'papers' / 'paper_notes.jsonl')
    rows = []
    for cluster_index, (cluster, notes) in enumerate(clustered.items()):
        rows.extend(build_signal_rows(cluster=cluster, notes=notes, cluster_index=cluster_index))

    write_markdown(out_path, signal_table_markdown(rows))
    write_jsonl(jsonl_path, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
