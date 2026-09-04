"""Regression: research-brief prose — clean truncation, no motivation-as-limitation.

An independent review of a real research-brief
SNAPSHOT.md flagged two deterministic defects the surface checks missed:

1. `_brief_summary` truncated a long reading rationale mid-clause ("... a novel
   TTA framework that selectively identifies and adapts to.") and produced the
   capitalization artifact "In The study". It now backs up to the last clause
   boundary within the word cap and only capitalizes "The study" sentence-
   initially.
2. `_brief_risk_bullets` surfaced a POSITIVE-MOTIVATION sentence as a "Reported
   limitation to weigh" because `_LIMITATION_CUE` matched the weak cue "only"
   ("TTA updates a model on-the-fly using only unlabeled test data, making it
   promising ..."). The cue is tightened and positive-framing sentences are
   excluded.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import _brief_summary, _brief_risk_bullets


def test_brief_summary_no_midclause_truncation_or_bad_caps() -> None:
    long_abstract = (
        "In this study, we propose CANDI, a novel TTA framework that selectively "
        "identifies and adapts to potential false positives while preserving "
        "pre-trained knowledge across a wide range of distribution shifts and "
        "benchmark settings that stress the adaptation loop."
    )
    out = _brief_summary(long_abstract, max_words=28)
    # No mid-clause dangling preposition end.
    assert not out.rstrip(".").endswith("adapts to"), out
    assert not out.rstrip(".").endswith(" to"), out
    # Capitalization artifact fixed: no "In The study".
    assert "In The study" not in out, out
    # If truncated, it ends with an ellipsis after a clean boundary.
    if out.endswith("..."):
        assert not out[:-3].rstrip().endswith((" and", " to", " of", " the")), out


def test_brief_summary_sentence_initial_the_study_ok() -> None:
    # "The study" at the start of the summary stays capitalized.
    text = "This study introduces a benchmark for evaluation under shift."
    out = _brief_summary(text, max_words=45)
    assert out.startswith("The study"), out


def test_risk_bullets_reject_positive_motivation_as_limitation() -> None:
    papers = [
        {
            "paper_id": "P0001",
            "title": "CANDI",
            "url": "http://arxiv.org/abs/2604.01845v1",
            # The exact false-positive: contains "only" but is positive motivation.
            "abstract": (
                "Test-time adaptation updates a pre-trained model on-the-fly using "
                "only unlabeled test data, making it promising for addressing this "
                "challenge."
            ),
        }
    ]
    bullets = _brief_risk_bullets(lenses=["Test Time Adaptation"], papers=papers)
    limitation_bullets = [b for b in bullets if b.startswith("Reported limitation")]
    # The motivation sentence must NOT be surfaced as a limitation.
    assert not limitation_bullets, limitation_bullets


def test_risk_bullets_accept_real_limitation() -> None:
    papers = [
        {
            "paper_id": "P0002",
            "title": "EEG TTA",
            "url": "http://arxiv.org/abs/2604.16926v2",
            "abstract": (
                "These findings highlight the limitations of existing TTA techniques "
                "in EEG and underscore the need for domain-specific adaptation."
            ),
        }
    ]
    bullets = _brief_risk_bullets(lenses=["Test Time Adaptation"], papers=papers)
    assert any(b.startswith("Reported limitation") and "limitations" in b for b in bullets), bullets


def test_brief_evidence_boundary_reconciles_with_shown_papers() -> None:
    """Whole-document coherence: the boundary count must reconcile with the
    number of highlighted papers (was '12 selected' but only 6 shown)."""
    from tooling.review_render import render_research_brief_markdown

    papers = [
        {"paper_id": f"P{i:04d}", "title": f"Paper {i}", "url": f"http://x/{i}",
         "abstract": f"We study topic {i} and report a result."}
        for i in range(1, 13)
    ]
    sections = ["Methods", "Evaluation", "Deployment", "Robustness"]
    brief = render_research_brief_markdown(goal="# Goal\n\nOrient me.", papers=papers, sections=sections)
    scope = brief.split("## Scope", 1)[1].split("## Key themes", 1)[0]
    # The boundary discloses BOTH the selected count and how many are shown.
    assert "12 selected papers" in scope, scope
    assert "6 most representative highlighted" in scope, scope


def test_brief_declared_lenses_match_findings_bullet() -> None:
    """Whole-document coherence: declared Comparison lenses == the lenses used in
    the 'Findings across' open-problems bullet (was 4 declared vs 3 used)."""
    from tooling.review_render import render_research_brief_markdown

    papers = [
        {"paper_id": f"P{i:04d}", "title": f"Paper {i}", "url": f"http://x/{i}",
         "abstract": "We study a topic and note a limitation: the method assumes clean labels."}
        for i in range(1, 13)
    ]
    sections = ["Methods", "Evaluation", "Deployment", "Robustness"]
    brief = render_research_brief_markdown(goal="# Goal\n\nOrient me.", papers=papers, sections=sections)
    scope = brief.split("## Scope", 1)[1].split("## Key themes", 1)[0]
    lens_line = next(ln for ln in scope.splitlines() if ln.startswith("- Comparison lenses:"))
    declared = [x.strip() for x in lens_line.split(":", 1)[1].rstrip(".").split(",") if x.strip()]
    findings = [ln for ln in brief.splitlines() if ln.startswith("- Findings across")]
    assert findings, brief
    # Every declared lens appears in the findings bullet (same set, no omission).
    for lens in declared:
        assert lens in findings[0], (lens, findings[0])
