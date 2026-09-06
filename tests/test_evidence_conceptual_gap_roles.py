"""Regression: conceptual-claim evidence gaps are role-specific, not one template.

A review of a real ml-interatomic manuscript ("Universal MLIPs are Ready for
Phonons" — a ~10,000-calculation benchmark whose headline finding is
"some models achieve high accuracy ... others still exhibit substantial
inaccuracies") found the evidence-auditor emitted the IDENTICAL gap + minimal-fix
for all seven conceptual claims: "The conceptual claim needs a clearer boundary and
stronger relation to prior work." A results-reporting finding, a methods/dataset
statement, and a background claim all got the same prior-work advice, giving the
referee no per-claim signal.

`_gap_for_claim`'s conceptual branch now routes to `_conceptual_gap`, which
differentiates by claim role: a results/findings sentence needs the missing
quantitative backing; a methods/dataset sentence needs provenance/coverage/protocol;
a background/motivation sentence keeps the boundary + prior-work gap. The
background-claim wording is preserved so the referee-render conceptual path is
unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import importlib.util

_SPEC = importlib.util.spec_from_file_location(
    "_evidence_auditor_run",
    REPO_ROOT / ".codex" / "skills" / "evidence-auditor" / "scripts" / "run.py",
)
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)

_gap_for_claim = _MOD._gap_for_claim


def _gap(text: str) -> str:
    return _gap_for_claim({"claim": text, "type": "conceptual"}, "ev")[1]


def _fix(text: str) -> str:
    return _gap_for_claim({"claim": text, "type": "conceptual"}, "ev")[2]


def test_results_finding_gap_asks_for_numbers() -> None:
    gap = _gap("The results reveal that some models achieve high accuracy in predicting harmonic phonon properties.")
    assert "qualitative finding" in gap.lower(), gap
    assert "prior work" not in gap.lower(), gap
    assert "metric" in gap.lower() or "magnitude" in gap.lower(), gap


def test_negative_finding_also_routed_to_findings() -> None:
    gap = _gap("However, others still exhibit substantial inaccuracies, even if they excel in energy and forces.")
    assert "qualitative finding" in gap.lower(), gap


def test_methods_dataset_gap_asks_for_provenance() -> None:
    gap = _gap("Using around 10 000 ab initio phonon calculations, we evaluate model performance across parameters.")
    assert "provenance" in gap.lower() and "coverage" in gap.lower(), gap
    fix = _fix("Using around 10 000 ab initio phonon calculations, we evaluate model performance.")
    assert "protocol" in fix.lower(), fix


def test_background_claim_keeps_boundary_prior_work_gap() -> None:
    # A background/motivation claim is unchanged (preserves the referee-render path).
    gap = _gap("There has been an ongoing race to develop the best universal machine-learning interatomic potential.")
    assert "clearer boundary" in gap.lower() and "prior work" in gap.lower(), gap


def test_three_roles_yield_three_distinct_gaps() -> None:
    finding = _gap("The results reveal that some models achieve high accuracy.")
    methods = _gap("Using around 10 000 calculations, we evaluate model performance.")
    background = _gap("This progress has led to increasingly accurate models over the years.")
    assert len({finding, methods, background}) == 3, (finding, methods, background)


def test_empirical_branch_unchanged() -> None:
    # The empirical routing (metric-bearing vs underspecified) is untouched.
    metric = _gap_for_claim(
        {"claim": "Our model reaches a mean absolute error of 5.06 meV/atom.", "type": "empirical"}, "ev"
    )[1]
    assert "concrete result" in metric.lower(), metric
    under = _gap_for_claim(
        {"claim": "Our method substantially improves performance.", "type": "empirical"}, "ev"
    )[1]
    assert "underspecified" in under.lower(), under
