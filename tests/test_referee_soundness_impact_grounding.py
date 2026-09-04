"""Regression: referee Soundness + Impact are grounded in the manuscript.

Before this fix the referee report's Soundness bullet was a bare count
("The review surfaced N major and M minor evidence issues.") and the Impact
bullet was a hardcoded literal ("If the major issues are fixed, the work could
become easier to compare and reproduce.") — byte-identical across every paper.
A referee learned neither WHICH claim's evidence was weak nor what THIS paper's
contribution would be if fixed.

The renderer already receives the manuscript-specific major gap, claims, and
novelty row (used for Summary/Novelty/Clarity). This locks that Soundness now
names the load-bearing claim + concern and Impact references the paper's own
headline result + closest related work, and that both vary between two distinct
manuscripts.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_rubric_review_markdown


def _section(review: str, header: str, nxt: str) -> str:
    return review.split(header, 1)[1].split(nxt, 1)[0]


_ROBOT = dict(
    claim_count=8,
    gap_count=8,
    major_gaps=[
        {
            "claim_id": "C04",
            "gap_id": "G04",
            "gap": "The empirical claim is underspecified: no concrete metric or benchmark appears.",
            "minimal_fix": "State the task, metric, baseline, and result.",
        }
    ],
    novelty_available=True,
    claims=[
        {
            "claim_id": "C01",
            "text": "On four benchmarks it improves task success by 6.4 points over retrieval.",
            "claim_type": "empirical",
            "scope": "abstract",
        },
        {
            "claim_id": "C04",
            "text": "a confidence-gated retrieval policy improves robotic test-time adaptation.",
            "claim_type": "conceptual",
            "scope": "method",
        },
    ],
    novelty_row={
        "claim_id": "C01",
        "related_work": "Salemi et al. Retrieval-augmented methods for robotics. 2024",
        "overlap": "adjacent problem setting",
        "delta": "claimed method delta requires verification",
    },
    minor_gaps=[{"claim_id": "C02", "gap": "needs a clearer boundary", "minimal_fix": "clarify exclusions"}],
)

_GENOMICS = dict(
    claim_count=8,
    gap_count=8,
    major_gaps=[
        {
            "claim_id": "C03",
            "gap_id": "G03",
            "gap": "The coverage-calibrated filter's gain is not attributed cleanly.",
            "minimal_fix": "Report an ablation isolating the filter.",
        }
    ],
    novelty_available=True,
    claims=[
        {
            "claim_id": "C01",
            "text": "On TCGA it improves F1 by 5.1 points over the strongest ensemble baseline.",
            "claim_type": "empirical",
            "scope": "abstract",
        },
        {
            "claim_id": "C03",
            "text": "The coverage-calibrated filter improves variant calling.",
            "claim_type": "conceptual",
            "scope": "conclusion",
        },
    ],
    novelty_row={
        "claim_id": "C01",
        "related_work": "Salemi et al. Retrieval-augmented methods for variant calling. 2024",
        "overlap": "adjacent problem setting",
        "delta": "claimed method delta requires verification",
    },
    minor_gaps=[{"claim_id": "C02", "gap": "calibration is depth-tuned", "minimal_fix": "hold the threshold fixed"}],
)


def test_soundness_names_the_load_bearing_claim() -> None:
    review = render_rubric_review_markdown(**_ROBOT)
    soundness = _section(review, "### Soundness", "### Clarity")
    # Still reports the counts, in referee language...
    assert "3 major" not in soundness  # only 1 major gap supplied here
    # 1 minor gap supplied -> "1 minor concern" (the count the reader sees), not
    # the raw gap_count-derived 7 that the old "(from 7 minor gap(s))" bookkeeping
    # parenthetical exposed.
    assert "1 major concern" in soundness and "1 minor concern" in soundness, soundness
    assert "minor gap" not in soundness, soundness
    # ...but now anchors on the specific claim + its concern.
    assert "claim C04" in soundness, soundness
    assert "confidence-gated retrieval policy" in soundness, soundness
    assert "underspecified" in soundness, soundness


def test_impact_references_headline_and_related_work() -> None:
    review = render_rubric_review_markdown(**_ROBOT)
    impact = _section(review, "### Impact", "### Major Concerns")
    assert "6.4 points" in impact, impact  # THIS paper's headline result
    assert "Salemi" in impact, impact  # closest related work
    # It is not the old hardcoded literal.
    assert "the work could become easier to compare and reproduce" not in impact


def test_soundness_and_impact_vary_between_manuscripts() -> None:
    robot = render_rubric_review_markdown(**_ROBOT)
    genom = render_rubric_review_markdown(**_GENOMICS)
    r_sound = _section(robot, "### Soundness", "### Clarity")
    g_sound = _section(genom, "### Soundness", "### Clarity")
    r_impact = _section(robot, "### Impact", "### Major Concerns")
    g_impact = _section(genom, "### Impact", "### Major Concerns")
    assert r_sound != g_sound, (r_sound, g_sound)
    assert r_impact != g_impact, (r_impact, g_impact)
    # Each names its own manuscript's distinctive claim / result.
    assert "C04" in r_sound and "C03" in g_sound
    assert "6.4 points" in r_impact and "5.1 points" in g_impact


def test_soundness_falls_back_gracefully_with_no_major_gap() -> None:
    review = render_rubric_review_markdown(
        claim_count=2, gap_count=1, major_gaps=[], novelty_available=True,
        claims=_GENOMICS["claims"], novelty_row=_GENOMICS["novelty_row"],
        minor_gaps=[{"claim_id": "C02", "gap": "calibration is depth-tuned", "minimal_fix": "hold fixed"}],
    )
    soundness = _section(review, "### Soundness", "### Clarity")
    assert "0 major" in soundness, soundness
    # Falls back to the first minor concern rather than crashing / going generic.
    assert "calibration is depth-tuned" in soundness, soundness
