"""Regression: idea-signal-mapper produces globally-unique signal_ids.

`build_signal_rows` derived signal_id from `slugify(cluster)[:16]` plus a
PER-CLUSTER index. Two distinct clusters whose slugs share the same first 16
characters (e.g. "Clinical Summarization Faithfulness" and "Clinical
Summarization Evaluation" both slugify to "clinical-summari") therefore produced
identical ids (SIG-clinical-summari-1/2/3), and the idea-signal-mapper's own
`idea_signal_table_duplicate_ids` gate blocked the run. Surfaced by driving the
real idea-brainstorm workflow on a real clinical-summarization arXiv corpus.

The fix folds a cluster ordinal into the id. This test pins uniqueness across
slug-colliding clusters, mirroring the skill's caller loop.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.ideation import build_signal_rows


def _note(paper_id: str) -> dict:
    return {
        "paper_id": paper_id,
        "summary": "A controlled study of the topic.",
        "method": "method",
        "results": "results",
        "limitations": ["confounded by budget"],
    }


def test_signal_ids_are_unique_across_slug_colliding_clusters() -> None:
    # Distinct clusters that slugify to the same 16-char prefix.
    clustered = {
        "Clinical Summarization Faithfulness": [_note("P0001"), _note("P0002")],
        "Clinical Summarization Evaluation": [_note("P0003"), _note("P0004")],
        "Clinical Summarisation Protocols": [_note("P0005")],
    }
    rows = []
    for cluster_index, (cluster, notes) in enumerate(clustered.items()):
        rows.extend(
            build_signal_rows(cluster=cluster, notes=notes, cluster_index=cluster_index)
        )
    ids = [r.signal_id for r in rows]
    assert ids, "expected signal rows"
    assert len(ids) == len(set(ids)), f"duplicate signal_ids across clusters: {ids}"


def test_signal_ids_unique_within_a_single_cluster() -> None:
    rows = build_signal_rows(
        cluster="Memory and retrieval",
        notes=[_note("P0001"), _note("P0002"), _note("P0003")],
        cluster_index=0,
    )
    ids = [r.signal_id for r in rows]
    assert len(ids) == len(set(ids)), ids
