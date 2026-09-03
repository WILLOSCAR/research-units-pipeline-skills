from __future__ import annotations

import argparse
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

def _need_tag(field: str) -> str | None:
    low = str(field or '').lower()
    if any(w in low for w in ['benchmark', 'benchmarks', 'dataset', 'datasets', 'metric', 'metrics', 'evaluation', 'protocol']):
        return 'evaluation'
    if any(w in low for w in ['tool', 'tools', 'api', 'function', 'schema', 'mcp', 'interface']):
        return 'tooling'
    if any(w in low for w in ['memory', 'retrieval', 'rag', 'cache']):
        return 'memory'
    if any(w in low for w in ['security', 'attack', 'threat', 'guardrail', 'sandbox', 'injection', 'jailbreak']):
        return 'security'
    if any(w in low for w in ['compute', 'cost', 'latency', 'token', 'budget', 'efficien']):
        return 'numbers'
    return None




def _per_subsection_from_queries(path: Path) -> int:
    """Read per-subsection mapping width from queries.md (best-effort).

    Keeps binder density aligned with section-mapper as we scale up.
    """

    if not path.exists():
        return 0

    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line.startswith("- "):
            continue
        if ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        if key not in {"per_subsection", "mapping_per_subsection", "section_mapper_per_subsection"}:
            continue

        value = value.split("#", 1)[0].strip().strip("\"").strip(chr(39))
        try:
            n = int(value)
        except Exception:
            return 0
        return n if n > 0 else 0

    return 0

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
    # Slightly stronger than before: subsection-specific title/axes terms should matter,
    # otherwise selection collapses into a near-constant "result-heavy" recipe.
    score += 0.10 * len(snip_toks & want)

    return score


def _assert_h3_cutover_ready(*, workspace: Path, consumer: str) -> None:
    from tooling.common import read_jsonl

    state_path = workspace / "outline" / "outline_state.jsonl"
    if not state_path.exists() or state_path.stat().st_size <= 0:
        return

    records = [rec for rec in read_jsonl(state_path) if isinstance(rec, dict)]
    if not records:
        return

    latest = records[-1]
    cutover_keys = {"structure_phase", "h3_status", "approval_status", "reroute_target", "retry_budget_remaining"}
    if not any(key in latest for key in cutover_keys):
        return

    h3_status = str(latest.get("h3_status") or "").strip().lower()
    if h3_status == "stable":
        return

    structure_phase = str(latest.get("structure_phase") or "").strip() or "unknown"
    reroute_target = str(latest.get("reroute_target") or "").strip() or "none"
    raise SystemExit(
        f"{consumer} is blocked until stable H3 ids exist: "
        f"`outline/outline_state.jsonl` reports h3_status={h3_status or 'missing'} "
        f"(structure_phase={structure_phase}, reroute_target={reroute_target})."
    )


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

    from tooling.common import atomic_write_text, ensure_dir, latest_outline_state, load_workspace_pipeline_spec, now_iso_seconds, parse_semicolon_list, read_jsonl, read_tsv, write_jsonl
    from tooling.quality_gate import _draft_profile, _pipeline_profile

    workspace = Path(args.workspace).resolve()
    spec = load_workspace_pipeline_spec(workspace)
    if spec is not None and str(spec.structure_mode or "").strip() == "section_first":
        state = latest_outline_state(workspace)
        if not state:
            raise SystemExit("Missing outline_state.jsonl; run the section-first C2 planner pass before evidence-binder.")
        if str(state.get("structure_phase") or "").strip() != "decomposed" or str(state.get("h3_status") or "").strip() != "stable":
            raise SystemExit("Section-first cutover not ready: `outline_state.jsonl` must report `structure_phase: decomposed` and `h3_status: stable` before evidence-binder.")

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

    _assert_h3_cutover_ready(workspace=workspace, consumer="evidence-binder")

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
    per_subsection = _per_subsection_from_queries(workspace / "queries.md")
    if profile == "arxiv-survey" and per_subsection <= 0:
        per_subsection = 28

    k = 14
    min_selected_bibkeys = 10
    max_per_paper = 3

    if profile == "arxiv-survey":
        if draft_profile == "course_paper":
            k = max(8, per_subsection)
            min_selected_bibkeys = max(6, int(round(per_subsection * 0.70)))
        elif draft_profile == "deep":
            k = max(28, per_subsection)
            min_selected_bibkeys = max(22, int(round(per_subsection * 0.80)))
        else:
            k = max(24, max(1, per_subsection - 4))
            min_selected_bibkeys = max(20, int(round(per_subsection * 0.70)))
        # Encourage breadth: keep many distinct papers so C5 has wider in-scope cite pools.
        max_per_paper = 2

    flags: list[str] = []
    for brief in briefs:
        sid = str(brief.get('sub_id') or '').strip()
        title = str(brief.get('title') or '').strip()
        rq = str(brief.get('rq') or '').strip()
        axes = brief.get('axes') or []
        axes_txt = ' '.join([str(a) for a in axes])

        required_fields = brief.get('required_evidence_fields') or []
        required_txt = ' '.join([str(x) for x in required_fields])
        want = _tokenize(f"{title} {rq} {axes_txt} {required_txt}")

        joined = f"{title} {rq} {axes_txt} {required_txt}".lower()
        want_tags: set[str] = set()
        if any(k in joined for k in ['benchmark', 'benchmarks', 'dataset', 'datasets', 'metric', 'metrics', 'evaluation', 'protocol']):
            want_tags.add('evaluation')
        if any(k in joined for k in ['tool', 'tools', 'api', 'function', 'schema', 'mcp', 'interface']):
            want_tags.add('tooling')
        if any(k in joined for k in ['memory', 'retrieval', 'rag', 'cache']):
            want_tags.add('memory')
        if any(k in joined for k in ['security', 'attack', 'threat', 'guardrail', 'sandbox', 'injection', 'jailbreak']):
            want_tags.add('security')
        if any(k in joined for k in ['compute', 'cost', 'latency', 'token', 'budget', 'efficien']):
            want_tags.add('numbers')

        # Tag targets: derive a small "coverage budget" from required_evidence_fields to avoid
        # a constant per-subsection recipe (and make subsection-specific needs visible).
        required_tag_counts: dict[str, int] = {}
        for field in required_fields:
            tag = _need_tag(str(field or ''))
            if not tag:
                continue
            required_tag_counts[tag] = required_tag_counts.get(tag, 0) + 1

        tag_target: dict[str, int] = {}
        for tag in sorted(want_tags):
            # Default: cover each desired tag at least once when possible.
            n = 1
            # If multiple required fields map to the same tag, prefer >=2 supporting items.
            if required_tag_counts.get(tag, 0) >= 2:
                n = 2
            # Some tags are typically under-specified with only one snippet.
            if tag in {'evaluation', 'security', 'numbers'} and required_tag_counts.get(tag, 0) >= 1:
                n = max(n, 2)
            tag_target[tag] = n

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
        used_bibkeys: set[str] = set()

        def pick(it: dict[str, Any], *, allow_dup_bibkey: bool = False) -> None:
            pid = str(it.get("paper_id") or "").strip()
            kind = str(it.get("claim_type") or "").strip().lower()
            bk = str(it.get("bibkey") or "").strip()
            if not pid or not bk:
                return
            if used_paper.get(pid, 0) >= max_per_paper:
                return
            # Prefer breadth early: keep adding new bibkeys until we hit the subsection budget.
            if (not allow_dup_bibkey) and len(used_bibkeys) < min_selected_bibkeys and bk in used_bibkeys:
                return
            # Avoid too many limitations (often boilerplate).
            if kind == "limitation" and used_kind.get(kind, 0) >= 3:
                return
            eid = str(it.get("evidence_id") or "").strip()
            if not eid:
                return
            if any(e.get("evidence_id") == eid for e in selected):
                return
            selected.append(it)
            used_paper[pid] = used_paper.get(pid, 0) + 1
            used_kind[kind] = used_kind.get(kind, 0) + 1
            used_bibkeys.add(bk)

        # Seed: keep a minimal "writeable" mix (contrast + mechanism + limitation),
        # but let subsection-specific tag targets shape the rest.
        for kind in ['result', 'result', 'method', 'limitation']:
            for _, _, it in scored:
                if str(it.get('claim_type') or '').strip().lower() != kind:
                    continue
                pick(it)
                break

        # Subsection-specific tag coverage: satisfy tag targets when available.
        for tag in sorted(tag_target.keys()):
            target_n = int(tag_target.get(tag, 0) or 0)
            if target_n <= 0:
                continue
            picked_n = 0
            for _, _, it in scored:
                tags = set([str(t).strip().lower() for t in (it.get('tags') or []) if str(t).strip()])
                if tag not in tags:
                    continue
                before = len(selected)
                pick(it)
                if len(selected) > before:
                    picked_n += 1
                if picked_n >= target_n:
                    break

        for _, _, it in scored:
            if len(selected) >= k:
                break
            pick(it)


        # If breadth constraints prevent reaching k, do a relaxed fill pass to hit evidence_id count.
        if len(selected) < k:
            for _, _, it in scored:
                if len(selected) >= k:
                    break
                pick(it, allow_dup_bibkey=True)

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

        selected_tags: dict[str, int] = {}
        for it in selected:
            for t in (it.get('tags') or []):
                t = str(t).strip().lower()
                if not t:
                    continue
                selected_tags[t] = selected_tags.get(t, 0) + 1

        binding_gaps: list[str] = []
        for field in required_fields:
            tag = _need_tag(str(field or ''))
            if tag and selected_tags.get(tag, 0) <= 0:
                if str(field or '').strip() and str(field or '').strip() not in binding_gaps:
                    binding_gaps.append(str(field).strip())

        binding_rationale: list[str] = []
        if axes and isinstance(axes, list):
            axes_short = ', '.join([str(a).strip() for a in axes[:3] if str(a).strip()])
            if axes_short:
                binding_rationale.append(f"axes: {axes_short}")
        if want_tags:
            binding_rationale.append('desired_tags: ' + ', '.join(sorted(want_tags)))
        if selected_tags:
            cov = ', '.join([f"{k}={v}" for k, v in sorted(selected_tags.items()) if v])
            if cov:
                binding_rationale.append(f"covered_tags: {cov}")
        if binding_gaps:
            binding_rationale.append('gaps: ' + ', '.join(binding_gaps[:6]))

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
                    'by_tag': selected_tags,
                    'by_evidence_level': by_lvl,
                },
                'binding_rationale': binding_rationale,
                'binding_gaps': binding_gaps,
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
        '| Subsection | evidence_ids | claim_type mix | tag mix | evidence_level mix | gaps |',
        '|---|---:|---|---|---|---|',
    ]

    for rec in sorted(records, key=lambda r: tuple(int(p) for p in str(r.get('sub_id') or '0').split('.') if p.isdigit())):
        sid = str(rec.get('sub_id') or '').strip()
        title = str(rec.get('title') or '').strip()
        cnt = rec.get('evidence_counts') or {}
        by_kind = cnt.get('by_claim_type') or {}
        by_tag = cnt.get('by_tag') or {}
        by_lvl = cnt.get('by_evidence_level') or {}
        kind_txt = ', '.join([f"{k}={v}" for k, v in sorted(by_kind.items())]) if isinstance(by_kind, dict) else '—'
        tag_txt = '—'
        if isinstance(by_tag, dict) and by_tag:
            top = sorted(by_tag.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
            tag_txt = ', '.join([f"{k}={v}" for k, v in top if v])
            tag_txt = tag_txt if tag_txt else '—'
        lvl_txt = ', '.join([f"{k}={v}" for k, v in sorted(by_lvl.items())]) if isinstance(by_lvl, dict) else '—'
        gaps = rec.get('binding_gaps') or []
        gaps_txt = ', '.join([str(g).strip() for g in gaps if str(g).strip()]) if isinstance(gaps, list) else ''
        gaps_txt = gaps_txt if gaps_txt else '—'
        lines.append(f"| {sid} {title} | {cnt.get('selected_total', 0)} | {kind_txt} | {tag_txt} | {lvl_txt} | {gaps_txt} |")

    if flags:
        lines.extend(['', '## Flags', ''])
        for f in flags[:20]:
            lines.append(f"- {f}")

    atomic_write_text(report_path, "\n".join(lines).rstrip() + "\n")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
