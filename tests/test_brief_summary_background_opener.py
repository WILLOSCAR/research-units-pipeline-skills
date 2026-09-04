"""Regression: brief key-theme summary picks the contribution over a background opener.

An L2 whole-SNAPSHOT read (real ml-interatomic corpus via the full research-brief
engine) found two "Key themes" / "What to read first" bullets that gave generic
field background instead of the paper's contribution: a benchmarking paper that
opens "Machine learning approaches have recently emerged as powerful tools to probe
structure-property relationships..." was summarized by that opener rather than by
its "Here, we benchmark popular MLIP..." contribution.

Two fixes in `_brief_summary`: (1) `background_pattern` now also penalizes the
"X have (recently) emerged as ..." and problem-statement openers ("Y is generally
not well known", "Z remains challenging", "traditional methods are costly");
(2) the contribution `action_pattern` now recognizes evaluative verbs
(benchmark/assess/quantify/measure/compare/analyze/investigate/explore), so a
"we benchmark ..." contribution outscores the background opener.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import _brief_summary


def test_benchmark_contribution_beats_emerged_opener() -> None:
    abstract = (
        "Machine learning approaches have recently emerged as powerful tools to probe "
        "structure-property relationships in crystals and molecules. Specifically, "
        "Machine learning interatomic potentials (MLIP) can accurately reproduce "
        "first-principles data. Here, we benchmark popular MLIP using the anharmonic "
        "vibrational Hamiltonian of ThO2 in the fluorite crystal structure."
    )
    summary = _brief_summary(abstract, max_words=45)
    assert "benchmark" in summary.lower(), summary
    assert "emerged as powerful tools" not in summary.lower(), summary


def test_emerged_opener_is_penalized() -> None:
    # A pure "have recently emerged" opener followed by a contribution -> the
    # contribution wins.
    abstract = (
        "Graph neural networks have recently emerged as a popular architecture. "
        "In this work, we develop a new message-passing scheme for interatomic potentials."
    )
    summary = _brief_summary(abstract, max_words=45)
    assert "develop" in summary.lower(), summary


def test_problem_statement_opener_is_penalized() -> None:
    abstract = (
        "Many materials' properties are generally not well known under extreme pressure. "
        "The authors present a self-consistent approach integrating computation and experiment."
    )
    summary = _brief_summary(abstract, max_words=45)
    assert "present a self-consistent approach" in summary.lower(), summary
    assert "not well known" not in summary.lower(), summary


def test_costly_methods_opener_is_penalized() -> None:
    abstract = (
        "Traditional trial-and-error methods for designing amorphous alloys are costly and inefficient. "
        "In this work, we develop a general-purpose machine learning interatomic potential."
    )
    summary = _brief_summary(abstract, max_words=45)
    assert "develop a general-purpose" in summary.lower(), summary


def test_genuine_contribution_first_still_wins() -> None:
    # No leading background — the contribution sentence is already first and stays.
    abstract = (
        "The authors propose CANDI, a curated test-time adaptation framework. "
        "It selectively adapts to potential false positives while preserving pretrained knowledge."
    )
    summary = _brief_summary(abstract, max_words=45)
    assert "propose candi" in summary.lower(), summary
