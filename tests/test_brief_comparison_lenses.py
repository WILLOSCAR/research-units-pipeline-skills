"""Regression: research-brief comparison lenses must be axes, not topic restatements.

An L2 whole-SNAPSHOT blind read (real embodied-adaptation corpus, 24 abstracts, via
the full research-brief engine) found the Scope line read "Comparison lenses: Test
Time Adaptation, Shifts". On a corpus where every paper is about test-time
adaptation, "Test Time Adaptation" restates the whole topic and "Shifts" is a
fragment of "distribution shift" — neither is an axis the reader can compare papers
along.

`render_research_brief_markdown` now derives lenses via `_brief_comparison_lenses`,
which drops any outline section whose significant tokens are all already in the goal
topic (singular/plural normalized), so a topic-restatement or topic-fragment is not
listed as a comparison lens. Genuine differentiating axes (e.g. "Shift Type",
"Update Mechanism") survive; when none qualify the caller falls back to the generic
"methods, evaluation, and deployment risks" phrase.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import _brief_comparison_lenses, render_research_brief_markdown


_GOAL = (
    "Produce a compact, traceable research brief on test-time adaptation under "
    "distribution shift, with a bounded reading path and explicit open risks."
)


def test_topic_restatement_and_fragment_dropped() -> None:
    assert _brief_comparison_lenses(["Test Time Adaptation", "Shifts"], _GOAL) == []


def test_genuine_axes_survive_on_shared_topic() -> None:
    lenses = _brief_comparison_lenses(
        ["Shift Type", "Adaptation Signal", "Deployment Protocol"], _GOAL
    )
    assert lenses == ["Shift Type", "Adaptation Signal", "Deployment Protocol"], lenses


def test_topic_restatement_dropped_but_axis_kept() -> None:
    lenses = _brief_comparison_lenses(
        ["Test Time Adaptation", "Shift Type", "Update Mechanism"], _GOAL
    )
    assert lenses == ["Shift Type", "Update Mechanism"], lenses


def test_generic_sections_unrelated_to_goal_are_kept() -> None:
    # A goal that names no topic tokens leaves genuine sections intact.
    lenses = _brief_comparison_lenses(
        ["Methods", "Evaluation", "Deployment", "Robustness"], "# Goal\n\nOrient me."
    )
    # "Methods" is a generic stopword token; the substantive axes survive.
    assert "Evaluation" in lenses and "Deployment" in lenses, lenses


def test_snapshot_lens_line_falls_back_when_all_restate_topic() -> None:
    papers = [
        {"paper_id": f"P{i:04d}", "title": f"TTA paper {i}", "url": f"http://x/{i}",
         "abstract": "We study test-time adaptation under distribution shift."}
        for i in range(1, 13)
    ]
    brief = render_research_brief_markdown(
        goal=f"# Goal\n\n{_GOAL}", papers=papers, sections=["Test Time Adaptation", "Shifts"]
    )
    lens_line = next(ln for ln in brief.splitlines() if ln.startswith("- Comparison lenses:"))
    assert "Test Time Adaptation" not in lens_line, lens_line
    assert "methods, evaluation, and deployment risks" in lens_line, lens_line


def test_no_dangling_findings_bullet_when_lenses_empty() -> None:
    papers = [
        {"paper_id": f"P{i:04d}", "title": f"TTA paper {i}", "url": f"http://x/{i}",
         "abstract": "We study test-time adaptation under distribution shift."}
        for i in range(1, 13)
    ]
    brief = render_research_brief_markdown(
        goal=f"# Goal\n\n{_GOAL}", papers=papers, sections=["Test Time Adaptation", "Shifts"]
    )
    # The "Findings across ..." open-problems bullet is omitted (not dangling) when
    # no genuine lens survives.
    assert "Findings across the comparison lenses" not in brief, brief
