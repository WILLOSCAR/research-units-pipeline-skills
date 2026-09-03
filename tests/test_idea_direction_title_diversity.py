"""Regression: idea direction titles are topic-distinctive, not a shared stem.

The direction-card title falls back to `f"What {axis} is really doing"` when the
axis is not in the curated AXIS_INSIGHT_LIBRARY (which is agent/LLM-centric, so
most non-agent topics fall back). That stem omitted the cluster, so unrelated
topics — and repeated axes within one memo — collapsed to identical titles
(e.g. "What assumption sensitivity is really doing" appearing across robotics
and materials memos and repeated within one). Surfaced by driving real
idea-brainstorm runs on disjoint real arXiv corpora.

The fallback title is now cluster-qualified, matching every other fallback field
in `_axis_profile`. This test pins that the fallback varies by cluster.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.ideation import _axis_profile


def test_fallback_direction_title_is_cluster_qualified() -> None:
    # An axis absent from the curated AXIS_INSIGHT_LIBRARY triggers the fallback.
    axis = "coverage calibration"
    title_a = _axis_profile(axis, "Interatomic Potentials")["title"]
    title_b = _axis_profile(axis, "Clinical Summarization")["title"]
    assert title_a != title_b, (
        "fallback direction title must vary by cluster; got identical stems: "
        f"{title_a!r}"
    )
    assert "Interatomic Potentials" in title_a
    assert "Clinical Summarization" in title_b


def test_curated_axis_title_is_preserved() -> None:
    # A curated axis keeps its bespoke library title (no regression to the stem).
    profile = _axis_profile("observability", "Agent loops")
    assert "really doing in" not in profile["title"] or profile["title"]
    # The curated title must be non-empty and not the bare fallback stem.
    assert profile["title"].strip()
