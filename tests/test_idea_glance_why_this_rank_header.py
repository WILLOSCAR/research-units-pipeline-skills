"""Regression: the idea glance table's rank-rationale column is headed to match
its content ("Why this rank"), not mislabeled "Why now".

A read of an idea-brainstorm §2 glance table (embodied-adaptation
corpus, full engine) found the middle column headed "Why now" — promising a
timeliness reason — while every cell was fed `why_this_ranks_here`, a
rank-placement rationale ("Leads because ...", "Ranks behind X ...", "Stays in
the lead set ..."). The header promised something the cells never delivered.

`shortlist_snapshot_table` now heads the column "Why this rank".
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.ideation import shortlist_snapshot_table

_RECORDS = [
    {
        "rank": 1,
        "title": "Observability granularity vs planner depth",
        "why_this_ranks_here": "Leads because it offers the fastest path to a decisive causal attribution result in sim.",
        "contribution_shape": "Could yield a causal-attribution result plus a reporting rule for agent-loop papers.",
        "kill_criteria": ["Kill quickly if an anchor paper already fixes observation access while varying planner."],
    },
    {
        "rank": 2,
        "title": "Action-space design or agent competence?",
        "why_this_ranks_here": "Ranks behind Observability granularity vs planner depth because isolating the shape is slower.",
        "contribution_shape": "Could produce an action-space normalization protocol.",
        "kill_criteria": ["Kill quickly if the key anchor papers already normalize action vocabularies."],
    },
]


def test_glance_column_is_headed_why_this_rank_not_why_now() -> None:
    table = shortlist_snapshot_table(_RECORDS)
    header = table.splitlines()[0]
    assert "Why this rank" in header, header
    # The old, mismatched header must be gone.
    assert "Why now" not in header, header


def test_glance_column_still_carries_rank_rationale() -> None:
    table = shortlist_snapshot_table(_RECORDS)
    assert "Leads because" in table, table
    assert "Ranks behind" in table, table


def test_glance_other_headers_unchanged() -> None:
    header = shortlist_snapshot_table(_RECORDS).splitlines()[0]
    for label in ("Rank", "Direction", "If it survives", "Fast kill signal"):
        assert label in header, (label, header)
