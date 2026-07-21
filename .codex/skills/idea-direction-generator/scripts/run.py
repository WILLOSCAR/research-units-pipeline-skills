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

    from tooling.common import load_workspace_pipeline_spec, parse_semicolon_list
    from tooling.ideation import IdeaSignal, collect_note_index, direction_pool_markdown, read_jsonl, resolve_idea_contract, signals_to_direction_cards, write_jsonl, write_markdown

    workspace = Path(args.workspace).resolve()
    if load_workspace_pipeline_spec(workspace) is None:
        raise SystemExit('Missing or invalid active pipeline contract; fix PIPELINE.lock.md and pipeline metadata before ideation C4.')
    outputs = parse_semicolon_list(args.outputs) or ["output/trace/IDEA_DIRECTION_POOL.md"]
    out_rel = outputs[0] if outputs else "output/trace/IDEA_DIRECTION_POOL.md"
    out_path = workspace / out_rel
    jsonl_path = out_path.with_suffix('.jsonl')

    try:
        contract = resolve_idea_contract(workspace)
    except Exception as exc:
        raise SystemExit(f'Invalid ideation runtime contract: {exc}')
    if not contract.get('focus_clusters'):
        raise SystemExit('Missing focus clusters; complete C2 approval before generating the direction pool.')
    signal_json = workspace / 'output' / 'trace' / 'IDEA_SIGNAL_TABLE.jsonl'
    raw_signals = [r for r in read_jsonl(signal_json) if isinstance(r, dict)]
    if not raw_signals:
        raise SystemExit('Missing signal rows; run idea-signal-mapper first')

    signals = [IdeaSignal(**row) for row in raw_signals]
    note_index = collect_note_index(workspace / 'papers' / 'paper_notes.jsonl')
    cards = signals_to_direction_cards(
        signals,
        note_index=note_index,
        focus_clusters=contract.get('focus_clusters') or [],
        hard_exclusions=contract.get('hard_exclusions') or [],
        pool_min=int(contract['direction_pool_min']),
        pool_max=int(contract['direction_pool_max']),
    )
    write_markdown(out_path, direction_pool_markdown(cards))
    write_jsonl(jsonl_path, [c.__dict__ for c in cards])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
