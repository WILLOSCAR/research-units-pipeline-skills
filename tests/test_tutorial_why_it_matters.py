"""Regression: source-tutorial 'Why it matters' is learner prose, not planner text.

The checkpoint-brief fix unblocked the full-engine TUTORIAL.md, exposing a new
L2 defect: every module's "Why it matters" block
recited the raw authoring goal ("This matters because the tutorial goal is to Teach
a new engineer ...") and dumped the internal module-output list ("The module output
is: Produce a short explanation or checklist that makes `X` concrete ..."). Both are
planner/authoring artifacts, not reader-facing prose.

`_render_why_it_matters` now states the objective and ties the module to the
tutorial's TOPIC (extracted by `_goal_topic`, which strips the "Teach <audience>"
imperative and the "from the source doc" trailer) and the reading flow — without
reciting the raw goal or the module-output list.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _goal_topic, _render_why_it_matters

_SPEC = {
    "goal": "Teach a new engineer the harness pipeline taxonomy (what each research "
    "Workflow is and when to use it) from the fixed source doc."
}
_MODULE = {
    "title": "Current Recipes and Exporter Migration",
    "objectives": ["Explain `Current Recipes`: how it fits into the end-to-end flow."],
    "outputs": [
        "Produce a short explanation or checklist that makes `Current Recipes` concrete in the tutorial flow.",
        "Update the running example so the module can be reused.",
    ],
}
_PACK = {"objective": "Explain `Current Recipes`: how it fits into the end-to-end flow."}


def test_goal_topic_strips_imperative_and_source_trailer() -> None:
    topic = _goal_topic(_SPEC["goal"])
    assert topic.startswith("the harness pipeline taxonomy"), topic
    assert "Teach" not in topic and "engineer" not in topic, topic
    assert "source doc" not in topic, topic


def test_why_it_matters_does_not_recite_raw_goal() -> None:
    text = _render_why_it_matters(_SPEC, _MODULE, _PACK)
    assert "the tutorial goal is to" not in text, text
    assert "Teach a new engineer" not in text, text


def test_why_it_matters_does_not_dump_module_outputs() -> None:
    text = _render_why_it_matters(_SPEC, _MODULE, _PACK)
    assert "The module output is:" not in text, text
    assert "Produce a short explanation or checklist" not in text, text


def test_why_it_matters_states_objective_and_topic() -> None:
    text = _render_why_it_matters(_SPEC, _MODULE, _PACK)
    # The objective is reframed as a reader OUTCOME, not the raw "Explain X:" directive.
    assert "By the end you should be able to explain `Current Recipes`" in text, text
    assert "Explain `Current Recipes`:" not in text, text  # no bare authoring imperative
    assert "harness pipeline taxonomy" in text, text


def test_why_it_matters_degrades_without_goal() -> None:
    text = _render_why_it_matters({"goal": ""}, _MODULE, _PACK)
    # No goal/topic: fall back to the reader-facing outcome alone.
    assert text == "By the end you should be able to explain `Current Recipes`: how it fits into the end-to-end flow.", text
