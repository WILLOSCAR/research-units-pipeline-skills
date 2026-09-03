"""Regression: the generic taxonomy has distinct, non-overlapping clusters.

The generic-profile taxonomy-builder derived cluster names and children from
`candidate_keywords` (single high-frequency title tokens). Because the children
were drawn from the same title pool without excluding the parent token or the
other top-level tokens, clusters collapsed into the same reshuffled keyword set
(e.g. top-level ['Time','Test','Adaptation','Distribution'] where "Time"'s
children were ['Time','Adaptation','Test']). That non-distinctness propagated
downstream into near-duplicate idea-brainstorm directions — a reader-facing
Artifact-quality failure observed on an arXiv corpus.

This test builds a taxonomy from a collision-prone title set and asserts the
top-level names are unique, the child names are globally unique, and no child
repeats a parent's name.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".codex" / "skills" / "taxonomy-builder" / "scripts" / "run.py"

# Titles that share a few high-frequency tokens (time / test / adaptation /
# distribution / shift) — the exact shape that previously produced degenerate,
# mutually-overlapping keyword clusters.
_TITLES = [
    "Benchmarking Test-Time Adaptation against Distribution Shifts",
    "Test-Time Adaptation under Real-World Distribution Shifts",
    "Time Series Prediction under Distribution Shift",
    "Label Distribution Shift-Aware Test-Time Adaptation",
    "Accurate Test-Time Adaptation for Time Series Forecasting",
    "Curated Test-Time Adaptation for Time-Series Anomaly Detection",
    "Continual Test-Time Adaptation against Temporal Distribution Shift",
    "Addressing Distribution Shift with Test-Time Adaptation",
    "Sim-to-Real Adaptation under Dynamics Distribution Shift",
    "Prediction Refinement for Test-Time Distribution Adaptation",
    "Confidence Maximization for Test-Time Distribution Shift",
    "Graph Test-Time Adaptation under Distribution Shift",
]


def _build_taxonomy(tmp_path: Path) -> list[dict]:
    (tmp_path / "papers").mkdir(parents=True, exist_ok=True)
    (tmp_path / "outline").mkdir(parents=True, exist_ok=True)
    with (tmp_path / "papers" / "core_set.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["paper_id", "title", "year", "url", "reason"])
        writer.writeheader()
        for idx, title in enumerate(_TITLES, start=1):
            writer.writerow(
                {"paper_id": f"P{idx:04d}", "title": title, "year": 2024, "url": f"https://example.org/{idx}", "reason": "fixture"}
            )
    (tmp_path / "queries.md").write_text("- draft_profile: idea_brainstorm\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SKILL), "--workspace", str(tmp_path), "--outputs", "outline/taxonomy.yml"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return yaml.safe_load((tmp_path / "outline" / "taxonomy.yml").read_text(encoding="utf-8")) or []


def test_generic_taxonomy_clusters_are_distinct_and_non_overlapping(tmp_path: Path) -> None:
    taxonomy = _build_taxonomy(tmp_path)
    assert taxonomy, "expected a non-empty taxonomy"

    names = [str(n.get("name") or "").strip() for n in taxonomy]
    children = [
        str(c.get("name") or "").strip()
        for n in taxonomy
        for c in (n.get("children") or [])
    ]
    assert names, "expected top-level clusters"
    assert children, "expected 2-level taxonomy with children"

    # Top-level cluster names are unique.
    assert len(names) == len(set(names)), f"duplicate top-level cluster names: {names}"
    # Child names are globally unique across all clusters.
    assert len(children) == len(set(children)), f"duplicate child names across clusters: {children}"
    # No child repeats any parent's name (the old degeneracy).
    overlap = set(names) & set(children)
    assert not overlap, f"children reuse parent cluster names: {overlap}"
