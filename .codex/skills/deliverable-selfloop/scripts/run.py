from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _count_shortlist(md: str) -> int:
    return len(re.findall(r'(?m)^###\s+Direction\s+\d+\.', md or ''))


def _brief_gate(workspace: Path) -> tuple[str, list[str], str, str]:
    from tooling.brief_evaluation import write_research_brief_scorecard

    _, scorecard = write_research_brief_scorecard(workspace)
    issues = (
        [
            str(item.get('message') or item.get('code') or 'scorecard failure')
            for item in scorecard['failures']
        ]
        if scorecard['verdict'] == 'FAIL'
        else []
    )
    return (
        'research brief (`output/SNAPSHOT.md`)',
        issues,
        f"The research-brief deliverable received {scorecard['score']}/100 against its structure, compactness, and source-traceability rubric.",
        'Repair the scorecard failures at their named upstream surfaces and rerun this unit.',
    )


def _paper_review_gate(workspace: Path) -> tuple[str, list[str], str, str]:
    from tooling.review_evaluation import write_paper_review_scorecard

    path = workspace / 'output' / 'REVIEW.md'
    issues: list[str] = []
    text = path.read_text(encoding='utf-8', errors='ignore') if path.exists() else ''
    if not path.exists() or not text.strip():
        issues.append('Missing `output/REVIEW.md`.')
    _, scorecard = write_paper_review_scorecard(workspace)
    if scorecard['verdict'] == 'FAIL':
        issues.extend(str(item.get('message') or item.get('code') or 'scorecard failure') for item in scorecard['failures'])
    return (
        'paper review (`output/REVIEW.md`)',
        issues,
        f"The paper-review deliverable received {scorecard['score']}/100 against the traceability rubric.",
        'Repair the scorecard failures at their named upstream surfaces and rerun this unit.',
    )


def _evidence_review_gate(workspace: Path) -> tuple[str, list[str], str, str]:
    from tooling.evidence_review_evaluation import write_evidence_review_scorecard

    _, scorecard = write_evidence_review_scorecard(workspace)
    issues = (
        [
            str(item.get('message') or item.get('code') or 'scorecard failure')
            for item in scorecard['failures']
        ]
        if scorecard['verdict'] == 'FAIL'
        else []
    )
    return (
        'evidence review synthesis (`output/SYNTHESIS.md`)',
        issues,
        f"The evidence-review deliverable received {scorecard['score']}/100 for protocol-to-synthesis traceability and bounded conclusions.",
        'Repair the scorecard failures at their named upstream surfaces and rerun this unit.',
    )


def _idea_brainstorm_gate(workspace: Path) -> tuple[str, list[str], str, str]:
    from tooling.idea_evaluation import write_idea_brainstorm_scorecard

    _, scorecard = write_idea_brainstorm_scorecard(workspace)
    issues = (
        [
            str(item.get('message') or item.get('code') or 'scorecard failure')
            for item in scorecard['failures']
        ]
        if scorecard['verdict'] == 'FAIL'
        else []
    )
    return (
        'research idea memo (`output/REPORT.md` + trace chain)',
        issues,
        f"The idea-brainstorm deliverable received {scorecard['score']}/100 for discussion readiness, actionability, diversity, and evidence traceability.",
        'Repair the scorecard failures at their named upstream surfaces and rerun this unit.',
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

    from tooling.common import atomic_write_text, ensure_dir, pipeline_profile, pipeline_quality_contract_value

    workspace = Path(args.workspace).resolve()
    profile = pipeline_profile(workspace)
    deliverable_kind = str(
        pipeline_quality_contract_value(workspace, "deliverable_kind", default="") or ""
    ).strip()
    signal_table = workspace / 'output' / 'trace' / 'IDEA_SIGNAL_TABLE.md'
    pool = workspace / 'output' / 'trace' / 'IDEA_DIRECTION_POOL.md'
    screening = workspace / 'output' / 'trace' / 'IDEA_SCREENING_TABLE.md'
    shortlist = workspace / 'output' / 'trace' / 'IDEA_SHORTLIST.md'
    report_md = workspace / 'output' / 'REPORT.md'
    appendix = workspace / 'output' / 'APPENDIX.md'
    report_json = workspace / 'output' / 'REPORT.json'
    report = workspace / 'output' / 'DELIVERABLE_SELFLOOP_TODO.md'
    ensure_dir(report.parent)

    issues: list[str] = []
    deliverable = ''
    summary = ''
    next_step = ''
    if deliverable_kind == 'brief' or profile == 'research-brief':
        deliverable, issues, summary, next_step = _brief_gate(workspace)
        changes_made = '- Wrote `output/BRIEF_SCORECARD.md` and `.json`, then checked briefing structure, compactness, and core-set pointers.'
    elif deliverable_kind == 'paper_review' or profile == 'paper-review':
        deliverable, issues, summary, next_step = _paper_review_gate(workspace)
        changes_made = '- Wrote `output/REVIEW_SCORECARD.md` and `.json`, then checked the machine-readable claim/evidence/review chain.'
    elif deliverable_kind == 'evidence_review' or profile == 'evidence-review':
        deliverable, issues, summary, next_step = _evidence_review_gate(workspace)
        changes_made = '- Wrote `output/EVIDENCE_SCORECARD.md` and `.json`, then checked protocol clauses, screening reasons, extraction coverage, bias fields, synthesis pointers, and bounded conclusions.'
    elif profile == 'idea-brainstorm':
        deliverable, issues, summary, next_step = _idea_brainstorm_gate(workspace)
        changes_made = '- Wrote `output/IDEA_SCORECARD.md` and `.json`, then checked the memo bundle, trace chain, direction actionability, diversity, and core-set pointers.'
    else:
        for path in [signal_table, pool, screening, shortlist, report_md, appendix, report_json]:
            if not path.exists() or path.stat().st_size <= 0:
                issues.append(f'Missing `{path.relative_to(workspace)}`.')

        shortlist_text = shortlist.read_text(encoding='utf-8', errors='ignore') if shortlist.exists() else ''
        report_text = report_md.read_text(encoding='utf-8', errors='ignore') if report_md.exists() else ''
        appendix_text = appendix.read_text(encoding='utf-8', errors='ignore') if appendix.exists() else ''

        shortlist_n = _count_shortlist(shortlist_text)
        if shortlist_text and not (3 <= shortlist_n <= 5):
            issues.append(f'Shortlist size should be 3-5 (found {shortlist_n}).')

        required_sections = [
            '## 1. Big-picture takeaways',
            '## 2. Top directions at a glance',
            '## 6. Other promising but not prioritized directions',
            '## 7. Cross-cutting discussion questions',
            '## 8. Uncertainty and disagreement',
        ]
        for section in required_sections:
            if report_text and section not in report_text:
                issues.append(f'`output/REPORT.md` is missing `{section}`.')
        if report_text and '## 3. Direction 1' not in report_text:
            issues.append('`output/REPORT.md` should expand the top directions into memo sections.')
        if appendix_text and not all(token in appendix_text for token in ['Anchor paper', 'Why read now', 'What to extract', 'Kill signal']):
            issues.append('`output/APPENDIX.md` should expose paper-specific reading-guide tables.')
        for phrase in ['reports a meaningful gain', 'Sharper mechanism question;', 'read it to extract what it really attributes gains to']:
            if phrase in report_text or phrase in appendix_text:
                issues.append(f'Found templated memo language: `{phrase}`.')
        deliverable = 'brainstorm memo bundle (`IDEA_SIGNAL_TABLE` -> `IDEA_DIRECTION_POOL` -> `IDEA_SCREENING_TABLE` -> `IDEA_SHORTLIST` -> `REPORT`)'
        summary = 'The ideation deliverable is evaluated as a memo bundle with a supporting trace chain, not as a symmetric top-3 proposal pack.'
        next_step = 'Fix the missing or thin memo artifacts and rerun this unit.'
        changes_made = '- Checked trace presence, shortlist size, and core memo sections for the final `REPORT.md` deliverable.'

    status = 'PASS' if not issues else 'FAIL'
    lines = [
        '# Deliverable self-loop',
        '',
        f'- Status: {status}',
        f'- Deliverable: {deliverable}',
        '',
        '## Summary',
        f'- {summary}',
        '',
        '## Changes made',
        changes_made,
        '',
    ]
    if issues:
        lines.extend(['## Remaining blockers (if FAIL)'])
        lines.extend([f'- {it}' for it in issues])
        lines.extend(['', '## Next step', f'- {next_step}'])
        atomic_write_text(report, '\n'.join(lines).rstrip() + '\n')
        return 2
    lines.extend(['## Remaining blockers (if FAIL)', '- (none)', '', '## Next step', '- Proceed to the next unit.'])
    atomic_write_text(report, '\n'.join(lines).rstrip() + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
