"""Regression: idea-screener rationale is direction-specific and decision-consistent.

A read of the IDEA_SCREENING_TABLE (clinical corpus)
found the Rationale column was repeated boilerplate: three different directions
(abstractive failure modes / clinical scope boundary / clinical sensitivity) all
read "Strongest on concrete anchor evidence + clean first probe; main risk is
controlling nearby design choices and evaluation framing cleanly." — and, worse, the
SAME rationale appeared with DIFFERENT decisions (a "keep" and a "maybe").

`score_direction_cards` built the rationale purely from score-dimension flags, so
sibling directions with equal scores got identical text regardless of decision. It
now names the direction's own focus axis (direction-specific) and frames it by the
decision ("Keep — X is strongest on" / "Maybe — X rests on" / "Drop — X offers
only"), so a keep and a maybe never read identically.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.ideation import DirectionCard, score_direction_cards


def _card(did: str, axis: str, conf: str = "medium") -> DirectionCard:
    return DirectionCard(
        direction_id=did, cluster="Clinical Text / Clinical Abstractive", direction_type="research",
        title=f"What {axis} is really doing in Clinical Text", focus_axis=axis,
        main_confound="nearby design choices and evaluation framing",
        program_kind="mechanism clarification", contribution_shape="a cleaner explanatory variable",
        time_to_clarity="medium", one_line_thesis="thesis", why_interesting="interesting",
        literature_suggests=["lit"], closest_prior_gap=["gap"], missing_piece="missing",
        possible_variants=["v"], academic_value="value", first_probes=["probe"],
        what_counts_as_insight="insight", weakness_conditions=["weak"], kill_criteria=["kill"],
        what_would_change_mind=["change"], best_fit="fit", why_this_ranks_here="ranks",
        evidence_confidence=conf, paper_ids=["P0001"], signal_ids=["S1"], anchor_reading_notes=[],
    )


_WEIGHTS = {
    "discussion_worthiness": 0.24, "academic_value": 0.22, "evidence_grounding": 0.18,
    "direction_distinctness": 0.16, "first_probe_clarity": 0.1, "thesis_potential": 0.1,
}


def _screen():
    cards = [
        _card("DIR-001", "clinical sensitivity"),
        _card("DIR-002", "abstractive failure modes"),
        _card("DIR-003", "clinical scope boundary"),
        _card("DIR-004", "adapted sensitivity", conf="low"),
        _card("DIR-005", "adapted scope boundary", conf="low"),
    ]
    return score_direction_cards(
        cards, focus_clusters=["Clinical Text / Clinical Abstractive"],
        keep_rank_max=3, maybe_rank_max=4, score_weights=_WEIGHTS,
    )


_AXES = {
    "DIR-001": "clinical sensitivity", "DIR-002": "abstractive failure modes",
    "DIR-003": "clinical scope boundary", "DIR-004": "adapted sensitivity",
    "DIR-005": "adapted scope boundary",
}


def test_rationales_are_direction_specific() -> None:
    rows = _screen()
    rationales = [r.rationale for r in rows]
    # No two directions share the exact rationale text.
    assert len(set(rationales)) == len(rationales), rationales
    # Each rationale names its own focus axis.
    for r in rows:
        assert _AXES[r.direction_id] in r.rationale, (r.direction_id, r.rationale)


def test_rationale_reflects_the_decision() -> None:
    rows = _screen()
    for r in rows:
        if r.recommendation == "keep":
            assert r.rationale.startswith("Keep —"), r.rationale
        elif r.recommendation == "maybe":
            assert r.rationale.startswith("Maybe —"), r.rationale
        else:
            assert r.rationale.startswith("Drop —"), r.rationale


def test_keep_and_maybe_never_read_identically() -> None:
    rows = _screen()
    keeps = {r.rationale for r in rows if r.recommendation == "keep"}
    maybes = {r.rationale for r in rows if r.recommendation == "maybe"}
    assert keeps.isdisjoint(maybes), (keeps, maybes)
