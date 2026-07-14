from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _extract_flagged_paths(todo_text: str) -> list[str]:
    paths: list[str] = []
    in_style = False
    for raw in (todo_text or '').splitlines():
        line = raw.rstrip()
        if line.startswith('## '):
            in_style = line.strip() == '## Style Smells'
            continue
        if not in_style:
            continue
        for match in re.findall(r"`(sections/[^`]+?\.md)`", line):
            if match not in paths:
                paths.append(match)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--unit-id', default='')
    parser.add_argument('--inputs', default='')
    parser.add_argument('--outputs', default='')
    parser.add_argument('--checkpoint', default='')
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
    from tooling.common import atomic_write_text, ensure_dir, now_iso_seconds
    from tooling.quality_checks.survey_writing import section_files_newer_than, section_tree_sha256

    workspace = Path(args.workspace).resolve()
    sections_dir = workspace / 'sections'
    todo_path = workspace / 'output' / 'WRITER_SELFLOOP_TODO.md'
    marker = sections_dir / 'opener_varied.refined.ok'
    ensure_dir(marker.parent)

    if not todo_path.exists() or todo_path.stat().st_size == 0:
        print('Blocked: output/WRITER_SELFLOOP_TODO.md is missing or empty.', file=sys.stderr)
        marker.unlink(missing_ok=True)
        return 2

    todo_text = todo_path.read_text(encoding='utf-8', errors='ignore')
    if '- Status: PASS' not in todo_text or '## Style Smells' not in todo_text:
        print('Blocked: rerun writer-selfloop and obtain a PASS report with Style Smells.', file=sys.stderr)
        marker.unlink(missing_ok=True)
        return 2

    flagged = _extract_flagged_paths(todo_text)
    if flagged:
        preview = ', '.join(flagged[:8])
        print(
            f'Blocked: opener repairs remain for {preview}. Rewrite only those sections, '
            'then rerun writer-selfloop before retrying this unit.',
            file=sys.stderr,
        )
        marker.unlink(missing_ok=True)
        return 2

    stale_sections = section_files_newer_than(workspace, todo_path)
    if stale_sections:
        preview = ', '.join(stale_sections[:8])
        print(
            f'Blocked: writer-selfloop report is stale for {preview}. Rerun writer-selfloop '
            'after the latest section edits, then retry this unit.',
            file=sys.stderr,
        )
        marker.unlink(missing_ok=True)
        return 2

    # The model-facing Skill owns the rewrite. This deterministic adapter only
    # certifies a fresh writer-selfloop report with no remaining flagged files.
    atomic_write_text(
        marker,
        f'openers varied at {now_iso_seconds()}\nsection_tree_sha256: {section_tree_sha256(workspace)}\n',
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
