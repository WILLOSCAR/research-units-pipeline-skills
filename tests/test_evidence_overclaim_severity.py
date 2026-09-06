"""Regression: evidence-auditor flags unqualified overclaims as MAJOR.

A review of a manuscript making unqualified superiority
claims — "no downsides observed", "never regresses", "strictly better" — with no
Limitations section found the evidence-auditor classified EVERY gap as minor
(the only path to "major" was the word "underspecified"), so an overclaiming
paper got 0 major concerns and a bland "borderline".

The auditor now detects unqualified superiority / absoluteness claims that lack a
scope qualifier and flags them as a MAJOR overclaim soundness gap. Hedged /
scoped strong claims ("improves by 6.4 points over five seeds", "on three
workloads") are NOT flagged.
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


def test_unqualified_overclaims_flagged() -> None:
    for claim in (
        "AP never regresses on any workload we tried.",
        "Adaptive prefetching is strictly better than static prefetching.",
        "The method has no downsides observed in practice.",
        "It always wins across settings.",
    ):
        gap = _ea._overclaim_gap(claim, "evidence")
        assert gap is not None, claim
        assert "overclaim" in gap[1].lower(), gap


def test_hedged_or_scoped_claims_not_flagged() -> None:
    for claim in (
        "On three workloads AP improves throughput by 31% over static prefetching.",
        "AP improves accuracy by 6.4 points over five seeds with 95% confidence intervals.",
        "The method may improve robustness under distribution shift.",
        "CE-VarNet improves F1 by 5.1 points on the TCGA benchmark.",
    ):
        assert _ea._overclaim_gap(claim, "evidence") is None, claim


def test_hedge_suppresses_a_real_cue() -> None:
    # These DO carry an overclaim cue, so they exercise the hedge branch itself
    # rather than exiting at the cue test. Without _HEDGE_CUE they would be MAJOR.
    for claim in (
        "AP never regresses in our experiments.",
        "The method may be strictly better under these assumptions.",
    ):
        assert _ea._OVERCLAIM_CUE.search(claim) is not None, claim
        assert _ea._overclaim_gap(claim, "evidence") is None, claim


def test_ordinary_technical_absolutes_are_not_overclaims() -> None:
    # A theorem, a protocol statement, a robustness spec, and a scoped claim are
    # ordinary technical English. Flagging them MAJOR pushes honest manuscripts
    # toward rejection, so the cue list must not match them.
    for claim in (
        "The scheduler is guaranteed to converge under Assumption 2.",
        "In all cases we report the mean over five random seeds.",
        "The watchdog never fails to fire within the timeout window.",
        "The method universally applies to the three graph families we study.",
    ):
        assert _ea._overclaim_gap(claim, "evidence") is None, claim
