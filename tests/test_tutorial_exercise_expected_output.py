"""Regression: module exercise expected_output is a learner answer, not an authoring directive.

The c91 unblock opened the source-tutorial exercises to review; on the real
SCHEMAS.md module plan every "Check yourself" block's expected_output was the
module's first AUTHORING output — "Produce a short explanation or checklist that
makes `X` concrete in the tutorial flow" — a directive to the tutorial author, not a
description of the learner's expected answer.

`add_module_exercises` now frames expected_output as the substance of a correct
learner response (what the concept is, how the module's concepts fit, how it applies
to the running example, traceable to sources), not the authoring output.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import add_module_exercises


def _module() -> dict:
    return {
        "id": "M01",
        "title": "Schemas and Run Projection Status",
        "concepts": ["c01-schemas", "c02-run-projection-status"],
        "objectives": ["Explain `Schemas`."],
        "outputs": [
            "Produce a short explanation or checklist that makes `Schemas` concrete in the tutorial flow.",
            "Update the running example so the module can be reused.",
        ],
        "running_example_steps": ["Work through Schemas on a concrete case."],
    }


def test_expected_output_is_not_the_authoring_directive() -> None:
    plan = add_module_exercises({"modules": [_module()]})
    ex = plan["modules"][0]["exercises"][0]
    assert "Produce a short explanation or checklist" not in ex["expected_output"], ex
    assert "in the tutorial flow" not in ex["expected_output"], ex


def test_expected_output_describes_a_learner_answer() -> None:
    plan = add_module_exercises({"modules": [_module()]})
    ex = plan["modules"][0]["exercises"][0]
    low = ex["expected_output"].lower()
    assert "learner" in low, ex
    assert "Schemas and Run Projection Status" in ex["expected_output"], ex
    assert "source" in low, ex  # traceability to sources


def test_exercise_still_has_prompt_and_verification() -> None:
    plan = add_module_exercises({"modules": [_module()]})
    ex = plan["modules"][0]["exercises"][0]
    assert ex["prompt"], ex
    assert len(ex["verification_steps"]) >= 3, ex


def test_existing_exercises_preserved() -> None:
    m = _module()
    m["exercises"] = [{"prompt": "keep", "expected_output": "keep", "verification_steps": ["k"]}]
    plan = add_module_exercises({"modules": [m]})
    assert plan["modules"][0]["exercises"][0]["prompt"] == "keep"
