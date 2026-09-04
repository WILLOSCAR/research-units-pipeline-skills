"""Regression: the tutorial's Worked example / Check yourself are reader-facing.

When no single running example is supported across the source set
(`running example mode == "none"`), the module's worked-example step fell back
to the string "Use the strongest source-backed example available to illustrate
`<module>` without inventing new context." — an instruction to the *generator*,
not guidance for the learner. It was printed verbatim into every module's
"Worked example" block and, via the exercise seed, into the "Check yourself"
verification step.

The fallback now emits a reader-facing worked step ("Work through `<module>` on
a concrete case from the source notes: state the inputs, apply the concept step
by step, and check the result against the cited snippet."). This locks that the
writer instruction never appears and the reader-facing step does.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _running_example_steps

_LEAK = "without inventing new context"
_LEAK2 = "strongest source-backed example available to illustrate"


def test_unsupported_running_example_step_is_reader_facing() -> None:
    steps = _running_example_steps("Domain Shape", {"mode": "none", "label": ""}, 2)
    assert steps, "expected a fallback worked step"
    joined = " ".join(steps)
    # The old writer instruction is gone.
    assert _LEAK not in joined, joined
    assert _LEAK2 not in joined, joined
    # It reads as guidance to the learner, tied to the concept + source notes.
    assert "Domain Shape" in joined
    assert "source notes" in joined.lower()


def test_supported_running_example_step_unchanged() -> None:
    steps = _running_example_steps(
        "Domain Shape", {"mode": "supported", "label": "pick-and-place arm"}, 3
    )
    assert steps == [
        "Advance `pick-and-place arm` through the decisions introduced in module 3: Domain Shape."
    ], steps


def test_worked_step_leak_absent_from_default_empty_running() -> None:
    # An empty running dict must also avoid the leak (defensive default).
    steps = _running_example_steps("Three Pillars", {}, 1)
    joined = " ".join(steps)
    assert _LEAK not in joined and _LEAK2 not in joined, joined
    assert "Three Pillars" in joined
