from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ALLOWED_MOVES = {
    'setup',
    'thesis',
    'contrast',
    'evidence',
    'evaluation',
    'limitation',
    'synthesis',
    'takeaway',
}


def _slug_unit_id(unit_id: str) -> str:
    raw = str(unit_id or '').strip()
    out: list[str] = []
    for ch in raw:
        out.append(ch if ch.isalnum() else '_')
    safe = ''.join(out).strip('_')
    return f'S{safe}' if safe else 'S'


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r'\n\s*\n', text.strip()) if p.strip()]


def _moves(idx: int, total: int, paragraph: str) -> list[str]:
    low = paragraph.lower()
    moves: list[str] = []
    if idx == 0:
        moves.extend(['setup', 'thesis'])
    if any(tok in low for tok in ['however', 'whereas', 'by contrast', 'while']):
        moves.append('contrast')
    if re.search(r'\[@[^\]]+\]', paragraph):
        moves.append('evidence')
    if any(tok in low for tok in ['benchmark', 'metric', 'protocol', 'evaluation', 'latency', 'cost']):
        moves.append('evaluation')
    if any(tok in low for tok in ['limitation', 'risk', 'constraint', 'caveat']):
        moves.append('limitation')
    if idx >= max(1, total - 2):
        moves.append('synthesis')
    if idx == total - 1:
        moves.append('takeaway')
    return [m for m in ['setup', 'thesis', 'contrast', 'evidence', 'evaluation', 'limitation', 'synthesis', 'takeaway'] if m in set(moves)] or ['evidence']


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

    from tooling.common import atomic_write_text, ensure_dir, load_yaml, now_iso_seconds, parse_semicolon_list, refresh_sections_manifest
    from tooling.quality_gate import _draft_profile, check_unit_outputs, write_quality_report

    workspace = Path(args.workspace).resolve()
    unit_id = str(args.unit_id or 'U1025').strip() or 'U1025'
    inputs = parse_semicolon_list(args.inputs)
    outputs = parse_semicolon_list(args.outputs) or [
        'output/ARGUMENT_SELFLOOP_TODO.md',
        'output/SECTION_ARGUMENT_SUMMARIES.jsonl',
        'output/ARGUMENT_SKELETON.md',
        'sections/sections_manifest.jsonl',
    ]

    todo_rel = next((x for x in outputs if x.endswith('ARGUMENT_SELFLOOP_TODO.md')), 'output/ARGUMENT_SELFLOOP_TODO.md')
    summaries_rel = next((x for x in outputs if x.endswith('SECTION_ARGUMENT_SUMMARIES.jsonl')), 'output/SECTION_ARGUMENT_SUMMARIES.jsonl')
    skeleton_rel = next((x for x in outputs if x.endswith('ARGUMENT_SKELETON.md')), 'output/ARGUMENT_SKELETON.md')
    manifest_rel = next((x for x in outputs if x.endswith('sections_manifest.jsonl')), 'sections/sections_manifest.jsonl')
    todo_path = workspace / todo_rel
    summaries_path = workspace / summaries_rel
    skeleton_path = workspace / skeleton_rel
    ensure_dir(todo_path.parent)

    outline_rel = next((x for x in inputs if x.endswith('outline.yml')), 'outline/outline.yml')
    outline = load_yaml(workspace / outline_rel) if (workspace / outline_rel).exists() else []

    records: list[dict[str, Any]] = []
    watchlist: list[str] = []
    paragraph_floor = {'course_paper': 5, 'survey': 10, 'deep': 11}.get(_draft_profile(workspace), 1)
    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            sec_id = str(sec.get('id') or '').strip()
            sec_title = str(sec.get('title') or '').strip()
            subs = [sub for sub in (sec.get('subsections') or []) if isinstance(sub, dict)]
            for sub in subs:
                sub_id = str(sub.get('id') or '').strip()
                title = str(sub.get('title') or '').strip()
                path = workspace / 'sections' / f'{_slug_unit_id(sub_id)}.md'
                text = path.read_text(encoding='utf-8', errors='ignore') if path.exists() else ''
                paras = _paragraphs(text)
                paragraph_records = []
                for idx, para in enumerate(paras):
                    mv = _moves(idx, len(paras), para)
                    if 'limitation' not in mv and idx == len(paras) - 2:
                        mv = mv + ['limitation']
                    paragraph_records.append({'index': idx + 1, 'moves': mv, 'preview': para[:240].strip()})
                records.append(
                    {
                        'kind': 'h3',
                        'id': sub_id,
                        'title': title,
                        'section_id': sec_id,
                        'section_title': sec_title,
                        'paragraphs': paragraph_records,
                    }
                )
                if not paras:
                    watchlist.append(f'{sub_id} missing prose body')
                elif len(paras) < paragraph_floor:
                    watchlist.append(f'{sub_id} has thin paragraph budget ({len(paras)} < {paragraph_floor})')

    atomic_write_text(summaries_path, '\n'.join(json.dumps(r, ensure_ascii=False) for r in records).rstrip() + ('\n' if records else ''))

    skeleton_lines = [
        '# Argument skeleton',
        '',
        '## Consistency Contract',
        '',
        '- Use one stable naming scheme for comparable agent components, evaluation settings, and benchmark references.',
        '- Keep evaluation claims tied to task, metric, and protocol constraints rather than architecture labels alone.',
        '- Treat limitations as part of the argument, not as detachable boilerplate.',
        '- Keep subsection comparisons chapter-scoped unless a citation is globally in-scope.',
        '',
        '## Chapter dependencies',
        '',
    ]
    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            title = str(sec.get('title') or '').strip()
            subs = [str(sub.get('title') or '').strip() for sub in (sec.get('subsections') or []) if isinstance(sub, dict) and str(sub.get('title') or '').strip()]
            if subs:
                skeleton_lines.append(f'- {title}: ' + '; '.join(subs))
    skeleton_lines.extend(['', '## Watchlist', ''])
    if watchlist:
        skeleton_lines.extend([f'- {item}' for item in watchlist])
    else:
        skeleton_lines.append('- (none)')
    atomic_write_text(skeleton_path, '\n'.join(skeleton_lines).rstrip() + '\n')
    refresh_sections_manifest(workspace, manifest_rel)

    status = 'FAIL' if watchlist else 'PASS'

    todo_lines = [
        '# Argument self-loop report',
        '',
        f'- Status: {status}',
        f'- Generated at: `{now_iso_seconds()}`',
        '',
        '## Summary',
        '',
        '- Section argument summaries and the section manifest were regenerated from the current `sections/` files.',
        '- The consistency contract is a diagnostic snapshot for downstream merge and review.',
        '',
    ]
    if watchlist:
        todo_lines.extend(['## Watchlist', ''])
        todo_lines.extend([f'- {item}' for item in watchlist])
        todo_lines.append('')
    atomic_write_text(todo_path, '\n'.join(todo_lines).rstrip() + '\n')

    issues = check_unit_outputs(skill='argument-selfloop', workspace=workspace, outputs=[todo_rel, summaries_rel, skeleton_rel, manifest_rel])
    if issues:
        write_quality_report(workspace=workspace, unit_id=unit_id, skill='argument-selfloop', issues=issues)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
