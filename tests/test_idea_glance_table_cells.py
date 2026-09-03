"""Regression: idea-memo 'at a glance' table cells are self-contained phrases.

A read of a generated idea memo (embodied-adaptation corpus) found every cell of the "Top directions at a glance" table (§2) truncated
mid-phrase, dangling on a preposition/article: "Leads because it offers the fastest
path to a", "Could yield a causal-attribution result plus a", "Kill quickly if an
anchor paper already fixes". The glance table is the reader's fast-triage artifact,
so a dangling fragment defeats its purpose.

`shortlist_snapshot_table` used `clean_sentence(..., limit=52/56/54)`, a hard char
truncation of a full sentence. It now uses `_glance_cell`, which cuts at the first
clause boundary and drops any trailing function word so a cell ends on content, not
on "to a". (The §3-5 "Smallest decisive probe" and §9 next-step mid-sentence cuts
the models also flagged trace to a separate serialization-roundtrip owner and are a
named follow-on, not addressed here.)
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.ideation import _glance_cell, shortlist_snapshot_table

_DANGLING = {
    "a", "an", "the", "to", "of", "and", "or", "but", "plus", "vs", "with", "for",
    "in", "on", "at", "by", "from", "into", "than", "as", "that", "which", "while",
    "because", "if", "it", "its",
}


def _last_word(cell: str) -> str:
    words = cell.split()
    return words[-1].lower().strip(",;:-") if words else ""


def test_glance_cell_does_not_dangle_on_function_word() -> None:
    for full in (
        "Leads because it offers the fastest path to a decisive causal attribution result in sim real transfer, and because it has the clearest path.",
        "Could yield a causal-attribution result plus a reporting rule for agent-loop papers about planning.",
        "Kill quickly if an anchor paper already fixes observation access while varying planner quality.",
    ):
        cell = _glance_cell(full)
        assert cell, full
        assert _last_word(cell) not in _DANGLING, (cell, _last_word(cell))
        assert not cell.endswith((" to a", " plus a", " of the", " and")), cell


def test_glance_cell_prefers_first_clause() -> None:
    cell = _glance_cell("Stays in the lead set because it opens a distinct systems boundary wedge, but it trails the first two.")
    # Cut at the coordinating ", but" clause boundary -> complete phrase, no trailing "but".
    assert "systems boundary wedge" in cell, cell
    assert "trails" not in cell, cell


def test_glance_cell_empty_input() -> None:
    assert _glance_cell("") == ""
    assert _glance_cell(None) == ""


def test_snapshot_table_cells_are_not_dangling() -> None:
    records = [
        {
            "rank": 1,
            "title": "Observability granularity vs planner depth",
            "why_this_ranks_here": "Leads because it offers the fastest path to a decisive causal attribution result in sim real transfer, and because it has the clearest path to a thesis-sized contribution.",
            "contribution_shape": "Could yield a causal-attribution result plus a reporting rule for agent-loop papers about controlling observation access.",
            "kill_criteria": ["Kill quickly if an anchor paper already fixes observation access while varying planner quality and the conclusion survives."],
        }
    ]
    table = shortlist_snapshot_table(records)
    # Parse the single data row's cells.
    data_row = [ln for ln in table.splitlines() if ln.startswith("| 1 |")][0]
    cells = [c.strip() for c in data_row.strip("|").split("|")]
    for cell in cells[2:]:  # skip Rank + Direction
        assert _last_word(cell) not in _DANGLING, (cell, table)
