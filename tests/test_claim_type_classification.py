"""Regression: claim classification requires a MEASURED RESULT to be empirical.

An independent review of the paper-review claim-extraction
intermediate artifact found claim-type misclassification: `classify_claim`
labeled any sentence with a number OR an empirical-hint token as "empirical",
so a contribution ("We claim a confidence-gated retrieval policy, a
cache-coherent memory, and an evaluation protocol"), a protocol statement ("We
report over five seeds with 95% confidence intervals"), and a limitation ("The
evaluation is limited to four benchmarks; ... confounding attribution of the
reported 6.4 points") were all typed empirical.

An empirical claim asserts a measured result (improves/reaches/outperforms/
reduces/ablation delta + a quantity or comparison). Contribution/definition,
experimental-protocol, and limitation framings are conceptual even when they
mention numbers.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_text import classify_claim


def test_measured_results_are_empirical() -> None:
    empirical = [
        "On four benchmarks it improves task success by 6.4 points over the strongest retrieval baseline while halving adaptation latency.",
        "On four benchmarks, CGC-RAG improves task success by 6.4 points over retrieval.",
        "On the TCGA dataset, CE-VarNet reaches F1 0.872 versus 0.821 for the strongest ensemble baseline.",
        "Ablations remove the gate (-4.1) and the cache (-2.3).",
    ]
    for s in empirical:
        assert classify_claim(s) == "empirical", s


def test_contribution_protocol_limitation_are_conceptual() -> None:
    conceptual = [
        # Contribution / definition (numbers absent or not a result).
        "We claim a confidence-gated retrieval policy, a cache-coherent memory, and an evaluation protocol separating task success from confounding factors.",
        "a confidence-gated retrieval policy improves test-time adaptation in robotic manipulation without test-time weight updates.",
        "We argue a coverage-calibrated confidence filter is the right primitive.",
        # Experimental protocol (has "95%" but asserts no result).
        "We report over five seeds with 95% confidence intervals.",
        # Limitation / caveat (mentions "four" and "6.4" but is a caveat).
        "The evaluation is limited to four benchmarks; the gate threshold is tuned per benchmark, confounding attribution of the reported 6.4 points.",
    ]
    for s in conceptual:
        assert classify_claim(s) == "conceptual", s


def test_bare_number_without_result_is_not_empirical() -> None:
    # A number alone (e.g. a section reference or a count) must not force empirical.
    assert classify_claim("Section 3 introduces the 2 core modules of the system.") == "conceptual"
