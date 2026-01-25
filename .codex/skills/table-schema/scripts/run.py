from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _is_placeholder(text: str) -> bool:
    low = (text or '').strip().lower()
    if not low:
        return True
    if '(placeholder)' in low:
        return True
    if '<!-- scaffold' in low:
        return True
    if re.search(r'(?i)\b(?:todo|tbd|fixme)\b', low):
        return True
    if '…' in (text or ''):
        return True
    return False


def _looks_refined(text: str) -> bool:
    if _is_placeholder(text):
        return False
    # Require both index (I*) and appendix (A*) table definitions.
    n = len(re.findall(r'(?m)^##\s+Table\s+[IA]\d+:', text))
    return n >= 4 and len(text.strip()) >= 900


def _read_goal(workspace: Path) -> str:
    goal_path = workspace / 'GOAL.md'
    if not goal_path.exists():
        return ''
    for raw in goal_path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or line.startswith(('-', '>', '<!--')):
            continue
        low = line.lower()
        if '写一句话' in line or 'fill' in low:
            continue
        return line
    return ''


def _backup_existing(path: Path) -> None:
    from tooling.common import backup_existing

    backup_existing(path)


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

    from tooling.common import atomic_write_text, ensure_dir, load_yaml, parse_semicolon_list, read_jsonl

    workspace = Path(args.workspace).resolve()

    inputs = parse_semicolon_list(args.inputs) or [
        'outline/outline.yml',
        'outline/subsection_briefs.jsonl',
        'outline/evidence_drafts.jsonl',
        'GOAL.md',
    ]
    outputs = parse_semicolon_list(args.outputs) or ['outline/table_schema.md']

    out_path = workspace / outputs[0]
    ensure_dir(out_path.parent)

    freeze_marker = out_path.with_name(f'{out_path.name}.refined.ok')
    if out_path.exists() and out_path.stat().st_size > 0:
        if freeze_marker.exists():
            return 0
        _backup_existing(out_path)

    outline = load_yaml(workspace / inputs[0]) if (workspace / inputs[0]).exists() else []
    briefs = read_jsonl(workspace / inputs[1]) if (workspace / inputs[1]).exists() else []
    packs = read_jsonl(workspace / inputs[2]) if (workspace / inputs[2]).exists() else []

    sub_count = 0
    if isinstance(outline, list):
        for section in outline:
            if not isinstance(section, dict):
                continue
            for sub in section.get('subsections') or []:
                if isinstance(sub, dict) and str(sub.get('id') or '').strip():
                    sub_count += 1

    goal = _read_goal(workspace)

    lines: list[str] = [
        '# Table schema (two layers: index + Appendix)',
        '',
        '- Policy: schema-first; design two layers of tables:',
        '  - Index tables: `outline/tables_index.md` (internal; NOT inserted into paper)',
        '  - Appendix tables: `outline/tables_appendix.md` (reader-facing; can be inserted)',
        '- Cell style: short phrases; avoid paragraph cells; prefer 1-2 clauses per cell.',
        '- Citation rule: every row must include at least one citation marker `[@BibKey]`.',
        '',
        f"- Goal (from `GOAL.md`): {goal or '(missing)'}",
        f'- Subsections (H3) detected: {sub_count}',
        f'- Evidence packs: {len([p for p in packs if isinstance(p, dict)])}',
        f'- Briefs: {len([b for b in briefs if isinstance(b, dict)])}',
        '',
        '## Table I1: Subsection map (axes + representative works)',
        '- Question: For each H3, what are the concrete comparison axes and which representative works ground them?',
        '- Row unit: H3 subsection (`sub_id`).',
        '- Columns:',
        '  - Subsection (id + title)',
        '  - Comparison dimensions (3-5 short phrases)',
        '  - Key refs (3-5 cite keys)',
        '- Evidence mapping:',
        '  - Dimensions: `outline/subsection_briefs.jsonl:axes`',
        '  - Key refs: cite keys from evidence pack blocks (snippets/claims/comparisons/limitations)',
        '',
        '## Table I2: Concrete anchors (benchmarks / numbers / caveats)',
        '- Question: What concrete, citation-backed anchor facts should the reader remember for each H3 (benchmarks, numbers, key caveats)?',
        '- Row unit: H3 subsection (`sub_id`).',
        '- Columns:',
        '  - Subsection (id + title)',
        '  - Anchor facts (2-3 short facts; may include benchmark names or metric names)',
        '  - Key refs (3-5 cite keys)',
        '- Evidence mapping:',
        '  - Anchor facts: `outline/anchor_sheet.jsonl:anchors[*].text`',
        '  - Key refs: `outline/anchor_sheet.jsonl:anchors[*].citations` (or pack citations)',
        '',
        '## Table A1: Method/architecture map (representative works)',
        '- Question: What representative agent approaches dominate this area, and what do they assume about the agent loop/interface?',
        '- Row unit: work/system line (a paper or system family).',
        '- Columns (example):',
        '  - Work (short name)',
        '  - Core idea (1 short phrase)',
        '  - Interface / loop assumption (1 short phrase)',
        '  - Key refs (2-4 cite keys)',
        '- Evidence mapping:',
        '  - Core idea / loop assumptions: `outline/evidence_drafts.jsonl` (definitions_setup + concrete_comparisons)',
        '  - Key refs: citations already present in those blocks / anchor sheet',
        '',
        '## Table A2: Evaluation protocol / benchmark map',
        '- Question: Which benchmarks/protocols anchor evaluation, and what task/metric/constraints should the reader track?',
        '- Row unit: benchmark or evaluation setting (fallback: protocol dimension if benchmarks are thin).',
        '- Columns (example):',
        '  - Benchmark / setting',
        '  - Task family + metric (short phrases)',
        '  - Key protocol constraints (budget/cost/latency/steps/tool access/threat model)',
        '  - Key refs (2-4 cite keys)',
        '- Evidence mapping:',
        '  - Protocol details: `outline/evidence_drafts.jsonl:evaluation_protocol` + `outline/anchor_sheet.jsonl`',
        '',
        '## Constraints (for table-filler + appendix-table-writer)',
        '- Index tables are allowed to be exhaustive; Appendix tables must be readable/publishable.',
        '- No placeholders or instruction-like fragments.',
        '- No long prose cells: keep each cell <= ~160 characters when possible.',
        '- Publication voice: no pipeline jargon in Appendix table captions or column labels.',
        '',
    ]

    out_text = '\n'.join(lines).rstrip() + '\n'
    if _is_placeholder(out_text) or not _looks_refined(out_text):
        raise SystemExit('Generated table_schema.md looks unrefined or contains placeholders')

    atomic_write_text(out_path, out_text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
