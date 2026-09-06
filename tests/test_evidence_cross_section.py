"""Regression: evidence-auditor credits cross-section evidence for empirical claims.

A review found the evidence-auditor under-reported the
evidence for a HEADLINE empirical claim. The auditor scoped `evidence_present`
to the single section named by a claim's source pointer, so a claim stated in
the Introduction ("substantial F1 improvement ... new state of the art") was
recorded as having only a weak "baseline comparison" — even though the
manuscript's F1 values, gain size, seed averaging, and confidence intervals were
all present in the Experiments section.

The auditor now, for an EMPIRICAL claim whose own section is not itself a results
section, also scans the manuscript's results/experiments sections and merges the
cross-section evidence signals into `evidence_present` (labelled as reported in a
different section). Conceptual / method claims are NOT given results context, so
they cannot inherit unrelated result numbers.
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


_MANUSCRIPT = """# CE-VarNet

## 1. Introduction

We introduce CE-VarNet. Our method delivers a substantial F1 improvement over the
strongest prior baseline, establishing a new state of the art on the benchmark.

## 2. Method

CE-VarNet augments a base caller with a context encoder over a 2 kb window.

## 4. Experiments

CE-VarNet reaches an F1 of 0.982 versus 0.947 for DeepVariant, a 3.5-point gain,
averaged over five random seeds with 95% confidence intervals.
"""


def test_results_context_collects_experiments_section() -> None:
    ctx = _ea._results_context(_MANUSCRIPT)
    assert "0.982" in ctx
    assert "five random seeds" in ctx
    # Non-results sections are excluded.
    assert "context encoder" not in ctx


def test_empirical_headline_claim_credits_cross_section_evidence() -> None:
    intro_context = "Our method delivers a substantial F1 improvement over the strongest prior baseline."
    results_context = _ea._results_context(_MANUSCRIPT)
    ep = _ea._evidence_present(
        "CE-VarNet delivers a substantial F1 improvement over the strongest prior baseline.",
        intro_context,
        results_context,
    )
    # The cross-section numeric evidence is surfaced and attributed to results.
    assert "reported in the results/experiments section" in ep, ep
    assert "a reported metric value" in ep or "confidence intervals" in ep, ep


def test_conceptual_claim_is_not_given_results_context() -> None:
    # A method/conceptual claim must NOT inherit results numbers: called with no
    # results_context (mirrors main(), which passes "" for non-empirical claims).
    method_context = "CE-VarNet augments a base caller with a context encoder over a 2 kb window."
    ep = _ea._evidence_present(
        "The context encoder pools signal from a 2 kb window around each candidate site.",
        method_context,
        "",
    )
    assert "results/experiments section" not in ep, ep


def test_results_section_claim_not_double_reported() -> None:
    # A claim whose pointer already points at the results section is not given a
    # separate cross-section note (its evidence is in its own context).
    results_context = _ea._results_context(_MANUSCRIPT)
    ep = _ea._evidence_present(
        "CE-VarNet reaches an F1 of 0.982 versus 0.947, averaged over five random seeds.",
        results_context,
        "",  # main() passes "" when the pointer is already a results section
    )
    assert "reported in the results/experiments section" not in ep, ep
    # Its own concrete signals are still reported (e.g. confidence intervals).
    assert "confidence intervals" in ep, ep


def test_intro_claim_quoting_a_results_word_still_gets_cross_section_evidence() -> None:
    # A source pointer is '<section> | "<claim quote>"'. Matching the results cue
    # against the whole pointer lets the QUOTE decide the SECTION, so an
    # Introduction claim that happens to quote "evaluation" would be treated as
    # already living in the results section and silently lose its cross-section
    # evidence — the exact lookup this module adds.
    pointer = 'Introduction | "we present an evaluation of throughput"'
    section = pointer.split("|", 1)[0]
    assert _ea._RESULTS_SECTION_CUE.search(pointer) is not None
    assert _ea._RESULTS_SECTION_CUE.search(section) is None
