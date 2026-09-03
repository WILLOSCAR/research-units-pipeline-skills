"""Regression: unmatched clusters get per-cluster axes, not one shared triple.

`_cluster_profile` matches a cluster label against agent/LLM-domain
CLUSTER_AXIS_HINTS; when nothing matches (a non-agent topic, or a
keyword-derived cluster), it previously returned the SAME default triple
`["assumption sensitivity", "failure analysis", "scope boundary"]` for every
cluster. Every idea-brainstorm direction then explored the identical axis, so
the memo's lead directions collapsed to one axis — a reader-facing
Artifact-quality failure observed on an arXiv corpus.

The fallback now derives axes from the cluster's own distinctive terms, so
distinct clusters yield distinct axes. This test pins that two different
unmatched clusters no longer share an identical axis list, and that the curated
agent-domain hints still win when they match.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.ideation import _cluster_profile


def test_unmatched_clusters_get_distinct_axes() -> None:
    _, axes_time, _ = _cluster_profile("Time / Shifts")
    _, axes_test, _ = _cluster_profile("Test / Prediction")
    _, axes_dist, _ = _cluster_profile("Distribution / Real")
    # Each cluster's axes are grounded in its own leading term...
    assert axes_time != axes_test, (axes_time, axes_test)
    assert axes_time != axes_dist, (axes_time, axes_dist)
    assert axes_test != axes_dist, (axes_test, axes_dist)
    # ...and none is the bare pre-fix default triple.
    default = ["assumption sensitivity", "failure analysis", "scope boundary"]
    for axes in (axes_time, axes_test, axes_dist):
        assert axes != default, f"cluster fell back to the shared default triple: {axes}"


def test_curated_agent_hint_still_wins() -> None:
    # A cluster that matches an agent-domain hint keeps its curated axes.
    _, axes, _ = _cluster_profile("Agent loop / action space")
    assert axes == ["observability granularity", "action-space design", "tool/environment boundary"], axes
