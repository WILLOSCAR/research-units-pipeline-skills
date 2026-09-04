"""Regression: named-metric results are classified empirical.

A review, run on a REAL arXiv abstract used as the manuscript body,
found a measured test-set result — "a mean absolute error of 5.06 meV/atom for
energy and 128.51 meV/A for forces" — classified conceptual, because it used no
canonical result verb and no EMPIRICAL_HINT token.

classify_claim now recognizes an explicit named-metric phrase (MAE/RMSE/error
of/accuracy of/F1/AUC/mIoU/meV-per-unit) with a value as empirical, and the
protocol-framing precedence yields conceptual only when no such metric value is
present (so "we report an RMSE of 0.03" is empirical, but "we report over five
seeds with 95% CI" stays conceptual).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_text import classify_claim


def test_named_metric_result_is_empirical() -> None:
    for sentence in (
        "The model demonstrates excellent predictive performance on an independent test set, "
        "with a mean absolute error of 5.06 meV/atom for energy and 128.51 meV/Å for forces.",
        "We report an RMSE of 0.03 eV on the held-out set.",
        "The classifier reaches an accuracy of 91% on the benchmark.",
        "The system attains an F1 of 0.82 and precision of 0.88.",
        "The segmenter records a mIoU of 79.2 on Cityscapes.",
    ):
        assert classify_claim(sentence) == "empirical", sentence


def test_protocol_without_metric_value_stays_conceptual() -> None:
    for sentence in (
        "We report results over five seeds with 95% confidence intervals.",
        "We evaluate on three datasets using standard splits.",
        "We run the experiments following the established protocol.",
    ):
        assert classify_claim(sentence) == "conceptual", sentence


def test_contribution_and_background_still_conceptual() -> None:
    for sentence in (
        "We propose a general-purpose interatomic potential for amorphous alloys.",
        "Machine learning offers a powerful alternative with near-DFT accuracy.",
        "The method assumes access to a differentiable simulator.",
    ):
        assert classify_claim(sentence) == "conceptual", sentence
