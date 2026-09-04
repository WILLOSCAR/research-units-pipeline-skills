"""Regression: the tutorial 'Running example policy' rejects results-claim
fragments and only surfaces a concrete, reusable running example.

A read of a source-tutorial spec built from real embodied-AI paper abstracts
found the Running-example-policy Summary read:

    Use `Effectiveness Of Our Method Showing` as the running example that
    accumulates across modules.

`Effectiveness Of Our Method Showing` is not a runnable example — it is the
object of a results-claim sentence ("demonstrate the effectiveness of our
method, showing significant performance enhancements..."), lifted verbatim by
`_pick_running_example`'s `demonstrates?` extractor and dressed up as a reusable
example.

`_pick_running_example` now gates the extracted phrase with
`_is_reusable_example_phrase`: a running example must name a concrete
artifact/task/system, not an authors' results/quality claim. Rejected phrases
fall through to the honest `mode: none`.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _is_reusable_example_phrase, _pick_running_example


def test_rejects_results_claim_fragments() -> None:
    # These are all lifted from real "demonstrate the <claim>" sentences.
    for claim in [
        "Effectiveness Of Our Method Showing",
        "CANDI Significantly Improves The Performance",
        "Greater Stability And More Reliable",
        "Successful Sim-To-Real Transfer Showcasing Similar",
        "Our Methodology By Transferring Quadrotor",
        "DART S Ability To Correct",  # possessive residue + claim word "ability"
    ]:
        assert not _is_reusable_example_phrase(claim), claim


def test_accepts_concrete_reusable_examples() -> None:
    for good in [
        "pick-and-place robot arm",
        "SHIFT Benchmark",
        "MNIST digit classifier",
        "a Transformer backbone",
        "entropy minimization on CIFAR",
        "Test-Time Adaptation To Data Shift",
    ]:
        assert _is_reusable_example_phrase(good), good


def test_demonstrates_claim_sentence_falls_through_to_none() -> None:
    # A real embodied-AI abstract sentence: the `demonstrates?` extractor would
    # otherwise manufacture "Effectiveness Of Our Method ..." as the example.
    bundle = [
        {
            "source_id": "p0",
            "kind": "arxiv",
            "title": "Robust Test-Time Adaptation",
            "text": (
                "We propose a new adaptation scheme. Experiments demonstrate the "
                "effectiveness of our method, showing significant performance "
                "enhancements on the SHIFT Benchmark."
            ),
        }
    ]
    result = _pick_running_example(bundle)
    assert result["mode"] == "none", result
    assert "Effectiveness" not in result["summary"], result


def test_running_example_around_phrase_still_supported() -> None:
    # The legit `example ... around X` shape must still produce a concrete example.
    bundle = [
        {
            "source_id": "lecture-video",
            "kind": "video",
            "title": "Debugging Rollouts Lecture",
            "text": (
                "The lecture explains rollout inspection and policy failure "
                "analysis. It also demonstrates a compact running example around "
                "a pick-and-place robot arm."
            ),
        }
    ]
    result = _pick_running_example(bundle)
    assert result["mode"] == "supported", result
    assert "Pick-And-Place Robot Arm" in result["label"], result
