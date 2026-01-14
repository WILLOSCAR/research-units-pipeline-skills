from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def _is_placeholder(text: str) -> bool:
    low = (text or '').strip().lower()
    if not low:
        return True
    if '(placeholder)' in low:
        return True
    if '<!-- scaffold' in low:
        return True
    if '…' in text:
        return True
    if re.search(r'(?i)\b(?:todo|tbd|fixme)\b', low):
        return True
    return False


def _backup_existing(path: Path) -> None:
    from tooling.common import backup_existing

    backup_existing(path)

def _tokenize(text: str) -> set[str]:
    toks = set()
    for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", (text or '').lower()):
        if t in {'the', 'and', 'with', 'from', 'into', 'this', 'that', 'these', 'those', 'their'}:
            continue
        toks.add(t)
    return toks


def _score_item(item: dict[str, Any], *, want: set[str]) -> float:
    kind = str(item.get('claim_type') or '').strip().lower()
    tags = set([str(t).strip().lower() for t in (item.get('tags') or []) if str(t).strip()])
    snippet = str(item.get('snippet') or '')

    score = 0.0
    if kind == 'result':
        score += 3.0
    elif kind == 'method':
        score += 2.0
    elif kind == 'limitation':
        score += 1.5
    elif kind == 'summary':
        score += 1.0
    else:
        score += 0.5

    if 'evaluation' in tags and any(k in want for k in ['benchmark', 'benchmarks', 'dataset', 'datasets', 'metric', 'metrics', 'evaluation']):
        score += 1.0
    if 'numbers' in tags:
        score += 0.5
    if 'security' in tags and any(k in want for k in ['security', 'attack', 'threat', 'guardrail', 'sandbox']):
        score += 0.8
    if 'tooling' in tags and any(k in want for k in ['tool', 'tools', 'api', 'mcp', 'schema', 'function']):
        score += 0.6

    # Light keyword overlap against the snippet itself.
    snip_toks = _tokenize(snippet)
    score += 0.06 * len(snip_toks & want)

    return score


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

    from tooling.common import atomic_write_text, ensure_dir, now_iso_seconds, parse_semicolon_list, read_jsonl, read_tsv, write_jsonl
    from tooling.quality_gate import _draft_profile, _pipeline_profile

    workspace = Path(args.workspace).resolve()

    profile = _pipeline_profile(workspace)
    draft_profile = _draft_profile(workspace)

    inputs = parse_semicolon_list(args.inputs) or [
        'outline/subsection_briefs.jsonl',
        'outline/mapping.tsv',
        'papers/evidence_bank.jsonl',
        'citations/ref.bib',
    ]
    outputs = parse_semicolon_list(args.outputs) or ['outline/evidence_bindings.jsonl', 'outline/evidence_binding_report.md']

    briefs_path = workspace / inputs[0]
    mapping_path = workspace / inputs[1]
    bank_path = workspace / inputs[2]

    out_path = workspace / (outputs[0] if outputs else 'outline/evidence_bindings.jsonl')
    report_path = workspace / (outputs[1] if len(outputs) >= 2 else 'outline/evidence_binding_report.md')

    ensure_dir(out_path.parent)
    ensure_dir(report_path.parent)

    freeze_marker = out_path.with_name('evidence_bindings.refined.ok')
    if out_path.exists() and out_path.stat().st_size > 0 and freeze_marker.exists():
        return 0
    if out_path.exists() and out_path.stat().st_size > 0:
        _backup_existing(out_path)

    briefs = read_jsonl(briefs_path)
    briefs = [b for b in briefs if isinstance(b, dict) and str(b.get('sub_id') or '').strip()]
    if not briefs:
        raise SystemExit(f"Missing or empty briefs: {briefs_path}")

    bank = read_jsonl(bank_path)
    items = [it for it in bank if isinstance(it, dict) and str(it.get('evidence_id') or '').strip()]
    if not items:
        raise SystemExit(f"Missing or empty evidence bank: {bank_path}")

    items_by_pid: dict[str, list[dict[str, Any]]] = {}
    by_eid: dict[str, dict[str, Any]] = {}
    for it in items:
        eid = str(it.get('evidence_id') or '').strip()
        pid = str(it.get('paper_id') or '').strip()
        if not eid or not pid:
            continue
        by_eid[eid] = it
        items_by_pid.setdefault(pid, []).append(it)

    # mapping.tsv: section_id -> paper_ids
    pids_by_sub: dict[str, list[str]] = {}
    for row in read_tsv(mapping_path):
        sid = str(row.get('section_id') or '').strip()
        pid = str(row.get('paper_id') or '').strip()
        if not sid or not pid:
            continue
        pids_by_sub.setdefault(sid, [])
        if pid not in pids_by_sub[sid]:
            pids_by_sub[sid].append(pid)

    records: list[dict[str, Any]] = []

    # Selection params.
    k = 14
    max_per_paper = 3

    if profile == "arxiv-survey":
        if draft_profile == "deep":
            k = 24
        elif draft_profile == "lite":
            k = 12
        else:
            k = 18

    flags: list[str] = []
    for brief in briefs:
        sid = str(brief.get('sub_id') or '').strip()
        title = str(brief.get('title') or '').strip()
        rq = str(brief.get('rq') or '').strip()
        axes = brief.get('axes') or []
        axes_txt = ' '.join([str(a) for a in axes])

        want = _tokenize(f"{title} {rq} {axes_txt}")

        pids = pids_by_sub.get(sid) or []
        if not pids:
            # Fallback: use cluster paper_ids if mapping is missing.
            for c in brief.get('clusters') or []:
                if isinstance(c, dict):
                    for pid in c.get('paper_ids') or []:
                        pid = str(pid).strip()
                        if pid and pid not in pids:
                            pids.append(pid)

        candidates: list[dict[str, Any]] = []
        for pid in pids:
            candidates.extend(items_by_pid.get(pid) or [])

        scored: list[tuple[float, str, dict[str, Any]]] = []
        for it in candidates:
            eid = str(it.get('evidence_id') or '').strip()
            if not eid:
                continue
            scored.append((_score_item(it, want=want), eid, it))

        scored.sort(key=lambda t: (-t[0], t[1]))

        selected: list[dict[str, Any]] = []
        used_paper: dict[str, int] = {}
        used_kind: dict[str, int] = {}

        def pick(it: dict[str, Any]) -> None:
            pid = str(it.get('paper_id') or '').strip()
            kind = str(it.get('claim_type') or '').strip().lower()
            if not pid:
                return
            if used_paper.get(pid, 0) >= max_per_paper:
                return
            # Avoid too many limitations (often boilerplate).
            if kind == 'limitation' and used_kind.get(kind, 0) >= 3:
                return
            eid = str(it.get('evidence_id') or '').strip()
            if not eid:
                return
            if any(e.get('evidence_id') == eid for e in selected):
                return
            selected.append(it)
            used_paper[pid] = used_paper.get(pid, 0) + 1
            used_kind[kind] = used_kind.get(kind, 0) + 1

        # Seed diversity: try to ensure at least 1 method + 2 results + 1 limitation if available.
        for kind in ['method', 'result', 'result', 'limitation']:
            for _, _, it in scored:
                if str(it.get('claim_type') or '').strip().lower() != kind:
                    continue
                pick(it)
                break

        for _, _, it in scored:
            if len(selected) >= k:
                break
            pick(it)

        eids = [str(it.get('evidence_id') or '').strip() for it in selected if str(it.get('evidence_id') or '').strip()]
        bibkeys = []
        for it in selected:
            bk = str(it.get('bibkey') or '').strip()
            if bk and bk not in bibkeys:
                bibkeys.append(bk)

        mapped_bibkeys: list[str] = []
        for pid in pids:
            for it in items_by_pid.get(pid) or []:
                bk = str(it.get('bibkey') or '').strip()
                if bk and bk not in mapped_bibkeys:
                    mapped_bibkeys.append(bk)

        # Coverage stats.
        by_kind: dict[str, int] = {}
        by_lvl: dict[str, int] = {}
        for it in selected:
            by_kind[str(it.get('claim_type') or 'unknown')] = by_kind.get(str(it.get('claim_type') or 'unknown'), 0) + 1
            by_lvl[str(it.get('evidence_level') or 'unknown')] = by_lvl.get(str(it.get('evidence_level') or 'unknown'), 0) + 1

        if len(eids) < 6:
            flags.append(f"{sid}: too few evidence_ids selected ({len(eids)}); evidence bank may be sparse for mapped papers")

        records.append(
            {
                'sub_id': sid,
                'title': title,
                'paper_ids': pids,
                'mapped_bibkeys': mapped_bibkeys,
                'bibkeys': bibkeys,
                'evidence_ids': eids,
                'evidence_counts': {
                    'selected_total': len(eids),
                    'by_claim_type': by_kind,
                    'by_evidence_level': by_lvl,
                },
                'generated_at': now_iso_seconds(),
            }
        )

    write_jsonl(out_path, records)

    # Summary report.
    lines: list[str] = [
        '# Evidence binding report (NO PROSE)',
        '',
        '- Policy: bind evidence IDs to subsections so writer/auditor can stay evidence-first.',
        f"- Subsections: {len(records)}",
        f"- Evidence bank items: {len(items)}",
        '',
        '## Per-subsection stats',
        '',
        '| Subsection | evidence_ids | claim_type mix | evidence_level mix |',
        '|---|---:|---|---|',
    ]

    for rec in sorted(records, key=lambda r: tuple(int(p) for p in str(r.get('sub_id') or '0').split('.') if p.isdigit())):
        sid = str(rec.get('sub_id') or '').strip()
        title = str(rec.get('title') or '').strip()
        cnt = rec.get('evidence_counts') or {}
        by_kind = cnt.get('by_claim_type') or {}
        by_lvl = cnt.get('by_evidence_level') or {}
        kind_txt = ', '.join([f"{k}={v}" for k, v in sorted(by_kind.items())]) if isinstance(by_kind, dict) else '—'
        lvl_txt = ', '.join([f"{k}={v}" for k, v in sorted(by_lvl.items())]) if isinstance(by_lvl, dict) else '—'
        lines.append(f"| {sid} {title} | {cnt.get('selected_total', 0)} | {kind_txt} | {lvl_txt} |")

    if flags:
        lines.extend(['', '## Flags', ''])
        for f in flags[:20]:
            lines.append(f"- {f}")

    atomic_write_text(report_path, "\n".join(lines).rstrip() + "\n")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
