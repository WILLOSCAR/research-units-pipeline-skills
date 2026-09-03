"""Regression: idea-brainstorm '### What the current literature actually shows'
bullets don't run the result excerpt into 'Open gap:' and don't leak LaTeX escapes.

A read of generated idea-brainstorm memos found two defects in the
per-direction `literature_suggests` bullets:
  1. The result excerpt was a clipped fragment with no terminal punctuation, so
     the appended 'Open gap:' clause ran onto it as one sentence
     ('... to Crazyflie 2.1 Open gap: ...', '... reports of MIMIC-CXR, Open gap: ...').
  2. A LaTeX-escaped percent leaked into reader text ('attains a 35\\% success rate').
Fixes in tooling/ideation.py: clean_text() unescapes LaTeX '\\%'/'\\&'/'\\_'/'\\#'/'\\$';
_paper_annotation() runs the result excerpt through _ensure_sentence_end() before
appending ' Open gap: ...'.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.ideation import _ensure_sentence_end, _paper_annotation, clean_text


def test_clean_text_unescapes_latex_punctuation() -> None:
    assert clean_text("attains a 35\\% average success rate") == "attains a 35% average success rate"
    assert clean_text("cost \\$5 and A \\& B \\_ C \\# D") == "cost $5 and A & B _ C # D"
    # A real percent is untouched.
    assert clean_text("45% vs 36%") == "45% vs 36%"


def test_ensure_sentence_end_terminates_fragments() -> None:
    assert _ensure_sentence_end("transferring controllers to Crazyflie 2.1") == "transferring controllers to Crazyflie 2.1."
    assert _ensure_sentence_end("reports of MIMIC-CXR,") == "reports of MIMIC-CXR."
    assert _ensure_sentence_end("trailing colon:") == "trailing colon."
    # Existing sentence punctuation is preserved.
    assert _ensure_sentence_end("already done.") == "already done."
    assert _ensure_sentence_end("a question?") == "a question?"
    assert _ensure_sentence_end("") == ""


def _note(title: str, results: list[str]) -> dict:
    return {"paper_id": "p1", "title": title, "key_results": results}


def test_paper_annotation_no_runon_before_open_gap() -> None:
    note = _note("Sim-to-Real Transfer", ["transferring quadrotor controllers from simulators to Crazyflie 2.1"])
    line = _paper_annotation(note, "observability granularity", "Embodied Adaptation")
    # 'Open gap:' must be preceded by terminal punctuation, never a run-on.
    idx = line.find("Open gap:")
    assert idx > 0, line
    preceding = line[:idx].rstrip()
    assert preceding.endswith((".", "!", "?")), line


def test_paper_annotation_no_latex_percent_leak() -> None:
    note = _note("World-Action Models", ["our policy attains a 35\\% average success rate"])
    line = _paper_annotation(note, "observability granularity", "Embodied Adaptation")
    assert "\\%" not in line, line
