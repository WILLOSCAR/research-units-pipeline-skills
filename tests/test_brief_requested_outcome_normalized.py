"""Regression: the research-brief Scope 'Requested outcome' normalizes prompt
residue but leaves a clean declarative request untouched.

A read of a research brief found the 'Requested outcome:' line echoing the
raw goal verbatim, so a conversational request leaked into the finished
deliverable: a question to the assistant ('Can you find me the key papers ...?'),
first-person chatter ('I need ... help me get oriented'), or a bare keyword
fragment ('test-time adaptation distribution shift') all read as the original
prompt rather than a stated outcome.

`render_research_brief_markdown` now runs the goal through
`_normalize_requested_outcome`: a clean declarative request (opens with an
outcome verb, not a question or first person) is kept verbatim; question /
first-person / bare-fragment goals are recast into 'Orient the reader to
<topic>.' on the goal's own topic words.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import _normalize_requested_outcome


def test_clean_declarative_request_is_kept() -> None:
    goal = ("# Goal\n\nProduce a compact, traceable research brief on test-time adaptation "
            "under distribution shift, with a bounded reading path and explicit open risks.")
    out = _normalize_requested_outcome(goal)
    assert out.startswith("Produce a compact, traceable research brief"), out
    assert out.endswith("."), out


def test_question_to_assistant_is_recast() -> None:
    out = _normalize_requested_outcome("# Goal\n\nCan you find me the key papers on clinical note summarization?")
    assert not out.rstrip().endswith("?"), out
    assert "Can you" not in out and "find me" not in out, out
    assert out.startswith("Orient the reader to"), out
    assert "clinical note summarization" in out, out


def test_first_person_chatter_is_stripped() -> None:
    out = _normalize_requested_outcome("# Goal\n\nI need to understand TTA for my thesis, help me get oriented")
    assert out.startswith("Orient the reader to"), out
    assert "help me" not in out and "for my thesis" not in out, out
    assert "I need" not in out, out
    # An acronym must not be mangled to lowercase ("TTA" not "tTA").
    assert "TTA" in out, out


def test_bare_fragment_is_recast() -> None:
    out = _normalize_requested_outcome("# Goal\n\ntest-time adaptation distribution shift")
    assert out == "Orient the reader to test-time adaptation distribution shift.", out


def test_empty_goal_falls_back() -> None:
    assert _normalize_requested_outcome("# Goal\n\n") == "Orient the reader to the target topic."
