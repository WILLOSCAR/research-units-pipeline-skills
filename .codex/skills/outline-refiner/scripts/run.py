from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def _sha1_text(text: str) -> str:
    return hashlib.sha1((text or '').encode('utf-8', errors='ignore')).hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='ignore') if path.exists() else ''


def _backup_existing(path: Path) -> None:
    from tooling.common import backup_existing

    backup_existing(path)

def _append_jsonl(path: Path, rec: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _generic_axis(x: str) -> bool:
    x = (x or '').strip().lower()
    x = ' '.join(x.split())
    generic = {
        'mechanism / architecture',
        'data / training setup',
        'evaluation protocol',
        'evaluation protocol (benchmarks / metrics / human)',
        'evaluation protocol (datasets / metrics / human)',
        'compute / efficiency',
        'efficiency / compute',
        'failure modes / limitations',
    }
    return x in generic


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--unit-id', default='')
    parser.add_argument('--inputs', default='')
    parser.add_argument('--outputs', default='')
    parser.add_argument('--checkpoint', default='')
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(repo_root))

    from tooling.common import atomic_write_text, load_yaml, now_iso_seconds, parse_semicolon_list, read_jsonl, read_tsv

    workspace = Path(args.workspace).resolve()

    inputs = parse_semicolon_list(args.inputs) or [
        'outline/outline.yml',
        'outline/mapping.tsv',
        'papers/paper_notes.jsonl',
        'outline/subsection_briefs.jsonl',
        'GOAL.md',
    ]
    outputs = parse_semicolon_list(args.outputs) or ['outline/coverage_report.md', 'outline/outline_state.jsonl']

    outline_rel = inputs[0] if len(inputs) >= 1 else 'outline/outline.yml'
    mapping_rel = inputs[1] if len(inputs) >= 2 else 'outline/mapping.tsv'

    notes_rel = ''
    briefs_rel = ''
    goal_rel = ''
    for rel in inputs[2:]:
        rel = (rel or '').strip()
        if rel.endswith('papers/paper_notes.jsonl') or rel.endswith('paper_notes.jsonl'):
            notes_rel = rel
        elif rel.endswith('outline/subsection_briefs.jsonl') or rel.endswith('subsection_briefs.jsonl'):
            briefs_rel = rel
        elif rel.endswith('GOAL.md'):
            goal_rel = rel

    report_rel = outputs[0] if outputs else 'outline/coverage_report.md'
    state_rel = outputs[1] if len(outputs) >= 2 else 'outline/outline_state.jsonl'

    report_path = workspace / report_rel
    state_path = workspace / state_rel
    report_path.parent.mkdir(parents=True, exist_ok=True)

    freeze_marker = report_path.with_name('coverage_report.refined.ok')
    if report_path.exists() and report_path.stat().st_size > 0 and freeze_marker.exists():
        # Still append a state record so the pipeline has a timeline of runs.
        rec = {
            'generated_at': now_iso_seconds(),
            'outline_sha1': _sha1_text(_read_text(workspace / outline_rel)),
            'mapping_sha1': _sha1_text(_read_text(workspace / mapping_rel)),
            'status': 'skipped_due_to_freeze_marker',
        }
        _append_jsonl(state_path, rec)
        return 0

    if report_path.exists() and report_path.stat().st_size > 0:
        _backup_existing(report_path)

    outline = load_yaml(workspace / outline_rel) if (workspace / outline_rel).exists() else []
    subsections: list[dict[str, str]] = []
    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            for sub in sec.get('subsections') or []:
                if not isinstance(sub, dict):
                    continue
                sid = str(sub.get('id') or '').strip()
                title = str(sub.get('title') or '').strip()
                if sid and title:
                    subsections.append({'sub_id': sid, 'title': title})

    mapping_rows = read_tsv(workspace / mapping_rel) if (workspace / mapping_rel).exists() else []
    pids_by_sub: dict[str, list[str]] = {}
    for row in mapping_rows:
        if not isinstance(row, dict):
            continue
        sid = str(row.get('section_id') or '').strip()
        pid = str(row.get('paper_id') or '').strip()
        if not sid or not pid:
            continue
        pids_by_sub.setdefault(sid, [])
        if pid not in pids_by_sub[sid]:
            pids_by_sub[sid].append(pid)

    # Evidence levels from notes (best-effort).
    lvl_by_pid: dict[str, str] = {}
    if notes_rel and (workspace / notes_rel).exists():
        for rec in read_jsonl(workspace / notes_rel):
            if not isinstance(rec, dict):
                continue
            pid = str(rec.get('paper_id') or '').strip()
            lvl = str(rec.get('evidence_level') or '').strip().lower()
            if pid and lvl:
                lvl_by_pid[pid] = lvl

    # Axes specificity from briefs (best-effort).
    axes_by_sub: dict[str, list[str]] = {}
    if briefs_rel and (workspace / briefs_rel).exists():
        for rec in read_jsonl(workspace / briefs_rel):
            if not isinstance(rec, dict):
                continue
            sid = str(rec.get('sub_id') or '').strip()
            axes = rec.get('axes') or []
            if sid and isinstance(axes, list):
                axes_by_sub[sid] = [str(a).strip() for a in axes if str(a).strip()]

    usage: dict[str, int] = {}
    for sid, pids in pids_by_sub.items():
        for pid in pids:
            usage[pid] = usage.get(pid, 0) + 1

    top_reuse = sorted(usage.items(), key=lambda kv: (-kv[1], kv[0]))[:10]

    rows: list[dict[str, Any]] = []
    for sub in subsections:
        sid = sub['sub_id']
        title = sub['title']
        pids = pids_by_sub.get(sid) or []
        lvls = [lvl_by_pid.get(pid, '') for pid in pids]
        fulltext = sum(1 for x in lvls if x == 'fulltext')
        abstract = sum(1 for x in lvls if x == 'abstract')
        title_only = sum(1 for x in lvls if x == 'title')

        axes = axes_by_sub.get(sid) or []
        generic_n = sum(1 for a in axes if _generic_axis(a))
        specific_n = max(0, len(axes) - generic_n)

        rows.append(
            {
                'sub_id': sid,
                'title': title,
                'mapped_papers': len(pids),
                'unique_papers': len(set(pids)),
                'evidence_levels': {'fulltext': fulltext, 'abstract': abstract, 'title': title_only} if lvls else {},
                'axes_total': len(axes) if axes else 0,
                'axes_specific': specific_n if axes else 0,
                'axes_generic': generic_n if axes else 0,
                'reuse_max': max([usage.get(pid, 0) for pid in pids], default=0),
            }
        )

    # Render report (bullets + a small table).
    lines: list[str] = [
        '# Coverage report (planner pass)',
        '',
        '- Guardrail: NO PROSE; this is a diagnostic artifact, not survey writing.',
        f"- Subsections (H3): {len(subsections)}",
        f"- Mapping rows: {len(mapping_rows)}",
        f"- Unique mapped papers: {len(usage)}",
    ]

    if top_reuse:
        top_txt = ', '.join([f"{pid}×{cnt}" for pid, cnt in top_reuse[:6]])
        lines.append(f"- Most reused papers: {top_txt}")

    lines.extend(['', '## Per-subsection summary', ''])

    lines.append('| Subsection | #papers | Evidence levels | Axes (specific/generic) | Max reuse |')
    lines.append('|---|---:|---|---:|---:|')
    by_sid = {r['sub_id']: r for r in rows}
    for sub in subsections:
        r = by_sid.get(sub['sub_id']) or {}
        ev = r.get('evidence_levels') or {}
        ev_txt = '—'
        if isinstance(ev, dict) and ev:
            ev_txt = f"fulltext={ev.get('fulltext', 0)}, abstract={ev.get('abstract', 0)}, title={ev.get('title', 0)}"
        axes_txt = '—'
        if r.get('axes_total'):
            axes_txt = f"{r.get('axes_specific', 0)}/{r.get('axes_generic', 0)}"
        lines.append(
            f"| {sub['sub_id']} {sub['title']} | {r.get('mapped_papers', 0)} | {ev_txt} | {axes_txt} | {r.get('reuse_max', 0)} |"
        )

    # Flags (bullets only).
    issues: list[str] = []
    low_axes = [r for r in rows if int(r.get('axes_total') or 0) and int(r.get('axes_specific') or 0) < 2]
    if low_axes:
        sample = ', '.join([f"{r['sub_id']}" for r in low_axes[:6]])
        issues.append(f"Some H3 briefs still look generic (specific axes <2): {sample}")

    high_reuse = [r for r in rows if int(r.get('reuse_max') or 0) >= 6]
    if high_reuse:
        sample = ', '.join([f"{r['sub_id']}" for r in high_reuse[:6]])
        issues.append(f"Mapping shows high reuse hotspots (a paper reused >=6× within a subsection set): {sample}")

    if issues:
        lines.extend(['', '## Flags (actionable)', ''])
        for it in issues:
            lines.append(f"- {it}")
        lines.extend(
            [
                '',
                '## Suggested next actions (still NO PROSE)',
                '- If reuse hotspots are high: expand `core_set.csv` (increase core size) or rerun `section-mapper` with stronger diversity penalty.',
                '- If axes are generic: regenerate `subsection_briefs.jsonl` after improving notes/evidence bank; avoid copying outline scaffold bullets.',
                '- If evidence is mostly abstract-only: consider `evidence_mode: fulltext` for a smaller subset to strengthen key comparisons.',
            ]
        )

    atomic_write_text(report_path, "\n".join(lines).rstrip() + "\n")

    state_rec = {
        'generated_at': now_iso_seconds(),
        'outline_sha1': _sha1_text(_read_text(workspace / outline_rel)),
        'mapping_sha1': _sha1_text(_read_text(workspace / mapping_rel)),
        'subsections': len(subsections),
        'mapping_rows': len(mapping_rows),
        'unique_papers': len(usage),
        'top_reuse': [{'paper_id': pid, 'count': cnt} for pid, cnt in top_reuse],
        'flags': issues,
    }
    _append_jsonl(state_path, state_rec)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())