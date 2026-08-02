from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists() or path.stat().st_size <= 0:
        return out
    for raw in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size <= 0:
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8', errors='ignore'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _uniq(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item or '').strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _cites(keys: list[str]) -> str:
    ks = _uniq(keys)
    return f"[@{'; '.join(ks)}]" if ks else ''


def _cite_range(keys: list[str], start: int, stop: int) -> str:
    return _cites(keys[start:stop])


def _sanitize_goal_text(text: str) -> str:
    s = ' '.join(str(text or '').strip().split())
    if not s:
        return ''
    s = re.sub(r'(?i)\bwith\b[^.]{0,160}\b(?:latex|pdf|output|writeup|draft|paper)\b.*$', '', s).strip(' ,;:-')
    s = re.sub(r'(?i)\b(?:latex|pdf)\s*/\s*(?:latex|pdf)\s+output\b.*$', '', s).strip(' ,;:-')
    s = re.sub(r'(?i)\b(?:survey|review|overview)\b(?:\s+paper)?$', '', s).strip(' ,;:-')
    return s or 'the approved survey topic'


def _goal_text(path: Path, *, subject_normalizer=None) -> str:
    if not path.exists():
        return 'the approved survey topic'
    lines = [
        ln.strip()
        for ln in path.read_text(encoding='utf-8', errors='ignore').splitlines()
        if ln.strip() and not ln.startswith('#')
    ]
    raw = lines[0] if lines else ''
    if subject_normalizer is not None:
        normalized = str(subject_normalizer(raw) or '').strip()
        if normalized:
            return normalized
    return _sanitize_goal_text(raw)


def _parse_stats(retrieval_path: Path, core_path: Path, queries_path: Path) -> tuple[str, str, str, str]:
    time_window = 'recent years'
    candidate_pool = 'a large candidate pool'
    evidence_mode = 'abstract-level evidence'
    if retrieval_path.exists():
        text = retrieval_path.read_text(encoding='utf-8', errors='ignore')
        m = re.search(r'Imported/collected records .*?`(\d+)`', text)
        if m:
            candidate_pool = f"a candidate pool of {m.group(1)} records"
        m = re.search(r'Time window:\s*`([^`]*)`\.\.`([^`]*)`', text)
        if m:
            left = m.group(1).strip()
            right = m.group(2).strip()
            if left and right:
                time_window = f'{left}–{right}'
            elif left:
                time_window = f'since {left}'
    core_set_size = 'a 300-paper core set'
    if core_path.exists():
        rows = max(0, sum(1 for _ in core_path.open(encoding='utf-8', errors='ignore')) - 1)
        if rows > 0:
            core_set_size = f'a {rows}-paper core set'
    if queries_path.exists():
        q = queries_path.read_text(encoding='utf-8', errors='ignore')
        m = re.search(r'(?im)^-\s*evidence_mode\s*:\s*([^#\n]+)', q)
        if m:
            raw_mode = m.group(1).strip().strip('"').strip("'").lower()
            if raw_mode == 'fulltext':
                evidence_mode = 'full-text evidence'
            elif raw_mode == 'abstract':
                evidence_mode = 'abstract-level evidence'
            elif raw_mode:
                evidence_mode = raw_mode
    return time_window, candidate_pool, core_set_size, evidence_mode


def _detect_domain(workspace: Path) -> str | None:
    package_root = Path(__file__).resolve().parents[1]
    domain_dir = package_root / 'assets' / 'domain_templates'
    if not domain_dir.is_dir():
        return None
    corpus_parts: list[str] = []
    for name in ('GOAL.md', 'queries.md'):
        p = workspace / name
        if p.exists():
            corpus_parts.append(p.read_text(encoding='utf-8', errors='ignore').lower())
    corpus = ' '.join(corpus_parts)
    if not corpus.strip():
        return None
    for pack_path in sorted(domain_dir.glob('*.json')):
        pack = _load_json(pack_path)
        triggers = pack.get('topic_triggers') or {}
        group_a = [str(t).lower() for t in (triggers.get('trigger_group_a') or []) if str(t).strip()]
        group_b = [str(t).lower() for t in (triggers.get('trigger_group_b') or []) if str(t).strip()]
        if not group_a or not group_b:
            continue
        if any(t in corpus for t in group_a) and any(t in corpus for t in group_b):
            return str(pack.get('domain_id') or pack_path.stem).strip() or pack_path.stem
    return None


def _load_domain_overlay(domain_id: str) -> dict[str, Any]:
    package_root = Path(__file__).resolve().parents[1]
    return _load_json(package_root / 'assets' / 'domain_templates' / f'{domain_id}.json')


def _merge_template_bank(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    if isinstance(overlay.get('hook_banks'), dict):
        hook_banks = dict(base.get('hook_banks') or {})
        for section_name, section_bank in overlay.get('hook_banks', {}).items():
            if isinstance(section_bank, dict):
                hook_banks[str(section_name)] = section_bank
        merged['hook_banks'] = hook_banks
    for key in ('abstract_sentences', 'discussion_paragraphs', 'conclusion_paragraphs', 'introduction_paragraphs', 'related_work_paragraphs'):
        if key in overlay:
            merged[key] = overlay[key]
    if isinstance(overlay.get('headings'), dict):
        headings = dict(base.get('headings') or {})
        headings.update({str(k): v for k, v in overlay.get('headings', {}).items()})
        merged['headings'] = headings
    return merged


def _chapter_path_text(chapter_titles: list[str]) -> str:
    titles = [re.sub(r'\s+', ' ', str(t or '').strip()) for t in chapter_titles if str(t or '').strip()]
    if not titles:
        return 'the main comparison chapters'
    if len(titles) == 1:
        return titles[0]
    if len(titles) == 2:
        return f'{titles[0]} and {titles[1]}'
    if len(titles) == 3:
        return f'{titles[0]}, {titles[1]}, and {titles[2]}'
    tail = titles[-1].lower() if titles[-1] else 'later deployment issues'
    return f'{titles[0]}, {titles[1]}, {titles[2]}, and later chapters on {tail}'


def _series_text(items: list[str]) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = re.sub(r'\s+', ' ', str(item or '').strip())
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        values.append(value)
    if not values:
        return ''
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f'{values[0]} and {values[1]}'
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def _prose_surface_text(text: str, *, limit: int = 120) -> str:
    s = str(text or '').strip()
    if not s:
        return ''
    s = re.sub(r'\s*/\s*', ' and ', s)
    s = re.sub(r'\s*&\s*', ' and ', s)
    s = re.sub(r'\s+', ' ', s).strip(' ,;:')
    if len(s) <= limit:
        return s
    clipped = s[:limit].rsplit(' ', 1)[0].strip()
    return clipped if clipped else s[:limit].strip()


def _chapter_theme_phrase(title: str, projection: dict[str, Any] | None = None) -> str:
    low = re.sub(r'\s+', ' ', str(title or '').strip().lower())
    if not low:
        return ''
    for rule in (projection or {}).get('chapter_theme_rules') or []:
        if not isinstance(rule, dict):
            continue
        terms = [str(x).strip().lower() for x in (rule.get('match_any') or []) if str(x).strip()]
        emitted = re.sub(r'\s+', ' ', str(rule.get('emit') or '').strip())
        if terms and emitted and any(term in low for term in terms):
            return emitted
    return low.replace('&', 'and')


def _chapter_contexts(
    outline: Any,
    chapter_briefs: list[dict[str, Any]],
    *,
    intro_id: str,
    related_id: str,
    projection: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    briefs_by_sec = {}
    for rec in chapter_briefs:
        sid = str(rec.get('section_id') or '').strip()
        if sid:
            briefs_by_sec[sid] = rec

    chapters: list[dict[str, str]] = []
    if not isinstance(outline, list):
        return chapters

    for sec in outline:
        if not isinstance(sec, dict):
            continue
        sid = str(sec.get('id') or '').strip()
        title = re.sub(r'\s+', ' ', str(sec.get('title') or '').strip())
        if not sid or not title:
            continue
        low = title.lower()
        if sid in {intro_id, related_id} or low in {'discussion', 'conclusion'}:
            continue
        brief = briefs_by_sec.get(sid) or {}
        throughline = [str(x).strip() for x in (brief.get('throughline') or []) if str(x).strip()]
        key_contrasts = [str(x).strip() for x in (brief.get('key_contrasts') or []) if str(x).strip()]
        focus_policy = (projection or {}).get('chapter_focus_policy') or {}
        throughline_take = max(1, int(focus_policy.get('throughline_take') or 2))
        contrast_take = max(1, int(focus_policy.get('contrast_take') or 1))
        surface_limit = max(60, int(focus_policy.get('surface_limit') or 120))
        focus_summary = _prose_surface_text(', '.join(throughline[:throughline_take]) if throughline else title.lower(), limit=surface_limit)
        key_contrast = _prose_surface_text(', '.join(key_contrasts[:contrast_take]) if key_contrasts else focus_summary or title.lower(), limit=surface_limit)
        chapters.append(
            {
                'section_id': sid,
                'chapter_title': title,
                'chapter_title_lower': title.lower(),
                'chapter_theme': _chapter_theme_phrase(title, projection),
                'chapter_focus_summary': focus_summary,
                'chapter_key_contrast': key_contrast,
            }
        )
    return chapters


def _group_chapter_contexts(
    chapters: list[dict[str, str]],
    *,
    section_name: str,
    projection: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    grouping = (projection or {}).get('chapter_grouping_policy') or {}
    section_override = ((grouping.get('section_overrides') or {}).get(section_name) or {}) if isinstance(grouping, dict) else {}
    max_groups = max(1, int(section_override.get('max_groups') or grouping.get('default_max_groups') or 2))
    min_group_size = max(1, int(grouping.get('min_group_size') or 2))
    if len(chapters) <= max_groups:
        return chapters
    group_size = max(min_group_size, (len(chapters) + max_groups - 1) // max_groups)
    grouped: list[dict[str, str]] = []
    for idx in range(0, len(chapters), group_size):
        chunk = chapters[idx: idx + group_size]
        if not chunk:
            continue
        titles = [c.get('chapter_title', '') for c in chunk if c.get('chapter_title')]
        themes = [_prose_surface_text(c.get('chapter_theme', '')) for c in chunk if c.get('chapter_theme')]
        focuses = [_prose_surface_text(c.get('chapter_focus_summary', '')) for c in chunk if c.get('chapter_focus_summary')]
        contrasts = [_prose_surface_text(c.get('chapter_key_contrast', '')) for c in chunk if c.get('chapter_key_contrast')]
        chapter_title = _chapter_path_text(titles) if titles else 'adjacent parts of the field'
        grouped.append(
            {
                'section_id': ','.join(str(c.get('section_id') or '').strip() for c in chunk if str(c.get('section_id') or '').strip()),
                'chapter_title': chapter_title,
                'chapter_title_lower': chapter_title.lower(),
                'chapter_theme': _series_text([t for t in themes if t]) or 'adjacent parts of the field',
                'chapter_focus_summary': _series_text([f for f in focuses if f][:2]) or chapter_title.lower(),
                'chapter_key_contrast': _series_text([c for c in contrasts if c][:2]) or _series_text([f for f in focuses if f][:2]) or chapter_title.lower(),
            }
        )
    return grouped[:max_groups]


def _global_values(
    *,
    goal: str,
    time_window: str,
    candidate_pool: str,
    core_set_size: str,
    evidence_mode: str,
    chapter_contexts: list[dict[str, str]],
    projection: dict[str, Any] | None = None,
) -> dict[str, str]:
    chapter_titles = [chapter['chapter_title'] for chapter in chapter_contexts if chapter.get('chapter_title')]
    title_join = _chapter_path_text(chapter_titles)
    chapter_themes = [chapter.get('chapter_theme', '') for chapter in chapter_contexts if chapter.get('chapter_theme')]
    global_policy = (projection or {}).get('global_value_projection') or {}
    lens_take = max(1, int(global_policy.get('lens_take') or 4))
    comparison_take = max(1, int(global_policy.get('comparison_take') or 3))

    lens_bits: list[str] = []
    compare_bits: list[str] = []
    for chapter in chapter_contexts:
        focus = str(chapter.get('chapter_focus_summary') or '').strip()
        contrast = str(chapter.get('chapter_key_contrast') or '').strip()
        if focus and focus not in lens_bits:
            lens_bits.append(focus)
        if contrast and contrast not in compare_bits:
            compare_bits.append(contrast)
    lens_summary = '; '.join(lens_bits[:lens_take]) if lens_bits else 'mechanism, protocol, transfer, and deployment conditions'
    comparison_summary = ', '.join(compare_bits[:comparison_take]) if compare_bits else 'mechanism, protocol, and limitations'
    theme_summary = _series_text(chapter_themes) if chapter_themes else 'problem settings, model design, data strategy, and evaluation constraints'
    if chapter_themes:
        if len(chapter_themes) == 1:
            chapter_flow_summary = chapter_themes[0]
        elif len(chapter_themes) == 2:
            chapter_flow_summary = f'from {chapter_themes[0]} to {chapter_themes[1]}'
        else:
            chapter_flow_summary = f"from {chapter_themes[0]}, through {', '.join(chapter_themes[1:-1])}, to {chapter_themes[-1]}"
    else:
        chapter_flow_summary = 'from problem settings, through design and data choices, to evaluation and deployment constraints'

    return {
        'goal': goal,
        'time_window': time_window,
        'candidate_pool': candidate_pool,
        'core_set_size': core_set_size,
        'evidence_mode': evidence_mode,
        'evidence_note': f'{core_set_size} using {evidence_mode}',
        'chapter_titles_joined': title_join,
        'chapter_path': title_join,
        'scope_boundary': title_join,
        'lens_summary': lens_summary,
        'comparison_summary': comparison_summary,
        'theme_summary': theme_summary,
        'chapter_flow_summary': chapter_flow_summary,
    }


def _stem_key(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9']+", re.sub(r'\s+', ' ', str(text or '').strip().lower()))[:4]
    return ' '.join(words)


def _render_choice(raw: Any, values: dict[str, str], *, seed_key: str, stem_counts: dict[str, int]) -> str:
    if isinstance(raw, list):
        options = [str(item or '').strip() for item in raw if str(item or '').strip()]
    else:
        single = str(raw or '').strip()
        options = [single] if single else []
    if not options:
        return ''

    digest = hashlib.sha1(seed_key.encode('utf-8', errors='ignore')).hexdigest()
    start = int(digest[:12], 16) % len(options)
    ordered = options[start:] + options[:start]
    best = ordered[0].format_map(values)
    best_stem = _stem_key(best)
    best_count = stem_counts.get(best_stem, 0) if best_stem else 0

    for option in ordered:
        candidate = option.format_map(values)
        stem = _stem_key(candidate)
        count = stem_counts.get(stem, 0) if stem else 0
        if count < best_count:
            best = candidate
            best_stem = stem
            best_count = count
        if stem and count == 0:
            best = candidate
            best_stem = stem
            break

    if best_stem:
        stem_counts[best_stem] = stem_counts.get(best_stem, 0) + 1
    return re.sub(r'\s+', ' ', best).strip()


def _render_lines(lines: list[Any], values: dict[str, str], *, seed_prefix: str) -> list[str]:
    stem_counts: dict[str, int] = {}
    rendered: list[str] = []
    for idx, raw in enumerate(lines):
        line = _render_choice(raw, values, seed_key=f'{seed_prefix}:{idx}:{values.get("goal", "")}', stem_counts=stem_counts)
        if line:
            rendered.append(line)
    return rendered


def _render_hook_job(job_name: str, hook_spec: dict[str, Any], values: dict[str, str], *, cite_text: str, seed_prefix: str, stem_counts: dict[str, int]) -> str:
    part_order = [str(x).strip() for x in (hook_spec.get('part_order') or []) if str(x).strip()]
    if not part_order:
        part_order = [str(k) for k in hook_spec.keys() if str(k) != 'part_order']
    local_values = dict(values)
    local_values['cite'] = cite_text
    parts: list[str] = []
    for idx, part in enumerate(part_order):
        rendered = _render_choice(hook_spec.get(part), local_values, seed_key=f'{seed_prefix}:{job_name}:{part}:{idx}', stem_counts=stem_counts)
        if rendered:
            parts.append(rendered)
    text = ' '.join(parts).strip()
    if text and text[-1] not in '.!?':
        text += '.'
    return text


def _render_job_graph(
    section_name: str,
    section_contract: dict[str, Any],
    hook_bank: dict[str, Any],
    values: dict[str, str],
    *,
    all_keys: list[str],
    chapter_contexts: list[dict[str, str]],
    projection: dict[str, Any] | None = None,
) -> str:
    paragraphs: list[str] = []
    jobs = section_contract.get('jobs') or []
    stem_counts: dict[str, int] = {}
    for spec_index, spec in enumerate(jobs, start=1):
        if not isinstance(spec, dict):
            continue
        job_name = str(spec.get('job') or '').strip()
        if not job_name or job_name not in hook_bank:
            continue
        width = max(1, int(spec.get('cite_width') or 6))
        start = max(0, int(spec.get('cite_start') or 0))
        stride = max(1, int(spec.get('cite_stride') or width))
        if str(spec.get('repeat_from') or '').strip() == 'chapters':
            limit = max(0, int(spec.get('limit') or len(chapter_contexts)))
            grouped_chapters = _group_chapter_contexts(chapter_contexts[:limit], section_name=section_name, projection=projection)
            for chapter_index, chapter in enumerate(grouped_chapters):
                local_values = dict(values)
                local_values.update(chapter)
                cite_text = _cite_range(all_keys, start + chapter_index * stride, start + chapter_index * stride + width)
                paragraph = _render_hook_job(job_name, hook_bank[job_name], local_values, cite_text=cite_text, seed_prefix=f'{section_name}:{spec_index}:{chapter_index}', stem_counts=stem_counts)
                if paragraph:
                    paragraphs.append(paragraph)
            continue
        cite_text = _cite_range(all_keys, start, start + width)
        paragraph = _render_hook_job(job_name, hook_bank[job_name], values, cite_text=cite_text, seed_prefix=f'{section_name}:{spec_index}', stem_counts=stem_counts)
        if paragraph:
            paragraphs.append(paragraph)
    if not paragraphs:
        raise SystemExit(f'No paragraphs rendered for {section_name}.')
    return '\n\n'.join(paragraphs).rstrip() + '\n'


def _lint_reader_facing(*, label: str, text: str, contract: dict[str, Any]) -> None:
    harness_anchor = (
        r'(?:checkpoint\s+C\d+|unit\s+U\d+|harness(?:\s+(?:lock|kernel))?|'
        r'attempt\s+ledger|locked\s+contract|template\s+residue|workspace)'
    )
    ambiguous_pipeline_term = r'(?:(?:this|across\s+the)\s+pipeline|quality\s+gate)'
    checks = [
        (
            rf'(?i)(?:\b{ambiguous_pipeline_term}\b[^.!?\n]{{0,160}}\b{harness_anchor}\b|'
            rf'\b{harness_anchor}\b[^.!?\n]{{0,160}}\b{ambiguous_pipeline_term}\b)',
            'pipeline narration',
        ),
        (r'(?i)\bthis\s+workspace\b', 'workspace narration'),
        (r'(?i)\bstage\s*C\d+\b', 'stage narration'),
        (r'(?i)\bapprove\s+C\d+\b', 'approval narration'),
        (r'(?i)\b(?:for\s+)?this\s+run\b', 'run-local narration'),
        (r'(?i)\bthis review\b', 'deictic review narration'),
        (r'(?i)\bthis survey\b', 'deictic survey narration'),
        (r'(?i)\bthe introduction therefore asks\b', 'planner-talk opener'),
        (r'(?i)\bsurveys? of [^.]+ help most when\b', 'survey-positioning template'),
        (r'(?i)\bused this way\b', 'planner-talk stem'),
        (r'(?i)\bthat stance keeps\b', 'planner-talk stem'),
        (r'(?i)\bthe transition to the body\b', 'planner-talk bridge'),
        (r'(?i)\bfunctions as the opening orientation\b', 'planner-talk framing'),
        (r'(?i)\bevidence-first treatment\b', 'internal method phrasing'),
        (r'(?i)\bthe discussion below\b', 'slide-like narration'),
        (r'(?i)\bwhat follows\b', 'slide-like narration'),
        (r'(?i)\bthe remaining sections\b', 'outline narration'),
        (r'(?i)\bthat methodology note appears once here\b', 'meta methodology narration'),
        (r'(?i)\bevidence assembled here\b', 'meta evidence narration'),
    ]
    forbidden = [str(x).strip() for x in ((contract.get('voice_guardrails') or {}).get('forbidden_stems') or []) if str(x).strip()]
    for stem in forbidden:
        checks.append((rf'(?i)\b{re.escape(stem)}\b', f'forbidden contract stem `{stem}`'))
    for pattern, name in checks:
        if re.search(pattern, text):
            raise SystemExit(f'Reader-facing {label} contains forbidden {name}: {pattern}')


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
        if (repo_root / 'AGENTS.md').exists():
            break
        parent = repo_root.parent
        if parent == repo_root:
            break
        repo_root = parent
    sys.path.insert(0, str(repo_root))

    from tooling.common import atomic_write_text, decisions_has_approval, ensure_dir, load_yaml, now_iso_seconds, parse_semicolon_list, research_subject_from_request, upsert_checkpoint_block
    from tooling.quality_gate import _draft_profile

    workspace = Path(args.workspace).resolve()
    inputs = parse_semicolon_list(args.inputs)
    outputs = parse_semicolon_list(args.outputs)
    sections_dir = workspace / 'sections'
    ensure_dir(sections_dir)

    decisions_path = workspace / 'DECISIONS.md'
    if not decisions_has_approval(decisions_path, 'C2'):
        block = '\n'.join([
            '## C5 front matter request',
            '',
            '- This unit writes prose into `sections/`.',
            '- Please tick `Approve C2` in `DECISIONS.md`, then rerun this unit.',
            '',
        ])
        upsert_checkpoint_block(decisions_path, 'C5', block)
        return 2

    outline = load_yaml(workspace / 'outline' / 'outline.yml') if (workspace / 'outline' / 'outline.yml').exists() else []
    goal = _goal_text(workspace / 'GOAL.md', subject_normalizer=research_subject_from_request)
    time_window, candidate_pool, core_set_size, evidence_mode = _parse_stats(
        workspace / 'papers' / 'retrieval_report.md',
        workspace / 'papers' / 'core_set.csv',
        workspace / 'queries.md',
    )

    intro_id = '1'
    related_id = '2'
    if isinstance(outline, list):
        for sec in outline:
            if not isinstance(sec, dict):
                continue
            sid = str(sec.get('id') or '').strip()
            title = str(sec.get('title') or '').strip().lower()
            if sid and 'intro' in title:
                intro_id = sid
            if sid and 'related' in title:
                related_id = sid

    chapter_briefs = _load_jsonl(workspace / 'outline' / 'chapter_briefs.jsonl')
    packs = _load_jsonl(workspace / 'outline' / 'writer_context_packs.jsonl')
    all_keys: list[str] = []
    for rec in packs:
        for field in ('allowed_bibkeys_selected', 'allowed_bibkeys_chapter', 'allowed_bibkeys_global'):
            for key in rec.get(field) or []:
                all_keys.append(str(key).strip())
        for fact in rec.get('anchor_facts') or []:
            if isinstance(fact, dict):
                for key in fact.get('citations') or []:
                    all_keys.append(str(key).strip())
    all_keys = _uniq(all_keys)

    intro_path = sections_dir / f'S{intro_id}.md'
    related_path = sections_dir / f'S{related_id}.md'
    abstract_path = sections_dir / 'abstract.md'
    discussion_path = sections_dir / 'discussion.md'
    conclusion_path = sections_dir / 'conclusion.md'
    report_path = workspace / 'output' / 'FRONT_MATTER_REPORT.md'
    context_path = workspace / 'output' / 'FRONT_MATTER_CONTEXT.json'
    ensure_dir(report_path.parent)

    package_root = Path(__file__).resolve().parents[1]
    template_asset_path = package_root / 'assets' / 'front_matter_templates.json'
    contract_asset_path = package_root / 'assets' / 'front_matter_contract.json'
    projection_asset_path = package_root / 'assets' / 'front_matter_context_projection.json'
    template_bank = _load_json(template_asset_path)
    contract = _load_json(contract_asset_path)
    projection = _load_json(projection_asset_path)
    if not template_bank:
        raise SystemExit(f'Missing or invalid front-matter template asset: {template_asset_path}')
    if not contract:
        raise SystemExit(f'Missing or invalid front-matter contract asset: {contract_asset_path}')
    if not projection:
        raise SystemExit(f'Missing or invalid front-matter projection asset: {projection_asset_path}')

    selected_template_assets = [template_asset_path]
    domain_id = _detect_domain(workspace)
    if domain_id:
        overlay_asset_path = package_root / 'assets' / 'domain_templates' / f'{domain_id}.json'
        overlay = _load_domain_overlay(domain_id)
        if overlay:
            template_bank = _merge_template_bank(template_bank, overlay)
            selected_template_assets.append(overlay_asset_path)

    chapter_contexts = _chapter_contexts(outline, chapter_briefs, intro_id=intro_id, related_id=related_id, projection=projection)
    values = _global_values(
        goal=goal,
        time_window=time_window,
        candidate_pool=candidate_pool,
        core_set_size=core_set_size,
        evidence_mode=evidence_mode,
        chapter_contexts=chapter_contexts,
        projection=projection,
    )

    headings = template_bank.get('headings') or {}
    hook_banks = template_bank.get('hook_banks') or {}
    section_contracts = dict(contract.get('sections') or {})
    draft_profile = _draft_profile(workspace)
    profile_sections = (((contract.get('profile_overrides') or {}).get(draft_profile) or {}).get('sections') or {})
    for section_name, override in profile_sections.items():
        if isinstance(override, dict):
            section_contracts[str(section_name)] = {**dict(section_contracts.get(str(section_name)) or {}), **override}

    values['candidate_pool'] = candidate_pool
    values['core_set_size'] = core_set_size
    values['evidence_mode'] = evidence_mode
    values['time_window'] = time_window
    values['evidence_note'] = f'{core_set_size} using {evidence_mode}'

    abstract_values = dict(values)
    for start, stop in ((0, 6), (6, 12), (12, 18), (18, 24), (24, 30), (0, 4), (4, 8), (8, 12), (12, 16), (16, 20), (20, 24)):
        abstract_values[f'cite_{start}_{stop}'] = _cite_range(all_keys, start, stop)

    if template_bank.get('introduction_paragraphs'):
        intro_lines = _render_lines(list(template_bank.get('introduction_paragraphs') or []), values, seed_prefix='intro-legacy')
        introduction = '\n\n'.join(intro_lines).rstrip() + '\n'
    else:
        introduction = _render_job_graph('introduction', section_contracts.get('introduction') or {}, hook_banks.get('introduction') or {}, values, all_keys=all_keys, chapter_contexts=chapter_contexts, projection=projection)

    if template_bank.get('related_work_paragraphs'):
        related_lines = _render_lines(list(template_bank.get('related_work_paragraphs') or []), values, seed_prefix='related-legacy')
        related_work = '\n\n'.join(related_lines).rstrip() + '\n'
    else:
        related_work = _render_job_graph('related_work', section_contracts.get('related_work') or {}, hook_banks.get('related_work') or {}, values, all_keys=all_keys, chapter_contexts=chapter_contexts, projection=projection)

    abstract_lines = _render_lines(list(template_bank.get('abstract_sentences') or []), abstract_values, seed_prefix='abstract')
    abstract = str(headings.get('abstract') or '## Abstract') + '\n\n' + ' '.join(abstract_lines).strip() + '\n'

    discussion_lines = _render_lines(list(template_bank.get('discussion_paragraphs') or []), abstract_values, seed_prefix='discussion')
    discussion = str(headings.get('discussion') or '## Discussion') + '\n\n' + '\n\n'.join(discussion_lines).rstrip() + '\n'

    conclusion_lines = _render_lines(list(template_bank.get('conclusion_paragraphs') or []), abstract_values, seed_prefix='conclusion')
    conclusion = str(headings.get('conclusion') or '## Conclusion') + '\n\n' + '\n\n'.join(conclusion_lines).rstrip() + '\n'

    _lint_reader_facing(label='abstract', text=abstract, contract=contract)
    _lint_reader_facing(label='introduction', text=introduction, contract=contract)
    _lint_reader_facing(label='related_work', text=related_work, contract=contract)
    _lint_reader_facing(label='discussion', text=discussion, contract=contract)
    _lint_reader_facing(label='conclusion', text=conclusion, contract=contract)

    atomic_write_text(abstract_path, abstract)
    atomic_write_text(intro_path, introduction)
    atomic_write_text(related_path, related_work)
    atomic_write_text(discussion_path, discussion)
    atomic_write_text(conclusion_path, conclusion)

    context = {
        'goal': goal,
        'section_ids': {'intro': intro_id, 'related': related_id},
        'time_window': time_window,
        'candidate_pool': candidate_pool,
        'core_set_size': core_set_size,
        'evidence_mode': evidence_mode,
        'chapter_titles_joined': values.get('chapter_titles_joined', ''),
        'sections': {
            'abstract': str(abstract_path.relative_to(workspace)),
            'introduction': str(intro_path.relative_to(workspace)),
            'related_work': str(related_path.relative_to(workspace)),
            'discussion': str(discussion_path.relative_to(workspace)),
            'conclusion': str(conclusion_path.relative_to(workspace)),
        },
        'reference_pack': contract.get('reference_pack') or [],
        'asset_pack': (contract.get('asset_pack') or []) + ['assets/front_matter_context_projection.json'],
        'template_asset': 'assets/front_matter_templates.json',
        'template_assets': [
            str(path.relative_to(repo_root)) for path in selected_template_assets
        ],
        'template_asset_sha256': {
            str(path.relative_to(repo_root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in selected_template_assets
        },
        'projection_asset': 'assets/front_matter_context_projection.json',
        'voice_hygiene': {
            'forbid_pipeline_voice': True,
            'forbid_domain_default_fallback': True,
            'methodology_note_max_occurrences': int(((contract.get('methodology_note_policy') or {}).get('max_occurrences') or 1)),
        },
        'citation_pool_size': len(all_keys),
        'draft_profile': draft_profile,
        'render_mode': 'job_graph',
        'domain_overlay': domain_id or '',
    }
    atomic_write_text(context_path, json.dumps(context, indent=2, ensure_ascii=False) + '\n')

    report = '\n'.join([
        '# Front matter report',
        '',
        '- Status: PASS',
        f'- Generated at: `{now_iso_seconds()}`',
        '- Render mode: `job_graph`',
        f'- Abstract: `sections/abstract.md`',
        f'- Introduction: `sections/S{intro_id}.md`',
        f'- Related Work: `sections/S{related_id}.md`',
        '- Context sidecar: `output/FRONT_MATTER_CONTEXT.json`',
        '- Template asset: `assets/front_matter_templates.json`',
        '- Contract asset: `assets/front_matter_contract.json`',
        '- Context projection asset: `assets/front_matter_context_projection.json`',
        '- Discussion: `sections/discussion.md`',
        '- Conclusion: `sections/conclusion.md`',
        '- Compatibility mode: prose outputs preserved; introduction and related work now render from hook-bank jobs instead of whole-paragraph banks.',
    ]) + '\n'
    atomic_write_text(report_path, report)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
