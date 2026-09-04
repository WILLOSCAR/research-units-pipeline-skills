"""Regression: the tutorial "Why it matters" prose never pastes the raw goal.

A read of a generated TUTORIAL.md (goal "Teach a new contributor the
pipeline taxonomy: recipe families and when to use each, from the source doc")
found every module's "Why it matters" grafting the raw authoring imperative into
prose: "... builds your understanding of Teach a new contributor the pipeline
taxonomy ... and sets up the module that follows." — the malformed "understanding
of Teach ...".

Root cause: `_goal_topic`'s imperative-strip required a fixed audience noun
(engineer/reader/developer/...) right after "Teach"; "contributor" was not in the
list, so the whole raw goal survived. `_goal_topic` now strips a leading
teaching-imperative + a generic short audience phrase (article + adjectives +
role) up to the topic lead-in, so an unusual role no longer leaks the goal.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _goal_topic, _render_why_it_matters


def test_goal_topic_strips_unusual_audience_roles() -> None:
    assert _goal_topic(
        "Teach a new contributor the pipeline taxonomy: recipe families and when to use each, from the source doc."
    ) == "the pipeline taxonomy: recipe families and when to use each"
    assert _goal_topic("Teach a practitioner how the loop works from the doc.") == "how the loop works"
    assert _goal_topic("Teach a scientist the evaluation protocol from the source.") == "the evaluation protocol"
    # A walk/guide "through" connector is consumed, keeping the topic (the
    # source-type trailer list covers source/repo/docs/video/material/paper).
    assert _goal_topic("Guide a new team member through the deployment steps from the source doc.") == "the deployment steps"


def test_goal_topic_preserves_original_engineer_goal() -> None:
    # The original goal (fixed audience noun) still strips correctly.
    assert _goal_topic(
        "Teach a new engineer the harness pipeline taxonomy (what each research Workflow is and when to use it) from the fixed source doc."
    ) == "the harness pipeline taxonomy (what each research Workflow is and when to use it)"


def test_goal_topic_leaves_non_teach_goal_unchanged() -> None:
    # A non-teaching goal must not be mangled.
    assert _goal_topic("Produce a compact research brief on test-time adaptation.") == "Produce a compact research brief on test-time adaptation"


def test_why_it_matters_does_not_paste_raw_goal() -> None:
    spec = {"goal": "Teach a new contributor the pipeline taxonomy: recipe families and when to use each, from the source doc."}
    module = {"title": "Current Recipes and Exporter Migration", "objectives": ["Explain `Current Recipes`: how it fits."]}
    pack = {"objective": "Explain `Current Recipes`: how it fits."}
    why = _render_why_it_matters(spec, module, pack)
    assert "understanding of Teach" not in why, why
    assert "Teach a new contributor" not in why, why
    assert "the pipeline taxonomy: recipe families and when to use each" in why, why
