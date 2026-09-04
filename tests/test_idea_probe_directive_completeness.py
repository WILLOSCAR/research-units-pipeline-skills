"""Regression: idea-memo probe/audit/next-step directives are not clipped.

A follow-on read of a generated memo found the "Smallest decisive probe" bullets
(§3-5) and the §9 next-step ended mid-sentence — "...for any ablation that already
fixes planner quality and broader" (dropping ", and if the conclusion survives,
demote this direction") and "...whether observability granularity is already"
(dropping the control it should be isolated against). Neither directive told the
reader what to actually do.

Cause: these complete instructional templates were `clean_sentence`-truncated at a
char limit (180/220) that a long embedded anchor-paper title pushed past, clipping
the actionable clause. Fix: cap the embedded title and raise the instruction-sentence
limits so the directive's actionable clause is never dropped.

These tests exercise the deterministic renderers directly (fast); the full-engine
end-to-end behaviour is covered by the other whole-memo idea-brainstorm tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.ideation import build_report_payload, report_markdown

_LONG_TITLE = "Skill Transfer and Discovery for Sim-to-Real Learning: A Representation-Based Viewpoint"


def _shortlist_record() -> dict:
    return {
        "rank": 1,
        "direction_id": "D1",
        "title": "Observability granularity vs planner depth",
        "cluster": "sim-real transfer",
        "focus_axis": "observability granularity",
        "main_confound": "planner quality and broader agent competence",
        "one_line_thesis": "Agent-loop gains are hard to interpret because observation access and planner both change.",
        "why_this_ranks_here": "Leads because it offers the fastest path to a decisive causal attribution result, and because it has a clear thesis-sized payoff.",
        "why_prioritized": "Fast path to a decisive control.",
        "why_interesting": "It reframes how planner gains are credited.",
        "missing_piece": "A fixed-interface comparison varying only observation access.",
        "academic_value": "A causal-attribution result plus a reporting rule.",
        "contribution_shape": "A causal-attribution result plus a reporting rule for agent-loop papers.",
        "what_counts_as_insight": "The failure taxonomy changes, not just the aggregate score.",
        "best_fit": "an empirical controls paper",
        "evidence_confidence": "medium",
        "paper_ids": ["P0001"],
        "possible_variants": ["vary only observation access"],
        "weakness_conditions": ["an anchor already runs the control"],
        "kill_criteria": ["Kill quickly if an anchor paper already fixes observation access while varying planner quality."],
        # The instructional directives with a LONG embedded anchor title.
        "first_probes": [
            "Intervention: vary observability granularity while holding planner quality and broader agent competence as fixed as possible on a small public task slice. Readout: success rate plus failure-type shifts. Decisive if the interpretation changes even after the control.",
            f"Prior-work audit: inspect {_LONG_TITLE} for any ablation that already fixes planner quality and broader agent competence, and if the conclusion survives, demote this direction.",
        ],
        "anchor_reading_notes": [{"paper_id": "P0001", "paper_title": _LONG_TITLE, "note": "reports concrete behaviour on a small task slice"}],
    }


def _memo() -> str:
    payload = build_report_payload(
        topic="reliable adaptation of embodied agents under distribution shift",
        shortlist=[_shortlist_record()],
        deferred=[],
        trace_paths={},
    )
    return report_markdown(payload)


def test_prior_work_audit_bullet_is_complete() -> None:
    memo = _memo()
    audits = [ln for ln in memo.splitlines() if ln.strip().startswith("- Prior-work audit:")]
    assert audits, memo
    for bullet in audits:
        assert bullet.rstrip().endswith("demote this direction."), bullet


def test_intervention_bullet_is_complete() -> None:
    memo = _memo()
    intervs = [ln for ln in memo.splitlines() if ln.strip().startswith("- Intervention:") and "Readout:" in ln]
    assert intervs, memo
    for bullet in intervs:
        assert "even after the control" in bullet, bullet


def test_next_step_directive_is_complete() -> None:
    memo = _memo()
    tail = memo.split("Suggested next reading", 1)
    assert len(tail) == 2, memo
    start = next(ln for ln in tail[1].splitlines() if ln.strip().startswith("- Start with"))
    assert "isolated against" in start, start
    assert not start.rstrip().endswith("is already"), start
