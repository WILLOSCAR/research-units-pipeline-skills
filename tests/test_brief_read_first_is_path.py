"""Regression: the research-brief "What to read first" is a path, not a Key-themes echo.

A read of a generated SNAPSHOT.md (real clinical-summarization corpus)
found "What to read first" repeating the "Key themes" one-sentence paper summaries
verbatim (both sections called `_brief_summary` on the same papers), so it gave no
reading-PATH value — no order, no reason to read each first.

`render_research_brief_markdown` now gives each "What to read first" entry a
sequencing reason (Start here / Read next / Then / Finally + what to take from it),
distinct from the Key-themes summary.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import render_research_brief_markdown


def _papers(n: int) -> list[dict]:
    return [
        {"paper_id": f"P{i:04d}", "title": f"Paper {i}",
         "url": f"http://x/{i}",
         "abstract": f"We propose method {i} for test-time adaptation and report distinct result {i} on a benchmark."}
        for i in range(1, n + 1)
    ]


def _section(brief: str, name: str) -> str:
    body = brief.split(f"## {name}", 1)[1]
    return body.split("\n## ", 1)[0]


def test_read_first_is_a_path_not_a_key_themes_echo() -> None:
    brief = render_research_brief_markdown(
        goal="# Goal\n\nOrient me on test-time adaptation.", papers=_papers(12),
        sections=["Methods", "Evaluation"],
    )
    key_themes = _section(brief, "Key themes")
    read_first = _section(brief, "What to read first")
    # Reading-path sequencing markers are present.
    assert "Start here" in read_first, read_first
    assert "Finally" in read_first, read_first
    # The read-first entries must NOT be verbatim copies of the Key-themes summaries.
    kt_bullets = {ln.strip() for ln in key_themes.splitlines() if ln.strip().startswith("- ")}
    rf_bullets = {ln.strip() for ln in read_first.splitlines() if ln.strip().startswith("- ")}
    assert kt_bullets.isdisjoint(rf_bullets), (kt_bullets & rf_bullets)
    # The read-first prose gives a REASON, not a re-summary of the abstract result.
    assert "entry point" in read_first, read_first
    assert "open problems and risks concentrate" in read_first, read_first


def test_read_first_small_set_still_has_ordinals() -> None:
    brief = render_research_brief_markdown(
        goal="# Goal\n\nOrient me.", papers=_papers(2), sections=["Methods"],
    )
    read_first = _section(brief, "What to read first")
    assert "Start here" in read_first, read_first
    # 2 papers: first is "Start here", last is the "Finally" reason.
    assert "read last to see where the open problems and risks concentrate" in read_first, read_first
