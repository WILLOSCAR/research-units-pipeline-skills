from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _sans_citations(text: str) -> str:
    return re.sub(r"\[@[^\]]+\]", "", text or "")




def _sentence_count(text: str) -> int:
    return len([s for s in re.split(r'(?<=[.!?])\s+', (text or '').strip()) if s.strip()])


def _merge_short_body_paragraphs(
    paragraphs: list[str],
    *,
    min_chars: int = 260,
    min_sentences: int = 3,
    min_paragraphs: int = 1,
) -> list[str]:
    min_paragraphs = max(1, int(min_paragraphs))
    if len(paragraphs) <= max(2, min_paragraphs):
        return paragraphs

    lead = paragraphs[:1]
    tail = paragraphs[1:]
    merged: list[str] = []
    pending = ''
    required_body = max(0, min_paragraphs - len(lead))
    for index, para in enumerate(tail):
        clean = para.strip()
        if not clean:
            continue
        pending = clean if not pending else (pending.rstrip() + ' ' + clean)
        remaining = len(tail) - index - 1
        must_flush_for_floor = len(merged) + 1 + remaining <= required_body
        if (
            len(_sans_citations(pending)) >= int(min_chars)
            or _sentence_count(pending) >= int(min_sentences)
            or must_flush_for_floor
        ):
            merged.append(pending.strip())
            pending = ''
    if pending:
        if merged:
            merged[-1] = merged[-1].rstrip() + ' ' + pending.strip()
        else:
            merged.append(pending.strip())
    return lead + merged

def _curate(
    text: str,
    *,
    max_paragraphs: int = 14,
    min_paragraphs: int = 1,
    tail_keep: int = 3,
    min_chars: int = 5200,
) -> str:
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text.strip()) if p.strip()]
    paragraphs = _merge_short_body_paragraphs(paragraphs, min_paragraphs=min_paragraphs)
    tail_keep = max(0, min(int(tail_keep), max(0, len(paragraphs) - 1)))

    # Paragraph compaction must never delete prose. Merge the shortest adjacent
    # body pair until the profile budget is met, preserving text and citation
    # block order exactly. Keep the opening paragraph and closing synthesis
    # region separate whenever the remaining body gives us that choice.
    while len(paragraphs) > int(max_paragraphs):
        protected_tail_start = max(1, len(paragraphs) - tail_keep)
        candidates = list(range(1, max(1, protected_tail_start - 1)))
        if not candidates:
            candidates = list(range(1, len(paragraphs) - 1))
        if not candidates:
            candidates = [0]
        merge_at = min(
            candidates,
            key=lambda idx: len(_sans_citations(paragraphs[idx])) + len(_sans_citations(paragraphs[idx + 1])),
        )
        paragraphs[merge_at : merge_at + 2] = [
            paragraphs[merge_at].rstrip() + ' ' + paragraphs[merge_at + 1].lstrip()
        ]

    return '\n\n'.join(paragraphs).rstrip() + ('\n' if paragraphs else '')


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
    from tooling.common import atomic_write_text, ensure_dir, now_iso_seconds, parse_semicolon_list
    from tooling.quality_gate import _draft_profile

    workspace = Path(args.workspace).resolve()
    outputs = parse_semicolon_list(args.outputs) or ['output/PARAGRAPH_CURATION_REPORT.md', 'sections/paragraphs_curated.refined.ok']
    report_rel = next((x for x in outputs if x.endswith('PARAGRAPH_CURATION_REPORT.md')), 'output/PARAGRAPH_CURATION_REPORT.md')
    marker_rel = next((x for x in outputs if x.endswith('.refined.ok')), 'sections/paragraphs_curated.refined.ok')
    report_path = workspace / report_rel
    marker_path = workspace / marker_rel
    ensure_dir(report_path.parent)
    ensure_dir(marker_path.parent)

    draft_profile = _draft_profile(workspace)
    curation_options = {
        'course_paper': {"max_paragraphs": 7, "min_paragraphs": 5, "tail_keep": 2, "min_chars": 1600},
        'survey': {"max_paragraphs": 12, "min_paragraphs": 10, "tail_keep": 3, "min_chars": 4200},
        'deep': {"max_paragraphs": 13, "min_paragraphs": 11, "tail_keep": 3, "min_chars": 5200},
    }.get(draft_profile, {})
    min_paragraphs = int(curation_options.get('min_paragraphs', 1))
    max_paragraphs = int(curation_options.get('max_paragraphs', 14))
    curated: list[tuple[str, int, int]] = []
    off_budget: list[str] = []
    citation_drift: list[str] = []
    for path in sorted((workspace / 'sections').glob('S*.md')):
        if path.name.endswith('_lead.md') or '_' not in path.stem:
            continue
        text = path.read_text(encoding='utf-8', errors='ignore') if path.exists() else ''
        if text:
            before = len([p for p in re.split(r'\n\s*\n', text.strip()) if p.strip()])
            before_cites = re.findall(r'\[@([^\]]+)\]', text)
            rendered = _curate(text, **curation_options)
            after = len([p for p in re.split(r'\n\s*\n', rendered.strip()) if p.strip()])
            after_cites = re.findall(r'\[@([^\]]+)\]', rendered)
            atomic_write_text(path, rendered)
            rel = str(path.relative_to(workspace))
            curated.append((rel, before, after))
            if after < min_paragraphs or after > max_paragraphs:
                off_budget.append(rel)
            if before_cites != after_cites:
                citation_drift.append(rel)

    status = 'PASS' if not off_budget and not citation_drift else 'FAIL'
    report_lines = [
        '# Paragraph curation report',
        '',
        f'- Status: {status}',
        f'- Draft profile: `{draft_profile}`',
        f'- Curated files: {len(curated)}',
        '',
        '| File | Paragraphs before | Paragraphs after |',
        '|---|---:|---:|',
        *[f'| `{rel}` | {before} | {after} |' for rel, before, after in curated[:20]],
    ]
    if off_budget or citation_drift:
        report_lines.extend([
            '',
            '## Blocking issues',
            *[f'- `{rel}` is outside the `{draft_profile}` paragraph budget ({min_paragraphs}-{max_paragraphs}).' for rel in off_budget],
            *[f'- `{rel}` changed citation block order or membership during compaction.' for rel in citation_drift],
        ])
    report = '\n'.join(report_lines) + '\n'
    atomic_write_text(report_path, report)
    if status == 'PASS':
        atomic_write_text(marker_path, f'paragraphs curated at {now_iso_seconds()}\n')
        return 0
    if marker_path.exists():
        marker_path.unlink()
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
