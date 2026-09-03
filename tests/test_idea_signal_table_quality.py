"""Regression: idea-brainstorm signal-table Theme + Claim are clean.

The first L1 (intermediate-artifact) evaluator pass on IDEA_SIGNAL_TABLE.md
(which feeds the direction pool) found two deterministic defects:

1. Doubled Theme: the theme was `f"{profile['title']} in {cluster}"`, but the
   default profile title already ends "... in {cluster}", so it read
   "What X is really doing in CLUSTER in CLUSTER".
2. Truncated Claim/observation: `_claim_text` returned a note bullet verbatim,
   which could be a truncated abstract fragment ending mid-list
   ("... ImageNet-C, DomainNet,").

`_signal_theme` now cluster-qualifies the title exactly once; `_claim_text`
prefers a complete-sentence bullet and otherwise trims to a clean boundary.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.ideation import _signal_theme, _claim_text


def test_signal_theme_qualifies_cluster_once() -> None:
    # Default profile title already contains the cluster -> no doubling.
    default_title = "What feedback type is really doing in Test Time Adaptation / Distribution Shifts"
    theme = _signal_theme(default_title, "Test Time Adaptation / Distribution Shifts")
    assert theme == default_title, theme
    assert theme.lower().count("test time adaptation / distribution shifts") == 1, theme


def test_signal_theme_adds_cluster_to_short_custom_title() -> None:
    # A custom short title carries no cluster -> qualify once.
    theme = _signal_theme("Observability granularity vs planner depth", "Foundations & Interfaces")
    assert theme == "Observability granularity vs planner depth in Foundations & Interfaces", theme


def test_claim_text_prefers_complete_sentence_and_no_trailing_comma() -> None:
    note = {
        "key_results": [
            # Truncated abstract fragment ending mid-list.
            "To address this issue, we present a benchmark that systematically evaluates 13 prominent TTA methods and their variants on five widely used image classification datasets: CIFAR-10-C, CIFAR-100-C, ImageNet-C, DomainNet,",
            # A complete sentence.
            "The gate improves task success by 6.4 points over the strongest baseline.",
        ]
    }
    claim = _claim_text(note)
    assert not claim.rstrip().endswith(","), claim
    # Prefers the complete sentence.
    assert "improves task success by 6.4 points" in claim, claim


def test_claim_text_trims_when_only_fragment_available() -> None:
    note = {
        "summary_bullets": [
            "We evaluate representative TTA approaches across multiple pretrained foundation models, diverse downstream tasks, and heterogeneous datasets spanning in-distribution, out-of-distribution, and extreme shifts, reporting consistent trends.",
        ]
    }
    claim = _claim_text(note)
    # A complete sentence is returned intact (no trailing comma / dangling cut).
    assert not claim.rstrip().endswith(","), claim
    assert claim, "expected a non-empty claim"


def test_claim_text_drops_trailing_comma_from_midlist_fragment() -> None:
    # When a long fragment ends mid-list with a comma, the trailing comma is
    # dropped (clean_sentence trims to a clean boundary).
    note = {
        "key_results": [
            "The benchmark evaluates 13 prominent TTA methods on five datasets: CIFAR-10-C, CIFAR-100-C, ImageNet-C, DomainNet,",
        ]
    }
    claim = _claim_text(note)
    assert not claim.rstrip().endswith(","), claim
