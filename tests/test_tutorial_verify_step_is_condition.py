"""Regression: the tutorial 'Check yourself' third verify step is a CONDITION,
not a pasted DO-THIS instruction.

A read of a generated tutorial (real repo docs) found the third
verification step read 'Check that the result connects cleanly to the running
example step: Work through `<module>` on a concrete case from the source notes:
state the inputs, apply the concept step by step, and check the result against
the cited snippet.' — it pasted the running-example STEP (a learner DO-THIS
task) after 'connects cleanly to the running example step:', so the verify item
became a fresh multi-step task rather than a condition to confirm. The first
two rubric-style verify items were judged acceptable and left unchanged.

`add_module_exercises` now renders the third verify step as a verification
condition: it names the supported running example when one exists, else a generic
concrete-case condition — never a pasted DO-THIS instruction.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import add_module_exercises


def _third_verify(module: dict) -> str:
    return module["exercises"][0]["verification_steps"][2]


def test_third_verify_is_a_condition_not_a_do_this_task_none_mode() -> None:
    # mode:none running example -> the step is a generic "Work through X ..." task.
    plan = {"modules": [{
        "title": "Research Loop Architecture",
        "running_example_steps": [
            "Work through `Research Loop Architecture` on a concrete case from the source notes: "
            "state the inputs, apply the concept step by step, and check the result against the cited snippet."
        ],
    }]}
    out = add_module_exercises(plan)
    third = _third_verify(out["modules"][0])
    # The verify item is a condition ("Check that the result ...").
    assert third.startswith("Check that the result"), third
    # It must NOT paste the DO-THIS instruction verbatim.
    assert "connects cleanly to the running example step:" not in third, third
    assert "Work through `" not in third, third
    # It states the observable subcriteria.
    assert "identifies the case inputs" in third, third
    assert "validates the outcome against a cited source snippet" in third, third


def test_third_verify_names_supported_running_example() -> None:
    plan = {"modules": [{
        "title": "Retrieval Policy",
        "running_example_steps": [
            "Advance `pick-and-place robot arm` through the decisions introduced in module 1: Retrieval Policy."
        ],
    }]}
    out = add_module_exercises(plan)
    third = _third_verify(out["modules"][0])
    assert third.startswith("Check that the result advances the running example `pick-and-place robot arm`"), third
    assert "Advance `" not in third, third  # the DO-THIS verb is not pasted


def test_all_three_verify_steps_present_and_first_two_unchanged() -> None:
    plan = {"modules": [{"title": "Schemas", "running_example_steps": []}]}
    out = add_module_exercises(plan)
    steps = out["modules"][0]["exercises"][0]["verification_steps"]
    assert len(steps) == 3, steps
    assert steps[0] == "Check that the result names the core concepts behind `Schemas`.", steps
    assert steps[1] == "Check that the result can be traced back to at least one source note or snippet.", steps
    assert steps[2].startswith("Check that the result works the concept on a concrete case"), steps
