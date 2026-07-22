from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_rationale_templates() -> dict:
    asset_path = Path(__file__).resolve().parents[1] / 'assets' / 'rationale_templates.json'
    data = json.loads(asset_path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise SystemExit('idea-shortlist-curator/assets/rationale_templates.json must be a JSON object.')
    return data


def _group_candidates(
    screen_rows: list[dict[str, object]],
    *,
    pool_lookup: dict[str, dict[str, object]],
    shortlist_size: int,
    diversity_target: int,
    diversity_axes: list[str],
) -> list[dict[str, object]]:
    chosen: list[dict[str, object]] = []
    seen_by_axis: dict[str, set[str]] = {axis: set() for axis in diversity_axes}
    used_ids: set[str] = set()
    diversity_target = min(max(1, diversity_target), shortlist_size)
    for row in screen_rows:
        direction_id = str(row.get('direction_id') or '').strip()
        card = pool_lookup.get(direction_id) or {}
        axis_values = {
            'cluster': str(card.get('cluster') or row.get('cluster') or '').strip(),
            'direction_type': str(card.get('direction_type') or row.get('direction_type') or '').strip(),
            'program_kind': str(card.get('program_kind') or '').strip(),
        }
        if len(chosen) >= diversity_target:
            break
        if direction_id in used_ids:
            continue
        if any(axis_values.get(axis) and axis_values[axis] not in seen_by_axis[axis] for axis in diversity_axes):
            chosen.append(row)
            for axis in diversity_axes:
                value = axis_values.get(axis, '')
                if value:
                    seen_by_axis[axis].add(value)
            used_ids.add(direction_id)
    for row in screen_rows:
        direction_id = str(row.get('direction_id') or '').strip()
        if direction_id in used_ids:
            continue
        chosen.append(row)
        used_ids.add(direction_id)
        if len(chosen) >= shortlist_size:
            break
    return chosen[:shortlist_size]


def _risk_note(card: dict[str, object], templates: dict) -> str:
    evidence = str(card.get('evidence_confidence') or '')
    program_kind = str(card.get('program_kind') or '').lower()
    confound = str(card.get('main_confound') or 'the main confound')
    for rule in templates.get('risk_notes') or []:
        when = rule.get('when') or {}
        if when.get('evidence_confidence_prefix') and evidence.startswith(str(when.get('evidence_confidence_prefix'))):
            return str(rule.get('text') or '').format(main_confound=confound)
        if when.get('program_kind_contains') and str(when.get('program_kind_contains')).lower() in program_kind:
            return str(rule.get('text') or '').format(main_confound=confound)
    return str(templates.get('risk_note_fallback') or '').format(main_confound=confound)


def _rank_reason(idx: int, cards: list[dict[str, object]], card: dict[str, object], templates: dict) -> str:
    cluster = str(card.get('cluster') or 'this area').lower()
    program_kind = str(card.get('program_kind') or 'research')
    main_confound = str(card.get('main_confound') or 'the main confound')
    time_to_clarity = str(card.get('time_to_clarity') or 'medium')
    risk_note = _risk_note(card, templates)
    if idx == 0:
        return str((templates.get('rank_reasons') or {}).get('lead') or '').format(program_kind=program_kind, cluster=cluster)
    leader = cards[0]
    leader_title = str(leader.get('title') or 'the current #1 direction')
    if idx == 1:
        return str((templates.get('rank_reasons') or {}).get('second') or '').format(leader_title=leader_title, main_confound=main_confound)
    return str((templates.get('rank_reasons') or {}).get('rest') or '').format(program_kind=program_kind, risk_note=risk_note, time_to_clarity=time_to_clarity)


def _prioritized_reason(card: dict[str, object], templates: dict) -> str:
    trimmed_risk_note = _risk_note(card, templates).replace('the ', '').replace('still ', '')
    return str(templates.get('prioritized_reason') or '').format(trimmed_risk_note=trimmed_risk_note)


def _deferred_reason(card: dict[str, object], leads: list[dict[str, object]], templates: dict) -> str:
    lead_clusters = {str(item.get('cluster') or '').strip() for item in leads}
    lead_programs = {str(item.get('program_kind') or '').strip() for item in leads}
    cluster = str(card.get('cluster') or '').strip()
    program_kind = str(card.get('program_kind') or '').strip()
    evidence = str(card.get('evidence_confidence') or '')
    for rule in templates.get('deferred_reasons') or []:
        when = rule.get('when') or {}
        if when.get('same_program_kind_as_lead') and program_kind and program_kind in lead_programs:
            return str(rule.get('text') or '').format(program_kind=program_kind)
        if when.get('same_cluster_as_lead') and cluster and cluster in lead_clusters:
            return str(rule.get('text') or '')
        if when.get('evidence_confidence_prefix') and evidence.startswith(str(when.get('evidence_confidence_prefix'))):
            return str(rule.get('text') or '')
    return str(templates.get('deferred_reason_fallback') or '')


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
    from tooling.ideation import read_jsonl, resolve_idea_contract, shortlist_markdown, uniq_keep_order, write_jsonl, write_markdown

    workspace = Path(args.workspace).resolve()
    if load_workspace_pipeline_spec(workspace) is None:
        raise SystemExit('Missing or invalid active pipeline contract; fix PIPELINE.lock.md and pipeline metadata before ideation C5.')
    templates = _load_rationale_templates()
    outputs = parse_semicolon_list(args.outputs) or ["output/trace/IDEA_SHORTLIST.md"]
    out_rel = outputs[0] if outputs else "output/trace/IDEA_SHORTLIST.md"
    out_path = workspace / out_rel
    jsonl_path = out_path.with_suffix('.jsonl')

    try:
        contract = resolve_idea_contract(workspace)
    except Exception as exc:
        raise SystemExit(f'Invalid ideation runtime contract: {exc}')
    shortlist_size = int(contract['shortlist_size'])
    report_top_n = int(contract['report_top_n'])
    diversity_target = int(contract['lead_diversity_target'])
    diversity_axes = [str(x) for x in contract['lead_diversity_axes'] if str(x)]
    pool = {str(r.get('direction_id') or ''): r for r in read_jsonl(workspace / 'output' / 'trace' / 'IDEA_DIRECTION_POOL.jsonl') if isinstance(r, dict)}
    screened = [
        r
        for r in read_jsonl(workspace / 'output' / 'trace' / 'IDEA_SCREENING_TABLE.jsonl')
        if isinstance(r, dict)
        and str(r.get('recommendation') or '').strip().lower() in {'keep', 'maybe'}
    ]
    screened.sort(key=lambda r: (-float(r.get('total_score') or 0.0), str(r.get('direction_id') or '')))
    chosen = _group_candidates(
        screened,
        pool_lookup=pool,
        shortlist_size=shortlist_size,
        diversity_target=diversity_target,
        diversity_axes=diversity_axes,
    )

    enriched: list[dict[str, object]] = []
    for row in chosen:
        did = str(row.get('direction_id') or '')
        card = dict(pool.get(did) or {})
        card['_screen_row'] = row
        enriched.append(card)

    records: list[dict[str, object]] = []
    for idx, card in enumerate(enriched, start=1):
        row = dict(card.get('_screen_row') or {})
        pids = uniq_keep_order(card.get('paper_ids') or [])[:4]
        record = {
            'rank': idx,
            'direction_id': card.get('direction_id'),
            'cluster': card.get('cluster'),
            'direction_type': card.get('direction_type'),
            'title': card.get('title'),
            'focus_axis': card.get('focus_axis'),
            'main_confound': card.get('main_confound'),
            'program_kind': card.get('program_kind'),
            'contribution_shape': card.get('contribution_shape') or card.get('academic_value'),
            'time_to_clarity': card.get('time_to_clarity') or 'medium',
            'one_line_thesis': card.get('one_line_thesis'),
            'why_interesting': card.get('why_interesting'),
            'literature_suggests': card.get('literature_suggests') or [],
            'closest_prior_gap': card.get('closest_prior_gap') or [],
            'missing_piece': card.get('missing_piece'),
            'possible_variants': card.get('possible_variants') or [],
            'academic_value': card.get('academic_value'),
            'first_probes': card.get('first_probes') or [],
            'what_counts_as_insight': card.get('what_counts_as_insight'),
            'weakness_conditions': card.get('weakness_conditions') or [],
            'kill_criteria': card.get('kill_criteria') or card.get('what_would_change_mind') or [],
            'what_would_change_mind': card.get('what_would_change_mind') or [],
            'best_fit': card.get('best_fit'),
            'why_this_ranks_here': '',
            'evidence_confidence': card.get('evidence_confidence') or 'low-medium',
            'paper_ids': pids,
            'signal_ids': card.get('signal_ids') or [],
            'anchor_reading_notes': card.get('anchor_reading_notes') or [],
            'why_prioritized': '',
            'why_not_prioritized': '',
            '_score_total': row.get('total_score'),
            '_screen_rationale': row.get('rationale'),
        }
        records.append(record)

    for idx, record in enumerate(records):
        record['why_this_ranks_here'] = _rank_reason(idx, records, record, templates)
        record['why_prioritized'] = _prioritized_reason(record, templates)

    leads = records[:report_top_n]
    for record in records[report_top_n:]:
        record['why_not_prioritized'] = _deferred_reason(record, leads, templates)

    for record in records:
        record.pop('_score_total', None)
        record.pop('_screen_rationale', None)

    write_markdown(out_path, shortlist_markdown(records))
    write_jsonl(jsonl_path, records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
