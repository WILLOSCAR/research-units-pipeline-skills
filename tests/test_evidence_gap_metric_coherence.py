"""Regression: evidence-auditor gap must not contradict a metric-bearing claim.

A whole-REVIEW.md coherence review found the referee report's load-bearing
Soundness/Major concern said claim C1 "is underspecified: no concrete metric,
dataset, or benchmark detail appears" — while C1 literally stated "a mean
absolute error of 5.06 meV/atom for energy and 128.51 meV/A for forces" on an
independent test set. The gap contradicted the claim's own text, making the
whole review incoherent.

_gap_for_claim now treats a claim that states a concrete metric (named error/
accuracy metric, or a numeric value with a unit) as HAVING a metric — so it gets
the "reports a concrete result but needs baseline/protocol context" gap (minor),
not the false "no concrete metric appears" gap (which drove a spurious major
soundness concern). A genuinely metric-less empirical claim still gets the
"underspecified" major gap (the overclaim/severity path is preserved).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "evidence_auditor_run", REPO_ROOT / ".codex" / "skills" / "evidence-auditor" / "scripts" / "run.py"
)
_ea = importlib.util.module_from_spec(_spec)
sys.modules["evidence_auditor_run"] = _ea
_spec.loader.exec_module(_ea)


def test_metric_bearing_claim_gap_is_coherent() -> None:
    for claim_text in (
        "The model demonstrates excellent performance with a mean absolute error of 5.06 meV/atom for energy and 128.51 meV/Å for forces.",
        "We reach an RMSE of 0.03 eV on the held-out test set.",
        "The classifier attains an accuracy of 91% on the benchmark.",
        "Latency drops to 12 ms per query.",
    ):
        _, gap, _fix = _ea._gap_for_claim({"claim": claim_text, "type": "empirical"}, "ev")
        # The gap must NOT falsely assert no concrete metric appears.
        assert "no concrete metric" not in gap.lower(), (claim_text, gap)
        assert "underspecified" not in gap.lower(), (claim_text, gap)
        assert "concrete result" in gap.lower(), (claim_text, gap)


def test_metricless_empirical_claim_still_underspecified() -> None:
    # The severity path (major iff "underspecified") is preserved for a claim
    # that genuinely states no metric.
    for claim_text in (
        "Our method substantially improves performance on the task.",
        "The approach yields better results than prior work.",
    ):
        _, gap, _fix = _ea._gap_for_claim({"claim": claim_text, "type": "empirical"}, "ev")
        assert "underspecified" in gap.lower(), (claim_text, gap)


def test_conceptual_claim_gap_unchanged() -> None:
    _, gap, _fix = _ea._gap_for_claim(
        {"claim": "We propose a general-purpose interatomic potential.", "type": "conceptual"}, "ev"
    )
    assert "conceptual claim" in gap.lower(), gap
