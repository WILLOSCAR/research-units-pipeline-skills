"""Regression: reader-facing paper titles in the idea memo are not chopped mid-title.

Section 9 of a generated idea memo, "Suggested next reading", told the reader to
"read Skill Transfer and Discovery for Sim-to-Real Learning: A" — the title
"Skill Transfer and Discovery for Sim-to-Real Learning: A Representation-Based
Viewpoint" was hard-truncated at 70 characters, ending on a dangling article, so
it ran into the following word and was neither searchable nor readable. The same
clip fed the "closest prior anchor" prose in each Direction section.

`clean_title` uses a generous cap (typical arXiv titles fit whole) and drops a
trailing dangling article or preposition when a clip is unavoidable, so a
"read <title>" instruction never ends on "... Learning: A".

The last test drives `build_report_payload`, the function that renders the §9
directive, so the regression is covered end to end rather than only at the
helper.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.ideation import build_report_payload, clean_title

_REAL = "Skill Transfer and Discovery for Sim-to-Real Learning: A Representation-Based Viewpoint"


def test_typical_arxiv_title_kept_whole() -> None:
    # An 87-char real title fits under the generous cap and is not chopped.
    assert clean_title(_REAL) == _REAL


def test_clip_does_not_end_on_dangling_article() -> None:
    # A genuinely long title clips but must not end on a dangling article/preposition.
    long = (
        "A Very Long Title About Test Time Adaptation Under Distribution Shift For "
        "Embodied Agents In The Real World And Beyond The Frontiers Of"
    )
    out = clean_title(long)
    last = out.split()[-1].lower().strip(":,;-")
    assert last not in {"a", "an", "the", "of", "for", "to", "in", "on", "and", "or", "with", "via", "from"}, out
    assert not out.rstrip().endswith(":"), out


def test_short_title_unchanged() -> None:
    assert clean_title("Short Title") == "Short Title"
    assert clean_title("") == ""


def test_section9_read_instruction_has_full_title() -> None:
    # End-to-end over the report builder: §9's "Suggested next reading" directive
    # must name the anchor title in full. This is the shape the original defect
    # took — "read Skill Transfer and Discovery for Sim-to-Real Learning: A
    # looking specifically for ..." — where the clipped title runs straight into
    # the following word and the reader cannot tell where the title ends.
    payload = build_report_payload(
        topic="embodied adaptation",
        shortlist=[
            {
                "title": "Representation transfer under distribution shift",
                "focus_axis": "representation transfer",
                "main_confound": "task-shift confound",
                "first_probes": ["Check whether the reported gain survives a single-variable control."],
                "anchor_reading_notes": [{"paper_title": _REAL}],
            }
        ],
        deferred=[],
        trace_paths={},
    )
    directive = "\n".join(payload["next_steps"])

    assert "Learning: A looking" not in directive, "title chopped to a dangling 'A'"
    assert _REAL in directive, directive
