"""Regression: the brief's Open-problems limitation is not a Key-themes repeat.

A read of a real-corpus SNAPSHOT.md found the "Reported limitation to
weigh" bullet drawn from a paper already highlighted in "Key themes" (P0004),
so its sentence appeared verbatim in Key themes, What-to-read-first, AND Open
problems. `_brief_risk_bullets` picked the first limitation-cued sentence in
core-set order, which lands on an already-highlighted paper.

It now prefers a limitation from a paper OUTSIDE the highlighted Key-themes set
(chosen[highlighted:]), so Open-problems surfaces a NEW paper's risk, falling
back to the highlighted papers only when the tail states no limitation.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tooling.review_render import _brief_risk_bullets


def _limitation(bullets: list[str]) -> str:
    return next((b for b in bullets if b.startswith("Reported limitation to weigh:")), "")


def test_limitation_prefers_non_highlighted_paper() -> None:
    papers = [
        # 6 highlighted papers; one of them states a limitation.
        {"paper_id": "P0001", "title": "Highlighted A", "url": "u1", "abstract": "We propose A and report gains."},
        {"paper_id": "P0002", "title": "Highlighted B", "url": "u2", "abstract": "We present B."},
        {"paper_id": "P0003", "title": "Highlighted C", "url": "u3", "abstract": "We show C."},
        {"paper_id": "P0004", "title": "Highlighted D", "url": "u4",
         "abstract": "Our results indicate the method still struggles with rare cases and does not consistently improve."},
        {"paper_id": "P0005", "title": "Highlighted E", "url": "u5", "abstract": "We introduce E."},
        {"paper_id": "P0006", "title": "Highlighted F", "url": "u6", "abstract": "We build F."},
        # tail (not highlighted); states its own limitation.
        {"paper_id": "P0007", "title": "Tail G", "url": "u7",
         "abstract": "This approach is limited by its reliance on abstract-only signals and cannot handle long context."},
    ]
    bullets = _brief_risk_bullets(lenses=["methods"], papers=papers, highlighted=6)
    lim = _limitation(bullets)
    assert lim, bullets
    # It draws from the non-highlighted tail (P0007), not the highlighted P0004.
    assert "P0007" in lim, lim
    assert "P0004" not in lim, lim


def test_limitation_falls_back_to_highlighted_when_tail_has_none() -> None:
    papers = [
        {"paper_id": "P0001", "title": "Highlighted A", "url": "u1",
         "abstract": "Our method is limited by the small evaluation set and does not generalize."},
        {"paper_id": "P0002", "title": "Highlighted B", "url": "u2", "abstract": "We present B with gains."},
        # tail states no limitation.
        {"paper_id": "P0007", "title": "Tail G", "url": "u7", "abstract": "We propose G and report strong gains."},
    ]
    bullets = _brief_risk_bullets(lenses=["methods"], papers=papers, highlighted=2)
    lim = _limitation(bullets)
    assert lim, bullets
    # Falls back to the highlighted P0001 limitation (better a real one than none).
    assert "P0001" in lim, lim
