"""Regression: generic taxonomy children are concepts, not years / connectives.

On arXiv corpora spanning test-time adaptation and clinical summarization, the
generic-profile taxonomy-builder emitted children that were bare
title tokens with no topical meaning — e.g. "Shifts", "Addressing", "Against",
"Aware", "Applications", and even a bare year "2023". A reader's brief was
structured by noise.

The builder now (a) rejects bare-year and generic connective/verb tokens as
children (`_is_concept_token`), and (b) upgrades a surviving single-token child
to a corpus bigram phrase when one exists (`_child_bigram_label`), so children
read as research sub-areas. This test drives the generic build on a title set
seeded with exactly those junk tokens and asserts none survive as a child name.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".codex" / "skills" / "taxonomy-builder" / "scripts" / "run.py"

# Real-shaped titles that surface bare-year and connective tokens as
# high-frequency candidates alongside the real topic tokens.
_TITLES = [
    "Addressing Distribution Shift against Corruption in 2023",
    "Test-Time Adaptation against Distribution Shifts 2023",
    "Confidence-Aware Test-Time Adaptation under Distribution Shift",
    "Benchmarking Distribution Shift Robustness in 2023",
    "Domain Adaptation against Covariate Shift for Vision Models",
    "Aware Prediction Refinement for Test-Time Distribution Shift",
    "Applications of Test-Time Adaptation to Anomaly Detection",
    "Continual Test-Time Adaptation against Temporal Distribution Shift",
    "Distribution Shift Aware Confidence Maximization at Test Time",
    "Graph Test-Time Adaptation under Distribution Shift 2023",
    "Robust Test-Time Adaptation against Label Distribution Shift",
    "Source-Free Domain Adaptation against Distribution Shift",
]


def _build_taxonomy(tmp_path: Path) -> list[dict]:
    (tmp_path / "papers").mkdir(parents=True, exist_ok=True)
    (tmp_path / "outline").mkdir(parents=True, exist_ok=True)
    with (tmp_path / "papers" / "core_set.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["paper_id", "title", "year", "url", "reason"])
        writer.writeheader()
        for idx, title in enumerate(_TITLES, start=1):
            writer.writerow(
                {"paper_id": f"P{idx:04d}", "title": title, "year": 2023, "url": f"https://example.org/{idx}", "reason": "fixture"}
            )
    (tmp_path / "queries.md").write_text("- draft_profile: idea_brainstorm\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SKILL), "--workspace", str(tmp_path), "--outputs", "outline/taxonomy.yml"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return yaml.safe_load((tmp_path / "outline" / "taxonomy.yml").read_text(encoding="utf-8")) or []


def test_generic_taxonomy_children_are_not_years_or_connectives(tmp_path: Path) -> None:
    taxonomy = _build_taxonomy(tmp_path)
    assert taxonomy, "expected a non-empty taxonomy"
    child_names = [
        str(c.get("name") or "").strip()
        for n in taxonomy
        for c in (n.get("children") or [])
    ]
    assert child_names, "expected a 2-level taxonomy with children"

    # No child is a bare year.
    for name in child_names:
        assert not name.strip().isdigit(), f"bare-year child name: {name!r}"
        assert "2023" != name.strip(), f"bare-year child name: {name!r}"

    # No child is a lone connective/verb non-concept token.
    _JUNK = {"against", "aware", "addressing", "applications", "can", "via", "using"}
    for name in child_names:
        # A single-word child must not be a pure connective/verb token.
        if len(name.strip().split()) == 1:
            assert name.strip().lower() not in _JUNK, f"non-concept single-word child: {name!r}"


def test_generic_taxonomy_spine_prefers_multiword_phrase(tmp_path: Path) -> None:
    # On a corpus dominated by one multi-word concept, the leading cluster spine
    # should be the full phrase ("Test Time Adaptation" / "Distribution Shift"),
    # not a bare single token ("Test") that would surface in the reader brief as
    # a meaningless "Comparison lens".
    taxonomy = _build_taxonomy(tmp_path)
    names = [str(n.get("name") or "").strip() for n in taxonomy]
    assert names, "expected top-level clusters"
    # At least one spine is a real multi-word phrase.
    assert any(len(name.split()) >= 2 for name in names), names
    # The leading spine is not a bare high-frequency single token.
    assert len(names[0].split()) >= 2, f"leading spine is a bare token: {names[0]!r}"
