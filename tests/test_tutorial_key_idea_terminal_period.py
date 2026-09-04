"""Regression: the tutorial 'Key idea' line ends with terminal punctuation.

A read of a generated tutorial (real repo docs) found a module's Key idea
line read '- **Research Loop Architecture**: It is the one part of the system we
can point at line-by-line in code, and it never trusts a self-reported verdict'
— a complete sentence with NO terminal period, because the stored snippet is a
contiguous source substring (grounding contract) that can be clipped without its
period.

`_render_key_idea` now adds a terminal period for DISPLAY when the body is
sentence-like and lacks end punctuation; the stored snippet is untouched, so the
grounding check (which compares snippet['snippet']) is unaffected.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.tutorial_workflows import _render_key_idea


def _pack(snippet_body: str) -> dict:
    return {"source_snippets": [{"source_id": "s", "title": "Research Loop Architecture", "snippet": snippet_body}]}


def test_key_idea_gets_terminal_period_when_missing() -> None:
    lines = _render_key_idea({"title": "Research Loop Architecture"},
                             _pack("It is the one part of the system we can point at line-by-line in code"))
    assert lines[0].endswith("."), lines
    assert lines[0] == "- **Research Loop Architecture**: It is the one part of the system we can point at line-by-line in code.", lines


def test_key_idea_keeps_existing_terminal_punctuation() -> None:
    for ending in (".", "!", "?"):
        body = f"A polished report is insufficient without provenance{ending}"
        lines = _render_key_idea({"title": "X"}, _pack(body))
        assert lines[0].endswith(ending), lines
        # No double punctuation.
        assert not lines[0].endswith(ending + "."), lines


def test_key_idea_does_not_append_after_a_code_span() -> None:
    # A body ending on a backtick code span must not get a period glued to it.
    lines = _render_key_idea({"title": "X"}, _pack("The read-only workspace is `.harness`"))
    assert lines[0].endswith("`"), lines
    assert not lines[0].endswith("`."), lines


def test_key_idea_fallback_unchanged_when_no_snippet() -> None:
    lines = _render_key_idea({"title": "Research Loop"}, {"source_snippets": []})
    assert lines[0].startswith("- Build the module around"), lines
