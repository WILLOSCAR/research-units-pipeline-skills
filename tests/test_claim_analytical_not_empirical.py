"""Regression: analytical / design claims are typed conceptual, not empirical.

A read of a generated REVIEW.md for a strong, concrete manuscript (Tensor
Decomposition Networks for MLIPs, real corpus abstract) landed on 'Weak reject:
2 major concerns' — but BOTH major concerns were byte-identical
('...no concrete metric, dataset, or benchmark detail appears in the extracted
claim text') and targeted the method's DESIGN/COMPLEXITY sentences, not results.
`classify_claim` had typed those sentences empirical because they pair a result
verb ('reduce') with a number (asymptotic notation O(L^3)/O(L^6)); the
evidence-auditor then demanded a dataset/metric they were never going to have.

`classify_claim` now treats a complexity-bound / parameter-count reduction / a
proven theoretical property as an ANALYTICAL claim (conceptual), so the auditor
does not manufacture a spurious major concern. Real measured results
(improves 6.4 points, MAE 5.06 meV/atom, F1 0.872, reduces error 4.1%) stay
empirical. After the fix the same manuscript's review reads 'Weak accept: no
major concerns'.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_text import classify_claim


def test_complexity_and_design_claims_are_conceptual() -> None:
    analytical = [
        "To further reduce the number of parameters, we propose path-weight sharing that ties all "
        "multiplicity-space weights across the O(L^3) CG paths into a single shared parameter set.",
        "The computational complexity of tensor products is reduced from O(L^6) to O(L^4).",
        "With the CP decomposition, we prove a uniform bound on the induced error of SO(3)-equivariance "
        "and the universality of approximating any equivariant bilinear map.",
        "The asymptotic time complexity is reduced from quadratic to linear in the sequence length.",
    ]
    for s in analytical:
        assert classify_claim(s) == "conceptual", s


def test_real_measured_results_stay_empirical() -> None:
    empirical = [
        "On four benchmarks it improves task success by 6.4 points over the strongest baseline.",
        "The model reaches a mean absolute error of 5.06 meV/atom on the test set.",
        "CE-VarNet reaches F1 0.872 versus 0.821 for the strongest ensemble baseline.",
        "Our loss reduces test error by 4.1% on ImageNet.",
        "The method achieves 91% accuracy on the held-out split.",
    ]
    for s in empirical:
        assert classify_claim(s) == "empirical", s


def test_complexity_with_a_measured_metric_stays_empirical() -> None:
    # A sentence that pairs complexity talk with an ACTUAL measured metric result
    # is still a result — the analytical guard must not swallow it.
    s = "Despite the O(n) memory, the model reaches 92.5% accuracy on the benchmark."
    assert classify_claim(s) == "empirical", s
